import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid

import psycopg

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
CLIENTS = int(os.environ.get("CLIENTS", "100"))
PLACES = int(os.environ.get("PLACES", "10"))
USER_HEADER = os.environ.get("USER_HEADER", "X-User-Id")


def owner_connect():
    url = os.environ["MIGRATION_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def build_fixture():
    suffix = uuid.uuid4().hex[:10]
    nif = str(uuid.uuid4().int % 10**9).zfill(9)
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
                ("Venue " + suffix, PLACES + 10),
            )
            venue_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sections (venue_id, name, kind, standing_capacity) "
                "VALUES (%s, 'Pista', 'standing', %s) RETURNING id",
                (venue_id, PLACES),
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
                "INSERT INTO section_prices (performance_id, section_id, price) VALUES (%s, %s, 30.00)",
                (performance_id, section_id),
            )
            for number in range(1, CLIENTS + 1):
                cur.execute(
                    "INSERT INTO customers (name, email, password_hash, date_of_birth, phone) "
                    "VALUES (%s, %s, 'x', '1990-01-01', '000000000') RETURNING id",
                    (f"Customer {number}", f"c{number}-{suffix}@test.local"),
                )
                customers.append(cur.fetchone()[0])
    return performance_id, section_id, customers


def post(path, body, customer_id):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", USER_HEADER: str(customer_id)},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, {}
    except Exception:
        return 0, {}


def buy_one_place(performance_id, section_id, customer_id, results, index, barrier):
    barrier.wait()
    status, data = post(
        f"/performances/{performance_id}/holds",
        {"section_id": str(section_id), "places": 1},
        customer_id,
    )
    if status != 201:
        results[index] = status
        return
    status, _ = post(
        "/checkout",
        {"hold_id": data["hold_id"], "simulate": "approved", "method": "card"},
        customer_id,
    )
    results[index] = status


def main():
    performance_id, section_id, customers = build_fixture()
    results = [None] * len(customers)
    barrier = threading.Barrier(len(customers))
    threads = [
        threading.Thread(
            target=buy_one_place,
            args=(performance_id, section_id, c, results, i, barrier),
        )
        for i, c in enumerate(customers)
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
            cur.execute(
                "SELECT count(*) FROM tickets "
                "WHERE performance_id = %s AND section_id = %s AND status IN ('valid', 'used')",
                (performance_id, section_id),
            )
            tickets = cur.fetchone()[0]

    rule_holds = successes == PLACES and tickets == PLACES and errors == 0

    print("scenario: last places in a standing section")
    print("mode: real")
    print(f"clients: {len(customers)}")
    print(f"places available: {PLACES}")
    print(f"successes: {successes}")
    print(f"refused: {refused}")
    print(f"errors_5xx: {errors}")
    print(f"tickets in database: {tickets}")
    print(f"rule holds: {rule_holds}")

    if not rule_holds:
        sys.exit(1)


if __name__ == "__main__":
    main()