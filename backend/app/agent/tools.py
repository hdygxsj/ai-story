def draft_rewrite(selected_text: str, instruction: str) -> str:
    return f"{selected_text} The room turned tense as every sound seemed to wait for the next mistake."


def classify_agent_intent(message: str, selected_text: str | None) -> str:
    lowered = message.lower()
    if selected_text and ("rewrite" in lowered or "改写" in lowered or "重写" in lowered):
        return "rewrite_selection"
    if "remember" in lowered or "记住" in lowered:
        return "draft_key_memory"
    return "chat"
