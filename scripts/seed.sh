
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
. ./.env
set +a

SCRIPT_START=$(date +%s)


psql_owner() {
    docker compose exec -T -e PGPASSWORD="$POSTGRES_OWNER_PASSWORD" postgres \
        psql -U "$POSTGRES_OWNER_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 "$@"
}


timed() {
    local label="$1"; shift
    local t0; t0=$(date +%s)
    echo "==> $label"
    "$@"
    echo "    ($(( $(date +%s) - t0 )) s)"
}


for f in postgres/seed/part1.sql postgres/seed/part2.sql \
         mongodb/seed_hold_attempts.py mongodb/export_reports.py redis/rebuild.py; do
    [ -f "$f" ] || { echo "FALTA o ficheiro $f"; exit 1; }
done

docker compose exec -T postgres pg_isready -U "$POSTGRES_SUPERUSER" -d "$POSTGRES_DB" >/dev/null \
    || { echo "FALHOU: PostgreSQL não está a correr (docker compose up -d)"; exit 1; }

[ "$(psql_owner -At -c "SELECT to_regclass('public.scan_records') IS NOT NULL")" = "t" ] \
    || { echo "FALHOU: migrações por aplicar (alembic upgrade head)"; exit 1; }


clean_postgres() {

    psql_owner <<'SQL'
DO $$
DECLARE t text;
BEGIN
    SELECT string_agg(format('%I', tablename), ', ') INTO t
    FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version';
    EXECUTE 'TRUNCATE ' || t || ' CASCADE';
END $$;
SQL
}

seed_postgres() {
    psql_owner < postgres/seed/part1.sql
    psql_owner < postgres/seed/part2.sql
    psql_owner -c "ANALYZE"
}

timed "1/5 Limpar o PostgreSQL"                   clean_postgres
timed "2/5 Seed do PostgreSQL (part1 e part2)"    seed_postgres
timed "3/5 Seed do log de tentativas (MongoDB)"   uv run python mongodb/seed_hold_attempts.py
timed "4/5 Exportar relatórios para o MongoDB"    uv run python mongodb/export_reports.py
timed "5/5 Reconstruir o Redis"                   uv run python redis/rebuild.py


echo
psql_owner -c "
SELECT 'venues' AS tabela, count(*) FROM venues
UNION ALL SELECT 'performances', count(*) FROM performances
UNION ALL SELECT 'customers',    count(*) FROM customers
UNION ALL SELECT 'orders',       count(*) FROM orders
UNION ALL SELECT 'tickets',      count(*) FROM tickets
UNION ALL SELECT 'scan_records', count(*) FROM scan_records"

TOTAL=$(( $(date +%s) - SCRIPT_START ))
echo "Seed concluído em ${TOTAL} s"
[ "$TOTAL" -le 300 ] || echo "AVISO: demorou mais de 5 minutos (limite do brief)"