"""OCR + heuristic classifier that decides whether uploaded images look like a
medical prescription before we try to extract medicines from them."""

import io
import re

import pymupdf
import pytesseract
from PIL import Image


class NotAPrescriptionError(Exception):
    """Raised when the uploaded image(s) do not look like a medical prescription."""


# Signals commonly present on printed/handwritten prescriptions. Each group
# counts at most once so a random document repeating "mg" doesn't pass.
_SIGNAL_GROUPS: list[list[str]] = [
    [r"\brx\b", r"\b℞"],
    [r"\bdr\.?\b", r"\bdoctor\b", r"\bphysician\b", r"\bm\.?b\.?b\.?s\b", r"\bm\.?d\.?\b"],
    [r"\bclinic\b", r"\bhospital\b", r"\bmedical\b", r"\bhealth\s*care\b"],
    [r"\bpatient\b", r"\bname\s*:", r"\bage\b", r"\bsex\b", r"\bgender\b"],
    [r"\bprescription\b", r"\bdiagnosis\b", r"\badvice\b", r"\bcomplaints?\b", r"\breg\.?\s*no\b"],
    [r"\btab\.?\b", r"\btablet\b", r"\bcap\.?\b", r"\bcapsule\b", r"\bsyp\.?\b", r"\bsyrup\b", r"\binj\.?\b", r"\binjection\b"],
    [r"\d+\s*(?:mg|mcg|ml|iu)\b"],
    [r"\bod\b", r"\bbd\b", r"\btds\b", r"\btid\b", r"\bbid\b", r"\bqid\b", r"\bhs\b", r"\b[01]\s*-\s*[01]\s*-\s*[01]\b", r"\bonce\s+(?:a\s+day|daily)\b", r"\btwice\s+(?:a\s+day|daily)\b"],
    [r"\bbefore\s+(?:food|meals?)\b", r"\bafter\s+(?:food|meals?)\b", r"\bdays?\b", r"\bweeks?\b"],
]

# How many distinct signal groups must match for the text to be considered a
# prescription. Tuned to be lenient towards noisy OCR of real prescriptions
# while rejecting unrelated photos/documents.
_MIN_SIGNALS = 3


def ocr_image(image_bytes: bytes) -> str:
    with Image.open(io.BytesIO(image_bytes)) as image:
        gray = image.convert("L")
        # Upscale small photos — tesseract accuracy drops sharply below ~300 DPI.
        if max(gray.size) < 2000:
            scale = 2000 / max(gray.size)
            gray = gray.resize((int(gray.width * scale), int(gray.height * scale)), Image.LANCZOS)
        return pytesseract.image_to_string(gray)


def extract_pdf_texts(pdf_bytes: bytes) -> list[str]:
    """Extract text from every page of a PDF — using the embedded text layer
    when present, falling back to rendering the page and OCRing it."""
    texts: list[str] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            embedded = page.get_text().strip()
            if len(embedded) > 50:
                texts.append(embedded)
                continue
            # Scanned page (no usable text layer) — render at 300 DPI and OCR.
            pixmap = page.get_pixmap(dpi=300)
            texts.append(ocr_image(pixmap.tobytes("png")))
    return texts


def extract_document_texts(content: bytes, content_type: str) -> list[str]:
    if content_type == "application/pdf":
        return extract_pdf_texts(content)
    if content_type.startswith("image/"):
        return [ocr_image(content)]
    return []


def prescription_signal_score(text: str) -> int:
    lowered = text.lower()
    return sum(
        1
        for group in _SIGNAL_GROUPS
        if any(re.search(pattern, lowered) for pattern in group)
    )


def looks_like_prescription(text: str) -> bool:
    return prescription_signal_score(text) >= _MIN_SIGNALS
