"""Teste de concorrência "mesmo lugar": 50 clientes pedem o mesmo lugar ao mesmo tempo.

Regra: exatamente 1 hold com sucesso, 49 recusados, nenhum erro 5xx,
e na base de dados só existe 1 reserva ativa para esse lugar.

A fixture cria uma performance nova (com data distante) e 50 clientes novos,
por isso o teste pode correr várias vezes seguidas.

Como correr (a partir da raiz, com a app a correr em --base-url):
  uv run --with-requirements app/requirements.txt python -m app.tests.test_same_seat --mode real
  uv run --with-requirements app/requirements.txt python -m app.tests.test_same_seat --mode naive

Para a versão ingénua, arranca a app com HOLD_MODE=naive antes de correr o teste.
Sai com 0 se a regra se mantém, e com 1 se a regra falhar ou houver erros 5xx.
"""

import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

CUSTOMERS = 50


def load_env() -> None:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def pg_url(name: str) -> str:
    return os.environ[name].replace("postgresql+psycopg://", "postgresql://", 1)


def create_fixture(conn) -> tuple[str, str, list[str]]:
    # Primeiro lugar sentado de um local
    venue_id, seat_id = conn.execute(
        """SELECT s.venue_id, st.id
           FROM seats st JOIN sections s ON s.id = st.section_id
           WHERE s.kind = 'seated'
           ORDER BY s.venue_id, st.id
           LIMIT 1"""
    ).fetchone()
    organiser_id = conn.execute("SELECT id FROM organisers LIMIT 1").fetchone()[0]

    # Evento e performance novos, daqui a 400 dias para não colidir com o seed
    event_id = str(uuid.uuid4())
    perf_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO events (id, organiser_id, title, category, min_age)
           VALUES (%s, %s, 'Teste de concorrência', 'other', 0)""",
        (event_id, organiser_id),
    )
    conn.execute(
        """INSERT INTO performances (id, event_id, venue_id, starts_at, ends_at, sales_open_at, status)
           VALUES (%s, %s, %s, now() + interval '400 days',
                   now() + interval '400 days 3 hours', now() - interval '1 day', 'on_sale')""",
        (perf_id, event_id, venue_id),
    )

    # 50 clientes novos, todos maiores de idade
    customers = []
    for _ in range(CUSTOMERS):
        cid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO customers (id, name, email, password_hash, date_of_birth, phone)
               VALUES (%s, 'Cliente teste', %s, 'x', '1990-01-01', '900000000')""",
            (cid, f"conc-{cid}@example.pt"),
        )
        customers.append(cid)

    return perf_id, str(seat_id), customers


def post_hold(base_url: str, perf_id: str, customer_id: str, seat_id: str,
              barrier: threading.Barrier) -> int:
    barrier.wait()  # todos disparam no mesmo instante
    body = json.dumps({"seat_ids": [seat_id]}).encode()
    req = urllib.request.Request(
        f"{base_url}/performances/{perf_id}/holds",
        data=body,
        headers={"Content-Type": "application/json", "X-User-Id": customer_id},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0  # sem resposta: conta como falha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["real", "naive"])
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    load_env()

    with psycopg.connect(pg_url("MIGRATION_DATABASE_URL"), autocommit=True) as conn:
        perf_id, seat_id, customers = create_fixture(conn)

    barrier = threading.Barrier(CUSTOMERS)
    with ThreadPoolExecutor(max_workers=CUSTOMERS) as pool:
        statuses = list(pool.map(
            lambda c: post_hold(args.base_url, perf_id, c, seat_id, barrier), customers
        ))

    ok = sum(1 for s in statuses if s == 201)
    refused = sum(1 for s in statuses if 400 <= s < 500)
    failed = sum(1 for s in statuses if s == 0 or s >= 500)

    # Verificação na base de dados (owner, para não depender de grants)
    with psycopg.connect(pg_url("MIGRATION_DATABASE_URL")) as conn:
        active = conn.execute(
            """SELECT count(*) FROM hold_items hi JOIN holds h ON h.id = hi.hold_id
               WHERE hi.seat_id = %s AND h.performance_id = %s
                 AND h.status = 'active' AND h.expires_at > now()""",
            (seat_id, perf_id),
        ).fetchone()[0]

    rule_holds = ok == 1 and active == 1
    print(f"Modo: {args.mode}")
    print(f"Clientes: {CUSTOMERS}")
    print(f"Sucessos (201): {ok}")
    print(f"Recusados (4xx): {refused}")
    print(f"Falhas (5xx ou sem resposta): {failed}")
    print(f"Reservas ativas para o lugar na base de dados: {active}")
    print(f"Regra mantém-se: {'SIM' if rule_holds else 'NÃO'}")

    return 0 if rule_holds and failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())