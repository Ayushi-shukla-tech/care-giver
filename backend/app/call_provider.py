from abc import ABC, abstractmethod

from app.config import get_settings


class CallProvider(ABC):
    @abstractmethod
    def call(self, phone_number: str, message: str) -> None:
        raise NotImplementedError


class LoggingCallProvider(CallProvider):
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def call(self, phone_number: str, message: str) -> None:
        self.calls.append((phone_number, message))
        print(f"[LoggingCallProvider] Would call {phone_number}: {message!r}")


class TwilioCallProvider(CallProvider):
    def call(self, phone_number: str, message: str) -> None:
        raise NotImplementedError(
            "TwilioCallProvider is not wired up yet — Twilio credentials "
            "integration is deferred per the design spec's Known Gaps."
        )


def get_call_provider() -> CallProvider:
    settings = get_settings()
    if settings.call_provider == "logging":
        return LoggingCallProvider()
    if settings.call_provider == "twilio":
        return TwilioCallProvider()
    raise ValueError(f"Unknown call provider: {settings.call_provider}")
