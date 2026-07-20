"""Portability fixes: DB sslmode passthrough + S3 region / default-credential chain.

These make the same image run against any managed Postgres + object store
(AWS/Azure/GCP/...) without cloud-specific coupling. All pure-unit, no network.
"""
import types


# --------------------------------------------------------------------------- DB sslmode
def _fake_settings(**over):
    s = types.SimpleNamespace(
        db_host="h", db_port=5432, db_name="d", db_user="u", db_password="p",
        db_sslmode="", storage_backend="s3", s3_endpoint_url="", s3_region="",
        s3_access_key="", s3_secret_key="",
    )
    for k, v in over.items():
        setattr(s, k, v)
    return s


def test_db_sslmode_omitted_when_unset(monkeypatch):
    from app.db import session
    captured = {}

    class FakePool:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(session, "ThreadedConnectionPool", FakePool)
    monkeypatch.setattr(session, "get_settings", lambda: _fake_settings(db_sslmode=""))
    monkeypatch.setattr(session, "_pool", None)
    session.pool()
    assert "sslmode" not in captured  # unset => libpq default ('prefer'), local unchanged


def test_db_sslmode_passed_when_set(monkeypatch):
    from app.db import session
    captured = {}

    class FakePool:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(session, "ThreadedConnectionPool", FakePool)
    monkeypatch.setattr(session, "get_settings", lambda: _fake_settings(db_sslmode="require"))
    monkeypatch.setattr(session, "_pool", None)
    session.pool()
    assert captured.get("sslmode") == "require"  # managed DB can enforce TLS


# --------------------------------------------------------------------------- S3 client
def test_s3_client_uses_default_chain_without_keys(monkeypatch):
    """s3 backend + no explicit keys => build a client that uses boto3's default
    credential chain (instance role / workload identity), not None."""
    from app.services import storage
    captured = {}

    def fake_client(name, **kw):
        captured["name"] = name
        captured["kw"] = kw
        return object()

    monkeypatch.setattr(storage.boto3, "client", fake_client)
    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _fake_settings(s3_region="us-east-1", s3_access_key="", s3_secret_key=""),
    )
    client = storage.get_s3_client()
    assert client is not None
    assert captured["name"] == "s3"
    assert captured["kw"].get("region_name") == "us-east-1"
    assert "aws_access_key_id" not in captured["kw"]  # falls through to default chain


def test_s3_client_uses_explicit_keys_and_endpoint(monkeypatch):
    from app.services import storage
    captured = {}

    def fake_client(name, **kw):
        captured["kw"] = kw
        return object()

    monkeypatch.setattr(storage.boto3, "client", fake_client)
    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _fake_settings(
            s3_region="eu-west-1", s3_endpoint_url="https://r2.example.com",
            s3_access_key="AK", s3_secret_key="SK",
        ),
    )
    storage.get_s3_client()
    kw = captured["kw"]
    assert kw["aws_access_key_id"] == "AK" and kw["aws_secret_access_key"] == "SK"
    assert kw["endpoint_url"] == "https://r2.example.com"  # S3-compatible (R2/GCS/MinIO)
    assert kw["region_name"] == "eu-west-1"


def test_s3_client_none_when_backend_not_s3(monkeypatch):
    from app.services import storage
    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _fake_settings(storage_backend="local"),
    )
    assert storage.get_s3_client() is None
