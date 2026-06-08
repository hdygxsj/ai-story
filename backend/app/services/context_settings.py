from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelProfile, Novel, NovelContextSettings
from app.schemas.context import ContextBudgetSettings, ContextSources

DEFAULT_SOURCES = ContextSources().model_dump()
DEFAULT_BUDGET = ContextBudgetSettings().model_dump()


async def _default_max_tokens(session: AsyncSession, novel: Novel) -> int:
    if novel.default_model_profile_id is None:
        return 8000
    profile = await session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == novel.default_model_profile_id,
            ModelProfile.owner_id == novel.owner_id,
        )
    )
    if profile is None:
        return 8000
    return profile.context_window


async def get_or_create_context_settings(session: AsyncSession, *, novel: Novel) -> NovelContextSettings:
    settings = await session.scalar(
        select(NovelContextSettings).where(NovelContextSettings.novel_id == novel.id)
    )
    if settings is not None:
        return settings

    budget = DEFAULT_BUDGET.copy()
    budget["max_context_tokens"] = await _default_max_tokens(session, novel)
    settings = NovelContextSettings(
        novel_id=novel.id,
        sources=DEFAULT_SOURCES,
        budget=budget,
        updated_at=datetime.now(UTC),
    )
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings


async def update_context_settings(
    session: AsyncSession,
    *,
    novel: Novel,
    sources: dict | None,
    budget: dict | None,
) -> NovelContextSettings:
    settings = await get_or_create_context_settings(session, novel=novel)
    if sources is not None:
        merged = {**settings.sources, **sources}
        settings.sources = merged
    if budget is not None:
        merged = {**settings.budget, **budget}
        settings.budget = merged
    settings.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(settings)
    return settings
