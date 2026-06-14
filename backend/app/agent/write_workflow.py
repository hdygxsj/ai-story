import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chapter_body import PROSE_BODY_GUIDANCE, is_outline_or_meta_content
from app.agent.model_runtime import build_chat_model
from app.agent.tool_trace import build_tool_call_record
from app.models import Document, Message, ModelProfile, WorkspaceNode
from app.services.document_actions import create_document_update_proposal, extract_document_plain_text
from app.services.rag import extract_text_from_prosemirror
from app.services.workspace_actions import create_chapter_with_content, list_workspace_nodes, load_workspace_nodes


_EXTRACT_SYSTEM = (
    "你是小说工坊落盘助手。根据对话提取已在对话中生成的小说章节正文。"
    "只输出 JSON 数组，格式：[{\"title\": \"第一章 标题\", \"content\": \"完整正文...\"}]。"
    f"规则：{PROSE_BODY_GUIDANCE} "
    "按章号从小到大；content 必须是连续散文段落（纯文本 txt，不要 Markdown），不是大纲/爽点清单/要点列表；"
    "不要编造对话中没有的内容；不要输出对话里尚未写出的章节；"
    "若某章只有爽点清单或章纲没有散文正文，跳过该章。"
)

_MIN_BODY_CHARS = 80


def _parse_chapters_payload(text: str) -> list[dict[str, str]]:
    cleaned = text.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if block:
        cleaned = block.group(1).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("模型未返回章节 JSON 数组。")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, list):
        raise ValueError("章节 JSON 必须是数组。")

    chapters: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        content = str(item.get("content", "")).strip()
        if title and len(content) >= _MIN_BODY_CHARS and not is_outline_or_meta_content(content):
            chapters.append({"title": title, "content": content})
    if not chapters:
        raise ValueError("未从对话中识别到可落盘的小说散文正文（爽点清单/大纲不能写入正文）。")
    return chapters


def _chapter_number(title: str) -> int | None:
    match = re.search(r"第([0-9一二三四五六七八九十百千]+)章", title)
    if not match:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return int(raw)
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if raw in mapping:
        return mapping[raw]
    return None


def _find_chapter_node(nodes: list[WorkspaceNode], title: str) -> WorkspaceNode | None:
    target_num = _chapter_number(title)
    for node in nodes:
        if node.node_type != "chapter" or node.status == "trashed":
            continue
        if title == node.title or title in node.title or node.title in title:
            return node
        if target_num is not None and f"第{target_num}章" in node.title:
            return node
    return None


async def _load_conversation_text(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    limit: int = 30,
) -> str:
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
        )
    )
    lines: list[str] = []
    for item in messages:
        role = "用户" if item.role == "user" else "助手"
        content = (item.content or "").strip()
        if content:
            lines.append(f"{role}：{content}")
    return "\n\n".join(lines)


async def _document_is_empty(session: AsyncSession, document_id: UUID | None) -> bool:
    if document_id is None:
        return True
    document = await session.get(Document, document_id)
    if document is None:
        return True
    text = extract_document_plain_text(document.content) or extract_text_from_prosemirror(document.content)
    return len(text.strip()) < _MIN_BODY_CHARS


