
import os

import psycopg
from psycopg.rows import dict_row

SCOPE = ["scheduled", "on_sale", "sold_out"]


OWNED_PREFIXES = ("sold:", "hold:", "sales:")

TRENDING_KEY = "sales:trending"


def sold_key(perf):
    return f"sold:{perf}"


def hold_key(hold_id):
    return f"hold:{hold_id}"


def hold_seat_key(perf, seat):
    return f"hold:seat:{perf}:{seat}"


def sold_counts_key(perf):
    return f"sales:sold:{perf}"


def left_counts_key(perf):
    return f"sales:left:{perf}"


def pg_connect():
    url = os.environ["READONLY_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(url, row_factory=dict_row)


def redis_connect():
    import redis  

    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


COUNTERS_SQL = """
SELECT p.id::text AS perf, s.id::text AS section,
       CASE WHEN s.kind = 'standing' THEN s.standing_capacity
            ELSE (SELECT count(*) FROM seats st WHERE st.section_id = s.id) END AS capacity,
       (SELECT count(*) FROM tickets t
         WHERE t.performance_id = p.id AND t.section_id = s.id
           AND t.status IN ('valid', 'used')) AS sold,
       (SELECT coalesce(sum(coalesce(hi.places, 1)), 0)
          FROM hold_items hi JOIN holds h ON h.id = hi.hold_id
         WHERE h.performance_id = p.id AND hi.section_id = s.id
           AND h.status = 'active' AND h.expires_at > now()) AS held
FROM performances p
JOIN sections s ON s.venue_id = p.venue_id
WHERE p.status = ANY(%s)
"""

SOLD_SEATS_SQL = """
SELECT t.performance_id::text AS perf, t.seat_id::text AS seat
FROM tickets t JOIN performances p ON p.id = t.performance_id
WHERE p.status = ANY(%s) AND t.seat_id IS NOT NULL AND t.status IN ('valid', 'used')
"""

HOLDS_SQL = """
SELECT h.id::text AS id, h.performance_id::text AS perf, h.customer_id::text AS customer,
       greatest(1, ceil(extract(epoch FROM h.expires_at - now()))::int) AS ttl,
       coalesce(json_agg(json_build_object('seat', hi.seat_id::text))
                FILTER (WHERE hi.seat_id IS NOT NULL), '[]'::json) AS seats
FROM holds h
JOIN performances p ON p.id = h.performance_id
LEFT JOIN hold_items hi ON hi.hold_id = h.id
WHERE h.status = 'active' AND h.expires_at > now() AND p.status = ANY(%s)
GROUP BY h.id
"""

TRENDING_SQL = """
SELECT e.id::text AS event, count(t.id) AS n
FROM tickets t
JOIN orders o ON o.id = t.order_id
JOIN performances p ON p.id = o.performance_id
JOIN events e ON e.id = p.event_id
WHERE o.status = 'paid' AND t.status IN ('valid', 'used')
  AND o.paid_at > now() - interval '1 hour'
GROUP BY e.id
"""


def expected_state(pg) -> dict:
    """Devolve o que o Redis deve conter, segundo o PostgreSQL neste momento."""
    perfs = [r["id"] for r in pg.execute(
        "SELECT id::text AS id FROM performances WHERE status = ANY(%s)", (SCOPE,))]

    sold_seats = {p: set() for p in perfs}
    for r in pg.execute(SOLD_SEATS_SQL, (SCOPE,)):
        sold_seats[r["perf"]].add(r["seat"])

    sold_counts = {p: {} for p in perfs}
    left_counts = {p: {} for p in perfs}
    for r in pg.execute(COUNTERS_SQL, (SCOPE,)):
        sold_counts[r["perf"]][r["section"]] = int(r["sold"])
        left_counts[r["perf"]][r["section"]] = int(r["capacity"]) - int(r["sold"]) - int(r["held"])

    holds = {r["id"]: {"perf": r["perf"], "customer": r["customer"], "ttl": r["ttl"],
                       "seats": [s["seat"] for s in r["seats"]]}
             for r in pg.execute(HOLDS_SQL, (SCOPE,))}

    trending = {r["event"]: int(r["n"]) for r in pg.execute(TRENDING_SQL)}

    return {"perfs": perfs, "sold_seats": sold_seats, "sold_counts": sold_counts,
            "left_counts": left_counts, "holds": holds, "trending": trending}