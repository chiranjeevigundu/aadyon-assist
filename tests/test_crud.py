"""Generic CRUD factory: writable-column whitelist + not-found handling.

Calls the generated endpoint functions directly (no HTTP client dependency).
"""
import inspect
import pytest
from fastapi import HTTPException

from app.models.tables import Entity
from app.routers import crud
from conftest import patch_query


def _endpoints(router):
    out = {}
    for r in router.routes:
        for method in r.methods:
            out[(method, r.path)] = r.endpoint
    return out


def _router():
    return _endpoints(crud.make_router(Entity("widgets", {"name": str, "color": str})))


def test_create_drops_unknown_fields(monkeypatch):
    fake = patch_query(
        monkeypatch, "app.routers.crud",
        lambda sql, p=(), c=False: [{"id": 1, "name": "x", "color": "red"}]
        if sql.strip().startswith("INSERT") else [],
    )
    create = _router()[("POST", "/api/widgets")]
    PayloadModel = inspect.signature(create).parameters["payload"].annotation
    out = create(PayloadModel(**{"name": "x", "color": "red", "secret": "drop-me"}))
    assert out["name"] == "x"
    insert = next(c for c in fake.calls if c[0].strip().startswith("INSERT"))
    assert "secret" not in insert[0]          # not in the SQL
    assert "user_id" in insert[0]             # owner injected server-side (multi-user)
    assert len(insert[1]) == 3                # name + color + user_id bound


def test_create_with_no_valid_fields_400(monkeypatch):
    patch_query(monkeypatch, "app.routers.crud", [[]])
    create = _router()[("POST", "/api/widgets")]
    PayloadModel = inspect.signature(create).parameters["payload"].annotation
    with pytest.raises(HTTPException) as e:
        create(PayloadModel(**{"secret": "nope"}))
    assert e.value.status_code == 400


def test_update_missing_row_404(monkeypatch):
    patch_query(monkeypatch, "app.routers.crud", [[]])   # UPDATE ... RETURNING -> nothing
    update = _router()[("PATCH", "/api/widgets/{row_id}")]
    PayloadModel = inspect.signature(update).parameters["payload"].annotation
    with pytest.raises(HTTPException) as e:
        update("missing-id", PayloadModel(**{"name": "z"}))
    assert e.value.status_code == 404


def test_delete_missing_row_404(monkeypatch):
    patch_query(monkeypatch, "app.routers.crud", [[]])
    delete = _router()[("DELETE", "/api/widgets/{row_id}")]
    with pytest.raises(HTTPException) as e:
        delete("missing-id")
    assert e.value.status_code == 404
