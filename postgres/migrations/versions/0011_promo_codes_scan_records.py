from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE promo_codes (
            id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code             text NOT NULL UNIQUE,
            discount_percent integer,
            discount_amount  numeric(10,2),
            valid_from       timestamptz NOT NULL,
            valid_to         timestamptz NOT NULL,
            event_id         bigint REFERENCES events(id) ON DELETE RESTRICT,
            max_uses         integer NOT NULL,
            uses             integer NOT NULL DEFAULT 0
        );
    """)
    op.execute("""
        ALTER TABLE orders
        ADD CONSTRAINT orders_promo_code_fk
        FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE RESTRICT;
    """)
    op.execute("""
        CREATE TABLE scan_records (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code_read  text NOT NULL,
            ticket_id  bigint REFERENCES tickets(id) ON DELETE RESTRICT,
            gate_id    bigint NOT NULL REFERENCES gates(id) ON DELETE RESTRICT,
            staff_name text NOT NULL,
            scanned_at timestamptz NOT NULL DEFAULT now(),
            result     text NOT NULL,
            CONSTRAINT scan_records_result_ok CHECK (
                result IN ('accepted','already_used','cancelled',
                           'wrong_day','unknown_code'))
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS scan_records;")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_promo_code_fk;")
    op.execute("DROP TABLE IF EXISTS promo_codes;")