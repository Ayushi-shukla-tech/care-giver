import base64
import json
import re
from abc import ABC, abstractmethod

from openai import OpenAI

from app.config import get_settings
from app.prescription_classifier import (
    NotAPrescriptionError,
    extract_document_texts,
    looks_like_prescription,
)

_SYSTEM_PROMPT = """You are an assistant that reads one or more photos or \
scans of a medical prescription — the images may be multiple pages of the \
same prescription — and extracts every medicine listed across all of them \
into a single combined list.

Rules you must follow:
- For each medicine you can identify anywhere across the provided images, \
extract: name, dose (e.g. "500mg"), and a short frequency hint in the \
prescriber's own words if legible (e.g. "twice daily", "once at night") — \
leave frequency_hint as an empty string if not legible or not present.
- If a medicine appears on more than one image (e.g. a continuation page), \
include it only once in the output.
- If you cannot confidently read a field, leave it as an empty string rather \
than guessing.
- Do not include any commentary, diagnosis, or advice — only extract what is \
literally written.
- Respond with ONLY a JSON array, no other text, in exactly this shape:
[{"name": "...", "dose": "...", "frequency_hint": "..."}, ...]
If no medicines are identifiable, respond with an empty array: []"""


class PrescriptionExtractionProvider(ABC):
    @abstractmethod
    def extract(self, images: list[tuple[bytes, str]]) -> list[dict]:
        raise NotImplementedError


def _parse_candidates(raw: str) -> list[dict]:
    # Reasoning-capable vision models may emit a <think>...</think> block before
    # the real JSON answer (see suggestion_provider.py for the same issue) —
    # only the content after the closing tag is the real answer.
    final_answer = raw.rsplit("</think>", 1)[-1].strip()
    match = re.search(r"\[.*\]", final_answer, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [
        {
            "name": str(item.get("name", "")).strip(),
            "dose": str(item.get("dose", "")).strip(),
            "frequency_hint": str(item.get("frequency_hint", "")).strip(),
        }
        for item in parsed
        if isinstance(item, dict)
    ]


class GroqVisionExtractionProvider(PrescriptionExtractionProvider):
    def extract(self, images: list[tuple[bytes, str]]) -> list[dict]:
        settings = get_settings()
        client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")

        image_content_blocks = []
        for image_bytes, content_type in images:
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            data_url = f"data:{content_type};base64,{b64_image}"
            image_content_blocks.append({"type": "image_url", "image_url": {"url": data_url}})

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract every medicine from these prescription image(s)."},
                        *image_content_blocks,
                    ],
                },
            ],
        )
        raw = response.choices[0].message.content.strip()
        return _parse_candidates(raw)


# Ordered: more specific patterns (three/twice, explicit 1-0-1 grids) must be
# checked before the generic once-a-day patterns.
_FREQUENCY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b1\s*-\s*1\s*-\s*1\b|\btds\b|\btid\b|\bthrice\b|\bthree\s+times\b", re.I),
     "three times a day — after breakfast, after lunch and after dinner"),
    (re.compile(r"\bqid\b|\bfour\s+times\b", re.I),
     "four times a day — after breakfast, after lunch, after dinner and at bedtime"),
    (re.compile(r"\b1\s*-\s*0\s*-\s*1\b|\bbd\b|\bbid\b|\btwice\b|\btwo\s+times\b", re.I),
     "twice a day — after breakfast and after dinner"),
    (re.compile(r"\b1\s*-\s*1\s*-\s*0\b", re.I),
     "twice a day — after breakfast and after lunch"),
    (re.compile(r"\b0\s*-\s*1\s*-\s*1\b", re.I),
     "twice a day — after lunch and after dinner"),
    (re.compile(r"\bhs\b|\bat\s+night\b|\bbed\s*time\b|\b0\s*-\s*0\s*-\s*1\b", re.I),
     "once a day — at night after dinner"),
    (re.compile(r"\b0\s*-\s*1\s*-\s*0\b", re.I),
     "once a day — after lunch"),
    (re.compile(r"\bod\b|\bqd\b|\bonce\s+(?:a\s+day|daily)\b|\b1\s*-\s*0\s*-\s*0\b", re.I),
     "once a day — after breakfast"),
]

