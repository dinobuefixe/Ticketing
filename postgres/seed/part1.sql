-- Seed da Parte 1: organizadores, locais, portas, secções, lugares, eventos,
-- performances e preços. Determinístico: os UUID vêm de md5() e não há random().
-- Corre como owner, depois de as migrações estarem aplicadas.
-- Apaga as tabelas usadas (e as que dependem delas, com CASCADE) antes de inserir.

BEGIN;

TRUNCATE gates, seats, sections, section_prices, performances, events,
         venues, organisers, holds, hold_items CASCADE;

-- Definição das secções que cada local tem
CREATE TEMP TABLE seed_section_defs (
    name              text PRIMARY KEY,
    kind              text NOT NULL,
    row_count         integer,
    seats_per_row     integer,
    standing_capacity integer,
    base_price        numeric(10, 2) NOT NULL
) ON COMMIT DROP;

INSERT INTO seed_section_defs VALUES
    ('Plateia',   'seated',   25, 60, NULL, 45.00),
    ('Balcão 1',  'seated',   20, 60, NULL, 30.00),
    ('Balcão 2',  'seated',   20, 60, NULL, 22.00),
    ('Balcão 3',  'seated',   15, 60, NULL, 15.00),
    ('Pista',     'standing', NULL, NULL, 1000, 35.00);

-- 30 locais, distribuídos por 10 cidades
CREATE TEMP TABLE seed_venues ON COMMIT DROP AS
SELECT n AS idx,
       md5('venue:' || n)::uuid AS id,
       (ARRAY['Lisboa', 'Porto', 'Braga', 'Coimbra', 'Faro',
              'Aveiro', 'Leiria', 'Setúbal', 'Évora', 'Funchal'])[((n - 1) % 10) + 1] AS city
FROM generate_series(1, 30) AS g(n);

-- 200 organizadores
INSERT INTO organisers (id, company_name, nif, contact_email, phone)
SELECT md5('organiser:' || n)::uuid,
       'Organizadora ' || n,
       lpad((100000000 + n)::text, 9, '0'),
       'org' || n || '@example.pt',
       '+351 2' || lpad(n::text, 8, '0')
FROM generate_series(1, 200) AS g(n);

-- Locais: capacidade máxima 5800 = 4800 lugares + 1000 de pista
INSERT INTO venues (id, name, city, address, max_capacity)
SELECT id,
       'Sala ' || idx || ' - ' || city,
       city,
       'Rua Principal ' || idx || ', ' || city,
       5800
FROM seed_venues;

-- Duas portas por local
INSERT INTO gates (venue_id, name)
SELECT v.id, g.name
FROM seed_venues v
CROSS JOIN (VALUES ('Porta 1'), ('Porta Norte')) AS g(name);

-- Cinco secções por local
INSERT INTO sections (id, venue_id, name, kind, standing_capacity)
SELECT md5('section:' || v.idx || ':' || d.name)::uuid,
       v.id, d.name, d.kind, d.standing_capacity
FROM seed_venues v
CROSS JOIN seed_section_defs d;

-- Lugares das secções sentadas: 4800 por local, 144 000 no total
INSERT INTO seats (section_id, row_label, seat_number, is_wheelchair_accessible, is_restricted_view)
SELECT s.id,
       chr(64 + r.r),
       n.n,
       (r.r = 1 AND n.n <= 2),
       (r.r = d.row_count AND n.n = 1)
FROM sections s
JOIN seed_section_defs d ON d.name = s.name AND d.kind = 'seated'
CROSS JOIN LATERAL generate_series(1, d.row_count) AS r(r)
CROSS JOIN LATERAL generate_series(1, d.seats_per_row) AS n(n);

-- 1500 eventos, cada um com um organizador e uma categoria
CREATE TEMP TABLE seed_events ON COMMIT DROP AS
SELECT n,
       md5('event:' || n)::uuid AS id,
       md5('organiser:' || (((n - 1) % 200) + 1))::uuid AS organiser_id,
       (ARRAY['concert', 'theatre', 'comedy', 'sport', 'other'])[(n % 5) + 1] AS category,
       (ARRAY[0, 6, 12, 16, 18])[(n % 5) + 1]::smallint AS min_age
FROM generate_series(1, 1500) AS g(n);

