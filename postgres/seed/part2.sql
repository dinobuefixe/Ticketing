\set ON_ERROR_STOP on

BEGIN;

SET LOCAL synchronous_commit = off;
SET LOCAL work_mem = '128MB';

INSERT INTO customers (id, name, email, password_hash, date_of_birth, phone)
SELECT md5('customer:' || i)::uuid,
       'Customer ' || i,
       'customer' || i || '@seed.local',
       'x',
       date '1960-01-01' + (i * 37 % 15000),
       '9' || lpad(i::text, 8, '0')
FROM generate_series(1, 100000) i
WHERE NOT EXISTS (SELECT 1 FROM customers);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM performances) OR NOT EXISTS (SELECT 1 FROM customers) THEN
        RAISE EXCEPTION 'load the base seed first';
    END IF;
    IF EXISTS (SELECT 1 FROM orders) THEN
        RAISE EXCEPTION 'orders are already seeded';
    END IF;
END
$$;

CREATE FUNCTION seed_hash(text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
    SELECT (('x' || substr(md5($1), 1, 8))::bit(32)::bigint)::double precision / 4294967296.0
$$;

CREATE INDEX seed_tmp_standing_idx ON tickets (performance_id, section_id) WHERE seat_id IS NULL;

CREATE TEMP TABLE seed_slots ON COMMIT DROP AS
SELECT venue_id,
       row_number() OVER (PARTITION BY venue_id
                          ORDER BY kind_rank, section_id, row_label, seat_number, place) AS ord,
       section_id,
       seat_id
FROM (
    SELECT s.venue_id, 0 AS kind_rank, s.id AS section_id, st.row_label, st.seat_number,
           0 AS place, st.id AS seat_id
    FROM seats st
    JOIN sections s ON s.id = st.section_id
    UNION ALL
    SELECT s.venue_id, 1, s.id, '', 0, g, NULL::uuid
    FROM sections s, generate_series(1, s.standing_capacity) g
    WHERE s.kind = 'standing'
) x;

CREATE INDEX ON seed_slots (venue_id, ord);

CREATE TEMP TABLE seed_venue ON COMMIT DROP AS
SELECT venue_id, count(*) AS cap
FROM seed_slots
GROUP BY venue_id;

CREATE TEMP TABLE seed_gates ON COMMIT DROP AS
SELECT venue_id, id,
       row_number() OVER (PARTITION BY venue_id ORDER BY id) AS ord,
       count(*) OVER (PARTITION BY venue_id) AS total
FROM gates;

CREATE TEMP TABLE seed_customers ON COMMIT DROP AS
SELECT row_number() OVER (ORDER BY id) AS ord, id
FROM customers
WHERE date_of_birth <= (now() - interval '19 years')::date;

CREATE TEMP TABLE seed_cust_meta ON COMMIT DROP AS
SELECT count(*) AS total, least(2000, count(*) / 20) AS heavy
FROM seed_customers;

CREATE TEMP TABLE seed_promo ON COMMIT DROP AS
SELECT i AS idx,
       md5('promo:' || i)::uuid AS id,
       CASE WHEN i % 2 = 1 THEN 5 + (i % 6) * 5 END AS percent_off,
       CASE WHEN i % 2 = 0 THEN (2 + (i % 5) * 2)::numeric(10, 2) END AS amount_off
FROM generate_series(1, 50) i;

INSERT INTO promo_codes (id, code, percent_off, amount_off, valid_from, valid_until, max_uses, uses)
SELECT id, 'SEED' || lpad(idx::text, 2, '0'), percent_off, amount_off,
       now() - interval '24 months', now() + interval '12 months', 1000000, 0
FROM seed_promo;

CREATE TEMP TABLE seed_perf ON COMMIT DROP AS
SELECT p.id AS performance_id,
       p.event_id,
       p.venue_id,
       p.status,
       p.starts_at,
       p.ends_at,
       p.sales_open_at,
       v.cap,
       seed_hash('weight:' || p.event_id) AS pop,
       seed_hash('offset:' || p.id) AS off_frac,
       (seed_hash('soldout:' || p.id) < 0.03
            AND p.status IN ('on_sale', 'finished', 'sold_out')) AS sold_out,
       1 + floor(seed_hash('size:' || p.id) * 4)::int AS group_size
FROM performances p
JOIN seed_venue v ON v.venue_id = p.venue_id
WHERE p.sales_open_at < now();

ALTER TABLE seed_perf ADD COLUMN n integer;

UPDATE seed_perf p
SET n = CASE
        WHEN p.sold_out THEN p.cap
        ELSE greatest(1, least(p.cap, round(p.cap * f.mean_fill * 4 * p.pop ^ 3)::int))
    END
FROM (
    SELECT greatest(0.001, (1150000 - coalesce(sum(cap) FILTER (WHERE sold_out), 0))
                           / nullif(sum(cap) FILTER (WHERE NOT sold_out), 0))::double precision AS mean_fill
    FROM seed_perf
) f;

CREATE TEMP TABLE seed_sales ON COMMIT DROP AS
SELECT p.performance_id, k.k, sl.section_id, sl.seat_id, sp.price
FROM seed_perf p
CROSS JOIN LATERAL generate_series(1, p.n) AS k(k)
JOIN seed_slots sl ON sl.venue_id = p.venue_id
                  AND sl.ord = ((k.k - 1 + floor(p.off_frac * p.cap)::int) % p.cap) + 1
JOIN section_prices sp ON sp.performance_id = p.performance_id
                      AND sp.section_id = sl.section_id;

CREATE TEMP TABLE seed_orders ON COMMIT DROP AS
WITH grouped AS (
    SELECT s.performance_id,
           ((s.k - 1) / p.group_size) + 1 AS g,
           count(*) AS tickets,
           sum(s.price) AS subtotal
    FROM seed_sales s
    JOIN seed_perf p ON p.performance_id = s.performance_id
    GROUP BY s.performance_id, ((s.k - 1) / p.group_size) + 1
),
counted AS (
    SELECT gr.*, count(*) OVER (PARTITION BY gr.performance_id) AS orders_in_perf
    FROM grouped gr
),
heavy AS (
    SELECT c.*, least(m.heavy, ceil(0.15 * c.orders_in_perf)::bigint) AS hc
    FROM counted c
    CROSS JOIN seed_cust_meta m
)
SELECT h.performance_id, h.g, h.tickets, h.subtotal,
       p.starts_at, p.sales_open_at, p.sold_out, p.status AS perf_status,
       CASE
           WHEN h.g <= h.hc THEN
               ((h.g - 1)::bigint * sh.stride + floor(p.off_frac * m.heavy)::bigint) % m.heavy + 1
           ELSE
               m.heavy + ((h.g - h.hc - 1) * sl.stride
                          + floor(p.off_frac * (m.total - m.heavy))::bigint) % (m.total - m.heavy) + 1
       END AS cust_ord
FROM heavy h
JOIN seed_perf p ON p.performance_id = h.performance_id
CROSS JOIN seed_cust_meta m
CROSS JOIN LATERAL (SELECT CASE WHEN gcd(7919, m.heavy) = 1 THEN 7919 ELSE 1 END AS stride) sh
CROSS JOIN LATERAL (SELECT CASE WHEN gcd(7919, m.total - m.heavy) = 1 THEN 7919 ELSE 1 END AS stride) sl;

CREATE TEMP TABLE seed_order_rows ON COMMIT DROP AS
WITH base AS (
    SELECT o.performance_id, o.g, o.tickets, o.subtotal, o.starts_at, o.sales_open_at, o.sold_out,
           md5('order:' || o.performance_id || ':' || o.g)::uuid AS id,
           c.id AS customer_id,
           CASE
               WHEN o.perf_status = 'cancelled' THEN 'refunded'
               WHEN NOT o.sold_out AND o.starts_at > now() + interval '48 hours'
                    AND seed_hash('cancel:' || o.performance_id || ':' || o.g) < 0.04 THEN 'refunded'
               ELSE 'paid'
           END AS status,
           CASE WHEN seed_hash('promo:' || o.performance_id || ':' || o.g) < 0.10
                THEN 1 + floor(seed_hash('promoidx:' || o.performance_id || ':' || o.g) * 50)::int
           END AS promo_idx,
           CASE
               WHEN seed_hash('method:' || o.performance_id || ':' || o.g) < 0.6 THEN 'card'
               WHEN seed_hash('method:' || o.performance_id || ':' || o.g) < 0.9 THEN 'mbway'
               ELSE 'multibanco'
           END AS method,
           o.sales_open_at
               + (least(o.starts_at, now()) - o.sales_open_at) * 0.9
                 * power(seed_hash('when:' || o.performance_id || ':' || o.g), 3) AS created_at
    FROM seed_orders o
    JOIN seed_customers c ON c.ord = o.cust_ord
)
SELECT b.*,
       least(b.created_at + interval '3 minutes', least(b.starts_at, now())) AS paid_at,
       sp.id AS promo_id,
       b.subtotal - CASE
           WHEN sp.id IS NULL THEN 0
           WHEN sp.percent_off IS NOT NULL THEN round(b.subtotal * sp.percent_off / 100.0, 2)
           ELSE least(sp.amount_off, b.subtotal)
       END AS total
FROM base b
LEFT JOIN seed_promo sp ON sp.idx = b.promo_idx;

INSERT INTO orders (id, customer_id, performance_id, promo_code_id, status, total, created_at, paid_at)
SELECT id, customer_id, performance_id, promo_id, status, total, created_at, paid_at
FROM seed_order_rows;

INSERT INTO tickets (id, order_id, performance_id, section_id, seat_id, price_paid, code, status, issued_at)
SELECT md5('ticket:' || x.performance_id || ':' || x.k)::uuid,
       x.order_id, x.performance_id, x.section_id, x.seat_id, x.price,
       upper(substr(md5('code:' || x.n), 1, 6)) || upper(lpad(to_hex(x.n), 6, '0')),
       CASE
           WHEN x.order_status = 'refunded' THEN 'cancelled'
           WHEN x.ends_at < now()
                AND seed_hash('show:' || x.performance_id || ':' || x.k) < 0.9 THEN 'used'
           ELSE 'valid'
       END,
       x.paid_at
FROM (
    SELECT s.performance_id, s.k, s.section_id, s.seat_id, s.price,
           o.id AS order_id, o.status AS order_status, o.paid_at, p.ends_at,
           row_number() OVER (ORDER BY s.performance_id, s.k) AS n
    FROM seed_sales s
    JOIN seed_perf p ON p.performance_id = s.performance_id
    JOIN seed_order_rows o ON o.performance_id = s.performance_id
                          AND o.g = ((s.k - 1) / p.group_size) + 1
) x;

INSERT INTO payments (id, order_id, amount, method, status, created_at, provider_reference)
SELECT md5('pay:' || o.id)::uuid, o.id, o.total, o.method, 'approved', o.paid_at, 'SEED-A-' || o.id
FROM seed_order_rows o;

INSERT INTO payments (id, order_id, amount, method, status, created_at, provider_reference)
SELECT md5('declined:' || o.id)::uuid, o.id, o.total, o.method, 'declined', o.created_at, 'SEED-D-' || o.id
FROM seed_order_rows o
WHERE seed_hash('declined:' || o.id) < 0.04;

INSERT INTO payments (id, order_id, amount, method, status, created_at, provider_reference)
SELECT md5('refund:' || o.id)::uuid, o.id, o.total, o.method, 'refunded',
       o.paid_at + (now() - o.paid_at) / 2, 'SEED-R-' || o.id
FROM seed_order_rows o
WHERE o.status = 'refunded';

INSERT INTO scan_records (id, ticket_code, gate_id, ticket_id, staff_id, result, scanned_at)
SELECT md5('scan:' || t.id)::uuid, t.code, g.id, t.id,
       md5('staff:' || floor(seed_hash('staff:' || t.id) * 20)::int)::uuid,
       'accepted',
       p.starts_at - interval '90 minutes' + interval '80 minutes' * seed_hash('scan:' || t.id)
FROM tickets t
JOIN performances p ON p.id = t.performance_id
JOIN seed_gates g ON g.venue_id = p.venue_id
                 AND g.ord = 1 + floor(seed_hash('gate:' || t.id) * g.total)::int
WHERE t.status = 'used';

INSERT INTO scan_records (id, ticket_code, gate_id, ticket_id, staff_id, result, scanned_at)
SELECT md5('dup:' || t.id)::uuid, t.code, g.id, t.id,
       md5('staff:' || floor(seed_hash('staff:' || t.id) * 20)::int)::uuid,
       'already_used',
       p.starts_at - interval '85 minutes' + interval '80 minutes' * seed_hash('scan:' || t.id)
FROM tickets t
JOIN performances p ON p.id = t.performance_id
JOIN seed_gates g ON g.venue_id = p.venue_id
                 AND g.ord = 1 + floor(seed_hash('gate:' || t.id) * g.total)::int
WHERE t.status = 'used'
  AND seed_hash('dup:' || t.id) < 0.01;

INSERT INTO scan_records (id, ticket_code, gate_id, ticket_id, staff_id, result, scanned_at)
SELECT md5('bad:' || t.id)::uuid, upper(substr(md5('badcode:' || t.id), 1, 12)), g.id, NULL,
       md5('staff:' || floor(seed_hash('staff:' || t.id) * 20)::int)::uuid,
       'unknown_code',
       p.starts_at - interval '88 minutes' + interval '80 minutes' * seed_hash('scan:' || t.id)
FROM tickets t
JOIN performances p ON p.id = t.performance_id
JOIN seed_gates g ON g.venue_id = p.venue_id
                 AND g.ord = 1 + floor(seed_hash('gate:' || t.id) * g.total)::int
WHERE t.status = 'used'
  AND seed_hash('bad:' || t.id) < 0.003;

UPDATE promo_codes pc
SET uses = u.n, max_uses = greatest(u.n + 20, 100)
FROM (
    SELECT promo_code_id, count(*) AS n
    FROM orders
    WHERE promo_code_id IS NOT NULL AND paid_at IS NOT NULL
    GROUP BY promo_code_id
) u
WHERE pc.id = u.promo_code_id;

UPDATE promo_codes SET max_uses = 100 WHERE code LIKE 'SEED%' AND uses = 0;

UPDATE performances
SET status = 'sold_out'
WHERE status = 'on_sale'
  AND id IN (SELECT performance_id FROM seed_perf WHERE sold_out);

DROP INDEX seed_tmp_standing_idx;
DROP FUNCTION seed_hash(text);

COMMIT;

ANALYZE orders;
ANALYZE tickets;
ANALYZE payments;
ANALYZE scan_records;

SELECT 'orders' AS item, count(*) FROM orders
UNION ALL SELECT 'tickets', count(*) FROM tickets
UNION ALL SELECT 'payments', count(*) FROM payments
UNION ALL SELECT 'scan_records', count(*) FROM scan_records
UNION ALL SELECT 'promo_codes', count(*) FROM promo_codes;