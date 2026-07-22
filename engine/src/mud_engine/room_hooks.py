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
    SkillLevels,
    Container,
    ItemTags,
)
from mud_engine.events import ON_TICK, Deny, TickContext
from mud_engine.world import EntityId, World

# 进房 / 离房事件名与 commands / entity_gate 对齐（字符串常量，避免循环 import）。
ON_ENTER_ROOM = "on_enter_room"
ON_LEAVE_ROOM = "on_leave_room"
ON_BEFORE_LEAVE_ROOM = "on_before_leave_room"


class RoomHook(Protocol):
    """房间生命周期钩子。方法全部可选；未实现的方法视为不参与对应事件点。

    约定可选方法签名::

        def on_enter(self, ctx: RoomHookContext) -> None: ...
        def on_leave(self, ctx: RoomHookContext) -> None: ...
        def on_tick(self, ctx: RoomHookContext) -> None: ...
        def on_dig(self, ctx: RoomHookContext) -> list[str]: ...  # 命令动词 dig
        def on_scrape(self, ctx: RoomHookContext) -> list[str]: ...
        def on_pull(self, ctx: RoomHookContext) -> list[str]: ...
        def on_push(self, ctx: RoomHookContext) -> list[str]: ...
        def on_jump(self, ctx: RoomHookContext) -> list[str]: ...
        def on_climb(self, ctx: RoomHookContext) -> list[str]: ...
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


class MultiStepGateHook:
    """机关 #3：多步顺序动作开出口（玉路刮锈→拔斧→推门灵感）。

    YAML ``hooks.params``::

        direction: <完成后新增出口方向>
        target: <目标房间键>
    """

    HOOK_ID = "multi_step_gate"
    # 步骤索引：0 未开始 → scrape → 1 → pull → 2 → push → 3（出口已开）
    _STEP_SCRAPE = 0
    _STEP_PULL = 1
    _STEP_PUSH = 2
    _STEP_DONE = 3

    def on_scrape(self, ctx: RoomHookContext) -> list[str]:
        return self._advance(ctx, expected=self._STEP_SCRAPE, done_msg="你刮去了门环上的铁锈。")

    def on_pull(self, ctx: RoomHookContext) -> list[str]:
        return self._advance(ctx, expected=self._STEP_PULL, done_msg="你拔出了插在门环里的斧头。")

    def on_push(self, ctx: RoomHookContext) -> list[str]:
        msgs = self._advance(ctx, expected=self._STEP_PUSH, done_msg="你用力推开了石门。")
        if int(ctx.get_state().get("step", 0)) == self._STEP_DONE:
            ctx.add_exit(str(ctx.params["direction"]), str(ctx.params["target"]))
        return msgs

    def _advance(self, ctx: RoomHookContext, *, expected: int, done_msg: str) -> list[str]:
        step = int(ctx.get_state().get("step", 0))
        if step != expected:
            return [self._out_of_order_message(step)]
        ctx.set_state({"step": expected + 1})
        return [done_msg]

    @staticmethod
    def _out_of_order_message(step: int) -> str:
        if step >= MultiStepGateHook._STEP_DONE:
            return "石门已经打开了。"
        hints = ("先刮去铁锈。", "先拔出斧头。", "按顺序：刮锈、拔斧、再推门。")
        if 0 <= step < len(hints):
            return hints[step]
        return "步骤不对，请按顺序操作。"


class LostInMazeHook:
    """机关 #4：离开前须在房内「走够」若干次（沙漠迷途灵感）。

    不进入 ``RoomHook`` 通用 before_leave 方法族；由 ``attach_room_hooks`` 专挂
    ``ON_BEFORE_LEAVE_ROOM``（可否决）。YAML ``hooks.params``::

        required_steps: <针对 escape_target 的否决次数阈值；达此步数后允许离开>
        escape_target: <可选；仅离开前往该房间键时否决/计步；缺省则任何离房都闸>
    """

    HOOK_ID = "lost_in_maze"

    def on_enter(self, ctx: RoomHookContext) -> None:
        ctx.set_state({"steps": 0})

    def veto_leave(
        self, ctx: RoomHookContext, *, to_room: EntityId | None = None
    ) -> Deny | None:
        """步数未达标则否决并计一步；达标则放行（不递增）。

        ``to_room`` 供 ``escape_target`` 过滤：非逃出方向的离房放行且不计步。
        """
        escape_key = ctx.params.get("escape_target")
        if escape_key is not None and to_room is not None:
            try:
                escape_id = ctx.resolve_room_id(str(escape_key))
            except KeyError:
                escape_id = None
            if escape_id is not None and to_room != escape_id:
                return None
        required = int(ctx.params.get("required_steps", 1))
        state = ctx.get_state()
        steps = int(state.get("steps", 0))
        if steps < required:
            ctx.set_state({"steps": steps + 1})
            return Deny("你在茫茫沙海中迷失了方向，只好走回原地。")
        return None


class SkillGateHook:
    """机关 #5：jump/climb 技能等级门槛（白玉峰 / 天路灵感）。

    命令面是 ``jump``/``climb``（非 ``go``）；``direction`` 标明该命令对应的通行方向
    （文案与作者意图），``target`` 为成功后落点。YAML ``hooks.params``::

        verb: jump | climb
        skill_id: <SkillLevels 键>
        min_level: <最低等级>
        direction: <对应通行方向，写入成功播报>
        target: <目标房间键>
    """

    HOOK_ID = "skill_gate"

    def on_jump(self, ctx: RoomHookContext) -> list[str]:
        return self._try_skill_passage(ctx, verb="jump")

    def on_climb(self, ctx: RoomHookContext) -> list[str]:
        return self._try_skill_passage(ctx, verb="climb")

    def _try_skill_passage(self, ctx: RoomHookContext, *, verb: str) -> list[str]:
        configured = str(ctx.params.get("verb", ""))
        if configured != verb:
            return ["这里不能这么做。"]
        if ctx.actor_id is None:
            return ["没有可移动的角色。"]
        skill_id = str(ctx.params["skill_id"])
        min_level = int(ctx.params["min_level"])
        level = ctx.actor_skill_level(skill_id)
        if level < min_level:
            return [f"你的轻功不够（需 {skill_id} 等级 {min_level}），过不去。"]
        target = str(ctx.params["target"])
        direction = str(ctx.params.get("direction", "")).strip()
        ctx.move_entity(ctx.actor_id, target)
        if verb == "jump":
            if direction:
                return [f"你向{direction}纵身一跃，过去了。"]
            return ["你纵身一跃，落到了对面。"]
        if direction:
            return [f"你向{direction}攀爬而上，过去了。"]
        return ["你攀爬而上，到了高处。"]


class TimeOfDayPassageHook:
    """机关 #6：仅在特定时段揭示隐藏出口（玉室日光灵感）。

    YAML 把秘道写成普通 ``exits``；钩子在进房 / 心跳时按 ``when`` 在
    ``Exits`` ↔ ``HiddenExits`` 间迁移（复用 ``reveal_exit`` / ``hide_exit``）。
    YAML ``hooks.params``::

        direction: <秘道方向>
        when: day | night   # 对应 ctx.is_day / ctx.is_night
    """

    HOOK_ID = "time_of_day_passage"

    def on_enter(self, ctx: RoomHookContext) -> None:
        self._sync(ctx)

    def on_tick(self, ctx: RoomHookContext) -> None:
        self._sync(ctx)

    def _sync(self, ctx: RoomHookContext) -> None:
        direction = str(ctx.params["direction"])
        when = str(ctx.params.get("when", "day"))
        if when not in ("day", "night"):
            raise ValueError(
                f"time_of_day_passage params.when 须为 'day' 或 'night'，实际是 {when!r}"
            )
        want_open = ctx.is_day if when == "day" else ctx.is_night
        state = ctx.get_state()
        if "revealed" not in state:
            # YAML 出口先落在 Exits；首 sync 立刻经 hide→(可选)reveal 迁入 HiddenExits 路径，
            # 与「非对应时段保持隐藏 / 对应时段从 HiddenExits 揭示」模型对齐。
            ctx.hide_exit(direction)
            if want_open:
                ctx.reveal_exit(direction)
                ctx.set_state({"revealed": True})
            else:
                ctx.set_state({"revealed": False})
            return
        revealed = bool(state["revealed"])
        if want_open and not revealed:
            ctx.reveal_exit(direction)
            ctx.set_state({"revealed": True})
        elif not want_open and revealed:
            ctx.hide_exit(direction)
            ctx.set_state({"revealed": False})


class MagneticIronHook:
    """机关 #7：携带命中标签物品进房时播报磁力效果（玉厅灵感）。

    本票只做到可观察播报，不强制卸除物品。YAML ``hooks.params``::

        tag: <ItemTags 中须命中的标签，默认 iron>
    """

    HOOK_ID = "magnetic_iron"

    def on_enter(self, ctx: RoomHookContext) -> None:
        tag = str(ctx.params.get("tag", "iron"))
        if ctx.actor_has_item_tag(tag):
            ctx.message_actor(f"一股强大的磁力将你身上带「{tag}」标记的器物牢牢吸住！")


def _register_builtin_hooks() -> None:
    """引擎内置机关钩子；``clear_room_hooks`` 后会重新挂上。"""
    builtins: list[tuple[str, RoomHook]] = [
        (DigCollapseHook.HOOK_ID, DigCollapseHook()),
        (MultiStepGateHook.HOOK_ID, MultiStepGateHook()),
        (LostInMazeHook.HOOK_ID, LostInMazeHook()),
        (SkillGateHook.HOOK_ID, SkillGateHook()),
        (TimeOfDayPassageHook.HOOK_ID, TimeOfDayPassageHook()),
        (MagneticIronHook.HOOK_ID, MagneticIronHook()),
    ]
    for hook_id, hook in builtins:
        if hook_id not in _ROOM_HOOKS:
            _ROOM_HOOKS[hook_id] = hook


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

    # ── 只读：角色技能等级（复用 SkillLevels，不新造判定）──

    def actor_skill_level(self, skill_id: str) -> int:
        if self.actor_id is None:
            return 0
        skills = self._world.get_component(self.actor_id, SkillLevels)
        if skills is None:
            return 0
        progress = skills.levels.get(skill_id)
        return progress.level if progress is not None else 0

    def actor_has_item_tag(self, tag: str) -> bool:
        """触发实体背包内是否有带 ``tag`` 的 ``ItemTags`` 物品（携带，非持刃专用谓词）。"""
        if self.actor_id is None:
            return False
        bag = self._world.get_component(self.actor_id, Container)
        if bag is None:
            return False
        for item in bag.items:
            tags = self._world.get_component(item, ItemTags)
            if tags is not None and tag in tags.tags:
                return True
        return False

    # ── 受限实体移动（委托独立方法本体）──────────────────

    def move_entity(self, entity_id: EntityId, target: EntityId | str) -> None:
        relocate_entity(self._world, entity_id, self._resolve_room(target))

    def resolve_room_id(self, target: EntityId | str) -> EntityId:
        """把房间键或实体 id 解析为 ``EntityId``（供钩子比对 escape_target 等）。"""
        return self._resolve_room(target)

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
    ``veto_leave`` 专挂 ``ON_BEFORE_LEAVE_ROOM``（可否决），不进入 RoomHook 通用协议族。
    """
    if getattr(world, "_room_hooks_attached", False):
        return

    enter_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}
    leave_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}
    tick_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}
    leave_veto_bindings: dict[EntityId, tuple[RoomHook, Mapping[str, object]]] = {}

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
        if hasattr(hook, "veto_leave"):
            leave_veto_bindings[room_id] = (hook, params)

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

    if leave_veto_bindings:

        def _on_before_leave(ctx: Any) -> Deny | None:
            entry = leave_veto_bindings.get(ctx.from_room)
            if entry is None:
                return None
            hook, params = entry
            hook_ctx = RoomHookContext(
                world, ctx.from_room, actor_id=ctx.player_id, params=params
            )
            return hook.veto_leave(hook_ctx, to_room=ctx.to_room)  # type: ignore[attr-defined]

        world.events.register(ON_BEFORE_LEAVE_ROOM, _on_before_leave)

    if tick_bindings:

        def _on_tick(tick_ctx: TickContext) -> None:
            for room_id, (hook, params) in tick_bindings.items():
                hook_ctx = RoomHookContext(
                    world, room_id, params=params, tick=tick_ctx.tick
                )
                hook.on_tick(hook_ctx)  # type: ignore[attr-defined]

        world.events.register(ON_TICK, _on_tick)
        # 冷启动：挂载后立刻跑一轮 on_tick（如时段秘道在首 look/go 前就藏/揭出口）。
        # dig_collapse 等无 due schedule 时 no-op。
        for room_id, (hook, params) in tick_bindings.items():
            hook_ctx = RoomHookContext(
                world, room_id, params=params, tick=world.tick
            )
            hook.on_tick(hook_ctx)  # type: ignore[attr-defined]

    world._room_hooks_attached = True  # noqa: SLF001


__all__ = [
    "ON_BEFORE_LEAVE_ROOM",
    "ON_ENTER_ROOM",
    "ON_LEAVE_ROOM",
    "DigCollapseHook",
    "LostInMazeHook",
    "MagneticIronHook",
    "MultiStepGateHook",
    "RoomHook",
    "RoomHookContext",
    "SkillGateHook",
    "TimeOfDayPassageHook",
    "attach_room_hooks",
    "clear_room_hooks",
    "get_room_hook",
    "register_room_hook",
    "relocate_entity",
]
