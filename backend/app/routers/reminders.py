import asyncio
import datetime
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.auth import (
    get_current_caregiver,
    get_current_caregiver_from_token,
    get_owned_patient_via_caregiver_or_patient_session,
)
from app.db import get_db
from app.events import event_bus
from app.ist_time import ist_date_to_utc_range, ist_today, to_ist
from app.models import (
    Medicine,
    PatientProfile,
    ReminderEvent,
    ReminderEventStatus,
    ReminderSchedule,
    User,
)
from app.scheduler import acknowledge_event
from app.schemas import AckRequest, DayAdherence, ReminderEventResponse

router = APIRouter(prefix="/api/v1", tags=["reminders"])

_ACK_STATUS_MAP = {
    "taken": ReminderEventStatus.acknowledged_taken,
    "skipped": ReminderEventStatus.acknowledged_skipped,
}


def _to_reminder_response(event: ReminderEvent) -> ReminderEventResponse:
    return ReminderEventResponse(
        id=event.id,
        reminder_schedule_id=event.reminder_schedule_id,
        scheduled_at=event.scheduled_at,
        status=event.status.value,
        medicine_name=event.schedule.medicine.name,
        medicine_dose=event.schedule.medicine.dose,
    )


@router.get("/patients/{patient_id}/reminders/today", response_model=list[ReminderEventResponse])
def todays_reminders(
    patient_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    get_owned_patient_via_caregiver_or_patient_session(patient_id, db, authorization)

    start, end = ist_date_to_utc_range(ist_today(datetime.datetime.utcnow()))

    events = (
        db.query(ReminderEvent)
        .join(ReminderSchedule, ReminderEvent.reminder_schedule_id == ReminderSchedule.id)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .filter(
            Medicine.patient_id == patient_id,
            ReminderEvent.scheduled_at >= start,
            ReminderEvent.scheduled_at <= end,
        )
        .all()
    )
    return [_to_reminder_response(e) for e in events]


@router.get("/patients/{patient_id}/reminders", response_model=list[ReminderEventResponse])
def reminders_on_date(
    patient_id: str,
    date: str = Query(...),
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    get_owned_patient_via_caregiver_or_patient_session(patient_id, db, authorization)

    target_date = datetime.date.fromisoformat(date)
    start, end = ist_date_to_utc_range(target_date)

    events = (
        db.query(ReminderEvent)
        .join(ReminderSchedule, ReminderEvent.reminder_schedule_id == ReminderSchedule.id)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .filter(
            Medicine.patient_id == patient_id,
            ReminderEvent.scheduled_at >= start,
            ReminderEvent.scheduled_at <= end,
        )
        .all()
    )
    return [_to_reminder_response(e) for e in events]


@router.get("/patients/{patient_id}/adherence/calendar", response_model=list[DayAdherence])
def adherence_calendar(
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

    events = (
        db.query(ReminderEvent)
        .join(ReminderSchedule, ReminderEvent.reminder_schedule_id == ReminderSchedule.id)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .filter(Medicine.patient_id == patient_id)
        .all()
    )

    by_date: dict[str, list[ReminderEvent]] = defaultdict(list)
    for event in events:
        by_date[to_ist(event.scheduled_at).date().isoformat()].append(event)

    result = []
    for date_str, all_day_events in sorted(by_date.items()):
        day_events = [e for e in all_day_events if e.status != ReminderEventStatus.cancelled]
        if not day_events:
            continue
        if any(e.status == ReminderEventStatus.escalated for e in day_events):
            status_value = "escalated"
        elif all(e.status == ReminderEventStatus.acknowledged_taken for e in day_events):
            status_value = "all_taken"
        else:
            status_value = "some_missed"
        result.append(DayAdherence(date=date_str, status=status_value))

    return result


@router.post("/reminders/{event_id}/ack", response_model=ReminderEventResponse)
def ack_reminder(event_id: str, body: AckRequest, db: Session = Depends(get_db)):
    try:
        event = acknowledge_event(db, event_id, _ACK_STATUS_MAP[body.status])
    except LookupError:
        raise HTTPException(status_code=404, detail="Reminder event not found")
    return _to_reminder_response(event)


@router.get("/patients/{patient_id}/events/stream")
async def event_stream(
    patient_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    caregiver = get_current_caregiver_from_token(token, db)
    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == patient_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    queue = event_bus.subscribe(patient_id)

    async def generator():
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(patient_id, queue)

    return StreamingResponse(generator(), media_type="text/event-stream")
