from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int
    response_tokens: int


@dataclass(frozen=True)
class ContextItem:
    source: str
    text: str
    priority: int
    estimated_tokens: int


@dataclass(frozen=True)
class ContextPack:
    items: list[ContextItem]
    estimated_tokens: int
    usage_ratio: float
    status_messages: list[str]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context_pack(
    *,
    user_instruction: str,
    current_document_text: str,
    selected_text: str | None,
    key_memories: list[str],
    structured_memories: list[str],
    neighboring_chapters: list[str],
    rag_results: list[str],
    conversation_histories: list[str] | None = None,
    budget: ContextBudget,
) -> ContextPack:
    candidates: list[ContextItem] = [
        ContextItem("user_instruction", user_instruction, 1000, estimate_tokens(user_instruction)),
    ]
    if selected_text:
        candidates.append(ContextItem("selected_text", selected_text, 950, estimate_tokens(selected_text)))
    if current_document_text:
        candidates.append(
            ContextItem(
                "current_document",
                current_document_text,
                900,
                estimate_tokens(current_document_text),
            )
        )
    candidates.extend(ContextItem("key_memory", text, 850, estimate_tokens(text)) for text in key_memories)
    candidates.extend(
        ContextItem("structured_memory", text, 750, estimate_tokens(text))
        for text in structured_memories
    )
    candidates.extend(
        ContextItem("neighboring_chapter", text, 650, estimate_tokens(text))
        for text in neighboring_chapters
    )
    candidates.extend(ContextItem("rag_result", text, 500, estimate_tokens(text)) for text in rag_results)
    if conversation_histories:
        joined = "\n".join(conversation_histories)
        candidates.append(
            ContextItem("conversation_history", joined, 450, estimate_tokens(joined)),
        )

    available_tokens = max(0, budget.max_tokens - budget.response_tokens)
    selected: list[ContextItem] = []
    used_tokens = 0
    for item in sorted(candidates, key=lambda value: value.priority, reverse=True):
        if used_tokens + item.estimated_tokens <= available_tokens:
            selected.append(item)
            used_tokens += item.estimated_tokens

    usage_ratio = used_tokens / budget.max_tokens if budget.max_tokens else 1
    status_messages = [f"上下文占用约 {round(usage_ratio * 100)}%。"]
    if any(item.source == "neighboring_chapter" for item in selected):
        status_messages.append("已包含相邻章节上下文。")
    if usage_ratio >= 0.7:
        status_messages.append("上下文接近上限，可能即将压缩。")

    return ContextPack(
        items=selected,
        estimated_tokens=used_tokens,
        usage_ratio=usage_ratio,
        status_messages=status_messages,
    )
