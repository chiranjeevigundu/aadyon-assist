"""S3-compatible cloud storage client."""
import boto3
from botocore.exceptions import ClientError
from app.core.config import get_settings

class StorageError(Exception):
    pass

def get_s3_client():
    s = get_settings()
    if not s.s3_access_key or not s.s3_secret_key:
        raise StorageError("S3 credentials not configured")
        
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url if s.s3_endpoint_url else None,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key
    )

def upload_fileobj(file_obj, object_name: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file-like object to S3. Returns the object key."""
    s = get_settings()
    s3 = get_s3_client()
    try:
        s3.upload_fileobj(
            file_obj,
            s.s3_bucket,
            object_name,
            ExtraArgs={"ContentType": content_type}
        )
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_name

def upload_file(file_path: str, object_name: str) -> str:
    """Upload a local file to S3. Returns the object key."""
    s = get_settings()
    s3 = get_s3_client()
    try:
        s3.upload_file(file_path, s.s3_bucket, object_name)
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}") from e
    return object_name

def download_fileobj(object_name: str, file_obj) -> None:
    """Download an object from S3 into a file-like object."""
    s = get_settings()
    s3 = get_s3_client()
    try:
        s3.download_fileobj(s.s3_bucket, object_name, file_obj)
    except ClientError as e:
        raise StorageError(f"Download failed: {e}") from e
