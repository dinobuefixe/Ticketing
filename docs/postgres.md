## Holds

A hold is a temporary reservation of seats (seated) or places (standing) for one customer
and one performance. PostgreSQL is the record of holds; Redis is the fast lock that
decides who gets a seat (see `docs/redis.md`, section "Holds").

### Tables

**`holds`**: one row per reservation.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Also used as the `hold_id` in Redis |
| `customer_id` | uuid | FK to `customers`, `ON DELETE RESTRICT` |
| `performance_id` | uuid | FK to `performances`, `ON DELETE RESTRICT` |
| `status` | text | `active`, `converted`, `expired` or `released` (CHECK constraint, migration 0004) |
| `created_at` | timestamptz | `now()` |
| `expires_at` | timestamptz | `now() + 600 s` at creation (`HOLD_TTL_SECONDS` in `app/routes/holds.py`) |

**`hold_items`**: the seats or places inside a hold.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `hold_id` | uuid | FK to `holds`, `ON DELETE CASCADE` |
| `section_id` | uuid | FK to `sections`, `ON DELETE RESTRICT` |
| `seat_id` | uuid, nullable | Set for seated sections, `NULL` for standing |
| `places` | integer, nullable | Set for standing sections, `NULL` for seated |

A seated hold has one `hold_items` row per seat (`seat_id` filled, `places` `NULL`).
A standing hold has one row with `seat_id` `NULL` and `places` set to the number of places.

### Index

`holds_perf_status_idx` on `holds (performance_id, status)` (migration 0020). It serves
the "active holds of a performance" queries used for the seat map, the places left and the
rebuild of Redis.

### Life cycle

1. **Creation** (`POST /performances/{id}/holds`). The app checks the performance, the
   customer's age and the limit of 6 tickets per performance (tickets already bought plus
   places in active holds that have not expired). It then reserves the seats in Redis and
   only after that inserts the `holds` row and its `hold_items`. If the insert fails, the
   Redis reservation is released and the request returns `503`.
2. **Converted** (`status = 'converted'`). Set by checkout when the order is paid
   (`app/routes/checkout.py`).
3. **Expired** (`status = 'expired'`). Set by checkout when someone tries to pay a hold
   that has already run out (`app/routes/checkout.py`).
4. **Released** (`status = 'released'`). Set for all active holds of a performance when it
   is cancelled (`app/routes/cancel.py`).

No job changes a hold to `expired` when its time runs out. The row stays `active` until
checkout or cancellation touches it. A hold is therefore effective only when
`status = 'active' AND expires_at > now()`. Every query that counts holds uses this
condition, so a hold that has run out stops counting even though its row still says
`active`.

### Queries that depend on holds

- Limit of 6 tickets per customer and performance: sum of the places in active, unexpired
  holds plus `valid` and `used` tickets of that customer.
- Places left per section (used by `redis/rebuild.py` and `redis/verify.py`):
  `capacity - tickets sold - places in active, unexpired holds`.

### Why PostgreSQL keeps the record

Redis deletes the hold key when the TTL runs out, so after 10 minutes it knows nothing about
the hold. PostgreSQL keeps the row with `expires_at`, which lets the app explain a refusal
(for example, "hold expired" at checkout), lets the rebuild recreate active holds with the
time that remains, and keeps the history of every hold.

### Attempts

Every hold attempt, accepted or refused, is logged in MongoDB (`app/hold_attempts.py`), not
in PostgreSQL. A refused attempt, such as the `429` rate limit, leaves no row in `holds`.