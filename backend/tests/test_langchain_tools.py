from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from app.agent.graph import (
    _build_agent_system_prompt,
    _compress_tool_round_history,
    _remove_incomplete_tool_call_history,
    build_agent_graph,
)
from app.agent.tool_runtime import build_runtime_tools
from app.agent.tools import get_agent_tools
from app.core.crypto import encrypt_api_key
from app.agent.context import ContextPack
from app.models import CreativeAsset, Document, DocumentVersion, ModelProfile, Novel, PendingConfirmation, User, WorkspaceNode
from app.services.materials import list_material_changes
from app.services.rag import extract_text_from_prosemirror


from sqlalchemy import select


def _empty_context_pack() -> ContextPack:
    return ContextPack(items=[], estimated_tokens=0, usage_ratio=0, status_messages=[])


def test_default_agent_prompt_allows_selective_automatic_memory() -> None:
    prompt = _build_agent_system_prompt(_empty_context_pack())
    assert "save_key_memory" in prompt
    assert "search_documents_by_keyword" in prompt
    assert "calculate" in prompt
    assert "精确计算" in prompt
    assert "write_document_content" in prompt
    assert "无需用户审批" in prompt
    assert "propose_document_update 等需用户确认" in prompt
    assert "split_chapter_by_max_chars" in prompt
    assert "已有章节必须更新原 document_id" in prompt
    assert "禁止新建同名章节" in prompt


def test_agent_tool_registry_exposes_structured_langchain_tools() -> None:
    tools = get_agent_tools()
    tool_names = {tool.name for tool in tools}

    assert all(isinstance(tool, BaseTool) for tool in tools)
    assert all(tool.args_schema is not None for tool in tools)
    assert {
        "read_document",
        "search_memory",
        "search_rag",
        "search_documents_by_keyword",
        "calculate",
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
        "delete_memory_item",
        "list_creative_assets",
        "update_creative_asset",
        "delete_creative_asset",
        "delete_creative_assets",
        "list_timeline_events",
        "update_timeline_event",
        "reorder_timeline_events",
        "delete_timeline_event",
        "delete_character_state",
        "update_relationship_edge",
        "delete_relationship_edge",
        "list_material_changes",
    }.issubset(tool_names)


async def test_keyword_document_search_tool_searches_current_novel(session) -> None:
    user = User(email="keyword-agent@example.com", username="keyword-agent", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Keyword Novel")
    other_novel = Novel(owner_id=user.id, title="Other Keyword Novel")
    session.add_all([novel, other_novel])
    await session.flush()
    document = Document(
        novel_id=novel.id,
        content={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "灯塔钥匙藏在雾港码头下。"}]}
            ],
        },
    )
    other_document = Document(
        novel_id=other_novel.id,
        content={
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "灯塔钥匙不该出现在这里。"}]}],
        },
    )
    session.add_all([document, other_document])
    await session.flush()
    node = WorkspaceNode(novel_id=novel.id, title="第一章 雾港", node_type="chapter", document_id=document.id)
    other_node = WorkspaceNode(
        novel_id=other_novel.id,
        title="其他章节",
        node_type="chapter",
        document_id=other_document.id,
    )
    session.add_all([node, other_node])
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

    result = await tools["search_documents_by_keyword"].ainvoke({"query": "灯塔钥匙"})

    assert result["status"] == "ok"
    assert result["query"] == "灯塔钥匙"
    assert len(result["results"]) == 1
    assert result["results"][0]["document_id"] == str(document.id)
    assert result["results"][0]["node_title"] == "第一章 雾港"
    assert "灯塔钥匙" in result["results"][0]["snippet"]


def test_calculate_tool_evaluates_decimal_math_and_percentages() -> None:
    tools = {tool.name: tool for tool in get_agent_tools()}

    result = tools["calculate"].invoke({"expression": "(19.9 * 3 + 40) * 15%"})

    assert result == {
        "status": "ok",
        "expression": "(19.9 * 3 + 40) * 15%",
        "result": "14.955",
    }


def test_calculate_tool_evaluates_day_label_differences() -> None:
    tools = {tool.name: tool for tool in get_agent_tools()}

    result = tools["calculate"].invoke({"expression": "Day66 - Day53"})

    assert result == {
        "status": "ok",
        "expression": "Day66 - Day53",
        "result": "13",
    }


def test_calculate_tool_rejects_unsafe_expressions() -> None:
    tools = {tool.name: tool for tool in get_agent_tools()}

    result = tools["calculate"].invoke({"expression": "__import__('os').system('date')"})

    assert result["status"] == "error"
    assert "不支持" in result["message"]


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


