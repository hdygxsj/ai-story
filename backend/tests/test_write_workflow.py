import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.write_workflow import _parse_chapters_payload, run_persist_to_workspace_workflow
from app.models import ModelProfile, Novel, User


def test_parse_chapters_payload_accepts_json_array() -> None:
    payload = json.dumps(
        [{"title": "第一章 雾港", "content": "a" * 100}, {"title": "第二章 灯塔", "content": "b" * 100}],
        ensure_ascii=False,
    )
    chapters = _parse_chapters_payload(payload)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "第一章 雾港"


def test_parse_chapters_payload_rejects_short_content() -> None:
    payload = json.dumps([{"title": "第一章", "content": "太短"}], ensure_ascii=False)
    with pytest.raises(ValueError, match="可落盘"):
        _parse_chapters_payload(payload)


def test_parse_chapters_payload_rejects_outline_content() -> None:
    outline = "\n".join(
        [
            "### 本章爽点清单",
            "> ✅ 城市狩猎：仓库+堆场",
            "> ✅ 商城首开：买唐刀",
        ]
        + ["补充情节。" * 20]
    )
    payload = json.dumps([{"title": "第五章", "content": outline}], ensure_ascii=False)
    with pytest.raises(ValueError, match="散文正文"):
        _parse_chapters_payload(payload)


async def test_persist_workflow_writes_new_chapters(session, monkeypatch) -> None:
    user = User(email="persist@example.com", username="persist", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Persist Novel")
    session.add(novel)
    await session.flush()
    conversation_id = uuid4()
    profile = ModelProfile(
        owner_id=user.id,
        name="writer",
        provider_kind="openai-compatible",
        chat_model="test-model",
        api_key_ciphertext="test-key",
    )

    chapters = [
        {"title": "第一章 起点", "content": "x" * 120},
        {"title": "第二章 转折", "content": "y" * 120},
    ]

    monkeypatch.setattr(
        "app.agent.write_workflow._extract_chapters_from_conversation",
        AsyncMock(return_value=chapters),
    )
    monkeypatch.setattr("app.services.workspace_actions.index_text", AsyncMock(return_value=None))

    result = await run_persist_to_workspace_workflow(
        session,
        novel_id=novel.id,
        owner_id=user.id,
        conversation_id=conversation_id,
        model_profile=profile,
    )

    assert "已写入" in result["response"]
    assert result["workspace_nodes"]
    assert len(result["tool_calls"]) >= 3
