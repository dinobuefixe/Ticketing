import os

import psycopg
import redis
from fastapi import APIRouter, FastAPI, FastAPI, Response
from pymongo import MongoClient, response

app = FastAPI(title="Ticketing API", version="0.1.0")


def check_postgres() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=2) as conn:
        conn.execute("SELECT 1")
 
 
def check_mongo() -> None:
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    finally:
        client.close()


def check_redis() -> None:
    redis.Redis.from_url(os.environ["REDIS_URL"], socket_timeout=2).ping()


@app.get("/health/services", tags=["Health"])
def services_health(response: Response):
    checks = {"postgres": check_postgres, "mongo": check_mongo, "redis": check_redis}
    result = {}
    for name, check in checks.items():
        try:
            check()
            result[name] = "ok"
        except Exception as exc:
            result[name] = f"error: {type(exc).__name__}"

    healthy = all(value == "ok" for value in result.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", "services": result}