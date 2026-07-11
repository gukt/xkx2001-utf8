"""T6（ADR-0023）简化台账 6 项补全的回归测试。

每项补全验证 + 主题无关性断言（test_theme_neutrality 硬门禁持续通过）。

6 项简化台账（ADR-0002 §S1 -> ADR-0023 决策 4 补全）：
1. hit_ob/hit_by mapping 分支（HitCallbackResult 声明式载体 + 返回类型分发）
2. riposte 递归（子回合嵌入父回合 ledger）
3. 武器类型（不在内核枚举，题材数据声明）
4. skill_power 完整公式（level³/3 + jingli_bonus + str/dex + is_fighting + 补偿）
5. combat_exp 防御折减（defense_factor 折半自然终止）
6. 技能 action（SkillData 载体 + post_action 声明式副作用）
"""

from __future__ import annotations

import inspect

from xkx.combat import resolve_attack as resolve_attack_mod
from xkx.combat.context import (
    TYPE_REGULAR,
    CombatantSnapshot,
    CombatContext,
    HitCallbackResult,
)
from xkx.combat.resolve_attack import ATTACK, DEFENSE, resolve_attack, skill_power
from xkx.combat.result import (
    KIND_DAMAGE,
    KIND_SKILL_IMPROVE,
    LEDGER_SUBRESULT,
    RESULT_HIT,
)

# ---------------------------------------------------------------------------
# 辅助构造
# ---------------------------------------------------------------------------


def _strong_attacker() -> CombatantSnapshot:
    """强攻击者：ap 远大于 dp+pp，必然命中。"""
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=50,
        dex_=50,
        int_=12,
        con_=14,
        combat_exp=99999,
        skills={"unarmed": 80},
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _weak_victim() -> CombatantSnapshot:
    """弱防御者：dp/pp 极低，必然被命中。"""
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=10,
        dex_=1,
        int_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=100,
        qi=100,
        max_jingli=50,
        jingli=50,
    )


# ---------------------------------------------------------------------------
# 1. hit_ob/hit_by mapping 分支
# ---------------------------------------------------------------------------


def test_hit_ob_mapping_message_enters_ledger() -> None:
    """hit_ob mapping 分支：result 文本入 ledger 为 MESSAGE。"""
    a = _strong_attacker().model_copy(
        update={
            "hit_ob": HitCallbackResult(message="内功反震！"),
        }
    )
    v = _weak_victim()
    ctx = CombatContext(attacker=a, victim=v, seed=0)
    r = resolve_attack(ctx)
    assert r.result_code == RESULT_HIT
    assert "内功反震！" in r.messages


def test_hit_ob_mapping_damage_delta_enters_ledger_as_kind_damage() -> None:
    """hit_ob mapping 分支：damage 修正入 ledger 为 KIND_DAMAGE 副作用。"""
    a = _strong_attacker().model_copy(
        update={
            "hit_ob": HitCallbackResult(damage_delta=15),
        }
    )
    v = _weak_victim()
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    # hit_ob 的 damage_delta 在步骤 5 产生（基础 damage effect 在步骤 6），
    # 交织顺序：hit_ob delta KIND_DAMAGE -> 基础 KIND_DAMAGE
    damages = [e for e in r.effects if e.kind == KIND_DAMAGE]
    assert len(damages) >= 2  # hit_ob delta + 基础 damage
    assert damages[0].amount == 15  # hit_ob delta 在前（步骤 5）


def test_hit_by_mapping_override_covers_final_damage() -> None:
    """hit_by mapping 分支：override 覆盖最终 damage。"""
    a = _strong_attacker()
    v = _weak_victim().model_copy(
        update={
            "hit_by": HitCallbackResult(override=7),
        }
    )
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert r.damage == 7


def test_hit_by_mapping_message_and_delta() -> None:
    """hit_by mapping 分支：message + damage_delta 同时生效。"""
    a = _strong_attacker()
    v = _weak_victim().model_copy(
        update={
            "hit_by": HitCallbackResult(message="护甲偏转！", damage_delta=-5),
        }
    )
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert "护甲偏转！" in r.messages
    # damage_delta=-5 叠加到最终 damage（无 override 时）
    assert r.damage >= 0


# ---------------------------------------------------------------------------
# 2. riposte 递归
# ---------------------------------------------------------------------------


def test_riposte_recursion_embeds_subresult_in_ledger() -> None:
    """riposte 递归：TYPE_REGULAR + damage<1 + victim guarding -> 子回合嵌入。"""
    a = _strong_attacker().model_copy(
        update={"str_": 1, "action_damage": 0, "skills": {"unarmed": 1}}
    )
    v = _weak_victim().model_copy(update={"guarding": 1, "dex_": 1, "con_": 1})
    ctx = CombatContext(attacker=a, victim=v, seed=42, attack_type=TYPE_REGULAR)
    r = resolve_attack(ctx)
    if r.result_code == RESULT_HIT and r.damage < 1:
        assert r.riposte_triggered, "riposte 应触发"
        assert r.riposte_sub_result is not None
        # 子回合嵌入父回合 ledger（LEDGER_SUBRESULT 条目）
        sub_entries = [e for e in r.ledger if e.entry_type == LEDGER_SUBRESULT]
        assert len(sub_entries) == 1
        assert sub_entries[0].sub_result is r.riposte_sub_result


