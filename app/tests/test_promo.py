import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid

import psycopg

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
CLIENTS = int(os.environ.get("CLIENTS", "20"))
MAX_USES = int(os.environ.get("MAX_USES", "5"))


def owner_connect():
    url = os.environ["MIGRATION_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def build_fixture():
    suffix = uuid.uuid4().hex[:10]
    nif = str(uuid.uuid4().int % 10**9).zfill(9)
    promo_code = "PROMO" + suffix.upper()
    customers = []
    with owner_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organisers (company_name, nif, contact_email, phone) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                ("Test " + suffix, nif, f"org-{suffix}@test.local", "000000000"),
            )
            organiser_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO venues (name, city, address, max_capacity) "
                "VALUES (%s, 'Faro', 'Test street', %s) RETURNING id",
                ("Venue " + suffix, CLIENTS + 10),
            )
            venue_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sections (venue_id, name, kind) VALUES (%s, 'Plateia', 'seated') RETURNING id",
                (venue_id,),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO events (organiser_id, title, category, min_age) "
                "VALUES (%s, %s, 'concert', 0) RETURNING id",
                (organiser_id, "Event " + suffix),
            )
            event_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO performances (event_id, venue_id, starts_at, ends_at, sales_open_at, status)
                VALUES (%s, %s, now() + interval '30 days', now() + interval '30 days 3 hours',
                        now() - interval '1 day', 'on_sale')
                RETURNING id
                """,
                (event_id, venue_id),
            )
            performance_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO section_prices (performance_id, section_id, price) VALUES (%s, %s, 50.00)",
                (performance_id, section_id),
            )
            cur.execute(
                """
                INSERT INTO promo_codes (code, percent_off, valid_from, valid_until, max_uses)
                VALUES (%s, 10, now() - interval '1 day', now() + interval '60 days', %s)
                RETURNING id
                """,
                (promo_code, MAX_USES),
            )
            promo_id = cur.fetchone()[0]

            for number in range(1, CLIENTS + 1):
                cur.execute(
                    "INSERT INTO seats (section_id, row_label, seat_number) VALUES (%s, 'A', %s) RETURNING id",
                    (section_id, number),
                )
                seat_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO customers (name, email, password_hash, date_of_birth, phone) "
                    "VALUES (%s, %s, 'x', '1990-01-01', '000000000') RETURNING id",
                    (f"Customer {number}", f"c{number}-{suffix}@test.local"),
                )
                customer_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO holds (customer_id, performance_id, expires_at) "
                    "VALUES (%s, %s, now() + interval '10 minutes') RETURNING id",
                    (customer_id, performance_id),
                )
                hold_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO hold_items (hold_id, section_id, seat_id) VALUES (%s, %s, %s)",
                    (hold_id, section_id, seat_id),
                )
                customers.append((customer_id, hold_id))
    return promo_code, promo_id, customers


def pay(customer_id, hold_id, promo_code, results, index, barrier):
    body = json.dumps(
        {
            "hold_id": str(hold_id),
            "simulate": "approved",
            "method": "card",
            "promo_code": promo_code,
        }
    ).encode()
    request = urllib.request.Request(
        BASE_URL + "/checkout",
        data=body,
        headers={"Content-Type": "application/json", "X-User-Id": str(customer_id)},
        method="POST",
    )
    barrier.wait()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            results[index] = response.status
    except urllib.error.HTTPError as error:
        results[index] = error.code
    except Exception:
        results[index] = 0


def main():
    promo_code, promo_id, customers = build_fixture()
    results = [None] * len(customers)
    barrier = threading.Barrier(len(customers))
    threads = [
        threading.Thread(target=pay, args=(c, h, promo_code, results, i, barrier))
        for i, (c, h) in enumerate(customers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    successes = sum(1 for s in results if s == 200)
    refused = sum(1 for s in results if s is not None and 400 <= s < 500)
    errors = sum(1 for s in results if s is None or s == 0 or s >= 500)

    with owner_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT uses FROM promo_codes WHERE id = %s", (promo_id,))
            uses = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM orders WHERE promo_code_id = %s AND status = 'paid'",
                (promo_id,),
            )
            paid_orders = cur.fetchone()[0]

    rule_holds = uses <= MAX_USES and uses == paid_orders and successes == MAX_USES

    print("scenario: promo code used at most max_uses times")
    print("mode: real")
    print(f"successes: {successes}")
    print(f"refused: {refused}")
    print(f"errors_5xx: {errors}")
    print(f"promo uses in database: {uses} (max {MAX_USES})")
    print(f"rule holds: {rule_holds}")

    if not rule_holds or errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()