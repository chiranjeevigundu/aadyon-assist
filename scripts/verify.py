#!/usr/bin/env python3
"""API parity check — confirm a change didn't alter untouched endpoints.

Fetches a set of endpoints from a running stack, hashes each response with a
stable (key-sorted) serialization, and compares against a saved baseline. This
is the safety net for refactors that are supposed to be behavior-preserving.

Usage:
    # 1) before a refactor, capture the baseline from the running stack
    python scripts/verify.py --base http://localhost:8000 --save
    # 2) after the refactor + redeploy, compare (exit code 1 on any mismatch)
    python scripts/verify.py --base http://localhost:8000

Note: /api/digital-me and /api/summary include date-derived values (days alive,
as-of date), so they shift day to day. Re-baseline on the same day you compare,
or pass --endpoints to limit the check to stable ones (e.g. /api/entities).
"""
import argparse
import hashlib
import json
import sys
import urllib.request

DEFAULT_ENDPOINTS = [
    "/api/digital-me",
    "/api/entities",
    "/api/summary",
    "/api/agency/org",
]
DEFAULT_BASELINE = "scripts/parity-baseline.json"


def _stable(value) -> str:
    """Deterministic JSON string with recursively sorted keys."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _fetch(base: str, path: str) -> dict:
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
    digest = hashlib.sha256(_stable(body).encode("utf-8")).hexdigest()[:16]
    n = len(body) if isinstance(body, (list, dict)) else 1
    return {"hash": digest, "count": n}


def main() -> int:
    ap = argparse.ArgumentParser(description="API parity check")
    ap.add_argument("--base", default="http://localhost:8000", help="base URL of a running API")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE, help="baseline JSON path")
    ap.add_argument("--save", action="store_true", help="save current responses as the baseline")
    ap.add_argument("--endpoints", nargs="*", default=DEFAULT_ENDPOINTS, help="paths to check")
    args = ap.parse_args()

    current = {}
    for path in args.endpoints:
        try:
            current[path] = _fetch(args.base, path)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {path}: {e}")
            return 2

    if args.save:
        with open(args.baseline, "w") as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
        print(f"Saved baseline for {len(current)} endpoint(s) -> {args.baseline}")
        for p, v in current.items():
            print(f"  {v['hash']}  {p}")
        return 0

    try:
        with open(args.baseline) as fh:
            baseline = json.load(fh)
    except FileNotFoundError:
        print(f"No baseline at {args.baseline} — run with --save first.")
        return 2

    ok = True
    for path in args.endpoints:
        b = baseline.get(path, {}).get("hash")
        c = current[path]["hash"]
        match = b == c
        ok = ok and match
        print(f"{'OK  ' if match else 'DIFF'}  {path}  baseline={b}  current={c}")
    print("PARITY OK" if ok else "PARITY FAILED — an untouched endpoint changed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
