from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    # Type stubs are a dev dependency and are not installed in the runtime image.
    from mypy_boto3_s3 import S3Client


def make_s3_client(settings: Settings, *, timeout_s: float = 10) -> S3Client:
    """S3 client for Cloudflare R2.

    R2 has no regions ("auto") and rejects some of the default request checksums that
    newer botocore versions send, so checksums are only computed when an operation requires them.
    """
    if not settings.s3_configured:
        raise RuntimeError("Object storage is not configured: set S3_* variables in .env")
    assert settings.s3_secret_access_key is not None
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=timeout_s,
            read_timeout=timeout_s,
            retries={"max_attempts": 3, "mode": "standard"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def put_bytes(key: str, data: bytes) -> None:
    settings = get_settings()
    if settings.s3_configured:
        make_s3_client(settings).put_object(Bucket=settings.s3_bucket, Key=key, Body=data)
        return
    path = Path(settings.local_storage_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_bytes(key: str) -> bytes:
    settings = get_settings()
    if settings.s3_configured:
        obj = make_s3_client(settings).get_object(Bucket=settings.s3_bucket, Key=key)
        return obj["Body"].read()
    return (Path(settings.local_storage_dir) / key).read_bytes()
