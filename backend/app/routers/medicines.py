import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_caregiver
from app.db import get_db
from app.models import Medicine, PatientProfile, ReminderSchedule, User
from app.scheduler import (
    apply_schedule_deletion_side_effects,
    apply_schedule_edit_side_effects,
    cancel_events_for_medicine,
)
from app.schemas import (
    MedicineCreate,
    MedicineResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["medicines"])


def _get_owned_patient(db: Session, patient_id: str, caregiver: User) -> PatientProfile:
    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == patient_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _get_owned_medicine(db: Session, medicine_id: str, caregiver: User) -> Medicine:
    medicine = (
        db.query(Medicine)
        .join(PatientProfile, Medicine.patient_id == PatientProfile.id)
        .filter(Medicine.id == medicine_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


def _get_owned_schedule(db: Session, schedule_id: str, caregiver: User) -> ReminderSchedule:
    schedule = (
        db.query(ReminderSchedule)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .join(PatientProfile, Medicine.patient_id == PatientProfile.id)
        .filter(ReminderSchedule.id == schedule_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.get("/patients/{patient_id}/medicines", response_model=List[MedicineResponse])
def list_medicines(
    patient_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_patient(db, patient_id, caregiver)
    return (
        db.query(Medicine)
        .filter(Medicine.patient_id == patient_id, Medicine.is_active.is_(True))
        .all()
    )


@router.post("/patients/{patient_id}/medicines", response_model=MedicineResponse)
def create_medicine(
    patient_id: str,
    body: MedicineCreate,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_patient(db, patient_id, caregiver)
    medicine = Medicine(patient_id=patient_id, name=body.name, dose=body.dose, instructions=body.instructions)
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    return medicine


@router.delete("/medicines/{medicine_id}", status_code=204)
def delete_medicine(
    medicine_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    medicine = _get_owned_medicine(db, medicine_id, caregiver)
    medicine.is_active = False
    db.add(medicine)
    db.commit()

    cancel_events_for_medicine(db, medicine_id, datetime.datetime.utcnow())


@router.post("/medicines/{medicine_id}/schedules", response_model=ScheduleResponse)
def create_schedule(
    medicine_id: str,
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_medicine(db, medicine_id, caregiver)
    schedule = ReminderSchedule(
        medicine_id=medicine_id,
        time_of_day=body.time_of_day,
        days_of_week=body.days_of_week,
        call_after_minutes=body.call_after_minutes,
        escalate_after_minutes=body.escalate_after_minutes,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/medicines/{medicine_id}/schedules", response_model=List[ScheduleResponse])
def list_schedules(
    medicine_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_medicine(db, medicine_id, caregiver)
    return db.query(ReminderSchedule).filter(ReminderSchedule.medicine_id == medicine_id).all()


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    schedule = _get_owned_schedule(db, schedule_id, caregiver)

    if body.time_of_day is not None:
        schedule.time_of_day = body.time_of_day
    if body.days_of_week is not None:
        schedule.days_of_week = body.days_of_week
    if body.call_after_minutes is not None:
        schedule.call_after_minutes = body.call_after_minutes
    if body.escalate_after_minutes is not None:
        schedule.escalate_after_minutes = body.escalate_after_minutes

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    apply_schedule_edit_side_effects(db, schedule_id, datetime.datetime.utcnow())

    return schedule


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    schedule = _get_owned_schedule(db, schedule_id, caregiver)

    apply_schedule_deletion_side_effects(db, schedule_id, datetime.datetime.utcnow())

    db.delete(schedule)
    db.commit()
