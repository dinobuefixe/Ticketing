"""Carrega do PostgreSQL para o Redis o que o mapa e as reservas precisam.

Só corre na primeira vez de cada performance (quando falta a chave perf:{id}:loaded).
Depois disso, os pedidos leem só do Redis.
"""

import json

from app.clients import pg, rd


def _load_layout(conn, r, venue_id: str) -> None:
    # Layout do local (secções e lugares) é igual para todas as performances do local
    key = f"venue:{venue_id}:layout"
    if r.exists(key):
        return

    rows = conn.execute(
        """
        SELECT s.id, s.name, s.kind, s.standing_capacity,
               st.id, st.row_label, st.seat_number,
               st.is_wheelchair_accessible, st.is_restricted_view
        FROM sections s
        LEFT JOIN seats st ON st.section_id = s.id
        WHERE s.venue_id = %s
        ORDER BY s.name, st.row_label, st.seat_number
        """,
        (venue_id,),
    ).fetchall()

    sections: dict[str, dict] = {}
    for sec_id, name, kind, capacity, seat_id, row, number, wheelchair, restricted in rows:
        sec = sections.setdefault(
            str(sec_id),
            {"id": str(sec_id), "name": name, "kind": kind,
             "standing_capacity": capacity, "seats": []},
        )
        if seat_id is not None:
            sec["seats"].append({
                "id": str(seat_id),
                "row": row,
                "number": number,
                "wheelchair_accessible": wheelchair,
                "restricted_view": restricted,
            })

    r.set(key, json.dumps({"sections": list(sections.values())}))


def ensure_performance_loaded(performance_id: str) -> None:
    """Lança LookupError se a performance não existir."""
    r = rd()
    if r.exists(f"perf:{performance_id}:loaded"):
        return

    with pg() as conn:
        row = conn.execute(
            "SELECT venue_id FROM performances WHERE id = %s", (performance_id,)
        ).fetchone()
        if row is None:
            raise LookupError(performance_id)
        venue_id = str(row[0])

        _load_layout(conn, r, venue_id)

        sold = [str(x[0]) for x in conn.execute(
            """SELECT seat_id FROM tickets
               WHERE performance_id = %s AND seat_id IS NOT NULL
                 AND status IN ('valid', 'used')""",
            (performance_id,),
        ).fetchall()]

        prices = conn.execute(
            "SELECT section_id, price FROM section_prices WHERE performance_id = %s",
            (performance_id,),
        ).fetchall()

        places = conn.execute(
            """SELECT s.id,
                      s.standing_capacity - (
                          SELECT count(*) FROM tickets t
                          WHERE t.performance_id = %s AND t.section_id = s.id
                            AND t.seat_id IS NULL AND t.status IN ('valid', 'used'))
               FROM sections s
               WHERE s.venue_id = %s AND s.kind = 'standing'""",
            (performance_id, venue_id),
        ).fetchall()

    # Tudo ou nada: ou a performance fica carregada por inteiro, ou não fica carregada
    pipe = r.pipeline(transaction=True)
    pipe.set(f"perf:{performance_id}:venue", venue_id)
    if sold:
        pipe.sadd(f"perf:{performance_id}:sold", *sold)
    if prices:
        pipe.hset(f"perf:{performance_id}:prices",
                  mapping={str(s): str(p) for s, p in prices})
    if places:
        pipe.hset(f"perf:{performance_id}:places_left",
                  mapping={str(s): int(n) for s, n in places})
    pipe.set(f"perf:{performance_id}:loaded", "1")
    pipe.execute()