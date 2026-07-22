"""NPC AI 驱动：AIController 遍历 + Chatter + Spawn/Reset 扫描（块 D，25/26/29）。

挂 ``on_tick``（07 号票事件总线）：每次 tick 先低频 Spawn 扫描，再遍历带
``AIController`` 的实体，按 ``tick_interval`` 跳过不足间隔的 tick，对其
``Behaviors`` 逐条调度。M1 只实现 Chatter（闲聊）；战斗行为推 M2。

``attach_ai_system`` 幂等：同一 world 重复调用不重复注册。rng 可注入，供
Chatter 概率测试用确定性源。条件求值走块 A 的 ``conditions.evaluate``；
Nature 落地后读 ``world.nature``，否则用 ``StubContext``。

M2-04：``SpawnerBlueprint`` + ``world.spawners`` 注册表修复"template 全灭后
扫描失效"；``_spawn_scan`` 遍历蓝图而非从存活 ``NpcSpawnMeta`` 反向聚合。
"""

from __future__ import annotations

import copy
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mud_engine.components import (
    AIController,
    Behaviors,
    BehaviorSpec,
    Container,
    Description,
    Identity,
    Inquiry,
    ItemSpawnMeta,
    NpcSpawnMeta,
    Position,
)
from mud_engine.conditions import (
    And,
    Condition,
    ConditionContext,
    Equals,
    Gte,
    Not,
    Or,
    Predicate,
    StubContext,
    evaluate,
)
from mud_engine.events import ON_TICK, TickContext
from mud_engine.messaging import room_say

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World

# 默认 Spawn/Reset 扫描间隔（tick 数）。M1 NPC 不死，扫描多为核对 desired_count。
DEFAULT_SPAWN_SCAN_INTERVAL = 10

Rng = random.Random


@dataclass
class SpawnerBlueprint:
    """重建一个 NPC 实例所需的全部数据快照（M2-04）。

    由 ``scene_loader._build_npcs`` 按 template_key 注册到 ``world.spawners``。
    纯内存、不进存档。``slots`` 登记具体实例 id（ADR-0010 槽位指针）；``extras``
    约定键：
    - ``capabilities``: ``tuple`` of 额外能力组件模板（Vitals/Currency/Faction 等），
      生成时 deepcopy 挂到新实例，避免多实例共享可变态。
    """

    template_key: str
    name: str
    aliases: tuple[str, ...]
    short: str
    long: str
    startroom: EntityId
    desired_count: int
    respawn: bool
    inquiry: Inquiry | None = None
    behaviors: Behaviors | None = None
    tick_interval: int = 1
    extras: Mapping[str, object] = field(default_factory=dict)
    slots: list[EntityId | None] = field(default_factory=list)


@dataclass
class ItemSpawnerBlueprint:
    """房间 ``objects`` 物品槽位蓝图（pre-m4-04）。

    键为 ``(room_key, template_key)``，登记在 ``world.item_spawners``。``slots``
    记住具体实例；实例仍在世界任意处则占名额，仅销毁后且 ``respawn`` 才补。
    """

    template_key: str
    room_key: str
    startroom: EntityId
    desired_count: int
    respawn: bool
    slots: list[EntityId | None] = field(default_factory=list)


@dataclass
class AISystem:
    """NPC AI 子系统挂到 world 的运行时态（25 号票）：rng + spawn 扫描间隔。

    纯内存、不进存档；由 ``attach_ai_system`` 挂载。和 ``NatureState`` 对称，
    避免把 ai 状态作 ad-hoc 私有 attr 猴补丁到 World。
    """

    rng: Rng
    spawn_scan_interval: int = DEFAULT_SPAWN_SCAN_INTERVAL


def attach_ai_system(
    world: World,
    *,
    rng: Rng | None = None,
    spawn_scan_interval: int = DEFAULT_SPAWN_SCAN_INTERVAL,
) -> None:
    """把 NPC AI 挂到 world：注册 ``on_tick`` handler（幂等）。

    ``rng`` 注入供 Chatter 概率（测试用 ``Random(0)`` 或恒真 stub）；缺省用
    系统 ``Random()``。``spawn_scan_interval`` 控制低频 Spawn/Reset 扫描频率。

    重复调用不重复注册（``handlers_for`` 查重，替代 world 上的哨兵猴补丁）；
    ``world.ai`` 会被覆盖为最新配置。
    """
    if _on_ai_tick not in world.events.handlers_for(ON_TICK):
        world.events.register(ON_TICK, _on_ai_tick)
    world.ai = AISystem(
        rng=rng if rng is not None else random.Random(),
        spawn_scan_interval=spawn_scan_interval,
    )


