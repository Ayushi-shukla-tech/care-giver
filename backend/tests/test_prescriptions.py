import datetime

from app.models import Prescription, PrescriptionStatus


def test_prescription_model_defaults(db_session):
    from app.models import PatientProfile, User, UserRole

    caregiver = User(email="model-test@example.com", role=UserRole.caregiver, created_at=datetime.datetime.utcnow())
    db_session.add(caregiver)
    db_session.commit()

    patient = PatientProfile(caregiver_id=caregiver.id, name="Test Patient", phone_number="+15550001111")
    db_session.add(patient)
    db_session.commit()

    prescription = Prescription(
        patient_id=patient.id,
        raw_extraction="[]",
        uploaded_at=datetime.datetime.utcnow(),
    )
    db_session.add(prescription)
    db_session.commit()
    db_session.refresh(prescription)

    assert prescription.status == PrescriptionStatus.pending_review
    assert prescription.raw_extraction == "[]"


def test_prescription_image_model(db_session):
    from app.models import PatientProfile, PrescriptionImage, User, UserRole

    caregiver = User(email="image-model-test@example.com", role=UserRole.caregiver, created_at=datetime.datetime.utcnow())
    db_session.add(caregiver)
    db_session.commit()

    patient = PatientProfile(caregiver_id=caregiver.id, name="Test Patient", phone_number="+15550002222")
    db_session.add(patient)
    db_session.commit()

    prescription = Prescription(
        patient_id=patient.id,
        raw_extraction="[]",
        uploaded_at=datetime.datetime.utcnow(),
    )
    db_session.add(prescription)
    db_session.commit()

    image = PrescriptionImage(prescription_id=prescription.id, file_url="logging://fake/page1.jpg", position=0)
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    assert image.position == 0
    assert image.file_url == "logging://fake/page1.jpg"


def _caregiver_headers(client, email="prescription-caregiver@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "s3cret123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_patient(client, headers, phone="+15551239876"):
    response = client.post(
        "/api/v1/patients", json={"name": "Grandma Jones", "phone_number": phone}, headers=headers
    )
    return response.json()["id"]


def test_upload_prescription_extracts_candidates(client):
    headers = _caregiver_headers(client, "upload-owner@example.com")
    patient_id = _create_patient(client, headers, "+15550010001")

    response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[("files", ("scan.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_review"
    assert len(body["images"]) == 1
    assert body["images"][0]["file_url"].startswith("logging://")
    assert body["images"][0]["position"] == 0
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["name"] == "Metformin"
    assert body["candidates"][0]["status"] == "pending"


def test_upload_prescription_with_multiple_images(client):
    headers = _caregiver_headers(client, "multi-upload-owner@example.com")
    patient_id = _create_patient(client, headers, "+15550010006")

    response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[
            ("files", ("page1.jpg", b"fake-page-1-bytes", "image/jpeg")),
            ("files", ("page2.jpg", b"fake-page-2-bytes", "image/jpeg")),
        ],
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["images"]) == 2
    assert body["images"][0]["position"] == 0
    assert body["images"][1]["position"] == 1
    assert body["images"][0]["file_url"] != body["images"][1]["file_url"]


def test_list_and_get_prescription(client):
    headers = _caregiver_headers(client, "list-owner@example.com")
    patient_id = _create_patient(client, headers, "+15550010002")
    upload_response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[("files", ("scan.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers,
    )
    prescription_id = upload_response.json()["id"]

    list_response = client.get(f"/api/v1/patients/{patient_id}/prescriptions", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(
        f"/api/v1/patients/{patient_id}/prescriptions/{prescription_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == prescription_id


def test_confirm_candidate_updates_status_and_marks_reviewed(client):
    headers = _caregiver_headers(client, "confirm-owner@example.com")
    patient_id = _create_patient(client, headers, "+15550010003")
    upload_response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[("files", ("scan.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers,
    )
    prescription_id = upload_response.json()["id"]

    patch_response = client.patch(
        f"/api/v1/patients/{patient_id}/prescriptions/{prescription_id}/candidates/0",
        json={"status": "confirmed", "name": "Metformin XR", "dose": "750mg"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["candidates"][0]["status"] == "confirmed"
    assert body["candidates"][0]["name"] == "Metformin XR"
    assert body["candidates"][0]["dose"] == "750mg"
    # only candidate, now resolved -> whole prescription flips to reviewed
    assert body["status"] == "reviewed"


def test_skip_candidate_updates_status(client):
    headers = _caregiver_headers(client, "skip-owner@example.com")
    patient_id = _create_patient(client, headers, "+15550010004")
    upload_response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[("files", ("scan.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers,
    )
    prescription_id = upload_response.json()["id"]

    patch_response = client.patch(
        f"/api/v1/patients/{patient_id}/prescriptions/{prescription_id}/candidates/0",
        json={"status": "skipped"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["candidates"][0]["status"] == "skipped"
    assert patch_response.json()["status"] == "reviewed"


def test_cannot_access_other_caregivers_prescriptions(client):
    headers_a = _caregiver_headers(client, "owner-a@example.com")
    headers_b = _caregiver_headers(client, "owner-b@example.com")
    patient_id = _create_patient(client, headers_a, "+15550010005")

    response = client.post(
        f"/api/v1/patients/{patient_id}/prescriptions",
        files=[("files", ("scan.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers_b,
    )
    assert response.status_code == 404
