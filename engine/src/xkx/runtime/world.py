"""加载场景 IR -> 构建 ECS 实体 + 战斗桥接。

把层0 IR（room/npc/quest）转为 ECS 实体 + 组件。提供实体 <-> CombatantSnapshot
转换（战斗时快照边界）与 Effect apply（按账本顺序写回组件）。
"""

from __future__ import annotations

from xkx.combat.context import CombatantSnapshot
from xkx.combat.result import (
    KIND_CLEAR_MARK,
    KIND_DAMAGE,
    KIND_DAMAGE_JING,
    KIND_EFF_JINGLI,
    KIND_EXP,
    KIND_HEAL,
    KIND_HEAL_JING,
    KIND_JINGLI,
    KIND_MAX_JINGLI,
    KIND_MAX_NEILI,
    KIND_NEILI,
    KIND_POTENTIAL,
    KIND_RESPIRATE,
    KIND_SKILL_IMPROVE,
    KIND_WOUND,
    KIND_WOUND_JING,
    Effect,
)
from xkx.dsl.layer2 import InquiryNode
from xkx.runtime.components import (
    Attributes,
    CombatState,
    DoorEntry,
    Equipment,
    FamilyComp,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.dbase_map import validate_dbase_map
from xkx.runtime.ecs import World
from xkx.runtime.schema import SchemaError, SchemaRegistry
from xkx.runtime.storage import (
    DEFAULT_CHECKPOINT_INTERVAL,
    DEFAULT_PERSIST_INTERVAL,
    StorageBackend,
    StorageSystem,
)
from xkx.runtime.theme import ThemeConfig


def build_world(
    ir: dict,
    *,
    storage_backend: StorageBackend | None = None,
    persist_interval: int = DEFAULT_PERSIST_INTERVAL,
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
    theme_config: ThemeConfig | None = None,
) -> tuple[World, dict[str, int], dict[str, dict]]:
    """从 IR 构建世界。返回 (world, room_id -> entity_id, quest_id -> quest dict)。

    用 ``SchemaRegistry.with_builtins()`` 创建带类型校验的 World（ADR-0019），
    生产路径组件类型拼写错误启动期/调用期失败，非静默 None。同时校验
    ``DBASE_KEY_MAP`` 映射目标字段存在（T3，ADR-0019 has_field 衔接）。

    ADR-0022 T5：可选 ``storage_backend`` 传入时创建 ``StorageSystem`` 并挂到
    ``world.storage_system``（动态属性，不改 World 类）。调用方通过该属性驱动 tick
    persist + mark_dirty。不传则不接入存档（向后兼容现有调用方）。

    ADR-0030 决策 2：可选 ``theme_config`` 传入时挂到 ``world.theme_config``
    （动态属性，类比 ``storage_system`` 注入模式）。``None`` 时用
    ``ThemeConfig.default()``（非武侠测试默认配置）。governance/death/cli 通过
    ``world.theme_config`` 读取房间路径，不硬编码武侠路径字面量。
    """
    schema = SchemaRegistry.with_builtins()
    issues = validate_dbase_map(schema)
    if issues:
        raise SchemaError(
            "DBASE_KEY_MAP 映射校验失败（ADR-0019）:\n" + "\n".join(issues)
        )
    world = World(schema)
    # ADR-0030 决策 2：注入 ThemeConfig（None 用默认非武侠配置）
    world.theme_config = theme_config or ThemeConfig.default()  # type: ignore[attr-defined]
    # M3-1 ADR-0032 决策 3：当前 tick（time-gate 冷却判定时间源，Engine.tick 更新）
    world.current_tick = 0  # type: ignore[attr-defined]
    # M3-1 子任务 5：最小消息缓冲（CLI 自动推进时收集 System/_tell 产生的消息，
    # 完整 WS 推送后置 M3；单玩家 demo 全量打印，多实体分发后置）
    world.pending_messages = []  # type: ignore[attr-defined]
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
                no_death=r.get("no_death", False),
                doors={
                    d: DoorEntry(
                        name=spec["name"],
                        other_room=spec["other_room"],
                        other_dir=spec["other_dir"],
                        closed=spec.get("closed", True),
                        locked=spec.get("locked", False),
                        key_id=spec.get("key_id", ""),
                    )
                    for d, spec in r.get("doors", {}).items()
                },
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

    # ADR-0022 T5：接入 StorageSystem（可选，最小改动）
    if storage_backend is not None:
        world.storage_system = StorageSystem(  # type: ignore[attr-defined]
            storage_backend,
            schema=schema,
            persist_interval=persist_interval,
            checkpoint_interval=checkpoint_interval,
        )

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
            eff_jing=n.get("max_jing", 100),
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
            apply_speed=n.get("apply_speed", 0),
            weapon=n.get("weapon"),
            skill_map=n.get("skill_map", {}),
            skill_prepare=n.get("skill_prepare", {}),
            learned=n.get("learned", {}),
        ),
    )
    world.add(
        eid,
        CombatState(
            attack_skill=n.get("attack_skill", "unarmed"),
            weapon_label=n.get("weapon_label", "拳头"),
        ),
    )
    raw_inquiry = n.get("inquiry", {}) or {}
    inquiry: dict[str, str | InquiryNode] = {}
    for topic, value in raw_inquiry.items():
        if isinstance(value, dict):
            inquiry[topic] = InquiryNode(**value)
        else:
            inquiry[topic] = value
    world.add(
        eid,
        NpcBehavior(
            attitude=n.get("attitude", "friendly"),
            chat_chance_combat=n.get("chat_chance_combat", 0),
            chat_msg_combat=n.get("chat_msg_combat", []),
            inquiry=inquiry,
            apprentice_config=n.get("apprentice"),  # M3-1 ADR-0032 决策 1
            vendetta_mark=n.get("vendetta_mark", ""),  # B-2 ADR-0045
        ),
    )
    # 2.5 ADR-0028：TitleComp 默认实例（rankd 求值可取字段，query("shen") 返回 0
    # 非 None，set("shen") 不 raise DbaseKeyError）。ADR-0051：NpcDef.shen 透传
    # （邪派 NPC shen 负，look 触发 berserk flavor）；title/char_class 等仍后置。
    world.add(eid, TitleComp(shen=n.get("shen", 0)))
    # M3-1 ADR-0032 决策 1：师傅 NPC 的 FamilyComp（LPC create_family 语义）。
    # apprentice_config 非空 = 该 NPC 是师傅，写师傅自己的 family（privs=-1 全部
    # 权限，对照 apprentice.c:52 assign_apprentice(title, -1)）。玩家拜师时
    # recruit 写玩家的 FamilyComp（generation = 师傅 generation + 1）。
    app = n.get("apprentice")
    if app:
        world.add(
            eid,
            FamilyComp(
                family_name=app["family_name"],
                generation=app["generation"],
                title=app["title"],
                privs=-1,
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
            eff_jing=150,
            jingli=200,
            max_jingli=200,
        ),
    )
    world.add(eid, Progression(combat_exp=500))
    world.add(eid, Skills(levels={"unarmed": 30, "dodge": 20}))
    world.add(eid, CombatState())
    world.add(eid, Inventory(items=items or set()))
    world.add(eid, Equipment())  # 2.3：装备组件（默认空槽，wield/wear 填充）
    world.add(eid, Marks())  # S4 ADR-0006：set_flag 副作用 / has_flag 谓词
    world.add(eid, QuestLog())  # S4 ADR-0007：任务状态
    world.add(eid, TitleComp())  # 2.5 ADR-0028：称谓组件（rankd 求值所需 dbase key）
    world.add(eid, FamilyComp())  # M3-1 ADR-0032：门派归属（拜师 recruit 写入）
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
        apply_speed=skills.apply_speed,
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
        # T10 整合遗留：CombatState 扩展字段传递（ADR-0023 决策 4 第 4/5 项）
        guarding=combat.guarding,
        is_fighting=combat.is_fighting,
        fight_dodge=combat.fight_dodge,
    )


