from fastapi.testclient import TestClient

from app.agent.model_runtime import build_chat_model
from app.core.crypto import decrypt_api_key, encrypt_api_key
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


def test_provider_factory_uses_purpose_specific_credentials() -> None:
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="Multi Key",
        provider_kind="openai-compatible",
        base_url="https://default.example/v1",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="chat-model",
        chat_base_url="https://chat.example/v1",
        chat_api_key_ciphertext=encrypt_api_key("sk-chat"),
        writing_model="writing-model",
        writing_base_url="https://writing.example/v1",
        writing_api_key_ciphertext=encrypt_api_key("sk-writing"),
        summary_model="summary-model",
        summary_base_url="https://summary.example/v1",
        summary_api_key_ciphertext=encrypt_api_key("sk-summary"),
        embedding_model="embedding-model",
        embedding_base_url="https://embedding.example/v1",
        embedding_api_key_ciphertext=encrypt_api_key("sk-embedding"),
    )

    writing_model = build_chat_model(profile, purpose="writing")
    summary_model = build_chat_model(profile, purpose="summary")

    assert writing_model.model_name == "writing-model"
    assert str(writing_model.openai_api_base) == "https://writing.example/v1"
    assert writing_model.openai_api_key.get_secret_value() == "sk-writing"
    assert summary_model.model_name == "summary-model"
    assert str(summary_model.openai_api_base) == "https://summary.example/v1"
    assert summary_model.openai_api_key.get_secret_value() == "sk-summary"


def test_provider_factory_uses_purpose_specific_provider_kind() -> None:
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="Mixed Provider",
        provider_kind="openai-compatible",
        base_url="https://default.example/v1",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_provider_kind="anthropic",
        chat_model="claude-3-5-sonnet-latest",
        chat_api_key_ciphertext=encrypt_api_key("sk-chat"),
        writing_provider_kind="openai-compatible",
        writing_model="writing-model",
        writing_base_url="https://writing.example/v1",
        writing_api_key_ciphertext=encrypt_api_key("sk-writing"),
        summary_model="summary-model",
        embedding_model="embedding-model",
    )

    chat_model = build_chat_model(profile, purpose="chat")
    writing_model = build_chat_model(profile, purpose="writing")

    assert chat_model.model == "claude-3-5-sonnet-latest"
    assert writing_model.model_name == "writing-model"
    assert str(writing_model.openai_api_base) == "https://writing.example/v1"


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
