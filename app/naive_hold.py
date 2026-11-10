"""VERSÃO INGÉNUA, só para a demonstração de concorrência.

Ativa-se com HOLD_MODE=naive. Verifica, espera 50 ms e só depois marca, sem WATCH nem MULTI.
Por isso, vários pedidos ao mesmo tempo passam a verificação e reservam o mesmo lugar.
"""

import time

from app.clients import rd
from app.redis_ops import perf_keys


def naive_reserve(pid: str, hold_id: str, seat_ids: list[str], data: str, ttl: int) -> tuple[str, str | None]:
    r = rd()
    k = perf_keys(pid)

    # 1. Verificar, sem bloquear nada
    for seat in seat_ids:
        if r.sismember(k["sold"], seat):
            return "SOLD", seat
        holder = r.hget(k["held"], seat)
        if holder and r.exists(f"hold:{holder}"):
            return "HELD", seat

    # 2. Janela para a corrida
    time.sleep(0.05)

    # 3. Marcar, sem garantia de que o lugar continua livre
    for seat in seat_ids:
        r.hset(k["held"], seat, hold_id)
    r.set(f"hold:{hold_id}", data, ex=ttl)
    return "OK", None