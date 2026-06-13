from app.agent.tool_trace import (
    build_tool_call_record,
    sanitize_tool_args,
    summarize_tool_result,
    tool_result_status,
)


def test_sanitize_tool_args_truncates_long_content() -> None:
    long_content = "章" * 200
    sanitized = sanitize_tool_args({"title": "第一章", "content": long_content})

    assert sanitized["title"] == "第一章"
    assert len(str(sanitized["content"])) < len(long_content)
    assert str(sanitized["content"]).endswith("…")


def test_summarize_tool_result_prefers_message() -> None:
    summary = summarize_tool_result({"status": "ok", "message": "已将《第一章》写入工作台。"})

    assert "第一章" in summary


def test_tool_result_status_marks_error_results() -> None:
    assert tool_result_status({"status": "error", "message": "文档不存在。"}) == "error"
    assert tool_result_status({"status": "ok"}) == "ok"


def test_build_tool_call_record_shape() -> None:
    record = build_tool_call_record(
        run_id="run-1",
        tool="create_chapter_with_content",
        status="running",
        args={"title": "第一章", "content": "正文"},
    )

    assert record["id"] == "run-1"
    assert record["tool"] == "create_chapter_with_content"
    assert record["status"] == "running"
    assert record["args"]["title"] == "第一章"
