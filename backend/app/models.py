import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    patient = "patient"
    caregiver = "caregiver"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    google_sub = Column(String, unique=True, nullable=True, index=True)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, nullable=False)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    caregiver_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")

    medicines = relationship("Medicine", back_populates="patient")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    name = Column(String, nullable=False)
    dose = Column(String, nullable=False)
    instructions = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    patient = relationship("PatientProfile", back_populates="medicines")
    schedules = relationship("ReminderSchedule", back_populates="medicine")


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id = Column(String, primary_key=True, default=_uuid)
    medicine_id = Column(String, ForeignKey("medicines.id"), nullable=False)
    time_of_day = Column(String, nullable=False)  # "HH:MM", 24h, patient-local
    days_of_week = Column(String, nullable=False)  # comma-separated ints, 0=Mon
    call_after_minutes = Column(Integer, nullable=False, default=5)
    escalate_after_minutes = Column(Integer, nullable=False, default=15)

    medicine = relationship("Medicine", back_populates="schedules")
    events = relationship("ReminderEvent", back_populates="schedule")


class ReminderEventStatus(str, enum.Enum):
    pending = "pending"
    alarm_fired = "alarm_fired"
    call_placed = "call_placed"
    acknowledged_taken = "acknowledged_taken"
    acknowledged_skipped = "acknowledged_skipped"
    escalated = "escalated"
    cancelled = "cancelled"


class ReminderEvent(Base):
    __tablename__ = "reminder_events"

    id = Column(String, primary_key=True, default=_uuid)
    reminder_schedule_id = Column(String, ForeignKey("reminder_schedules.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)  # UTC
    status = Column(Enum(ReminderEventStatus), nullable=False, default=ReminderEventStatus.pending)
    status_updated_at = Column(DateTime, nullable=False)

    schedule = relationship("ReminderSchedule", back_populates="events")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


class Condition(Base):
    __tablename__ = "conditions"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class Allergy(Base):
    __tablename__ = "allergies"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class DailySuggestion(Base):
    __tablename__ = "daily_suggestions"
    __table_args__ = (UniqueConstraint("patient_id", "ist_date", name="uq_daily_suggestion_patient_date"),)

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    ist_date = Column(String, nullable=False)
    text = Column(String, nullable=False)
    greeting = Column(String, nullable=True)
    source = Column(String, nullable=False)
    location_label = Column(String, nullable=True)
    weather_summary = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)


class PrescriptionStatus(str, enum.Enum):
    pending_review = "pending_review"
    reviewed = "reviewed"


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String, primary_key=True, default=_uuid)
    patient_id = Column(String, ForeignKey("patient_profiles.id"), nullable=False)
    status = Column(Enum(PrescriptionStatus), nullable=False, default=PrescriptionStatus.pending_review)
    raw_extraction = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False)


class PrescriptionImage(Base):
    __tablename__ = "prescription_images"

    id = Column(String, primary_key=True, default=_uuid)
    prescription_id = Column(String, ForeignKey("prescriptions.id"), nullable=False)
    file_url = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
