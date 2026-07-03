"""Generic CRUD router factory — one set of REST endpoints per table.

Keeps the API tiny: each entity (see app.models.tables) declares its writable
columns and we generate GET (list), POST (create), PATCH (update), DELETE.
"""
from fastapi import APIRouter, HTTPException
from pydantic import create_model
from typing import Optional
from uuid import UUID
import psycopg2.errors

from app.db.session import current_user_id, query
from app.models.tables import ENTITIES, Entity

# Global (non-per-user) tables have no user_id column and no RLS policy.
GLOBAL_TABLES = {"model_routes"}


def make_router(entity: Entity) -> APIRouter:
    table = entity.table
    allowed = set(entity.columns.keys())
    order_by = entity.order_by
    per_user = table not in GLOBAL_TABLES
    router = APIRouter(prefix=f"/api/{table}", tags=[table])

    # Build a dynamic Pydantic model for the payload
    model_fields = {
        name: (Optional[typ], None)
        for name, typ in entity.columns.items()
    }
    PayloadModel = create_model(f"{table.capitalize()}Payload", **model_fields)

    @router.get("")
    def list_rows():
        return query(f"SELECT * FROM {table} ORDER BY {order_by}")

    if entity.create:
        @router.post("", status_code=201)
        def create_row(payload: PayloadModel):
            data = payload.model_dump(exclude_unset=True)
            if not data:
                raise HTTPException(400, f"No valid fields. Allowed: {sorted(allowed)}")
            # Server-set the owner; RLS WITH CHECK requires it to match the current user.
            if per_user:
                data["user_id"] = current_user_id()
            cols = ", ".join(data.keys())
            ph = ", ".join(["%s"] * len(data))
            try:
                rows = query(
                    f"INSERT INTO {table} ({cols}) VALUES ({ph}) RETURNING *",
                    tuple(data.values()), commit=True,
                )
            # ValueError: psycopg2's adaptation layer raises it for values Postgres
            # can't hold (e.g. NUL bytes in text) — invalid input, not a server bug.
            except (psycopg2.errors.IntegrityError, psycopg2.errors.DataError, ValueError) as e:
                raise HTTPException(422, str(e)) from e
            return rows[0]

    @router.patch("/{row_id}")
    def update_row(row_id: UUID, payload: PayloadModel):
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, f"No valid fields. Allowed: {sorted(allowed)}")
        sets = ", ".join(f"{k} = %s" for k in data)
        try:
            rows = query(
                f"UPDATE {table} SET {sets} WHERE id = %s RETURNING *",
                tuple(data.values()) + (str(row_id),), commit=True,
            )
        # ValueError: see create_row — psycopg2 adaptation failures are bad input.
        except (psycopg2.errors.IntegrityError, psycopg2.errors.DataError, ValueError) as e:
            raise HTTPException(422, str(e)) from e
        if not rows:
            raise HTTPException(404, "Not found")
        return rows[0]

    @router.delete("/{row_id}", status_code=204)
    def delete_row(row_id: UUID):
        rows = query(f"DELETE FROM {table} WHERE id = %s RETURNING id",
                     (str(row_id),), commit=True)
        if not rows:
            raise HTTPException(404, "Not found")
        return None

    return router


CRUD_ROUTERS = [make_router(e) for e in ENTITIES]

