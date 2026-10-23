import datetime

from app.call_provider import LoggingCallProvider
from app.models import (
    Medicine,
    PatientProfile,
    ReminderEvent,
    ReminderEventStatus,
    ReminderSchedule,
    User,
    UserRole,
)
from app.scheduler import (
    acknowledge_event,
    advance_reminder_events,
    materialize_todays_events,
)


def _make_schedule(db_session, call_after=5, escalate_after=15):
    caregiver = User(
        email="sched@example.com",
        password_hash="hash",
        role=UserRole.caregiver,
        created_at=datetime.datetime.utcnow(),
    )
    db_session.add(caregiver)
    db_session.flush()

    patient = PatientProfile(
        caregiver_id=caregiver.id,
        name="Grandma Jones",
        phone_number="+15551234567",
        timezone="UTC",
    )
    db_session.add(patient)
    db_session.flush()

    medicine = Medicine(patient_id=patient.id, name="Metformin", dose="500mg")
    db_session.add(medicine)
    db_session.flush()

    schedule = ReminderSchedule(
        medicine_id=medicine.id,
        time_of_day="08:00",
        days_of_week="0,1,2,3,4,5,6",
        call_after_minutes=call_after,
        escalate_after_minutes=escalate_after,
    )
    db_session.add(schedule)
    db_session.commit()
    return schedule, patient


def test_materialize_creates_event_for_todays_schedule(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))

    materialize_todays_events(db_session, now)

    events = db_session.query(ReminderEvent).all()
    assert len(events) == 1
    assert events[0].status == ReminderEventStatus.pending


def test_materialize_is_idempotent(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))

    materialize_todays_events(db_session, now)
    materialize_todays_events(db_session, now)

    assert db_session.query(ReminderEvent).count() == 1


def test_pending_to_alarm_fired_when_time_reached(db_session):
    schedule, _ = _make_schedule(db_session)
    materialize_todays_events(db_session, datetime.datetime.utcnow())
    scheduled_at = db_session.query(ReminderEvent).first().scheduled_at

    advance_reminder_events(db_session, scheduled_at, LoggingCallProvider())

    event = db_session.query(ReminderEvent).first()
    assert event.status == ReminderEventStatus.alarm_fired


def test_alarm_fired_to_call_placed_after_grace_period(db_session):
    schedule, patient = _make_schedule(db_session, call_after=5, escalate_after=15)
    materialize_todays_events(db_session, datetime.datetime.utcnow())
    scheduled_at = db_session.query(ReminderEvent).first().scheduled_at
    advance_reminder_events(db_session, scheduled_at, LoggingCallProvider())

    call_provider = LoggingCallProvider()
    six_minutes_later = scheduled_at + datetime.timedelta(minutes=6)
    advance_reminder_events(db_session, six_minutes_later, call_provider)

    event = db_session.query(ReminderEvent).first()
    assert event.status == ReminderEventStatus.call_placed
    assert call_provider.calls == [(patient.phone_number, "Time to take your Metformin, 500mg.")]


def test_escalates_to_caregiver_after_escalate_grace_period(db_session):
    schedule, _ = _make_schedule(db_session, call_after=5, escalate_after=15)
    scheduled_at = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, scheduled_at)
    advance_reminder_events(db_session, scheduled_at, LoggingCallProvider())

    sixteen_minutes_later = scheduled_at + datetime.timedelta(minutes=16)
    advance_reminder_events(db_session, sixteen_minutes_later, LoggingCallProvider())

    event = db_session.query(ReminderEvent).first()
    assert event.status == ReminderEventStatus.escalated


def test_acknowledgment_short_circuits_escalation(db_session):
    schedule, _ = _make_schedule(db_session, call_after=5, escalate_after=15)
    scheduled_at = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, scheduled_at)
    advance_reminder_events(db_session, scheduled_at, LoggingCallProvider())

    event_id = db_session.query(ReminderEvent).first().id
    acknowledge_event(db_session, event_id, ReminderEventStatus.acknowledged_taken)

    sixteen_minutes_later = scheduled_at + datetime.timedelta(minutes=16)
    advance_reminder_events(db_session, sixteen_minutes_later, LoggingCallProvider())

    event = db_session.query(ReminderEvent).filter(ReminderEvent.id == event_id).first()
    assert event.status == ReminderEventStatus.acknowledged_taken