async def test_list_workspace_nodes_reports_chapter_content_state(session) -> None:
    user = User(email="content-state@example.com", username="content-state", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Content State Novel")
    session.add(novel)
    await session.flush()
    empty_document = Document(novel_id=novel.id)
    written_document = Document(
        novel_id=novel.id,
        content={"type": "doc", "content": [{"type": "paragraph", "text": "已有正文"}]},
    )
    session.add_all([empty_document, written_document])
    await session.flush()
    session.add_all(
        [
            WorkspaceNode(
                novel_id=novel.id,
                document_id=empty_document.id,
                title="第一章",
                node_type="chapter",
                position=0,
            ),
            WorkspaceNode(
                novel_id=novel.id,
                document_id=written_document.id,
                title="第二章",
                node_type="chapter",
                position=1,
            ),
        ]
    )
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
    result = await tools["list_workspace_nodes"].ainvoke({"novel_id": str(novel.id)})

    by_title = {node["title"]: node for node in result["nodes"]}
    assert by_title["第一章"]["has_content"] is False
    assert by_title["第一章"]["content_chars"] == 0
    assert by_title["第二章"]["has_content"] is True
    assert by_title["第二章"]["content_chars"] == 4


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


async def test_create_chapter_with_content_rejects_outline_checklist(session) -> None:
    user = User(email="outline@example.com", username="outline", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Outline Novel")
    session.add(novel)
    await session.commit()

    tools = {tool.name: tool for tool in build_runtime_tools(session, model_profile=None)}
    result = await tools["create_chapter_with_content"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "第五章",
            "content": "### 本章爽点清单\n> ✅ 城市狩猎\n> ✅ 商城首开",
            "parent_id": None,
        }
    )

    nodes = list(await session.scalars(select(WorkspaceNode)))
    assert result["status"] == "error"
    assert "爽点清单" in result["message"]
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


def test_agent_tools_include_atomic_write_ops() -> None:
    tool_names = {tool.name for tool in get_agent_tools()}
    assert "write_document_content" in tool_names
    assert "split_chapter_by_max_chars" in tool_names
    assert "create_chapter_with_content" in tool_names


async def test_create_workspace_node_allows_empty_chapter(session) -> None:
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

    assert result["status"] == "ok"
    assert result["node"]["node_type"] == "chapter"
    assert len(nodes) == 1


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
    @tool("create_chapter_with_content")
    async def create_chapter_with_content() -> dict[str, object]:
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
                tool_calls=[{"name": "create_chapter_with_content", "args": {}, "id": "call-write"}],
            )

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[create_chapter_with_content], model_profile=profile)

    result = await graph.ainvoke({"novel_id": uuid4(), "message": "写第一章并放到工作台"})

    assert result["response"] == "第一章已写入工作台。"
    assert result["workspace_nodes"] == [{"id": "node-1", "document_id": "doc-1"}]


async def test_agent_graph_stops_repeated_identical_tool_calls(monkeypatch) -> None:
    calls = 0

    @tool("list_workspace_nodes")
    async def list_workspace_nodes() -> dict[str, object]:
        """List workspace nodes."""
        nonlocal calls
        calls += 1
        return {"status": "ok", "message": "已读取章节树。", "nodes": []}

    class RepeatingChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_workspace_nodes",
                        "args": {"novel_id": "novel-1"},
                        "id": f"call-{len(messages)}",
                    }
                ],
            )

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": RepeatingChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[list_workspace_nodes], model_profile=profile)

    result = await graph.ainvoke(
        {"novel_id": uuid4(), "message": "查看章节树"},
        {"recursion_limit": 8},
    )

    assert calls == 1
    assert "重复" in result["response"]


async def test_agent_graph_continues_beyond_previous_tool_round_cap(monkeypatch) -> None:
    calls = 0

    @tool("read_document")
    async def read_document(step: int) -> dict[str, object]:
        """Read a document for one step."""
        nonlocal calls
        calls += 1
        return {"status": "ok", "message": f"已读取第 {step} 步。"}

    class CyclingChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            step = 1 + sum(isinstance(message, ToolMessage) for message in messages)
            if step > 12:
                return AIMessage(content="全部读取完成。")
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"step": step}, "id": f"call-{step}"}],
            )

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": CyclingChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[read_document], model_profile=profile)

    result = await graph.ainvoke({"novel_id": uuid4(), "message": "持续读取"})

    assert calls == 12
    assert "轮次" not in result["response"]
    assert "全部读取完成" in result["response"]


def test_agent_graph_compresses_old_tool_results_when_context_is_large() -> None:
    messages = [
        SystemMessage(content="系统提示"),
        HumanMessage(content="请连续读取多个文档"),
    ]
    for step in range(20):
        messages.append(
            AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"step": step}, "id": f"call-{step}"}],
            )
        )
        messages.append(
            ToolMessage(
                content="x" * 8000,
                name="read_document",
                tool_call_id=f"call-{step}",
            )
        )

    compressed, did_compress = _compress_tool_round_history(messages, max_tokens=12000)

    assert did_compress is True
    assert _estimate_messages_tokens(compressed) < _estimate_messages_tokens(messages)
    assert str(compressed[-1].content).endswith("x")
    assert "…" in str(compressed[3].content)


def _estimate_messages_tokens(messages: list) -> int:
    from app.agent.context import estimate_tokens

    total = 0
    for message in messages:
        content = message.content if isinstance(message.content, str) else str(message.content)
        total += estimate_tokens(content)
    return total


async def test_agent_graph_prioritizes_current_request_over_prior_planning(monkeypatch) -> None:
    captured_messages = []

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            captured_messages.extend(messages)
            return AIMessage(content="收到。")

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    profile = ModelProfile(owner_id=uuid4(), name="test", provider_kind="openai-compatible", chat_model="test")
    graph = build_agent_graph(tools=[get_agent_tools()[0]], model_profile=profile)

    await graph.ainvoke(
        {
            "novel_id": uuid4(),
            "message": "我想你先把前四章的正文写进去",
            "system_prompt": "对话历史一直在讨论第八章规划。",
        }
    )

    system_text = "\n".join(
        str(message.content) for message in captured_messages if isinstance(message, SystemMessage)
    )
    assert "始终优先处理用户当前消息" in system_text
    assert "自主规划并组合原子工具" in system_text
