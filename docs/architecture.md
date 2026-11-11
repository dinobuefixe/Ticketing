# Architecture

## Part 2: orders, tickets, payments and check-in (M2)

### Source of truth

| Data | Source of truth | Copies | If the second write fails |
|------|-----------------|--------|---------------------------|
| Orders, tickets, payments, promo code uses, scan records | PostgreSQL | none | Not applicable. Everything is written in one transaction. |
| Sale counters and the "trending now" list | PostgreSQL (derived) | Redis | The sale stays valid. The failure is logged and the counters are rebuilt from PostgreSQL with `redis/rebuild.py`. `redis/verify.py` shows any difference. |
| Reports (orders and performances) | PostgreSQL (derived) | MongoDB `report_orders` and `report_performances` | PostgreSQL is not affected. The reports are old until `mongodb/export_reports.py` runs again. The export can run any number of times and gives the same result. |

### Why PostgreSQL is written first

Money and tickets must never depend on a cache. At checkout, the order, the payment, the tickets, the promo code use and the hold status change together in one PostgreSQL transaction. Only after it commits does the app update Redis. If Redis is down, the customer still has a valid ticket.

### Where each rule is enforced

| Rule | Where |
|------|-------|
| A seat never has two valid or used tickets for one performance | PostgreSQL, partial unique index `tickets_one_valid_seat` |
| A standing section never sells more than its capacity | PostgreSQL, trigger `tickets_standing_capacity` |
| A promo code is never used more than its maximum | PostgreSQL, trigger `promo_codes_max_uses`, plus a row lock in checkout |
| A promo code has a percentage or a fixed amount, never both | PostgreSQL, CHECK `promo_one_kind` |
| Prices, totals and payment amounts are never negative | PostgreSQL, CHECK constraints |
| The app role never updates or deletes scan records | PostgreSQL, `REVOKE UPDATE, DELETE` on `scan_records` |
| Cancellation only up to 48 hours before the performance | App (`cancel.py`) |
| Check-in only on the day of the performance (Lisbon time) | App (`checkin.py`) |
| An expired hold cannot be paid | App (`checkout.py`) |

The app rules are in the app because they depend on the current time and are cheap to check. The rules that protect money and seats are in PostgreSQL, so they hold even if the app has a bug.

### Data that expires

| Data | How long it lives | Where |
|------|-------------------|-------|
| The "trending now" window | Sales of the last hour | Redis. Sales are counted in one key per minute (`sales:trending:{minute}`), each with a TTL of 3660 seconds. The list `sales:trending` is rebuilt from the last 60 minute keys after every sale or cancellation. |

These counters are derived data. If they are lost, `redis/rebuild.py` rebuilds them from PostgreSQL.