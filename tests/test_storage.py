import io
from unittest.mock import MagicMock

def test_upload_fileobj(monkeypatch):
    from app.services import storage

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.storage_backend = "s3"
    mock_settings.s3_access_key = "test_key"
    mock_settings.s3_secret_key = "test_secret"
    mock_settings.s3_bucket = "test-bucket"
    mock_settings.s3_endpoint_url = "http://localhost:9000"
    monkeypatch.setattr("app.services.storage.get_settings", lambda: mock_settings)

    # Mock boto3 client
    mock_client = MagicMock()
    monkeypatch.setattr("app.services.storage.get_s3_client", lambda: mock_client)

    file_obj = io.BytesIO(b"test content")
    result = storage.upload_fileobj(file_obj, "test/object.txt", "text/plain")

    assert result == "test/object.txt"
    mock_client.upload_fileobj.assert_called_once_with(
        file_obj, "test-bucket", "test/object.txt", ExtraArgs={"ContentType": "text/plain"}
    )

def test_download_fileobj(monkeypatch):
    from app.services import storage

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.storage_backend = "s3"
    mock_settings.s3_access_key = "test_key"
    mock_settings.s3_secret_key = "test_secret"
    mock_settings.s3_bucket = "test-bucket"
    monkeypatch.setattr("app.services.storage.get_settings", lambda: mock_settings)

    # Mock boto3 client
    def mock_download(bucket, key, file_obj):
        file_obj.write(b"downloaded content")

    mock_client = MagicMock()
    mock_client.download_fileobj.side_effect = mock_download
    monkeypatch.setattr("app.services.storage.get_s3_client", lambda: mock_client)

    file_obj = io.BytesIO()
    storage.download_fileobj("test/object.txt", file_obj)

    assert file_obj.getvalue() == b"downloaded content"


def _local_settings(tmp_path):
    """Settings with no S3 keys -> the local-disk fallback path."""
    s = MagicMock()
    s.storage_backend = "local"
    s.s3_access_key = ""
    s.s3_secret_key = ""
    s.artifacts_dir = tmp_path
    return s


def test_local_fallback_roundtrip(monkeypatch, tmp_path):
    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_settings", lambda: _local_settings(tmp_path))

    storage.upload_fileobj(io.BytesIO(b"local content"), "uid/report.pdf", "application/pdf")
    assert (tmp_path / "uploads" / "uid" / "report.pdf").read_bytes() == b"local content"

    out = io.BytesIO()
    storage.download_fileobj("uid/report.pdf", out)
    assert out.getvalue() == b"local content"


def test_local_fallback_rejects_traversal(monkeypatch, tmp_path):
    import pytest

    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_settings", lambda: _local_settings(tmp_path))

    for bad_key in ("uid/..", "../escape.txt", ".", ""):
        with pytest.raises(storage.StorageError):
            storage.upload_fileobj(io.BytesIO(b"x"), bad_key)

    with pytest.raises(storage.StorageError):
        storage.download_fileobj("uid/missing.txt", io.BytesIO())


def _s3_settings(**over):
    """A settings stub with the full S3 knob set, overridable per-test."""
    s = MagicMock()
    s.storage_backend = "s3"
    s.s3_access_key = over.get("s3_access_key", "test")
    s.s3_secret_key = over.get("s3_secret_key", "test")
    s.s3_bucket = over.get("s3_bucket", "aadyon-assist")
    s.s3_endpoint_url = over.get("s3_endpoint_url", "http://host.docker.internal:4566")
    s.s3_region = over.get("s3_region", "us-east-1")
    s.s3_force_path_style = over.get("s3_force_path_style", True)
    s.s3_auto_create_bucket = over.get("s3_auto_create_bucket", True)
    return s


