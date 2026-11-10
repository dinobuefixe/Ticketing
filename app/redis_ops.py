"""Operações atómicas no Redis, em Python (sem Lua).

Atomicidade com WATCH/MULTI: lemos as chaves vigiadas. Se alguma mudar antes do EXEC,
o Redis aborta a transação (WatchError) e repetimos a operação.

Estrutura das chaves de uma performance:
  perf:{id}:held            hash   seat_id -> hold_id
  perf:{id}:sold            set    seat_id vendidos
  perf:{id}:places_left     hash   section_id -> lugares livres (standing)
  perf:{id}:standing_holds  hash   hold_id -> "section_id:places"
  hold:{id}                 string dados da reserva, com TTL de 600 s
  ratelimit:holds:{cliente} string contador de tentativas, com TTL de 60 s
"""

import time

from redis import WatchError

from app.clients import rd


def perf_keys(pid: str) -> dict[str, str]:
    return {
        "held": f"perf:{pid}:held",
        "sold": f"perf:{pid}:sold",
        "places": f"perf:{pid}:places_left",
        "standing": f"perf:{pid}:standing_holds",
    }


def _watched(keys: list[str], body):
    """Executa body(pipe) com WATCH nas chaves e repete se alguma mudar.

    body devolve (valor, escrita). Se escrita for None, só lê e devolve o valor.
    Caso contrário, a escrita corre dentro de MULTI/EXEC.
    """
    r = rd()
    while True:
        with r.pipeline() as pipe:
            try:
                pipe.watch(*keys)
                value, write = body(pipe)  # leituras imediatas, porque estamos em WATCH
                if write is None:
                    pipe.unwatch()
                    return value
                pipe.multi()
                write(pipe)
                pipe.execute()
                return value
            except WatchError:
                continue  # outro pedido mexeu nas chaves: tenta de novo


def count_hold_attempt(customer_id: str, window_seconds: int = 60) -> int:
    """Conta uma tentativa de hold. A janela começa na primeira tentativa."""
    key = f"ratelimit:holds:{customer_id}"
    with rd().pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)  # define o prazo só se não existir
        count, _ = pipe.execute()
    return count


def sweep_standing(pid: str) -> None:
    """Devolve os lugares standing das reservas cujo hold já expirou."""
    k = perf_keys(pid)

    def body(pipe):
        expired = []
        for hold_id, value in pipe.hgetall(k["standing"]).items():
            if not pipe.exists(f"hold:{hold_id}"):
                expired.append((hold_id, value))
        if not expired:
            return None, None

        def write(p):
            for hold_id, value in expired:
                section_id, places = value.split(":", 1)
                p.hincrby(k["places"], section_id, int(places))
                p.hdel(k["standing"], hold_id)

        return None, write

    _watched([k["standing"], k["places"]], body)


def reserve_hold(pid: str, hold_id: str, seat_ids: list[str], section_id: str | None,
                 places: int, data: str, ttl: int) -> tuple[str, str | None]:
    """Reserva lugares (ou places em standing). Devolve ('OK', None) ou (motivo, detalhe)."""
    k = perf_keys(pid)

    def body(pipe):
        for seat in seat_ids:
            if pipe.sismember(k["sold"], seat):
                return ("SOLD", seat), None
            holder = pipe.hget(k["held"], seat)
            if holder and pipe.exists(f"hold:{holder}"):
                return ("HELD", seat), None
        if places:
            left = int(pipe.hget(k["places"], section_id) or 0)
            if left < places:
                return ("NO_PLACES", section_id), None

        def write(p):
            for seat in seat_ids:
                p.hset(k["held"], seat, hold_id)
            if places:
                p.hincrby(k["places"], section_id, -places)
                p.hset(k["standing"], hold_id, f"{section_id}:{places}")
            p.set(f"hold:{hold_id}", data, ex=ttl)

        return ("OK", None), write

    return _watched([k["held"], k["sold"], k["places"], k["standing"]], body)


def release_hold(pid: str, hold_id: str, seat_ids: list[str]) -> None:
    """Desfaz uma reserva. Usado quando a gravação no PostgreSQL falha."""
    k = perf_keys(pid)

    def body(pipe):
        standing_value = pipe.hget(k["standing"], hold_id)
        mine = [s for s in seat_ids if pipe.hget(k["held"], s) == hold_id]

        def write(p):
            for seat in mine:
                p.hdel(k["held"], seat)
            if standing_value:
                section_id, places = standing_value.split(":", 1)
                p.hincrby(k["places"], section_id, int(places))
                p.hdel(k["standing"], hold_id)
            p.delete(f"hold:{hold_id}")

        return None, write

    _watched([k["held"], k["places"], k["standing"]], body)


# ---------- Trending e contadores de vendas (Parte 2) ----------
# Um sorted set por minuto: trending:{minuto} com event_id -> bilhetes vendidos nesse minuto.
# A lista "trending now" soma os últimos 60 minutos.

TRENDING_WINDOW_MINUTES = 60


def record_sale(pid: str, event_id: str, quantity: int, ttl_seconds: int = 3600) -> None:
    """Regista uma venda. Corre depois de a encomenda ser paga.

    Não mexe nos lugares livres: esses já foram retirados quando o hold foi criado.
    Só MULTI é necessário, porque os comandos são somas e não dependem de leituras.
    """
    minute_key = f"trending:{int(time.time() // 60)}"
    with rd().pipeline(transaction=True) as pipe:
        pipe.zincrby(minute_key, quantity, event_id)
        pipe.expire(minute_key, ttl_seconds)
        pipe.incrby(f"perf:{pid}:sold_count", quantity)
        pipe.execute()


def trending_now(limit: int = 20) -> list[tuple[str, float]]:
    """Os eventos com mais bilhetes vendidos na última hora."""
    r = rd()
    now_minute = int(time.time() // 60)
    keys = [f"trending:{now_minute - i}" for i in range(TRENDING_WINDOW_MINUTES)]
    keys = [k for k in keys if r.exists(k)]
    if not keys:
        return []
    dest = "trending:window"
    r.zunionstore(dest, keys)
    r.expire(dest, 5)  # cache curta: o resultado é recalculado a cada 5 segundos
    return r.zrevrange(dest, 0, limit - 1, withscores=True)