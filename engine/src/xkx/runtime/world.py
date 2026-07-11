"""加载场景 IR -> 构建 ECS 实体 + 战斗桥接。

把层0 IR（room/npc/quest）转为 ECS 实体 + 组件。提供实体 <-> CombatantSnapshot
转换（战斗时快照边界）与 Effect apply（按账本顺序写回组件）。
"""

from __future__ import annotations

from xkx.combat.context import CombatantSnapshot
from xkx.combat.result import (
    KIND_DAMAGE,
    KIND_EXP,
    KIND_JINGLI,
    KIND_POTENTIAL,
    KIND_SKILL_IMPROVE,
    KIND_WOUND,
    Effect,
)
from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.dbase_map import validate_dbase_map
from xkx.runtime.ecs import World
from xkx.runtime.schema import SchemaError, SchemaRegistry


def build_world(ir: dict) -> tuple[World, dict[str, int], dict[str, dict]]:
    """从 IR 构建世界。返回 (world, room_id -> entity_id, quest_id -> quest dict)。

    用 ``SchemaRegistry.with_builtins()`` 创建带类型校验的 World（ADR-0019），
    生产路径组件类型拼写错误启动期/调用期失败，非静默 None。同时校验
    ``DBASE_KEY_MAP`` 映射目标字段存在（T3，ADR-0019 has_field 衔接）。
    """
    schema = SchemaRegistry.with_builtins()
    issues = validate_dbase_map(schema)
    if issues:
        raise SchemaError(
            "DBASE_KEY_MAP 映射校验失败（ADR-0019）:\n" + "\n".join(issues)
        )
    world = World(schema)
    npc_defs = {n["id"]: n for n in ir["npcs"]}
    room_entities: dict[str, int] = {}
    quest_idx: dict[str, dict] = {q["id"]: q for q in ir.get("quests", [])}

    for r in ir["rooms"]:
        eid = world.new_entity()
        world.add(
            eid,
            RoomComp(
                room_id=r["id"],
                short=r["short"],
                long=r["long"],
                exits=r.get("exits", {}),
                objects=r.get("objects", {}),
                items=set(r.get("items", [])),
                outdoors=r.get("outdoors", False),
                no_fight=r.get("no_fight", False),
            ),
        )
        room_entities[r["id"]] = eid

    for r in ir["rooms"]:
        for npc_id, count in r.get("objects", {}).items():
            ndef = npc_defs.get(npc_id)
            if not ndef:
                continue
            for _ in range(count):
                _spawn_npc(world, ndef, r["id"])

    return world, room_entities, quest_idx


def _spawn_npc(world: World, n: dict, room_id: str) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name=n["name"], aliases=n.get("aliases", []), prototype_id=n["id"]))
    world.add(eid, Position(room_id=room_id))
    world.add(
        eid,
        Attributes(
            str_=n.get("str_", 20),
            dex_=n.get("dex_", 20),
            int_=n.get("int_", 20),
            con_=n.get("con_", 20),
            age=n.get("age", 20),
            gender=n.get("gender", "男性"),
        ),
    )
    world.add(
        eid,
        Vitals(
            qi=n.get("max_qi", 100),
            max_qi=n.get("max_qi", 100),
            eff_qi=n.get("max_qi", 100),
            jing=n.get("max_jing", 100),
            max_jing=n.get("max_jing", 100),
            jingli=n.get("max_jingli", 100),
            max_jingli=n.get("max_jingli", 100),
            max_neili=n.get("max_neili", 0),
        ),
    )
    world.add(eid, Progression(combat_exp=n.get("combat_exp", 0)))
    world.add(
        eid,
        Skills(
            levels=n.get("skills", {}),
            apply_attack=n.get("apply_attack", 0),
            apply_dodge=n.get("apply_dodge", 0),
            apply_parry=n.get("apply_parry", 0),
            apply_damage=n.get("apply_damage", 0),
            apply_armor=n.get("apply_armor", 0),
            weapon=n.get("weapon"),
        ),
    )
    world.add(
        eid,
        CombatState(
            attack_skill=n.get("attack_skill", "unarmed"),
            weapon_label=n.get("weapon_label", "拳头"),
        ),
    )
    world.add(
        eid,
        NpcBehavior(
            attitude=n.get("attitude", "friendly"),
            chat_chance_combat=n.get("chat_chance_combat", 0),
            chat_msg_combat=n.get("chat_msg_combat", []),
            inquiry=n.get("inquiry", {}),
        ),
    )
    return eid