async def _extract_chapters_from_conversation(
    *,
    conversation_text: str,
    workspace_summary: str,
    model_profile: ModelProfile,
) -> list[dict[str, str]]:
    purpose = "writing" if model_profile.writing_model else "chat"
    model = build_chat_model(model_profile, purpose=purpose)
    response = await model.ainvoke(
        [
            SystemMessage(content=_EXTRACT_SYSTEM),
            HumanMessage(
                content=(
                    f"对话记录：\n{conversation_text}\n\n"
                    f"当前工作台章节：\n{workspace_summary or '（暂无章节）'}"
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return _parse_chapters_payload(content)


async def run_persist_to_workspace_workflow(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_id: UUID,
    conversation_id: UUID,
    model_profile: ModelProfile,
    open_document_id: UUID | None = None,
) -> dict[str, Any]:
    tool_calls: list[dict[str, Any]] = []

    nodes = await load_workspace_nodes(session, novel_id)
    workspace_nodes = await list_workspace_nodes(session, novel_id=novel_id)
    tool_calls.append(
        build_tool_call_record(
            run_id=str(uuid.uuid4()),
            tool="list_workspace_nodes",
            status="ok",
            args={"novel_id": str(novel_id)},
            summary=f"已加载 {len(nodes)} 个工作区节点",
        )
    )

    conversation_text = await _load_conversation_text(session, conversation_id=conversation_id)
    workspace_summary = "\n".join(
        f"- {node.title} (document_id={node.document_id})" for node in nodes if node.node_type == "chapter"
    )
    try:
        chapters = await _extract_chapters_from_conversation(
            conversation_text=conversation_text,
            workspace_summary=workspace_summary,
            model_profile=model_profile,
        )
    except ValueError as exc:
        return {
            "response": str(exc),
            "tool_calls": tool_calls,
            "workspace_nodes": workspace_nodes,
        }

    written_titles: list[str] = []
    pending_titles: list[str] = []
    confirmation_id: str | None = None
    last_workspace_nodes = workspace_nodes

    for chapter in chapters:
        title = chapter["title"]
        content = chapter["content"]
        existing = _find_chapter_node(nodes, title)
        if existing is not None and existing.document_id is not None:
            if not await _document_is_empty(session, existing.document_id):
                continue
            confirmation = await create_document_update_proposal(
                session,
                owner_id=owner_id,
                novel_id=novel_id,
                document_id=existing.document_id,
                content=content,
            )
            confirmation_id = str(confirmation.id)
            pending_titles.append(title)
            tool_calls.append(
                build_tool_call_record(
                    run_id=str(uuid.uuid4()),
                    tool="propose_document_update",
                    status="ok",
                    args={"document_id": str(existing.document_id), "title": title},
                    summary=f"《{title}》更新方案已生成",
                )
            )
            continue

        if open_document_id is not None and len(chapters) == 1:
            confirmation = await create_document_update_proposal(
                session,
                owner_id=owner_id,
                novel_id=novel_id,
                document_id=open_document_id,
                content=content,
            )
            confirmation_id = str(confirmation.id)
            pending_titles.append(title)
            tool_calls.append(
                build_tool_call_record(
                    run_id=str(uuid.uuid4()),
                    tool="propose_document_update",
                    status="ok",
                    args={"document_id": str(open_document_id), "title": title},
                    summary=f"《{title}》更新方案已生成",
                )
            )
            continue

        result = await create_chapter_with_content(
            session,
            novel_id=novel_id,
            title=title,
            content=content,
            parent_id=existing.parent_id if existing is not None else None,
        )
        if result.get("status") != "ok":
            tool_calls.append(
                build_tool_call_record(
                    run_id=str(uuid.uuid4()),
                    tool="create_chapter_with_content",
                    status="error",
                    args={"title": title},
                    summary=str(result.get("message", "写入失败")),
                )
            )
            continue
        written_titles.append(title)
        last_workspace_nodes = result.get("workspace_nodes") or last_workspace_nodes
        tool_calls.append(
            build_tool_call_record(
                run_id=str(uuid.uuid4()),
                tool="create_chapter_with_content",
                status="ok",
                args={"title": title, "content": content[:160]},
                summary=str(result.get("message", f"已写入《{title}》")),
            )
        )
        nodes = await load_workspace_nodes(session, novel_id)

    if not written_titles and not pending_titles:
        return {
            "response": "未找到可落盘的小说散文正文。请先在对话里生成完整章节正文；爽点清单、章纲、要点列表不能写入正文。",
            "tool_calls": tool_calls,
            "workspace_nodes": last_workspace_nodes,
        }

    parts: list[str] = []
    if written_titles:
        parts.append(f"已写入：{'、'.join(written_titles)}")
    if pending_titles:
        parts.append(f"待确认：{'、'.join(pending_titles)}（请在下方点击「写入正文」）")
    return {
        "response": "。".join(parts) + "。",
        "confirmation_id": confirmation_id,
        "workspace_nodes": last_workspace_nodes,
        "tool_calls": tool_calls,
    }


async def stream_persist_to_workspace_workflow(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_id: UUID,
    conversation_id: UUID,
    model_profile: ModelProfile,
    open_document_id: UUID | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    yield "delta", "正在分析对话并准备落盘…\n"
    result = await run_persist_to_workspace_workflow(
        session,
        novel_id=novel_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
        model_profile=model_profile,
        open_document_id=open_document_id,
    )
    for record in result.get("tool_calls") or []:
        yield "tool_call", record
    yield "done", result
