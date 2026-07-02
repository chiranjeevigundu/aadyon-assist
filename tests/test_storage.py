import io
from unittest.mock import MagicMock

def test_upload_fileobj(monkeypatch):
    from app.services import storage

    # Mock settings
    mock_settings = MagicMock()
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
