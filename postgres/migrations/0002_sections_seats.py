"""tabelas base: sections, seats

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE sections (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            venue_id          uuid NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
            name              text NOT NULL,
            kind              text NOT NULL,
            standing_capacity integer
        )
    """)
    op.execute("""
        CREATE TABLE seats (
            id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            section_id               uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            row_label                text NOT NULL,
            seat_number              integer NOT NULL,
            is_wheelchair_accessible boolean NOT NULL DEFAULT false,
            is_restricted_view       boolean NOT NULL DEFAULT false
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS seats")
    op.execute("DROP TABLE IF EXISTS sections")
