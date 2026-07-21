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
    Description,
    Identity,
    Inquiry,
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

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World

# 默认 Spawn/Reset 扫描间隔（tick 数）。M1 NPC 不死，扫描多为核对 desired_count。
DEFAULT_SPAWN_SCAN_INTERVAL = 10

Rng = random.Random


@dataclass(frozen=True)
class SpawnerBlueprint:
    """重建一个 NPC 实例所需的全部数据快照（M2-04）。

    由 ``scene_loader._build_npcs`` 按 template_key 注册到 ``world.spawners``。
    纯内存、不进存档。``extras`` 约定键：
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
    # 延迟 import：避免 commands <-> ai 循环（commands 不 import ai）。
    from mud_engine.commands import room_say

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
    """低频 Spawn/Reset 扫描：按 ``world.spawners`` 核对存活数（M2-04）。

    遍历蓝图注册表（不再从存活 ``NpcSpawnMeta`` 反向聚合），因此即使某
    template 实例全灭，仍能发现缺口。``respawn=True`` 且存活数不足时按蓝图
    补齐；``respawn=False`` 不补（保持 M1 语义）。
    """
    by_template: dict[str, list[EntityId]] = {}
    for entity in world.entities_with(NpcSpawnMeta):
        meta = world.require_component(entity, NpcSpawnMeta)
        by_template.setdefault(meta.template_key, []).append(entity)

    for template_key, blueprint in world.spawners.items():
        if not blueprint.respawn:
            continue
        alive = len(by_template.get(template_key, ()))
        missing = blueprint.desired_count - alive
        for _ in range(max(0, missing)):
            spawn_from_blueprint(world, blueprint)


def spawn_from_blueprint(
    world: World,
    blueprint: SpawnerBlueprint,
    *,
    room: EntityId | None = None,
) -> EntityId:
    """按蓝图重建一个全新 NPC 实例（不带上一实例任何累积可变状态）。

    ``room`` 覆盖初始位置（场景加载时用 ``in_room``；缺省用 ``blueprint.startroom``
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
    "Rng",
    "SpawnerBlueprint",
    "attach_ai_system",
    "condition_from_data",
    "spawn_from_blueprint",
    "spawn_scan",
]
