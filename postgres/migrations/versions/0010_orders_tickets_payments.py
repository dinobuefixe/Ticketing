from alembic import op

revision = "0010"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE orders (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            customer_id    bigint NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            performance_id bigint NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            promo_code_id  bigint,
            status         text NOT NULL DEFAULT 'pending',
            total          numeric(10,2) NOT NULL DEFAULT 0,
            created_at     timestamptz NOT NULL DEFAULT now(),
            paid_at        timestamptz,
            CONSTRAINT orders_status_ok CHECK (
                status IN ('pending','paid','cancelled','refunded'))
        );
    """)
    op.execute("""
        CREATE TABLE tickets (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id       bigint NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
            performance_id bigint NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            section_id     bigint NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            seat_id        bigint REFERENCES seats(id) ON DELETE RESTRICT,
            price          numeric(10,2) NOT NULL,
            code           char(12) NOT NULL UNIQUE,
            status         text NOT NULL DEFAULT 'valid',
            CONSTRAINT tickets_status_ok CHECK (
                status IN ('valid','used','cancelled'))
        );
    """)
    op.execute("""
        CREATE TABLE payments (
            id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id     bigint NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
            amount       numeric(10,2) NOT NULL,
            method       text NOT NULL,
            status       text NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            provider_ref text NOT NULL UNIQUE,
            CONSTRAINT payments_method_ok CHECK (
                method IN ('card','mbway','multibanco')),
            CONSTRAINT payments_status_ok CHECK (
                status IN ('approved','declined','refunded'))
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS payments;")
    op.execute("DROP TABLE IF EXISTS tickets;")
    op.execute("DROP TABLE IF EXISTS orders;")