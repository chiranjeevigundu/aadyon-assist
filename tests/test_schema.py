"""Data-admin metadata: column types, writable/managed/required + FK detection."""
from app.models.tables import Entity
from app.services import schema
from conftest import patch_query


def test_entities_meta(monkeypatch):
    monkeypatch.setattr(schema, "ENTITIES", [Entity("widgets", ["name", "color"])])
    cols = [
        {"column_name": "id", "data_type": "uuid", "is_nullable": "NO",
         "column_default": "gen_random_uuid()"},
        {"column_name": "name", "data_type": "text", "is_nullable": "NO", "column_default": None},
        {"column_name": "color", "data_type": "text", "is_nullable": "YES", "column_default": None},
        {"column_name": "team_id", "data_type": "uuid", "is_nullable": "YES", "column_default": None},
    ]

    def q(sql, p=(), c=False):
        if "information_schema.columns" in sql:
            return cols
        if "FOREIGN KEY" in sql or "table_constraints" in sql:
            return [{"column_name": "team_id", "ref_table": "teams"}]
        return []

    patch_query(monkeypatch, "app.services.schema", q)
    meta = schema.entities_meta()
    assert len(meta) == 1
    by_name = {c["name"]: c for c in meta[0]["columns"]}

    assert by_name["id"]["managed"] is True and by_name["id"]["writable"] is False
    assert by_name["id"]["required"] is False                     # managed -> never required
    assert by_name["name"]["writable"] is True
    assert by_name["name"]["required"] is True                    # NOT NULL, no default, writable
    assert by_name["color"]["required"] is False                  # nullable
    assert by_name["team_id"]["references"] == "teams"
    assert by_name["team_id"]["writable"] is False                # not in the entity whitelist
