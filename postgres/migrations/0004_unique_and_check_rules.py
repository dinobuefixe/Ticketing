"""regras: nomes únicos, lugar único por secção, enums, valores válidos e não negativos

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Organizadores: NIF com 9 dígitos e único, email único
    op.execute("""
        ALTER TABLE organisers
            ADD CONSTRAINT organisers_nif_key UNIQUE (nif),
            ADD CONSTRAINT organisers_nif_format CHECK (nif ~ '^[0-9]{9}$'),
            ADD CONSTRAINT organisers_email_key UNIQUE (contact_email)
    """)

    # Locais: nome único; capacidade positiva
    op.execute("""
        ALTER TABLE venues
            ADD CONSTRAINT venues_name_key UNIQUE (name),
            ADD CONSTRAINT venues_capacity_positive CHECK (max_capacity > 0)
    """)

    # Portas: nome único dentro do local
    op.execute("""
        ALTER TABLE gates
            ADD CONSTRAINT gates_name_per_venue UNIQUE (venue_id, name)
    """)

    # Secções: nome único dentro do local; tipo só seated ou standing
    op.execute("""
        ALTER TABLE sections
            ADD CONSTRAINT sections_name_per_venue UNIQUE (venue_id, name),
            ADD CONSTRAINT sections_kind_valid CHECK (kind IN ('seated', 'standing'))
    """)

    # Lugares: um lugar por fila e número dentro da secção
    op.execute("""
        ALTER TABLE seats
            ADD CONSTRAINT seats_one_per_row_number UNIQUE (section_id, row_label, seat_number),
            ADD CONSTRAINT seats_row_format CHECK (row_label ~ '^[A-Z]{1,2}$'),
            ADD CONSTRAINT seats_number_positive CHECK (seat_number > 0)
    """)

    # Eventos: categoria e idade mínima só com valores permitidos
    op.execute("""
        ALTER TABLE events
            ADD CONSTRAINT events_category_valid
                CHECK (category IN ('concert', 'theatre', 'comedy', 'sport', 'other')),
            ADD CONSTRAINT events_min_age_valid CHECK (min_age IN (0, 6, 12, 16, 18))
    """)

    # Performances: estado válido; fim depois do início; vendas abrem antes do início
    op.execute("""
        ALTER TABLE performances
            ADD CONSTRAINT performances_status_valid
                CHECK (status IN ('scheduled', 'on_sale', 'sold_out', 'finished', 'cancelled')),
            ADD CONSTRAINT performances_end_after_start CHECK (ends_at > starts_at),
            ADD CONSTRAINT performances_sales_before_start CHECK (sales_open_at < starts_at)
    """)

    # Preços: nunca negativos
    op.execute("""
        ALTER TABLE section_prices
            ADD CONSTRAINT section_prices_non_negative CHECK (price >= 0)
    """)

    # Clientes: email único
    op.execute("""
        ALTER TABLE customers
            ADD CONSTRAINT customers_email_key UNIQUE (email)
    """)

    # Holds: estado válido; expira depois de criado
    op.execute("""
        ALTER TABLE holds
            ADD CONSTRAINT holds_status_valid
                CHECK (status IN ('active', 'converted', 'expired', 'released')),
            ADD CONSTRAINT holds_expiry_after_creation CHECK (expires_at > created_at)
    """)

    # Itens de hold: ou um lugar, ou um número de lugares em standing
    op.execute("""
        ALTER TABLE hold_items
            ADD CONSTRAINT hold_items_places_positive CHECK (places > 0),
            ADD CONSTRAINT hold_items_seat_or_places CHECK ((seat_id IS NULL) <> (places IS NULL))
    """)


def downgrade():
    op.execute("ALTER TABLE hold_items DROP CONSTRAINT IF EXISTS hold_items_seat_or_places")
    op.execute("ALTER TABLE hold_items DROP CONSTRAINT IF EXISTS hold_items_places_positive")
    op.execute("ALTER TABLE holds DROP CONSTRAINT IF EXISTS holds_expiry_after_creation")
    op.execute("ALTER TABLE holds DROP CONSTRAINT IF EXISTS holds_status_valid")
    op.execute("ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_email_key")
    op.execute("ALTER TABLE section_prices DROP CONSTRAINT IF EXISTS section_prices_non_negative")
    op.execute("ALTER TABLE performances DROP CONSTRAINT IF EXISTS performances_sales_before_start")
    op.execute("ALTER TABLE performances DROP CONSTRAINT IF EXISTS performances_end_after_start")
    op.execute("ALTER TABLE performances DROP CONSTRAINT IF EXISTS performances_status_valid")
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_min_age_valid")
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_category_valid")
    op.execute("ALTER TABLE seats DROP CONSTRAINT IF EXISTS seats_number_positive")
    op.execute("ALTER TABLE seats DROP CONSTRAINT IF EXISTS seats_row_format")
    op.execute("ALTER TABLE seats DROP CONSTRAINT IF EXISTS seats_one_per_row_number")
    op.execute("ALTER TABLE sections DROP CONSTRAINT IF EXISTS sections_kind_valid")
    op.execute("ALTER TABLE sections DROP CONSTRAINT IF EXISTS sections_name_per_venue")
    op.execute("ALTER TABLE gates DROP CONSTRAINT IF EXISTS gates_name_per_venue")
    op.execute("ALTER TABLE venues DROP CONSTRAINT IF EXISTS venues_capacity_positive")
    op.execute("ALTER TABLE venues DROP CONSTRAINT IF EXISTS venues_name_key")
    op.execute("ALTER TABLE organisers DROP CONSTRAINT IF EXISTS organisers_email_key")
    op.execute("ALTER TABLE organisers DROP CONSTRAINT IF EXISTS organisers_nif_format")
    op.execute("ALTER TABLE organisers DROP CONSTRAINT IF EXISTS organisers_nif_key")
