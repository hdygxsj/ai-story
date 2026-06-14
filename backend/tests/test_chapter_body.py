import pytest

from app.agent.chapter_body import is_outline_or_meta_content, normalize_prose_text
from app.services.rag import extract_text_from_prosemirror
from app.services.workspace_actions import text_document


def test_normalize_prose_text_strips_markdown() -> None:
    text = """# 第一章 开端

**叶尘**翻进宿舍时，走廊的灯已经灭了。

> 他左臂在窗框上蹭出一道血痕。

---

下铺传来[王磊](https://example.com)的鼾声。"""
    normalized = normalize_prose_text(text)
    assert "#" not in normalized
    assert "**" not in normalized
    assert "第一章 开端" in normalized
    assert "叶尘翻进宿舍时" in normalized
    assert "王磊" in normalized
    assert "https://" not in normalized


def test_text_document_stores_plain_txt_paragraphs() -> None:
    document = text_document("## 标题\n\n这是**正文**段落。")
    assert extract_text_from_prosemirror(document) == "标题\n这是正文段落。"


def test_detects_satisfaction_point_checklist() -> None:
    text = """第五章 城市狩猎

---

### 本章爽点清单

> ✅ 城市狩猎：仓库+堆场，新怪物「铁爪鼬」登场
> ✅ 行为差异：独行 vs 群居怪，扩展世界观
> ✅ 敏捷26非人：揭示系统本身是最强外挂
"""
    assert is_outline_or_meta_content(text)


def test_accepts_narrative_prose() -> None:
    text = (
        "叶尘翻进宿舍时，走廊的灯已经灭了两个小时。"
        "他左臂在窗框上蹭出一道血痕，旧伤跟着一跳。"
        "下铺传来王磊的鼾声，像一台坏掉的风箱。"
    ) * 3
    assert not is_outline_or_meta_content(text)


def test_detects_bullet_heavy_planning_list() -> None:
    text = "\n".join(
        [
            "- 仓库战斗引入铁爪鼬",
            "- 商城首次购买唐刀",
            "- 王磊金刚体觉醒",
            "- 倒计时17天",
            "- 全市12个红点",
        ]
    )
    assert is_outline_or_meta_content(text)
