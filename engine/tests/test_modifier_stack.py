"""ModifierStack + Equipment 测试（阶段 2.3，ADR-0026）。

覆盖：
- Equipment 组件 + wield/wear/unequip 语义（prop 注入/扣减 + 槽位 + reset_action）
- ModifierStack 三类叠加（永久基础值 + 临时修正 apply_* + 装备加成）
- query_skill 三层叠加（apply/{skill} + levels/2 + skill_map，对照 skill.c:94-109）
- 负重（add_encumbrance/total_weight）
- apply/ 路径前缀 + equipped 语义 key（ADR-0026 §3 后置 key 激活）
- death 衔接（make_corpse 装备重穿 + skill_death_penalty learned 公式）
- hypothesis 属性测试（三类叠加交换律 + unequip 回归 condition-only）
- 主题无关性（Equipment 源码无武侠字面量）

[ADR-0026](../../../docs/adr/ADR-0026-modifier-stack-and-skill-layers.md)
"""

from __future__ import annotations

import inspect

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime import equipment as equipment_mod
from xkx.runtime.components import (
    CombatState,
    Equipment,
    Inventory,
    Skills,
)
from xkx.runtime.dbase_map import DbaseKeyError
from xkx.runtime.death import make_corpse, skill_death_penalty
from xkx.runtime.ecs import World
from xkx.runtime.equipment import (
    SECONDARY,
    TWO_HANDED,
    add_encumbrance,
    is_equipped,
    total_weight,
    unequip,
    wear,
    wield,
)
from xkx.runtime.query import (
    effective_apply,
    effective_skill_level,
    query,
    query_skill,
    set,
)
from xkx.runtime.schema import SchemaRegistry
from xkx.runtime.world import spawn_player


def _make_world_with_player() -> tuple[World, int]:
    """创建带玩家的 world（spawn_player 含 Equipment 组件，2.3）。"""
    world = World(SchemaRegistry.with_builtins())
    eid = spawn_player(world, "测试玩家", "test/room")
    return world, eid


# ──────────────────────── wield / wear / unequip ────────────────────────


def test_wield_weapon_injects_apply_and_resets_action() -> None:
    """wield 武器：注入 apply_* + 存 prop 副本 + 更新 CombatState。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    assert skills.apply_attack == 0
    ok = wield(
        world, eid, "sword",
        props={"attack": 10, "damage": 5},
        skill="sword", label="长剑",
    )
    assert ok is True
    equipment = world.get(eid, Equipment)
    assert equipment.weapon == "sword"
    assert skills.apply_attack == 10
    assert skills.apply_damage == 5
    assert equipment.weapon_props == {"attack": 10, "damage": 5}
    combat = world.get(eid, CombatState)
    assert combat.attack_skill == "sword"
    assert combat.weapon_label == "长剑"


def test_wield_idempotent() -> None:
    """已装备幂等返回 True（不重复注入 apply）。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10})
    skills = world.get(eid, Skills)
    assert skills.apply_attack == 10
    ok = wield(world, eid, "sword", props={"attack": 10})
    assert ok is True
    assert skills.apply_attack == 10  # 不重复累加


def test_wield_main_hand_occupied_returns_false() -> None:
    """主手已占用返回 False（不自动切换，后置 2.4）。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10})
    ok = wield(world, eid, "blade", props={"attack": 5})
    assert ok is False
    assert world.get(eid, Equipment).weapon == "sword"


def test_wield_two_handed_needs_both_hands() -> None:
    """双手武器需空出双手（weapon + secondary + shield）。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10})
    ok = wield(world, eid, "heavyaxe", props={"attack": 20}, flag=TWO_HANDED)
    assert ok is False  # 主手已占
    # 空手双手武器成功
    world2, eid2 = _make_world_with_player()
    ok2 = wield(world2, eid2, "heavyaxe", props={"attack": 20}, flag=TWO_HANDED)
    assert ok2 is True


