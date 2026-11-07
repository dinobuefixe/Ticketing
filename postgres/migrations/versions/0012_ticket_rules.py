from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX tickets_one_seat_per_performance
        ON tickets (performance_id, seat_id)
        WHERE seat_id IS NOT NULL AND status IN ('valid','used');
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS tickets_one_seat_per_performance;")