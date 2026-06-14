from copy import deepcopy
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chapter_body import is_outline_or_meta_content
from app.models import Document, DocumentVersion, WorkspaceNode
from app.services.rag import extract_text_from_prosemirror, index_text


def text_document(text: str) -> dict[str, object]:
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
            for paragraph in paragraphs
        ],
    }


def workspace_snapshot(
    nodes: list[WorkspaceNode],
    document_text_by_id: dict[UUID, str] | None = None,
) -> list[dict[str, object]]:
    document_text_by_id = document_text_by_id or {}
    return [
        {
            "id": str(node.id),
            "title": node.title,
            "node_type": node.node_type,
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "document_id": str(node.document_id) if node.document_id else None,
            "position": node.position,
            "status": node.status,
            "has_content": bool(document_text_by_id.get(node.document_id, "").strip())
            if node.document_id
            else False,
            "content_chars": len(document_text_by_id.get(node.document_id, "").strip())
            if node.document_id
            else 0,
        }
        for node in nodes
    ]


async def load_workspace_nodes(session: AsyncSession, novel_id: UUID) -> list[WorkspaceNode]:
    return list(
        await session.scalars(
            select(WorkspaceNode)
            .where(WorkspaceNode.novel_id == novel_id)
            .order_by(WorkspaceNode.position, WorkspaceNode.created_at)
        )
    )


async def list_workspace_nodes(session: AsyncSession, *, novel_id: UUID) -> list[dict[str, object]]:
    nodes = await load_workspace_nodes(session, novel_id)
    document_ids = [node.document_id for node in nodes if node.document_id is not None]
    documents = (
        list(await session.scalars(select(Document).where(Document.id.in_(document_ids))))
        if document_ids
        else []
    )
    document_text_by_id = {
        document.id: extract_text_from_prosemirror(document.content) for document in documents
    }
    return workspace_snapshot(nodes, document_text_by_id)


async def create_workspace_node(
    session: AsyncSession,
    *,
    novel_id: UUID,
    title: str,
    node_type: str,
    parent_id: UUID | None = None,
) -> dict[str, object]:
    if parent_id is not None:
        parent = await session.scalar(
            select(WorkspaceNode).where(
                WorkspaceNode.id == parent_id,
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.node_type == "folder",
            )
        )
        if parent is None:
            return {"status": "error", "message": "父文件夹不存在。"}

    document_id = None
    if node_type != "folder":
        document = Document(novel_id=novel_id)
        session.add(document)
        await session.flush()
        document_id = document.id

    siblings = list(
        await session.scalars(
            select(WorkspaceNode).where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.parent_id == parent_id,
            )
        )
    )
    node = WorkspaceNode(
        novel_id=novel_id,
        parent_id=parent_id,
        document_id=document_id,
        title=title,
        node_type=node_type,
        position=(max((sibling.position for sibling in siblings), default=-1) + 1),
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    nodes = await load_workspace_nodes(session, novel_id)
    return {
        "status": "ok",
        "action_type": "workspace_create",
        "message": f"已创建{node_type}「{title}」。",
        "node": workspace_snapshot([node])[0],
        "workspace_nodes": workspace_snapshot(nodes),
    }


async def create_chapter_with_content(
    session: AsyncSession,
    *,
    novel_id: UUID,
    title: str,
    content: str,
    parent_id: UUID | None = None,
) -> dict[str, object]:
    normalized = content.strip()
    if not normalized:
        return {"status": "error", "message": "章节正文不能为空。"}
    if is_outline_or_meta_content(normalized):
        return {
            "status": "error",
            "message": "检测到爽点清单/大纲/要点列表，不能写入章节正文。请先生成小说散文正文。",
        }
    if parent_id is not None:
        parent = await session.scalar(
            select(WorkspaceNode).where(
                WorkspaceNode.id == parent_id,
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.node_type == "folder",
                WorkspaceNode.status != "trashed",
            )
        )
        if parent is None:
            return {"status": "error", "message": "父文件夹不存在。"}

    document_content = text_document(normalized)
    document = Document(novel_id=novel_id, content=document_content)
    session.add(document)
    await session.flush()
    session.add(DocumentVersion(document_id=document.id, source="agent", content=document_content))

    siblings = list(
        await session.scalars(
            select(WorkspaceNode).where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.parent_id == parent_id,
            )
        )
    )
    node = WorkspaceNode(
        novel_id=novel_id,
        parent_id=parent_id,
        document_id=document.id,
        title=title,
        node_type="chapter",
        position=max((sibling.position for sibling in siblings), default=-1) + 1,
    )
    session.add(node)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="document",
        source_id=str(document.id),
        text=normalized,
    )
    await session.commit()
    await session.refresh(node)
    nodes = await load_workspace_nodes(session, novel_id)
    return {
        "status": "ok",
        "action_type": "chapter_write",
        "message": f"已将《{title}》写入工作台。",
        "node": workspace_snapshot([node])[0],
        "workspace_nodes": workspace_snapshot(nodes),
    }