def test_wield_secondary_weapon() -> None:
    """SECONDARY flag 装备到副手。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10})  # 主手
    ok = wield(world, eid, "dagger", props={"attack": 3}, flag=SECONDARY)
    assert ok is True
    equipment = world.get(eid, Equipment)
    assert equipment.weapon == "sword"
    assert equipment.secondary_weapon == "dagger"
    assert world.get(eid, Skills).apply_attack == 13


def test_wear_armor_injects_apply() -> None:
    """wear 护甲：注入 apply_* + 存 armor_props 副本。"""
    world, eid = _make_world_with_player()
    ok = wear(world, eid, "leather", props={"armor": 8, "dodge": -2}, armor_type="cloth")
    assert ok is True
    equipment = world.get(eid, Equipment)
    assert equipment.armors["cloth"] == "leather"
    skills = world.get(eid, Skills)
    assert skills.apply_armor == 8
    assert skills.apply_dodge == -2
    assert equipment.armor_props["cloth"] == {"armor": 8, "dodge": -2}


def test_wear_same_type_fails() -> None:
    """同类型护甲已穿戴返回 False。"""
    world, eid = _make_world_with_player()
    wear(world, eid, "leather", props={"armor": 8}, armor_type="cloth")
    ok = wear(world, eid, "chain", props={"armor": 12}, armor_type="cloth")
    assert ok is False
    assert world.get(eid, Equipment).armors["cloth"] == "leather"


def test_wear_empty_armor_type_fails() -> None:
    """空 armor_type 返回 False。"""
    world, eid = _make_world_with_player()
    ok = wear(world, eid, "leather", props={"armor": 8}, armor_type="")
    assert ok is False


def test_unequip_weapon_reverses_apply() -> None:
    """unequip 武器：按 prop 副本反向扣减 apply_*。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10, "damage": 5})
    skills = world.get(eid, Skills)
    assert skills.apply_attack == 10
    ok = unequip(world, eid, "sword")
    assert ok is True
    assert skills.apply_attack == 0
    assert skills.apply_damage == 0
    equipment = world.get(eid, Equipment)
    assert equipment.weapon is None
    assert equipment.weapon_props == {}


def test_unequip_armor_reverses_apply() -> None:
    """unequip 护甲：按 prop 副本反向扣减。"""
    world, eid = _make_world_with_player()
    wear(world, eid, "leather", props={"armor": 8, "dodge": -2}, armor_type="cloth")
    ok = unequip(world, eid, "leather")
    assert ok is True
    skills = world.get(eid, Skills)
    assert skills.apply_armor == 0
    assert skills.apply_dodge == 0
    assert "cloth" not in world.get(eid, Equipment).armors


def test_unequip_not_equipped_returns_false() -> None:
    """未装备返回 False。"""
    world, eid = _make_world_with_player()
    assert unequip(world, eid, "nothing") is False


def test_wield_unknown_prop_key_ignored() -> None:
    """未知 prop key（武侠特有等）忽略，后置 2.7 题材扩展。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10, "cimu_power": 5})
    skills = world.get(eid, Skills)
    assert skills.apply_attack == 10  # attack 注入
    # cimu_power 未知，忽略（无对应标量，不报错）


def test_is_equipped() -> None:
    """is_equipped 判断物品是否已装备。"""
    world, eid = _make_world_with_player()
    equipment = world.get(eid, Equipment)
    assert is_equipped(equipment, "sword") is False
    wield(world, eid, "sword", props={"attack": 10})
    assert is_equipped(equipment, "sword") is True
    assert is_equipped(equipment, "blade") is False


# ──────────────────────── 负重 ────────────────────────


def test_add_encumbrance_and_total_weight() -> None:
    """add_encumbrance 累加 + total_weight 返回 encumbrance。"""
    world, eid = _make_world_with_player()
    equipment = world.get(eid, Equipment)
    assert total_weight(equipment) == 0
    add_encumbrance(world, eid, 50)
    assert total_weight(equipment) == 50
    add_encumbrance(world, eid, -20)
    assert total_weight(equipment) == 30


# ──────────────────────── ModifierStack 三类叠加 / query_skill ────────────────────────


def test_query_skill_raw_returns_level() -> None:
    """raw 模式返回 levels 原值。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels["unarmed"] = 30
    assert query_skill(world, eid, "unarmed", raw=True) == 30
    assert query_skill(world, eid, "nosuchskill", raw=True) == 0


def test_query_skill_three_layers() -> None:
    """query_skill 非 raw 三层叠加（apply + levels/2 + skill_map）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels["unarmed"] = 30
    skills.levels["daxe"] = 20
    skills.skill_map["unarmed"] = "daxe"
    skills.apply_attack = 8
    # unarmed: apply/unarmed(0) + 30/2(15) + daxe(20) = 35
    assert query_skill(world, eid, "unarmed") == 35
    # attack skill: apply_attack(8) + 0 + 0 = 8
    assert query_skill(world, eid, "attack") == 8


def test_query_skill_no_skills_returns_zero() -> None:
    """无 Skills 组件返回 0。"""
    world = World(SchemaRegistry.with_builtins())
    eid = world.new_entity()
    assert query_skill(world, eid, "unarmed") == 0


def test_effective_apply_returns_known_scalar() -> None:
    """effective_apply 返回已知 6 个标量；未知返回 0。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.apply_attack = 15
    skills.apply_speed = 5
    assert effective_apply(world, eid, "attack") == 15
    assert effective_apply(world, eid, "speed") == 5
    assert effective_apply(world, eid, "unarmed") == 0  # 未知 apply_key


