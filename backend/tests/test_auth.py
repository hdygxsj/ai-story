from fastapi.testclient import TestClient

from app.main import app


def test_register_and_login_user() -> None:
    client = TestClient(app)

    register_response = client.post(
        "/auth/register",
        json={"email": "writer@example.com", "username": "writer", "password": "secret123"},
    )

    assert register_response.status_code == 201
    assert register_response.json()["email"] == "writer@example.com"

    login_response = client.post(
        "/auth/login",
        json={"login": "writer@example.com", "password": "secret123"},
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)


def test_register_rejects_duplicate_email_or_username() -> None:
    client = TestClient(app)

    first_response = client.post(
        "/auth/register",
        json={"email": "dupe@example.com", "username": "dupe", "password": "secret123"},
    )
    duplicate_email_response = client.post(
        "/auth/register",
        json={"email": "dupe@example.com", "username": "other", "password": "secret123"},
    )
    duplicate_username_response = client.post(
        "/auth/register",
        json={"email": "other@example.com", "username": "dupe", "password": "secret123"},
    )

    assert first_response.status_code == 201
    assert duplicate_email_response.status_code == 409
    assert duplicate_username_response.status_code == 409


def test_login_accepts_username_and_rejects_invalid_credentials() -> None:
    client = TestClient(app)

    client.post(
        "/auth/register",
        json={"email": "username@example.com", "username": "username-login", "password": "secret123"},
    )

    username_login_response = client.post(
        "/auth/login",
        json={"login": "username-login", "password": "secret123"},
    )
    invalid_password_response = client.post(
        "/auth/login",
        json={"login": "username-login", "password": "wrong-password"},
    )
    missing_user_response = client.post(
        "/auth/login",
        json={"login": "missing@example.com", "password": "secret123"},
    )

    assert username_login_response.status_code == 200
    assert username_login_response.json()["token_type"] == "bearer"
    assert invalid_password_response.status_code == 401
    assert missing_user_response.status_code == 401


def test_me_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_with_valid_token_returns_current_user() -> None:
    client = TestClient(app)

    client.post(
        "/auth/register",
        json={"email": "me@example.com", "username": "me-user", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "me@example.com", "password": "secret123"},
    ).json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
