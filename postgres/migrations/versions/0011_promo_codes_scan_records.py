from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE promo_codes (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code        text NOT NULL UNIQUE,
            percent_off smallint,
            amount_off  numeric(10, 2),
            valid_from  timestamptz NOT NULL,
            valid_until timestamptz NOT NULL,
            event_id    uuid REFERENCES events(id) ON DELETE RESTRICT,
            max_uses    integer NOT NULL,
            uses        integer NOT NULL DEFAULT 0
        );
    """)
    op.execute("""
        ALTER TABLE orders
        ADD CONSTRAINT orders_promo_code_fk
        FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE RESTRICT;
    """)
    op.execute("""
        CREATE TABLE scan_records (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            ticket_code char(12) NOT NULL,
            gate_id     uuid NOT NULL REFERENCES gates(id) ON DELETE RESTRICT,
            ticket_id   uuid REFERENCES tickets(id) ON DELETE RESTRICT,
            staff_id    uuid NOT NULL,
            result      text NOT NULL CHECK (result IN (
                            'accepted', 'already_used', 'cancelled', 'wrong_day', 'unknown_code')),
            scanned_at  timestamptz NOT NULL DEFAULT now(),
            CHECK ((result = 'unknown_code') = (ticket_id IS NULL))
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS scan_records;")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_promo_code_fk;")
    op.execute("DROP TABLE IF EXISTS promo_codes;")