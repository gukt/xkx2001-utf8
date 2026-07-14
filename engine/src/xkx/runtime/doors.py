"""门状态机运行时（C5 ADR-0042 + ADR-0044，对照 LPC room.c doors + gate.c knock + call_out 关门）。

标准 doors 状态模式：exits 静态声明不变，``RoomComp.doors`` 存门定义+开闭状态。
``open_door``/``close_door``（ADR-0044）标准开/关门副作用（对照 LPC room.c open_door/
close_door，标准模式无定时关）。``knock_door`` 开门 + schedule ``door_close`` EffectComp
定时关门（gate.c 模式，独有定时关语义）。``DoorSystem`` tick 驱动 ``door_close`` EffectComp
到期关门（closed=True + 同步对面）。

call_out("close_door", N) 翻译为 EffectComp（``effect_id="door_close"``，``detail`` 存门方向），
复用 ADR-0027 call_out->EffectComp 惯例 + GovernanceSystem death_stage 模式。
remove_call_out("close_door") 翻译为移除旧 door_close EffectComp（防重入）。

[ADR-0042](../../../docs/adr/ADR-0042-door-state-machine.md) /
[ADR-0044](../../../docs/adr/ADR-0044-door-open-close-locked.md) /
[ADR-0027](../../../docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) /
[inherit/room/room.c](../../../inherit/room/room.c) /
[d/zhongnan/gate.c](../../../d/zhongnan/gate.c)
"""

from __future__ import annotations

from xkx.runtime.components import EffectComp, RoomComp
from xkx.runtime.ecs import World
from xkx.runtime.systems import System

# door_close EffectComp 标识（detail 字段存门方向）
DOOR_CLOSE_EFFECT_ID = "door_close"
# 默认定时关门延迟（tick，对照 LPC gate.c call_out("close_door", 10)）
DEFAULT_CLOSE_DELAY = 10


def open_door(world: World, room_eid: int, direction: str) -> str:
    """开门副作用（C5 ADR-0044，对照 LPC room.c open_door）。

    开门（``closed=False`` + 同步对面），**不 schedule 定时关**（标准 open 无 timer，
    对照 LPC ``cmds/std/open.c``；定时关是 knock 独有语义，gate.c 模式）。
    返回状态：``no_door`` / ``already_open`` / ``locked`` / ``ok``。消息由调用方
    （open 命令 / knock_door）按状态组织（对齐 LPC open_door 做副作用返回 1/0，
    message_vision 在命令层）。
    """
    room = world.get(room_eid, RoomComp)
    if room is None or direction not in room.doors:
        return "no_door"
    door = room.doors[direction]
    if not door.closed:
        return "already_open"
    if door.locked:
        return "locked"
    door.closed = False
    _sync_other_side(world, room_eid, direction, closed=False)
    return "ok"


def close_door(world: World, room_eid: int, direction: str) -> str:
    """关门副作用（C5 ADR-0044，对照 LPC room.c close_door）。

    关门（``closed=True`` + 同步对面）+ 取消未到期的 ``door_close`` EffectComp
    （手动关门后不再定时关）。返回状态：``no_door`` / ``already_closed`` / ``ok``。
    """
    room = world.get(room_eid, RoomComp)
    if room is None or direction not in room.doors:
        return "no_door"
    door = room.doors[direction]
    if door.closed:
        return "already_closed"
    door.closed = True
    _sync_other_side(world, room_eid, direction, closed=True)
    _remove_door_close_effect(world, room_eid, direction)
    return "ok"


