from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("REVOKE UPDATE, DELETE ON scan_records FROM ticketing_app;")


def downgrade():
    op.execute("GRANT UPDATE, DELETE ON scan_records TO ticketing_app;")