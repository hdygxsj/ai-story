from app.agent.context import ContextBudget, build_context_pack


def test_context_pack_prioritizes_key_memory_and_neighboring_chapter() -> None:
    pack = build_context_pack(
        user_instruction="Write the next chapter.",
        current_document_text="",
        selected_text=None,
        key_memories=["Never let the protagonist betray a patient."],
        structured_memories=["A border clinic sits between two rival states."],
        neighboring_chapters=["Chapter 2 ended with the clinic under siege."],
        rag_results=["A minor note about weather."],
        budget=ContextBudget(max_tokens=2000, response_tokens=500),
    )

    assert pack.items[0].source == "user_instruction"
    assert any(item.source == "key_memory" for item in pack.items[:3])
    assert any(item.source == "neighboring_chapter" for item in pack.items)
    assert pack.estimated_tokens < 2000
