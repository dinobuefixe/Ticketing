import logging
import os
import secrets
import string
import time
from decimal import Decimal
from typing import Literal
from uuid import UUID

import psycopg
import redis
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
log = logging.getLogger(__name__)

CODE_ALPHABET = string.ascii_uppercase + string.digits


class CheckoutRequest(BaseModel):
    hold_id: UUID
    simulate: Literal["approved", "declined"]
    method: Literal["card", "mbway", "multibanco"] = "card"
    promo_code: str | None = None


def connect():
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def refuse(status_code, detail):
    return JSONResponse(status_code=status_code, content={"detail": detail}), None


def ticket_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))


def update_counters(performance_id, event_id, sold):
    try:
        client = redis.Redis.from_url(
            os.environ["REDIS_URL"], decode_responses=True, socket_timeout=2
        )
        minute = int(time.time() // 60)
        current = f"sales:trending:{minute}"

        pipe = client.pipeline()
        for section_id, quantity in sold.items():
            pipe.hincrby(f"sales:sold:{performance_id}", str(section_id), quantity)
        pipe.zincrby(current, sum(sold.values()), str(event_id))
        pipe.expire(current, 3660)
        sources = [f"sales:trending:{minute - i}" for i in range(60)]
        pipe.zunionstore("sales:trending", sources)
        pipe.zremrangebyscore("sales:trending", "-inf", 0)
        pipe.execute()
    except Exception:
        log.warning("could not update redis counters", exc_info=True)


def process(body, user_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT customer_id, performance_id, status, expires_at > now() "
                "FROM holds WHERE id = %s FOR UPDATE",
                (body.hold_id,),
            )
            hold = cur.fetchone()
            if hold is None or hold[0] != user_id:
                return refuse(404, "hold not found")
            customer_id, performance_id, hold_status, not_expired = hold

            cur.execute(
                "SELECT id, status FROM orders WHERE hold_id = %s "
                "ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
                (body.hold_id,),
            )
            order = cur.fetchone()
            order_id = None
            if order is not None:
                order_id, order_status = order
                if order_status == "paid":
                    return refuse(409, "order already paid")
                if order_status != "pending":
                    return refuse(409, f"order is {order_status}")

            if hold_status == "converted":
                return refuse(409, "hold already paid")

            if hold_status != "active" or not not_expired:
                if order_id is not None:
                    cur.execute(
                        "UPDATE orders SET status = 'cancelled' WHERE id = %s", (order_id,)
                    )
                if hold_status == "active":
                    cur.execute(
                        "UPDATE holds SET status = 'expired' WHERE id = %s", (body.hold_id,)
                    )
                return refuse(409, "hold expired")

            cur.execute("SELECT event_id FROM performances WHERE id = %s", (performance_id,))
            event_id = cur.fetchone()[0]

            cur.execute(
                """
                SELECT hi.section_id, hi.seat_id, COALESCE(hi.places, 1), sp.price
                FROM hold_items hi
                LEFT JOIN section_prices sp
                       ON sp.performance_id = %s AND sp.section_id = hi.section_id
                WHERE hi.hold_id = %s
                """,
                (performance_id, body.hold_id),
            )
            items = cur.fetchall()
            if not items:
                return refuse(409, "hold has no items")
            if any(item[3] is None for item in items):
                return refuse(409, "a section in the hold has no price")
            subtotal = sum((item[3] * item[2] for item in items), Decimal("0"))

            promo_id = None
            discount = Decimal("0")
            if body.promo_code:
                cur.execute(
                    """
                    SELECT id, percent_off, amount_off, event_id,
                           now() BETWEEN valid_from AND valid_until,
                           uses < max_uses
                    FROM promo_codes
                    WHERE code = %s
                    FOR UPDATE
                    """,
                    (body.promo_code,),
                )
                promo = cur.fetchone()
                if promo is None:
                    return refuse(404, "promo code not found")
                promo_id, percent, amount, promo_event, in_period, has_uses = promo
                if not in_period:
                    return refuse(409, "promo code is not valid now")
                if promo_event is not None and promo_event != event_id:
                    return refuse(409, "promo code does not apply to this event")
                if not has_uses:
                    return refuse(409, "promo code has no uses left")
                if percent is not None:
                    discount = (subtotal * percent / Decimal(100)).quantize(Decimal("0.01"))
                else:
                    discount = min(amount, subtotal)
            total = subtotal - discount

            if order_id is None:
                cur.execute(
                    """
                    INSERT INTO orders (customer_id, performance_id, hold_id,
                                        promo_code_id, status, total)
                    VALUES (%s, %s, %s, %s, 'pending', %s)
                    RETURNING id
                    """,
                    (customer_id, performance_id, body.hold_id, promo_id, total),
                )
                order_id = cur.fetchone()[0]
            else:
                cur.execute(
                    "UPDATE orders SET promo_code_id = %s, total = %s WHERE id = %s",
                    (promo_id, total, order_id),
                )

            provider_reference = "SIM-" + secrets.token_hex(8).upper()
            codes = []
            try:
                with conn.transaction():
                    cur.execute(
                        """
                        INSERT INTO payments (order_id, amount, method, status,
                                              provider_reference)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (order_id, total, body.method, body.simulate, provider_reference),
                    )
                    if body.simulate == "approved":
                        for section_id, seat_id, quantity, price in items:
                            for _ in range(quantity):
                                code = ticket_code()
                                cur.execute(
                                    """
                                    INSERT INTO tickets (order_id, performance_id, section_id,
                                                         seat_id, price_paid, code, status)
                                    VALUES (%s, %s, %s, %s, %s, %s, 'valid')
                                    """,
                                    (order_id, performance_id, section_id, seat_id, price, code),
                                )
                                codes.append(code)
                        if promo_id is not None:
                            cur.execute(
                                "UPDATE promo_codes SET uses = uses + 1 WHERE id = %s",
                                (promo_id,),
                            )
                        cur.execute(
                            "UPDATE orders SET status = 'paid', paid_at = now() WHERE id = %s",
                            (order_id,),
                        )
                        cur.execute(
                            "UPDATE holds SET status = 'converted' WHERE id = %s",
                            (body.hold_id,),
                        )
            except psycopg.errors.CheckViolation as exc:
                message = exc.diag.message_primary or ""
                if "standing section" in message:
                    return refuse(409, "section is sold out")
                if "promo code" in message:
                    return refuse(409, "promo code has no uses left")
                raise
            except psycopg.errors.UniqueViolation as exc:
                if exc.diag.constraint_name == "tickets_one_valid_seat":
                    return refuse(409, "seat already sold")
                raise

            if body.simulate == "declined":
                return (
                    JSONResponse(
                        status_code=402,
                        content={
                            "result": "declined",
                            "order_id": str(order_id),
                            "detail": "payment declined, the hold is still active",
                        },
                    ),
                    None,
                )

            sold = {}
            for section_id, seat_id, quantity, price in items:
                sold[section_id] = sold.get(section_id, 0) + quantity
            return (
                JSONResponse(
                    status_code=200,
                    content={
                        "result": "approved",
                        "order_id": str(order_id),
                        "total": str(total),
                        "ticket_codes": codes,
                    },
                ),
                (performance_id, event_id, sold),
            )


@router.post("/checkout")
def checkout(body: CheckoutRequest, x_user_id: UUID = Header()):
    response, sale = process(body, x_user_id)
    if sale is not None:
        update_counters(*sale)
    return response