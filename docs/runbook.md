# Runbook

## Requirements

Docker with Compose, and [uv](https://docs.astral.sh/uv/). Nothing else.

## Start from a clean clone

```bash
cp .env.example .env          # then replace every "change-me" in .env
docker compose up -d
./scripts/setup.sh
./scripts/seed.sh
```

| Step | What it does | Safe to repeat? |
|---|---|---|
| `docker compose up -d` | starts PostgreSQL, MongoDB, Redis and the app | yes |
| `./scripts/setup.sh` | roles and database (superuser), migrations (owner), MongoDB user, collections and indexes (root), checks Redis password | yes |
| `./scripts/seed.sh` | empties the tables, loads the PostgreSQL seed, seeds the hold-attempt log, exports the reports, rebuilds Redis | yes, it starts by cleaning |

The seed takes about <N> minutes on <machine>.
The app never connects as `postgres` or `root`.

## Check that everything is up

```bash
curl -s localhost:8000/health/services     # postgres, mongo and redis must say "ok"
curl -s localhost:8000/reports             # list of the report endpoints
```

## Concurrency test

```bash
<the exact command from the README / scripts/run_concurrency.py>
```
It prints the mode, successes, refusals and 5xx, and exits `0` if the rules hold and `1`
if not. Scenarios: <same-seat>, <last-places>.

## Routine tasks

| I want to... | Command |
|---|---|
| Refresh the reports in MongoDB | `uv run python mongodb/export_reports.py` |
| Run one report pipeline | `uv run python mongodb/run_pipeline.py 3 --limit 5` |
| Rebuild Redis from PostgreSQL | `uv run python redis/rebuild.py` |
| Check Redis against PostgreSQL | `uv run python redis/verify.py` |
| Wipe the data and seed again | `./scripts/seed.sh` |
| Start from zero, including volumes | `docker compose down -v` and the "clean clone" steps |

Scripts that run on the host read their connection strings from `.env`:
`set -a; . ./.env; set +a` before `uv run`. `seed.sh` and `setup.sh` do it themselves.

## Recovering from failures

| Situation | What to do |
|---|---|
| Redis lost its data (restart without volume, `FLUSHALL`) | `rebuild.py`, then `verify.py`. Active holds come back with the time they had left |
| MongoDB report collections are empty or stale | `export_reports.py` (idempotent) |
| The export failed halfway | Run it again. PostgreSQL is never written by it |
| `hold_attempts` lost | Not rebuildable (it is a log). `seed_hold_attempts.py` creates demo data only |
| A new migration is needed | `uv run alembic -c postgres/alembic.ini upgrade head` with `MIGRATION_DATABASE_URL` set |

## Common problems

| Symptom | Cause and fix |
|---|---|
| `KeyError: 'READONLY_DATABASE_URL'` | `.env` not loaded: `set -a; . ./.env; set +a` |
| `permission denied for table ...` | Grants migration not applied: run `alembic upgrade head` |
| `NOAUTH Authentication required` | `REDIS_PASSWORD` in `.env` changed after the container was created: `docker compose up -d --force-recreate redis` |
| MongoDB `Authentication failed` | Passwords in `.env` changed after the first start: run `./scripts/setup.sh` again |
| `port is already allocated` | Another PostgreSQL, MongoDB or Redis is using 5432, 27017 or 6379 |
| Seed is slow | Check `PG_LOG_STATEMENT` is `none` in `.env` |