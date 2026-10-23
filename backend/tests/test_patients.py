def _signup_and_auth_headers(client, email="caregiver2@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "s3cret123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_patients(client):
    headers = _signup_and_auth_headers(client)

    create_response = client.post(
        "/api/v1/patients",
        json={"name": "Grandma Jones", "phone_number": "+15551234567", "timezone": "America/New_York"},
        headers=headers,
    )
    assert create_response.status_code == 200
    assert create_response.json()["name"] == "Grandma Jones"

    list_response = client.get("/api/v1/patients", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_patients_scoped_to_caregiver(client):
    headers_a = _signup_and_auth_headers(client, "caregiver-a@example.com")
    headers_b = _signup_and_auth_headers(client, "caregiver-b@example.com")

    client.post(
        "/api/v1/patients",
        json={"name": "Patient A", "phone_number": "+15550000001"},
        headers=headers_a,
    )

    response_b = client.get("/api/v1/patients", headers=headers_b)
    assert response_b.json() == []


def test_create_patient_requires_auth(client):
    response = client.post(
        "/api/v1/patients", json={"name": "No Auth", "phone_number": "+15550000000"}
    )
    assert response.status_code == 401
