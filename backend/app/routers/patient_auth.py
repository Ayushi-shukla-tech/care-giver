import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_patient_access_token
from app.db import get_db
from app.models import PatientProfile
from app.otp_service import verify_otp
from app.schemas import PatientTokenResponse, PatientVerifyRequest

router = APIRouter(prefix="/api/v1/auth/patient", tags=["patient-auth"])


@router.post("/verify", response_model=PatientTokenResponse)
def verify(body: PatientVerifyRequest, db: Session = Depends(get_db)):
    try:
        user = verify_otp(db, body.phone_number, body.code, datetime.datetime.utcnow())
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    patient = db.query(PatientProfile).filter(PatientProfile.user_id == user.id).first()

    return PatientTokenResponse(
        access_token=create_patient_access_token(user.id),
        patient_id=patient.id,
    )
