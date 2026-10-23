import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_caregiver
from app.db import get_db
from app.models import PatientProfile, User
from app.otp_provider import get_otp_provider
from app.otp_service import generate_otp
from app.schemas import InviteResponse, PatientCreate, PatientResponse

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


@router.get("", response_model=List[PatientResponse])
def list_patients(
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    return (
        db.query(PatientProfile)
        .filter(PatientProfile.caregiver_id == caregiver.id)
        .all()
    )


@router.post("", response_model=PatientResponse)
def create_patient(
    body: PatientCreate,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    patient = PatientProfile(
        caregiver_id=caregiver.id,
        name=body.name,
        phone_number=body.phone_number,
        timezone=body.timezone,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/invite", response_model=InviteResponse)
def invite_patient(
    patient_id: str,
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

    code = generate_otp(db, patient_id, datetime.datetime.utcnow())
    get_otp_provider().send(patient.phone_number, code)

    return InviteResponse()
