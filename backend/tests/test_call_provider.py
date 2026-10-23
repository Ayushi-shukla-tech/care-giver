import pytest

from app.call_provider import LoggingCallProvider, TwilioCallProvider, get_call_provider


def test_logging_call_provider_records_calls():
    provider = LoggingCallProvider()
    provider.call("+15551234567", "Time to take your Metformin")
    assert provider.calls == [("+15551234567", "Time to take your Metformin")]


def test_twilio_call_provider_raises_not_implemented():
    provider = TwilioCallProvider()
    with pytest.raises(NotImplementedError):
        provider.call("+15551234567", "Time to take your Metformin")


def test_get_call_provider_returns_logging_by_default():
    provider = get_call_provider()
    assert isinstance(provider, LoggingCallProvider)
