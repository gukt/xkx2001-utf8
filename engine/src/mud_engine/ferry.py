"""渡口渡船：动态出口周期翻转（M2-09 / spec F2）。

``Ferry`` 组件挂在两岸房间上；``FerryState`` 纯内存挂 ``world.ferries``，不进存档。
``attach_ferries`` 与 ``attach_ai_system`` 同构（幂等 + on_tick）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mud_engine.components import Exit, Exits, Ferry, Identity
from mud_engine.events import ON_TICK, TickContext

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World


@dataclass
class FerryCrossing:
    """一对渡口的运行时态（不进存档）。"""

    bank_a: EntityId
    bank_b: EntityId
    direction_a: str  # A 岸过河方向名
    direction_b: str  # B 岸过河方向名
    cross_interval: int
    # 渡船当前停靠岸：True=A，False=B
    at_bank_a: bool = True
    ticks_until_flip: int = 0


@dataclass
class FerryState:
    """全部渡口运行时态。"""

    crossings: list[FerryCrossing] = field(default_factory=list)


def attach_ferries(world: World) -> None:
    """扫描房间 ``Ferry`` 组件，建 ``FerryState`` 并挂 on_tick（幂等）。

    重复调用：不重复注册 tick handler；``world.ferries`` 按当前组件重建。
    """
    if _on_ferry_tick not in world.events.handlers_for(ON_TICK):
        world.events.register(ON_TICK, _on_ferry_tick)
    world.ferries = _build_ferry_state(world)
    _apply_all_exits(world)


def ferry_status_line(world: World, room: EntityId) -> str | None:
    """渡口房间 look 追加文案；非渡口返回 None。"""
    ferry = world.get_component(room, Ferry)
    if ferry is None or world.ferries is None:
        return None
    crossing = _crossing_for_room(world.ferries, room)
    if crossing is None:
        return None
    at_here = (crossing.at_bank_a and room == crossing.bank_a) or (
        not crossing.at_bank_a and room == crossing.bank_b
    )
    if at_here:
        return (
            f"渡船停靠在此岸，可向{ferry.direction}过河"
            f"（约 {crossing.ticks_until_flip} 个时辰后离岸）。"
        )
    other = crossing.bank_a if room == crossing.bank_b else crossing.bank_b
    other_name = world.require_component(other, Identity).name
    return f"渡船在{other_name}，约 {crossing.ticks_until_flip} 个时辰后到达此岸。"


def _build_ferry_state(world: World) -> FerryState:
    seen: set[frozenset[EntityId]] = set()
    crossings: list[FerryCrossing] = []
    for room in list(world.entities_with(Ferry)):
        ferry = world.require_component(room, Ferry)
        far = ferry.far_bank
        pair = frozenset({room, far})
        if pair in seen:
            continue
        seen.add(pair)
        far_ferry = world.get_component(far, Ferry)
        if far_ferry is None:
            continue
        interval = max(1, ferry.cross_interval)
        crossings.append(
            FerryCrossing(
                bank_a=room,
                bank_b=far,
                direction_a=ferry.direction,
                direction_b=far_ferry.direction,
                cross_interval=interval,
                at_bank_a=True,
                ticks_until_flip=interval,
            )
        )
    return FerryState(crossings=crossings)


def _on_ferry_tick(context: TickContext) -> None:
    world = context.world
    state = world.ferries
    if state is None:
        return
    for crossing in state.crossings:
        crossing.ticks_until_flip -= 1
        if crossing.ticks_until_flip > 0:
            continue
        crossing.at_bank_a = not crossing.at_bank_a
        crossing.ticks_until_flip = crossing.cross_interval
        _apply_crossing_exits(world, crossing)


def _apply_all_exits(world: World) -> None:
    if world.ferries is None:
        return
    for crossing in world.ferries.crossings:
        _apply_crossing_exits(world, crossing)


def _apply_crossing_exits(world: World, crossing: FerryCrossing) -> None:
    """渡船在哪一岸，哪一岸就有指向对岸的 Exit；对岸对应方向移除。"""
    exits_a = world.require_component(crossing.bank_a, Exits)
    exits_b = world.require_component(crossing.bank_b, Exits)
    if crossing.at_bank_a:
        exits_a.by_direction[crossing.direction_a] = Exit(target=crossing.bank_b)
        exits_b.by_direction.pop(crossing.direction_b, None)
    else:
        exits_b.by_direction[crossing.direction_b] = Exit(target=crossing.bank_a)
        exits_a.by_direction.pop(crossing.direction_a, None)


def _crossing_for_room(state: FerryState, room: EntityId) -> FerryCrossing | None:
    for crossing in state.crossings:
        if room in (crossing.bank_a, crossing.bank_b):
            return crossing
    return None


__all__ = [
    "FerryCrossing",
    "FerryState",
    "attach_ferries",
    "ferry_status_line",
]