async def write_document_content(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
    content: str,
) -> dict[str, object]:
    from app.services.document_actions import get_owned_document

    normalized = content.strip()
    if not normalized:
        return {"status": "error", "message": "章节正文不能为空。"}
    if is_outline_or_meta_content(normalized):
        return {
            "status": "error",
            "message": "检测到爽点清单/大纲/要点列表，不能写入章节正文。",
        }

    document = await get_owned_document(
        session,
        owner_id=owner_id,
        novel_id=novel_id,
        document_id=document_id,
    )
    session.add(
        DocumentVersion(document_id=document.id, source="agent", content=deepcopy(document.content))
    )
    document.content = text_document(normalized)
    await index_text(
        session,
        novel_id=document.novel_id,
        source_type="document",
        source_id=str(document.id),
        text=normalized,
    )
    await session.commit()
    await session.refresh(document)
    return {
        "status": "ok",
        "action_type": "document_write",
        "message": "已更新章节正文。",
        "document_id": str(document.id),
    }


def split_prose_by_max_chars(text: str, max_chars: int) -> list[str]:
    max_chars = max(500, max_chars)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    if not paragraphs:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            flush()
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + max_chars])
                start += max_chars
            continue

        extra = len(paragraph) + (2 if current else 0)
        if current and current_len + extra > max_chars:
            flush()
        current.append(paragraph)
        current_len += extra

    flush()
    return chunks


def _split_chapter_titles(base_title: str, parts: int) -> list[str]:
    if parts <= 1:
        return [base_title]
    if parts == 2:
        return [f"{base_title}（上）", f"{base_title}（下）"]
    return [f"{base_title}（{index + 1}）" for index in range(parts)]


async def split_chapter_by_max_chars(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_id: UUID,
    node_id: UUID,
    max_chars: int = 3000,
) -> dict[str, object]:
    node = await session.scalar(
        select(WorkspaceNode).where(
            WorkspaceNode.id == node_id,
            WorkspaceNode.novel_id == novel_id,
            WorkspaceNode.node_type == "chapter",
            WorkspaceNode.status != "trashed",
        )
    )
    if node is None or node.document_id is None:
        return {"status": "error", "message": "章节不存在或缺少文档。"}

    from app.services.document_actions import extract_document_plain_text

    document = await session.get(Document, node.document_id)
    if document is None:
        return {"status": "error", "message": "章节文档不存在。"}

    text = extract_document_plain_text(document.content) or extract_text_from_prosemirror(document.content)
    normalized = text.strip()
    if not normalized:
        return {"status": "error", "message": "章节正文为空，无法拆分。"}
    if len(normalized) <= max_chars:
        return {"status": "error", "message": f"章节未超过 {max_chars} 字，无需拆分。"}

    chunks = split_prose_by_max_chars(normalized, max_chars)
    if len(chunks) < 2:
        return {"status": "error", "message": "无法按段落边界拆分，请调整字数上限后重试。"}

    titles = _split_chapter_titles(node.title, len(chunks))
    await write_document_content(
        session,
        owner_id=owner_id,
        novel_id=novel_id,
        document_id=document.id,
        content=chunks[0],
    )
    await update_workspace_node(session, novel_id=novel_id, node_id=node.id, title=titles[0])

    created_titles: list[str] = [titles[0]]
    insert_position = node.position + 1
    for index, chunk in enumerate(chunks[1:], start=1):
        result = await create_chapter_with_content(
            session,
            novel_id=novel_id,
            title=titles[index],
            content=chunk,
            parent_id=node.parent_id,
        )
        if result.get("status") != "ok":
            return result
        created_node = result.get("node")
        if isinstance(created_node, dict) and created_node.get("id"):
            await update_workspace_node(
                session,
                novel_id=novel_id,
                node_id=UUID(str(created_node["id"])),
                position=insert_position,
            )
            insert_position += 1
        created_titles.append(titles[index])

    nodes = await load_workspace_nodes(session, novel_id)
    return {
        "status": "ok",
        "action_type": "chapter_split",
        "message": f"已将「{node.title}」拆为 {len(chunks)} 章：{'、'.join(created_titles)}。",
        "workspace_nodes": workspace_snapshot(nodes),
        "parts": created_titles,
    }


