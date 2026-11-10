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