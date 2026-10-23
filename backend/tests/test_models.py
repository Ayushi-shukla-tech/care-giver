import datetime

from app.models import (
    Medicine,
    PatientProfile,
    ReminderEvent,
    ReminderEventStatus,
    ReminderSchedule,
    User,
    UserRole,
)


def test_create_patient_with_medicine_and_schedule(db_session):
    caregiver = User(
        email="caregiver@example.com",
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
        timezone="America/New_York",
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
    )
    db_session.add(schedule)
    db_session.flush()

    event = ReminderEvent(
        reminder_schedule_id=schedule.id,
        scheduled_at=datetime.datetime.utcnow(),
        status=ReminderEventStatus.pending,
        status_updated_at=datetime.datetime.utcnow(),
    )
    db_session.add(event)
    db_session.commit()

    assert db_session.query(ReminderEvent).count() == 1
    assert db_session.query(ReminderEvent).first().status == ReminderEventStatus.pending
    assert schedule.call_after_minutes == 5
    assert schedule.escalate_after_minutes == 15


def test_create_otp_code_for_patient(db_session):
    from app.models import OtpCode

    caregiver = User(
        email="otp-caregiver@example.com",
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

    otp = OtpCode(
        patient_id=patient.id,
        code="123456",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
        created_at=datetime.datetime.utcnow(),
    )
    db_session.add(otp)
    db_session.commit()

    assert db_session.query(OtpCode).count() == 1
    assert db_session.query(OtpCode).first().consumed_at is None


def test_create_condition_allergy_and_note_for_patient(db_session):
    import datetime as dt

    from app.models import Allergy, Condition, Note, PatientProfile, User, UserRole

    caregiver = User(
        email="medhist-caregiver@example.com",
        password_hash="hash",
        role=UserRole.caregiver,
        created_at=dt.datetime.utcnow(),
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

    db_session.add(Condition(patient_id=patient.id, text="Type 2 diabetes", created_at=dt.datetime.utcnow()))
    db_session.add(Allergy(patient_id=patient.id, text="Penicillin", created_at=dt.datetime.utcnow()))
    db_session.add(Note(patient_id=patient.id, text="Prefers morning appointments", created_at=dt.datetime.utcnow()))
    db_session.commit()

    assert db_session.query(Condition).count() == 1
    assert db_session.query(Allergy).count() == 1
    assert db_session.query(Note).count() == 1


def test_create_daily_suggestion_for_patient(db_session):
    import datetime as dt

    from app.models import DailySuggestion, PatientProfile, User, UserRole

    caregiver = User(
        email="dailysugg-caregiver@example.com",
        password_hash="hash",
        role=UserRole.caregiver,
        created_at=dt.datetime.utcnow(),
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

    suggestion = DailySuggestion(
        patient_id=patient.id,
        ist_date="2026-07-17",
        text="It's a sunny day — a short walk could be nice.",
        source="ai",
        location_label="your area",
        weather_summary="30°C, sunny",
        created_at=dt.datetime.utcnow(),
    )
    db_session.add(suggestion)
    db_session.commit()

    assert db_session.query(DailySuggestion).count() == 1
    assert db_session.query(DailySuggestion).first().source == "ai"
