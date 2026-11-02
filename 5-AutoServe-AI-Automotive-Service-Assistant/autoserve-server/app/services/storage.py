"""Object storage (rules/70): private bucket, random keys `ro/{ro_id}/{uuid}.{ext}`, SSE, presigned reads.

Backends: `s3` (MinIO locally, S3 SSE-KMS in AWS) and `local` (filesystem; tests/offline only).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def presigned_url(self, key: str, expires_s: int = 300) -> str: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.s3_bucket
        self.sse = settings.s3_sse
        self.kms_key_id = settings.s3_kms_key_id
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key.get_secret_value() if settings.s3_access_key else None,
            aws_secret_access_key=settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else None,
            region_name=settings.s3_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        extra: dict[str, Any] = {"ContentType": content_type}
        if self.sse == "aws:kms":
            extra["ServerSideEncryption"] = "aws:kms"
            if self.kms_key_id:
                extra["SSEKMSKeyId"] = self.kms_key_id
        elif self.sse == "AES256":
            extra["ServerSideEncryption"] = "AES256"
        await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=key, Body=data, **extra)

    async def get(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=key)
        return bytes(obj["Body"].read())

    async def presigned_url(self, key: str, expires_s: int = 300) -> str:
        return str(
            await asyncio.to_thread(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_s,
            )
        )


class LocalStorage:
    """Filesystem storage for tests/offline demos. Never used when APP_ENV is prod."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def presigned_url(self, key: str, expires_s: int = 300) -> str:
        return f"local://{key}?expires={expires_s}"


def get_storage(settings: Settings | None = None) -> Storage:
    s = settings or get_settings()
    if s.storage_backend == "local":
        if s.app_env == "prod":
            raise RuntimeError("local storage backend is not allowed in prod")
        return LocalStorage(Path(s.local_storage_dir))
    return S3Storage(s)
