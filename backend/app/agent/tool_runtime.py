from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import (
    ReadDocumentArgs,
    SaveKeyMemoryArgs,
    SearchMemoryArgs,
    SearchRagArgs,
    get_agent_tools,
)
from app.models import Document, ModelProfile, Novel
from app.services.memory import create_memory_item
from app.services.memory_search import search_memory_items
from app.services.rag import extract_text_from_prosemirror, search_rag_chunks


def build_runtime_tools(
    session: AsyncSession,
    *,
    model_profile: ModelProfile | None,
    owner_id: UUID | None = None,
    novel_id: UUID | None = None,
) -> list[BaseTool]:
    scoped_novel_id = novel_id

    def current_novel_id(requested_novel_id: str) -> UUID:
        return scoped_novel_id or UUID(requested_novel_id)

    @tool("search_memory", args_schema=SearchMemoryArgs)
    async def search_memory_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search layered novel memory for facts relevant to the query."""
        target_novel_id = current_novel_id(novel_id)
        results = await search_memory_items(
            session,
            novel_id=target_novel_id,
            query=query,
            limit=limit,
        )
        return {
            "novel_id": str(target_novel_id),
            "query": query,
            "limit": limit,
            "results": results,
        }

    @tool("search_rag", args_schema=SearchRagArgs)
    async def search_rag_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search vector-indexed RAG chunks for semantically related context."""
        target_novel_id = current_novel_id(novel_id)
        try:
            chunks = await search_rag_chunks(
                session,
                novel_id=target_novel_id,
                query=query,
                limit=limit,
                model_profile=model_profile,
            )
            results = [
                {
                    "text": chunk.text,
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                }
                for chunk in chunks
            ]
        except Exception:
            results = []
        return {
            "novel_id": str(target_novel_id),
            "query": query,
            "limit": limit,
            "results": results,
        }

    @tool("read_document", args_schema=ReadDocumentArgs)
    async def read_document_runtime(document_id: str) -> dict[str, Any]:
        """Read a document by id."""
        query = select(Document).where(Document.id == UUID(document_id))
        if scoped_novel_id is not None:
            query = query.where(Document.novel_id == scoped_novel_id)
        if owner_id is not None:
            query = query.join(Novel, Novel.id == Document.novel_id).where(
                Novel.owner_id == owner_id
            )
        document = await session.scalar(query)
        if document is None:
            return {"document_id": document_id, "content": None, "status": "not_found"}
        return {
            "document_id": document_id,
            "content": extract_text_from_prosemirror(document.content),
            "status": "ok",
        }

    @tool("save_key_memory", args_schema=SaveKeyMemoryArgs)
    async def save_key_memory_runtime(
        novel_id: str, title: str, body: str, importance: int = 80
    ) -> dict[str, Any]:
        """Save durable novel memory without approval."""
        if owner_id is None or scoped_novel_id is None:
            return {
                "status": "error",
                "action_type": "memory_save_failed",
                "message": "Authenticated owner and novel scope are required to save memory.",
            }
        memory = await create_memory_item(
            session,
            novel_id=scoped_novel_id,
            memory_type="key_memory",
            title=title,
            body=body,
            importance=importance,
            metadata={"source": "agent_inferred"},
        )
        await session.commit()
        await session.refresh(memory)
        return {
            "status": "ok",
            "action_type": "memory_saved",
            "message": f"已保存关键记忆「{title}」。",
            "memory_item_id": str(memory.id),
        }

    runtime_by_name = {
        "search_memory": search_memory_runtime,
        "search_rag": search_rag_runtime,
        "read_document": read_document_runtime,
        "save_key_memory": save_key_memory_runtime,
    }

    tools: list[BaseTool] = []
    for tool_obj in get_agent_tools():
        tools.append(runtime_by_name.get(tool_obj.name, tool_obj))
    return tools
