import json
from typing import Any

_MAX_ARG_VALUE_LENGTH = 160
_MAX_SUMMARY_LENGTH = 240


def _truncate(value: str, limit: int = _MAX_ARG_VALUE_LENGTH) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def sanitize_tool_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str):
            if key in {"content", "selected_text", "replacement_text", "instruction", "message"}:
                sanitized[key] = _truncate(value)
            else:
                sanitized[key] = value
        elif isinstance(value, (int, float, bool)) or value is None:
            sanitized[key] = value
        else:
            sanitized[key] = _truncate(str(value))
    return sanitized


def _parse_tool_result(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return {"message": output}
        return parsed if isinstance(parsed, dict) else {"message": output}
    return {}


def summarize_tool_result(output: Any) -> str:
    parsed = _parse_tool_result(output)
    message = parsed.get("message")
    if isinstance(message, str) and message.strip():
        return _truncate(message.strip(), _MAX_SUMMARY_LENGTH)
    status = parsed.get("status")
    if status == "error":
        return _truncate(str(parsed.get("message") or "工具执行失败"), _MAX_SUMMARY_LENGTH)
    if status == "ok":
        action_type = parsed.get("action_type")
        if isinstance(action_type, str) and action_type:
            return _truncate(f"已完成：{action_type}", _MAX_SUMMARY_LENGTH)
        return "执行成功"
    if isinstance(output, str) and output.strip():
        return _truncate(output.strip(), _MAX_SUMMARY_LENGTH)
    return "执行完成"


def tool_result_status(output: Any) -> str:
    parsed = _parse_tool_result(output)
    if parsed.get("status") == "error":
        return "error"
    return "ok"


def build_tool_call_record(
    *,
    run_id: str,
    tool: str,
    status: str,
    args: Any = None,
    summary: str | None = None,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "tool": tool,
        "status": status,
        "args": sanitize_tool_args(args),
        "summary": summary,
    }
