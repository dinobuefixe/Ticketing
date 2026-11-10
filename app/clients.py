import os

import psycopg
import redis

_redis: redis.Redis | None = None


def pg() -> psycopg.Connection:
    # Usa o role da app (DATABASE_URL). Cada chamada abre uma ligação e fecha-a no fim do bloco "with".
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(url, connect_timeout=3)


def rd() -> redis.Redis:
    # Um único cliente Redis partilhado. decode_responses=True devolve str em vez de bytes.
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _redis