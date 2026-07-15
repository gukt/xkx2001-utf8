"""pilot 共享桩：新引擎缺失的 LPC 等价行为占位。

ADR-0048 决策 2：多个 pending/logic 样本共用这些缺口 API，pilot 前
一次性补建最小可用桩，避免每样本重复建。

桩为"最小等价行为占位"：满足调用契约（参数/返回/副作用语义），行为
按首个依赖样本（xue.c:main）的需求补全，不追求完整，仅保证调用通过 +
主路径行为等价。后续样本实测时按需细化。

注意：这是测量用桩，不是 src/xkx 正式实现。落一次性目录
（ADR-0048 决策 8），测完即丢，不污染 src/xkx。

桩清单（xue.c:main 实读 + ADR-0048 点名，6 桩；SKILL_D.type/valid_learn
已有简化版见 combat/context.py，不重建）：
- is_spouse_of(me, ob) -> bool           （xue L53,80,91,93 配偶链）
- recognize_apprentice(me) -> bool        （xue L53 ob 侧付费认可）
- prevent_learn(me, skill) -> bool       （xue L74 师傅侧门控）
- query_skill_name(skill, level) -> str  （xue L124 招式名）
- to_chinese(skill) -> str               （xue L102,107 技能中文名）
- receive_damage(entity, vital, amount)  （xue L110,148 通用 vital 扣减）
"""

from __future__ import annotations

from typing import Any

from xkx.runtime.components import Vitals


def is_spouse_of(world: Any, me_id: int, ob_id: int) -> bool:
    """双向配偶校验（对照 xue.c L53,80,91,93）。

    桩：默认 False（新引擎无 MarriageComp）。
    真实：需 MarriageComp + 双向校验 + married_times/spouse/title
    （xue.c L80-88 配偶婚次惩罚 + 实战经验门控）。
    """
    return False


def recognize_apprentice(world: Any, me_id: int, ob_id: int) -> bool:
    """ob 侧付费认可学徒（对照 xue.c L50-53）。

    桩：默认 False。真实含 mark/朱 事务性 add/回滚（L91-93）+
    potential 扣费。xue.c L50-51 注释：recognize_apprentice 内部
    处理 literate 付费，learn_times 次循环外部已处理（L52）。
    """
    return False


def prevent_learn(world: Any, ob_id: int, me_id: int, skill_id: str) -> bool:
    """师傅侧可教白/黑名单门控（对照 xue.c L74）。

    桩：默认 False（可教）。返回 True = 拒绝教。
    真实：师傅 NPC 的可教技能白名单/黑名单逻辑。
    """
    return False


def query_skill_name(skill_id: str, level: int) -> str | None:
    """技能招式名（对照 xue.c L124 SKILL_D->query_skill_name）。

    桩：默认 None（无招式名表，xue.c L132-133 走"似乎有些心得"兜底）。
    真实：SkillData 增招式表字段，按 level 返回招式名。
    """
    return None


def to_chinese(skill_id: str) -> str:
    """技能 id -> 中文名（对照 xue.c L102,107 to_chinese）。

    桩：默认返回 skill_id（占位，无中文名映射表）。
    真实：技能 id -> 中文名映射表。
    """
    return skill_id


def receive_damage(world: Any, entity_id: int, vital: str, amount: int) -> None:
    """通用 vital 扣减（对照 xue.c L110,148 receive_damage）。

    新引擎当前仅 combat apply 有 damage，runtime 无通用扣减
    （learn() 直接 vitals.jing -= gin_cost，无 clamp）。
    桩：扣 Vitals.<vital>，clamp >=0（行为等价 learn.c receive_damage）。
    """
    vitals = world.get(entity_id, Vitals)
    if vitals is None:
        return
    cur = getattr(vitals, vital, None)
    if cur is None:
        return
    setattr(vitals, vital, max(0, cur - amount))
