# Concurrency

## Part 2: last places and promo code (M2)

Both scenarios have the same rule: PostgreSQL decides, and the application only asks. Redis is a cache and a lock helper. If it is wrong or down, the database still refuses a bad sale.

### Last places

**Scenario.** A standing section has 10 places left. 100 customers each hold 1 place and pay at the same moment (`app/tests/test_last_places.py`).

**Mechanism.**
1. The hold step (`POST /performances/{id}/holds`) reserves places in Redis with `WATCH` and `MULTI/EXEC`. If another request changes the places counter between the read and the write, the transaction is repeated. A request that finds fewer places than it asked for is refused, so almost all the surplus requests stop here.
2. A request that still reaches checkout meets the trigger `tickets_standing_capacity` (migration `0014`). It runs before each ticket insert, locks the section row with `FOR UPDATE`, counts the `valid` and `used` tickets for that performance and section, and refuses the insert when the section is full.
3. Because of the lock, two buyers of the same section wait in line, so each one counts the tickets correctly. The refused buyer gets a conflict error (HTTP 409), not a server error.
4. The database role of the app needs `UPDATE` on `sections` for the `FOR UPDATE` lock. It is granted in `scripts/setup.sh`.

**Expected result.** Exactly 10 payments succeed, 90 are refused, PostgreSQL has exactly 10 valid tickets in the section, and there are no 5xx errors.

**Result of the last run** (local PostgreSQL 16 and Redis, the real hold and checkout routes, 100 customers, 10 places):

| Clients | Places | Payments accepted (200) | Refused | Server errors | Valid tickets in the section |
|---------|--------|-------------------------|---------|---------------|------------------------------|
| 100 | 10 | 10 | 90 | 0 | 10 |

The rule holds. Run it with `python scripts/run_concurrency.py --only last-places`.

### Promo code

**Scenario.** A promo code with a maximum of 5 uses. 20 customers pay at the same moment with it (`app/tests/test_promo.py`). Each customer already has an active hold on one seat, created directly in PostgreSQL, so the test isolates the checkout.

**Mechanism.**
1. At checkout, the promo code row is read with `FOR UPDATE`. The 20 requests wait for each other on this row.
2. Each request checks `uses < max_uses`, and the winner increments `uses` in the same transaction as the order.
3. The trigger `promo_codes_max_uses` (migration `0013`) is the last guard. If any code path tried to set `uses` above `max_uses`, PostgreSQL would refuse it, and checkout answers 409.
4. The app role needs `UPDATE` on `promo_codes` for the lock and the increment. It is granted in `scripts/setup.sh`.

**Expected result.** Exactly 5 payments succeed, `uses` in the database is 5, and it equals the number of paid orders with that code.

**Result of the last run** (local PostgreSQL 16 and Redis, the real checkout route):

| Clients | Max uses | Successes | Refused | Server errors | `uses` in the database |
|---------|----------|-----------|---------|---------------|------------------------|
| 20 | 5 | 5 | 15 | 0 | 5 |

The rule holds. Run it with `python scripts/run_concurrency.py --only promo`.

### Counters in Redis

After a paid order or a refund, `checkout.py` and `cancel.py` update `sales:sold:{performance}` and `sales:trending` in one Redis transaction. This is best-effort: if Redis fails, the sale or the refund is still saved in PostgreSQL and a warning is logged. `redis/rebuild.py` recreates the counters from PostgreSQL, and `redis/verify.py` checks them.