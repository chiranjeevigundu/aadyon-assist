"""Importer: reads artifacts/inbox.json and creates tracker entities.

Each inbox item is {"table": "<entity>", "data": {<column: value>, ...}}.
- Columns are filtered against the per-table whitelist in app.models.tables.
- Rows are de-duplicated by a natural key so re-running is safe (idempotent).
- Processed inbox files are archived to artifacts/imported/ with a timestamp.

Run inside the api container:  python -m app.jobs.import_entities
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.db.session import query
from app.models.tables import ENTITIES

ALLOWED = {e.table: set(e.columns) for e in ENTITIES}

# Natural key used to detect an already-imported row (skip if present).
NATURAL_KEY = {
    "deadlines": ["title"],
    "debts": ["name"],
    "bills": ["name"],
    "subscriptions": ["name"],
    "shifts": ["employer", "shift_date"],
}


def _exists(table: str, data: dict) -> bool:
    keys = NATURAL_KEY[table]
    if not all(k in data for k in keys):
        return False
    where = " AND ".join(f"{k} = %s" for k in keys)
    rows = query(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1",
                 tuple(data[k] for k in keys))
    return bool(rows)


def _insert(table: str, data: dict) -> dict:
    cols = ", ".join(data.keys())
    ph = ", ".join(["%s"] * len(data))
    return query(f"INSERT INTO {table} ({cols}) VALUES ({ph}) RETURNING *",
                 tuple(data.values()), commit=True)[0]


def run(inbox: Path) -> dict:
    items = json.loads(inbox.read_text(encoding="utf-8"))
    created, skipped, errors = [], [], []
    for it in items:
        table = it.get("table")
        raw = it.get("data", {})
        if table not in ALLOWED:
            errors.append({"item": it, "why": f"unknown table {table!r}"})
            continue
        data = {k: v for k, v in raw.items() if k in ALLOWED[table]}
        if not data:
            errors.append({"item": it, "why": "no valid columns"})
            continue
        try:
            if _exists(table, data):
                skipped.append({table: data})
                continue
            row = _insert(table, data)
            created.append({table: row.get("id")})
        except Exception as e:  # noqa: BLE001
            errors.append({"item": it, "why": str(e)})
    return {"created": created, "skipped": skipped, "errors": errors}


def main() -> None:
    s = get_settings()
    inbox = s.artifacts_dir / "inbox.json"
    if not inbox.exists():
        print(f"[import] no inbox at {inbox}; nothing to do")
        return
    result = run(inbox)
    print(f"[import] created={len(result['created'])} "
          f"skipped={len(result['skipped'])} errors={len(result['errors'])}")
    for e in result["errors"]:
        print(f"[import]   error: {e['why']}")
    # Archive the processed inbox so it isn't re-imported on the next run.
    archive = s.artifacts_dir / "imported"
    archive.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.move(str(inbox), str(archive / f"inbox-{stamp}.json"))
    (archive / f"result-{stamp}.json").write_text(
        json.dumps(result, default=str, indent=2), encoding="utf-8")
    print(f"[import] archived to {archive}")


if __name__ == "__main__":
    main()
