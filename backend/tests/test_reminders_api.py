import datetime


def _auth_headers(client, email="reminders-caregiver@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup_patient_with_reminder_today(client, headers, db_session):
    from app.scheduler import materialize_todays_events
    from app.ist_time import to_ist

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

    now = datetime.datetime.utcnow()
    time_str = to_ist(now).strftime("%H:%M")
    all_days = "0,1,2,3,4,5,6"

    client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": time_str, "days_of_week": all_days},
        headers=headers,
    )

    materialize_todays_events(db_session, now)
    return patient_id


def test_todays_reminders_lists_materialized_events(client, db_session):
    headers = _auth_headers(client)
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    response = client.get(f"/api/v1/patients/{patient_id}/reminders/today", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"
    assert response.json()[0]["medicine_name"] == "Metformin"
    assert response.json()[0]["medicine_dose"] == "500mg"


def test_ack_reminder_marks_taken(client, db_session):
    headers = _auth_headers(client)
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    reminders = client.get(f"/api/v1/patients/{patient_id}/reminders/today", headers=headers).json()
    event_id = reminders[0]["id"]

    ack_response = client.post(f"/api/v1/reminders/{event_id}/ack", json={"status": "taken"})

    assert ack_response.status_code == 200
    assert ack_response.json()["status"] == "acknowledged_taken"
    assert ack_response.json()["medicine_name"] == "Metformin"
    assert ack_response.json()["medicine_dose"] == "500mg"


def test_ack_unknown_reminder_returns_404(client):
    response = client.post("/api/v1/reminders/does-not-exist/ack", json={"status": "taken"})
    assert response.status_code == 404


def test_reminders_today_requires_auth(client, db_session):
    headers = _auth_headers(client)
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    response = client.get(f"/api/v1/patients/{patient_id}/reminders/today")
    assert response.status_code == 401


def test_event_stream_rejects_invalid_token(client):
    response = client.get("/api/v1/patients/some-id/events/stream?token=garbage")
    assert response.status_code == 401


def test_patient_can_view_own_todays_reminders(client, db_session):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _auth_headers(client, "patient-view-caregiver@example.com")
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    captured = LoggingOTPProvider()
    original = patients_module.get_otp_provider
    patients_module.get_otp_provider = lambda: captured
    try:
        client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers)
    finally:
        patients_module.get_otp_provider = original

    phone, code = captured.sent[0]
    verify_response = client.post(
        "/api/v1/auth/patient/verify", json={"phone_number": phone, "code": code}
    )
    patient_token = verify_response.json()["access_token"]

    response = client.get(
        f"/api/v1/patients/{patient_id}/reminders/today",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_patient_cannot_view_other_patients_reminders(client, db_session):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _auth_headers(client, "patient-other-caregiver@example.com")
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    other_patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Other Patient", "phone_number": "+15550001111"},
        headers=headers,
    )
    other_patient_id = other_patient_response.json()["id"]

    captured = LoggingOTPProvider()
    original = patients_module.get_otp_provider
    patients_module.get_otp_provider = lambda: captured
    try:
        client.post(f"/api/v1/patients/{other_patient_id}/invite", headers=headers)
    finally:
        patients_module.get_otp_provider = original

    phone, code = captured.sent[0]
    verify_response = client.post(
        "/api/v1/auth/patient/verify", json={"phone_number": phone, "code": code}
    )
    other_patient_token = verify_response.json()["access_token"]

    response = client.get(
        f"/api/v1/patients/{patient_id}/reminders/today",
        headers={"Authorization": f"Bearer {other_patient_token}"},
    )
    assert response.status_code == 404


def test_patient_can_access_reminders_on_date(client, db_session):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _auth_headers(client, "date-patient-caregiver@example.com")
    patient_id = _setup_patient_with_reminder_today(client, headers, db_session)

    captured = LoggingOTPProvider()
    original = patients_module.get_otp_provider
    patients_module.get_otp_provider = lambda: captured
    try:
        client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers)
    finally:
        patients_module.get_otp_provider = original

    phone, code = captured.sent[0]
    verify_response = client.post(
        "/api/v1/auth/patient/verify", json={"phone_number": phone, "code": code}
    )
    patient_token = verify_response.json()["access_token"]

    from app.ist_time import ist_today

    today_str = ist_today(datetime.datetime.utcnow()).isoformat()
    response = client.get(
        f"/api/v1/patients/{patient_id}/reminders?date={today_str}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200


def test_reminders_on_date_finds_event_stored_at_ist_boundary(client, db_session):
    from app.scheduler import materialize_todays_events

    headers = _auth_headers(client, "ist-boundary-caregiver@example.com")

    patient_response = client.post(
        "/api/v1/patients",
        json={"name": "IST Test", "phone_number": "+15559998888"},
        headers=headers,
    )
    patient_id = patient_response.json()["id"]

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    medicine_id = medicine_response.json()["id"]

    # 23:45 IST schedule, materialized at a fake "now" that is the
    # *previous* UTC calendar day but the *current* IST calendar day
    # (2026-07-16 19:00 UTC = 2026-07-17 00:30 IST).
    client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "23:45", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )

    fake_now = datetime.datetime(2026, 7, 16, 19, 0, 0)
    materialize_todays_events(db_session, fake_now)

    response = client.get(
        f"/api/v1/patients/{patient_id}/reminders?date=2026-07-17", headers=headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1

    wrong_day_response = client.get(
        f"/api/v1/patients/{patient_id}/reminders?date=2026-07-16", headers=headers
    )
    assert wrong_day_response.json() == []
