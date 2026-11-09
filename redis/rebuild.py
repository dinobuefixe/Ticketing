
import sys
import time

from redis_common import (OWNED_PREFIXES, TRENDING_KEY, expected_state, hold_key, hold_seat_key,
                          left_counts_key, pg_connect, redis_connect, sold_counts_key, sold_key)

CHUNK = 1000


def clear(r) -> int:
    removed = 0
    for prefix in OWNED_PREFIXES:
        batch = []
        for key in r.scan_iter(match=prefix + "*", count=1000):
            batch.append(key)
            if len(batch) >= CHUNK:
                removed += r.unlink(*batch)
                batch = []
        if batch:
            removed += r.unlink(*batch)
    return removed


def write(r, exp: dict) -> None:
    pipe = r.pipeline(transaction=False)
    pending = 0

    def tick():
        nonlocal pending
        pending += 1
        if pending >= 5000:
            pipe.execute()
            pending = 0

    for perf in exp["perfs"]:
        seats = list(exp["sold_seats"][perf])
        for i in range(0, len(seats), CHUNK):
            pipe.sadd(sold_key(perf), *seats[i:i + CHUNK])
            tick()
        if exp["sold_counts"][perf]:
            pipe.hset(sold_counts_key(perf), mapping=exp["sold_counts"][perf])
            pipe.hset(left_counts_key(perf), mapping=exp["left_counts"][perf])
            tick()

    for hold_id, h in exp["holds"].items():
        pipe.hset(hold_key(hold_id), mapping={"customer": h["customer"], "performance": h["perf"]})
        pipe.expire(hold_key(hold_id), h["ttl"])
        for seat in h["seats"]:
            pipe.set(hold_seat_key(h["perf"], seat), hold_id, ex=h["ttl"])
        tick()

    if exp["trending"]:
        pipe.zadd(TRENDING_KEY, exp["trending"])
        tick()

    pipe.execute()


def main() -> int:
    t0 = time.time()
    r = redis_connect()
    r.ping()
    with pg_connect() as pg:
        exp = expected_state(pg)
    removed = clear(r)
    write(r, exp)
    sold = sum(len(s) for s in exp["sold_seats"].values())
    print(f"rebuild: {len(exp['perfs'])} performances, {sold} lugares vendidos, "
          f"{len(exp['holds'])} holds ativos, {len(exp['trending'])} eventos em trending "
          f"({removed} chaves antigas apagadas, {time.time() - t0:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())