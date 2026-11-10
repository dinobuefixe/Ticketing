## Keys

Redis holds data that is **fast and disposable**. PostgreSQL is the source of truth; every
key below can be rebuilt from it with `redis/rebuild.py`, except the rate-limit counters,
which only live one minute.

| Key | Type | Content | TTL | Written by | Used by |
|---|---|---|---|---|---|
| `sold:{performance}` | set | ids of the sold seats | none | checkout | F1 seat map |
| `hold:{hold}` | hash | `customer`, `performance` | until the hold expires (10 min) | hold | F2, F3 |
| `hold:seat:{performance}:{seat}` | string | id of the hold that locks the seat | same as the hold | hold | F2 (blocks double holds) |
| `sales:sold:{performance}` | hash | `section -> tickets sold` | none | checkout | live counters |
| `sales:left:{performance}` | hash | `section -> places left` | none | hold, checkout | live counters, F1 |
| `sales:trending` | sorted set | `event -> tickets sold in the last hour` | none | checkout (`trending.lua`) | "trending now" |
| `ratelimit:{customer}` | <string> | <counter of hold attempts> | 60 s | hold | limit of 10 attempts per minute |

(Adjust names, types and TTLs to what the code really does.)

Places left in a section = capacity - tickets sold - places in active holds.

### Why each expiry

- **Hold, 10 minutes:** Redis deletes the key by itself, so seats become available again
  without any job or person. The `expires_at` column in PostgreSQL is the record; the TTL
  is the mechanism.
- **Rate limit, 1 minute:** the counter only needs to remember the current minute.
- **Trending, last hour:** <how the window is kept>.

## Rebuild and verification

`redis/rebuild.py` reads PostgreSQL (read-only role) and rewrites every key above. It only
deletes keys with the prefixes `sold:`, `hold:` and `sales:` (never `FLUSHALL`), so the rate
limit is untouched. Active holds are recreated with the **remaining** time to `expires_at`,
not 10 new minutes. It only covers performances that are `scheduled`, `on_sale` or
`sold_out`: finished performances are not shown in the seat map.

`redis/verify.py` computes the same expected state from PostgreSQL and compares it with
Redis. It exits `0` if they match and `1` with a list of differences otherwise.

```bash
docker compose exec redis redis-cli FLUSHALL
uv run python redis/rebuild.py
uv run python redis/verify.py      # exit code 0
```

Run `verify.py` with no traffic: sales happening in the middle give legitimate differences,
and the trending window moves every minute.

## Cache proof (F1)

The second request for the same seat map must not query PostgreSQL. To prove it, statement
logging is turned on (`PG_LOG_STATEMENT=all` in `.env`), the same map is requested twice and
the PostgreSQL log is read after the second request.

First request (reads PostgreSQL and fills the cache):
```
<paste the SELECT lines from the log>
```
Second request (no SELECT):
```
<paste: 0 statements>
```
Turn the logging back to `none` afterwards: with `all` the seed is much slower.