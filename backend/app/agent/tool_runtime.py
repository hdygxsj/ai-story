from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import ReadDocumentArgs, SearchMemoryArgs, SearchRagArgs, get_agent_tools
from app.models import Document, ModelProfile
from app.services.memory_search import search_memory_items
from app.services.rag import extract_text_from_prosemirror, search_rag_chunks


def build_runtime_tools(
    session: AsyncSession,
    *,
    model_profile: ModelProfile | None,
) -> list[BaseTool]:
    @tool("search_memory", args_schema=SearchMemoryArgs)
    async def search_memory_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search layered novel memory for facts relevant to the query."""
        results = await search_memory_items(
            session,
            novel_id=UUID(novel_id),
            query=query,
            limit=limit,
        )
        return {"novel_id": novel_id, "query": query, "limit": limit, "results": results}

    @tool("search_rag", args_schema=SearchRagArgs)
    async def search_rag_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search vector-indexed RAG chunks for semantically related context."""
        try:
            chunks = await search_rag_chunks(
                session,
                novel_id=UUID(novel_id),
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
        return {"novel_id": novel_id, "query": query, "limit": limit, "results": results}

    @tool("read_document", args_schema=ReadDocumentArgs)
    async def read_document_runtime(document_id: str) -> dict[str, Any]:
        """Read a document by id."""
        document = await session.scalar(select(Document).where(Document.id == UUID(document_id)))
        if document is None:
            return {"document_id": document_id, "content": None, "status": "not_found"}
        return {
            "document_id": document_id,
            "content": extract_text_from_prosemirror(document.content),
            "status": "ok",
        }

    runtime_by_name = {
        "search_memory": search_memory_runtime,
        "search_rag": search_rag_runtime,
        "read_document": read_document_runtime,
    }

    tools: list[BaseTool] = []
    for tool_obj in get_agent_tools():
        tools.append(runtime_by_name.get(tool_obj.name, tool_obj))
    return tools
