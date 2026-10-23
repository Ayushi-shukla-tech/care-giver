import app.routers.auth as auth_module


def _fake_verify(claims):
    def _verify(token, request, audience):
        if token == "invalid-token":
            raise ValueError("invalid token")
        return claims

    return _verify


def _patch_verify(claims):
    original = auth_module.id_token.verify_oauth2_token
    auth_module.id_token.verify_oauth2_token = _fake_verify(claims)
    return original


def _restore_verify(original):
    auth_module.id_token.verify_oauth2_token = original


def test_google_signin_creates_new_caregiver(client):
    original = _patch_verify(
        {"sub": "google-sub-1", "email": "newgoogleuser@example.com", "name": "New User"}
    )
    try:
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-valid-token"})
    finally:
        _restore_verify(original)

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_google_signin_links_existing_password_account(client):
    signup_response = client.post(
        "/api/v1/auth/signup", json={"email": "existing-caregiver@example.com", "password": "s3cret123"}
    )
    assert signup_response.status_code == 200

    original = _patch_verify(
        {"sub": "google-sub-2", "email": "existing-caregiver@example.com", "name": "Existing User"}
    )
    try:
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-valid-token"})
    finally:
        _restore_verify(original)

    assert response.status_code == 200

    # existing password login must still work after linking
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "existing-caregiver@example.com", "password": "s3cret123"}
    )
    assert login_response.status_code == 200


def test_google_signin_returning_user_logs_in_by_google_sub(client):
    original = _patch_verify(
        {"sub": "google-sub-3", "email": "returning@example.com", "name": "Returning User"}
    )
    try:
        first_response = client.post("/api/v1/auth/google", json={"id_token": "fake-valid-token"})
        assert first_response.status_code == 200

        second_response = client.post("/api/v1/auth/google", json={"id_token": "fake-valid-token"})
        assert second_response.status_code == 200
    finally:
        _restore_verify(original)


def test_google_signin_rejects_invalid_token(client):
    original = _patch_verify({"sub": "unused", "email": "unused@example.com", "name": "Unused"})
    try:
        response = client.post("/api/v1/auth/google", json={"id_token": "invalid-token"})
    finally:
        _restore_verify(original)

    assert response.status_code == 401
