import datetime

from sqlalchemy.orm import Session

from app.call_provider import CallProvider
from app.events import event_bus
from app.ist_time import ist_date_to_utc_range, ist_today, ist_wall_clock_to_utc
from app.models import (
    Medicine,
    PatientProfile,
    ReminderEvent,
    ReminderEventStatus,
    ReminderSchedule,
)


def materialize_todays_events(db: Session, now: datetime.datetime) -> None:
    today = ist_today(now)
    schedules = (
        db.query(ReminderSchedule)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .filter(Medicine.is_active.is_(True))
        .all()
    )

    for schedule in schedules:
        weekday = today.weekday()
        allowed_days = {int(d) for d in schedule.days_of_week.split(",")}
        if weekday not in allowed_days:
            continue

        hour, minute = (int(part) for part in schedule.time_of_day.split(":"))
        scheduled_at = ist_wall_clock_to_utc(today, hour, minute)

        existing = (
            db.query(ReminderEvent)
            .filter(
                ReminderEvent.reminder_schedule_id == schedule.id,
                ReminderEvent.scheduled_at == scheduled_at,
            )
            .first()
        )
        if existing is not None:
            continue

        event = ReminderEvent(
            reminder_schedule_id=schedule.id,
            scheduled_at=scheduled_at,
            status=ReminderEventStatus.pending,
            status_updated_at=now,
        )
        db.add(event)

    db.commit()


def _patient_id_for_event(db: Session, event: ReminderEvent) -> str:
    return (
        db.query(PatientProfile.id)
        .join(Medicine, Medicine.patient_id == PatientProfile.id)
        .join(ReminderSchedule, ReminderSchedule.medicine_id == Medicine.id)
        .filter(ReminderSchedule.id == event.reminder_schedule_id)
        .scalar()
    )


def advance_reminder_events(
    db: Session, now: datetime.datetime, call_provider: CallProvider
) -> None:
    active_events = (
        db.query(ReminderEvent)
        .join(ReminderSchedule, ReminderEvent.reminder_schedule_id == ReminderSchedule.id)
        .join(Medicine, ReminderSchedule.medicine_id == Medicine.id)
        .filter(
            ReminderEvent.status.in_(
                [
                    ReminderEventStatus.pending,
                    ReminderEventStatus.alarm_fired,
                    ReminderEventStatus.call_placed,
                ]
            ),
            Medicine.is_active.is_(True),
        )
        .all()
    )

    for event in active_events:
        schedule = event.schedule
        elapsed_minutes = (now - event.scheduled_at).total_seconds() / 60

        if event.status == ReminderEventStatus.pending and now >= event.scheduled_at:
            event.status = ReminderEventStatus.alarm_fired
            event.status_updated_at = now
            db.add(event)
            db.flush()
            patient_id = _patient_id_for_event(db, event)
            event_bus.publish(
                patient_id, {"type": "alarm_fired", "reminder_event_id": event.id}
            )

        if (
            event.status == ReminderEventStatus.alarm_fired
            and elapsed_minutes >= schedule.call_after_minutes
        ):
            medicine = schedule.medicine
            call_provider.call(
                medicine.patient.phone_number,
                f"Time to take your {medicine.name}, {medicine.dose}.",
            )
            event.status = ReminderEventStatus.call_placed
            event.status_updated_at = now
            db.add(event)

        if (
            event.status
            in (ReminderEventStatus.alarm_fired, ReminderEventStatus.call_placed)
            and elapsed_minutes >= schedule.escalate_after_minutes
        ):
            event.status = ReminderEventStatus.escalated
            event.status_updated_at = now
            db.add(event)
            db.flush()
            patient_id = _patient_id_for_event(db, event)
            event_bus.publish(
                patient_id, {"type": "escalated", "reminder_event_id": event.id}
            )

    db.commit()


def acknowledge_event(
    db: Session, event_id: str, status: ReminderEventStatus
) -> ReminderEvent:
    if status not in (
        ReminderEventStatus.acknowledged_taken,
        ReminderEventStatus.acknowledged_skipped,
    ):
        raise ValueError(f"Invalid acknowledgment status: {status}")

    event = db.query(ReminderEvent).filter(ReminderEvent.id == event_id).first()
    if event is None:
        raise LookupError(f"ReminderEvent not found: {event_id}")

    event.status = status
    event.status_updated_at = datetime.datetime.utcnow()
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def cancel_events_for_medicine(db: Session, medicine_id: str, now: datetime.datetime) -> None:
    active_events = (
        db.query(ReminderEvent)
        .join(ReminderSchedule, ReminderEvent.reminder_schedule_id == ReminderSchedule.id)
        .filter(
            ReminderSchedule.medicine_id == medicine_id,
            ReminderEvent.status.in_(
                [
                    ReminderEventStatus.pending,
                    ReminderEventStatus.alarm_fired,
                    ReminderEventStatus.call_placed,
                ]
            ),
        )
        .all()
    )

    for event in active_events:
        event.status = ReminderEventStatus.cancelled
        event.status_updated_at = now
        db.add(event)

    db.commit()


def _todays_event_for_schedule(db: Session, schedule_id: str, now: datetime.datetime) -> ReminderEvent | None:
    start, end = ist_date_to_utc_range(ist_today(now))
    return (
        db.query(ReminderEvent)
        .filter(
            ReminderEvent.reminder_schedule_id == schedule_id,
            ReminderEvent.scheduled_at >= start,
            ReminderEvent.scheduled_at <= end,
        )
        .first()
    )


def apply_schedule_edit_side_effects(db: Session, schedule_id: str, now: datetime.datetime) -> None:
    event = _todays_event_for_schedule(db, schedule_id, now)
    if event is None or event.status != ReminderEventStatus.pending:
        return

    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.id == schedule_id).first()
    if schedule is None:
        return

    today = ist_today(now)
    allowed_days = {int(d) for d in schedule.days_of_week.split(",")}
    if today.weekday() not in allowed_days:
        db.delete(event)
        db.commit()
        return

    hour, minute = (int(part) for part in schedule.time_of_day.split(":"))
    event.scheduled_at = ist_wall_clock_to_utc(today, hour, minute)
    db.add(event)
    db.commit()


def apply_schedule_deletion_side_effects(db: Session, schedule_id: str, now: datetime.datetime) -> None:
    event = _todays_event_for_schedule(db, schedule_id, now)
    if event is None or event.status != ReminderEventStatus.pending:
        return

    db.delete(event)
    db.commit()
