#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "app" / "tests"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SCENARIOS = {
    "same-seat": {"script": "test_same_seat.py", "env": {"CLIENTS": "50"}},
    "last-places": {"script": "test_last_places.py", "env": {"CLIENTS": "100"}},
    "promo": {"script": "test_promo.py", "env": {"CLIENTS": "20", "MAX_USES": "5"}},
}


def api_is_up(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(base_url + "/health/services", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def field(name: str, text: str):
    match = re.search(rf"^{re.escape(name)}:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def run_scenario(name: str, args) -> dict:
    spec = SCENARIOS[name]
    script = TESTS_DIR / spec["script"]
    if not script.is_file():
        return {"name": name, "ok": False, "note": f"{spec['script']} não existe"}

    env = os.environ.copy()
    env.update(spec["env"])
    env["BASE_URL"] = args.base_url
    env["MODE"] = args.mode

    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            env=env, capture_output=True, text=True, timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "note": f"timeout ({args.timeout} s)"}

    return {
        "name": name,
        "ok": proc.returncode == 0,
        "mode": field("mode", proc.stdout) or args.mode,
        "successes": field("successes", proc.stdout) or "?",
        "refused": field("refused", proc.stdout) or "?",
        "errors_5xx": field("errors_5xx", proc.stdout) or "?",
        "output": (proc.stdout + proc.stderr).strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=list(SCENARIOS), help="cenários a correr (por omissão, todos)")
    parser.add_argument("--mode", choices=["real", "naive"], default="real")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--timeout", type=int, default=300, help="segundos por cenário")
    parser.add_argument("--quiet", action="store_true", help="só o resumo, sem o output de cada teste")
    args = parser.parse_args()

    if not api_is_up(args.base_url):
        print(f"FALHOU: a app não responde em {args.base_url}/health/services")
        return 1

    results = []
    for name in args.only or list(SCENARIOS):
        print(f"==> {name} (modo {args.mode})")
        result = run_scenario(name, args)
        if not args.quiet and result.get("output"):
            print("\n".join("    " + line for line in result["output"].splitlines()))
        if result.get("note"):
            print(f"    {result['note']}")
        results.append(result)

    print()
    print(f"{'cenário':<14}{'modo':<8}{'sucessos':<10}{'recusas':<9}{'5xx':<6}resultado")
    for r in results:
        print(f"{r['name']:<14}{r.get('mode', args.mode):<8}{r.get('successes', '-'):<10}"
              f"{r.get('refused', '-'):<9}{r.get('errors_5xx', '-'):<6}{'OK' if r['ok'] else 'FALHOU'}")

    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())