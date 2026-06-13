from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from app.agent.graph import _build_agent_system_prompt, _remove_incomplete_tool_call_history, build_agent_graph
from app.agent.tool_runtime import build_runtime_tools
from app.agent.tools import classify_agent_intent, get_agent_tools
from app.core.crypto import encrypt_api_key
from app.agent.context import ContextPack
from app.models import CreativeAsset, Document, DocumentVersion, MemoryItem, MemoryReviewItem, ModelProfile, Novel, PendingConfirmation, RagChunk, User, WorkspaceNode
from app.services.materials import list_material_changes
from app.services.rag import extract_text_from_prosemirror


from sqlalchemy import select


def _empty_context_pack() -> ContextPack:
    return ContextPack(items=[], estimated_tokens=0, usage_ratio=0, status_messages=[])


def test_default_agent_prompt_allows_selective_automatic_memory() -> None:
    prompt = _build_agent_system_prompt(_empty_context_pack())
    assert "save_key_memory" in prompt
    assert "propose_document_update" in prompt
    assert "无需用户审批" in prompt
    assert "文档和工作区的破坏性写入仍须遵循现有确认流程" in prompt


def test_agent_tool_registry_exposes_structured_langchain_tools() -> None:
    tools = get_agent_tools()
    tool_names = {tool.name for tool in tools}

    assert all(isinstance(tool, BaseTool) for tool in tools)
    assert all(tool.args_schema is not None for tool in tools)
    assert {
        "read_document",
        "search_memory",
        "search_rag",
        "propose_rewrite",
        "save_key_memory",
        "create_character_asset",
        "create_world_rule",
        "create_timeline_event",
        "update_character_state",
        "list_workspace_nodes",
        "create_workspace_node",
        "create_chapter_with_content",
        "propose_document_update",
        "propose_selection_replace",
        "list_document_versions",
        "propose_version_restore",
        "restore_workspace_node",
        "update_workspace_node",
        "update_novel",
        "trash_workspace_node",
        "organize_workspace_tree",
        "cleanup_workspace_folders",
        "list_memory_items",
        "list_creative_assets",
        "update_creative_asset",
        "delete_creative_asset",
        "delete_creative_assets",
        "list_timeline_events",
        "update_timeline_event",
        "delete_timeline_event",
        "delete_character_state",
        "update_relationship_edge",
        "delete_relationship_edge",
        "list_material_changes",
    }.issubset(tool_names)


async def test_agent_can_update_and_delete_creative_asset(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.materials.index_text", fake_index_text)

    user = User(email="material-agent@example.com", username="material-agent", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Material Novel")
    session.add(novel)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=user.id,
            novel_id=novel.id,
        )
    }
    created = await tools["create_character_asset"].ainvoke(
        {"novel_id": str(novel.id), "name": "Mira", "summary": "Keeper of the lighthouse."}
    )
    asset_id = created["id"]

    updated = await tools["update_creative_asset"].ainvoke(
        {
            "novel_id": str(novel.id),
            "asset_id": asset_id,
            "summary": "Retired lighthouse keeper.",
        }
    )
    deleted = await tools["delete_creative_asset"].ainvoke(
        {"novel_id": str(novel.id), "asset_id": asset_id}
    )

    changes = await list_material_changes(session, novel_id=novel.id)
    assert updated["status"] == "ok"
    assert deleted["status"] == "ok"
    assert len(changes) == 3
    assert changes[0].action == "deleted"
    assert changes[0].actor_source == "agent"
    assert changes[1].action == "updated"
    assert changes[2].action == "created"


async def test_agent_can_batch_delete_creative_assets(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.materials.index_text", fake_index_text)

    user = User(email="batch-delete@example.com", username="batch-delete", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Batch Delete Novel")
    session.add(novel)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=user.id,
            novel_id=novel.id,
        )
    }
    first = await tools["create_character_asset"].ainvoke(
        {"novel_id": str(novel.id), "name": "Old A", "summary": "Old summary A."}
    )
    second = await tools["create_character_asset"].ainvoke(
        {"novel_id": str(novel.id), "name": "Old B", "summary": "Old summary B."}
    )
    result = await tools["delete_creative_assets"].ainvoke(
        {"novel_id": str(novel.id), "asset_ids": [first["id"], second["id"], "00000000-0000-0000-0000-000000000999"]}
    )

    assets = list(
        await session.scalars(__import__("sqlalchemy").select(CreativeAsset).where(CreativeAsset.novel_id == novel.id))
    )
    assert result["status"] == "ok"
    assert len(result["deleted_ids"]) == 2
    assert len(result["missing_ids"]) == 1
    assert assets == []