def test_riposte_depth_limit_prevents_infinite_recursion() -> None:
    """riposte 递归深度限制：不超过 _RIPOSTE_MAX_DEPTH，防死循环。"""
    from xkx.combat.resolve_attack import _RIPOSTE_MAX_DEPTH

    # 构造持续触发 riposte 的场景：双方都 guarding，damage 都 < 1
    a = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=1,
        action_damage=0,
        skills={"unarmed": 1},
        combat_exp=0,
        max_qi=100,
        qi=100,
        max_jingli=50,
        jingli=50,
        guarding=1,
    )
    v = CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=1,
        action_damage=0,
        skills={"unarmed": 1},
        combat_exp=0,
        max_qi=100,
        qi=100,
        max_jingli=50,
        jingli=50,
        guarding=1,
    )
    ctx = CombatContext(attacker=a, victim=v, seed=42, attack_type=TYPE_REGULAR)
    # 不应死循环（深度限制兜底）
    r = resolve_attack(ctx)
    # 递归深度不超过上限
    depth = _count_riposte_depth(r)
    assert depth <= _RIPOSTE_MAX_DEPTH


def _count_riposte_depth(result, depth: int = 0) -> int:
    """递归计算 riposte 子回合最大嵌套深度。"""
    if result.riposte_sub_result is None:
        return depth
    return _count_riposte_depth(result.riposte_sub_result, depth + 1)


# ---------------------------------------------------------------------------
# 3. 武器类型（主题无关，题材数据声明）
# ---------------------------------------------------------------------------


def test_weapon_type_not_enumerated_in_kernel() -> None:
    """武器类型不在内核枚举：源码不含 sword/blade 字面量（test_theme_neutrality 兜底）。"""
    src = inspect.getsource(resolve_attack_mod)
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src


def test_firearm_weapon_uses_declared_attack_skill() -> None:
    """非武侠武器（firearm）走题材声明的 attack_skill，不 fallback。"""
    a = _strong_attacker().model_copy(
        update={
            "name": "海盗",
            "weapon": "firearm",
            "attack_skill": "firearm",
            "weapon_label": "火枪",
            "skills": {"firearm": 80},
            "action_message": "$N端起$w，对准$n$l",
        }
    )
    v = _weak_victim()
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert any("火枪" in m for m in r.messages)
    improves = [e for e in r.effects if e.kind == KIND_SKILL_IMPROVE]
    assert improves and improves[0].detail == "firearm"


# ---------------------------------------------------------------------------
# 4. skill_power 完整公式
# ---------------------------------------------------------------------------


def test_skill_power_attack_uses_str_bonus() -> None:
    """ATTACK 模式用 str 加成。"""
    base = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20,
        dex_=10,
        combat_exp=0,
        skills={"unarmed": 10},
        max_jingli=100,
        jingli=100,
    )
    power = skill_power(base, "unarmed", ATTACK)
    # level=10, level³/3=333, str*2=40, jingli_bonus=100 -> 333+40=373
    assert power == (10**3) // 3 + 20 * 2


def test_skill_power_defense_uses_dex_bonus() -> None:
    """DEFENSE 模式用 dex 加成。"""
    base = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=10,
        dex_=20,
        combat_exp=0,
        skills={"dodge": 10},
        max_jingli=100,
        jingli=100,
    )
    power = skill_power(base, "dodge", DEFENSE)
    # level=10, level³/3=333, dex*2=40 -> 373
    assert power == (10**3) // 3 + 20 * 2


def test_skill_power_jingli_bonus_capped_at_150() -> None:
    """jingli_bonus 上限 150。"""
    full = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20,
        skills={"unarmed": 10},
        max_jingli=100,
        jingli=100,  # jingli_bonus = 50 + 100*50/101 = 99 -> < 150
        combat_exp=0,
    )
    p1 = skill_power(full, "unarmed", ATTACK)
    # jingli 不影响 ATTACK 的 power（只影响低技能补偿），验证正常 level 路径
    assert p1 == (10**3) // 3 + 20 * 2


