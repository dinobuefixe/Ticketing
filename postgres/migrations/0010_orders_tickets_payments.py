from alembic import op

revision = "0010"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE orders (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id    uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            hold_id        uuid REFERENCES holds(id) ON DELETE RESTRICT,
            promo_code_id  uuid,
            status         text NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded')),
            total          numeric(10, 2) NOT NULL DEFAULT 0,
            created_at     timestamptz NOT NULL DEFAULT now(),
            paid_at        timestamptz,
            CHECK (status <> 'paid' OR paid_at IS NOT NULL)
        );
    """)
    op.execute("""
        CREATE TABLE tickets (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            order_id       uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
            performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            section_id     uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            seat_id        uuid REFERENCES seats(id) ON DELETE RESTRICT,
            price_paid     numeric(10, 2) NOT NULL,
            code           char(12) NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9]{12}$'),
            status         text NOT NULL DEFAULT 'valid'
                           CHECK (status IN ('valid', 'used', 'cancelled')),
            issued_at      timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE TABLE payments (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            order_id           uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
            amount             numeric(10, 2) NOT NULL,
            method             text NOT NULL CHECK (method IN ('card', 'mbway', 'multibanco')),
            status             text NOT NULL CHECK (status IN ('approved', 'declined', 'refunded')),
            created_at         timestamptz NOT NULL DEFAULT now(),
            provider_reference text NOT NULL UNIQUE
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS payments;")
    op.execute("DROP TABLE IF EXISTS tickets;")
    op.execute("DROP TABLE IF EXISTS orders;")