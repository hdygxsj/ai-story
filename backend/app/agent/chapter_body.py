import re

_META_MARKERS = (
    "爽点清单",
    "本章爽点",
    "情节要点",
    "章节要点",
    "写作要点",
    "章纲",
    "细纲",
    "剧情点",
    "节奏点",
    "本章结构",
    "下一章方向",
    "待写要点",
    "outline",
    "beat sheet",
)

_BULLET_PREFIXES = ("-", "*", ">", "•", "·", "✅", "☑", "✔", "▪", "◦")


def is_outline_or_meta_content(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if any(marker in stripped or marker in lowered for marker in _META_MARKERS):
        return True

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    bullet_lines = 0
    for line in lines:
        normalized = line.lstrip()
        if normalized.startswith(_BULLET_PREFIXES):
            bullet_lines += 1
            continue
        if re.match(r"^\d+[.)、]\s*", normalized):
            bullet_lines += 1

    bullet_ratio = bullet_lines / len(lines)
    avg_len = sum(len(line) for line in lines) / len(lines)
    if bullet_ratio >= 0.45 and avg_len < 120:
        return True

    sentence_endings = sum(stripped.count(mark) for mark in "。！？…")
    if len(stripped) >= 200 and sentence_endings <= 1 and bullet_lines >= 2:
        return True

    return False


PROSE_BODY_GUIDANCE = (
    "章节正文必须是可直接发表的小说散文（场景、对话、动作、心理描写），"
    "禁止写入：爽点清单、情节要点、章纲、细纲、大纲、节奏点、待办列表、"
    "带 ✅ 的策划条目、系统说明式条目。这些内容只能留在对话里讨论，不能落盘到正文。"
)
