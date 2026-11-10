# MongoDB

MongoDB holds data that is **derived** from PostgreSQL or that is **append-only logging**.
It is never the source of truth for tickets, orders, seats or payments: PostgreSQL is
(see `docs/architecture.md`). Everything in MongoDB can be rebuilt from PostgreSQL, except
the hold-attempt log, which is a record of events and is kept for 90 days.

The application connects as `ticketing_app` (role `readWrite` on the `ticketing` database
only). `root` is used only by `scripts/setup.sh`.

## Where event details are stored

Details that depend on the category (line-up, cast, home team, ...) are stored in a
`jsonb` column `events.details` in PostgreSQL, not in MongoDB and not in extra tables.

Why:

- **No schema change for a new category.** A new category adds new keys to the JSON, not a migration.
- **One database for the event.** The details are read together with the event title and organiser, so they live in the same row, in the same transaction.
- **Still constrained.** The category and minimum age are checked columns, and PostgreSQL can index `jsonb` (GIN) if a query needs it.
- **Why not separate tables:** one table per category means a migration per new category, which is exactly what the company wants to avoid.
- **Why not MongoDB:** it would split one event over two engines, and a failed write to the second would leave an event without its details.

## Collections

| Collection | Written by | Source of truth | Documents | Created by |
|---|---|---|---|---|
| `hold_attempts` | the app, on every hold attempt (and `mongodb/seed_hold_attempts.py` for demo data) | MongoDB (event log) | one per attempt | `mongodb/setup_collections.js` |
| `report_orders` | `mongodb/export_reports.py` | PostgreSQL | one per `paid` or `refunded` order | `mongodb/setup_collections.js` |
| `report_performances` | `mongodb/export_reports.py` | PostgreSQL | one per performance | `mongodb/setup_collections.js` |
| `<sales collection>` | `mongodb/sales.py` | PostgreSQL | `<one per performance>` | `<file>` |

All validators use `validationLevel: strict` and `validationAction: error`: a malformed
document is rejected instead of stored. `scripts/setup.sh` can be run again at any time:
collections are created the first time and updated afterwards.

### `hold_attempts`

One document per hold attempt, accepted or refused.

| Field | Type | Meaning |
|---|---|---|
| `customer_id` | string | UUID of the customer |
| `performance_id` | string | UUID of the performance |
| `requested` | object | `seat_ids` (seated) or `section_id` and `places` (standing) |
| `result` | `accepted` / `refused` | outcome of the attempt |
| `reason` | string or null | why it was refused (`seat_taken`, `limit_6_tickets`, `rate_limit`, ...) |
| `attempted_at` | date | when the attempt was made |

Indexes:

- `attempted_at_ttl`: TTL index, 90 days. MongoDB deletes old attempts by itself.
- `performance_attempted_at`: `performance_id` ascending, `attempted_at` descending.

Used by report 6.

### `report_orders`

One document per `paid` or `refunded` order, with its tickets embedded (a ticket is never
read without its order). Used by reports 2, 3 and 5.

| Field | Type | Meaning |
|---|---|---|
| `_id` | string | order UUID (makes the export idempotent) |
| `status` | `paid` / `refunded` | revenue counts only `paid` |
| `performance_id`, `event_id`, `event_title`, `organiser_id`, `venue_id`, `city` | string | denormalised so reports need no join |
| `paid_at` | date | when the order was paid |
| `total_cents` | int | order total in cents |
| `discount_cents` | int | discount given by the promo code, in cents |
| `promo_code` | string or null | code used, if any |
| `method` | string or null | payment method of the approved payment |
| `tickets` | array | `section_id`, `price_cents` and `status` of each ticket |
| `exported_at` | date | export run that wrote the document |

Index: `status_paid_at` (`status`, `paid_at`).

### `report_performances`

One document per performance, with sales per section. Used by report 4.

