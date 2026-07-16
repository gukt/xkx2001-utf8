"""装备系统（阶段 2.3，对照 LPC feature/equip.c wield/wear/unequip）。

装备槽管理 + prop 注入/扣减（对照 LPC ``add_temp("apply/" + key, prop[key])``
累加、``applied_prop[key] -= prop[key]`` 反向扣减）。装备加成在 equip 时注入
``Skills.apply_*`` 标量（注入式设计，ADR-0026 §1），unequip 按 per-slot prop
副本反向扣减，不依赖 apply_* 当前值（避免 LPC "中途 condition 改了同 key
导致扣减出错"的隐性 bug）。

**2.3 简化**（ADR-0026 §5 简化台账）：
- 双武器完整切换（辟邪剑/双手互博）后置 2.4 Combat（ADR-0023 §不做）。
- 物品重量/负重自动计算后置 M3 物品系统（wield/wear 不自动算重量，
  ``encumbrance`` 由调用方经 ``add_encumbrance`` 管理）。
- 未知 prop key（武侠特有等）忽略（后置 2.7 门派切割按题材数据声明补）。
- reset_action 完整逻辑后置（2.3 只在调用方传 skill/label 时更新 CombatState）。

[ADR-0026](../../../docs/adr/ADR-0026-modifier-stack-and-skill-layers.md) /
[feature/equip.c](../../../feature/equip.c) /
[include/weapon.h](../../../include/weapon.h)
"""

from __future__ import annotations

from xkx.runtime.components import CombatState, Equipment, Skills
from xkx.runtime.dbase_map import APPLY_SUBPATH_MAP
from xkx.runtime.ecs import World

# 武器 flag（include/weapon.h 位掩码）
TWO_HANDED = 1
SECONDARY = 2
EDGED = 4
POINTED = 8
LONG = 16
SELF_ACTION = 32


# ──────────────────────── prop 注入/扣减 ────────────────────────


def _inject_props(skills: Skills, props: dict[str, int], sign: int) -> None:
    """把 props 按 APPLY_SUBPATH_MAP 注入/扣减 Skills.apply_* 标量。

    sign=+1 注入（equip），-1 扣减（unequip）。未知 prop key（不在已知 6 个）
    忽略（后置 2.7 题材扩展），对齐 LPC add_temp 开放 mapping 的已知子路径子集。
    """
    for key, val in props.items():
        field = APPLY_SUBPATH_MAP.get(key)
        if field is None:
            continue  # 未知 prop key（武侠特有等），后置 2.7
        setattr(skills, field, getattr(skills, field) + sign * val)


# ──────────────────────── wield / wear / unequip ────────────────────────


def wield(
    world: World,
    eid: int,
    item_id: str,
    *,
    props: dict[str, int],
    flag: int = 0,
    skill: str = "",
    label: str = "",
) -> bool:
    """装备武器（对照 LPC equip.c wield，ADR-0026 §3）。

    Args:
        item_id: 武器物品 id。
        props: 武器属性（key: attack/dodge/parry/damage/armor/speed）。
        flag: 武器标记（TWO_HANDED/SECONDARY，include/weapon.h）。
        skill/label: 可选，更新 CombatState.attack_skill/weapon_label（reset_action）。

    返回是否成功（已装备幂等 True；槽位冲突 False）。双武器完整切换后置 2.4。
    """
    equipment = _get_or_create(world, eid)
    if is_equipped(equipment, item_id):
        return True  # 已装备幂等
    # flag 槽位检查（简化：不自动切换，后置 2.4）
    if flag & TWO_HANDED:
        # 双手武器需空出双手（weapon + secondary + shield）
        if equipment.weapon or equipment.secondary_weapon or "shield" in equipment.armors:
            return False
        slot = "weapon"
    elif flag & SECONDARY:
        if equipment.secondary_weapon:
            return False  # 副手已占用
        slot = "secondary"
    else:
        if equipment.weapon:
            return False  # 主手已占用（不自动切换，后置 2.4）
        slot = "weapon"
    skills = world.get(eid, Skills)
    if skills is None:
        skills = Skills()
        world.add(eid, skills)
    _inject_props(skills, props, +1)
    if slot == "weapon":
        equipment.weapon = item_id
        equipment.weapon_props = dict(props)
    else:
        equipment.secondary_weapon = item_id
        equipment.secondary_weapon_props = dict(props)
    # reset_action：传 skill/label 则更新 CombatState（2.3 最小，不完整推断）
    if skill or label:
        combat = world.get(eid, CombatState)
        if combat is not None:
            if skill:
                combat.attack_skill = skill
            if label:
                combat.weapon_label = label
    _mark_dirty(world, eid)
    return True


def wear(
    world: World,
    eid: int,
    item_id: str,
    *,
    props: dict[str, int],
    armor_type: str,
) -> bool:
    """穿戴护甲（对照 LPC equip.c wear，ADR-0026 §3）。

    Args:
        item_id: 护甲物品 id。
        props: 护甲属性（key: attack/dodge/parry/damage/armor/speed）。
        armor_type: 护甲类型（head/cloth/armor/...，题材数据声明，内核不枚举）。

    返回是否成功（已装备幂等 True；同类型已穿 False）。
    """
    if not armor_type:
        return False
    equipment = _get_or_create(world, eid)
    if is_equipped(equipment, item_id):
        return True
    if armor_type in equipment.armors:
        return False  # 同类型护甲已穿戴
    skills = world.get(eid, Skills)
    if skills is None:
        skills = Skills()
        world.add(eid, skills)
    _inject_props(skills, props, +1)
    equipment.armors[armor_type] = item_id
    equipment.armor_props[armor_type] = dict(props)
    _mark_dirty(world, eid)
    return True


