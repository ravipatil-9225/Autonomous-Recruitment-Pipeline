"""
Object Storage Service  (MinIO / AWS S3)
──────────────────────────────────────────
Abstraction over boto3 for resume file storage.
Configured via settings; transparently works with both MinIO (local dev)
and real AWS S3 (production).
"""
import logging
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Return a boto3 S3 client, optionally pointed at MinIO."""
    kwargs: dict = {
        "aws_access_key_id": settings.s3_access_key,
        "aws_secret_access_key": settings.s3_secret_key,
        "region_name": settings.s3_region,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def ensure_bucket_exists() -> None:
    """Create the resume bucket if it doesn't exist (idempotent)."""
    client = _get_client()
    bucket = settings.s3_bucket_resumes
    try:
        client.head_bucket(Bucket=bucket)
        logger.info(f"S3 bucket '{bucket}' already exists.")
    except ClientError as exc:
        error_code = int(exc.response["Error"]["Code"])
        if error_code == 404:
            client.create_bucket(Bucket=bucket)
            logger.info(f"S3 bucket '{bucket}' created.")
        else:
            raise


def upload_resume(file_bytes: bytes, s3_key: str, content_type: str) -> str:
    """
    Upload resume bytes to S3/MinIO.

    Args:
        file_bytes: Raw file content.
        s3_key:     Target object key (e.g. "resumes/<uuid>/<filename>").
        content_type: MIME type ("application/pdf" or
                      "application/vnd.openxmlformats-officedocument…").

    Returns:
        The s3_key on success.
    """
    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket_resumes,
        Key=s3_key,
        Body=BytesIO(file_bytes),
        ContentType=content_type,
        ServerSideEncryption="AES256",  # server-side encryption at rest
    )
    logger.info(f"Uploaded resume to s3://{settings.s3_bucket_resumes}/{s3_key}")
    return s3_key


def download_resume(s3_key: str) -> bytes:
    """Download resume bytes from S3/MinIO."""
    client = _get_client()
    response = client.get_object(Bucket=settings.s3_bucket_resumes, Key=s3_key)
    return response["Body"].read()


def delete_resume(s3_key: str) -> bool:
    """
    Delete a resume from S3/MinIO.
    Returns True if deleted, False if object did not exist.
    """
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.s3_bucket_resumes, Key=s3_key)
        logger.info(f"Deleted s3://{settings.s3_bucket_resumes}/{s3_key}")
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return False
        raise


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """
    Generate a pre-signed URL for temporary secure access to a resume.

    Args:
        s3_key:     Object key.
        expires_in: URL TTL in seconds (default 1 hour).

    Returns:
        Pre-signed HTTPS URL.
    """
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_resumes, "Key": s3_key},
        ExpiresIn=expires_in,
    )
