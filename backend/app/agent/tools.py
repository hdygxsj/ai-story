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


class UpdateNovelArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    title: str | None = Field(default=None, description="New novel title")
    description: str | None = Field(default=None, description="New novel description")


class ListWorkspaceNodesArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class CreateWorkspaceNodeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    title: str = Field(description="Node title")
    node_type: str = Field(description="folder, chapter, note, or draft")
    parent_id: str | None = Field(default=None, description="Parent folder UUID")


class CreateChapterWithContentArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    title: str = Field(description="Chapter title")
    content: str = Field(description="Complete non-empty chapter body")
    parent_id: str | None = Field(default=None, description="Optional parent folder UUID")


class ProposeDocumentUpdateArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")
    content: str = Field(description="Complete replacement document text")


class ProposeSelectionReplaceArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")
    selected_text: str = Field(description="Existing uniquely matching text")
    replacement_text: str = Field(description="Replacement text")


class ListDocumentVersionsArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")


class ProposeVersionRestoreArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")
    version_id: str = Field(description="Version UUID belonging to the document")


class RestoreWorkspaceNodeArgs(BaseModel):
    node_id: str = Field(description="Trashed workspace node UUID in the current novel")


class UpdateWorkspaceNodeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    node_id: str = Field(description="Workspace node UUID")
    title: str | None = Field(default=None, description="New title")
    parent_id: str | None = Field(default=None, description="New parent folder UUID")
    position: int | None = Field(default=None, description="Sibling position")


class TrashWorkspaceNodeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    node_id: str = Field(description="Workspace node UUID to trash")


class OrganizeWorkspaceTreeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    instruction: str = Field(default="", description="Optional natural language instruction")


class CleanupWorkspaceFoldersArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    instruction: str = Field(default="", description="Optional natural language instruction")


class ListMemoryItemsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class ListMemoryReviewItemsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class ProposeRewriteArgs(BaseModel):
    document_id: str = Field(description="Target document UUID")
    selected_text: str = Field(description="User-selected text to rewrite")
    instruction: str = Field(description="Rewrite instruction")


class SaveKeyMemoryArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    title: str = Field(description="Short memory title")
    body: str = Field(description="Memory body")
    importance: int = Field(default=80, ge=1, le=100)


class ListCreativeAssetsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class CreateCharacterAssetArgs(BaseModel):
    novel_id: str
    name: str
    summary: str


class CreateWorldRuleArgs(BaseModel):
    novel_id: str
    title: str
    rule: str


class ListTimelineEventsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class CreateTimelineEventArgs(BaseModel):
    novel_id: str
    title: str
    event_time: str
    summary: str


class ListCharacterStatesArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class UpdateCharacterStateArgs(BaseModel):
    novel_id: str
    character_name: str
    state: str
    state_id: str | None = Field(default=None, description="Existing character state UUID to update")
    scope: str | None = Field(default=None, description="Scope label such as chapter_3 or global")


class CreateRelationshipEdgeArgs(BaseModel):
    novel_id: str
    source_character: str
    target_character: str
    relationship_type: str
    description: str = ""


class UpdateCreativeAssetArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    asset_id: str = Field(description="Creative asset UUID")
    asset_type: str | None = Field(default=None, description="Asset type such as character or world_rule")
    name: str | None = Field(default=None, description="Updated asset name")
    summary: str | None = Field(default=None, description="Updated asset summary")


class DeleteCreativeAssetArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    asset_id: str = Field(description="Creative asset UUID")


class UpdateTimelineEventArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    event_id: str = Field(description="Timeline event UUID")
    title: str | None = Field(default=None, description="Updated event title")
    event_time: str | None = Field(default=None, description="Updated event time label")
    summary: str | None = Field(default=None, description="Updated event summary")


class DeleteTimelineEventArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    event_id: str = Field(description="Timeline event UUID")


class DeleteCharacterStateArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    state_id: str = Field(description="Character state UUID")


class UpdateRelationshipEdgeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    edge_id: str = Field(description="Relationship edge UUID")
    source_character: str | None = Field(default=None, description="Updated source character")
    target_character: str | None = Field(default=None, description="Updated target character")
    relationship_type: str | None = Field(default=None, description="Updated relationship type")
    description: str | None = Field(default=None, description="Updated relationship description")


class DeleteRelationshipEdgeArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    edge_id: str = Field(description="Relationship edge UUID")


class ListMaterialChangesArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    material_type: str | None = Field(default=None, description="Optional material type filter")
    material_id: str | None = Field(default=None, description="Optional material UUID filter")
    limit: int = Field(default=20, ge=1, le=100)


def draft_rewrite(selected_text: str, instruction: str) -> str:
    return f"{selected_text} The room turned tense as every sound seemed to wait for the next mistake."


def classify_agent_intent(message: str, selected_text: str | None) -> str:
    lowered = message.lower()
    if selected_text and ("rewrite" in lowered or "改写" in lowered or "重写" in lowered):
        return "rewrite_selection"

    material_keywords = (
        "素材",
        "材料",
        "资产",
        "角色",
        "世界观",
        "时间线",
        "人物关系",
        "关系网",
        "material",
        "asset",
    )
    workspace_keywords = (
        "文件夹",
        "folder",
        "目录",
        "章节",
        "chapter",
        "正文",
        "草稿",
        "draft",
        "workspace",
        "工作台",
    )
    delete_keywords = ("删", "删除", "移除", "去掉", "清理", "清除", "delete", "remove", "trash", "clear")
    organize_keywords = ("整理", "归类", "organize")

    if any(keyword in message for keyword in material_keywords):
        return "chat"

    if any(keyword in message for keyword in delete_keywords) and any(
        keyword in message for keyword in workspace_keywords
    ):
        return "cleanup_workspace"

    if any(keyword in message for keyword in organize_keywords) and any(
        keyword in message for keyword in workspace_keywords
    ):
        return "organize_workspace"

    if "remember" in lowered or "记住" in lowered:
        return "draft_key_memory"
    return "chat"


def _stub_tool(name: str, description: str, args_schema: type[BaseModel]):
    @tool(name, args_schema=args_schema)
    def _runtime_stub(**kwargs: Any) -> dict[str, Any]:
        return {"status": "error", "message": f"{name} requires runtime session"}

    return _runtime_stub


@tool("read_document", args_schema=ReadDocumentArgs)
def read_document(document_id: str) -> dict[str, Any]:
    """Read a document by id."""
    return {"document_id": document_id, "content": None, "status": "requires_runtime_loader"}


