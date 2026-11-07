#!/usr/bin/env bash
# Cria (ou atualiza, se já existirem) as contas de PostgreSQL e MongoDB.
# Pode ser corrido várias vezes sem erro. Lê tudo do .env.
# O Redis não tem contas: só tem a password (REDIS_PASSWORD) definida no compose.yml.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
. ./.env
set +a

# ---------- PostgreSQL ----------
# Corre como superuser. Cada bloco cria o role se não existir e define sempre a password.
# \gexec executa o SQL gerado pelo format(). :'var' põe o valor como literal, :"var" como identificador.

echo "[PostgreSQL] roles e base de dados"
docker compose exec -T postgres psql \
    -U "$POSTGRES_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
    -v db="$POSTGRES_DB" \
    -v owner_user="$POSTGRES_OWNER_USER" -v owner_pw="$POSTGRES_OWNER_PASSWORD" \
    -v app_user="$POSTGRES_APP_USER" -v app_pw="$POSTGRES_APP_PASSWORD" \
    -v ro_user="$POSTGRES_READONLY_USER" -v ro_pw="$POSTGRES_READONLY_PASSWORD" <<'SQL'
-- owner: aplica as migrações
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'owner_user', :'owner_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'owner_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'owner_user', :'owner_pw') \gexec

-- app: usada pela API, sem superuser nem CREATE
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_pw') \gexec

-- leitura: relatórios e exportação
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'ro_user', :'ro_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'ro_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'ro_user', :'ro_pw') \gexec

-- base de dados do projeto, com o owner como dono
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
SQL

echo "[PostgreSQL] extensões e dono do schema public"
docker compose exec -T postgres psql \
    -U "$POSTGRES_SUPERUSER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
    -v owner_user="$POSTGRES_OWNER_USER" <<'SQL'
-- Extensões que precisam de superuser (btree_gist é usada pela migração 0006)
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- No PostgreSQL 15 e superiores, só o dono pode criar tabelas no schema public
ALTER SCHEMA public OWNER TO :"owner_user";
SQL

# ---------- MongoDB ----------
# Corre como root do MongoDB. Cria o utilizador da app com readWrite só na base do projeto,
# ou atualiza a password se já existir. As variáveis vão por -e, para não haver problemas com aspas.

echo "[MongoDB] utilizador da app"
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

echo "Contas criadas ou atualizadas."
