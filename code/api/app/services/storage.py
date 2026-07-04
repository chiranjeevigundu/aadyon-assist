"""S3-compatible cloud storage client with a local disk fallback."""
import shutil

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


class StorageError(Exception):
    pass


def _backend() -> str:
    """Which storage backend is active: 'local' (disk), 's3', or 'mock'.

    Explicit via STORAGE_BACKEND (see config). For backward compatibility with the
    unit tests that set s3 creds and monkeypatch get_s3_client without a backend,
    a real-looking s3 credential pair still infers 's3'; the literal 'ci' sentinel
    (used only as a dummy in CI secrets) does NOT — it falls through to 'local' so
    a deployment carrying placeholder creds persists uploads instead of mocking."""
    s = get_settings()
    b = getattr(s, "storage_backend", "") if isinstance(getattr(s, "storage_backend", ""), str) else ""
    if b in ("local", "s3", "mock"):
        return b
    if s.s3_access_key and s.s3_secret_key and s.s3_access_key != "ci":
        return "s3"
    return "local"


def get_s3_client():
    s = get_settings()
    if not s.s3_access_key or not s.s3_secret_key:
        return None

    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url if s.s3_endpoint_url else None,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
    )


def _get_local_path(object_key: str):
    """Map an object key to a path under the uploads root, refusing keys that
    would escape it (e.g. '..' segments surviving filename sanitization)."""
    root = (get_settings().artifacts_dir / "uploads").resolve()
    path = (root / object_key).resolve()
    if root not in path.parents:
        raise StorageError(f"Invalid object key: {object_key!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _require_s3():
    s3 = get_s3_client()
    if not s3:
        raise StorageError("STORAGE_BACKEND=s3 but S3 credentials are not configured")
    return s3


def upload_fileobj(file_obj, object_key: str, content_type: str | None = None) -> str:
    """Persist a file-like object to the active backend (local disk / S3 / mock)."""
    backend = _backend()
    if backend == "mock":
        return object_key
    if backend == "local":
        with open(_get_local_path(object_key), "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return object_key
    try:
        _require_s3().upload_fileobj(
            file_obj,
            get_settings().s3_bucket,
            object_key,
            ExtraArgs={"ContentType": content_type} if content_type else None,
        )
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_key


def upload_file(file_path: str, object_name: str) -> str:
    """Persist a local file to the active backend (local disk / S3 / mock)."""
    backend = _backend()
    if backend == "mock":
        return object_name
    if backend == "local":
        shutil.copy2(file_path, _get_local_path(object_name))
        return object_name
    try:
        _require_s3().upload_file(file_path, get_settings().s3_bucket, object_name)
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_name


def download_fileobj(object_key: str, file_obj):
    """Read an object from the active backend into a file-like object."""
    backend = _backend()
    if backend == "mock":
        file_obj.write(b"dummy content")
        return
    if backend == "local":
        local_path = _get_local_path(object_key)
        if not local_path.exists():
            raise StorageError("File not found on local disk")
        with open(local_path, "rb") as f:
            shutil.copyfileobj(f, file_obj)
        return
    try:
        _require_s3().download_fileobj(get_settings().s3_bucket, object_key, file_obj)
    except ClientError as e:
        raise StorageError(f"Download failed: {e}") from e
