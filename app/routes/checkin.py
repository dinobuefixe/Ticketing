import os
from uuid import UUID

import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class CheckinRequest(BaseModel):
    code: str
    gate_id: UUID
    staff_id: UUID


def connect():
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def record_scan(cur, code, ticket_id, gate_id, staff_id, result):
    cur.execute(
        """
        INSERT INTO scan_records (ticket_code, gate_id, ticket_id, staff_id, result)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (code[:12], gate_id, ticket_id, staff_id, result),
    )


@router.post("/checkin")
def checkin(body: CheckinRequest):
    code = body.code.strip()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM gates WHERE id = %s", (body.gate_id,))
            if cur.fetchone() is None:
                return JSONResponse(status_code=404, content={"detail": "gate not found"})

            cur.execute(
                """
                SELECT t.id,
                       t.status,
                       (p.starts_at AT TIME ZONE 'Europe/Lisbon')::date
                           = (now() AT TIME ZONE 'Europe/Lisbon')::date AS is_today
                FROM tickets t
                JOIN performances p ON p.id = t.performance_id
                WHERE t.code = %s
                FOR UPDATE OF t
                """,
                (code,),
            )
            row = cur.fetchone()

            if row is None:
                record_scan(cur, code, None, body.gate_id, body.staff_id, "unknown_code")
                return JSONResponse(
                    status_code=404,
                    content={"result": "unknown_code", "detail": "ticket code not found"},
                )

            ticket_id, status, is_today = row

            if status == "cancelled":
                record_scan(cur, code, ticket_id, body.gate_id, body.staff_id, "cancelled")
                return JSONResponse(
                    status_code=409,
                    content={"result": "cancelled", "detail": "ticket is cancelled"},
                )

            if status == "used":
                record_scan(cur, code, ticket_id, body.gate_id, body.staff_id, "already_used")
                return JSONResponse(
                    status_code=409,
                    content={"result": "already_used", "detail": "ticket was already used"},
                )

            if not is_today:
                record_scan(cur, code, ticket_id, body.gate_id, body.staff_id, "wrong_day")
                return JSONResponse(
                    status_code=409,
                    content={"result": "wrong_day", "detail": "performance is not today"},
                )

            cur.execute("UPDATE tickets SET status = 'used' WHERE id = %s", (ticket_id,))
            record_scan(cur, code, ticket_id, body.gate_id, body.staff_id, "accepted")
            return {"result": "accepted", "ticket_id": str(ticket_id)}