def unequip(world: World, eid: int, item_id: str) -> bool:
    """卸下装备（对照 LPC equip.c unequip，ADR-0026 §3）。

    按槽位区分 wielded/worn，按 per-slot prop 副本反向扣减 Skills.apply_*。
    返回是否成功（未装备 False）。
    """
    equipment = world.get(eid, Equipment)
    if equipment is None:
        return False
    skills = world.get(eid, Skills)
    if equipment.weapon == item_id:
        if skills:
            _inject_props(skills, equipment.weapon_props, -1)
        equipment.weapon = None
        equipment.weapon_props = {}
    elif equipment.secondary_weapon == item_id:
        if skills:
            _inject_props(skills, equipment.secondary_weapon_props, -1)
        equipment.secondary_weapon = None
        equipment.secondary_weapon_props = {}
    else:
        # 找护甲槽
        armor_type = next(
            (t for t, iid in equipment.armors.items() if iid == item_id), None
        )
        if armor_type is None:
            return False  # 未装备
        if skills:
            _inject_props(skills, equipment.armor_props.get(armor_type, {}), -1)
        del equipment.armors[armor_type]
        equipment.armor_props.pop(armor_type, None)
    _mark_dirty(world, eid)
    return True


def reset_action(world: World, eid: int) -> None:
    """重算战斗动作集（对照 feature/attack.c:143-171）。

    greenfield 等价范围（当前阶段，actions 闭包/招式表后置 M3 combat）：

    - 无 CombatState 组件则 no-op（reset 仅刷新已有战斗状态，不建空）。
    - 无武器时推断战斗类型 type（attack.c:152-156）：无 prepare -> ``unarmed``；
      单 prepare -> 该 key；双 prepare -> 按 ``action_flag`` 选（action_flag
      runtime 读写后置，默认取首个）。
    - 有武器时 type = weapon skill_type，需 item_registry 桥接查武器 skill_type
      （当前未桥接，保留 wield 已设的 attack_skill，后置）。
    - mapped = ``skill_map[type]``，更新 ``CombatState.attack_skill = mapped or
      type``（attack.c:158 query_skill_mapped）。
    - actions 闭包（``SKILL_D(skill)->query_action`` / 武器自带 / default_actions）
      后置 M3 combat（ADR-0023 裁决 perform/exert 后置；CombatState 招式字段
      S1 简化固定）。
    """

    combat = world.get(eid, CombatState)
    if combat is None:
        return
    equipment = world.get(eid, Equipment)
    if equipment is not None and equipment.weapon:
        # 有武器：type=weapon skill_type 需 item_registry 桥接（后置），
        # 当前保留 wield 已设的 attack_skill
        return
    skills = world.get(eid, Skills)
    prepare = skills.skill_prepare if skills else {}
    if not prepare:
        type_ = "unarmed"
    elif len(prepare) == 1:
        type_ = next(iter(prepare))
    else:
        # 双 prepare 按 action_flag 选（attack.c:156），action_flag 后置默认首个
        type_ = next(iter(prepare))
    mapped = skills.skill_map.get(type_) if skills else None
    combat.attack_skill = mapped or type_
    _mark_dirty(world, eid)


# ──────────────────────── 辅助语义函数 ────────────────────────


def is_equipped(equipment: Equipment, item_id: str) -> bool:
    """物品是否已装备（LPC ``query("equipped")``，ADR-0026 §3）。"""
    if equipment.weapon == item_id or equipment.secondary_weapon == item_id:
        return True
    return item_id in equipment.armors.values()


def total_weight(equipment: Equipment) -> int:
    """当前装备总重量（LPC ``weight()``，ADR-0026 §3）。

    greenfield 简化：返回 ``Equipment.encumbrance``（物品重量后置 M3 物品系统；
    wield/wear 不自动算重量，由调用方经 ``add_encumbrance`` 管理）。
    """
    return equipment.encumbrance


def add_encumbrance(world: World, eid: int, amount: int) -> None:
    """增减负重（对照 LPC ``add_encumbrance``，ADR-0026 §3 F_MOVE 负重）。"""
    equipment = _get_or_create(world, eid)
    equipment.encumbrance += amount
    _mark_dirty(world, eid)


# ──────────────────────── 内部辅助 ────────────────────────


def _get_or_create(world: World, eid: int) -> Equipment:
    """获取或创建 Equipment 组件（LPC wield/wear 要求 owner 是 character，
    greenfield 检查 Equipment 组件，无则创建）。"""
    equipment = world.get(eid, Equipment)
    if equipment is None:
        equipment = Equipment()
        world.add(eid, equipment)
    return equipment


def _mark_dirty(world: World, eid: int) -> None:
    """ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist。"""
    storage = getattr(world, "storage_system", None)
    if storage is not None:
        storage.mark_dirty(eid)