def apply_effects(world: World, effects: list[Effect]) -> None:
    """按账本顺序把 Effect apply 到组件（交织顺序，不批量）。"""
    for e in effects:
        vitals = world.get(e.target_id, Vitals)
        if e.kind == KIND_DAMAGE and vitals:
            vitals.qi = max(0, vitals.qi - e.amount)
        elif e.kind == KIND_WOUND and vitals:
            vitals.eff_qi = max(0, vitals.eff_qi - e.amount)
        elif e.kind == KIND_HEAL and vitals:
            # condition 驱动的 qi 恢复（drunk 微醺活血等），clamp eff_qi
            vitals.qi = min(vitals.eff_qi, vitals.qi + e.amount)
        elif e.kind == KIND_HEAL_JING and vitals:
            # condition 驱动的 jing 恢复，clamp eff_jing
            vitals.jing = min(vitals.eff_jing, vitals.jing + e.amount)
        elif e.kind == KIND_DAMAGE_JING and vitals:
            # condition 驱动的 jing 扣减（drunk 扣精等），clamp 0
            vitals.jing = max(0, vitals.jing - e.amount)
        elif e.kind == KIND_WOUND_JING and vitals:
            # condition 驱动的 eff_jing 扣减（snake_poison wound jing），clamp 0
            vitals.eff_jing = max(0, vitals.eff_jing - e.amount)
        elif e.kind == KIND_CLEAR_MARK:
            # Marks.flags 移除（revive 苏醒清 unconscious 等，2.2）
            marks = world.get(e.target_id, Marks)
            if marks and e.detail:
                marks.flags.discard(e.detail)
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
        elif e.kind == KIND_NEILI and vitals:
            # dazuo neili 增长（clamp max_neili*2，对照 LPC dazuo.c:59-62 启动钳制）
            vitals.neili = max(0, min(vitals.max_neili * 2, vitals.neili + e.amount))
        elif e.kind == KIND_RESPIRATE and vitals:
            # tuna jingli 增长（clamp max_jingli*2，对照 LPC respirating 不钳制 +
            # 结束判定 jingli>=max_jingli*2 涨上限；区别于 KIND_JINGLI clamp max_jingli）
            vitals.jingli = max(0, min(vitals.max_jingli * 2, vitals.jingli + e.amount))
        elif e.kind == KIND_MAX_NEILI and vitals:
            # max_neili += amount（amount=0 瓶颈只重置）+ neili 重置为 max_neili
            # （对照 LPC dazuo.c:98/102 set("neili", max_neili)）
            vitals.max_neili += e.amount
            vitals.neili = vitals.max_neili
        elif e.kind == KIND_MAX_JINGLI and vitals:
            # max_jingli += amount + jingli 重置（对照 LPC tuna.c:87/91 set jingli=max_jingli）
            vitals.max_jingli += e.amount
            vitals.jingli = vitals.max_jingli
        elif e.kind == KIND_EFF_JINGLI and vitals:
            # eff_jingli += amount（tuna 瓶颈增长，对照 LPC tuna.c:87 eff_jingli += 1）
            vitals.eff_jingli += e.amount
