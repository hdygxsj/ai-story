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


def test_create_profile_accepts_purpose_specific_providers() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="purpose-provider@example.com", username="purposeprovider")
    create_response = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Mixed providers",
            "provider_kind": "openai-compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "default-key",
            "chat_provider_kind": "anthropic",
            "chat_model": "claude-3-5-sonnet-latest",
            "chat_api_key": "chat-key",
            "writing_provider_kind": "openai-compatible",
            "writing_model": "qwen-writing",
            "writing_api_key": "writing-key",
            "summary_provider_kind": "openai",
            "summary_model": "gpt-4o-mini",
            "embedding_provider_kind": "openai-compatible",
            "embedding_model": "embedding-model",
        },
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["chat_provider_kind"] == "anthropic"
    assert body["writing_provider_kind"] == "openai-compatible"
    assert body["summary_provider_kind"] == "openai"
    assert body["embedding_provider_kind"] == "openai-compatible"


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


def test_test_connectivity_returns_results(monkeypatch) -> None:
    from app.services import model_profile_connectivity

    async def fake_run_tests(profile, *, purposes=None) -> list[model_profile_connectivity.ConnectivityResult]:
        return [
            model_profile_connectivity.ConnectivityResult(
                purpose="chat",
                ok=True,
                message="连通正常",
                model=profile.chat_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="writing",
                ok=False,
                message="timeout",
                model=profile.writing_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="summary",
                ok=True,
                message="连通正常",
                model=profile.summary_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="embedding",
                ok=True,
                message="连通正常，向量维度 3",
                model=profile.embedding_model,
            ),
        ]

    monkeypatch.setattr(
        "app.api.routes.model_profiles.run_model_profile_connectivity_tests",
        fake_run_tests,
    )

    client = TestClient(app)
    headers = auth_headers(client, email="connectivity@example.com", username="connectivityuser")
    response = client.post(
        "/model-profiles/test-connectivity",
        headers=headers,
        json={
            "name": "测试配置",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 4
    assert body["results"][0] == {
        "purpose": "chat",
        "label": "对话",
        "ok": True,
        "message": "连通正常",
        "model": "gpt-4o",
    }
    assert body["results"][1]["ok"] is False
    assert body["results"][1]["label"] == "写作"


def test_test_connectivity_uses_stored_api_key_when_editing(monkeypatch) -> None:
    from app.services import model_profile_connectivity

    captured: dict[str, object] = {}

    async def fake_run_tests(profile, *, purposes=None) -> list[model_profile_connectivity.ConnectivityResult]:
        captured["profile"] = profile
        return [
            model_profile_connectivity.ConnectivityResult(
                purpose="chat",
                ok=True,
                message="连通正常",
                model=profile.chat_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="writing",
                ok=True,
                message="连通正常",
                model=profile.writing_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="summary",
                ok=True,
                message="连通正常",
                model=profile.summary_model,
            ),
            model_profile_connectivity.ConnectivityResult(
                purpose="embedding",
                ok=True,
                message="连通正常，向量维度 3",
                model=profile.embedding_model,
            ),
        ]

    monkeypatch.setattr(
        "app.api.routes.model_profiles.run_model_profile_connectivity_tests",
        fake_run_tests,
    )

    client = TestClient(app)
    headers = auth_headers(client, email="stored-key@example.com", username="storedkeyuser")
    created = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "默认 OpenAI",
            "provider_kind": "openai",
            "api_key": "sk-stored",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    ).json()

    response = client.post(
        "/model-profiles/test-connectivity",
        headers=headers,
        json={
            "profile_id": created["id"],
            "name": "默认 OpenAI",
            "provider_kind": "openai",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    )

    assert response.status_code == 200
    profile = captured["profile"]
    from app.core.crypto import decrypt_api_key

    assert decrypt_api_key(profile.api_key_ciphertext) == "sk-stored"


def test_test_connectivity_requires_api_key_for_new_profile() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="missing-key@example.com", username="missingkeyuser")

    response = client.post(
        "/model-profiles/test-connectivity",
        headers=headers,
        json={
            "name": "测试配置",
            "provider_kind": "openai",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    )

    assert response.status_code == 400
    assert "API Key" in response.json()["detail"]


def test_update_model_profile_changes_models_without_requiring_api_key() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="update@example.com", username="updateuser")
    created = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "默认 OpenAI",
            "provider_kind": "openai",
            "api_key": "default-key",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        },
    ).json()

    response = client.patch(
        f"/model-profiles/{created['id']}",
        headers=headers,
        json={
            "name": "更新后的配置",
            "embedding_provider_kind": "ollama",
            "embedding_model": "nomic-embed-text",
            "embedding_base_url": "http://ollama:11434",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "更新后的配置"
    assert body["embedding_provider_kind"] == "ollama"
    assert body["embedding_model"] == "nomic-embed-text"
    assert body["chat_model"] == "gpt-4o"


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


def test_create_profile_without_embedding_model() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="no-embed@example.com", username="noembeduser")
    response = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Chat only",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 201
    assert response.json()["embedding_model"] == ""


def test_test_connectivity_filters_by_purpose(monkeypatch) -> None:
    from app.services import model_profile_connectivity

    calls: list[str] = []

    async def fake_chat_purpose(profile, purpose):
        calls.append(purpose)
        return model_profile_connectivity.ConnectivityResult(
            purpose=purpose,
            ok=True,
            message="连通正常",
            model=getattr(profile, f"{purpose}_model"),
        )

    monkeypatch.setattr(model_profile_connectivity, "_test_chat_purpose", fake_chat_purpose)
    monkeypatch.setattr(
        model_profile_connectivity,
        "_test_embedding_purpose",
        lambda profile: (_ for _ in ()).throw(AssertionError("embedding test should not run")),
    )

    client = TestClient(app)
    headers = auth_headers(client, email="purpose-filter@example.com", username="purposefilter")
    response = client.post(
        "/model-profiles/test-connectivity",
        headers=headers,
        json={
            "name": "测试配置",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "purposes": ["chat"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["purpose"] == "chat"
    assert calls == ["chat"]


def test_test_connectivity_skips_embedding_when_not_configured(monkeypatch) -> None:
    from app.services import model_profile_connectivity

    async def fake_chat_purpose(profile, purpose):
        return model_profile_connectivity.ConnectivityResult(
            purpose=purpose,
            ok=True,
            message="连通正常",
            model=getattr(profile, f"{purpose}_model"),
        )

    monkeypatch.setattr(model_profile_connectivity, "_test_chat_purpose", fake_chat_purpose)
    monkeypatch.setattr(
        model_profile_connectivity,
        "_test_embedding_purpose",
        lambda profile: (_ for _ in ()).throw(AssertionError("embedding test should be skipped")),
    )

    client = TestClient(app)
    headers = auth_headers(client, email="skip-embed@example.com", username="skipembeduser")
    response = client.post(
        "/model-profiles/test-connectivity",
        headers=headers,
        json={
            "name": "测试配置",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 4
    assert body["results"][3] == {
        "purpose": "embedding",
        "label": "向量",
        "ok": True,
        "message": "未配置，已跳过",
        "model": "未配置",
    }