def spawn_player(
    world: World,
    name: str,
    room_id: str,
    *,
    family: str = "",
    items: set[str] | None = None,
) -> int:
    """创建玩家实体（S1 默认属性）。

    S4 ADR-0005：``family`` + ``items`` 供 ``family_eq`` / ``has_item`` 谓词求值。
    S4 ADR-0006：``Marks`` 组件供 ``set_flag`` 副作用 / ``has_flag`` 谓词。
    S4 ADR-0007：``QuestLog`` 组件跟踪任务状态。
    """
    eid = world.new_entity()
    world.add(eid, Identity(name=name, is_player=True, prototype_id="player"))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Attributes(str_=20, dex_=20, int_=20, con_=20, age=22, family=family))
    world.add(
        eid,
        Vitals(
            qi=200,
            max_qi=200,
            eff_qi=200,
            jing=150,
            max_jing=150,
            jingli=200,
            max_jingli=200,
        ),
    )
    world.add(eid, Progression(combat_exp=500))
    world.add(eid, Skills(levels={"unarmed": 30, "dodge": 20}))
    world.add(eid, CombatState())
    world.add(eid, Inventory(items=items or set()))
    world.add(eid, Marks())  # S4 ADR-0006：set_flag 副作用 / has_flag 谓词
    world.add(eid, QuestLog())  # S4 ADR-0007：任务状态
    return eid


def to_snapshot(world: World, eid: int) -> CombatantSnapshot:
    """实体 -> CombatantSnapshot（战斗开始边界快照）。"""
    ident = world.get(eid, Identity)
    attrs = world.get(eid, Attributes)
    vitals = world.get(eid, Vitals)
    prog = world.get(eid, Progression)
    skills = world.get(eid, Skills)
    combat = world.get(eid, CombatState)
    assert ident and attrs and vitals and prog and skills and combat
    return CombatantSnapshot(
        entity_id=eid,
        name=ident.name,
        str_=attrs.str_,
        dex_=attrs.dex_,
        int_=attrs.int_,
        con_=attrs.con_,
        qi=vitals.qi,
        max_qi=vitals.max_qi,
        eff_qi=vitals.eff_qi,
        jing=vitals.jing,
        max_jing=vitals.max_jing,
        jingli=vitals.jingli,
        max_jingli=vitals.max_jingli,
        combat_exp=prog.combat_exp,
        potential=prog.potential,
        max_potential=prog.max_potential,
        skills=skills.levels,
        apply_attack=skills.apply_attack,
        apply_dodge=skills.apply_dodge,
        apply_parry=skills.apply_parry,
        apply_damage=skills.apply_damage,
        apply_armor=skills.apply_armor,
        weapon=skills.weapon,
        attack_skill=combat.attack_skill,
        weapon_label=combat.weapon_label,
        action_message=combat.action_message,
        action_force=combat.action_force,
        action_dodge=combat.action_dodge,
        action_parry=combat.action_parry,
        action_damage=combat.action_damage,
        action_damage_type=combat.action_damage_type,
        hit_ob_bonus=combat.hit_ob_bonus,
        hit_by_override=combat.hit_by_override,
    )


def apply_effects(world: World, effects: list[Effect]) -> None:
    """按账本顺序把 Effect apply 到组件（交织顺序，不批量）。"""
    for e in effects:
        vitals = world.get(e.target_id, Vitals)
        if e.kind == KIND_DAMAGE and vitals:
            vitals.qi = max(0, vitals.qi - e.amount)
        elif e.kind == KIND_WOUND and vitals:
            vitals.eff_qi = max(0, vitals.eff_qi - e.amount)
        elif e.kind == KIND_EXP:
            prog = world.get(e.target_id, Progression)
            if prog:
                prog.combat_exp += e.amount
        elif e.kind == KIND_POTENTIAL:
            prog = world.get(e.target_id, Progression)
            if prog:
                prog.potential = min(prog.max_potential, prog.potential + e.amount)
        elif e.kind == KIND_JINGLI and vitals:
            vitals.jingli = max(0, min(vitals.max_jingli, vitals.jingli + e.amount))
        elif e.kind == KIND_SKILL_IMPROVE:
            skills = world.get(e.target_id, Skills)
            if skills and e.detail:
                skills.levels[e.detail] = skills.levels.get(e.detail, 0) + 1
