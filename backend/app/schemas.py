import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PatientCreate(BaseModel):
    name: str
    phone_number: str
    timezone: str = "UTC"


class PatientResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    timezone: str

    class Config:
        from_attributes = True


class ReminderEventResponse(BaseModel):
    id: str
    reminder_schedule_id: str
    scheduled_at: datetime.datetime
    status: str
    medicine_name: str
    medicine_dose: str

    class Config:
        from_attributes = True


class AckRequest(BaseModel):
    status: Literal["taken", "skipped"]


class MedicineCreate(BaseModel):
    name: str
    dose: str
    instructions: Optional[str] = None


class MedicineResponse(BaseModel):
    id: str
    patient_id: str
    name: str
    dose: str
    instructions: Optional[str]

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    time_of_day: str  # "HH:MM"
    days_of_week: str  # "0,1,2,3,4,5,6"
    call_after_minutes: int = 5
    escalate_after_minutes: int = 15


class ScheduleResponse(BaseModel):
    id: str
    medicine_id: str
    time_of_day: str
    days_of_week: str
    call_after_minutes: int
    escalate_after_minutes: int

    class Config:
        from_attributes = True


class ScheduleUpdate(BaseModel):
    time_of_day: Optional[str] = None
    days_of_week: Optional[str] = None
    call_after_minutes: Optional[int] = None
    escalate_after_minutes: Optional[int] = None


class InviteResponse(BaseModel):
    detail: str = "Invite code sent"


class PatientVerifyRequest(BaseModel):
    phone_number: str
    code: str


class PatientTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient_id: str


class DayAdherence(BaseModel):
    date: str
    status: Literal["all_taken", "some_missed", "escalated"]


class EntryCreate(BaseModel):
    text: str


class EntryResponse(BaseModel):
    id: str
    text: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class MedicalHistoryResponse(BaseModel):
    conditions: list[EntryResponse]
    allergies: list[EntryResponse]
    notes: list[EntryResponse]


class GenerateSuggestionRequest(BaseModel):
    latitude: float
    longitude: float


class DailySuggestionResponse(BaseModel):
    text: str
    greeting: Optional[str] = None
    source: str
    location_label: Optional[str] = None
    weather_summary: Optional[str] = None


class CaregiverNoteRequest(BaseModel):
    text: str


class PrescriptionCandidate(BaseModel):
    name: str
    dose: str
    frequency_hint: str
    status: Literal["pending", "confirmed", "skipped"] = "pending"


class PrescriptionImageResponse(BaseModel):
    id: str
    file_url: str
    position: int


class PrescriptionResponse(BaseModel):
    id: str
    patient_id: str
    images: list[PrescriptionImageResponse]
    status: str
    candidates: list[PrescriptionCandidate]
    uploaded_at: datetime.datetime

    class Config:
        from_attributes = True


class CandidateUpdateRequest(BaseModel):
    status: Literal["confirmed", "skipped"]
    name: Optional[str] = None
    dose: Optional[str] = None
