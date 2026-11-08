"""tabelas base: organisers, venues, gates

Revision ID: 0001
Revises: 0000
"""

from alembic import op

revision = "0001"
down_revision = "0000"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE organisers (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_name  text NOT NULL,
            nif           char(9) NOT NULL,
            contact_email text NOT NULL,
            phone         text NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE venues (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name         text NOT NULL,
            city         text NOT NULL,
            address      text NOT NULL,
            max_capacity integer NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE gates (
            id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            venue_id uuid NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
            name     text NOT NULL
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS gates")
    op.execute("DROP TABLE IF EXISTS venues")
    op.execute("DROP TABLE IF EXISTS organisers")
