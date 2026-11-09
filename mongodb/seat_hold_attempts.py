

import os
import random
import sys
from datetime import datetime, timedelta, timezone

import psycopg
from pymongo import MongoClient

TOTAL = 60_000
BATCH = 10_000
random.seed(42)  

REFUSAL_REASONS = ["seat_taken", "limit_6_tickets", "rate_limit", "not_on_sale", "underage"]
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 3, 5, 6, 7, 8, 9, 10, 9, 8, 8, 9, 10, 12, 14, 14, 10, 5, 2]


def load_ids(pg_url: str):
    with psycopg.connect(pg_url) as pg:
        customers = [r[0] for r in pg.execute(
            "SELECT id::text FROM customers ORDER BY random() LIMIT 5000")]
        performances = [r[0] for r in pg.execute("SELECT id::text FROM performances")]
        seats = [(r[0], r[1]) for r in pg.execute(
            "SELECT id::text, section_id::text FROM seats TABLESAMPLE SYSTEM (1) LIMIT 2000")]
        standing = [r[0] for r in pg.execute(
            "SELECT id::text FROM sections WHERE kind = 'standing'")]
    return customers, performances, seats, standing


def make_attempt(now, customers, performances, seats, standing):
    day = now - timedelta(days=random.randint(0, 89), hours=random.randint(0, 23))
    hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
    attempted_at = day.replace(hour=hour, minute=random.randint(0, 59),
                               second=random.randint(0, 59), microsecond=0)

    if standing and random.random() < 0.3:
        requested = {"section_id": random.choice(standing), "places": random.randint(1, 4)}
    else:
        picked = random.sample(seats, k=random.randint(1, 4))
        requested = {"seat_ids": [s[0] for s in picked]}

    accepted = random.random() < 0.35
    return {
        "customer_id": random.choice(customers),
        "performance_id": random.choice(performances),
        "requested": requested,
        "result": "accepted" if accepted else "refused",
        "reason": None if accepted else random.choice(REFUSAL_REASONS),
        "attempted_at": attempted_at,
    }


def main() -> int:
    for var in ("READONLY_DATABASE_URL", "MONGO_URL"):
        if var not in os.environ:
            print(f"Falta a variável {var} (ver .env.example)")
            return 1

    pg_url = os.environ["READONLY_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    customers, performances, seats, standing = load_ids(pg_url)
    if not (customers and performances and seats):
        print("Faltam clientes, performances ou lugares: corre primeiro o seed do PostgreSQL")
        return 1

    mongo = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    coll = mongo.get_default_database()["hold_attempts"]
    coll.delete_many({})
    now = datetime.now(timezone.utc)

    for start in range(0, TOTAL, BATCH):
        docs = [make_attempt(now, customers, performances, seats, standing)
                for _ in range(min(BATCH, TOTAL - start))]
        coll.insert_many(docs, ordered=False)

    print(f"hold_attempts: {coll.count_documents({})} documentos")
    mongo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
