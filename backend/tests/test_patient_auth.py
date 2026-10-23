import datetime

from app.models import PatientProfile, User, UserRole
from app.otp_service import generate_otp, verify_otp


def _make_patient(db_session):
    caregiver = User(
        email="pairing-caregiver@example.com",
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
    db_session.commit()
    return patient


def test_generate_then_verify_otp_creates_patient_user(db_session):
    patient = _make_patient(db_session)
    now = datetime.datetime.utcnow()

    code = generate_otp(db_session, patient.id, now)
    assert len(code) == 6

    user = verify_otp(db_session, patient.phone_number, code, now)

    assert user.role == UserRole.patient
    assert user.phone_number == patient.phone_number

    db_session.refresh(patient)
    assert patient.user_id == user.id


def test_verify_otp_rejects_wrong_code(db_session):
    patient = _make_patient(db_session)
    now = datetime.datetime.utcnow()
    generate_otp(db_session, patient.id, now)

    import pytest

    with pytest.raises(ValueError):
        verify_otp(db_session, patient.phone_number, "000000", now)


def test_verify_otp_rejects_expired_code(db_session):
    patient = _make_patient(db_session)
    now = datetime.datetime.utcnow()
    code = generate_otp(db_session, patient.id, now)

    eleven_minutes_later = now + datetime.timedelta(minutes=11)

    import pytest

    with pytest.raises(ValueError):
        verify_otp(db_session, patient.phone_number, code, eleven_minutes_later)


def test_verify_otp_rejects_already_consumed_code(db_session):
    patient = _make_patient(db_session)
    now = datetime.datetime.utcnow()
    code = generate_otp(db_session, patient.id, now)

    verify_otp(db_session, patient.phone_number, code, now)

    import pytest

    with pytest.raises(ValueError):
        verify_otp(db_session, patient.phone_number, code, now)


def test_verify_otp_reuses_existing_user_on_second_pairing(db_session):
    patient = _make_patient(db_session)
    now = datetime.datetime.utcnow()

    code1 = generate_otp(db_session, patient.id, now)
    user1 = verify_otp(db_session, patient.phone_number, code1, now)

    code2 = generate_otp(db_session, patient.id, now)
    user2 = verify_otp(db_session, patient.phone_number, code2, now)

    assert user1.id == user2.id


def _caregiver_headers(client, email="invite-caregiver@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_invite_and_verify_full_flow(client):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    headers = _caregiver_headers(client)
    patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Grandma Jones", "phone_number": "+15559998888"},
        headers=headers,
    )
    patient_id = patient_response.json()["id"]

    captured = LoggingOTPProvider()
    original_get_provider = patients_module.get_otp_provider
    patients_module.get_otp_provider = lambda: captured
    try:
        invite_response = client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers)
    finally:
        patients_module.get_otp_provider = original_get_provider

    assert invite_response.status_code == 200
    assert len(captured.sent) == 1
    sent_phone, sent_code = captured.sent[0]
    assert sent_phone == "+15559998888"

    verify_response = client.post(
        "/api/v1/auth/patient/verify",
        json={"phone_number": "+15559998888", "code": sent_code},
    )
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
    assert "patient_id" in verify_response.json()
    assert verify_response.json()["patient_id"] == patient_id


def test_verify_with_wrong_code_returns_401(client):
    headers = _caregiver_headers(client, "invite-b@example.com")
    patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Someone", "phone_number": "+15557776666"},
        headers=headers,
    )
    patient_id = patient_response.json()["id"]
    client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers)

    response = client.post(
        "/api/v1/auth/patient/verify",
        json={"phone_number": "+15557776666", "code": "000000"},
    )
    assert response.status_code == 401


def test_invite_requires_caregiver_ownership(client):
    headers_a = _caregiver_headers(client, "owner-a@example.com")
    headers_b = _caregiver_headers(client, "owner-b@example.com")
    patient_response = client.post(
        "/api/v1/patients",
        json={"name": "Owned By A", "phone_number": "+15551112222"},
        headers=headers_a,
    )
    patient_id = patient_response.json()["id"]

    response = client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers_b)
    assert response.status_code == 404