def _on_ai_tick(context: TickContext) -> None:
    """on_tick 订阅者：Spawn 扫描 + AIController 行为调度。"""
    world = context.world
    ai = world.ai
    if ai is None:
        return
    tick = context.tick
    if ai.spawn_scan_interval > 0 and tick % ai.spawn_scan_interval == 0:
        spawn_scan(world)
    cond_ctx = _condition_context(world)
    for entity in list(world.entities_with(AIController)):
        controller = world.require_component(entity, AIController)
        interval = max(1, controller.tick_interval)
        if tick % interval != 0:
            continue
        behaviors = world.get_component(entity, Behaviors)
        if behaviors is None:
            continue
        for spec in behaviors.entries:
            _tick_behavior(world, entity, spec, rng=ai.rng, cond_ctx=cond_ctx)


def _tick_behavior(
    world: World,
    entity: EntityId,
    spec: BehaviorSpec,
    *,
    rng: Rng,
    cond_ctx: ConditionContext,
) -> None:
    """按 kind 分发单条行为；认识 chatter / aggro，未知 kind 静默跳过。"""
    if spec.kind == "chatter":
        _tick_chatter(world, entity, spec, rng=rng, cond_ctx=cond_ctx)
    elif spec.kind == "aggro":
        _tick_aggro(world, entity, spec, cond_ctx=cond_ctx)


def _tick_chatter(
    world: World,
    entity: EntityId,
    spec: BehaviorSpec,
    *,
    rng: Rng,
    cond_ctx: ConditionContext,
) -> None:
    """Chatter：条件通过且概率命中时 ``room_say`` 一条预设消息（29 号票）。"""
    if not spec.chat_msgs:
        return
    condition = condition_from_data(spec.when)
    if condition is not None and not evaluate(condition, cond_ctx):
        return
    chance = spec.chat_chance
    if chance <= 0:
        return
    if chance < 1.0 and rng.random() >= chance:
        return
    text = rng.choice(spec.chat_msgs)
    room_say(world, entity, text)


def _tick_aggro(
    world: World,
    entity: EntityId,
    spec: BehaviorSpec,
    *,
    cond_ctx: ConditionContext,
) -> None:
    """Aggro（M2-19）：条件通过后攻击同房间第一个未交战的玩家。

    目标遍历按 entity id 升序，保证确定性（不依赖 set 遍历顺序）。
    建立交战复用 ``try_engage``（与 attack 命令同一底层函数）。
    """
    from mud_engine.combat_system import try_engage
    from mud_engine.components import Engaged, PlayerSession, Position

    condition = condition_from_data(spec.when)
    if condition is not None and not evaluate(condition, cond_ctx):
        return
    if world.has_component(entity, Engaged):
        return
    pos = world.get_component(entity, Position)
    if pos is None:
        return
    # 确定性：按 entity id 排序后取第一个未 Engaged 的玩家。
    candidates = sorted(
        e
        for e in world.entities_in_room(pos.room, exclude=entity)
        if world.has_component(e, PlayerSession) and not world.has_component(e, Engaged)
    )
    if not candidates:
        return
    try_engage(world, entity, candidates[0])


def spawn_scan(world: World) -> None:
    """低频 Spawn/Reset 扫描：按蓝图槽位指针补齐缺口（ADR-0010 / pre-m4-04）。

    登记实例仍存在于世界任意处则占名额（``get``/``drop``/换房不产生缺口）；
    仅 ``destroy_entity`` 后且 ``respawn=True`` 时在出生房补齐空槽。
    """
    for blueprint in world.spawners.values():
        if not blueprint.respawn:
            continue
        _refill_npc_slots(world, blueprint)
    for blueprint in world.item_spawners.values():
        if not blueprint.respawn:
            continue
        _refill_item_slots(world, blueprint)


def _ensure_slot_capacity(slots: list[EntityId | None], desired: int) -> None:
    while len(slots) < desired:
        slots.append(None)


def _refill_npc_slots(world: World, blueprint: SpawnerBlueprint) -> None:
    _ensure_slot_capacity(blueprint.slots, blueprint.desired_count)
    for index in range(blueprint.desired_count):
        eid = blueprint.slots[index]
        if eid is not None and world.has_entity(eid):
            continue
        blueprint.slots[index] = spawn_from_blueprint(world, blueprint)


def _refill_item_slots(world: World, blueprint: ItemSpawnerBlueprint) -> None:
    _ensure_slot_capacity(blueprint.slots, blueprint.desired_count)
    for index in range(blueprint.desired_count):
        eid = blueprint.slots[index]
        if eid is not None and world.has_entity(eid):
            continue
        blueprint.slots[index] = spawn_item_from_blueprint(world, blueprint)


