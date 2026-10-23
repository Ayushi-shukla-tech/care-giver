from app.suggestion_provider import LoggingSuggestionProvider, get_suggestion_provider
from app.weather_provider import LoggingWeatherProvider, WeatherSummary, get_weather_provider


def test_logging_weather_provider_returns_fixed_summary():
    provider = LoggingWeatherProvider()
    summary = provider.get_forecast(19.07, 72.87)
    assert summary.temperature_celsius == 25.0
    assert summary.condition == "clear"
    assert summary.location_label == "your area"
    assert provider.calls == [(19.07, 72.87)]


def test_get_weather_provider_returns_logging_by_default():
    provider = get_weather_provider()
    assert isinstance(provider, LoggingWeatherProvider)


def test_logging_suggestion_provider_returns_fixed_text():
    provider = LoggingSuggestionProvider()
    weather = WeatherSummary(temperature_celsius=30.0, condition="sunny", location_label="your area")
    result = provider.generate("Grandma Jones", weather, ["hypertension"], ["pollen"])
    assert "30.0" in result.suggestion
    assert "Grandma Jones" in result.greeting
    assert len(provider.calls) == 1
    assert provider.calls[0][0] == "Grandma Jones"
    assert provider.calls[0][2] == ["hypertension"]
    assert provider.calls[0][3] == ["pollen"]


def test_get_suggestion_provider_returns_logging_by_default():
    provider = get_suggestion_provider()
    assert isinstance(provider, LoggingSuggestionProvider)


def _caregiver_headers(client, email="dailysugg-caregiver@example.com"):
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


def _pair_patient(client, headers, patient_id, phone):
    from app.otp_provider import LoggingOTPProvider
    import app.routers.patients as patients_module

    captured = LoggingOTPProvider()
    original = patients_module.get_otp_provider
    patients_module.get_otp_provider = lambda: captured
    try:
        client.post(f"/api/v1/patients/{patient_id}/invite", headers=headers)
    finally:
        patients_module.get_otp_provider = original

    _phone, code = captured.sent[0]
    verify_response = client.post(
        "/api/v1/auth/patient/verify", json={"phone_number": phone, "code": code}
    )
    return verify_response.json()["access_token"]


def test_generate_creates_and_caches_suggestion(client):
    headers = _caregiver_headers(client, "gen-caregiver@example.com")
    patient_id = _create_patient(client, headers, "+15559990010")
    patient_token = _pair_patient(client, headers, patient_id, "+15559990010")

    response1 = client.post(
        f"/api/v1/patients/{patient_id}/daily-suggestion/generate",
        json={"latitude": 19.07, "longitude": 72.87},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response1.status_code == 200
    assert response1.json()["source"] == "ai"
    first_text = response1.json()["text"]

    response2 = client.post(
        f"/api/v1/patients/{patient_id}/daily-suggestion/generate",
        json={"latitude": 19.07, "longitude": 72.87},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response2.status_code == 200
    assert response2.json()["text"] == first_text


def test_get_daily_suggestion_returns_default_when_none_exists(client):
    headers = _caregiver_headers(client, "default-caregiver@example.com")
    patient_id = _create_patient(client, headers, "+15559990011")

    response = client.get(f"/api/v1/patients/{patient_id}/daily-suggestion", headers=headers)
    assert response.status_code == 200
    assert response.json()["source"] == "default"
    assert response.json()["text"] == "Have a wonderful day!"


def test_caregiver_can_set_note_and_it_is_visible_to_patient(client):
    headers = _caregiver_headers(client, "note-caregiver@example.com")
    patient_id = _create_patient(client, headers, "+15559990012")
    patient_token = _pair_patient(client, headers, patient_id, "+15559990012")

    put_response = client.put(
        f"/api/v1/patients/{patient_id}/daily-suggestion",
        json={"text": "Grandma, let's have a quiet day indoors today."},
        headers=headers,
    )
    assert put_response.status_code == 200
    assert put_response.json()["source"] == "caregiver"

    get_response = client.get(
        f"/api/v1/patients/{patient_id}/daily-suggestion",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert get_response.json()["text"] == "Grandma, let's have a quiet day indoors today."
    assert get_response.json()["source"] == "caregiver"


def test_generate_does_not_overwrite_caregiver_note(client):
    headers = _caregiver_headers(client, "no-overwrite-caregiver@example.com")
    patient_id = _create_patient(client, headers, "+15559990013")
    patient_token = _pair_patient(client, headers, patient_id, "+15559990013")

    client.put(
        f"/api/v1/patients/{patient_id}/daily-suggestion",
        json={"text": "Caregiver's note for today."},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/patients/{patient_id}/daily-suggestion/generate",
        json={"latitude": 19.07, "longitude": 72.87},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "Caregiver's note for today."
    assert response.json()["source"] == "caregiver"


def test_generate_rejects_other_patients_session(client):
    headers = _caregiver_headers(client, "cross-patient-caregiver@example.com")
    patient_a_id = _create_patient(client, headers, "+15559990014")
    patient_b_id = _create_patient(client, headers, "+15559990015")
    patient_a_token = _pair_patient(client, headers, patient_a_id, "+15559990014")

    response = client.post(
        f"/api/v1/patients/{patient_b_id}/daily-suggestion/generate",
        json={"latitude": 19.07, "longitude": 72.87},
        headers={"Authorization": f"Bearer {patient_a_token}"},
    )
    assert response.status_code == 404