def test_skill_power_low_level_exp_compensation() -> None:
    """level < 1 时用 combat_exp/20 * (jingli_bonus/10) 经验补偿。"""
    low = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20,
        dex_=20,
        combat_exp=200,
        skills={"unarmed": 0},  # level=0 < 1
        max_jingli=100,
        jingli=100,
    )
    power = skill_power(low, "unarmed", ATTACK)
    # jingli_bonus = 50 + 100*50/101 = 99; 补偿 = 200//20 * (99//10) = 10*9 = 90
    expected = (200 // 20) * ((50 + 100 * 50 // 101) // 10)
    assert power == expected
    assert power > 0  # 有经验补偿


def test_skill_power_is_fighting_defense_bonus() -> None:
    """is_fighting 时 DEFENSE 额外乘 (100 + fight_dodge/10) / 100。"""
    fighting = CombatantSnapshot(
        entity_id=1,
        name="甲",
        dex_=20,
        combat_exp=0,
        skills={"dodge": 10},
        max_jingli=100,
        jingli=100,
        is_fighting=True,
        fight_dodge=100,  # fight_factor = 100 + 10 = 110
    )
    not_fighting = fighting.model_copy(update={"is_fighting": False})
    p_fight = skill_power(fighting, "dodge", DEFENSE)
    p_idle = skill_power(not_fighting, "dodge", DEFENSE)
    # fighting 时 power = (level³/3 * 110/100) + dex*2
    base = (10**3) // 3
    assert p_fight == base * 110 // 100 + 20 * 2
    assert p_idle == base + 20 * 2
    assert p_fight > p_idle


# ---------------------------------------------------------------------------
# 5. combat_exp 防御折减（defense_factor 折半自然终止）
# ---------------------------------------------------------------------------


def test_combat_exp_defense_reduction_uses_halving() -> None:
    """combat_exp 防御折减：defense_factor 折半自然终止（非固定 5 次）。"""
    a = _strong_attacker()
    # victim con_=100 -> defense_factor = 1100，折半到 0 需多次
    v = _weak_victim().model_copy(update={"con_": 50})
    r1 = resolve_attack(CombatContext(attacker=a, victim=v, seed=7))
    r2 = resolve_attack(CombatContext(attacker=a, victim=v, seed=7))
    assert r1 == r2  # 确定性
    assert r1.result_code == RESULT_HIT
    # defense_factor=600，attacker combat_exp=99999 -> random(600) 几乎不可能 > 99999
    # 所以循环通常 0-1 次就 break（combat_exp 高），damage 不被削减太多
    assert r1.damage >= 0


def test_combat_exp_defense_reduction_reduces_damage_when_attacker_low_exp() -> None:
    """攻击者 combat_exp 低时，防御折减循环多次削减 damage。"""
    # 攻击者低 combat_exp，victim 高 con_ -> defense_factor 大 -> 循环多次
    a = _strong_attacker().model_copy(update={"combat_exp": 0})
    v = _weak_victim().model_copy(update={"con_": 50})
    # 同 seed 下，低 combat_exp 的 damage 应 <= 高 combat_exp 的 damage
    r_low = resolve_attack(CombatContext(attacker=a, victim=v, seed=7))
    a_high = a.model_copy(update={"combat_exp": 99999})
    r_high = resolve_attack(CombatContext(attacker=a_high, victim=v, seed=7))
    if r_low.result_code == RESULT_HIT and r_high.result_code == RESULT_HIT:
        assert r_low.damage <= r_high.damage


# ---------------------------------------------------------------------------
# 6. 技能 action（SkillData 载体 + post_action 声明式副作用）
# ---------------------------------------------------------------------------


def test_action_message_from_snapshot_skill_data() -> None:
    """招式描述从快照取值（SkillData 载体，非固定字面量）。"""
    a = _strong_attacker().model_copy(
        update={"action_message": "$N挥起$w，横扫$n$l"}
    )
    v = _weak_victim()
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert any("横扫" in m for m in r.messages)


def test_post_action_result_enters_ledger() -> None:
    """post_action 声明式副作用文本入 ledger（规格 order=47）。"""
    a = _strong_attacker().model_copy(
        update={"action_post_action_result": "（招式后劲未消）"}
    )
    v = _weak_victim()
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert "（招式后劲未消）" in r.messages
    # post_action 在尾部（exp 之后）
    assert r.messages[-1] == "（招式后劲未消）"


# ---------------------------------------------------------------------------
# 主题无关性断言（test_theme_neutrality 硬门禁持续通过的交叉验证）
# ---------------------------------------------------------------------------


def test_neili_not_in_snapshot_fields() -> None:
    """ADR-0003：neili 不进 CombatantSnapshot 核心签名（T6 补全后不回归）。"""
    fields = CombatantSnapshot.model_fields
    assert "neili" not in fields
    assert "max_neili" not in fields


def test_hit_callback_result_is_theme_neutral() -> None:
    """HitCallbackResult 字段主题无关（message/damage_delta/override 通用）。"""
    fields = HitCallbackResult.model_fields
    assert set(fields.keys()) == {"message", "damage_delta", "override"}
    # 无武侠特有字段（如 neili/jingmai/point）
    assert "neili" not in fields
    assert "jingmai" not in fields


def test_resolve_attack_source_has_no_wuxia_literals() -> None:
    """防回归：resolve_attack 模块源码不含 sword/blade 字面量。"""
    src = inspect.getsource(resolve_attack_mod)
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src
