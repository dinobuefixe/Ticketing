# AI usage

I, Sabrina, used Claude (Anthropic) for my part of the project (M2, orders and tickets). I used it to learn and to speed up my work, and I kept the decisions and the checking for myself.

## Entries

| # | What I used it for | What I did with the result |
|---|--------------------|----------------------------|
| 1 | Explaining the brief, the ER model and the group rules in plain words, and planning my tasks | Followed the plan task by task, in the order of `group_management.md` |
| 2 | Purchase migrations `0010` to `0015` | The first draft used guessed names and `bigint` ids. I had it rewritten against M1's real schema (uuid ids, real column names) and fixed `down_revision` and the folder |
| 3 | Checkout, cancellations and check-in (`checkout.py`, `cancel.py`, `checkin.py`) | I rejected the first checkout because it used guessed names. It was rewritten against the real columns |
| 4 | Redis counters, first as a Lua script (`redis/trending.lua`) | The script was used until the team removed the Lua files. I then had the counters rewritten in Python inside `checkout.py` and `cancel.py`, and checked the keys against `docs/redis.md` and `redis/verify.py` |
| 5 | MongoDB sales collection and report 1 (`mongodb/sales.py`) | Used, and moved the pipeline into the shared `pipelines` folder |
| 6 | Concurrency tests (promo code, last places) | Used. I ran them against PostgreSQL and Redis with the real hold and checkout routes. MongoDB was not part of that run |
| 7 | Seed for orders, tickets, payments and scans | Added customer creation because the base seed had none, and lowered the group size so the volume matches the brief (about 450,000 orders) |
| 8 | Connecting my routers in `app/main.py` | Checked on the running app that checkout, cancel and check-in answer |
| 9 | Checking the whole project on `main` before delivery | It found problems in other people's files: wrong import names in `holds.py`, a file name that `seed.sh` could not find, and missing `UPDATE` grants on `performances` and `sections`. I did not fix them myself, I sent the list to the owner of each file |
| 10 | Git and GitHub help, PR descriptions, and these docs | Followed the steps myself, one command at a time |

## Declaration

I used Claude as a learning aid and assistant, as listed above. I asked it to explain things, I read what it produced, I rejected and corrected what did not match our real schema or the brief, and I committed the result myself. I am responsible for everything in my files and can explain how it works.



## Dinis

## Entries

| # | What I used it for | What I did with the result |
|---|--------------------|----------------------------|
| 1 | Planning the group work: splitting the tasks, time estimates and `group_management.md` | The first split was by database engine, which the README forbids. I rewrote it so each member owns a complete part (PostgreSQL, MongoDB, Redis and the app), with the setup done by one person first |
| 2 | PostgreSQL schema: 16 tables, as Alembic migrations `0000` to `0012` | The first draft put the rules inside the table definitions. I split it so the base tables are in `0001` to `0003` and the rules in `0004` to `0006`, as the plan says. I also wrote a 17th table by mistake and removed it. The result was checked for valid Python only, not run against a database |
| 3 | Seed `postgres/seed/part1.sql`: organisers, venues, gates, sections, seats, events, performances and prices | Used the same UUIDs on every run (`md5`, no `random()`) so the seed is repeatable. Added a check block that stops the seed if the counts differ from the brief. Not run yet |
| 4 | Setup: `scripts/setup.sh` steps 1 to 4, `scripts/healthy.sh`, `mongodb/setup_collections.js` | Used as a base and adapted to the `.env` names. Step 2 (migrations and grants) and the MongoDB check were added later. I did not run the script; I checked the shell syntax only |
| 5 | Health endpoint in `app/routes/health.py` | Moved from `app/health.py` into a router. Checked the file compiles; not tested against the running services |
| 6 | Seat map (F1) and holds (F2): `app/routes/seat_map.py`, `app/routes/holds.py`, `app/cache.py`, `app/clients.py`, `app/deps.py` | First written with Lua scripts, then rewritten in Python with `WATCH`/`MULTI` in `app/redis_ops.py` when the team removed Lua. I checked the rules against the brief line by line (6 tickets, 10 attempts per minute, 10-minute hold, age, on sale). Not run against the services |
| 7 | Hold attempt log: `app/hold_attempts.py` and the logging wrapper in `holds.py` | Every attempt is logged, refused ones included, with the reason. The module first lived in `mongodb/` and was moved into `app/`, because the app image only copies `app/` |
| 8 | Seed of hold attempts `mongodb/seed_hold_attempts.py` | I rewrote a draft that was not deterministic (database `random()` and `TABLESAMPLE`), did not match the venue of each performance, and could create attempts in the future. The rewrite sorts every list by id and uses a fixed seed |
| 9 | Same-seat concurrency test `app/tests/test_same_seat.py` and the naive version `app/naive_holds.py` | The test fires 50 requests at the same seat with a barrier and checks there is one active hold in the database. The naive version is switched on with `HOLD_MODE=naive` so the race can be shown. Not run |
| 10 | Trending and sales counters: `record_sale` and `trending_now` in `app/redis_ops.py` | Replaced the Lua script with Python. I did not copy the placeholder decrement of free places, because places are already taken when the hold is made, so decrementing again at sale would count them twice. Not called yet, because checkout is not finished |