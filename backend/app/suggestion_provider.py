import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings
from app.weather_provider import WeatherSummary

_SYSTEM_PROMPT = """You are a friendly assistant writing a short, warm, personal \
daily message for an elderly patient, based on today's weather and their known \
medical conditions and allergies.

Rules you must follow:
- Write a warm, personal greeting using the patient's name (e.g. "Hi Grandma \
Jones, looks like it's a sunny day today!" or "Hi Grandma Jones, looks like it's \
a rainy day today."), mentioning today's weather in plain, everyday terms — not \
meteorological jargon.
- Separately, suggest one general lifestyle or activity idea only (e.g. a short \
walk, resting indoors, light stretching). Never mention medications, dosing, or \
timing of any drug. If a recorded condition or allergy is relevant to today's \
weather, add a brief, gentle caveat here (e.g. "since you have hypertension, keep \
today's activity light").
- Keep both parts short and plain, warm language, no medical jargon.
- Never phrase anything as a diagnosis, prescription, or medical instruction. This \
is a friendly suggestion, not medical advice.
- Respond in EXACTLY this format, with no extra commentary:
GREETING: <the greeting and weather mention, one sentence>
SUGGESTION: <the activity idea and optional caveat, one to two sentences>"""


@dataclass
class Suggestion:
    greeting: str
    suggestion: str


def _parse_response(raw: str, patient_name: str, weather: WeatherSummary) -> Suggestion:
    # Reasoning models (e.g. qwen3) emit a <think>...</think> block that can itself
    # contain draft "GREETING:"/"SUGGESTION:" lines while reasoning about the format.
    # Only the content after the closing tag is the real answer.
    final_answer = raw.rsplit("</think>", 1)[-1]

    greeting_matches = re.findall(r"GREETING:\s*(.+)", final_answer)
    suggestion_matches = re.findall(r"SUGGESTION:\s*(.+)", final_answer, re.DOTALL)
    if greeting_matches and suggestion_matches:
        greeting = greeting_matches[-1].split("SUGGESTION:")[0].strip()
        suggestion = suggestion_matches[-1].strip()
        return Suggestion(greeting=greeting, suggestion=suggestion)
    return Suggestion(
        greeting=f"Hi {patient_name}, looks like it's a {weather.condition} day today.",
        suggestion=final_answer.strip() or raw.strip(),
    )


class SuggestionProvider(ABC):
    @abstractmethod
    def generate(
        self, patient_name: str, weather: WeatherSummary, conditions: list[str], allergies: list[str]
    ) -> Suggestion:
        raise NotImplementedError


def _build_user_prompt(
    patient_name: str, weather: WeatherSummary, conditions: list[str], allergies: list[str]
) -> str:
    conditions_text = ", ".join(conditions) if conditions else "none recorded"
    allergies_text = ", ".join(allergies) if allergies else "none recorded"
    return (
        f"Patient's name: {patient_name}.\n"
        f"Today's weather in {weather.location_label}: {weather.temperature_celsius}°C, "
        f"{weather.condition}.\n"
        f"Patient's recorded conditions: {conditions_text}.\n"
        f"Patient's recorded allergies: {allergies_text}.\n"
        "Write the greeting and one gentle activity idea for today."
    )


class GroqSuggestionProvider(SuggestionProvider):
    def generate(
        self, patient_name: str, weather: WeatherSummary, conditions: list[str], allergies: list[str]
    ) -> Suggestion:
        settings = get_settings()
        client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(patient_name, weather, conditions, allergies)},
            ],
        )
        raw = response.choices[0].message.content.strip()
        return _parse_response(raw, patient_name, weather)


class LoggingSuggestionProvider(SuggestionProvider):
    def __init__(self):
        self.calls: list[tuple[str, WeatherSummary, list[str], list[str]]] = []

    def generate(
        self, patient_name: str, weather: WeatherSummary, conditions: list[str], allergies: list[str]
    ) -> Suggestion:
        self.calls.append((patient_name, weather, conditions, allergies))
        greeting = f"Hi {patient_name}, looks like it's a {weather.condition} day today."
        suggestion = (
            f"[LoggingSuggestionProvider] Maybe a short walk would be nice, "
            f"it's {weather.temperature_celsius}°C out there."
        )
        print(f"{greeting} {suggestion}")
        return Suggestion(greeting=greeting, suggestion=suggestion)


def get_suggestion_provider() -> SuggestionProvider:
    settings = get_settings()
    if settings.suggestion_provider == "logging":
        return LoggingSuggestionProvider()
    if settings.suggestion_provider == "groq":
        return GroqSuggestionProvider()
    raise ValueError(f"Unknown suggestion provider: {settings.suggestion_provider}")
