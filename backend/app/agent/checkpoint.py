import os
from contextlib import AbstractAsyncContextManager
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

_postgres_checkpointer = None
_postgres_context: AbstractAsyncContextManager[Any] | None = None
_postgres_setup_done = False


def _use_memory_checkpointer() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    backend = os.getenv("AGENT_CHECKPOINT_BACKEND", "").lower()
    if backend == "memory":
        return True
    return backend != "postgres"


async def get_checkpointer():
    global _postgres_checkpointer, _postgres_context, _postgres_setup_done

    if _use_memory_checkpointer():
        return MemorySaver()

    if _postgres_checkpointer is not None:
        return _postgres_checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from app.core.config import settings

        conn_string = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        context = AsyncPostgresSaver.from_conn_string(conn_string)
        checkpointer = await context.__aenter__()
        if not _postgres_setup_done:
            await checkpointer.setup()
            _postgres_setup_done = True
        _postgres_context = context
        _postgres_checkpointer = checkpointer
        return checkpointer
    except Exception:
        return MemorySaver()


async def close_checkpointer() -> None:
    global _postgres_checkpointer, _postgres_context, _postgres_setup_done

    if _postgres_context is None:
        return

    await _postgres_context.__aexit__(None, None, None)
    _postgres_context = None
    _postgres_checkpointer = None
    _postgres_setup_done = False
