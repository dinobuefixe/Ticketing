from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS tickets_standing_capacity ON tickets;")
    op.execute("DROP FUNCTION IF EXISTS check_standing_capacity();")