async def update_workspace_node(
    session: AsyncSession,
    *,
    novel_id: UUID,
    node_id: UUID,
    title: str | None = None,
    parent_id: UUID | None = None,
    position: int | None = None,
) -> dict[str, object]:
    node = await session.scalar(
        select(WorkspaceNode).where(WorkspaceNode.id == node_id, WorkspaceNode.novel_id == novel_id)
    )
    if node is None or node.status == "trashed":
        return {"status": "error", "message": "节点不存在。"}

    if parent_id is not None:
        if parent_id == node_id:
            return {"status": "error", "message": "节点不能移动到自身。"}
        parent = await session.scalar(
            select(WorkspaceNode).where(
                WorkspaceNode.id == parent_id,
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.node_type == "folder",
            )
        )
        if parent is None:
            return {"status": "error", "message": "目标文件夹不存在。"}
        node.parent_id = parent_id

    if title is not None:
        node.title = title
    if position is not None:
        node.position = position

    await session.commit()
    nodes = await load_workspace_nodes(session, novel_id)
    return {
        "status": "ok",
        "action_type": "workspace_update",
        "message": f"已更新「{node.title}」。",
        "node": workspace_snapshot([node])[0],
        "workspace_nodes": workspace_snapshot(nodes),
    }


async def trash_workspace_node(
    session: AsyncSession,
    *,
    novel_id: UUID,
    node_id: UUID,
) -> dict[str, object]:
    node = await session.scalar(
        select(WorkspaceNode).where(WorkspaceNode.id == node_id, WorkspaceNode.novel_id == novel_id)
    )
    if node is None or node.status == "trashed":
        return {"status": "error", "message": "节点不存在或已在回收站。"}

    node.status = "trashed"
    await session.commit()
    nodes = await load_workspace_nodes(session, novel_id)
    return {
        "status": "ok",
        "action_type": "workspace_trash",
        "message": f"已将「{node.title}」移入回收站。",
        "workspace_nodes": workspace_snapshot(nodes),
    }


async def restore_workspace_node(
    session: AsyncSession,
    *,
    novel_id: UUID,
    node_id: UUID,
) -> dict[str, object]:
    node = await session.scalar(
        select(WorkspaceNode).where(WorkspaceNode.id == node_id, WorkspaceNode.novel_id == novel_id)
    )
    if node is None:
        return {"status": "error", "message": "节点不存在。"}
    if node.status != "trashed":
        return {"status": "error", "message": "节点不在回收站。"}

    before = workspace_snapshot(await load_workspace_nodes(session, novel_id))
    node.status = "draft"
    if node.parent_id is not None:
        parent = await session.get(WorkspaceNode, node.parent_id)
        if parent is None or parent.status == "trashed":
            node.parent_id = None
    await session.commit()
    nodes = await load_workspace_nodes(session, novel_id)
    after = workspace_snapshot(nodes)
    return {
        "status": "ok",
        "action_type": "workspace_restore",
        "message": f"已恢复「{node.title}」。",
        "workspace_diff": {
            "summary": f"Agent 已恢复「{node.title}」",
            "before": before,
            "after": after,
            "changes": [{"action": "restore", "node_id": str(node.id), "title": node.title}],
        },
        "workspace_nodes": after,
    }


