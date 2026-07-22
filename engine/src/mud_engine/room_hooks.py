"""官方可信房间钩子：协议 + 全局注册表 + 窄 ctx（Pre-M4 / ADR-0012）。

与 ``SkillBehavior`` 同信任级、同注册模式：YAML 只引用 ``hook_id``，实现永远是
引擎 / 题材包自带的可信 Python。改世界必须经 ``RoomHookContext``，不得直接摸
``World`` 私有结构。UGC 内容包禁止 ``hooks`` 字段（见 ``scene_loader``）。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from mud_engine.components import (
    Exit,
    Exits,
    HiddenExit,
    HiddenExits,
    PlayerSession,
    Position,
    RoomFreeState,
    RoomHookBinding,
)
from mud_engine.events import ON_TICK, TickContext
from mud_engine.world import EntityId, World

# 进房 / 离房事件名与 commands / entity_gate 对齐（字符串常量，避免循环 import）。
ON_ENTER_ROOM = "on_enter_room"
ON_LEAVE_ROOM = "on_leave_room"


class RoomHook(Protocol):
    """房间生命周期钩子。方法全部可选；未实现的方法视为不参与对应事件点。

    约定可选方法签名::

        def on_enter(self, ctx: RoomHookContext) -> None: ...
        def on_leave(self, ctx: RoomHookContext) -> None: ...
        def on_tick(self, ctx: RoomHookContext) -> None: ...
        def on_dig(self, ctx: RoomHookContext) -> list[str]: ...  # 命令动词 dig
    """


_ROOM_HOOKS: dict[str, RoomHook] = {}


def register_room_hook(hook_id: str, hook: RoomHook) -> None:
    """按 ``hook_id`` 注册可信钩子实现（与 ``register_skill_behavior`` 同构）。"""
    _ROOM_HOOKS[hook_id] = hook


def get_room_hook(hook_id: str) -> RoomHook | None:
    """查询已注册钩子；未注册返回 ``None``（加载期视为 fail-closed）。"""
    return _ROOM_HOOKS.get(hook_id)


def clear_room_hooks() -> None:
    """测试辅助：清空注册表后重新挂上引擎内置机关钩子。"""
    _ROOM_HOOKS.clear()
    _register_builtin_hooks()


class DigCollapseHook:
    """机关 #1：挖洞开出口、超时崩塌（白玉峰灵感）。

    YAML ``hooks.params``::

        direction: <出口方向>
        target: <目标房间键>
        ttl_ticks: <挖开后存活 tick 数>
    """

    SCHEDULE_KEY = "dig_collapse"
    HOOK_ID = "dig_collapse"

    def on_dig(self, ctx: RoomHookContext) -> list[str]:
        direction = str(ctx.params["direction"])
        target = str(ctx.params["target"])
        ttl = int(ctx.params["ttl_ticks"])
        state = ctx.get_state()
        if state.get("open"):
            return ["洞口已经挖开了。"]
        ctx.add_exit(direction, target)
        base = ctx.tick if ctx.tick is not None else 0
        ctx.schedule(self.SCHEDULE_KEY, due_tick=base + ttl)
        ctx.set_state({"open": True, "direction": direction})
        return ["你挖开了一个洞口。"]

    def on_tick(self, ctx: RoomHookContext) -> None:
        if not ctx.schedule_due(self.SCHEDULE_KEY):
            return
        state = ctx.get_state()
        direction = str(state.get("direction") or ctx.params.get("direction", ""))
        if direction:
            ctx.remove_exit(direction)
        ctx.clear_schedule(self.SCHEDULE_KEY)
        ctx.set_state({})
        ctx.message_room("洞口塌陷了！")


def _register_builtin_hooks() -> None:
    """引擎内置机关钩子；``clear_room_hooks`` 后会重新挂上。"""
    if DigCollapseHook.HOOK_ID not in _ROOM_HOOKS:
        _ROOM_HOOKS[DigCollapseHook.HOOK_ID] = DigCollapseHook()


_register_builtin_hooks()


class RoomHookContext:
    """只服务钩子实现的窄外观：绑定当前房间 / 触发实体，不透出 ``World`` 私有结构。"""

    def __init__(
        self,
        world: World,
        room_id: EntityId,
        *,
        actor_id: EntityId | None = None,
        params: Mapping[str, object] | None = None,
        tick: int | None = None,
    ) -> None:
        self._world = world
        self.room_id = room_id
        self.actor_id = actor_id
        self.params: Mapping[str, object] = dict(params) if params is not None else {}
        self.tick = tick
        nature = world.nature
        self.phase = getattr(nature, "phase", "day") if nature else "day"
        self.is_night = bool(getattr(nature, "is_night", False)) if nature else False
        self.is_day = bool(getattr(nature, "is_day", True)) if nature else True

    # ── 出口 ──────────────────────────────────────────────

    def add_exit(
        self,
        direction: str,
        target: EntityId | str,
        aliases: tuple[str, ...] = (),
    ) -> None:
        target_id = self._resolve_room(target)
        exits = self._world.require_component(self.room_id, Exits)
        exits.by_direction[direction] = Exit(target=target_id, aliases=aliases)

    def remove_exit(self, direction: str) -> None:
        exits = self._world.get_component(self.room_id, Exits)
        if exits is not None:
            exits.by_direction.pop(direction, None)

    def hide_exit(self, direction: str) -> None:
        exits = self._world.require_component(self.room_id, Exits)
        pending = exits.by_direction.pop(direction, None)
        if pending is None:
            return
        hidden = self._world.get_component(self.room_id, HiddenExits)
        if hidden is None:
            hidden = HiddenExits()
            self._world.add_component(self.room_id, hidden)
        hidden.by_direction[direction] = HiddenExit(
            target=pending.target, aliases=pending.aliases
        )

    def reveal_exit(self, direction: str) -> None:
        hidden = self._world.get_component(self.room_id, HiddenExits)
        if hidden is None:
            return
        pending = hidden.by_direction.pop(direction, None)
        if pending is None:
            return
        exits = self._world.require_component(self.room_id, Exits)
        exits.by_direction[direction] = Exit(target=pending.target, aliases=pending.aliases)

    # ── 延时自查（落在房间自由状态，不新建通用调度服务）──

    def schedule(self, key: str, due_tick: int) -> None:
        self._free_state().schedules[key] = due_tick

    def clear_schedule(self, key: str) -> None:
        self._free_state().schedules.pop(key, None)

    def schedule_due(self, key: str) -> bool:
        if self.tick is None:
            return False
        due = self._free_state().schedules.get(key)
        return due is not None and self.tick >= due

    # ── 播报 ──────────────────────────────────────────────

    def message_room(self, text: str) -> None:
        for entity in self._world.entities_in_room(self.room_id):
            if self._world.has_component(entity, PlayerSession):
                self._world.push_message(entity, text)

    def message_actor(self, text: str) -> None:
        if self.actor_id is None:
            return
        if self._world.has_component(self.actor_id, PlayerSession):
            self._world.push_message(self.actor_id, text)

    # ── 房间自由状态 ──────────────────────────────────────

    def get_state(self) -> dict[str, object]:
        return dict(self._free_state().data)

    def set_state(self, data: Mapping[str, object]) -> None:
        self._free_state().data = dict(data)

    # ── 受限实体移动（委托独立方法本体）──────────────────

    def move_entity(self, entity_id: EntityId, target: EntityId | str) -> None:
        relocate_entity(self._world, entity_id, self._resolve_room(target))

    def _free_state(self) -> RoomFreeState:
        free = self._world.get_component(self.room_id, RoomFreeState)
        if free is None:
            free = RoomFreeState()
            self._world.add_component(self.room_id, free)
        return free

    def _resolve_room(self, target: EntityId | str) -> EntityId:
        if isinstance(target, str):
            if not self._world.room_ids or target not in self._world.room_ids:
                raise KeyError(f"未知房间键: {target}")
            return self._world.room_ids[target]
        return target


def relocate_entity(world: World, entity_id: EntityId, to_room: EntityId) -> None:
    """受限实体移动方法本体：改 ``Position`` + 分发离房/进房事件。

    供 ``RoomHookContext.move_entity`` 与未来 ``SkillBehavior``（柔丝索）双方直调。
    不跑 before 否决、不自动 look、不处理骑乘——不是通用远程传送命令面。
    """
    from mud_engine.commands import EnterRoomContext

    position = world.require_component(entity_id, Position)
    from_room = position.room
    if from_room == to_room:
        return
    position.room = to_room
    enter_ctx = EnterRoomContext(player_id=entity_id, from_room=from_room, to_room=to_room)
    world.events.dispatch(ON_LEAVE_ROOM, enter_ctx)
    world.events.dispatch(ON_ENTER_ROOM, enter_ctx)


def attach_room_hooks(world: World) -> None:
    """场景加载 / restore 后：按房间绑定订阅进房/离房/心跳（幂等）。

    仅当至少一间房的钩子实现了对应方法时才订阅该事件点，避免无关轮询。
    """
    if getattr(world, "_room_hooks_attached", False):
        return

    enter_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}
    leave_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}
    tick_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}

    for room_id in world.entities_with(RoomHookBinding):
        binding = world.require_component(room_id, RoomHookBinding)
        hook = get_room_hook(binding.hook_id)
        if hook is None:
            raise RuntimeError(
                f"房间 {room_id} 绑定 hook_id '{binding.hook_id}' 但注册表中无此钩子"
            )
        params = binding.params
        if hasattr(hook, "on_enter"):
            enter_bindings[room_id] = (hook, params)
        if hasattr(hook, "on_leave"):
            leave_bindings[room_id] = (hook, params)
        if hasattr(hook, "on_tick"):
            tick_bindings[room_id] = (hook, params)

    if enter_bindings:

        def _on_enter(ctx: Any) -> None:
            entry = enter_bindings.get(ctx.to_room)
            if entry is None:
                return
            hook, params = entry
            hook_ctx = RoomHookContext(
                world, ctx.to_room, actor_id=ctx.player_id, params=params
            )
            hook.on_enter(hook_ctx)  # type: ignore[attr-defined]

        world.events.register(ON_ENTER_ROOM, _on_enter)

    if leave_bindings:

        def _on_leave(ctx: Any) -> None:
            entry = leave_bindings.get(ctx.from_room)
            if entry is None:
                return
            hook, params = entry
            hook_ctx = RoomHookContext(
                world, ctx.from_room, actor_id=ctx.player_id, params=params
            )
            hook.on_leave(hook_ctx)  # type: ignore[attr-defined]

        world.events.register(ON_LEAVE_ROOM, _on_leave)

    if tick_bindings:

        def _on_tick(tick_ctx: TickContext) -> None:
            for room_id, (hook, params) in tick_bindings.items():
                hook_ctx = RoomHookContext(
                    world, room_id, params=params, tick=tick_ctx.tick
                )
                hook.on_tick(hook_ctx)  # type: ignore[attr-defined]

        world.events.register(ON_TICK, _on_tick)

    world._room_hooks_attached = True  # noqa: SLF001


__all__ = [
    "ON_ENTER_ROOM",
    "ON_LEAVE_ROOM",
    "DigCollapseHook",
    "RoomHook",
    "RoomHookContext",
    "attach_room_hooks",
    "clear_room_hooks",
    "get_room_hook",
    "register_room_hook",
    "relocate_entity",
]
