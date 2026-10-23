import pytest

from app.otp_provider import LoggingOTPProvider, TwilioOTPProvider, get_otp_provider


def test_logging_otp_provider_records_sends():
    provider = LoggingOTPProvider()
    provider.send("+15551234567", "123456")
    assert provider.sent == [("+15551234567", "123456")]


def test_twilio_otp_provider_raises_not_implemented():
    provider = TwilioOTPProvider()
    with pytest.raises(NotImplementedError):
        provider.send("+15551234567", "123456")


def test_get_otp_provider_returns_logging_by_default():
    provider = get_otp_provider()
    assert isinstance(provider, LoggingOTPProvider)
