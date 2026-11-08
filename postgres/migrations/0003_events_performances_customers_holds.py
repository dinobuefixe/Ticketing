"""tabelas base: events, performances, section_prices, customers, holds, hold_items

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE events (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            organiser_id uuid NOT NULL REFERENCES organisers(id) ON DELETE RESTRICT,
            title        text NOT NULL,
            category     text NOT NULL,
            min_age      smallint NOT NULL,
            description  text NOT NULL DEFAULT '',
            details      jsonb NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("""
        CREATE TABLE performances (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id      uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
            venue_id      uuid NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
            starts_at     timestamptz NOT NULL,
            ends_at       timestamptz NOT NULL,
            sales_open_at timestamptz NOT NULL,
            status        text NOT NULL DEFAULT 'scheduled'
        )
    """)
    op.execute("""
        CREATE TABLE section_prices (
            performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            section_id     uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            price          numeric(10, 2) NOT NULL,
            PRIMARY KEY (performance_id, section_id)
        )
    """)
    op.execute("""
        CREATE TABLE customers (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name          text NOT NULL,
            email         text NOT NULL,
            password_hash text NOT NULL,
            date_of_birth date NOT NULL,
            phone         text NOT NULL,
            registered_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE holds (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id    uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            status         text NOT NULL DEFAULT 'active',
            created_at     timestamptz NOT NULL DEFAULT now(),
            expires_at     timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE hold_items (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            hold_id    uuid NOT NULL REFERENCES holds(id) ON DELETE CASCADE,
            section_id uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            seat_id    uuid REFERENCES seats(id) ON DELETE RESTRICT,
            places     integer
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS hold_items")
    op.execute("DROP TABLE IF EXISTS holds")
    op.execute("DROP TABLE IF EXISTS customers")
    op.execute("DROP TABLE IF EXISTS section_prices")
    op.execute("DROP TABLE IF EXISTS performances")
    op.execute("DROP TABLE IF EXISTS events")
