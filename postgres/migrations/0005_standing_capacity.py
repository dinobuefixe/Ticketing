"""regras de capacidade standing: secção standing não tem lugares e tem capacidade

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # Secção sentada não tem capacidade standing; standing tem capacidade positiva
    op.execute("""
        ALTER TABLE sections
            ADD CONSTRAINT sections_standing_capacity CHECK (
                (kind = 'standing' AND standing_capacity > 0)
                OR (kind = 'seated' AND standing_capacity IS NULL)
            )
    """)

    # Uma secção standing não pode ter lugares
    op.execute("""
        CREATE FUNCTION forbid_seats_in_standing() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (SELECT kind FROM sections WHERE id = NEW.section_id) = 'standing' THEN
                RAISE EXCEPTION 'standing section % cannot have seats', NEW.section_id;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER seats_not_in_standing
        BEFORE INSERT OR UPDATE ON seats
        FOR EACH ROW EXECUTE FUNCTION forbid_seats_in_standing()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS seats_not_in_standing ON seats")
    op.execute("DROP FUNCTION IF EXISTS forbid_seats_in_standing()")
    op.execute("ALTER TABLE sections DROP CONSTRAINT IF EXISTS sections_standing_capacity")
