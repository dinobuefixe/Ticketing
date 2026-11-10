
import json
import os
from functools import lru_cache
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pymongo import MongoClient
from pymongo.errors import ExecutionTimeout, PyMongoError

router = APIRouter(prefix="/reports", tags=["Reports"])


PIPELINES_DIR = Path(
    os.environ.get("PIPELINES_DIR", Path(__file__).resolve().parents[2] / "mongodb" / "pipelines")
)

REPORTS = [
    (1, "performance-sales", "Sales, revenue and check-in rate per performance"),
    (2, "revenue-by-organiser", "Revenue per organiser per month, last 12 months"),
    (3, "top-events-by-city", "Top 10 events per city by tickets sold, last 30 days"),
    (4, "occupancy", "Average occupancy per venue, last 90 days"),
    (5, "promo-effectiveness", "Orders, discount and average order value per promo code"),
    (6, "failed-attempts-by-hour", "Hours of the day with most refused hold attempts"),
]


@lru_cache(maxsize=1)
def get_db():
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
    return client.get_default_database()


def run_report(number: int, limit: int) -> dict:
    path = PIPELINES_DIR / f"report{number}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"pipeline report{number}.json not found")
    spec = json.loads(path.read_text(encoding="utf-8"))

    pipeline = spec["pipeline"] + [{"$limit": limit}]
    try:
        docs = list(get_db()[spec["collection"]].aggregate(
            pipeline, allowDiskUse=True, maxTimeMS=20_000))
    except ExecutionTimeout:
        raise HTTPException(status_code=504, detail="report took too long")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB unavailable")

    return jsonable_encoder(
        {"report": number, "description": spec.get("description", ""),
         "count": len(docs), "results": docs},
        custom_encoder={ObjectId: str},
    )


@router.get("", summary="List the available reports")
def list_reports():
    return [{"report": n, "path": f"/reports/{slug}", "title": title} for n, slug, title in REPORTS]


def _register(number: int, slug: str, title: str) -> None:
    @router.get(f"/{slug}", name=f"report_{number}", summary=title)
    def endpoint(limit: int = Query(100, ge=1, le=5000, description="Maximum rows returned")):
        return run_report(number, limit)


for _number, _slug, _title in REPORTS:
    _register(_number, _slug, _title)
