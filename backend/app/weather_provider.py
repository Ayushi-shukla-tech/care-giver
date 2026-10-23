from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import get_settings

_WEATHER_CODE_CONDITIONS = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    80: "rain showers",
    95: "thunderstorms",
}


@dataclass
class WeatherSummary:
    temperature_celsius: float
    condition: str
    location_label: str


class WeatherProvider(ABC):
    @abstractmethod
    def get_forecast(self, latitude: float, longitude: float) -> WeatherSummary:
        raise NotImplementedError


def _reverse_geocode_location_label(latitude: float, longitude: float) -> str:
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": latitude, "lon": longitude, "format": "json", "zoom": 10},
            headers={"User-Agent": "CareGiverApp/1.0"},
            timeout=10.0,
        )
        response.raise_for_status()
        address = response.json().get("address", {})
    except (httpx.HTTPError, ValueError):
        return "your area"

    area = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("suburb")
        or address.get("county")
    )
    if not area:
        return "your area"
    return area


class OpenMeteoWeatherProvider(WeatherProvider):
    def get_forecast(self, latitude: float, longitude: float) -> WeatherSummary:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()["current"]
        weather_code = data["weather_code"]
        condition = _WEATHER_CODE_CONDITIONS.get(weather_code, "unclear")
        return WeatherSummary(
            temperature_celsius=data["temperature_2m"],
            condition=condition,
            location_label=_reverse_geocode_location_label(latitude, longitude),
        )


class LoggingWeatherProvider(WeatherProvider):
    def __init__(self):
        self.calls: list[tuple[float, float]] = []

    def get_forecast(self, latitude: float, longitude: float) -> WeatherSummary:
        self.calls.append((latitude, longitude))
        print(f"[LoggingWeatherProvider] Would fetch forecast for ({latitude}, {longitude})")
        return WeatherSummary(temperature_celsius=25.0, condition="clear", location_label="your area")


def get_weather_provider() -> WeatherProvider:
    settings = get_settings()
    if settings.weather_provider == "logging":
        return LoggingWeatherProvider()
    if settings.weather_provider == "open-meteo":
        return OpenMeteoWeatherProvider()
    raise ValueError(f"Unknown weather provider: {settings.weather_provider}")
