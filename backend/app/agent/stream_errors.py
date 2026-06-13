def format_agent_stream_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    text = str(exc).strip()

    if name == "APIConnectionError" or "Connection error" in text:
        return "无法连接模型服务，请检查 Base URL 是否正确、模型服务是否已启动。"

    if name in {"APITimeoutError", "TimeoutError"} or "timeout" in text.lower():
        return "模型服务响应超时，请稍后重试。"

    if name in {"NotFoundError", "NotFound"} or "404" in text:
        return f"模型不存在或地址错误：{text}"

    if name == "AuthenticationError" or "401" in text or "403" in text:
        return "模型 API Key 无效或权限不足，请检查配置。"

    if text:
        return f"Agent 调用失败：{text}"

    return "Agent 调用失败，请检查模型配置。"
