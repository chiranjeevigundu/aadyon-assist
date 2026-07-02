"""Generic CRUD router factory — one set of REST endpoints per table.

Keeps the API tiny: each entity (see app.models.tables) declares its writable
columns and we generate GET (list), POST (create), PATCH (update), DELETE.
"""
from fastapi import APIRouter, HTTPException

from app.db.session import current_user_id, query
from app.models.tables import ENTITIES, Entity

# Global (non-per-user) tables have no user_id column and no RLS policy.
GLOBAL_TABLES = {"model_routes"}


def make_router(entity: Entity) -> APIRouter:
    table = entity.table
    allowed = set(entity.columns)
    order_by = entity.order_by
    per_user = table not in GLOBAL_TABLES
    router = APIRouter(prefix=f"/api/{table}", tags=[table])

    @router.get("")
    def list_rows():
        return query(f"SELECT * FROM {table} ORDER BY {order_by}")

    @router.post("", status_code=201)
    def create_row(payload: dict):
        data = {k: v for k, v in payload.items() if k in allowed}
        if not data:
            raise HTTPException(400, f"No valid fields. Allowed: {sorted(allowed)}")
        # Server-set the owner; RLS WITH CHECK requires it to match the current user.
        if per_user:
            data["user_id"] = current_user_id()
        cols = ", ".join(data.keys())
        ph = ", ".join(["%s"] * len(data))
        rows = query(
            f"INSERT INTO {table} ({cols}) VALUES ({ph}) RETURNING *",
            tuple(data.values()), commit=True,
        )
        return rows[0]

    @router.patch("/{row_id}")
    def update_row(row_id: str, payload: dict):
        data = {k: v for k, v in payload.items() if k in allowed}
        if not data:
            raise HTTPException(400, f"No valid fields. Allowed: {sorted(allowed)}")
        sets = ", ".join(f"{k} = %s" for k in data)
        rows = query(
            f"UPDATE {table} SET {sets} WHERE id = %s RETURNING *",
            tuple(data.values()) + (row_id,), commit=True,
        )
        if not rows:
            raise HTTPException(404, "Not found")
        return rows[0]

    @router.delete("/{row_id}", status_code=204)
    def delete_row(row_id: str):
        rows = query(f"DELETE FROM {table} WHERE id = %s RETURNING id",
                     (row_id,), commit=True)
        if not rows:
            raise HTTPException(404, "Not found")
        return None

    return router


CRUD_ROUTERS = [make_router(e) for e in ENTITIES]
