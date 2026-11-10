import json
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.cache import ensure_performance_loaded
from app.clients import rd
from app.deps import CurrentUser
from app.redis_ops import perf_keys, sweep_standing

router = APIRouter()


@router.get("/performances/{performance_id}/seat-map", tags=["F1 Seat map"])
def seat_map(performance_id: UUID, user_id: CurrentUser):
    pid = str(performance_id)

    # Só vai ao PostgreSQL na primeira vez desta performance
    try:
        ensure_performance_loaded(pid)
    except LookupError:
        raise HTTPException(status_code=404, detail="performance não existe")

    r = rd()
    sweep_standing(pid)

    k = perf_keys(pid)
    venue_id = r.get(f"perf:{pid}:venue")
    layout = json.loads(r.get(f"venue:{venue_id}:layout"))
    prices = r.hgetall(f"perf:{pid}:prices")
    sold = r.smembers(k["sold"])
    held = r.hgetall(k["held"])
    places_left = r.hgetall(k["places"])

    # Uma reserva só conta se a chave hold:{id} ainda existir
    holders = list(set(held.values()))
    pipe = r.pipeline()
    for holder in holders:
        pipe.exists(f"hold:{holder}")
    alive = {h for h, flag in zip(holders, pipe.execute()) if flag}
    held_seats = {seat for seat, holder in held.items() if holder in alive}

    sections = []
    for sec in layout["sections"]:
        entry = {
            "id": sec["id"],
            "name": sec["name"],
            "kind": sec["kind"],
            "price": prices.get(sec["id"]),
        }
        if sec["kind"] == "seated":
            entry["seats"] = [
                {
                    "id": s["id"],
                    "row": s["row"],
                    "number": s["number"],
                    "wheelchair_accessible": s["wheelchair_accessible"],
                    "restricted_view": s["restricted_view"],
                    "status": "sold" if s["id"] in sold
                              else "held" if s["id"] in held_seats
                              else "free",
                }
                for s in sec["seats"]
            ]
        else:
            entry["places_left"] = int(places_left.get(sec["id"], sec["standing_capacity"]))
        sections.append(entry)

    return {"performance_id": pid, "sections": sections}