def spawn_from_blueprint(
    world: World,
    blueprint: SpawnerBlueprint,
    *,
    room: EntityId | None = None,
) -> EntityId:
    """按蓝图重建一个全新 NPC 实例（不带上一实例任何累积可变状态）。

    ``room`` 覆盖初始位置（场景加载时用 objects 房；缺省用 ``blueprint.startroom``
    供重生路径）。load 与 respawn 共用本函数，避免双路径装配分叉。
    """
    npc = world.create_entity()
    world.add_component(npc, Identity(name=blueprint.name, aliases=blueprint.aliases))
    world.add_component(npc, Description(short=blueprint.short, long=blueprint.long))
    world.add_component(npc, Position(room=blueprint.startroom if room is None else room))
    world.add_component(
        npc,
        NpcSpawnMeta(
            template_key=blueprint.template_key,
            startroom=blueprint.startroom,
            desired_count=blueprint.desired_count,
            respawn=blueprint.respawn,
        ),
    )
    if blueprint.inquiry is not None:
        world.add_component(
            npc,
            Inquiry(
                topics=dict(blueprint.inquiry.topics),
                default=blueprint.inquiry.default,
                handler=blueprint.inquiry.handler,
            ),
        )
    if blueprint.behaviors is not None:
        world.add_component(npc, AIController(tick_interval=blueprint.tick_interval))
        world.add_component(npc, Behaviors(entries=list(blueprint.behaviors.entries)))
    # M2-05+：Vitals/Currency/Faction/ShopInventory 等走 extras.capabilities。
    extra_caps = blueprint.extras.get("capabilities", ())
    if isinstance(extra_caps, (list, tuple)):
        for component in extra_caps:
            world.add_component(npc, copy.deepcopy(component))
    return npc


def spawn_item_from_blueprint(world: World, blueprint: ItemSpawnerBlueprint) -> EntityId:
    """按物品槽位蓝图在出生房地面生成一件新实例（挂 ``ItemSpawnMeta``）。"""
    from mud_engine.scene_loader import instantiate_item

    item = instantiate_item(world, blueprint.template_key)
    world.add_component(
        item,
        ItemSpawnMeta(
            template_key=blueprint.template_key,
            startroom=blueprint.startroom,
            desired_count=blueprint.desired_count,
            respawn=blueprint.respawn,
        ),
    )
    room_container = world.require_component(blueprint.startroom, Container)
    room_container.items.add(item)
    return item


# 兼容旧私有名（tick handler / 历史测试引用）。
_spawn_scan = spawn_scan
_spawn_from_blueprint = spawn_from_blueprint


def _condition_context(world: World) -> ConditionContext:
    """取条件求值 context：优先 ``world.nature``（块 B），否则 StubContext。"""
    nature = getattr(world, "nature", None)
    if nature is not None and isinstance(nature, ConditionContext):
        return nature
    return StubContext()


def _convert_condition_parts(parts: object) -> tuple[Condition, ...] | None:
    """把 and/or 的子条件列表转成 Condition 元组；非 list/tuple 返回 None。"""
    if not isinstance(parts, (list, tuple)):
        return None
    return tuple(
        c for p in parts if (c := condition_from_data(p if isinstance(p, Mapping) else None))
    )


def condition_from_data(data: Mapping | None) -> Condition | None:
    """把 YAML/组件里的结构化 dict 转成条件节点（受限 AST 形状，避坑清单 §F）。

    支持最小子集：

    - ``{"predicate": "is_night"}``
    - ``{"equals": {"field": "phase", "value": "night"}}`` 或扁平
      ``{"field": "phase", "value": "night"}``
    - ``{"gte": {"field": "con", "value": 12}}`` 或 ``{"op": "gte", "field", "value"}``
    - ``{"and": [子条件, ...]}`` / ``{"or": [...]}`` / ``{"not": 子条件}``
    """
    if data is None:
        return None
    if not isinstance(data, Mapping):
        return None
    if "predicate" in data:
        return Predicate(name=str(data["predicate"]))
    if "equals" in data:
        eq = data["equals"]
        if isinstance(eq, Mapping):
            return Equals(field=str(eq["field"]), value=eq["value"])
        return None
    if "gte" in data:
        gte = data["gte"]
        if isinstance(gte, Mapping):
            return Gte(field=str(gte["field"]), value=gte["value"])
        return None
    if data.get("op") == "gte" and "field" in data and "value" in data:
        return Gte(field=str(data["field"]), value=data["value"])
    if "field" in data and "value" in data:
        return Equals(field=str(data["field"]), value=data["value"])
    if "and" in data:
        converted = _convert_condition_parts(data["and"])
        if converted is None:
            return None
        return And(parts=converted)
    if "or" in data:
        converted = _convert_condition_parts(data["or"])
        if converted is None:
            return None
        return Or(parts=converted)
    if "not" in data:
        raw = data["not"]
        operand = condition_from_data(raw if isinstance(raw, Mapping) else None)
        if operand is None:
            return None
        return Not(operand=operand)
    return None


__all__ = [
    "AISystem",
    "DEFAULT_SPAWN_SCAN_INTERVAL",
    "ItemSpawnerBlueprint",
    "Rng",
    "SpawnerBlueprint",
    "attach_ai_system",
    "condition_from_data",
    "spawn_from_blueprint",
    "spawn_item_from_blueprint",
    "spawn_scan",
]
