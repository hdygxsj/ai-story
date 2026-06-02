from app.agent.context import ContextBudget, ContextPack, build_context_pack


def build_agent_context(
    *,
    user_instruction: str,
    current_document_text: str,
    selected_text: str | None,
    key_memories: list[str],
    structured_assets: list[str],
    neighboring_chapters: list[str],
    rag_results: list[str],
    budget: ContextBudget,
) -> ContextPack:
    return build_context_pack(
        user_instruction=user_instruction,
        current_document_text=current_document_text,
        selected_text=selected_text,
        key_memories=key_memories,
        structured_memories=structured_assets,
        neighboring_chapters=neighboring_chapters,
        rag_results=rag_results,
        budget=budget,
    )
