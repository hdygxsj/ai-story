from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent.model_runtime import build_chat_model
from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.db.session import get_session
from app.main import app
from app.models import ModelProfile


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "model@example.com", "username": "model", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "model@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_key_encryption_roundtrip() -> None:
    ciphertext = encrypt_api_key("sk-test")

    assert ciphertext != "sk-test"
    assert decrypt_api_key(ciphertext) == "sk-test"


def test_provider_factory_builds_openai_compatible_chat_model() -> None:
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="Compatible",
        provider_kind="openai-compatible",
        base_url="https://llm.example/v1",
        api_key_ciphertext=encrypt_api_key("sk-compatible"),
        chat_model="custom-chat",
        writing_model="custom-writing",
        summary_model="custom-summary",
        embedding_model="custom-embedding",
    )

    model = build_chat_model(profile, purpose="chat")

    assert model.model_name == "custom-chat"
    assert str(model.openai_api_base) == "https://llm.example/v1"


def test_model_profile_route_encrypts_api_key_before_storage() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    created = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "OpenAI",
            "provider_kind": "openai",
            "api_key": "sk-live-secret",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    )

    assert created.status_code == 201
    assert "sk-live-secret" not in created.text


def test_agent_streaming_endpoint_returns_incremental_response() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Streaming Novel"}).json()

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "Help me plan the next scene."},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "data:" in body
    assert "I can help shape the novel" in body
