from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.thinking_chat_model import ThinkingCompatibleChatOpenAI, _inject_reasoning_content


def test_inject_reasoning_content_for_tool_call_assistant_messages() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]},
            {"role": "tool", "content": "ok", "tool_call_id": "call-1"},
            {"role": "assistant", "content": "done"},
        ]
    }
    source_messages = [
        HumanMessage(content="hello"),
        AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "call-1"}]),
        ToolMessage(content="ok", tool_call_id="call-1"),
        AIMessage(content="done"),
    ]

    _inject_reasoning_content(payload, source_messages)

    assert payload["messages"][1]["reasoning_content"] == ""
    assert "reasoning_content" not in payload["messages"][3]


def test_inject_reasoning_content_preserves_stored_reasoning() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
            },
        ]
    }
    source_messages = [
        HumanMessage(content="hello"),
        AIMessage(
            content="",
            tool_calls=[{"name": "x", "args": {}, "id": "call-1"}],
            additional_kwargs={"reasoning_content": "chain-of-thought"},
        ),
    ]

    _inject_reasoning_content(payload, source_messages)

    assert payload["messages"][1]["reasoning_content"] == "chain-of-thought"


def test_create_chat_result_stores_reasoning_content() -> None:
    model = ThinkingCompatibleChatOpenAI(api_key="sk-test", model="deepseek-reasoner")
    result = model._create_chat_result(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "final answer",
                        "reasoning_content": "thinking trace",
                    },
                    "finish_reason": "stop",
                }
            ]
        }
    )

    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.additional_kwargs["reasoning_content"] == "thinking trace"


def test_get_request_payload_round_trips_reasoning_content() -> None:
    model = ThinkingCompatibleChatOpenAI(api_key="sk-test", model="deepseek-reasoner")
    payload = model._get_request_payload(
        [
            HumanMessage(content="hello"),
            AIMessage(
                content="",
                tool_calls=[{"name": "lookup", "args": {}, "id": "call-1"}],
                additional_kwargs={"reasoning_content": "plan the lookup"},
            ),
            ToolMessage(content='{"status":"ok"}', tool_call_id="call-1"),
        ]
    )

    assistant_message = next(message for message in payload["messages"] if message["role"] == "assistant")
    assert assistant_message["reasoning_content"] == "plan the lookup"
