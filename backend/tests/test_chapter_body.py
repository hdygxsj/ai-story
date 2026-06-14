import pytest

from app.agent.chapter_body import is_outline_or_meta_content


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
