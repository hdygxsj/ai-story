from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field


class ReadDocumentArgs(BaseModel):
    document_id: str = Field(description="Document UUID to read")


class SearchMemoryArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID to search inside")
    query: str = Field(description="Natural language memory query")
    limit: int = Field(default=8, ge=1, le=20)


class SearchRagArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID to retrieve from")
    query: str = Field(description="RAG semantic query")
    limit: int = Field(default=8, ge=1, le=20)


class ProposeRewriteArgs(BaseModel):
    document_id: str = Field(description="Target document UUID")
    selected_text: str = Field(description="User-selected text to rewrite")
    instruction: str = Field(description="Rewrite instruction")


class SaveKeyMemoryArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    title: str = Field(description="Short memory title")
    body: str = Field(description="Memory body")
    importance: int = Field(default=80, ge=1, le=100)


class CreateCharacterAssetArgs(BaseModel):
    novel_id: str
    name: str
    summary: str


class CreateWorldRuleArgs(BaseModel):
    novel_id: str
    title: str
    rule: str


class CreateTimelineEventArgs(BaseModel):
    novel_id: str
    title: str
    event_time: str
    summary: str


class UpdateCharacterStateArgs(BaseModel):
    novel_id: str
    character_name: str
    state: str


class ProposeWorkspaceChangeArgs(BaseModel):
    novel_id: str
    title: str
    node_type: str = Field(description="folder, chapter, note, or draft")
    parent_id: str | None = None


class OrganizeWorkspaceTreeArgs(BaseModel):
    novel_id: str
    instruction: str = Field(description="Natural language instruction for organizing chapters, folders, and drafts")


def draft_rewrite(selected_text: str, instruction: str) -> str:
    return f"{selected_text} The room turned tense as every sound seemed to wait for the next mistake."


def classify_agent_intent(message: str, selected_text: str | None) -> str:
    lowered = message.lower()
    if selected_text and ("rewrite" in lowered or "改写" in lowered or "重写" in lowered):
        return "rewrite_selection"
    if any(keyword in lowered for keyword in ["整理", "目录", "章节", "草稿", "文件夹", "folder", "chapter", "draft"]):
        return "organize_workspace"
    if "remember" in lowered or "记住" in lowered:
        return "draft_key_memory"
    return "chat"


@tool("read_document", args_schema=ReadDocumentArgs)
def read_document(document_id: str) -> dict[str, Any]:
    """Read a document by id. The runtime injects real persistence in the API layer."""
    return {"document_id": document_id, "content": None, "status": "requires_runtime_loader"}


@tool("search_memory", args_schema=SearchMemoryArgs)
def search_memory(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    """Search layered novel memory for facts relevant to the query."""
    return {"novel_id": novel_id, "query": query, "limit": limit, "results": []}


@tool("search_rag", args_schema=SearchRagArgs)
def search_rag(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    """Search Milvus-backed RAG chunks for semantically related context."""
    return {"novel_id": novel_id, "query": query, "limit": limit, "results": []}


@tool("propose_rewrite", args_schema=ProposeRewriteArgs)
def propose_rewrite(document_id: str, selected_text: str, instruction: str) -> dict[str, Any]:
    """Draft a rewrite proposal without mutating the document."""
    return {
        "action_type": "rewrite_selection",
        "message": "I drafted a tenser replacement. Please confirm before I apply it.",
        "payload": {
            "document_id": document_id,
            "selected_text": selected_text,
            "replacement_text": draft_rewrite(selected_text, instruction),
        },
    }


@tool("save_key_memory", args_schema=SaveKeyMemoryArgs)
def save_key_memory(novel_id: str, title: str, body: str, importance: int = 80) -> dict[str, Any]:
    """Save a key memory directly without approval."""
    return {
        "action_type": "memory_saved",
        "payload": {
            "novel_id": novel_id,
            "memory_type": "key_memory",
            "title": title,
            "body": body,
            "importance": importance,
        },
    }


@tool("create_character_asset", args_schema=CreateCharacterAssetArgs)
def create_character_asset(novel_id: str, name: str, summary: str) -> dict[str, Any]:
    """Propose creating a character asset."""
    return {"action_type": "create_character_asset", "payload": locals()}


@tool("create_world_rule", args_schema=CreateWorldRuleArgs)
def create_world_rule(novel_id: str, title: str, rule: str) -> dict[str, Any]:
    """Propose creating a worldbuilding rule."""
    return {"action_type": "create_world_rule", "payload": locals()}


@tool("create_timeline_event", args_schema=CreateTimelineEventArgs)
def create_timeline_event(novel_id: str, title: str, event_time: str, summary: str) -> dict[str, Any]:
    """Propose creating a timeline event."""
    return {"action_type": "create_timeline_event", "payload": locals()}


@tool("update_character_state", args_schema=UpdateCharacterStateArgs)
def update_character_state(novel_id: str, character_name: str, state: str) -> dict[str, Any]:
    """Propose updating a character state."""
    return {"action_type": "update_character_state", "payload": locals()}


@tool("propose_workspace_change", args_schema=ProposeWorkspaceChangeArgs)
def propose_workspace_change(
    novel_id: str,
    title: str,
    node_type: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Propose adding or reorganizing workspace nodes."""
    return {"action_type": "workspace_change", "payload": locals()}


@tool("organize_workspace_tree", args_schema=OrganizeWorkspaceTreeArgs)
def organize_workspace_tree(novel_id: str, instruction: str) -> dict[str, Any]:
    """Organize chapter, folder, and draft nodes. The API runtime applies validated changes."""
    return {
        "action_type": "organize_workspace",
        "payload": {"novel_id": novel_id, "instruction": instruction},
    }


def get_agent_tools() -> list[BaseTool]:
    return [
        read_document,
        search_memory,
        search_rag,
        propose_rewrite,
        save_key_memory,
        create_character_asset,
        create_world_rule,
        create_timeline_event,
        update_character_state,
        propose_workspace_change,
        organize_workspace_tree,
    ]
