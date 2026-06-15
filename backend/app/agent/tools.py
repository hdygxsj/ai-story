import ast
import re
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

MATH_CALCULATION_GUIDANCE = (
    "遇到金额、比例、百分比、字数、时间差、年龄、等级、战力数值或其他精确计算时，"
    "必须调用 calculate 工具取得结果；不要依赖模型心算。"
)


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


class CalculateArgs(BaseModel):
    expression: str = Field(
        min_length=1,
        max_length=500,
        description="Arithmetic expression. Supports +, -, *, /, **, parentheses, decimals, and percentages like 15%.",
    )


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
    content: str = Field(description="Complete non-empty chapter body as plain txt prose (no Markdown)")
    parent_id: str | None = Field(default=None, description="Optional parent folder UUID")


class ProposeDocumentUpdateArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")
    content: str = Field(description="Complete replacement chapter body as plain txt prose (no Markdown)")


class WriteDocumentContentArgs(BaseModel):
    document_id: str = Field(description="Document UUID to update")
    content: str = Field(description="Complete chapter body as plain txt prose to save immediately (no Markdown)")


class SplitChapterByMaxCharsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    node_id: str = Field(description="Chapter node UUID to split")
    max_chars: int = Field(default=3000, ge=500, le=10000, description="Maximum characters per part")


class ProposeSelectionReplaceArgs(BaseModel):
    document_id: str = Field(description="Document UUID in the current novel")
    selected_text: str = Field(description="Existing uniquely matching text")
    replacement_text: str = Field(description="Replacement plain txt prose (no Markdown)")


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
    title: str = Field(description="Arc or milestone title, e.g. 第二卷：世界大变")
    event_time: str = Field(description="When it happens, e.g. 第一卷结束后. Same title+event_time upserts.")
    summary: str


class ListCharacterStatesArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")


class UpdateCharacterStateArgs(BaseModel):
    novel_id: str
    character_name: str
    state: str
    state_id: str | None = Field(default=None, description="Existing character state UUID to update")
    scope: str | None = Field(
        default=None,
        description="Scope label such as current, chapter_3, or global. Same character+scope upserts.",
    )


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


class DeleteCreativeAssetsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    asset_ids: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Creative asset UUIDs to delete in one batch",
    )


class UpdateTimelineEventArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    event_id: str = Field(description="Timeline event UUID")
    title: str | None = Field(default=None, description="Updated event title")
    event_time: str | None = Field(default=None, description="Updated event time label")
    summary: str | None = Field(default=None, description="Updated event summary")
    position: int | None = Field(default=None, ge=1, description="Explicit display order; lower comes first")


class ReorderTimelineEventsArgs(BaseModel):
    novel_id: str = Field(description="Novel UUID")
    event_ids: list[str] = Field(
        min_length=1,
        description="Timeline event UUIDs in desired display order. Unlisted events are appended automatically.",
    )


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


_PERCENT_PATTERN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%")


def _normalize_calculation_expression(expression: str) -> str:
    return _PERCENT_PATTERN.sub(r"(\1/100)", expression)


