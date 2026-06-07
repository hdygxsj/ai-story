from dataclasses import dataclass
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage

from app.agent.model_runtime import ModelPurpose, build_chat_model, embed_with_model_profile
from app.core.crypto import encrypt_api_key
from app.models import ModelProfile
from app.schemas.model_profile import ModelProfileTestRequest

PURPOSE_LABELS: dict[ModelPurpose, str] = {
    "chat": "对话",
    "writing": "写作",
    "summary": "总结",
    "embedding": "向量",
}


@dataclass
class ConnectivityResult:
    purpose: ModelPurpose
    ok: bool
    message: str
    model: str


def _embedding_configured(model_name: str | None) -> bool:
    return bool(model_name and model_name.strip())


def _api_key_ciphertext(value: str | None, stored: str | None, *, required: bool = True) -> str | None:
    if value:
        return encrypt_api_key(value)
    if stored:
        return stored
    if required:
        raise ValueError("缺少 API Key")
    return None


def build_test_model_profile(
    payload: ModelProfileTestRequest,
    *,
    owner_id: UUID,
    stored: ModelProfile | None = None,
) -> ModelProfile:
    default_api_key = _api_key_ciphertext(payload.api_key, stored.api_key_ciphertext if stored else None)
    if default_api_key is None:
        raise ValueError("请填写默认 API Key")

    return ModelProfile(
        id=stored.id if stored else uuid4(),
        owner_id=owner_id,
        name=payload.name or (stored.name if stored else "test"),
        provider_kind=payload.provider_kind,
        base_url=payload.base_url,
        api_key_ciphertext=default_api_key,
        chat_provider_kind=payload.chat_provider_kind,
        chat_model=payload.chat_model,
        chat_base_url=payload.chat_base_url,
        chat_api_key_ciphertext=_api_key_ciphertext(
            payload.chat_api_key,
            stored.chat_api_key_ciphertext if stored else None,
            required=False,
        ),
        writing_provider_kind=payload.writing_provider_kind,
        writing_model=payload.writing_model,
        writing_base_url=payload.writing_base_url,
        writing_api_key_ciphertext=_api_key_ciphertext(
            payload.writing_api_key,
            stored.writing_api_key_ciphertext if stored else None,
            required=False,
        ),
        summary_provider_kind=payload.summary_provider_kind,
        summary_model=payload.summary_model,
        summary_base_url=payload.summary_base_url,
        summary_api_key_ciphertext=_api_key_ciphertext(
            payload.summary_api_key,
            stored.summary_api_key_ciphertext if stored else None,
            required=False,
        ),
        embedding_provider_kind=payload.embedding_provider_kind,
        embedding_model=payload.embedding_model or (stored.embedding_model if stored else ""),
        embedding_base_url=payload.embedding_base_url,
        embedding_api_key_ciphertext=_api_key_ciphertext(
            payload.embedding_api_key,
            stored.embedding_api_key_ciphertext if stored else None,
            required=False,
        ),
        supports_tool_calling=payload.supports_tool_calling,
        supports_json_mode=payload.supports_json_mode,
        supports_streaming=False,
        context_window=payload.context_window,
        embedding_dimensions=payload.embedding_dimensions,
        extra_headers=payload.extra_headers,
    )


async def _test_chat_purpose(profile: ModelProfile, purpose: ModelPurpose) -> ConnectivityResult:
    from app.agent.model_runtime import _model_name

    model_name = _model_name(profile, purpose)
    try:
        model = build_chat_model(profile, purpose=purpose)
        await model.ainvoke([HumanMessage(content="ping")])
        return ConnectivityResult(purpose=purpose, ok=True, message="连通正常", model=model_name)
    except Exception as exc:
        return ConnectivityResult(purpose=purpose, ok=False, message=str(exc), model=model_name)


async def _test_embedding_purpose(profile: ModelProfile) -> ConnectivityResult:
    from app.agent.model_runtime import embedding_runtime_label

    runtime_label = embedding_runtime_label(profile)
    try:
        vector = await embed_with_model_profile(profile, "ping")
        if not vector:
            return ConnectivityResult(purpose="embedding", ok=False, message="未返回向量", model=runtime_label)
        return ConnectivityResult(
            purpose="embedding",
            ok=True,
            message=f"连通正常，向量维度 {len(vector)}",
            model=runtime_label,
        )
    except Exception as exc:
        return ConnectivityResult(purpose="embedding", ok=False, message=str(exc), model=runtime_label)


async def run_model_profile_connectivity_tests(
    profile: ModelProfile,
    *,
    purposes: list[ModelPurpose] | None = None,
) -> list[ConnectivityResult]:
    selected: tuple[ModelPurpose, ...] = tuple(purposes or ("chat", "writing", "summary", "embedding"))
    results: list[ConnectivityResult] = []
    for purpose in ("chat", "writing", "summary"):
        if purpose in selected:
            results.append(await _test_chat_purpose(profile, purpose))
    if "embedding" in selected:
        if _embedding_configured(profile.embedding_model):
            results.append(await _test_embedding_purpose(profile))
        else:
            results.append(
                ConnectivityResult(
                    purpose="embedding",
                    ok=True,
                    message="未配置，已跳过",
                    model="未配置",
                )
            )
    return results
