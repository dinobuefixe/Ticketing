"""Registo de tentativas de hold no MongoDB (coleção hold_attempts).

Um documento por tentativa, aceite ou recusada. A coleção, o validador e o índice TTL
de 90 dias são criados por scripts/setup.sh (mongodb/setup_collections.js).

Se a escrita falhar, a reserva não é cancelada: o erro é registado no log da app.
"""

import logging
import os
from datetime import datetime, timezone

from pymongo import MongoClient

log = logging.getLogger(__name__)

_client: MongoClient | None = None


def _collection():
    global _client
    if _client is None:
        # A base de dados vem no MONGO_URL (/ticketing), por isso não é preciso outra variável
        _client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=2000)
    return _client.get_default_database()["hold_attempts"]


def log_attempt(customer_id: str, performance_id: str, requested: dict,
                result: str, reason: str | None = None) -> None:
    """result: 'accepted' ou 'refused'. requested: {"seat_ids": [...]} ou {"section_id", "places"}."""
    doc = {
        "customer_id": customer_id,
        "performance_id": performance_id,
        "requested": requested,
        "result": result,
        "reason": reason,
        "attempted_at": datetime.now(timezone.utc),
    }
    try:
        _collection().insert_one(doc)
    except Exception as exc:  # o registo nunca deve impedir a reserva
        log.error("falha ao registar tentativa de hold: %s", exc)