def _is_draft_like_node(node: WorkspaceNode) -> bool:
    return node.node_type != "folder" and (
        node.node_type == "draft" or "草稿" in node.title or "废稿" in node.title
    )


def _workspace_node_depth(node: WorkspaceNode, nodes_by_id: dict[UUID, WorkspaceNode]) -> int:
    depth = 0
    parent_id = node.parent_id
    while parent_id is not None:
        depth += 1
        parent = nodes_by_id.get(parent_id)
        if parent is None:
            break
        parent_id = parent.parent_id
    return depth


def _protected_folder_titles(message: str) -> set[str]:
    lowered = message.lower()
    if "草稿" in message or "draft" in lowered:
        return set()
    return {"草稿", "草稿箱", "废稿箱"}


async def cleanup_workspace_folders(
    session: AsyncSession,
    *,
    novel_id: UUID,
    message: str = "",
) -> dict[str, object]:
    nodes = await load_workspace_nodes(session, novel_id)
    lowered_message = message.lower()
    cleanup_chapters = ("章节" in message or "chapter" in lowered_message or "正文" in message) and not (
        "文件夹" in message or "folder" in lowered_message
    )
    if cleanup_chapters:
        return await _cleanup_chapters(
            session,
            novel_id=novel_id,
            nodes=nodes,
            include_written="正文" in message,
        )

    nodes_by_id = {node.id: node for node in nodes}
    before = workspace_snapshot(nodes)
    protected_titles = _protected_folder_titles(message)
    folders = [
        node
        for node in nodes
        if node.node_type == "folder" and node.status != "trashed" and node.title not in protected_titles
    ]
    if not folders:
        return {"status": "ok", "message": "没有发现可删除的文件夹。", "workspace_diff": None}

    changes: list[dict[str, object]] = []
    root_positions = [node.position for node in nodes if node.parent_id is None and node.status != "trashed"]
    next_root_position = (max(root_positions) + 1) if root_positions else 0

    for folder in sorted(folders, key=lambda item: _workspace_node_depth(item, nodes_by_id), reverse=True):
        children = [node for node in nodes if node.parent_id == folder.id and node.status != "trashed"]
        for child in children:
            if child.node_type == "folder":
                continue
            changes.append(
                {
                    "action": "move",
                    "node_id": str(child.id),
                    "title": child.title,
                    "before_parent_id": str(folder.id),
                    "after_parent_id": None,
                    "before_position": child.position,
                    "after_position": next_root_position,
                }
            )
            child.parent_id = None
            child.position = next_root_position
            next_root_position += 1

    trashed_count = 0
    for folder in sorted(folders, key=lambda item: _workspace_node_depth(item, nodes_by_id), reverse=True):
        if folder.status == "trashed":
            continue
        remaining = [node for node in nodes if node.parent_id == folder.id and node.status != "trashed"]
        if remaining:
            continue
        folder.status = "trashed"
        trashed_count += 1
        changes.append(
            {
                "action": "trash",
                "node_id": str(folder.id),
                "title": folder.title,
            }
        )

    if not changes:
        return {
            "status": "ok",
            "message": "文件夹里还有子文件夹，请先说明要保留哪些目录。",
            "workspace_diff": None,
        }

    await session.commit()
    updated_nodes = await load_workspace_nodes(session, novel_id)
    moved_count = sum(1 for change in changes if change["action"] == "move")
    after = workspace_snapshot(updated_nodes)
    diff = {
        "summary": f"Agent 已删除 {trashed_count} 个文件夹",
        "before": before,
        "after": after,
        "changes": changes,
    }
    if moved_count:
        text = f"已删除 {trashed_count} 个文件夹，并将 {moved_count} 个章节移到根目录。"
    else:
        text = f"已删除 {trashed_count} 个文件夹。"
    return {
        "status": "ok",
        "action_type": "cleanup_workspace",
        "message": text,
        "workspace_diff": diff,
        "workspace_nodes": after,
    }


