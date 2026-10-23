from app.config import get_settings
from app.storage_provider import LoggingStorageProvider, SupabaseStorageProvider, get_storage_provider


def test_logging_storage_provider_returns_fake_url_and_records_call():
    provider = LoggingStorageProvider()
    url = provider.upload("patient-123", "prescription.jpg", b"fake-bytes", "image/jpeg")
    assert url.startswith("logging://patient-123/")
    assert "prescription.jpg" in url
    assert len(provider.calls) == 1
    assert provider.calls[0] == ("patient-123", "prescription.jpg", b"fake-bytes", "image/jpeg")


def test_get_storage_provider_returns_logging_by_default():
    provider = get_storage_provider()
    assert isinstance(provider, LoggingStorageProvider)


def test_get_storage_provider_returns_supabase_when_configured():
    settings = get_settings()
    original = settings.storage_provider
    settings.storage_provider = "supabase"
    try:
        provider = get_storage_provider()
        assert isinstance(provider, SupabaseStorageProvider)
    finally:
        settings.storage_provider = original