# Longest alternatives first so e.g. "capsule" isn't half-eaten by "cap".
_FORM_PREFIX = re.compile(
    r"^\s*(?:\d+\s*[\).:-]?\s*)?(?:rx\.?\s+)?"
    r"(?:tablet|tab|capsule|cap|syrup|syp|injection|inj|ointment|oint|drops?|cream|gel)s?\.?\s*",
    re.I,
)
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|units?)\b", re.I)
_FREQ_TOKEN = re.compile(
    r"\b(?:od|bd|bid|tds|tid|qid|qd|hs|[01]\s*-\s*[01]\s*-\s*[01]|once|twice|thrice|daily|"
    r"at\s+night|bed\s*time|before\s+(?:food|meals?)|after\s+(?:food|meals?))\b",
    re.I,
)


def _frequency_hint(line: str) -> str:
    for pattern, hint in _FREQUENCY_RULES:
        if pattern.search(line):
            return hint
    return ""


# Dose-column phrases in tabular prescriptions, e.g. "1 cap once daily after
# meal", "1 tab once daily after breakfast", "once every fortnight".
_DOSE_PHRASE = re.compile(
    r"\b(?:\d+\s*(?:tab|tablet|cap|capsule|tsp|puff|drop)s?\s+)?"
    r"(?:once|twice|thrice|\d+\s*times?)\s+(?:a\s+day|daily|every\s+\w+)"
    r"(?:\s+(?:after|before|with)\s+(?:meals?|food|breakfast|lunch|dinner))?",
    re.I,
)


def _pair_tabular_frequencies(text: str, candidates: list[dict]) -> None:
    """Tabular prescriptions OCR column by column: medicine names first, then
    the dose column as its own block in the same row order. When the number of
    dose phrases matches the number of candidates missing a frequency, pair
    them positionally."""
    flat = re.sub(r"\s+", " ", text)
    phrases = [m.group(0).strip() for m in _DOSE_PHRASE.finditer(flat)]
    missing = [c for c in candidates if not c["frequency_hint"]]
    if not phrases or len(phrases) != len(missing):
        return
    for candidate, phrase in zip(missing, phrases):
        candidate["frequency_hint"] = _frequency_hint(phrase) or phrase


def _parse_ocr_text(text: str) -> list[dict]:
    candidates: list[dict] = []
    seen_names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) < 3:
            continue

        has_form_prefix = bool(_FORM_PREFIX.match(line))
        dose_match = _DOSE.search(line)
        if not has_form_prefix and not dose_match:
            continue

        name = _FORM_PREFIX.sub("", line)
        # The medicine name is whatever comes before the dose / frequency tokens.
        cut_points = [m.start() for m in (_DOSE.search(name), _FREQ_TOKEN.search(name)) if m]
        if cut_points:
            name = name[: min(cut_points)]
        name = re.sub(r"[^A-Za-z0-9 \-/]+", " ", name)
        name = re.sub(r"\s{2,}", " ", name).strip(" -/")
        if len(name) < 2:
            continue

        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        candidates.append(
            {
                "name": name,
                "dose": dose_match.group(0).strip() if dose_match else "",
                "frequency_hint": _frequency_hint(line),
            }
        )
    _pair_tabular_frequencies(text, candidates)
    return candidates


class TesseractOcrExtractionProvider(PrescriptionExtractionProvider):
    """OCRs the uploaded images with pytesseract, rejects images that don't look
    like a medical prescription, then parses medicines + dosing schedule."""

    def extract(self, images: list[tuple[bytes, str]]) -> list[dict]:
        texts = []
        for file_bytes, content_type in images:
            texts.extend(extract_document_texts(file_bytes, content_type))

        combined = "\n".join(texts)
        if not combined.strip() or not looks_like_prescription(combined):
            raise NotAPrescriptionError(
                "Oops — that doesn't look like a medical prescription. "
                "Please upload a valid prescription image."
            )

        return _parse_ocr_text(combined)


class LoggingPrescriptionExtractionProvider(PrescriptionExtractionProvider):
    def __init__(self):
        self.calls: list[list[tuple[bytes, str]]] = []

    def extract(self, images: list[tuple[bytes, str]]) -> list[dict]:
        self.calls.append(images)
        print(f"[LoggingPrescriptionExtractionProvider] Would extract from {len(images)} image(s)")
        return [{"name": "Metformin", "dose": "500mg", "frequency_hint": "twice daily"}]


def get_extraction_provider() -> PrescriptionExtractionProvider:
    settings = get_settings()
    if settings.prescription_extraction_provider == "logging":
        return LoggingPrescriptionExtractionProvider()
    if settings.prescription_extraction_provider == "groq":
        return GroqVisionExtractionProvider()
    if settings.prescription_extraction_provider == "tesseract":
        return TesseractOcrExtractionProvider()
    raise ValueError(f"Unknown prescription extraction provider: {settings.prescription_extraction_provider}")
