"""regra: duas performances no mesmo local não se podem sobrepor

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # btree_gist permite misturar igualdade (venue_id) com intervalos no EXCLUDE
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # Performances canceladas não bloqueiam o local
    op.execute("""
        ALTER TABLE performances
            ADD CONSTRAINT performances_no_overlap
            EXCLUDE USING gist (
                venue_id WITH =,
                tstzrange(starts_at, ends_at) WITH &&
            ) WHERE (status <> 'cancelled')
    """)


def downgrade():
    op.execute("ALTER TABLE performances DROP CONSTRAINT IF EXISTS performances_no_overlap")
