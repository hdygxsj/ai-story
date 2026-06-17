from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import get_agent_tools
from app.core.security import create_access_token
from app.main import app
from app.models import Novel, User


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.mark.asyncio
async def test_agent_tools_list_matches_registered_tools(session: AsyncSession) -> None:
    user = User(email="tool-list@example.com", username="tool-list", password_hash="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/agent-tools", headers=_headers(user))

    assert response.status_code == 200
    tool_names = {item["name"] for item in response.json()}
    assert tool_names == {tool.name for tool in get_agent_tools()}
    assert "calculate" in tool_names
    assert "read_document" in tool_names


@pytest.mark.asyncio
async def test_agent_tool_detail_returns_argument_schema(session: AsyncSession) -> None:
    user = User(email="tool-schema@example.com", username="tool-schema", password_hash="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/agent-tools/calculate", headers=_headers(user))

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "calculate"
    assert "expression" in payload["args_schema"]["properties"]


@pytest.mark.asyncio
async def test_agent_tool_run_executes_pure_tool(session: AsyncSession) -> None:
    user = User(email="tool-run@example.com", username="tool-run", password_hash="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    owned_novel = Novel(owner_id=user.id, title="Tool Novel")
    session.add(owned_novel)
    await session.commit()
    await session.refresh(owned_novel)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/novels/{owned_novel.id}/agent/tools/calculate",
            headers=_headers(user),
            json={"arguments": {"expression": "(12 + 8) * 15%"}},
        )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert response.json()["result"]["result"] == "3"


@pytest.mark.asyncio
async def test_agent_tool_run_enforces_novel_ownership(session: AsyncSession) -> None:
    owner = User(email="tool-owner@example.com", username="tool-owner", password_hash="hash")
    other_id = uuid4()
    novel = Novel(owner_id=other_id, title="Other Novel")
    session.add_all([owner, novel])
    await session.commit()
    await session.refresh(owner)
    await session.refresh(novel)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/novels/{novel.id}/agent/tools/list_workspace_nodes",
            headers=_headers(owner),
            json={"arguments": {}},
        )

    assert response.status_code == 404
