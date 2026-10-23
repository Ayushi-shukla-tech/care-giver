from app.prescription_extraction_provider import (
    LoggingPrescriptionExtractionProvider,
    get_extraction_provider,
)


def test_logging_extraction_provider_returns_fixed_candidate():
    provider = LoggingPrescriptionExtractionProvider()
    candidates = provider.extract([(b"fake-image-bytes", "image/jpeg")])
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Metformin"
    assert candidates[0]["dose"] == "500mg"
    assert candidates[0]["frequency_hint"] == "twice daily"
    assert len(provider.calls) == 1
    assert provider.calls[0] == [(b"fake-image-bytes", "image/jpeg")]


def test_logging_extraction_provider_accepts_multiple_images():
    provider = LoggingPrescriptionExtractionProvider()
    images = [(b"page-1-bytes", "image/jpeg"), (b"page-2-bytes", "image/jpeg")]
    candidates = provider.extract(images)
    assert len(candidates) == 1
    assert provider.calls[0] == images


def test_get_extraction_provider_returns_logging_by_default():
    provider = get_extraction_provider()
    assert isinstance(provider, LoggingPrescriptionExtractionProvider)