def test_acknowledge_event_rejects_invalid_status(db_session):
    schedule, _ = _make_schedule(db_session)
    scheduled_at = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, scheduled_at)
    event_id = db_session.query(ReminderEvent).first().id

    import pytest

    with pytest.raises(ValueError):
        acknowledge_event(db_session, event_id, ReminderEventStatus.pending)


def test_apply_schedule_edit_updates_pending_event_time(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.utcnow()
    materialize_todays_events(db_session, now)

    from app.scheduler import apply_schedule_edit_side_effects
    from app.ist_time import ist_wall_clock_to_utc, ist_today

    schedule.time_of_day = "09:30"
    db_session.add(schedule)
    db_session.commit()

    apply_schedule_edit_side_effects(db_session, schedule.id, now)

    event = db_session.query(ReminderEvent).first()
    expected_scheduled_at = ist_wall_clock_to_utc(ist_today(now), 9, 30)
    assert event.scheduled_at == expected_scheduled_at
    assert event.status == ReminderEventStatus.pending


def test_apply_schedule_edit_deletes_pending_event_if_today_removed(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, now)

    from app.scheduler import apply_schedule_edit_side_effects

    today_weekday = datetime.date.today().weekday()
    other_day = (today_weekday + 1) % 7
    schedule.days_of_week = str(other_day)
    db_session.add(schedule)
    db_session.commit()

    apply_schedule_edit_side_effects(db_session, schedule.id, now)

    assert db_session.query(ReminderEvent).count() == 0


def test_apply_schedule_edit_leaves_non_pending_event_untouched(db_session):
    schedule, _ = _make_schedule(db_session)
    materialize_todays_events(db_session, datetime.datetime.utcnow())
    scheduled_at = db_session.query(ReminderEvent).first().scheduled_at
    advance_reminder_events(db_session, scheduled_at, LoggingCallProvider())

    from app.scheduler import apply_schedule_edit_side_effects

    event_before = db_session.query(ReminderEvent).first()
    assert event_before.status == ReminderEventStatus.alarm_fired
    original_scheduled_at = event_before.scheduled_at

    schedule.time_of_day = "23:59"
    db_session.add(schedule)
    db_session.commit()

    apply_schedule_edit_side_effects(db_session, schedule.id, scheduled_at)

    event_after = db_session.query(ReminderEvent).first()
    assert event_after.status == ReminderEventStatus.alarm_fired
    assert event_after.scheduled_at == original_scheduled_at


def test_apply_schedule_deletion_removes_pending_event(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, now)

    from app.scheduler import apply_schedule_deletion_side_effects

    apply_schedule_deletion_side_effects(db_session, schedule.id, now)

    assert db_session.query(ReminderEvent).count() == 0


def test_apply_schedule_deletion_leaves_non_pending_event_untouched(db_session):
    schedule, _ = _make_schedule(db_session)
    now = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 0))
    materialize_todays_events(db_session, now)
    advance_reminder_events(db_session, now, LoggingCallProvider())

    from app.scheduler import apply_schedule_deletion_side_effects

    apply_schedule_deletion_side_effects(db_session, schedule.id, now)

    assert db_session.query(ReminderEvent).count() == 1


def test_materialize_uses_ist_day_not_utc_day_near_boundary(db_session):
    schedule, _ = _make_schedule(db_session)
    schedule.time_of_day = "23:45"
    db_session.add(schedule)
    db_session.commit()

    # 2026-07-16 19:00 UTC = 2026-07-17 00:30 IST — IST day is the 17th,
    # even though UTC day is still the 16th.
    utc_now = datetime.datetime(2026, 7, 16, 19, 0, 0)

    materialize_todays_events(db_session, utc_now)

    event = db_session.query(ReminderEvent).first()
    assert event is not None
    # 23:45 IST on 2026-07-17 is 18:15 UTC on 2026-07-17.
    assert event.scheduled_at == datetime.datetime(2026, 7, 17, 18, 15, 0)
