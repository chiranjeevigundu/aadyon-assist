"""Schema metadata for the generic data admin UI.

Reads real column types from information_schema so the front-end can render
correctly-typed inputs for every registered entity without any hardcoding.
"""
from app.db.session import query
from app.models.tables import ENTITIES

MANAGED = {"id", "created_at", "updated_at"}


def _foreign_keys(table: str) -> dict:
    """Map of {column_name: referenced_table} for a table's foreign keys."""
    rows = query(
        """
        SELECT kcu.column_name, ccu.table_name AS ref_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
        """,
        (table,),
    )
    return {r["column_name"]: r["ref_table"] for r in rows}


def entities_meta() -> list[dict]:
    out: list[dict] = []
    for e in ENTITIES:
        cols = query(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = %s "
            "ORDER BY ordinal_position",
            (e.table,),
        )
        fks = _foreign_keys(e.table)
        writable = set(e.columns.keys())
        col_meta = []
        for c in cols:
            name = c["column_name"]
            managed = name in MANAGED
            col_meta.append({
                "name": name,
                "type": c["data_type"],
                "writable": name in writable,
                "managed": managed,
                "references": fks.get(name),  # referenced table, or None
                "required": (
                    c["is_nullable"] == "NO"
                    and c["column_default"] is None
                    and not managed
                    and name in writable
                ),
            })
        out.append({"table": e.table, "order_by": e.order_by, "columns": col_meta})
    return out
