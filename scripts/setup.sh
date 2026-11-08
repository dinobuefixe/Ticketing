#!/usr/bin/env bash
# Setup do projeto. Pode ser corrido várias vezes sem erro. Lê tudo do .env.
#   Passo 1: PostgreSQL, roles, base de dados e extensões (superuser)
#   Passo 3: MongoDB, utilizador da app, coleções e índices (root)
#   Passo 4: Redis, confirma que responde com password e não responde sem ela
# O passo 2 (migrações Alembic, como owner) ainda não está incluído.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
. ./.env
set +a

# ---------- Passo 1: PostgreSQL ----------
echo "Passo 1: roles, base de dados e extensões (superuser)"

docker compose exec -T postgres psql \
    -U "$POSTGRES_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
    -v db="$POSTGRES_DB" \
    -v owner_user="$POSTGRES_OWNER_USER" -v owner_pw="$POSTGRES_OWNER_PASSWORD" \
    -v app_user="$POSTGRES_APP_USER" -v app_pw="$POSTGRES_APP_PASSWORD" \
    -v ro_user="$POSTGRES_READONLY_USER" -v ro_pw="$POSTGRES_READONLY_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'owner_user', :'owner_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'owner_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'owner_user', :'owner_pw') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_pw') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'ro_user', :'ro_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'ro_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'ro_user', :'ro_pw') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
SQL

docker compose exec -T postgres psql \
    -U "$POSTGRES_SUPERUSER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
    -v owner_user="$POSTGRES_OWNER_USER" <<'SQL'
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
ALTER SCHEMA public OWNER TO :"owner_user";
SQL

echo "Passo 1 concluído."

# ---------- Passo 3: MongoDB ----------
echo "Passo 3: MongoDB, utilizador da app, coleções e índices (root)"

docker compose exec -T \
    -e DB="$MONGO_DB" -e APP_USER="$MONGO_APP_USER" -e APP_PW="$MONGO_APP_PASSWORD" \
    mongo mongosh --quiet \
    -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
    --eval '
const d = db.getSiblingDB(process.env.DB);
if (d.getUser(process.env.APP_USER)) {
  d.updateUser(process.env.APP_USER, { pwd: process.env.APP_PW });
  print("utilizador atualizado: " + process.env.APP_USER);
} else {
  d.createUser({
    user: process.env.APP_USER,
    pwd: process.env.APP_PW,
    roles: [{ role: "readWrite", db: process.env.DB }]
  });
  print("utilizador criado: " + process.env.APP_USER);
}
'

cat mongodb/setup_collections.js | docker compose exec -T \
    -e DB="$MONGO_DB" \
    mongo mongosh --quiet \
    -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin

echo "Passo 3 concluído."

# ---------- Passo 4: Redis ----------
echo "Passo 4: Redis, password"

# Com a password tem de responder PONG
docker compose exec -T -e REDISCLI_AUTH="$REDIS_PASSWORD" redis redis-cli ping | grep -q PONG \
    || { echo "FALHOU: Redis não responde com a password"; exit 1; }

# Sem password não pode responder. O compose.yml define REDISCLI_AUTH no container,
# por isso é preciso removê-la para testar sem autenticação.
if docker compose exec -T redis env -u REDISCLI_AUTH redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "FALHOU: Redis responde sem password"
    exit 1
fi

echo "Passo 4 concluído."
echo "Setup concluído."