import pytest
from fastapi.testclient import TestClient

from app.agent.model_runtime import build_chat_model, embed_with_model_profile
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


async def test_embedding_infers_ollama_from_base_url_without_provider_kind(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.4, 0.5]}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.agent.model_runtime.httpx.AsyncClient", FakeClient)
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="DeepSeek default",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_model="nomic-embed-text",
        embedding_base_url="http://ollama:11434",
    )

    vector = await embed_with_model_profile(profile, "ping")

    assert vector == [0.4, 0.5]
    assert captured["url"] == "http://ollama:11434/api/embeddings"
    assert captured["headers"] is None


async def test_embedding_infers_ollama_from_model_name_without_provider_kind(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.6, 0.7]}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.agent.model_runtime.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr("app.agent.model_runtime.settings.ollama_base_url", "http://ollama:11434")
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="DeepSeek default",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_model="nomic-embed-text",
    )

    await embed_with_model_profile(profile, "ping")

    assert captured["url"] == "http://ollama:11434/api/embeddings"


async def test_embedding_prefers_ollama_base_url_over_generic_provider_kind(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.8, 0.9]}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.agent.model_runtime.httpx.AsyncClient", FakeClient)
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="DeepSeek default",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_provider_kind="openai-compatible",
        embedding_model="nomic-embed-text",
        embedding_base_url="http://ollama:11434",
    )

    await embed_with_model_profile(profile, "ping")

    assert captured["url"] == "http://ollama:11434/api/embeddings"


async def test_embedding_without_provider_kind_does_not_fall_back_to_default_chat_provider() -> None:
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="DeepSeek default",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_model="custom-embedding-model",
    )

    with pytest.raises(ValueError, match="向量场景供应商"):
        await embed_with_model_profile(profile, "ping")


async def test_ollama_embedding_provider_calls_local_embeddings_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.1, 0.2, 0.3]}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.agent.model_runtime.httpx.AsyncClient", FakeClient)
    profile = ModelProfile(
        owner_id="00000000-0000-0000-0000-000000000001",
        name="Local Ollama",
        provider_kind="openai-compatible",
        api_key_ciphertext=encrypt_api_key("sk-default"),
        chat_model="chat-model",
        writing_model="writing-model",
        summary_model="summary-model",
        embedding_provider_kind="ollama",
        embedding_model="nomic-embed-text",
        embedding_base_url="http://ollama:11434",
    )

    vector = await embed_with_model_profile(profile, "lighthouse map")

    assert vector == [0.1, 0.2, 0.3]
    assert captured["url"] == "http://ollama:11434/api/embeddings"
    assert captured["json"] == {"model": "nomic-embed-text", "prompt": "lighthouse map"}
    assert captured["headers"] is None


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


def _fake_chat_model_factory():
    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="我可以帮你继续写下去。")

    return FakeChatModel()


def test_agent_streaming_endpoint_returns_incremental_response(monkeypatch) -> None:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, AIMessageChunk
    from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

    class StreamingFakeChatModel(BaseChatModel):
        @property
        def _llm_type(self):
            return "streaming-fake"

        def bind_tools(self, tools):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="我可以帮你继续写下去。"))])

        def _stream(self, messages, stop=None, run_manager=None, **kwargs):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", additional_kwargs={"reasoning_content": "先分析场景目标。"})
            )
            yield ChatGenerationChunk(message=AIMessageChunk(content="我可以帮你"))
            yield ChatGenerationChunk(message=AIMessageChunk(content="继续写下去。"))

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": StreamingFakeChatModel())

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Streaming Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Chat profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "Help me plan the next scene."},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert body.count('"type": "delta"') == 2
    assert '"type": "reasoning"' in body
    assert "我可以帮你" in body
    assert "继续写下去。" in body
    conversations = client.get(f"/novels/{novel['id']}/conversations", headers=headers).json()
    messages = client.get(
        f"/novels/{novel['id']}/conversations/{conversations[0]['id']}/messages",
        headers=headers,
    ).json()
    assert messages[1]["metadata"]["reasoning_content"] == "先分析场景目标。"


def test_agent_stream_returns_error_event_when_model_call_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from langchain_core.messages import AIMessageChunk

    class FailingStreamingChatModel:
        def bind_tools(self, _tools):
            return self

        async def astream(self, _messages):
            if False:
                yield AIMessageChunk(content="")
            raise ConnectionError("Connection error.")

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FailingStreamingChatModel())

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Failing Stream Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Chat profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "hello"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    events = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]
    assert events[-1]["type"] == "error"
    assert "无法连接模型服务" in events[-1]["message"]