def _format_decimal_result(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    formatted = format(value.normalize(), "f")
    return formatted.rstrip("0").rstrip(".")


def _eval_decimal_ast(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval_decimal_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp):
        operand = _eval_decimal_ast(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        left = _eval_decimal_ast(node.left)
        right = _eval_decimal_ast(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            if right != right.to_integral_value() or abs(right) > 100:
                raise ValueError("指数必须是 -100 到 100 之间的整数。")
            return left ** int(right)
    raise ValueError("表达式包含不支持的内容。")


def evaluate_calculation(expression: str) -> Decimal:
    normalized = _normalize_calculation_expression(expression.strip())
    parsed = ast.parse(normalized, mode="eval")
    return _eval_decimal_ast(parsed)


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


@tool("calculate", args_schema=CalculateArgs)
def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a precise arithmetic expression before answering numeric questions."""
    try:
        result = evaluate_calculation(expression)
    except (DivisionByZero, InvalidOperation, OverflowError, SyntaxError, ValueError) as exc:
        return {"status": "error", "message": f"不支持的计算表达式：{exc}"}
    return {
        "status": "ok",
        "expression": expression,
        "result": _format_decimal_result(result),
    }


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
    """List nodes with document ids and content state; use existing document_id for old or empty chapters."""
    return {"novel_id": novel_id, "nodes": []}


@tool("create_workspace_node", args_schema=CreateWorkspaceNodeArgs)
def create_workspace_node_tool(
    novel_id: str,
    title: str,
    node_type: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a folder, chapter, note, or draft node shell."""
    return {"novel_id": novel_id, "title": title, "node_type": node_type, "parent_id": parent_id}


@tool("create_chapter_with_content", args_schema=CreateChapterWithContentArgs)
def create_chapter_with_content_tool(
    novel_id: str,
    title: str,
    content: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a new chapter only when no matching chapter exists; never duplicate an existing chapter title."""
    return {"novel_id": novel_id, "title": title, "content": content, "parent_id": parent_id}


@tool("propose_document_update", args_schema=ProposeDocumentUpdateArgs)
def propose_document_update(document_id: str, content: str) -> dict[str, Any]:
    """Propose a full chapter body replacement; user must confirm before it applies."""
    return {"document_id": document_id, "content": content, "status": "requires_runtime_loader"}


@tool("write_document_content", args_schema=WriteDocumentContentArgs)
def write_document_content_tool(document_id: str, content: str) -> dict[str, Any]:
    """Atomically replace a chapter body and save immediately without confirmation."""
    return {"document_id": document_id, "content": content, "status": "requires_runtime_loader"}


@tool("split_chapter_by_max_chars", args_schema=SplitChapterByMaxCharsArgs)
def split_chapter_by_max_chars_tool(
    novel_id: str, node_id: str, max_chars: int = 3000
) -> dict[str, Any]:
    """Split an overlong chapter into multiple parts, each at most max_chars."""
    return {"novel_id": novel_id, "node_id": node_id, "max_chars": max_chars}


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
    """Delete one creative asset by id. Execute directly; never ask the user to delete manually."""
    return {"novel_id": novel_id, "asset_id": asset_id}


@tool("delete_creative_assets", args_schema=DeleteCreativeAssetsArgs)
def delete_creative_assets_tool(novel_id: str, asset_ids: list[str]) -> dict[str, Any]:
    """Delete multiple creative assets by id in one batch. Use when cleaning up old or duplicate assets."""
    return {"novel_id": novel_id, "asset_ids": asset_ids}


@tool("update_timeline_event", args_schema=UpdateTimelineEventArgs)
def update_timeline_event_tool(
    novel_id: str,
    event_id: str,
    title: str | None = None,
    event_time: str | None = None,
    summary: str | None = None,
    position: int | None = None,
) -> dict[str, Any]:
    """Update an existing timeline event by id."""
    return {"novel_id": novel_id, "event_id": event_id}


@tool("reorder_timeline_events", args_schema=ReorderTimelineEventsArgs)
def reorder_timeline_events_tool(novel_id: str, event_ids: list[str]) -> dict[str, Any]:
    """Reorder timeline events by providing event ids in the desired display order."""
    return {"novel_id": novel_id, "event_ids": event_ids}


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
        calculate,
        update_novel_tool,
        list_workspace_nodes_tool,
        create_workspace_node_tool,
        create_chapter_with_content_tool,
        write_document_content_tool,
        split_chapter_by_max_chars_tool,
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
        delete_creative_assets_tool,
        list_timeline_events_tool,
        create_timeline_event,
        update_timeline_event_tool,
        reorder_timeline_events_tool,
        delete_timeline_event_tool,
        list_character_states_tool,
        update_character_state,
        delete_character_state_tool,
        create_relationship_edge,
        update_relationship_edge_tool,
        delete_relationship_edge_tool,
        list_material_changes_tool,
    ]