async def test_create_chapter_with_content_persists_workspace_document(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.workspace_actions.index_text", fake_index_text)
    user = User(email="writer@example.com", username="writer", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Written Novel")
    session.add(novel)
    await session.commit()

    tools = {tool.name: tool for tool in build_runtime_tools(session, model_profile=None)}
    result = await tools["create_chapter_with_content"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "第一章 雾港",
            "content": "雾从海面漫上来，灯塔第一次熄灭。",
            "parent_id": None,
        }
    )

    node = await session.get(WorkspaceNode, UUID(result["node"]["id"]))
    document = await session.get(Document, node.document_id)
    versions = list(
        await session.scalars(
            __import__("sqlalchemy").select(DocumentVersion).where(DocumentVersion.document_id == document.id)
        )
    )
    assert result["status"] == "ok"
    assert result["action_type"] == "chapter_write"
    assert extract_text_from_prosemirror(document.content) == "雾从海面漫上来，灯塔第一次熄灭。"
    assert versions[0].source == "agent"


async def test_create_chapter_with_content_rejects_empty_content(session) -> None:
    user = User(email="empty@example.com", username="empty", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Empty Novel")
    session.add(novel)
    await session.commit()

    tools = {tool.name: tool for tool in build_runtime_tools(session, model_profile=None)}
    result = await tools["create_chapter_with_content"].ainvoke(
        {"novel_id": str(novel.id), "title": "第一章", "content": "   ", "parent_id": None}
    )

    nodes = list(await session.scalars(__import__("sqlalchemy").select(WorkspaceNode)))
    assert result["status"] == "error"
    assert nodes == []


async def test_scoped_document_tools_create_confirmation_and_hide_other_novels(session) -> None:
    user = User(email="scope@example.com", username="scope", password_hash="hash")
    session.add(user)
    await session.flush()
    current_novel = Novel(owner_id=user.id, title="Current")
    other_novel = Novel(owner_id=user.id, title="Other")
    session.add_all([current_novel, other_novel])
    await session.flush()
    current_document = Document(
        novel_id=current_novel.id,
        content={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "当前"}]}]},
    )
    other_document = Document(novel_id=other_novel.id)
    session.add_all([current_document, other_document])
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=user.id,
            novel_id=current_novel.id,
        )
    }
    proposal = await tools["propose_document_update"].ainvoke(
        {"document_id": str(current_document.id), "content": "更新正文"}
    )
    hidden = await tools["read_document"].ainvoke({"document_id": str(other_document.id)})
    created = await tools["create_workspace_node"].ainvoke(
        {
            "novel_id": str(other_novel.id),
            "title": "必须写入当前小说",
            "node_type": "folder",
            "parent_id": None,
        }
    )

    confirmation = await session.get(PendingConfirmation, UUID(proposal["confirmation_id"]))
    assert proposal["status"] == "ok"
    assert confirmation.action_type == "document_update"
    assert hidden["status"] == "error"
    created_node = await session.get(WorkspaceNode, UUID(created["node"]["id"]))
    assert created_node.novel_id == current_novel.id


async def test_restore_workspace_node_tool_restores_trashed_node(session) -> None:
    user = User(email="restore@example.com", username="restore", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Restore")
    session.add(novel)
    await session.flush()
    node = WorkspaceNode(novel_id=novel.id, title="旧章节", node_type="chapter", status="trashed")
    session.add(node)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=user.id,
            novel_id=novel.id,
        )
    }
    result = await tools["restore_workspace_node"].ainvoke({"node_id": str(node.id)})

    await session.refresh(node)
    assert result["status"] == "ok"
    assert result["workspace_diff"]["changes"][0]["action"] == "restore"
    assert node.status == "draft"


def test_agent_classifies_cleanup_chapters_as_workspace_cleanup() -> None:
    assert classify_agent_intent("清理一下章节", None) == "cleanup_workspace"


def test_agent_classifies_delete_written_followup_as_workspace_cleanup() -> None:
    assert classify_agent_intent("有正文的也删除", None) == "cleanup_workspace"


def test_agent_classifies_material_organize_as_chat() -> None:
    assert classify_agent_intent("整理一下素材", None) == "chat"
    assert classify_agent_intent("你整理一下角色资产", None) == "chat"


def test_agent_classifies_vague_organize_as_chat() -> None:
    assert classify_agent_intent("你整理一下", None) == "chat"


def test_agent_classifies_workspace_organize_shortcut() -> None:
    assert classify_agent_intent("帮我整理章节和草稿目录", None) == "organize_workspace"


def test_agent_classifies_write_chapter_content_intent() -> None:
    assert classify_agent_intent("先写进正文里", None) == "write_chapter_content"
    assert classify_agent_intent("帮我把这章正文保存到工作台", None) == "write_chapter_content"
    assert classify_agent_intent("我想写一个打怪升级的小说", None) == "chat"


