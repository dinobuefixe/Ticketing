"""VERSÃO INGÉNUA, só para a demonstração de concorrência.

Ativa-se com HOLD_MODE=naive. Não é atómica: verifica, espera um pouco e só depois marca.
Por isso, vários pedidos ao mesmo tempo passam a verificação e reservam o mesmo lugar.
Nunca deve ser usada no funcionamento normal.
"""

import time

from app.clients import rd
from app.lua_scripts import perf_keys


def naive_reserve(pid: str, hold_id: str, seat_ids: list[str], data: str, ttl: int) -> list[str]:
    r = rd()
    held_key, sold_key = perf_keys(pid)[0], perf_keys(pid)[1]

    # 1. Verificar (sem bloquear nada)
    for seat in seat_ids:
        if r.sismember(sold_key, seat):
            return ["SOLD", seat]
        holder = r.hget(held_key, seat)
        if holder and r.exists(f"hold:{holder}"):
            return ["HELD", seat]

    # 2. Janela para a corrida: os outros pedidos também passam a verificação
    time.sleep(0.05)

    # 3. Marcar (já sem garantia de que o lugar continua livre)
    for seat in seat_ids:
        r.hset(held_key, seat, hold_id)
    r.set(f"hold:{hold_id}", data, ex=ttl)
    return ["OK"]