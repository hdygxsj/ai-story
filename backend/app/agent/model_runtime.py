from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.crypto import decrypt_api_key
from app.models import ModelProfile

ModelPurpose = Literal["chat", "writing", "summary"]


def _model_name(profile: ModelProfile, purpose: ModelPurpose) -> str:
    if purpose == "writing":
        return profile.writing_model
    if purpose == "summary":
        return profile.summary_model
    return profile.chat_model


def build_chat_model(profile: ModelProfile, purpose: ModelPurpose = "chat") -> BaseChatModel:
    api_key = decrypt_api_key(profile.api_key_ciphertext)
    model_name = _model_name(profile, purpose)
    provider_kind = profile.provider_kind.lower()

    if provider_kind == "anthropic":
        return ChatAnthropic(
            api_key=api_key,
            model_name=model_name,
            streaming=bool(profile.supports_streaming),
        )

    if provider_kind in {"openai", "openai-compatible"}:
        kwargs = {
            "api_key": api_key,
            "model": model_name,
            "streaming": bool(profile.supports_streaming),
        }
        if profile.base_url:
            kwargs["base_url"] = profile.base_url
        if profile.extra_headers:
            kwargs["default_headers"] = profile.extra_headers
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported model provider: {profile.provider_kind}")
