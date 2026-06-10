from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_runtime import build_runtime_tools
from app.main import app
from app.models import MemoryItem


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "tool@example.com", "username": "tool", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "tool@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_runtime_search_memory_returns_approved_items(session: AsyncSession) -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Tool Novel"}).json()

    session.add(
        MemoryItem(
            novel_id=UUID(novel["id"]),
            memory_type="key_memory",
            title="誓言",
            body="主角不能背叛病人。",
            importance=90,
        )
    )
    await session.commit()

    tools = build_runtime_tools(session, model_profile=None)
    search_tool = next(tool for tool in tools if tool.name == "search_memory")
    result = await search_tool.ainvoke({"novel_id": novel["id"], "query": "背叛", "limit": 8})

    assert result["results"]
    assert any("背叛" in entry["body"] for entry in result["results"])
