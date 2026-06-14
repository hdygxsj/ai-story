from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, WorkspaceNode
from app.services.document_actions import extract_document_plain_text

SNIPPET_RADIUS = 48


def _build_snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - SNIPPET_RADIUS)
    right = min(len(text), end + SNIPPET_RADIUS)
    snippet = text[left:right].replace("\n", " ")
    if left > 0:
        snippet = f"...{snippet}"
    if right < len(text):
        snippet = f"{snippet}..."
    return snippet


def _find_matches(text: str, query: str) -> list[tuple[int, int, str]]:
    lowered_text = text.casefold()
    lowered_query = query.casefold()
    if not lowered_query:
        return []

    matches: list[tuple[int, int, str]] = []
    start = 0
    while True:
        index = lowered_text.find(lowered_query, start)
        if index == -1:
            break
        end = index + len(query)
        matches.append((index, end, text[index:end]))
        start = index + 1
    return matches


async def search_novel_documents(
    session: AsyncSession,
    *,
    novel_id: UUID,
    query: str,
    limit: int = 50,
    max_matches_per_document: int = 5,
) -> list[dict[str, object]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.status != "trashed",
                WorkspaceNode.document_id.is_not(None),
            )
            .order_by(WorkspaceNode.position.asc(), WorkspaceNode.title.asc())
        )
    )
    if not nodes:
        return []

    document_ids = [node.document_id for node in nodes if node.document_id is not None]
    documents = list(
        await session.scalars(select(Document).where(Document.id.in_(document_ids)))
    )
    documents_by_id = {document.id: document for document in documents}

    hits: list[dict[str, object]] = []
    for node in nodes:
        if node.document_id is None:
            continue
        document = documents_by_id.get(node.document_id)
        if document is None:
            continue

        plain_text = extract_document_plain_text(document.content)
        title_matches = normalized_query.casefold() in node.title.casefold()
        body_matches = _find_matches(plain_text, normalized_query)

        if not body_matches and not title_matches:
            continue

        if title_matches and not body_matches:
            hits.append(
                {
                    "document_id": str(document.id),
                    "node_id": str(node.id),
                    "node_title": node.title,
                    "match_index": 0,
                    "match_length": 0,
                    "matched_text": "",
                    "snippet": f"章节标题：{node.title}",
                    "match_source": "title",
                    "total_matches_in_document": 0,
                }
            )
            if len(hits) >= limit:
                break
            continue

        total_matches = len(body_matches)
        for match_index, (start, end, matched_text) in enumerate(body_matches[:max_matches_per_document]):
            hits.append(
                {
                    "document_id": str(document.id),
                    "node_id": str(node.id),
                    "node_title": node.title,
                    "match_index": start,
                    "match_length": end - start,
                    "matched_text": matched_text,
                    "snippet": _build_snippet(plain_text, start, end),
                    "match_source": "body",
                    "total_matches_in_document": total_matches,
                    "occurrence_index": match_index,
                }
            )
            if len(hits) >= limit:
                return hits

    return hits
