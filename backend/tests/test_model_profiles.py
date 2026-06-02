from fastapi.testclient import TestClient

from app.main import app


def auth_headers(
    client: TestClient,
    *,
    email: str = "model@example.com",
    username: str = "modeluser",
) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": email, "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_openai_compatible_profile() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    create_response = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Local compatible",
            "provider_kind": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "local-key",
            "chat_model": "qwen",
            "writing_model": "qwen",
            "summary_model": "qwen",
            "embedding_model": "text-embedding-3-small",
            "supports_tool_calling": True,
            "supports_json_mode": True,
            "supports_streaming": True,
            "context_window": 32000,
            "embedding_dimensions": 1536,
            "extra_headers": {},
        },
    )
    assert create_response.status_code == 201
    assert "api_key" not in create_response.json()
    list_response = client.get("/model-profiles", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Local compatible"


def test_model_profiles_are_scoped_to_current_user() -> None:
    client = TestClient(app)
    first_headers = auth_headers(client)
    second_headers = auth_headers(
        client,
        email="other-model@example.com",
        username="othermodeluser",
    )

    client.post(
        "/model-profiles",
        headers=first_headers,
        json={
            "name": "Private profile",
            "provider_kind": "openai_compatible",
            "api_key": "local-key",
            "chat_model": "qwen",
            "writing_model": "qwen",
            "summary_model": "qwen",
            "embedding_model": "text-embedding-3-small",
        },
    )

    response = client.get("/model-profiles", headers=second_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_model_profile_defaults_match_agent_capabilities() -> None:
    client = TestClient(app)
    headers = auth_headers(
        client,
        email="defaults@example.com",
        username="defaultsuser",
    )

    response = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Default capabilities",
            "provider_kind": "openai",
            "api_key": "local-key",
            "chat_model": "gpt",
            "writing_model": "gpt",
            "summary_model": "gpt",
            "embedding_model": "text-embedding-3-small",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["supports_tool_calling"] is True
    assert body["supports_json_mode"] is True
    assert body["supports_streaming"] is True
    assert body["context_window"] == 128000
    assert body["embedding_dimensions"] == 1536
