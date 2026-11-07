from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE promo_codes
        ADD CONSTRAINT promo_one_kind CHECK (
            (discount_percent IS NOT NULL) <> (discount_amount IS NOT NULL)),
        ADD CONSTRAINT promo_percent_range CHECK (
            discount_percent IS NULL OR discount_percent BETWEEN 1 AND 100),
        ADD CONSTRAINT promo_amount_positive CHECK (
            discount_amount IS NULL OR discount_amount > 0),
        ADD CONSTRAINT promo_period_ok CHECK (valid_to > valid_from),
        ADD CONSTRAINT promo_max_uses_positive CHECK (max_uses > 0),
        ADD CONSTRAINT promo_uses_not_negative CHECK (uses >= 0);
    """)
    op.execute("""
        CREATE FUNCTION check_promo_uses() RETURNS trigger AS $$
        BEGIN
            IF NEW.uses > NEW.max_uses THEN
                RAISE EXCEPTION 'promo code used too many times'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER promo_codes_max_uses
        BEFORE INSERT OR UPDATE OF uses, max_uses ON promo_codes
        FOR EACH ROW EXECUTE FUNCTION check_promo_uses();
    """)
    op.execute("ALTER TABLE orders ADD CONSTRAINT orders_total_ok CHECK (total >= 0);")
    op.execute("ALTER TABLE tickets ADD CONSTRAINT tickets_price_ok CHECK (price >= 0);")
    op.execute("ALTER TABLE payments ADD CONSTRAINT payments_amount_ok CHECK (amount >= 0);")


def downgrade():
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_amount_ok;")
    op.execute("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_price_ok;")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_total_ok;")
    op.execute("DROP TRIGGER IF EXISTS promo_codes_max_uses ON promo_codes;")
    op.execute("DROP FUNCTION IF EXISTS check_promo_uses();")
    op.execute("""
        ALTER TABLE promo_codes
        DROP CONSTRAINT IF EXISTS promo_one_kind,
        DROP CONSTRAINT IF EXISTS promo_percent_range,
        DROP CONSTRAINT IF EXISTS promo_amount_positive,
        DROP CONSTRAINT IF EXISTS promo_period_ok,
        DROP CONSTRAINT IF EXISTS promo_max_uses_positive,
        DROP CONSTRAINT IF EXISTS promo_uses_not_negative;
    """)