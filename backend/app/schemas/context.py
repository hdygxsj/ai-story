from uuid import UUID

from pydantic import BaseModel, Field


class ContextSources(BaseModel):
    current_document: bool = True
    selected_text: bool = True
    key_memories: bool = True
    structured_assets: bool = True
    neighboring_chapters: bool = True
    rag_search: bool = True
    conversation_history: bool = True


class ContextBudgetSettings(BaseModel):
    max_context_tokens: int = 8000
    response_reserve: int = 1000
    recent_chapters_count: int = 3
    conversation_history_limit: int = 20


class ContextSettingsResponse(BaseModel):
    novel_id: UUID
    sources: ContextSources
    budget: ContextBudgetSettings
    updated_at: str


class ContextSettingsUpdate(BaseModel):
    sources: ContextSources | None = None
    budget: ContextBudgetSettings | None = None


class ContextDetailItem(BaseModel):
    source: str
    tokens: int
    compressed: bool = False


class ContextDetail(BaseModel):
    usage_ratio: float
    items: list[ContextDetailItem]
    warnings: list[str] = Field(default_factory=list)
    snapshot_id: UUID | None = None
