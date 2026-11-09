"""Scripts Lua que correm no Redis de forma atómica.

Cada script recebe as mesmas 4 chaves, por esta ordem:
  KEYS[1] perf:{id}:held            seat_id -> hold_id (lugares reservados)
  KEYS[2] perf:{id}:sold            conjunto de seat_id vendidos
  KEYS[3] perf:{id}:places_left     section_id -> lugares livres (standing)
  KEYS[4] perf:{id}:standing_holds  hold_id -> "section_id:places" (reservas standing)
"""

from pathlib import Path

from app.clients import rd

LUA_DIR = Path(__file__).parent / "lua"

SWEEP = (LUA_DIR / "sweep.lua").read_text(encoding="utf-8")
HOLD = SWEEP + (LUA_DIR / "hold_seats.lua").read_text(encoding="utf-8")
RELEASE = (LUA_DIR / "release_hold.lua").read_text(encoding="utf-8")
RATE_LIMIT = (LUA_DIR / "rate_limit.lua").read_text(encoding="utf-8")

_scripts: dict | None = None


def get_scripts() -> dict:
    global _scripts
    if _scripts is None:
        r = rd()
        _scripts = {
            "sweep": r.register_script(SWEEP),
            "hold": r.register_script(HOLD),
            "release": r.register_script(RELEASE),
            "rate": r.register_script(RATE_LIMIT),
        }
    return _scripts


def perf_keys(performance_id: str) -> list[str]:
    return [
        f"perf:{performance_id}:held",
        f"perf:{performance_id}:sold",
        f"perf:{performance_id}:places_left",
        f"perf:{performance_id}:standing_holds",
    ]