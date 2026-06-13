from typing import Literal

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.crypto import decrypt_api_key
from app.models import ModelProfile

ModelPurpose = Literal["chat", "writing", "summary", "embedding"]

OLLAMA_EMBEDDING_MODELS = frozenset(
    {
        "nomic-embed-text",
        "mxbai-embed-large",
        "snowflake-arctic-embed",
    }
)


def _model_name(profile: ModelProfile, purpose: ModelPurpose) -> str:
    if purpose == "embedding":
        return profile.embedding_model
    if purpose == "writing":
        return profile.writing_model
    if purpose == "summary":
        return profile.summary_model
    return profile.chat_model


def _api_key_ciphertext(profile: ModelProfile, purpose: ModelPurpose) -> str:
    if purpose == "embedding" and profile.embedding_api_key_ciphertext:
        return profile.embedding_api_key_ciphertext
    if purpose == "writing" and profile.writing_api_key_ciphertext:
        return profile.writing_api_key_ciphertext
    if purpose == "summary" and profile.summary_api_key_ciphertext:
        return profile.summary_api_key_ciphertext
    if purpose == "chat" and profile.chat_api_key_ciphertext:
        return profile.chat_api_key_ciphertext
    return profile.api_key_ciphertext


def _looks_like_ollama_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    normalized = base_url.lower().rstrip("/")
    return ":11434" in normalized or "ollama:" in normalized or normalized.endswith("/ollama")


def _resolve_embedding_provider_kind(profile: ModelProfile) -> str:
    if _looks_like_ollama_base_url(profile.embedding_base_url):
        return "ollama"
    model = (profile.embedding_model or "").strip().lower()
    if model in OLLAMA_EMBEDDING_MODELS:
        return "ollama"
    if profile.embedding_provider_kind:
        return profile.embedding_provider_kind.lower()
    return profile.provider_kind.lower()


def _base_url(profile: ModelProfile, purpose: ModelPurpose) -> str | None:
    if purpose == "embedding":
        if profile.embedding_base_url:
            return profile.embedding_base_url
        provider_kind = _resolve_embedding_provider_kind(profile)
        if provider_kind == "ollama":
            return settings.ollama_base_url
        if provider_kind in {"openai", "openai-compatible", "openai_compatible"}:
            return profile.base_url
        return None
    if purpose == "writing" and profile.writing_base_url:
        return profile.writing_base_url
    if purpose == "summary" and profile.summary_base_url:
        return profile.summary_base_url
    if purpose == "chat" and profile.chat_base_url:
        return profile.chat_base_url
    return profile.base_url


def _provider_kind(profile: ModelProfile, purpose: ModelPurpose) -> str:
    if purpose == "embedding":
        return _resolve_embedding_provider_kind(profile)
    if purpose == "writing" and profile.writing_provider_kind:
        return profile.writing_provider_kind
    if purpose == "summary" and profile.summary_provider_kind:
        return profile.summary_provider_kind
    if purpose == "chat" and profile.chat_provider_kind:
        return profile.chat_provider_kind
    return profile.provider_kind


def build_chat_model(profile: ModelProfile, purpose: ModelPurpose = "chat") -> BaseChatModel:
    api_key = decrypt_api_key(_api_key_ciphertext(profile, purpose))
    model_name = _model_name(profile, purpose)
    base_url = _base_url(profile, purpose)
    provider_kind = _provider_kind(profile, purpose).lower()

    if provider_kind == "anthropic":
        return ChatAnthropic(
            api_key=api_key,
            model_name=model_name,
            streaming=bool(profile.supports_streaming),
        )

    if provider_kind in {"openai", "openai-compatible", "openai_compatible"}:
        kwargs = {
            "api_key": api_key,
            "model": model_name,
            "streaming": bool(profile.supports_streaming),
        }
        if base_url:
            kwargs["base_url"] = base_url
        if profile.extra_headers:
            kwargs["default_headers"] = profile.extra_headers
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported model provider: {provider_kind}")


def embedding_runtime_label(profile: ModelProfile) -> str:
    model_name = _model_name(profile, "embedding")
    provider_kind = _resolve_embedding_provider_kind(profile)
    base_url = _base_url(profile, "embedding") or settings.ollama_base_url
    return f"{provider_kind} @ {base_url} · {model_name}"


async def embed_with_model_profile(profile: ModelProfile, text: str) -> list[float]:
    model_name = _model_name(profile, "embedding")
    provider_kind = _resolve_embedding_provider_kind(profile)

    if provider_kind == "ollama":
        base_url = (_base_url(profile, "embedding") or settings.ollama_base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/api/embeddings",
                json={"model": model_name, "prompt": text},
            )
        response.raise_for_status()
        embedding = response.json().get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("Ollama embedding response did not include an embedding vector")
        return [float(value) for value in embedding]

    if provider_kind in {"openai", "openai-compatible", "openai_compatible"}:
        base_url = (_base_url(profile, "embedding") or "https://api.openai.com/v1").rstrip("/")
        api_key = decrypt_api_key(_api_key_ciphertext(profile, "embedding"))
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/embeddings",
                json={"model": model_name, "input": text},
                headers=headers,
            )
        response.raise_for_status()
        data = response.json().get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Embedding response did not include data")
        embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
        if not isinstance(embedding, list):
            raise ValueError("Embedding response did not include an embedding vector")
        return [float(value) for value in embedding]

    raise ValueError(f"Unsupported embedding provider: {provider_kind}")
