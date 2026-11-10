import logging
import os
import secrets
import time
from uuid import UUID

import psycopg
import redis
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

router = APIRouter()
log = logging.getLogger(__name__)


def connect():
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def reply(status_code, content):
    return JSONResponse(status_code=status_code, content=content)


def update_counters(performance_id, event_id, released):
    try:
        client = redis.Redis.from_url(
            os.environ["REDIS_URL"], decode_responses=True, socket_timeout=2
        )
        minute = int(time.time() // 60)
        current = f"sales:trending:{minute}"
        sold_key = f"sales:sold:{performance_id}"
        left_key = f"sales:left:{performance_id}"
        track_sold = client.exists(sold_key) == 1
        track_left = client.exists(left_key) == 1

        pipe = client.pipeline()
        for section_id, quantity in released.items():
            if track_sold:
                pipe.hincrby(sold_key, str(section_id), -quantity)
            if track_left:
                pipe.hincrby(left_key, str(section_id), quantity)
        pipe.zincrby(current, -sum(released.values()), str(event_id))
        pipe.expire(current, 3660)
        sources = [f"sales:trending:{minute - i}" for i in range(60)]
        pipe.zunionstore("sales:trending", sources)
        pipe.zremrangebyscore("sales:trending", "-inf", 0)
        pipe.execute()
    except Exception:
        log.warning("could not update redis counters", exc_info=True)


def refund_order(cur, order_id, total):
    cur.execute(
        """
        UPDATE tickets SET status = 'cancelled'
        WHERE order_id = %s AND status <> 'cancelled'
        RETURNING section_id
        """,
        (order_id,),
    )
    released = {}
    for (section_id,) in cur.fetchall():
        released[section_id] = released.get(section_id, 0) + 1

    cur.execute("UPDATE orders SET status = 'refunded' WHERE id = %s", (order_id,))

    cur.execute(
        """
        SELECT method FROM payments
        WHERE order_id = %s AND status = 'approved'
        ORDER BY created_at LIMIT 1
        """,
        (order_id,),
    )
    row = cur.fetchone()
    method = row[0] if row else "card"

    cur.execute(
        """
        INSERT INTO payments (order_id, amount, method, status, provider_reference)
        VALUES (%s, %s, %s, 'refunded', %s)
        """,
        (order_id, total, method, "REF-" + secrets.token_hex(8).upper()),
    )
    return released


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: UUID, x_user_id: UUID = Header()):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.customer_id, o.status, o.total, o.performance_id,
                       p.event_id, p.starts_at - now() >= interval '48 hours'
                FROM orders o
                JOIN performances p ON p.id = o.performance_id
                WHERE o.id = %s
                FOR UPDATE OF o
                """,
                (order_id,),
            )
            order = cur.fetchone()
            if order is None or order[0] != x_user_id:
                return reply(404, {"detail": "order not found"})
            _, status, total, performance_id, event_id, early_enough = order

            if status == "refunded":
                return reply(409, {"detail": "order already refunded"})
            if status != "paid":
                return reply(409, {"detail": f"only paid orders can be cancelled, this one is {status}"})
            if not early_enough:
                return reply(
                    409,
                    {"detail": "orders can only be cancelled up to 48 hours before the performance"},
                )

            released = refund_order(cur, order_id, total)

    update_counters(performance_id, event_id, released)
    return {"result": "refunded", "order_id": str(order_id), "refunded_amount": str(total)}


@router.post("/performances/{performance_id}/cancel")
def cancel_performance(performance_id: UUID):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, status, ends_at < now()
                FROM performances WHERE id = %s FOR UPDATE
                """,
                (performance_id,),
            )
            perf = cur.fetchone()
            if perf is None:
                return reply(404, {"detail": "performance not found"})
            event_id, status, already_over = perf

            if status == "cancelled":
                return reply(409, {"detail": "performance already cancelled"})
            if already_over:
                return reply(409, {"detail": "performance already finished"})

            cur.execute(
                "UPDATE performances SET status = 'cancelled' WHERE id = %s",
                (performance_id,),
            )

            cur.execute(
                "SELECT id, total FROM orders WHERE performance_id = %s AND status = 'paid' FOR UPDATE",
                (performance_id,),
            )
            paid_orders = cur.fetchall()

            released = {}
            refunded_total = 0
            for order_id, total in paid_orders:
                for section_id, quantity in refund_order(cur, order_id, total).items():
                    released[section_id] = released.get(section_id, 0) + quantity
                refunded_total += total

            cur.execute(
                "UPDATE orders SET status = 'cancelled' WHERE performance_id = %s AND status = 'pending'",
                (performance_id,),
            )
            cur.execute(
                "UPDATE holds SET status = 'released' WHERE performance_id = %s AND status = 'active'",
                (performance_id,),
            )

    update_counters(performance_id, event_id, released)
    return {
        "result": "cancelled",
        "performance_id": str(performance_id),
        "orders_refunded": len(paid_orders),
        "refunded_amount": str(refunded_total),
    }