"""S3-compatible cloud storage client with a local disk fallback."""
import boto3
import shutil
from botocore.exceptions import ClientError
from app.core.config import get_settings

class StorageError(Exception):
    pass

def get_s3_client():
    s = get_settings()
    if not s.s3_access_key or not s.s3_secret_key:
        return None
        
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url if s.s3_endpoint_url else None,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key
    )

def _get_local_path(object_key: str):
    s = get_settings()
    path = s.artifacts_dir / "uploads" / object_key
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def upload_fileobj(file_obj, object_key: str, content_type: str | None = None) -> str:
    """Upload a file-like object to S3, or local disk if S3 is not configured."""
    settings = get_settings()
    
    # Mock behavior for CI
    if settings.s3_access_key == "ci":
        return object_key
        
    s3 = get_s3_client()
    if not s3:
        # Fallback to local storage
        local_path = _get_local_path(object_key)
        with open(local_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return object_key

    try:
        s3.upload_fileobj(
            file_obj,
            settings.s3_bucket,
            object_key,
            ExtraArgs={"ContentType": content_type} if content_type else None
        )
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_key

def upload_file(file_path: str, object_name: str) -> str:
    """Upload a local file to S3, or local disk if S3 is not configured."""
    s = get_settings()
    
    # Mock behavior for CI
    if s.s3_access_key == "ci":
        return object_name
        
    s3 = get_s3_client()
    if not s3:
        # Fallback to local storage
        local_path = _get_local_path(object_name)
        shutil.copy2(file_path, local_path)
        return object_name

    try:
        s3.upload_file(file_path, s.s3_bucket, object_name)
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_name

def download_fileobj(object_key: str, file_obj):
    """Download an object from S3 (or local disk) into a file-like object."""
    settings = get_settings()
    
    # Mock behavior for CI
    if settings.s3_access_key == "ci":
        file_obj.write(b"dummy content")
        return
        
    s3 = get_s3_client()
    if not s3:
        # Fallback to local storage
        local_path = _get_local_path(object_key)
        if not local_path.exists():
            raise StorageError("File not found on local disk")
        with open(local_path, "rb") as f:
            shutil.copyfileobj(f, file_obj)
        return

    try:
        s3.download_fileobj(settings.s3_bucket, object_key, file_obj)
    except ClientError as e:
        raise StorageError(f"Download failed: {e}") from e