async def _cleanup_chapters(
    session: AsyncSession,
    *,
    novel_id: UUID,
    nodes: list[WorkspaceNode],
    include_written: bool = False,
) -> dict[str, object]:
    before = workspace_snapshot(nodes)
    active_chapters = [
        node
        for node in nodes
        if node.node_type != "folder" and node.status != "trashed" and node.document_id is not None
    ]
    document_ids = [node.document_id for node in active_chapters if node.document_id is not None]
    documents = list(await session.scalars(select(Document).where(Document.id.in_(document_ids)))) if document_ids else []
    documents_by_id = {document.id: document for document in documents}
    chapters_to_trash = [
        node
        for node in active_chapters
        if include_written or not extract_text_from_prosemirror(documents_by_id[node.document_id].content).strip()
    ]
    if not chapters_to_trash:
        return {"status": "ok", "message": "没有发现可清理的空章节。", "workspace_diff": None}

    changes: list[dict[str, object]] = []
    for chapter in chapters_to_trash:
        chapter.status = "trashed"
        changes.append({"action": "trash", "node_id": str(chapter.id), "title": chapter.title})

    await session.commit()
    updated_nodes = await load_workspace_nodes(session, novel_id)
    after = workspace_snapshot(updated_nodes)
    diff = {
        "summary": f"Agent 已删除 {len(chapters_to_trash)} 个章节" if include_written else f"Agent 已清理 {len(chapters_to_trash)} 个空章节",
        "before": before,
        "after": after,
        "changes": changes,
    }
    return {
        "status": "ok",
        "action_type": "cleanup_workspace",
        "message": (
            f"已将 {len(chapters_to_trash)} 个章节移入回收站。"
            if include_written
            else f"已将 {len(chapters_to_trash)} 个空章节移入回收站，有正文的章节已保留。"
        ),
        "workspace_diff": diff,
        "workspace_nodes": after,
    }


async def organize_workspace_tree(
    session: AsyncSession,
    *,
    novel_id: UUID,
) -> dict[str, object]:
    nodes = await load_workspace_nodes(session, novel_id)
    before = workspace_snapshot(nodes)
    root_folders = [node for node in nodes if node.parent_id is None and node.node_type == "folder"]
    drafts_folder = next((node for node in root_folders if node.title in {"草稿", "草稿箱", "废稿箱"}), None)
    draft_nodes = [node for node in nodes if _is_draft_like_node(node)]

    if drafts_folder is None and draft_nodes:
        root_positions = [node.position for node in nodes if node.parent_id is None]
        drafts_folder = WorkspaceNode(
            novel_id=novel_id,
            title="草稿",
            node_type="folder",
            position=(max(root_positions) + 1) if root_positions else 0,
        )
        session.add(drafts_folder)
        await session.flush()
        nodes.append(drafts_folder)

    changes: list[dict[str, object]] = []
    if drafts_folder is not None:
        existing_child_positions = [
            node.position for node in nodes if node.parent_id == drafts_folder.id and node.id != drafts_folder.id
        ]
        next_position = (max(existing_child_positions) + 1) if existing_child_positions else 0
        for node in draft_nodes:
            if node.parent_id == drafts_folder.id:
                continue
            changes.append(
                {
                    "action": "move",
                    "node_id": str(node.id),
                    "title": node.title,
                    "before_parent_id": str(node.parent_id) if node.parent_id else None,
                    "after_parent_id": str(drafts_folder.id),
                    "before_position": node.position,
                    "after_position": next_position,
                }
            )
            node.parent_id = drafts_folder.id
            node.position = next_position
            next_position += 1

    if not changes:
        return {"status": "ok", "message": "没有发现需要整理的章节或草稿。", "workspace_diff": None}

    await session.commit()
    updated_nodes = await load_workspace_nodes(session, novel_id)
    after = workspace_snapshot(updated_nodes)
    diff = {
        "summary": "Agent 已整理章节目录",
        "before": before,
        "after": after,
        "changes": changes,
    }
    return {
        "status": "ok",
        "action_type": "organize_workspace",
        "message": "已整理章节、文件夹和草稿，并保存目录草稿。",
        "workspace_diff": diff,
        "workspace_nodes": after,
    }
