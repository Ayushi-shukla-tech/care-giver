import pytest


def _caregiver_headers(client, email="medhist-caregiver@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_patient(client, headers, phone="+15551234567"):
    response = client.post(
        "/api/v1/patients",
        json={"name": "Grandma Jones", "phone_number": phone},
        headers=headers,
    )
    return response.json()["id"]


@pytest.mark.parametrize("path_segment", ["conditions", "allergies", "notes"])
def test_create_list_and_delete_entry(client, path_segment):
    headers = _caregiver_headers(client, f"{path_segment}-owner@example.com")
    patient_id = _create_patient(client, headers, f"+1555{hash(path_segment) % 10000:04d}")

    create_response = client.post(
        f"/api/v1/patients/{patient_id}/{path_segment}",
        json={"text": "Example entry"},
        headers=headers,
    )
    assert create_response.status_code == 200
    entry_id = create_response.json()["id"]
    assert create_response.json()["text"] == "Example entry"

    list_response = client.get(f"/api/v1/patients/{patient_id}/{path_segment}", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = client.delete(f"/api/v1/{path_segment}/{entry_id}", headers=headers)
    assert delete_response.status_code == 204

    list_after_delete = client.get(f"/api/v1/patients/{patient_id}/{path_segment}", headers=headers)
    assert list_after_delete.json() == []


@pytest.mark.parametrize("path_segment", ["conditions", "allergies", "notes"])
def test_cannot_add_entry_to_other_caregivers_patient(client, path_segment):
    headers_a = _caregiver_headers(client, f"{path_segment}-a@example.com")
    headers_b = _caregiver_headers(client, f"{path_segment}-b@example.com")
    patient_id = _create_patient(client, headers_a, f"+1555{hash(path_segment + 'a') % 10000:04d}")

    response = client.post(
        f"/api/v1/patients/{patient_id}/{path_segment}",
        json={"text": "Example entry"},
        headers=headers_b,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("path_segment", ["conditions", "allergies", "notes"])
def test_cannot_delete_other_caregivers_entry(client, path_segment):
    headers_a = _caregiver_headers(client, f"{path_segment}-del-a@example.com")
    headers_b = _caregiver_headers(client, f"{path_segment}-del-b@example.com")
    patient_id = _create_patient(client, headers_a, f"+1555{hash(path_segment + 'b') % 10000:04d}")

    create_response = client.post(
        f"/api/v1/patients/{patient_id}/{path_segment}",
        json={"text": "Example entry"},
        headers=headers_a,
    )
    entry_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/{path_segment}/{entry_id}", headers=headers_b)
    assert response.status_code == 404


def test_patient_can_view_own_combined_medical_history(client):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _caregiver_headers(client, "medhist-patient-view@example.com")
    patient_id = _create_patient(client, headers, "+15559990001")

    client.post(
        f"/api/v1/patients/{patient_id}/conditions",
        json={"text": "Type 2 diabetes"},
        headers=headers,
    )
    client.post(
        f"/api/v1/patients/{patient_id}/allergies",
        json={"text": "Penicillin"},
        headers=headers,
    )
    client.post(
        f"/api/v1/patients/{patient_id}/notes",
        json={"text": "Prefers morning appointments"},
        headers=headers,
    )

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
        f"/api/v1/patients/{patient_id}/medical-history",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["conditions"]) == 1
    assert body["conditions"][0]["text"] == "Type 2 diabetes"
    assert len(body["allergies"]) == 1
    assert len(body["notes"]) == 1


def test_patient_cannot_view_other_patients_medical_history(client):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _caregiver_headers(client, "medhist-patient-other@example.com")
    patient_id = _create_patient(client, headers, "+15559990002")

    other_patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Other Patient", "phone_number": "+15559990003"},
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
        f"/api/v1/patients/{patient_id}/medical-history",
        headers={"Authorization": f"Bearer {other_patient_token}"},
    )
    assert response.status_code == 404