def knock_door(
    world: World,
    room_eid: int,
    direction: str,
    current_tick: int,
    close_delay: int = DEFAULT_CLOSE_DELAY,
) -> str | None:
    """敲门开门 + 定时关（C5 ADR-0042，对照 LPC gate.c do_knock + call_out）。

    knock 独有定时关语义（gate.c 模式），区别于标准 open（无 timer，ADR-0044）。
    调 ``open_door`` 开门（复用开门副作用 + locked 检查），成功后 remove 旧
    ``door_close`` EffectComp（对齐 LPC ``remove_call_out`` 防重入）+ schedule 新
    ``door_close`` EffectComp 定时关。返回敲门消息（None=没门，调用方另行提示）。
    """
    room = world.get(room_eid, RoomComp)
    if room is None or direction not in room.doors:
        return None
    door = room.doors[direction]
    status = open_door(world, room_eid, direction)
    if status == "already_open":
        return f"{door.name}已经开着了。"
    if status == "locked":
        return f"{door.name}锁着，敲不开。"
    # status == "ok"：开门成功，schedule 定时关（knock 独有，对齐 LPC call_out）
    _remove_door_close_effect(world, room_eid, direction)
    effect_eid = world.new_entity()
    world.add(
        effect_eid,
        EffectComp(
            effect_id=DOOR_CLOSE_EFFECT_ID,
            kind="door",
            target_id=room_eid,
            detail=direction,
            duration=close_delay,
            tick_interval=close_delay,
            next_tick=current_tick + close_delay,
        ),
    )
    return f"你敲了敲{door.name}，{door.name}吱呀一声开了。"


def _sync_other_side(
    world: World, room_eid: int, direction: str, *, closed: bool
) -> None:
    """双向同步：设对面房间 doors[other_dir].closed（对照 LPC open_door 递归同步）。"""
    room = world.get(room_eid, RoomComp)
    if room is None or direction not in room.doors:
        return
    door = room.doors[direction]
    other_room = _get_room_by_id(world, door.other_room)
    if other_room is not None and door.other_dir in other_room.doors:
        other_room.doors[door.other_dir].closed = closed


def _close_door(world: World, room_eid: int, direction: str) -> None:
    """关门 + 同步对面（DoorSystem 到期调用）。"""
    room = world.get(room_eid, RoomComp)
    if room is None or direction not in room.doors:
        return
    room.doors[direction].closed = True
    _sync_other_side(world, room_eid, direction, closed=True)


def _remove_door_close_effect(
    world: World, room_eid: int, direction: str
) -> None:
    """移除旧 door_close EffectComp（对齐 LPC remove_call_out，防重入）。"""
    for eid in list(world.entities_with(EffectComp)):
        eff = world.get(eid, EffectComp)
        if (
            eff is not None
            and eff.effect_id == DOOR_CLOSE_EFFECT_ID
            and eff.target_id == room_eid
            and eff.detail == direction
        ):
            world.remove(eid, EffectComp)


def _get_room_by_id(world: World, room_id: str) -> RoomComp | None:
    """按 room_id 找 RoomComp（线性扫描，房间数有限，复用 auto_fight._get_room 模式）。"""
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    return None


class DoorSystem(System):
    """门定时关门系统（C5 ADR-0042，对照 LPC call_out("close_door", N)）。

    tick 驱动 door_close EffectComp（非均匀 tick，``next_tick<=tick`` 触发），到期关门
    （``closed=True`` + 同步对面）+ remove EffectComp。仿 GovernanceSystem death_stage 模式。
    door_close EffectComp 用 ``detail`` 字段存门方向（不改 EffectComp 结构）。
    """

    name = "DoorSystem"

    def update(self, world: World, tick: int) -> None:
        """每 tick 遍历到期 door_close EffectComp，apply 关门 + remove。"""
        pending: list[tuple[int, EffectComp]] = []
        for effect_eid in world.entities_with(EffectComp):
            eff = world.get(effect_eid, EffectComp)
            if eff is None or eff.effect_id != DOOR_CLOSE_EFFECT_ID:
                continue
            if eff.next_tick <= tick:
                pending.append((effect_eid, eff))
        for effect_eid, eff in pending:
            _close_door(world, eff.target_id, eff.detail)
            world.remove(effect_eid, EffectComp)
