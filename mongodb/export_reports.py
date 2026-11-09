
import os
import sys
import time
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient, ReplaceOne

BATCH = 5000

ORDERS_SQL = """
SELECT o.id::text AS _id,
       o.status,
       o.performance_id::text,
       o.paid_at,
       round(o.total * 100)::int AS total_cents,
       coalesce(round(sum(t.price_paid) * 100)::int, 0) - round(o.total * 100)::int AS discount_cents,
       e.id::text AS event_id,
       e.title AS event_title,
       e.organiser_id::text,
       v.id::text AS venue_id,
       v.city,
       pc.code AS promo_code,
       (SELECT p.method FROM payments p
         WHERE p.order_id = o.id AND p.status = 'approved' LIMIT 1) AS method,
       coalesce(json_agg(json_build_object(
           'section_id', t.section_id::text,
           'price_cents', round(t.price_paid * 100)::int,
           'status', t.status)) FILTER (WHERE t.id IS NOT NULL), '[]'::json) AS tickets
FROM orders o
JOIN performances pf ON pf.id = o.performance_id
JOIN events e ON e.id = pf.event_id
JOIN venues v ON v.id = pf.venue_id
LEFT JOIN promo_codes pc ON pc.id = o.promo_code_id
LEFT JOIN tickets t ON t.order_id = o.id
WHERE o.status IN ('paid', 'refunded')
GROUP BY o.id, e.id, v.id, pc.code
"""

PERFORMANCES_SQL = """
SELECT pf.id::text AS _id,
       pf.status,
       pf.starts_at,
       e.id::text AS event_id,
       e.title AS event_title,
       e.category,
       v.id::text AS venue_id,
       v.name AS venue_name,
       v.city,
       (SELECT count(*) FROM seats st JOIN sections s ON s.id = st.section_id
         WHERE s.venue_id = v.id) AS seated_capacity,
       (SELECT coalesce(sum(s.standing_capacity), 0) FROM sections s
         WHERE s.venue_id = v.id AND s.kind = 'standing') AS standing_capacity,
       coalesce((
           SELECT json_agg(json_build_object(
                      'section_id', s.id::text, 'name', s.name, 'kind', s.kind,
                      'sold', x.sold, 'gross_cents', x.gross))
           FROM sections s
           JOIN LATERAL (
               SELECT count(*) AS sold,
                      coalesce(round(sum(t.price_paid) * 100)::int, 0) AS gross
               FROM tickets t
               WHERE t.performance_id = pf.id AND t.section_id = s.id
                 AND t.status IN ('valid', 'used')) x ON true
           WHERE s.venue_id = v.id), '[]'::json) AS sections,
       (SELECT count(*) FROM tickets t
         WHERE t.performance_id = pf.id AND t.status = 'used') AS checked_in
FROM performances pf
JOIN events e ON e.id = pf.event_id
JOIN venues v ON v.id = pf.venue_id
"""


def add_totals(doc: dict) -> dict:
    doc["tickets_sold"] = sum(s["sold"] for s in doc["sections"])
    doc["gross_cents"] = sum(s["gross_cents"] for s in doc["sections"])
    return doc


def export(pg, collection, sql: str, name: str, run_at: datetime, transform=None) -> None:
    t0 = time.time()
    total = 0
    ops = []
    with pg.cursor(name=f"cur_{name}", row_factory=dict_row) as cur:
        cur.itersize = BATCH
        cur.execute(sql)
        for row in cur:
            if transform:
                row = transform(row)
            row["exported_at"] = run_at
            ops.append(ReplaceOne({"_id": row["_id"]}, row, upsert=True))
            if len(ops) >= BATCH:
                collection.bulk_write(ops, ordered=False)
                total += len(ops)
                ops = []
    if ops:
        collection.bulk_write(ops, ordered=False)
        total += len(ops)

    removed = collection.delete_many({"exported_at": {"$lt": run_at}}).deleted_count
    print(f"{name}: {total} documentos gravados, {removed} removidos ({time.time() - t0:.1f} s)")


def main() -> int:
    for var in ("READONLY_DATABASE_URL", "MONGO_URL"):
        if var not in os.environ:
            print(f"Falta a variável {var} (ver .env.example)")
            return 1

    pg_url = os.environ["READONLY_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    mongo = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    db = mongo.get_default_database()
    run_at = datetime.now(timezone.utc)

    try:
        with psycopg.connect(pg_url) as pg:
            export(pg, db["report_orders"], ORDERS_SQL, "report_orders", run_at)
            export(pg, db["report_performances"], PERFORMANCES_SQL,
                   "report_performances", run_at, transform=add_totals)
    finally:
        mongo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())