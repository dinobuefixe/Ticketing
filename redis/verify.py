
import sys

from redis_common import (TRENDING_KEY, expected_state, hold_key, hold_seat_key, left_counts_key,
                          pg_connect, redis_connect, sold_counts_key, sold_key)

MAX_SHOWN = 10


def report(problems: list, label: str, detail: str) -> None:
    problems.append(f"{label}: {detail}")


def main() -> int:
    r = redis_connect()
    with pg_connect() as pg:
        exp = expected_state(pg)
    problems: list[str] = []

    for perf in exp["perfs"]:
        have = r.smembers(sold_key(perf))
        want = exp["sold_seats"][perf]
        if have != want:
            report(problems, f"sold:{perf}",
                   f"faltam {len(want - have)} e sobram {len(have - want)} lugares")

        for name, key, wanted in (("sold", sold_counts_key(perf), exp["sold_counts"][perf]),
                                  ("left", left_counts_key(perf), exp["left_counts"][perf])):
            got = r.hgetall(key)
            want_str = {k: str(v) for k, v in wanted.items()}
            if got != want_str:
                diff = {k: (got.get(k), want_str.get(k)) for k in set(got) | set(want_str)
                        if got.get(k) != want_str.get(k)}
                report(problems, key, f"(redis, esperado) por secção: {dict(list(diff.items())[:3])}")

    for hold_id, h in exp["holds"].items():
        info = r.hgetall(hold_key(hold_id))
        if info.get("customer") != h["customer"]:
            report(problems, hold_key(hold_id), "hold em falta ou com outro cliente")
        elif r.ttl(hold_key(hold_id)) <= 0:
            report(problems, hold_key(hold_id), "sem TTL")
        for seat in h["seats"]:
            if r.get(hold_seat_key(h["perf"], seat)) != hold_id:
                report(problems, hold_seat_key(h["perf"], seat), "lugar do hold não está preso")

    want_ids = set(exp["holds"])
    want_seat_locks = sum(len(h["seats"]) for h in exp["holds"].values())
    have_ids, have_locks = set(), 0
    for key in r.scan_iter(match="hold:*", count=1000):
        if key.startswith("hold:seat:"):
            have_locks += 1
        else:
            have_ids.add(key.split(":", 1)[1])
    if have_ids != want_ids:
        report(problems, "hold:*", f"{len(have_ids - want_ids)} holds a mais e {len(want_ids - have_ids)} em falta")
    if have_locks != want_seat_locks:
        report(problems, "hold:seat:*", f"{have_locks} bloqueios no Redis, esperados {want_seat_locks}")

    scope = set(exp["perfs"])
    for pattern in ("sold:*", "sales:sold:*", "sales:left:*"):
        for key in r.scan_iter(match=pattern, count=1000):
            if key.rsplit(":", 1)[1] not in scope:
                report(problems, key, "chave de uma performance fora do âmbito")

    got = {m: int(s) for m, s in r.zrange(TRENDING_KEY, 0, -1, withscores=True)}
    if got != exp["trending"]:
        report(problems, TRENDING_KEY,
               f"{len(got)} eventos no Redis, {len(exp['trending'])} esperados")

    if problems:
        print(f"verify: {len(problems)} diferenças")
        for p in problems[:MAX_SHOWN]:
            print("  -", p)
        if len(problems) > MAX_SHOWN:
            print(f"  ... e mais {len(problems) - MAX_SHOWN}")
        return 1

    print(f"verify: OK ({len(exp['perfs'])} performances, {len(exp['holds'])} holds, "
          f"{len(exp['trending'])} eventos em trending)")
    return 0


if __name__ == "__main__":
    sys.exit(main())