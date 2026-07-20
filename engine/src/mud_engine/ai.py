"""NPC AI 驱动：AIController 遍历 + Chatter + Spawn/Reset 扫描（块 D，25/26/29）。

挂 ``on_tick``（07 号票事件总线）：每次 tick 先低频 Spawn 扫描，再遍历带
``AIController`` 的实体，按 ``tick_interval`` 跳过不足间隔的 tick，对其
``Behaviors`` 逐条调度。M1 只实现 Chatter（闲聊）；战斗行为推 M2。

``attach_ai_system`` 幂等：同一 world 重复调用不重复注册。rng 可注入，供
Chatter 概率测试用确定性源。条件求值走块 A 的 ``conditions.evaluate``；
Nature 落地后读 ``world.nature``，否则用 ``StubContext``。
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mud_engine.components import (
    AIController,
    Behaviors,
    BehaviorSpec,
    NpcSpawnMeta,
)
from mud_engine.conditions import (
    And,
    Condition,
    ConditionContext,
    Equals,
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
        _spawn_scan(world)
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
    """按 kind 分发单条行为；M1 只认识 chatter，未知 kind 静默跳过。"""
    if spec.kind == "chatter":
        _tick_chatter(world, entity, spec, rng=rng, cond_ctx=cond_ctx)


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


def _spawn_scan(world: World) -> None:
    """低频 Spawn/Reset 扫描：按 template_key 核对存活数（26 号票）。

    M1 NPC 不死不触发重生：``respawn=True`` 且 count 已达标时为空转；不足时
    也先不补齐（蓝图重建推 M2 死亡重生路径）。机制地基（spec D2"先埋"）：
    扫描挂 tick、聚合 meta、对照 desired_count。

    M2 复核点：``NpcSpawnMeta`` 挂在每个 NPC 实例上，从存活实例聚合 ``metas``。
    若某 template 实例全灭（尤其 desired_count=1 的单例 NPC，如 boss/quest），
    template_key 从 ``metas`` 消失，扫描无法发现缺口--M2 死亡重生路径需改用
    spawner 实体或模板注册表，不从存活实例聚合。
    """
    by_template: dict[str, list[EntityId]] = {}
    metas: dict[str, NpcSpawnMeta] = {}
    for entity in world.entities_with(NpcSpawnMeta):
        meta = world.require_component(entity, NpcSpawnMeta)
        by_template.setdefault(meta.template_key, []).append(entity)
        metas[meta.template_key] = meta
    for template_key, meta in metas.items():
        if not meta.respawn:
            continue
        alive = len(by_template.get(template_key, ()))
        if alive >= meta.desired_count:
            continue
        # M1：缺口存在但不补齐（NPC 不死，正常路径走不到这里）。留钩子给 M2。


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
        c
        for p in parts
        if (c := condition_from_data(p if isinstance(p, Mapping) else None))
    )


def condition_from_data(data: Mapping | None) -> Condition | None:
    """把 YAML/组件里的结构化 dict 转成条件节点（受限 AST 形状，避坑清单 §F）。

    支持最小子集：

    - ``{"predicate": "is_night"}``
    - ``{"equals": {"field": "phase", "value": "night"}}`` 或扁平
      ``{"field": "phase", "value": "night"}``
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
    "attach_ai_system",
    "condition_from_data",
]
