"""CombatKernel 主题无关性硬门禁（04 kill criteria 2 / 范围检查点 2）。

验证核心战斗引擎不硬编码武侠语义：
1. 非武侠题材（火器/戒尺）snapshot 跑 resolve_attack，武器->技能/标签映射走题材
   数据声明（attack_skill/weapon_label），不 fallback 到武侠默认；
2. resolve_attack 模块源码不含 sword/blade 字符串字面量（防回归硬门禁）；
3. neili（内力）不在 CombatantSnapshot 核心签名（ADR-0003）。

关联 [05] dissent 1（CombatKernel 抽象时机张力）：从武侠提取的接口用非武侠验证。
"""

from __future__ import annotations

import inspect

from xkx.combat import resolve_attack as resolve_attack_mod
from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import KIND_SKILL_IMPROVE, RESULT_HIT


def _firearm_attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1,
        name="海盗",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"firearm": 80},
        weapon="firearm",
        attack_skill="firearm",
        weapon_label="火枪",
        action_message="$N端起$w，对准$n$l",
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _ruler_attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=3,
        name="监生",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"ruler": 80},
        weapon="ruler",
        attack_skill="ruler",
        weapon_label="戒尺",
        action_message="$N挥起$w，抽向$n$l",
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2,
        name="靶子",
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=10,
        qi=10,
    )


def test_firearm_theme_runs_and_uses_declared_mapping() -> None:
    """火器题材：resolve_attack 走声明的 attack_skill=firearm / weapon_label=火枪。"""
    ctx = CombatContext(attacker=_firearm_attacker(), victim=_victim(), seed=0)
    r = resolve_attack(ctx)
    assert r.result_code == RESULT_HIT
    # weapon_label 走题材声明（$w 替换），非内核 fallback
    assert any("火枪" in m for m in r.messages)
    # attack_skill 走题材声明 -> skill_improve detail=firearm
    improves = [e for e in r.effects if e.kind == KIND_SKILL_IMPROVE]
    assert improves and improves[0].detail == "firearm"


def test_ruler_theme_runs_and_uses_declared_mapping() -> None:
    """戒尺题材：同样验证非武侠武器映射走题材声明。"""
    ctx = CombatContext(attacker=_ruler_attacker(), victim=_victim(), seed=0)
    r = resolve_attack(ctx)
    assert r.result_code == RESULT_HIT
    assert any("戒尺" in m for m in r.messages)
    improves = [e for e in r.effects if e.kind == KIND_SKILL_IMPROVE]
    assert improves and improves[0].detail == "ruler"


def test_non_wuxia_deterministic_replay() -> None:
    """非武侠 snapshot 同 seed 同输出（combat 确定性不绑题材）。"""
    ctx = CombatContext(attacker=_firearm_attacker(), victim=_victim(), seed=123)
    assert resolve_attack(ctx) == resolve_attack(ctx)


def test_resolve_attack_source_has_no_wuxia_weapon_literals() -> None:
    """防回归硬门禁：resolve_attack 模块源码不得含 sword/blade 字符串字面量。"""
    src = inspect.getsource(resolve_attack_mod)
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src


def test_neili_not_in_core_snapshot() -> None:
    """ADR-0003：内力（neili）不进 CombatantSnapshot 核心签名。"""
    fields = CombatantSnapshot.model_fields
    assert "neili" not in fields
    assert "max_neili" not in fields
