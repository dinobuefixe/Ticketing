import argparse
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from bson import json_util
from bson.decimal128 import Decimal128
from psycopg.rows import dict_row
from pymongo import MongoClient, ReplaceOne

COLLECTION = "sales_by_performance"
PIPELINE_PATH = Path(__file__).resolve().parent / "pipelines" / "report1.json"
BATCH = 500

MONEY = {"bsonType": "decimal"}
COUNT = {"bsonType": ["int", "long"], "minimum": 0}

VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "_id",
            "performance_id",
            "event_id",
            "event_title",
            "venue_name",
            "city",
            "starts_at",
            "status",
            "tickets_sold",
            "tickets_used",
            "sections",
            "payment_methods",
            "promo_codes",
            "exported_at",
        ],
        "properties": {
            "_id": {"bsonType": "string"},
            "performance_id": {"bsonType": "string"},
            "event_id": {"bsonType": "string"},
            "event_title": {"bsonType": "string"},
            "venue_name": {"bsonType": "string"},
            "city": {"bsonType": "string"},
            "starts_at": {"bsonType": "date"},
            "status": {
                "enum": ["scheduled", "on_sale", "sold_out", "finished", "cancelled"]
            },
            "tickets_sold": COUNT,
            "tickets_used": COUNT,
            "sections": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["section_id", "section_name", "tickets_sold", "revenue"],
                    "properties": {
                        "section_id": {"bsonType": "string"},
                        "section_name": {"bsonType": "string"},
                        "tickets_sold": COUNT,
                        "revenue": MONEY,
                    },
                },
            },
            "payment_methods": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["method", "revenue"],
                    "properties": {
                        "method": {"enum": ["card", "mbway", "multibanco"]},
                        "revenue": MONEY,
                    },
                },
            },
            "promo_codes": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["code", "orders", "discount"],
                    "properties": {
                        "code": {"bsonType": "string"},
                        "orders": COUNT,
                        "discount": MONEY,
                    },
                },
            },
            "exported_at": {"bsonType": "date"},
        },
    }
}

META_SQL = """
    SELECT p.id, p.event_id, e.title AS event_title, v.name AS venue_name,
           v.city, p.starts_at, p.status
    FROM performances p
    JOIN events e ON e.id = p.event_id
    JOIN venues v ON v.id = p.venue_id
"""

SECTIONS_SQL = """
    SELECT t.performance_id, t.section_id, s.name AS section_name,
           count(*) AS tickets_sold, sum(t.price_paid) AS revenue
    FROM tickets t
    JOIN sections s ON s.id = t.section_id
    WHERE t.status IN ('valid', 'used')
    GROUP BY t.performance_id, t.section_id, s.name
"""

CHECKIN_SQL = """
    SELECT performance_id,
           count(*) FILTER (WHERE status IN ('valid', 'used')) AS tickets_sold,
           count(*) FILTER (WHERE status = 'used') AS tickets_used
    FROM tickets
    GROUP BY performance_id
"""

METHODS_SQL = """
    SELECT o.performance_id, p.method,
           sum(CASE p.status
                   WHEN 'approved' THEN p.amount
                   WHEN 'refunded' THEN -p.amount
                   ELSE 0
               END) AS revenue
    FROM payments p
    JOIN orders o ON o.id = p.order_id
    GROUP BY o.performance_id, p.method
"""

PROMO_SQL = """
    SELECT o.performance_id, pc.code, count(*) AS orders,
           sum(g.gross - o.total) AS discount
    FROM orders o
    JOIN promo_codes pc ON pc.id = o.promo_code_id
    JOIN LATERAL (
        SELECT COALESCE(sum(price_paid), 0) AS gross
        FROM tickets WHERE order_id = o.id
    ) g ON true
    WHERE o.paid_at IS NOT NULL
    GROUP BY o.performance_id, pc.code
"""


def pg_connect():
    url = os.environ["READONLY_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url, row_factory=dict_row)


def money(value):
    return Decimal128(Decimal(value or 0).quantize(Decimal("0.01")))


def setup(db):
    if COLLECTION not in db.list_collection_names():
        db.create_collection(
            COLLECTION,
            validator=VALIDATOR,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        db.command(
            "collMod",
            COLLECTION,
            validator=VALIDATOR,
            validationLevel="strict",
            validationAction="error",
        )
    db[COLLECTION].create_index([("starts_at", -1)], name="sales_starts_at_idx")
    db[COLLECTION].create_index([("event_id", 1)], name="sales_event_idx")
    print("sales collection ready")


def export_sales(db):
    now = datetime.now(timezone.utc)
    docs = {}
    with pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(META_SQL)
            for r in cur.fetchall():
                key = str(r["id"])
                docs[key] = {
                    "_id": key,
                    "performance_id": key,
                    "event_id": str(r["event_id"]),
                    "event_title": r["event_title"],
                    "venue_name": r["venue_name"],
                    "city": r["city"],
                    "starts_at": r["starts_at"],
                    "status": r["status"],
                    "tickets_sold": 0,
                    "tickets_used": 0,
                    "sections": [],
                    "payment_methods": [],
                    "promo_codes": [],
                    "exported_at": now,
                }

            cur.execute(SECTIONS_SQL)
            for r in cur.fetchall():
                docs[str(r["performance_id"])]["sections"].append(
                    {
                        "section_id": str(r["section_id"]),
                        "section_name": r["section_name"],
                        "tickets_sold": r["tickets_sold"],
                        "revenue": money(r["revenue"]),
                    }
                )

            cur.execute(CHECKIN_SQL)
            for r in cur.fetchall():
                doc = docs[str(r["performance_id"])]
                doc["tickets_sold"] = r["tickets_sold"]
                doc["tickets_used"] = r["tickets_used"]

            cur.execute(METHODS_SQL)
            for r in cur.fetchall():
                docs[str(r["performance_id"])]["payment_methods"].append(
                    {"method": r["method"], "revenue": money(r["revenue"])}
                )

            cur.execute(PROMO_SQL)
            for r in cur.fetchall():
                docs[str(r["performance_id"])]["promo_codes"].append(
                    {
                        "code": r["code"],
                        "orders": r["orders"],
                        "discount": money(r["discount"]),
                    }
                )

    collection = db[COLLECTION]
    operations = []
    for doc in docs.values():
        operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        if len(operations) >= BATCH:
            collection.bulk_write(operations, ordered=False)
            operations = []
    if operations:
        collection.bulk_write(operations, ordered=False)

    removed = collection.delete_many({"_id": {"$nin": list(docs)}}).deleted_count
    print(f"exported {len(docs)} performances, removed {removed} stale documents")


def report1(db, limit):
    pipeline = json_util.loads(PIPELINE_PATH.read_text())
    pipeline.append({"$limit": limit})
    for doc in db[COLLECTION].aggregate(pipeline):
        print(json_util.dumps(doc, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "export", "report1"])
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    client = MongoClient(os.environ["MONGO_URL"])
    db = client.get_default_database()
    try:
        if args.command == "setup":
            setup(db)
        elif args.command == "export":
            export_sales(db)
        else:
            report1(db, args.limit)
    finally:
        client.close()


if __name__ == "__main__":
    main()