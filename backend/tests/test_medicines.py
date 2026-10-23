def _auth_headers(client, email="med-caregiver@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_patient(client, headers):
    response = client.post(
        "/api/v1/patients",
        json={"name": "Grandma Jones", "phone_number": "+15551234567"},
        headers=headers,
    )
    return response.json()["id"]


def test_create_medicine_and_schedule(client):
    headers = _auth_headers(client)
    patient_id = _create_patient(client, headers)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    assert medicine_response.status_code == 200
    medicine_id = medicine_response.json()["id"]

    schedule_response = client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "08:00", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )
    assert schedule_response.status_code == 200
    assert schedule_response.json()["call_after_minutes"] == 5
    assert schedule_response.json()["escalate_after_minutes"] == 15

    list_response = client.get(f"/api/v1/patients/{patient_id}/medicines", headers=headers)
    assert len(list_response.json()) == 1


def test_cannot_add_medicine_to_other_caregivers_patient(client):
    headers_a = _auth_headers(client, "med-a@example.com")
    headers_b = _auth_headers(client, "med-b@example.com")
    patient_id = _create_patient(client, headers_a)

    response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers_b,
    )
    assert response.status_code == 404


def test_delete_medicine_removes_it_from_list(client):
    headers = _auth_headers(client, "delete-med@example.com")
    patient_id = _create_patient(client, headers)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    medicine_id = medicine_response.json()["id"]

    delete_response = client.delete(f"/api/v1/medicines/{medicine_id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = client.get(f"/api/v1/patients/{patient_id}/medicines", headers=headers)
    assert list_response.json() == []


def test_cannot_delete_other_caregivers_medicine(client):
    headers_a = _auth_headers(client, "delete-a@example.com")
    headers_b = _auth_headers(client, "delete-b@example.com")
    patient_id = _create_patient(client, headers_a)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers_a,
    )
    medicine_id = medicine_response.json()["id"]

    response = client.delete(f"/api/v1/medicines/{medicine_id}", headers=headers_b)
    assert response.status_code == 404


def test_delete_medicine_cancels_in_flight_reminder_and_stops_new_ones(client, db_session):
    import datetime

    from app.models import ReminderEvent, ReminderEventStatus
    from app.scheduler import materialize_todays_events

    headers = _auth_headers(client, "delete-cancel@example.com")
    patient_id = _create_patient(client, headers)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    medicine_id = medicine_response.json()["id"]

    now = datetime.datetime.utcnow()
    time_str = now.strftime("%H:%M")
    client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": time_str, "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )
    materialize_todays_events(db_session, now)

    event = db_session.query(ReminderEvent).first()
    event.status = ReminderEventStatus.alarm_fired
    db_session.add(event)
    db_session.commit()

    delete_response = client.delete(f"/api/v1/medicines/{medicine_id}", headers=headers)
    assert delete_response.status_code == 204

    db_session.refresh(event)
    assert event.status == ReminderEventStatus.cancelled

    # A second materialize pass (e.g. next scheduler tick) must not create a
    # new event for the now-archived medicine's schedule.
    tomorrow = now + datetime.timedelta(days=1)
    materialize_todays_events(db_session, tomorrow)
    assert db_session.query(ReminderEvent).count() == 1


def test_list_schedules_for_medicine(client):
    headers = _auth_headers(client, "list-sched@example.com")
    patient_id = _create_patient(client, headers)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers,
    )
    medicine_id = medicine_response.json()["id"]

    client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "08:00", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )
    client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "20:00", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers,
    )

    response = client.get(f"/api/v1/medicines/{medicine_id}/schedules", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_update_schedule_time_and_days(client):
    headers = _auth_headers(client, "update-sched@example.com")
    patient_id = _create_patient(client, headers)

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

    update_response = client.patch(
        f"/api/v1/schedules/{schedule_id}",
        json={"time_of_day": "09:00", "days_of_week": "0,2,4"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["time_of_day"] == "09:00"
    assert update_response.json()["days_of_week"] == "0,2,4"


def test_delete_schedule_removes_it(client):
    headers = _auth_headers(client, "delete-sched@example.com")
    patient_id = _create_patient(client, headers)

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

    delete_response = client.delete(f"/api/v1/schedules/{schedule_id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = client.get(f"/api/v1/medicines/{medicine_id}/schedules", headers=headers)
    assert list_response.json() == []


def test_cannot_update_other_caregivers_schedule(client):
    headers_a = _auth_headers(client, "sched-owner-a@example.com")
    headers_b = _auth_headers(client, "sched-owner-b@example.com")
    patient_id = _create_patient(client, headers_a)

    medicine_response = client.post(
        f"/api/v1/patients/{patient_id}/medicines",
        json={"name": "Metformin", "dose": "500mg"},
        headers=headers_a,
    )
    medicine_id = medicine_response.json()["id"]

    schedule_response = client.post(
        f"/api/v1/medicines/{medicine_id}/schedules",
        json={"time_of_day": "08:00", "days_of_week": "0,1,2,3,4,5,6"},
        headers=headers_a,
    )
    schedule_id = schedule_response.json()["id"]

    response = client.patch(
        f"/api/v1/schedules/{schedule_id}",
        json={"time_of_day": "09:00"},
        headers=headers_b,
    )
    assert response.status_code == 404
