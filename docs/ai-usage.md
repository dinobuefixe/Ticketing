# AI usage

I, Sabrina, used Claude (Anthropic) for my part of the project (M2, orders and tickets). I used it to learn and to speed up my work, and I kept the decisions and the checking for myself.

## Entries

| # | What I used it for | What I did with the result |
|---|--------------------|----------------------------|
| 1 | Explaining the brief, the ER model and the group rules in plain words, and planning my tasks | Followed the plan task by task, in the order of `group_management.md` |
| 2 | Purchase migrations `0010` to `0015` | The first draft used guessed names and `bigint` ids. I had it rewritten against M1's real schema (uuid ids, real column names) and fixed `down_revision` and the folder |
| 3 | Checkout, cancellations and check-in (`checkout.py`, `cancel.py`, `checkin.py`) | I rejected the first checkout because it used guessed names. It was rewritten against the real columns |
| 4 | Redis counters script (`redis/trending.lua`) | Used as written, and checked against M1's and M3's Redis keys |
| 5 | MongoDB sales collection and report 1 (`mongodb/sales.py`) | Used, and moved the pipeline into the shared `pipelines` folder |
| 6 | Concurrency tests (promo code, last places) | Used. They are run against the real stack before delivery |
| 7 | Seed for orders, tickets, payments and scans | Added customer creation because the base seed had none |
| 8 | Git and GitHub help, PR descriptions, and these docs | Followed the steps myself, one command at a time |

## Declaration

I used Claude as a learning aid and assistant, as listed above. I asked it to explain things, I read what it produced, I rejected and corrected what did not match our real schema or the brief, and I committed the result myself. I am responsible for everything in my files and can explain how it works.