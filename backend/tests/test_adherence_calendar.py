import datetime

from app.models import ReminderEvent, ReminderEventStatus


def _caregiver_headers(client, email="calendar-caregiver@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_patient_with_medicine(db_session, headers, client):
    patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Grandma Jones", "phone_number": "+15551234567"},
        headers=headers,
    )
    patient_id = patient_response.json()["id"]
    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    medicine_id = medicine_response.json()["id"]
    schedule_response = client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "08:00", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )
    schedule_id = schedule_response.json()["id"]
    return patient_id, schedule_id


def _add_event(db_session, schedule_id, date, status):
    event = ReminderEvent(
        reminder_schedule_id=schedule_id,
        scheduled_at=datetime.datetime.combine(date, datetime.time(8, 0)),
        status=status,
        status_updated_at=datetime.datetime.utcnow(),
    )
    db_session.add(event)
    db_session.commit()


def test_adherence_calendar_aggregates_by_day(client, db_session):
    headers = _caregiver_headers(client)
    patient_id, schedule_id = _make_patient_with_medicine(db_session, headers, client)

    day1 = datetime.date(2026, 7, 1)
    day2 = datetime.date(2026, 7, 2)
    day3 = datetime.date(2026, 7, 3)

    _add_event(db_session, schedule_id, day1, ReminderEventStatus.acknowledged_taken)
    _add_event(db_session, schedule_id, day2, ReminderEventStatus.acknowledged_skipped)
    _add_event(db_session, schedule_id, day3, ReminderEventStatus.escalated)

    response = client.get(f"/api/v1/patients/{patient_id}/adherence/calendar", headers=headers)

    assert response.status_code == 200
    by_date = {entry["date"]: entry["status"] for entry in response.json()}
    assert by_date["2026-07-01"] == "all_taken"
    assert by_date["2026-07-02"] == "some_missed"
    assert by_date["2026-07-03"] == "escalated"


def test_adherence_calendar_omits_dates_with_no_events(client, db_session):
    headers = _caregiver_headers(client)
    patient_id, schedule_id = _make_patient_with_medicine(db_session, headers, client)

    day1 = datetime.date(2026, 7, 1)
    _add_event(db_session, schedule_id, day1, ReminderEventStatus.acknowledged_taken)

    response = client.get(f"/api/v1/patients/{patient_id}/adherence/calendar", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_adherence_calendar_excludes_cancelled_only_day(client, db_session):
    headers = _caregiver_headers(client)
    patient_id, schedule_id = _make_patient_with_medicine(db_session, headers, client)

    day1 = datetime.date(2026, 7, 1)
    day2 = datetime.date(2026, 7, 2)

    _add_event(db_session, schedule_id, day1, ReminderEventStatus.acknowledged_taken)
    _add_event(db_session, schedule_id, day2, ReminderEventStatus.cancelled)

    response = client.get(f"/api/v1/patients/{patient_id}/adherence/calendar", headers=headers)

    assert response.status_code == 200
    by_date = {entry["date"]: entry["status"] for entry in response.json()}
    assert by_date == {"2026-07-01": "all_taken"}
    assert "2026-07-02" not in by_date


def test_adherence_calendar_groups_by_ist_day_not_utc_day(client, db_session):
    headers = _caregiver_headers(client, "ist-calendar-caregiver@example.com")
    patient_id, schedule_id = _make_patient_with_medicine(db_session, headers, client)

    # 19:00 UTC on 2026-07-16 is 00:30 IST on 2026-07-17 — this event should
    # be grouped under 2026-07-17, not 2026-07-16.
    utc_scheduled_at = datetime.datetime(2026, 7, 16, 19, 0, 0)
    event = ReminderEvent(
        reminder_schedule_id=schedule_id,
        scheduled_at=utc_scheduled_at,
        status=ReminderEventStatus.acknowledged_taken,
        status_updated_at=utc_scheduled_at,
    )
    db_session.add(event)
    db_session.commit()

    response = client.get(f"/api/v1/patients/{patient_id}/adherence/calendar", headers=headers)

    assert response.status_code == 200
    by_date = {entry["date"]: entry["status"] for entry in response.json()}
    assert by_date == {"2026-07-17": "all_taken"}


def test_reminders_on_date_returns_that_days_events(client, db_session):
    headers = _caregiver_headers(client)
    patient_id, schedule_id = _make_patient_with_medicine(db_session, headers, client)

    day1 = datetime.date(2026, 7, 1)
    _add_event(db_session, schedule_id, day1, ReminderEventStatus.acknowledged_taken)

    response = client.get(
        f"/api/v1/patients/{patient_id}/reminders?date=2026-07-01", headers=headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "acknowledged_taken"
    assert response.json()[0]["medicine_name"] == "Metformin"
    assert response.json()[0]["medicine_dose"] == "500mg"
