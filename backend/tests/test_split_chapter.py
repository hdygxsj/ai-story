from app.services.workspace_actions import _split_chapter_titles, split_prose_by_max_chars


def test_split_prose_by_max_chars_respects_paragraphs() -> None:
    paragraph_a = "甲" * 1500
    paragraph_b = "乙" * 1500
    text = f"{paragraph_a}\n\n{paragraph_b}"

    chunks = split_prose_by_max_chars(text, max_chars=3000)

    assert len(chunks) == 2
    assert paragraph_a in chunks[0]
    assert paragraph_b in chunks[1]


def test_split_prose_by_max_chars_keeps_short_text_single() -> None:
    text = "这是一段很短的正文。"

    chunks = split_prose_by_max_chars(text, max_chars=3000)

    assert chunks == [text]


def test_split_chapter_titles() -> None:
    assert _split_chapter_titles("第五章", 1) == ["第五章"]
    assert _split_chapter_titles("第五章", 2) == ["第五章（上）", "第五章（下）"]
    assert _split_chapter_titles("第五章", 3) == ["第五章（1）", "第五章（2）", "第五章（3）"]