@tool("search_memory", args_schema=SearchMemoryArgs)
def search_memory(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    """Search approved novel memory items."""
    return {"novel_id": novel_id, "query": query, "limit": limit, "results": []}


@tool("search_rag", args_schema=SearchRagArgs)
def search_rag(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    """Search vector-indexed RAG chunks."""
    return {"novel_id": novel_id, "query": query, "limit": limit, "results": []}


@tool("update_novel", args_schema=UpdateNovelArgs)
def update_novel_tool(
    novel_id: str,
    title: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Rename a novel or update its description."""
    return {"novel_id": novel_id, "title": title, "description": description}


@tool("list_workspace_nodes", args_schema=ListWorkspaceNodesArgs)
def list_workspace_nodes_tool(novel_id: str) -> dict[str, Any]:
    """List chapter tree nodes including folders, chapters, and trash status."""
    return {"novel_id": novel_id, "nodes": []}


@tool("create_workspace_node", args_schema=CreateWorkspaceNodeArgs)
def create_workspace_node_tool(
    novel_id: str,
    title: str,
    node_type: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a folder, chapter, note, or draft node."""
    return {"novel_id": novel_id, "title": title, "node_type": node_type, "parent_id": parent_id}


@tool("create_chapter_with_content", args_schema=CreateChapterWithContentArgs)
def create_chapter_with_content_tool(
    novel_id: str,
    title: str,
    content: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a chapter and persist its complete body in the workspace."""
    return {"novel_id": novel_id, "title": title, "content": content, "parent_id": parent_id}


@tool("propose_document_update", args_schema=ProposeDocumentUpdateArgs)
def propose_document_update(document_id: str, content: str) -> dict[str, Any]:
    """Propose replacing a complete document after user confirmation."""
    return {"document_id": document_id, "content": content, "status": "requires_runtime_loader"}


@tool("propose_selection_replace", args_schema=ProposeSelectionReplaceArgs)
def propose_selection_replace(
    document_id: str, selected_text: str, replacement_text: str
) -> dict[str, Any]:
    """Propose replacing one unique text selection after user confirmation."""
    return {"document_id": document_id, "status": "requires_runtime_loader"}


@tool("list_document_versions", args_schema=ListDocumentVersionsArgs)
def list_document_versions_tool(document_id: str) -> dict[str, Any]:
    """List saved versions for a document in the current novel."""
    return {"document_id": document_id, "versions": []}


@tool("propose_version_restore", args_schema=ProposeVersionRestoreArgs)
def propose_version_restore(document_id: str, version_id: str) -> dict[str, Any]:
    """Propose restoring a saved document version after user confirmation."""
    return {"document_id": document_id, "version_id": version_id, "status": "requires_runtime_loader"}


@tool("restore_workspace_node", args_schema=RestoreWorkspaceNodeArgs)
def restore_workspace_node_tool(node_id: str) -> dict[str, Any]:
    """Restore a trashed workspace node in the current novel."""
    return {"node_id": node_id, "status": "requires_runtime_loader"}


@tool("update_workspace_node", args_schema=UpdateWorkspaceNodeArgs)
def update_workspace_node_tool(
    novel_id: str,
    node_id: str,
    title: str | None = None,
    parent_id: str | None = None,
    position: int | None = None,
) -> dict[str, Any]:
    """Rename or move a workspace node."""
    return {"novel_id": novel_id, "node_id": node_id}


@tool("trash_workspace_node", args_schema=TrashWorkspaceNodeArgs)
def trash_workspace_node_tool(novel_id: str, node_id: str) -> dict[str, Any]:
    """Move a workspace node to trash."""
    return {"novel_id": novel_id, "node_id": node_id}


@tool("organize_workspace_tree", args_schema=OrganizeWorkspaceTreeArgs)
def organize_workspace_tree(novel_id: str, instruction: str = "") -> dict[str, Any]:
    """Organize draft-like chapters into the drafts folder."""
    return {"novel_id": novel_id, "instruction": instruction}


@tool("cleanup_workspace_folders", args_schema=CleanupWorkspaceFoldersArgs)
def cleanup_workspace_folders(novel_id: str, instruction: str = "") -> dict[str, Any]:
    """Delete folders and move chapters to root when possible."""
    return {"novel_id": novel_id, "instruction": instruction}


@tool("list_memory_items", args_schema=ListMemoryItemsArgs)
def list_memory_items_tool(novel_id: str) -> dict[str, Any]:
    """List approved memory items."""
    return {"novel_id": novel_id, "items": []}


@tool("list_memory_review_items", args_schema=ListMemoryReviewItemsArgs)
def list_memory_review_items_tool(novel_id: str) -> dict[str, Any]:
    """List memory review queue items."""
    return {"novel_id": novel_id, "items": []}


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


@tool("list_creative_assets", args_schema=ListCreativeAssetsArgs)
def list_creative_assets_tool(novel_id: str) -> dict[str, Any]:
    """List creative assets such as characters and world entries."""
    return {"novel_id": novel_id, "assets": []}


@tool("create_character_asset", args_schema=CreateCharacterAssetArgs)
def create_character_asset(novel_id: str, name: str, summary: str) -> dict[str, Any]:
    """Create a character creative asset."""
    return {"action_type": "create_character_asset", "payload": locals()}


@tool("create_world_rule", args_schema=CreateWorldRuleArgs)
def create_world_rule(novel_id: str, title: str, rule: str) -> dict[str, Any]:
    """Create a worldbuilding rule asset."""
    return {"action_type": "create_world_rule", "payload": locals()}


@tool("list_timeline_events", args_schema=ListTimelineEventsArgs)
def list_timeline_events_tool(novel_id: str) -> dict[str, Any]:
    """List timeline events."""
    return {"novel_id": novel_id, "events": []}


@tool("create_timeline_event", args_schema=CreateTimelineEventArgs)
def create_timeline_event(novel_id: str, title: str, event_time: str, summary: str) -> dict[str, Any]:
    """Create a timeline event."""
    return {"action_type": "create_timeline_event", "payload": locals()}


@tool("list_character_states", args_schema=ListCharacterStatesArgs)
def list_character_states_tool(novel_id: str) -> dict[str, Any]:
    """List character states."""
    return {"novel_id": novel_id, "states": []}


@tool("update_character_state", args_schema=UpdateCharacterStateArgs)
def update_character_state(
    novel_id: str,
    character_name: str,
    state: str,
    state_id: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Create or update a character state snapshot."""
    return {"action_type": "update_character_state", "payload": locals()}


@tool("delete_character_state", args_schema=DeleteCharacterStateArgs)
def delete_character_state_tool(novel_id: str, state_id: str) -> dict[str, Any]:
    """Delete a character state record."""
    return {"novel_id": novel_id, "state_id": state_id}


@tool("update_creative_asset", args_schema=UpdateCreativeAssetArgs)
def update_creative_asset_tool(
    novel_id: str,
    asset_id: str,
    asset_type: str | None = None,
    name: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Update an existing creative asset by id."""
    return {"novel_id": novel_id, "asset_id": asset_id}


@tool("delete_creative_asset", args_schema=DeleteCreativeAssetArgs)
def delete_creative_asset_tool(novel_id: str, asset_id: str) -> dict[str, Any]:
    """Delete a creative asset by id."""
    return {"novel_id": novel_id, "asset_id": asset_id}


@tool("update_timeline_event", args_schema=UpdateTimelineEventArgs)
def update_timeline_event_tool(
    novel_id: str,
    event_id: str,
    title: str | None = None,
    event_time: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Update an existing timeline event by id."""
    return {"novel_id": novel_id, "event_id": event_id}


@tool("delete_timeline_event", args_schema=DeleteTimelineEventArgs)
def delete_timeline_event_tool(novel_id: str, event_id: str) -> dict[str, Any]:
    """Delete a timeline event by id."""
    return {"novel_id": novel_id, "event_id": event_id}


@tool("update_relationship_edge", args_schema=UpdateRelationshipEdgeArgs)
def update_relationship_edge_tool(
    novel_id: str,
    edge_id: str,
    source_character: str | None = None,
    target_character: str | None = None,
    relationship_type: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update an existing relationship edge by id."""
    return {"novel_id": novel_id, "edge_id": edge_id}


@tool("delete_relationship_edge", args_schema=DeleteRelationshipEdgeArgs)
def delete_relationship_edge_tool(novel_id: str, edge_id: str) -> dict[str, Any]:
    """Delete a relationship edge by id."""
    return {"novel_id": novel_id, "edge_id": edge_id}


@tool("list_material_changes", args_schema=ListMaterialChangesArgs)
def list_material_changes_tool(
    novel_id: str,
    material_type: str | None = None,
    material_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List recent material create/update/delete history."""
    return {"novel_id": novel_id, "material_type": material_type, "material_id": material_id, "limit": limit}


@tool("create_relationship_edge", args_schema=CreateRelationshipEdgeArgs)
def create_relationship_edge(
    novel_id: str,
    source_character: str,
    target_character: str,
    relationship_type: str,
    description: str = "",
) -> dict[str, Any]:
    """Create a relationship edge between characters."""
    return {"action_type": "create_relationship_edge", "payload": locals()}


def get_agent_tools() -> list[BaseTool]:
    return [
        read_document,
        search_memory,
        search_rag,
        update_novel_tool,
        list_workspace_nodes_tool,
        create_workspace_node_tool,
        create_chapter_with_content_tool,
        propose_document_update,
        propose_selection_replace,
        list_document_versions_tool,
        propose_version_restore,
        restore_workspace_node_tool,
        update_workspace_node_tool,
        trash_workspace_node_tool,
        organize_workspace_tree,
        cleanup_workspace_folders,
        list_memory_items_tool,
        list_memory_review_items_tool,
        propose_rewrite,
        save_key_memory,
        list_creative_assets_tool,
        create_character_asset,
        create_world_rule,
        update_creative_asset_tool,
        delete_creative_asset_tool,
        list_timeline_events_tool,
        create_timeline_event,
        update_timeline_event_tool,
        delete_timeline_event_tool,
        list_character_states_tool,
        update_character_state,
        delete_character_state_tool,
        create_relationship_edge,
        update_relationship_edge_tool,
        delete_relationship_edge_tool,
        list_material_changes_tool,
    ]