def test_effective_skill_level_delegates_query_skill() -> None:
    """effective_skill_level 委托 query_skill。"""
    world, eid = _make_world_with_player()
    world.get(eid, Skills).levels["unarmed"] = 40
    assert effective_skill_level(world, eid, "unarmed") == 40 // 2


# ──────────────────────── apply/ 路径前缀 + equipped 语义 key ────────────────────────


def test_apply_path_query_returns_scalar() -> None:
    """apply/attack 路径读返回 Skills.apply_attack 标量。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.apply_attack = 12
    assert query(world, eid, "apply/attack") == 12
    assert query(world, eid, "apply/speed") == 0


def test_apply_path_set_writes_scalar() -> None:
    """apply/attack 路径写 Skills.apply_attack 标量。"""
    world, eid = _make_world_with_player()
    set(world, eid, "apply/attack", 20)
    assert world.get(eid, Skills).apply_attack == 20


def test_apply_unknown_subpath_query_returns_zero() -> None:
    """apply/unarmed 未知子路径读返回 0（LPC query_temp 未设，通用后置 M3）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "apply/unarmed") == 0
    assert query(world, eid, "apply/foobar") == 0


def test_apply_unknown_subpath_set_raises() -> None:
    """apply/unarmed 未知子路径 set raise（无存储）。"""
    world, eid = _make_world_with_player()
    try:
        set(world, eid, "apply/unarmed", 5)
        raise AssertionError("应 raise DbaseKeyError")
    except DbaseKeyError as exc:
        assert "无存储" in str(exc)


def test_equipped_semantic_query_returns_set() -> None:
    """query('equipped') 返回装备物品集合（语义 key，ADR-0026 §3）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "equipped") == frozenset()
    wield(world, eid, "sword", props={"attack": 10})
    wear(world, eid, "leather", props={"armor": 5}, armor_type="cloth")
    assert query(world, eid, "equipped") == frozenset({"sword", "leather"})


def test_equipped_semantic_set_raises() -> None:
    """set('equipped') raise（装备走 wield/wear）。"""
    world, eid = _make_world_with_player()
    try:
        set(world, eid, "equipped", "sword")
        raise AssertionError("应 raise DbaseKeyError")
    except DbaseKeyError as exc:
        assert "语义 key" in str(exc)


# ──────────────────────── death 衔接（2.2 stub 补全） ────────────────────────


def test_make_corpse_unequips_and_transfers() -> None:
    """make_corpse 卸下装备（反向扣减 apply_*）+ 装备物品转移尸体。"""
    world, eid = _make_world_with_player()
    wield(world, eid, "sword", props={"attack": 10})
    wear(world, eid, "leather", props={"armor": 5}, armor_type="cloth")
    skills = world.get(eid, Skills)
    assert skills.apply_attack == 10
    assert skills.apply_armor == 5
    corpse_id = make_corpse(world, eid)
    assert corpse_id is not None
    # 装备卸下：apply_* 扣减回 0
    assert skills.apply_attack == 0
    assert skills.apply_armor == 0
    equipment = world.get(eid, Equipment)
    assert equipment.weapon is None
    assert "cloth" not in equipment.armors
    # 装备物品转移到尸体 Inventory
    corpse_inv = world.get(corpse_id, Inventory)
    assert "sword" in corpse_inv.items
    assert "leather" in corpse_inv.items


def test_skill_death_penalty_no_learned() -> None:
    """无 learned：所有技能降级 + 设 learned[sk]=(降后 lvl+1)²/2（skill.c:121-134）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels = {"unarmed": 30, "dodge": 20}
    skills.learned = {}
    ok = skill_death_penalty(world, eid)
    assert ok is True
    assert skills.levels["unarmed"] == 29
    assert skills.levels["dodge"] == 19
    assert skills.learned["unarmed"] == 30 * 30 // 2  # (29+1)²/2 = 450
    assert skills.learned["dodge"] == 20 * 20 // 2  # (19+1)²/2 = 200


def test_skill_death_penalty_with_learned_below_threshold() -> None:
    """有 learned 且 < 阈值：降级 + 累加 learned（skill.c:136-144）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels = {"unarmed": 30}
    skills.learned = {"unarmed": 100}  # threshold=(30+1)²/2=480, 100 < 480
    skill_death_penalty(world, eid)
    assert skills.levels["unarmed"] == 29
    # learned = 100 + (29+1)²/2 = 100 + 450 = 550
    assert skills.learned["unarmed"] == 100 + 30 * 30 // 2


def test_skill_death_penalty_with_learned_above_threshold() -> None:
    """有 learned 且 > 阈值：扣 learned 不降级（skill.c:137-138）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels = {"unarmed": 30}
    skills.learned = {"unarmed": 1000}  # > 480 -> 扣 learned
    skill_death_penalty(world, eid)
    assert skills.levels["unarmed"] == 30  # 不降级
    # threshold = (30+1)²/2 = 480；learned = 1000 - 480 = 520
    assert skills.learned["unarmed"] == 1000 - (30 + 1) * (30 + 1) // 2