| Field | Type | Meaning |
|---|---|---|
| `_id` | string | performance UUID |
| `status`, `starts_at`, `event_id`, `event_title`, `category` | | denormalised from PostgreSQL |
| `venue_id`, `venue_name`, `city` | string | where it takes place |
| `seated_capacity`, `standing_capacity` | int | capacity of the venue, seated and standing apart |
| `sections` | array | per section: `section_id`, `name`, `kind`, `sold`, `gross_cents` |
| `tickets_sold`, `gross_cents`, `checked_in` | int | totals |
| `exported_at` | date | export run that wrote the document |

Index: `status_starts_at` (`status`, `starts_at`).

### Design decisions

- **Money is stored in cents (integers).** MongoDB cannot store PostgreSQL's `numeric` directly, and floats give rounding errors. Pipelines convert to euros only in the last stage.
- **Report collections are a mirror.** `export_reports.py` upserts every document by `_id` and deletes the ones not touched in the run, so running it twice gives the same result and rows removed from PostgreSQL disappear.
- **The export reads PostgreSQL with the read-only role** (`READONLY_DATABASE_URL`), so a bug in it cannot change business data.
- **If the export fails halfway,** PostgreSQL is untouched and the collections keep their previous content. Run the export again (see `docs/runbook.md`).
- **Demo data.** `mongodb/seed_hold_attempts.py` writes 60,000 synthetic attempts in the last 90 days. They do not correspond to real holds.

## Report pipelines

All pipelines live in `mongodb/pipelines/` as `{ "collection", "description", "pipeline" }`.
Run one with:

```bash
uv run python mongodb/run_pipeline.py <n> --limit 3
```

The same pipelines are served by the app under `/reports/...` (see the README).
Money is stored in cents and converted to euros in the last stage. Dates and hours use the
`Europe/Lisbon` time zone. "Revenue" counts only `paid` orders, because refunded orders gave
the money back.

| # | File | Collection | Question it answers |
|---|---|---|---|
| 1 | `report1.json` | `<sales collection>` | Sales, revenue per section, per payment method, promo codes and check-in rate per performance |
| 2 | `report2.json` | `report_orders` | Revenue per organiser per month, current month plus the previous 11 |
| 3 | `report3.json` | `report_orders` | The 10 events that sold most tickets in each city in the last 30 days |
| 4 | `report4.json` | `report_performances` | Average percentage of capacity sold per venue in the last 90 days, seated and standing apart |
| 5 | `report5.json` | `report_orders` | Per promo code: orders, total discount, average order value with and without a code for the same events |
| 6 | `report6.json` | `hold_attempts` | Hours of the day with most refused hold attempts |

### Report 2: revenue per organiser per month

Two `$match` stages on purpose: the first (`status`) can use the `status_paid_at` index, the
second computes the start of the 12-month window with `$expr`.

Sample result:

```json
<paste the output of: uv run python mongodb/run_pipeline.py 2 --limit 3>
```

### Report 3: top 10 events per city

Groups by city and event, sorts, then groups again with `$push` and keeps 10 with `$slice`.
The sort has a tie-break on `event_id`, so the result is stable.

Sample result:

```json
<paste the output of: uv run python mongodb/run_pipeline.py 3 --limit 2>
```

### Report 4: occupancy per venue

Cancelled and future performances are excluded (they do not fill seats yet). Seated and
standing sold counts are computed from `sections`. A venue without a standing area gets
`avg_standing_pct: null` instead of 0%, because `$avg` ignores `null`.

Sample result:

```json
<paste the output of: uv run python mongodb/run_pipeline.py 4 --limit 3>
```

### Report 5: promo code effectiveness

Orders are grouped by event and code first. For each event, the group without a code is
attached to each code's group, so the "with" and "without" averages compare orders of the
same events, as the brief asks.

Sample result:

```json
<paste the output of: uv run python mongodb/run_pipeline.py 5 --limit 3>
```

### Report 6: hours with most failed attempts

Sample result:

```json
<paste the output of: uv run python mongodb/run_pipeline.py 6 --limit 5>
```

**Limitation.** The hold-attempt log records the outcome of the hold, not whether the
customer paid afterwards. "Did not end in a sale" is therefore approximated by refused
attempts.