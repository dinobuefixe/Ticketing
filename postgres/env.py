"""Ambiente do Alembic. Liga-se com MIGRATION_DATABASE_URL (role owner)."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config

url = os.environ.get("MIGRATION_DATABASE_URL")
if not url:
    raise RuntimeError("a variável MIGRATION_DATABASE_URL não está definida (ver .env.example)")

# O configparser do Alembic trata % como especial, por isso escapa-se
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

# Não usamos modelos do SQLAlchemy: o esquema é escrito em SQL nas migrações
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()