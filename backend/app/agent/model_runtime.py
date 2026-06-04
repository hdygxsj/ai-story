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


def _api_key_ciphertext(profile: ModelProfile, purpose: ModelPurpose) -> str:
    if purpose == "writing" and profile.writing_api_key_ciphertext:
        return profile.writing_api_key_ciphertext
    if purpose == "summary" and profile.summary_api_key_ciphertext:
        return profile.summary_api_key_ciphertext
    if purpose == "chat" and profile.chat_api_key_ciphertext:
        return profile.chat_api_key_ciphertext
    return profile.api_key_ciphertext


def _base_url(profile: ModelProfile, purpose: ModelPurpose) -> str | None:
    if purpose == "writing" and profile.writing_base_url:
        return profile.writing_base_url
    if purpose == "summary" and profile.summary_base_url:
        return profile.summary_base_url
    if purpose == "chat" and profile.chat_base_url:
        return profile.chat_base_url
    return profile.base_url


def _provider_kind(profile: ModelProfile, purpose: ModelPurpose) -> str:
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
