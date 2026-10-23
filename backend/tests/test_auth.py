def test_signup_then_login(client):
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": "caregiver@example.com", "password": "s3cret123"},
    )
    assert signup_response.status_code == 200
    assert "access_token" in signup_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "caregiver@example.com", "password": "s3cret123"},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


def test_signup_duplicate_email_rejected(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "s3cret123"},
    )
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "different"},
    )
    assert response.status_code == 400


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "wrongpw@example.com", "password": "s3cret123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "nope"},
    )
    assert response.status_code == 401
