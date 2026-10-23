from abc import ABC, abstractmethod

from app.config import get_settings


class OTPProvider(ABC):
    @abstractmethod
    def send(self, phone_number: str, code: str) -> None:
        raise NotImplementedError


class LoggingOTPProvider(OTPProvider):
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))
        print(f"[LoggingOTPProvider] Would send OTP {code} to {phone_number}")


class TwilioOTPProvider(OTPProvider):
    def send(self, phone_number: str, code: str) -> None:
        raise NotImplementedError(
            "TwilioOTPProvider is not wired up yet — Twilio SMS credentials "
            "integration is deferred per the design spec's Known Gaps."
        )


def get_otp_provider() -> OTPProvider:
    settings = get_settings()
    if settings.otp_provider == "logging":
        return LoggingOTPProvider()
    if settings.otp_provider == "twilio":
        return TwilioOTPProvider()
    raise ValueError(f"Unknown OTP provider: {settings.otp_provider}")