INSERT INTO events (id, organiser_id, title, category, min_age, description, details)
SELECT id,
       organiser_id,
       'Evento ' || n,
       category,
       min_age,
       'Descrição do evento ' || n,
       CASE category
           WHEN 'concert' THEN jsonb_build_object(
               'genres', jsonb_build_array('rock', 'pop'),
               'lineup', jsonb_build_array(
                   jsonb_build_object('artist', 'Artista ' || n, 'headliner', true)))
           WHEN 'theatre' THEN jsonb_build_object(
               'director', 'Encenador ' || n,
               'duration_min', 90,
               'language', 'pt',
               'surtitles', false)
           WHEN 'sport' THEN jsonb_build_object(
               'competition', 'Campeonato',
               'home_team', 'Equipa A ' || n,
               'away_team', 'Equipa B ' || n,
               'round', (n % 30) + 1)
           WHEN 'comedy' THEN jsonb_build_object(
               'comedians', jsonb_build_array('Humorista ' || n),
               'recorded_for_tv', (n % 2 = 0))
           ELSE '{}'::jsonb
       END
FROM seed_events;

-- 4000 performances. Cada local recebe uma performance a cada 30 posições,
-- espaçadas de 4 dias, com 3 horas de duração: não se sobrepõem.
-- Vão de 365 dias atrás até cerca de 167 dias à frente (dentro dos 6 meses do brief).
CREATE TEMP TABLE seed_perf_slots ON COMMIT DROP AS
SELECT n,
       md5('performance:' || n)::uuid AS id,
       md5('event:' || (((n - 1) % 1500) + 1))::uuid AS event_id,
       ((n - 1) % 30) + 1 AS venue_idx,
       (n - 1) / 30 AS slot
FROM generate_series(1, 4000) AS g(n);

CREATE TEMP TABLE seed_perf_times ON COMMIT DROP AS
SELECT p.*,
       ((date_trunc('day', now() AT TIME ZONE 'Europe/Lisbon')
         - interval '365 days'
         + p.slot * interval '4 days'
         + interval '20 hours') AT TIME ZONE 'Europe/Lisbon') AS starts_at
FROM seed_perf_slots p;

INSERT INTO performances (id, event_id, venue_id, starts_at, ends_at, sales_open_at, status)
SELECT t.id,
       t.event_id,
       v.id,
       t.starts_at,
       t.starts_at + interval '3 hours',
       t.starts_at - interval '60 days',
       CASE
           WHEN t.n % 97 = 0 THEN 'cancelled'
           WHEN t.starts_at <= now() THEN 'finished'
           WHEN t.starts_at - interval '60 days' <= now() THEN 'on_sale'
           ELSE 'scheduled'
       END
FROM seed_perf_times t
JOIN seed_venues v ON v.idx = t.venue_idx;

-- Preço de cada secção em cada performance. Varia de forma determinística (hashtext).
INSERT INTO section_prices (performance_id, section_id, price)
SELECT pf.id,
       s.id,
       round(d.base_price * (1 + (abs(hashtext(pf.id::text)) % 4) * 0.1), 2)
FROM performances pf
JOIN sections s ON s.venue_id = pf.venue_id
JOIN seed_section_defs d ON d.name = s.name;

-- Verificação: se alguma contagem não bater com o brief, o seed falha e nada fica gravado
DO $$
BEGIN
    IF (SELECT count(*) FROM organisers) <> 200 THEN
        RAISE EXCEPTION 'organisers: esperado 200';
    END IF;
    IF (SELECT count(*) FROM venues) <> 30 THEN
        RAISE EXCEPTION 'venues: esperado 30';
    END IF;
    IF (SELECT count(DISTINCT city) FROM venues) < 8 THEN
        RAISE EXCEPTION 'venues: esperado pelo menos 8 cidades';
    END IF;
    IF (SELECT count(*) FROM gates) <> 60 THEN
        RAISE EXCEPTION 'gates: esperado 60';
    END IF;
    IF (SELECT count(*) FROM sections) <> 150 THEN
        RAISE EXCEPTION 'sections: esperado 150';
    END IF;
    IF (SELECT count(*) FROM seats) <> 144000 THEN
        RAISE EXCEPTION 'seats: esperado 144000';
    END IF;
    IF (SELECT count(*) FROM events) <> 1500 THEN
        RAISE EXCEPTION 'events: esperado 1500';
    END IF;
    IF (SELECT count(*) FROM performances) <> 4000 THEN
        RAISE EXCEPTION 'performances: esperado 4000';
    END IF;
    IF (SELECT count(*) FROM section_prices) <> 20000 THEN
        RAISE EXCEPTION 'section_prices: esperado 20000';
    END IF;
END $$;

SELECT 'organisers'    AS tabela, count(*) FROM organisers
UNION ALL SELECT 'venues',         count(*) FROM venues
UNION ALL SELECT 'gates',          count(*) FROM gates
UNION ALL SELECT 'sections',       count(*) FROM sections
UNION ALL SELECT 'seats',          count(*) FROM seats
UNION ALL SELECT 'events',         count(*) FROM events
UNION ALL SELECT 'performances',   count(*) FROM performances
UNION ALL SELECT 'section_prices', count(*) FROM section_prices;

COMMIT;