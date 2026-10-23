from abc import ABC, abstractmethod

import boto3
import httpx

from app.config import get_settings


class StorageProvider(ABC):
    @abstractmethod
    def upload(self, patient_id: str, filename: str, content: bytes, content_type: str) -> str:
        raise NotImplementedError


class LoggingStorageProvider(StorageProvider):
    def __init__(self):
        self.calls: list[tuple[str, str, bytes, str]] = []

    def upload(self, patient_id: str, filename: str, content: bytes, content_type: str) -> str:
        self.calls.append((patient_id, filename, content, content_type))
        url = f"logging://{patient_id}/{filename}"
        print(f"[LoggingStorageProvider] Would upload {filename} ({len(content)} bytes) -> {url}")
        return url


class R2StorageProvider(StorageProvider):
    def upload(self, patient_id: str, filename: str, content: bytes, content_type: str) -> str:
        settings = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        key = f"{patient_id}/{filename}"
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return f"{settings.r2_public_base_url}/{key}"


class SupabaseStorageProvider(StorageProvider):
    def upload(self, patient_id: str, filename: str, content: bytes, content_type: str) -> str:
        settings = get_settings()
        key = f"{patient_id}/{filename}"
        response = httpx.put(
            f"{settings.supabase_url}/storage/v1/object/{settings.supabase_bucket_name}/{key}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=content,
            timeout=30.0,
        )
        response.raise_for_status()
        return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket_name}/{key}"


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_provider == "logging":
        return LoggingStorageProvider()
    if settings.storage_provider == "r2":
        return R2StorageProvider()
    if settings.storage_provider == "supabase":
        return SupabaseStorageProvider()
    raise ValueError(f"Unknown storage provider: {settings.storage_provider}")
