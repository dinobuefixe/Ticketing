import json
import os
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.cache import ensure_performance_loaded
from app.clients import pg
from app.deps import CurrentUser
from app.lua_scripts import get_scripts, perf_keys
from app.naive_holds import naive_reserve
from mongodb.hold_attempts import log_attempt

router = APIRouter()

HOLD_TTL_SECONDS = 600
MAX_TICKETS_PER_PERFORMANCE = 6
MAX_HOLD_ATTEMPTS_PER_MINUTE = 10
LISBON = ZoneInfo("Europe/Lisbon")


class HoldRequest(BaseModel):
    seat_ids: list[UUID] = Field(default_factory=list, description="Lugares (secção sentada)")
    section_id: UUID | None = Field(default=None, description="Secção standing")
    places: int | None = Field(default=None, ge=1, le=6)

    @model_validator(mode="after")
    def one_mode(self):
        seated = len(self.seat_ids) > 0
        standing = self.section_id is not None and self.places is not None
        if seated == standing:
            raise ValueError("indique seat_ids (sentada) ou section_id com places (standing), não os dois")
        if seated and len(set(self.seat_ids)) != len(self.seat_ids):
            raise ValueError("lugares repetidos no pedido")
        if seated and len(self.seat_ids) > MAX_TICKETS_PER_PERFORMANCE:
            raise ValueError("no máximo 6 lugares por pedido")
        return self