def test_get_s3_client_is_config_driven(monkeypatch):
    """The client is built from config: endpoint, region, and path-style addressing
    all flow through — this is what makes AWS<->emulator a config-only switch."""
    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_settings", lambda: _s3_settings())
    client = storage.get_s3_client()
    assert client is not None
    assert client.meta.region_name == "us-east-1"
    assert client.meta.endpoint_url == "http://host.docker.internal:4566"
    # path-style requested -> botocore records it on the client config
    assert client.meta.config.s3["addressing_style"] == "path"


def test_get_s3_client_virtual_addressing_for_real_aws(monkeypatch):
    from app.services import storage

    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _s3_settings(s3_endpoint_url="", s3_force_path_style=False, s3_region="eu-west-1"),
    )
    client = storage.get_s3_client()
    assert client.meta.region_name == "eu-west-1"
    assert client.meta.endpoint_url.endswith("amazonaws.com")
    assert client.meta.config.s3["addressing_style"] == "virtual"


def test_get_s3_client_none_when_unconfigured(monkeypatch):
    """No static creds and no emulator endpoint -> None, so callers fall back to
    local disk instead of guessing at ambient AWS credentials."""
    from app.services import storage

    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _s3_settings(s3_access_key="", s3_secret_key="", s3_endpoint_url=""),
    )
    assert storage.get_s3_client() is None


def test_ensure_bucket_noop_when_present(monkeypatch):
    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_settings", lambda: _s3_settings())
    client = MagicMock()
    assert storage.ensure_bucket(client) is True
    client.head_bucket.assert_called_once_with(Bucket="aadyon-assist")
    client.create_bucket.assert_not_called()


def test_ensure_bucket_creates_when_missing(monkeypatch):
    from botocore.exceptions import ClientError

    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_settings", lambda: _s3_settings())
    client = MagicMock()
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
    )
    assert storage.ensure_bucket(client) is True
    # emulator endpoint set -> plain create, no LocationConstraint
    client.create_bucket.assert_called_once_with(Bucket="aadyon-assist")


def test_ensure_bucket_region_constraint_on_real_aws(monkeypatch):
    from botocore.exceptions import ClientError

    from app.services import storage

    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _s3_settings(s3_endpoint_url="", s3_region="ap-south-1"),
    )
    client = MagicMock()
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadBucket"
    )
    storage.ensure_bucket(client)
    client.create_bucket.assert_called_once_with(
        Bucket="aadyon-assist",
        CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
    )


def test_ensure_bucket_false_without_client(monkeypatch):
    from app.services import storage

    monkeypatch.setattr("app.services.storage.get_s3_client", lambda: None)
    monkeypatch.setattr("app.services.storage.get_settings", lambda: _s3_settings())
    assert storage.ensure_bucket() is False


def _backend_settings(backend, access_key="ci", secret_key="ci", tmp_path=None):
    s = MagicMock()
    s.storage_backend = backend
    s.s3_access_key = access_key
    s.s3_secret_key = secret_key
    s.artifacts_dir = tmp_path
    return s


def test_mock_backend_is_noop(monkeypatch):
    # Explicit mock backend: no real I/O (for CI/tests that don't touch disk or S3).
    from app.services import storage
    monkeypatch.setattr("app.services.storage.get_settings",
                        lambda: _backend_settings("mock"))
    assert storage.upload_fileobj(io.BytesIO(b"x"), "uid/f.txt") == "uid/f.txt"
    out = io.BytesIO()
    storage.download_fileobj("uid/f.txt", out)
    assert out.getvalue() == b"dummy content"


def test_ci_placeholder_creds_persist_locally(monkeypatch, tmp_path):
    # The bug: dev/prod secrets literally contained "ci", which used to force mock
    # mode and silently discard uploads. Now the default is local disk, so content
    # actually round-trips even with the placeholder creds present.
    from app.services import storage
    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: _backend_settings("local", access_key="ci", secret_key="ci", tmp_path=tmp_path),
    )
    storage.upload_fileobj(io.BytesIO(b"real statement bytes"), "uid/stmt.txt")
    out = io.BytesIO()
    storage.download_fileobj("uid/stmt.txt", out)
    assert out.getvalue() == b"real statement bytes"
