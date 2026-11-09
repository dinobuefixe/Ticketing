-- Esquema do Projeto A (Ticketing), equivalente às migrações 0001 a 0012.

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 0001: organizadores, locais, portas
CREATE TABLE organisers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name  text NOT NULL,
    nif           char(9) NOT NULL UNIQUE CHECK (nif ~ '^[0-9]{9}$'),
    contact_email text NOT NULL UNIQUE,
    phone         text NOT NULL
);

CREATE TABLE venues (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL UNIQUE,
    city         text NOT NULL,
    address      text NOT NULL,
    max_capacity integer NOT NULL CHECK (max_capacity > 0)
);

CREATE TABLE gates (
    id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id uuid NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name     text NOT NULL,
    UNIQUE (venue_id, name)
);

-- 0002: secções e lugares
CREATE TABLE sections (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id          uuid NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
    name              text NOT NULL,
    kind              text NOT NULL CHECK (kind IN ('seated', 'standing')),
    standing_capacity integer,
    UNIQUE (venue_id, name),
    CHECK (
        (kind = 'standing' AND standing_capacity > 0)
        OR (kind = 'seated' AND standing_capacity IS NULL)
    )
);

CREATE TABLE seats (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id               uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
    row_label                text NOT NULL CHECK (row_label ~ '^[A-Z]{1,2}$'),
    seat_number              integer NOT NULL CHECK (seat_number > 0),
    is_wheelchair_accessible boolean NOT NULL DEFAULT false,
    is_restricted_view       boolean NOT NULL DEFAULT false,
    UNIQUE (section_id, row_label, seat_number)
);

CREATE FUNCTION forbid_seats_in_standing() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT kind FROM sections WHERE id = NEW.section_id) = 'standing' THEN
        RAISE EXCEPTION 'standing section % cannot have seats', NEW.section_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER seats_not_in_standing
BEFORE INSERT OR UPDATE ON seats
FOR EACH ROW EXECUTE FUNCTION forbid_seats_in_standing();

-- 0003: eventos, performances, preços
CREATE TABLE events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organiser_id uuid NOT NULL REFERENCES organisers(id) ON DELETE RESTRICT,
    title        text NOT NULL,
    category     text NOT NULL CHECK (category IN ('concert', 'theatre', 'comedy', 'sport', 'other')),
    min_age      smallint NOT NULL CHECK (min_age IN (0, 6, 12, 16, 18)),
    description  text NOT NULL DEFAULT '',
    details      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE performances (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id      uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    venue_id      uuid NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
    starts_at     timestamptz NOT NULL,
    ends_at       timestamptz NOT NULL,
    sales_open_at timestamptz NOT NULL,
    status        text NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled', 'on_sale', 'sold_out', 'finished', 'cancelled')),
    CHECK (ends_at > starts_at),
    CHECK (sales_open_at < starts_at),
    EXCLUDE USING gist (
        venue_id WITH =,
        tstzrange(starts_at, ends_at) WITH &&
    ) WHERE (status <> 'cancelled')
);

CREATE TABLE section_prices (
    performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
    section_id     uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
    price          numeric(10, 2) NOT NULL CHECK (price >= 0),
    PRIMARY KEY (performance_id, section_id)
);

-- 0004: clientes, holds
CREATE TABLE customers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text NOT NULL,
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    date_of_birth date NOT NULL,
    phone         text NOT NULL,
    registered_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE holds (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id    uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
    status         text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'converted', 'expired', 'released')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    CHECK (expires_at > created_at)
);

CREATE TABLE hold_items (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hold_id    uuid NOT NULL REFERENCES holds(id) ON DELETE CASCADE,
    section_id uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
    seat_id    uuid REFERENCES seats(id) ON DELETE RESTRICT,
    places     integer CHECK (places > 0),
    CHECK ((seat_id IS NULL) <> (places IS NULL))
);

-- 0010: códigos promocionais, encomendas
CREATE TABLE promo_codes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL UNIQUE,
    percent_off smallint CHECK (percent_off BETWEEN 1 AND 100),
    amount_off  numeric(10, 2) CHECK (amount_off > 0),
    valid_from  timestamptz NOT NULL,
    valid_until timestamptz NOT NULL,
    event_id    uuid REFERENCES events(id) ON DELETE RESTRICT,
    max_uses    integer NOT NULL CHECK (max_uses > 0),
    uses        integer NOT NULL DEFAULT 0,
    CHECK (num_nonnulls(percent_off, amount_off) = 1),
    CHECK (valid_until > valid_from),
    CHECK (uses >= 0 AND uses <= max_uses)
);

CREATE TABLE orders (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id    uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
    hold_id        uuid REFERENCES holds(id) ON DELETE RESTRICT,
    promo_code_id  uuid REFERENCES promo_codes(id) ON DELETE RESTRICT,
    status         text NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded')),
    total          numeric(10, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    created_at     timestamptz NOT NULL DEFAULT now(),
    paid_at        timestamptz,
    CHECK (status <> 'paid' OR paid_at IS NOT NULL)
);

-- 0011: bilhetes, pagamentos, leituras à porta
CREATE TABLE tickets (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id       uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    performance_id uuid NOT NULL REFERENCES performances(id) ON DELETE RESTRICT,
    section_id     uuid NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
    seat_id        uuid REFERENCES seats(id) ON DELETE RESTRICT,
    price_paid     numeric(10, 2) NOT NULL CHECK (price_paid >= 0),
    code           char(12) NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9]{12}$'),
    status         text NOT NULL DEFAULT 'valid'
                   CHECK (status IN ('valid', 'used', 'cancelled')),
    issued_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX tickets_one_valid_seat
ON tickets (performance_id, seat_id)
WHERE seat_id IS NOT NULL AND status IN ('valid', 'used');

CREATE TABLE payments (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    amount             numeric(10, 2) NOT NULL CHECK (amount >= 0),
    method             text NOT NULL CHECK (method IN ('card', 'mbway', 'multibanco')),
    status             text NOT NULL CHECK (status IN ('approved', 'declined', 'refunded')),
    created_at         timestamptz NOT NULL DEFAULT now(),
    provider_reference text NOT NULL UNIQUE
);

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

-- 0012: capacidade das secções standing e registos só de inserção
CREATE FUNCTION check_standing_capacity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    cap  integer;
    sold integer;
BEGIN
    IF NEW.seat_id IS NOT NULL OR NEW.status NOT IN ('valid', 'used') THEN
        RETURN NEW;
    END IF;

    SELECT standing_capacity INTO cap
    FROM sections WHERE id = NEW.section_id FOR UPDATE;

    SELECT count(*) INTO sold
    FROM tickets
    WHERE section_id = NEW.section_id
      AND performance_id = NEW.performance_id
      AND seat_id IS NULL
      AND status IN ('valid', 'used')
      AND id <> NEW.id;

    IF sold + 1 > cap THEN
        RAISE EXCEPTION 'standing section % is full for performance %',
            NEW.section_id, NEW.performance_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tickets_standing_capacity
BEFORE INSERT OR UPDATE OF status ON tickets
FOR EACH ROW EXECUTE FUNCTION check_standing_capacity();

CREATE FUNCTION forbid_scan_changes() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'scan_records is append-only';
END;
$$;

CREATE TRIGGER scan_records_no_update_delete
BEFORE UPDATE OR DELETE ON scan_records
FOR EACH ROW EXECUTE FUNCTION forbid_scan_changes();