def age_on(birth, day) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def _attempt(performance_id: UUID, body: HoldRequest, customer_id: UUID):
    pid, cid = str(performance_id), str(customer_id)
    scripts = get_scripts()

    # 1. Limite de tentativas por minuto. Conta todas as tentativas, mesmo as recusadas.
    attempts = scripts["rate"](keys=[f"ratelimit:holds:{cid}"], args=[60])
    if attempts > MAX_HOLD_ATTEMPTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="demasiadas tentativas de hold neste minuto")

    requested = len(body.seat_ids) if body.seat_ids else body.places
    seat_ids = [str(s) for s in body.seat_ids]
    section_id = str(body.section_id) if body.section_id else None

    with pg() as conn:
        # 2. Performance: existe, está à venda e ainda não começou
        perf = conn.execute(
            """SELECT p.venue_id, p.status, p.starts_at, e.min_age
               FROM performances p JOIN events e ON e.id = p.event_id
               WHERE p.id = %s""",
            (pid,),
        ).fetchone()
        if perf is None:
            raise HTTPException(status_code=404, detail="performance não existe")
        venue_id, status, starts_at, min_age = str(perf[0]), perf[1], perf[2], perf[3]

        if status != "on_sale" or starts_at <= datetime.now(starts_at.tzinfo):
            raise HTTPException(status_code=409, detail="a performance não está à venda")

        # 3. Cliente: existe e tem a idade mínima no dia da performance (Lisboa)
        cust = conn.execute("SELECT date_of_birth FROM customers WHERE id = %s", (cid,)).fetchone()
        if cust is None:
            raise HTTPException(status_code=404, detail="cliente não existe")
        day = starts_at.astimezone(LISBON).date()
        if age_on(cust[0], day) < min_age:
            raise HTTPException(status_code=403, detail="idade mínima não cumprida")

        # 4. Máximo de 6 bilhetes por performance: já comprados + reservas ativas
        already = conn.execute(
            """SELECT
                 (SELECT count(*) FROM tickets t JOIN orders o ON o.id = t.order_id
                   WHERE o.customer_id = %(c)s AND t.performance_id = %(p)s
                     AND t.status IN ('valid', 'used'))
               + (SELECT COALESCE(SUM(COALESCE(hi.places, 1)), 0)
                    FROM hold_items hi JOIN holds h ON h.id = hi.hold_id
                   WHERE h.customer_id = %(c)s AND h.performance_id = %(p)s
                     AND h.status = 'active' AND h.expires_at > now())""",
            {"c": cid, "p": pid},
        ).fetchone()[0]
        if already + requested > MAX_TICKETS_PER_PERFORMANCE:
            raise HTTPException(status_code=409, detail="limite de 6 bilhetes por performance")

        # 5. Os lugares ou a secção existem neste local, com o tipo certo
        section_by_seat: dict[str, str] = {}
        if seat_ids:
            rows = conn.execute(
                """SELECT st.id, st.section_id
                   FROM seats st JOIN sections s ON s.id = st.section_id
                   WHERE s.venue_id = %s AND s.kind = 'seated'
                     AND st.id = ANY(%s::uuid[])""",
                (venue_id, seat_ids),
            ).fetchall()
            if len(rows) != len(seat_ids):
                raise HTTPException(status_code=422, detail="algum lugar não existe neste local")
            section_by_seat = {str(a): str(b) for a, b in rows}
        else:
            row = conn.execute(
                "SELECT id FROM sections WHERE id = %s AND venue_id = %s AND kind = 'standing'",
                (section_id, venue_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=422, detail="secção standing não existe neste local")

    # 6. Cache do Redis carregada (só PostgreSQL na primeira vez)
    ensure_performance_loaded(pid)

    # 7. Reserva atómica no Redis: ou fica tudo reservado, ou nada
    hold_id = str(uuid4())
    data = json.dumps({
        "hold_id": hold_id, "performance_id": pid, "customer_id": cid,
        "section_id": section_id, "places": body.places, "seat_ids": seat_ids,
    })
    if os.environ.get("HOLD_MODE") == "naive" and seat_ids:
        result = naive_reserve(pid, hold_id, seat_ids, data, HOLD_TTL_SECONDS)
    else:
        result = scripts["hold"](
            keys=perf_keys(pid),
            args=[hold_id, HOLD_TTL_SECONDS, data, section_id or "", body.places or 0, *seat_ids],
        )
    if result[0] == "SOLD":
        raise HTTPException(status_code=409, detail=f"lugar {result[1]} já vendido")
    if result[0] == "HELD":
        raise HTTPException(status_code=409, detail=f"lugar {result[1]} já reservado")
    if result[0] == "NO_PLACES":
        raise HTTPException(status_code=409, detail="não há lugares suficientes")

    # 8. Gravar no PostgreSQL. Se falhar, desfazer a reserva no Redis.
    try:
        with pg() as conn:
            expires_at = conn.execute(
                """INSERT INTO holds (id, customer_id, performance_id, status, created_at, expires_at)
                   VALUES (%s, %s, %s, 'active', now(), now() + make_interval(secs => %s))
                   RETURNING expires_at""",
                (hold_id, cid, pid, HOLD_TTL_SECONDS),
            ).fetchone()[0]

            if seat_ids:
                for seat in seat_ids:
                    conn.execute(
                        """INSERT INTO hold_items (hold_id, section_id, seat_id, places)
                           VALUES (%s, %s, %s, NULL)""",
                        (hold_id, section_by_seat[seat], seat),
                    )
            else:
                conn.execute(
                    """INSERT INTO hold_items (hold_id, section_id, seat_id, places)
                       VALUES (%s, %s, NULL, %s)""",
                    (hold_id, section_id, body.places),
                )
    except Exception:
        scripts["release"](keys=perf_keys(pid), args=[hold_id, *seat_ids])
        raise HTTPException(status_code=503, detail="falha ao gravar a reserva, tente novamente")

    return {
        "hold_id": hold_id,
        "performance_id": pid,
        "expires_at": expires_at.isoformat(),
        "seat_ids": seat_ids,
        "section_id": section_id,
        "places": body.places,
    }


@router.post("/performances/{performance_id}/holds", status_code=201, tags=["F2 Hold"])
def create_hold(performance_id: UUID, body: HoldRequest, customer_id: CurrentUser):
    # Regista cada tentativa no MongoDB, aceite ou recusada (inclui o limite de 429)
    if body.seat_ids:
        requested = {"seat_ids": [str(s) for s in body.seat_ids]}
    else:
        requested = {"section_id": str(body.section_id), "places": body.places}

    try:
        response = _attempt(performance_id, body, customer_id)
    except HTTPException as exc:
        log_attempt(str(customer_id), str(performance_id), requested, "refused", str(exc.detail))
        raise
    except Exception:
        log_attempt(str(customer_id), str(performance_id), requested, "refused", "erro interno")
        raise

    log_attempt(str(customer_id), str(performance_id), requested, "accepted")
    return response