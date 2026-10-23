import datetime
import random

from sqlalchemy.orm import Session

from app.models import OtpCode, PatientProfile, User, UserRole


def generate_otp(db: Session, patient_id: str, now: datetime.datetime) -> str:
    patient = db.query(PatientProfile).filter(PatientProfile.id == patient_id).first()
    if patient is None:
        raise LookupError(f"PatientProfile not found: {patient_id}")

    code = f"{random.randint(0, 999999):06d}"
    otp = OtpCode(
        patient_id=patient_id,
        code=code,
        expires_at=now + datetime.timedelta(minutes=10),
        created_at=now,
    )
    db.add(otp)
    db.commit()
    return code


def verify_otp(db: Session, phone_number: str, code: str, now: datetime.datetime) -> User:
    invalid_error = ValueError("Invalid or expired code")

    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.phone_number == phone_number)
        .first()
    )
    if patient is None:
        raise invalid_error

    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.patient_id == patient.id,
            OtpCode.code == code,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if otp is None or otp.expires_at < now:
        raise invalid_error

    otp.consumed_at = now
    db.add(otp)

    user = db.query(User).filter(User.phone_number == phone_number).first()
    if user is None:
        user = User(
            phone_number=phone_number,
            role=UserRole.patient,
            created_at=now,
        )
        db.add(user)
        db.flush()

    if patient.user_id is None:
        patient.user_id = user.id
        db.add(patient)

    db.commit()
    db.refresh(user)
    return user
