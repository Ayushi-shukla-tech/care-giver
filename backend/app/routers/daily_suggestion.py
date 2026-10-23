import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_caregiver, get_current_patient, get_owned_patient_via_caregiver_or_patient_session
from app.db import get_db
from app.ist_time import ist_today
from app.models import Allergy, Condition, DailySuggestion, PatientProfile, User
from app.schemas import CaregiverNoteRequest, DailySuggestionResponse, GenerateSuggestionRequest
from app.suggestion_provider import get_suggestion_provider
from app.weather_provider import get_weather_provider

router = APIRouter(prefix="/api/v1", tags=["daily-suggestion"])

_DEFAULT_MESSAGE = "Have a wonderful day!"


def _get_existing(db: Session, patient_id: str, ist_date: str) -> DailySuggestion | None:
    return (
        db.query(DailySuggestion)
        .filter(DailySuggestion.patient_id == patient_id, DailySuggestion.ist_date == ist_date)
        .first()
    )


def _to_response(suggestion: DailySuggestion) -> DailySuggestionResponse:
    return DailySuggestionResponse(
        text=suggestion.text,
        greeting=suggestion.greeting,
        source=suggestion.source,
        location_label=suggestion.location_label,
        weather_summary=suggestion.weather_summary,
    )


@router.post(
    "/patients/{patient_id}/daily-suggestion/generate", response_model=DailySuggestionResponse
)
def generate_daily_suggestion(
    patient_id: str,
    body: GenerateSuggestionRequest,
    db: Session = Depends(get_db),
    patient_session=Depends(get_current_patient),
):
    _patient_user, own_patient = patient_session
    if own_patient.id != patient_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    today = ist_today(datetime.datetime.utcnow()).isoformat()

    existing = _get_existing(db, patient_id, today)
    if existing is not None:
        return _to_response(existing)

    weather = get_weather_provider().get_forecast(body.latitude, body.longitude)
    conditions = [c.text for c in db.query(Condition).filter(Condition.patient_id == patient_id).all()]
    allergies = [a.text for a in db.query(Allergy).filter(Allergy.patient_id == patient_id).all()]

    generated = get_suggestion_provider().generate(own_patient.name, weather, conditions, allergies)

    suggestion = DailySuggestion(
        patient_id=patient_id,
        ist_date=today,
        text=generated.suggestion,
        greeting=generated.greeting,
        source="ai",
        location_label=weather.location_label,
        weather_summary=f"{weather.temperature_celsius}°C, {weather.condition}",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return _to_response(suggestion)


@router.get("/patients/{patient_id}/daily-suggestion", response_model=DailySuggestionResponse)
def get_daily_suggestion(
    patient_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    get_owned_patient_via_caregiver_or_patient_session(patient_id, db, authorization)

    today = ist_today(datetime.datetime.utcnow()).isoformat()
    existing = _get_existing(db, patient_id, today)
    if existing is None:
        return DailySuggestionResponse(text=_DEFAULT_MESSAGE, source="default")
    return _to_response(existing)


@router.put("/patients/{patient_id}/daily-suggestion", response_model=DailySuggestionResponse)
def set_caregiver_daily_note(
    patient_id: str,
    body: CaregiverNoteRequest,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == patient_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    today = ist_today(datetime.datetime.utcnow()).isoformat()
    existing = _get_existing(db, patient_id, today)

    if existing is not None:
        existing.text = body.text
        existing.greeting = None
        existing.source = "caregiver"
        existing.location_label = None
        existing.weather_summary = None
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _to_response(existing)

    suggestion = DailySuggestion(
        patient_id=patient_id,
        ist_date=today,
        text=body.text,
        source="caregiver",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return _to_response(suggestion)