def test_skill_death_penalty_clears_skill_map() -> None:
    """skill_death_penalty 清空 skill_map（LPC skill_map = 0）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels = {"unarmed": 30}
    skills.skill_map = {"unarmed": "daxe"}
    skill_death_penalty(world, eid)
    assert skills.skill_map == {}


def test_skill_death_penalty_no_skills_returns_false() -> None:
    """无 Skills 或空 levels 返回 False。"""
    world, eid = _make_world_with_player()
    world.get(eid, Skills).levels = {}
    assert skill_death_penalty(world, eid) is False


# ──────────────────────── hypothesis 属性测试 ────────────────────────


@given(
    level=st.integers(min_value=0, max_value=200),
    mapped_level=st.integers(min_value=0, max_value=200),
    apply=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=50)
def test_query_skill_three_layer_formula(
    level: int, mapped_level: int, apply: int
) -> None:
    """query_skill 非 raw = apply/{skill} + levels[skill]/2 + levels[skill_map[skill]]。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    skills.levels = {"unarmed": level, "daxe": mapped_level}
    skills.skill_map = {"unarmed": "daxe"}
    skills.apply_attack = apply
    # unarmed：apply/unarmed(0) + level/2 + mapped_level
    assert query_skill(world, eid, "unarmed") == level // 2 + mapped_level
    assert query_skill(world, eid, "unarmed", raw=True) == level
    # attack：apply_attack + 0 + 0
    assert query_skill(world, eid, "attack") == apply


@given(
    equip_val=st.integers(min_value=-50, max_value=100),
    cond_val=st.integers(min_value=-50, max_value=100),
)
@settings(max_examples=50)
def test_equip_condition_additive_commutative(equip_val: int, cond_val: int) -> None:
    """装备加成与 condition 修正叠加满足交换律（apply_* 累加标量，ADR-0026 §1）。"""
    # 顺序 A：先装备后 condition
    w1, e1 = _make_world_with_player()
    wield(w1, e1, "sword", props={"attack": equip_val})
    w1.get(e1, Skills).apply_attack += cond_val
    v1 = w1.get(e1, Skills).apply_attack
    # 顺序 B：先 condition 后装备
    w2, e2 = _make_world_with_player()
    w2.get(e2, Skills).apply_attack += cond_val
    wield(w2, e2, "sword", props={"attack": equip_val})
    v2 = w2.get(e2, Skills).apply_attack
    assert v1 == v2 == equip_val + cond_val


@given(
    equip_val=st.integers(min_value=0, max_value=100),
    cond_val=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=50)
def test_unequip_preserves_condition_only(equip_val: int, cond_val: int) -> None:
    """equip + condition 同 key 后 unequip，apply_* 回到 condition-only（dissent 3）。"""
    world, eid = _make_world_with_player()
    skills = world.get(eid, Skills)
    wield(world, eid, "sword", props={"attack": equip_val})
    skills.apply_attack += cond_val  # condition 修正（模拟 EffectComp 驱动）
    unequip(world, eid, "sword")
    # 装备按副本扣减 equip_val，condition 修正 cond_val 保留
    assert skills.apply_attack == cond_val


# ──────────────────────── 主题无关性硬门禁（ADR-0003） ────────────────────────


def test_equipment_source_has_no_wuxia_literals() -> None:
    """equipment.py 源码不含 sword/blade/family 字符串字面量（主题无关性硬门禁）。

    装备槽 weapon/secondary_weapon/armors 是通用 item_id/armor_type 字符串，
    内核不解释具体武器/护甲名（由题材数据声明，ADR-0003/0026）。
    """
    src = inspect.getsource(equipment_mod)
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src
    assert '"family"' not in src and "'family'" not in src


def test_equipment_component_no_wuxia_fields() -> None:
    """Equipment 组件字段无武侠语义（weapon 是通用 item_id，非武侠烙印）。"""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(Equipment)}
    assert "weapon" in field_names  # 通用物品 id 字段
    assert "armors" in field_names  # 通用 armor_type -> item_id
    # 无武侠特有字段（如 sword_type/martial_art 等）
    for name in field_names:
        assert "sword" not in name and "blade" not in name
        assert "wuxia" not in name and "martial" not in name
