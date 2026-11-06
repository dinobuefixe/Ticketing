from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE staff (
            id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name text NOT NULL
        );
    """)

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
            uses             integer NOT NULL DEFAULT 0,
            CONSTRAINT promo_one_kind CHECK (
                (discount_percent IS NOT NULL) <> (discount_amount IS NOT NULL)),
            CONSTRAINT promo_percent_range CHECK (
                discount_percent IS NULL OR discount_percent BETWEEN 1 AND 100),
            CONSTRAINT promo_amount_positive CHECK (
                discount_amount IS NULL OR discount_amount > 0),
            CONSTRAINT promo_period_ok CHECK (valid_to > valid_from),
            CONSTRAINT promo_max_uses_positive CHECK (max_uses > 0),
            CONSTRAINT promo_uses_limit CHECK (uses >= 0 AND uses <= max_uses)
        );
    """)

    op.execute("""
        CREATE TABLE orders (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            customer_id    bigint NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            performance_id bigint NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
            promo_code_id  bigint REFERENCES promo_codes(id) ON DELETE RESTRICT,
            status         text NOT NULL DEFAULT 'pending',
            total          numeric(10,2) NOT NULL DEFAULT 0,
            created_at     timestamptz NOT NULL DEFAULT now(),
            paid_at        timestamptz,
            CONSTRAINT orders_status_ok CHECK (
                status IN ('pending','paid','cancelled','refunded')),
            CONSTRAINT orders_total_ok CHECK (total >= 0)
        );
    """)

    op.execute("""
        CREATE TABLE order_lines (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id   bigint NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            section_id bigint NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
            seat_id    bigint REFERENCES seats(id) ON DELETE RESTRICT,
            unit_price numeric(10,2) NOT NULL,
            CONSTRAINT order_lines_price_ok CHECK (unit_price >= 0)
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
            CONSTRAINT tickets_price_ok CHECK (price >= 0),
            CONSTRAINT tickets_status_ok CHECK (
                status IN ('valid','used','cancelled'))
        );
    """)

    op.execute("""
        CREATE UNIQUE INDEX tickets_one_seat_per_performance
        ON tickets (performance_id, seat_id)
        WHERE seat_id IS NOT NULL AND status IN ('valid','used');
    """)

    op.execute("""
        CREATE FUNCTION check_standing_capacity() RETURNS trigger AS $$
        DECLARE
            cap  integer;
            sold integer;
        BEGIN
            IF NEW.seat_id IS NULL AND NEW.status IN ('valid','used') THEN
                SELECT capacity INTO cap
                FROM sections WHERE id = NEW.section_id FOR UPDATE;

                SELECT count(*) INTO sold FROM tickets
                WHERE performance_id = NEW.performance_id
                  AND section_id = NEW.section_id
                  AND seat_id IS NULL
                  AND status IN ('valid','used')
                  AND id <> NEW.id;

                IF sold >= cap THEN
                    RAISE EXCEPTION 'standing section is full'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER tickets_standing_capacity
        BEFORE INSERT OR UPDATE OF status ON tickets
        FOR EACH ROW EXECUTE FUNCTION check_standing_capacity();
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
            CONSTRAINT payments_amount_ok CHECK (amount >= 0),
            CONSTRAINT payments_method_ok CHECK (
                method IN ('card','mbway','multibanco')),
            CONSTRAINT payments_status_ok CHECK (
                status IN ('approved','declined','refunded'))
        );
    """)

    op.execute("""
        CREATE TABLE checkin_scans (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code_read  text NOT NULL,
            ticket_id  bigint REFERENCES tickets(id) ON DELETE RESTRICT,
            gate_id    bigint NOT NULL REFERENCES gates(id) ON DELETE RESTRICT,
            staff_id   bigint NOT NULL REFERENCES staff(id) ON DELETE RESTRICT,
            scanned_at timestamptz NOT NULL DEFAULT now(),
            result     text NOT NULL,
            CONSTRAINT scans_result_ok CHECK (
                result IN ('accepted','already_used','cancelled',
                           'wrong_day','unknown_code'))
        );
    """)

    op.execute("CREATE INDEX orders_customer_created_idx ON orders (customer_id, created_at DESC);")
    op.execute("CREATE INDEX orders_performance_idx ON orders (performance_id);")
    op.execute("CREATE INDEX order_lines_order_idx ON order_lines (order_id);")
    op.execute("CREATE INDEX tickets_order_idx ON tickets (order_id);")
    op.execute("""
        CREATE INDEX tickets_perf_section_active_idx
        ON tickets (performance_id, section_id)
        WHERE status IN ('valid','used');
    """)
    op.execute("CREATE INDEX payments_order_idx ON payments (order_id);")
    op.execute("CREATE INDEX scans_gate_time_idx ON checkin_scans (gate_id, scanned_at);")

    op.execute("REVOKE ALL ON checkin_scans FROM ticketing_app;")
    op.execute("GRANT SELECT, INSERT ON checkin_scans TO ticketing_app;")
    op.execute("GRANT USAGE ON SEQUENCE checkin_scans_id_seq TO ticketing_app;")


def downgrade():
    op.execute("DROP TABLE IF EXISTS checkin_scans;")
    op.execute("DROP TABLE IF EXISTS payments;")
    op.execute("DROP TRIGGER IF EXISTS tickets_standing_capacity ON tickets;")
    op.execute("DROP FUNCTION IF EXISTS check_standing_capacity();")
    op.execute("DROP TABLE IF EXISTS tickets;")
    op.execute("DROP TABLE IF EXISTS order_lines;")
    op.execute("DROP TABLE IF EXISTS orders;")
    op.execute("DROP TABLE IF EXISTS promo_codes;")
    op.execute("DROP TABLE IF EXISTS staff;")