async def test_create_workspace_node_rejects_empty_chapter(session) -> None:
    user = User(email="empty-chapter@example.com", username="empty-chapter", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Guard Novel")
    session.add(novel)
    await session.commit()

    tools = {tool.name: tool for tool in build_runtime_tools(session, model_profile=None)}
    result = await tools["create_workspace_node"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "第一章",
            "node_type": "chapter",
            "parent_id": None,
        }
    )
    nodes = list(await session.scalars(select(WorkspaceNode)))

    assert result["status"] == "error"
    assert "create_chapter_with_content" in result["message"]
    assert nodes == []


async def test_create_workspace_node_still_allows_folder(session) -> None:
    user = User(email="folder@example.com", username="folder", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Folder Novel")
    session.add(novel)
    await session.commit()

    tools = {tool.name: tool for tool in build_runtime_tools(session, model_profile=None)}
    result = await tools["create_workspace_node"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "第一卷",
            "node_type": "folder",
            "parent_id": None,
        }
    )

    assert result["status"] == "ok"
    assert result["node"]["node_type"] == "folder"


def test_agent_removes_incomplete_tool_call_history() -> None:
    messages = [
        HumanMessage(content="先读取文档和目录"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "read_document", "args": {}, "id": "call-document"},
                {"name": "list_workspace_nodes", "args": {}, "id": "call-workspace"},
            ],
        ),
        ToolMessage(content="{}", tool_call_id="call-document"),
    ]

    cleaned = _remove_incomplete_tool_call_history(messages)

    assert cleaned == [messages[0]]


def test_agent_graph_uses_tool_result_for_rewrite_confirmation_payload() -> None:
    document_id = uuid4()
    graph = build_agent_graph()

    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "document_id": document_id,
            "message": "Rewrite this with more tension.",
            "selected_text": "The clinic was quiet.",
        }
    )

    assert result["proposed_payload"]["document_id"] == str(document_id)
    assert result["proposed_payload"]["selected_text"] == "The clinic was quiet."
    assert "replacement_text" in result["proposed_payload"]
    assert result["response"] == "I drafted a tenser replacement. Please confirm before I apply it."


def test_agent_chat_uses_configured_model_response(monkeypatch) -> None:
    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="我可以帮你规划第一卷的冲突和人物弧光。")

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())

    profile = ModelProfile(
        owner_id=uuid4(),
        name="DeepSeek",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-test"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_model="",
    )
    graph = build_agent_graph(model_profile=profile)
    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "message": "我想写小说",
        }
    )

    assert "规划" in result["response"]


def test_agent_chat_without_model_profile_prompts_configuration() -> None:
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "message": "我想写小说",
        }
    )

    assert "Agent 配置" in result["response"]


async def test_agent_graph_executes_multiple_tools_sequentially(monkeypatch) -> None:
    running = False
    calls: list[str] = []

    @tool("first_tool")
    async def first_tool() -> dict[str, str]:
        """Run the first test tool."""
        nonlocal running
        assert not running
        running = True
        calls.append("first:start")
        await __import__("asyncio").sleep(0)
        calls.append("first:end")
        running = False
        return {"status": "ok", "message": "first"}

    @tool("second_tool")
    async def second_tool() -> dict[str, str]:
        """Run the second test tool."""
        nonlocal running
        assert not running
        running = True
        calls.append("second:start")
        await __import__("asyncio").sleep(0)
        calls.append("second:end")
        running = False
        return {"status": "ok", "message": "second"}

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            if any(getattr(message, "type", "") == "tool" for message in messages):
                return AIMessage(content="done")
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "first_tool", "args": {}, "id": "call-first"},
                    {"name": "second_tool", "args": {}, "id": "call-second"},
                ],
            )

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[first_tool, second_tool], model_profile=profile)

    result = await graph.ainvoke({"novel_id": uuid4(), "message": "run tools"})

    assert result["response"] == "done"
    assert calls == ["first:start", "first:end", "second:start", "second:end"]


async def test_agent_graph_preserves_workspace_effects_after_final_model_reply(monkeypatch) -> None:
    @tool("write_chapter")
    async def write_chapter() -> dict[str, object]:
        """Write a chapter."""
        return {
            "status": "ok",
            "action_type": "chapter_write",
            "message": "已写入。",
            "workspace_nodes": [{"id": "node-1", "document_id": "doc-1"}],
        }

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            if any(isinstance(message, ToolMessage) for message in messages):
                return AIMessage(content="第一章已写入工作台。")
            return AIMessage(
                content="",
                tool_calls=[{"name": "write_chapter", "args": {}, "id": "call-write"}],
            )

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[write_chapter], model_profile=profile)

    result = await graph.ainvoke({"novel_id": uuid4(), "message": "写第一章并放到工作台"})

    assert result["response"] == "第一章已写入工作台。"
    assert result["workspace_nodes"] == [{"id": "node-1", "document_id": "doc-1"}]
