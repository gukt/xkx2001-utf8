"""C5 ADR-0042：门状态机端到端测试。

标准 doors 状态模式：knock 开门 + call_out 定时关 + 跨房间双向同步 + go 挡路。
对照 LPC d/zhongnan/gate.c do_knock + call_out("close_door", 10) + 双向同步。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items, load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, close, go, knock, look, take, unlock
from xkx.runtime.commands import open as open_cmd
from xkx.runtime.components import Inventory, Position, RoomComp
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(start_room: str = "xueshan/shanmen") -> tuple[Game, int]:
    """加载场景 + 接入 Engine（含 DoorSystem），返回 (game, player_id)。"""
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    item_defs = load_items(SCENE_DIR / "items.yaml")
    ir = compile_scene(rooms, npcs, quests, items=item_defs)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room)
    item_registry = {i.id: i.model_dump() for i in item_defs}  # C4 ADR-0043 完整 dict
    game = Game(world, room_idx, rules, quests=quest_idx, item_registry=item_registry)
    from xkx.runtime.conditions import ConditionSystem
    from xkx.runtime.doors import DoorSystem
    from xkx.runtime.engine import CombatBridge, Engine
    from xkx.runtime.governance import GovernanceSystem
    from xkx.runtime.heal import HealSystem

    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    engine.add_system(DoorSystem())  # C5 门定时关门
    game.engine = engine  # type: ignore[attr-defined]
    return game, pid


def test_door_closed_blocks_go() -> None:
    """门关着挡路（对照 LPC valid_leave doors status 检查）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = go(game, pid, "north")  # wangyou north 铁门关
    assert any("铁门关着" in m for m in msgs)
    # 玩家仍在 wangyou
    assert game.world.get(pid, Position).room_id == "xueshan/wangyou"


def test_knock_opens_door() -> None:
    """knock 开门后 go 通过（对照 LPC do_knock）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = knock(game, pid, "north")
    assert any("开了" in m for m in msgs)
    go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/mishi"


def test_knock_syncs_other_side() -> None:
    """knock 双向同步：对面房间 doors[other_dir] 同步开（对照 LPC open_door 递归）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    knock(game, pid, "north")
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    mishi = game.world.get(game.room_entities["xueshan/mishi"], RoomComp)
    assert not wangyou.doors["north"].closed
    assert not mishi.doors["south"].closed  # 双向同步


def test_door_auto_close_after_tick() -> None:
    """DoorSystem 定时关门（对照 LPC call_out("close_door", 10)）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    knock(game, pid, "north")
    # 推进 tick（DEFAULT_CLOSE_DELAY=10，推进 11 tick 到期关门）
    for _ in range(11):
        game.engine.tick()
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    mishi = game.world.get(game.room_entities["xueshan/mishi"], RoomComp)
    assert wangyou.doors["north"].closed  # 自动关
    assert mishi.doors["south"].closed  # 双向同步关


def test_look_shows_door_status() -> None:
    """look 出口标注门状态（对照 LPC item_desc look_door）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = look(game, pid)
    assert any("铁门关" in m for m in msgs)
    knock(game, pid, "north")
    msgs = look(game, pid)
    assert any("铁门开" in m for m in msgs)


def test_knock_no_door() -> None:
    """无门方向 knock 提示（门数据驱动，对照 LPC 无 add_action verb）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = knock(game, pid, "west")  # west 无门（exit 到 luyeyuan 但无门）
    assert any("没有门" in m for m in msgs)


# ── C5 ADR-0044：open/close 命令 + LOCKED 位 ──


def test_open_command_opens_door() -> None:
    """open 命令开门（对照 LPC cmds/std/open.c，标准模式无定时关）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = open_cmd(game, pid, "north")
    assert any("打开" in m for m in msgs)
    go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/mishi"


def test_close_command_closes_door() -> None:
    """close 命令关门 + go 再挡路（对照 LPC cmds/std/close.c）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    open_cmd(game, pid, "north")
    msgs = close(game, pid, "north")
    assert any("关上" in m for m in msgs)
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    assert wangyou.doors["north"].closed  # 关上
    msgs = go(game, pid, "north")
    assert any("关着" in m for m in msgs)  # 挡路


def test_open_no_timer() -> None:
    """open 开门后推进 tick 门不自动关（标准 open 无 timer，对照 knock 定时关）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    open_cmd(game, pid, "north")
    for _ in range(11):  # DEFAULT_CLOSE_DELAY=10，推进 11 tick
        game.engine.tick()
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    assert not wangyou.doors["north"].closed  # open 无定时关，门保持开


def test_close_cancels_knock_timer() -> None:
    """close 取消 knock 的定时关 EffectComp（手动关门后不再定时关）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    knock(game, pid, "north")  # knock 开门 + schedule 定时关
    close(game, pid, "north")  # close 关门 + 取消定时关 EffectComp
    open_cmd(game, pid, "north")  # 再开门（open 不 schedule 定时关）
    for _ in range(11):
        game.engine.tick()
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    assert not wangyou.doors["north"].closed  # timer 已被 close 取消，门保持开


def test_open_already_open() -> None:
    """已开门再 open 提示（对照 LPC open_door 已开 notify_fail）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    open_cmd(game, pid, "north")
    msgs = open_cmd(game, pid, "north")
    assert any("已经开着" in m for m in msgs)


def test_locked_door_blocks_open() -> None:
    """locked 门 open 提示需钥匙，knock 敲不开，go 仍挡路（locked 检查分支）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    wangyou = game.world.get(game.room_entities["xueshan/wangyou"], RoomComp)
    wangyou.doors["north"].locked = True  # 场景铁门构造 locked 测试 locked 分支
    msgs = open_cmd(game, pid, "north")
    assert any("锁着" in m and "钥匙" in m for m in msgs)
    assert wangyou.doors["north"].closed  # 仍关着
    msgs = knock(game, pid, "north")
    assert any("锁着" in m for m in msgs)  # knock 也敲不开
    msgs = go(game, pid, "north")
    assert any("锁着" in m for m in msgs)  # go 挡路提示锁着


# ── C5 钥匙系统：unlock 命令 + key_id 匹配（对照 LPC donglang.c/houyuan.c do_unlock）──


def test_locked_scene_door_blocks_go() -> None:
    """场景 locked 门挡路：dadian 北铁锁门 locked，go 提示锁着需钥匙。"""
    game, pid = _game(start_room="xueshan/dadian")
    msgs = go(game, pid, "north")
    assert any("锁" in m for m in msgs)
    assert game.world.get(pid, Position).room_id == "xueshan/dadian"


def test_unlock_without_key_rejected() -> None:
    """无钥匙 unlock 被拒，门仍锁（对照 LPC present(key) 检查失败）。"""
    game, pid = _game(start_room="xueshan/dadian")
    msgs = unlock(game, pid, "north")
    assert any("没有合适的钥匙" in m for m in msgs)
    door = game.world.get(game.room_entities["xueshan/dadian"], RoomComp).doors["north"]
    assert door.locked  # 仍锁


def test_unlock_with_key_opens_and_syncs() -> None:
    """有钥匙 unlock 开锁开门 + 双向同步 + go 通过（对照 LPC do_unlock + set exits 双向）。"""
    game, pid = _game(start_room="xueshan/changlang")
    take(game, pid, "铁钥匙")  # changlang 地面拾取钥匙
    inv = game.world.get(pid, Inventory)
    assert "xueshan/obj/key" in inv.items
    go(game, pid, "north")  # changlang -> dadian
    assert game.world.get(pid, Position).room_id == "xueshan/dadian"
    msgs = unlock(game, pid, "north")
    assert any("钥匙" in m and "开" in m for m in msgs)
    # 双向同步：dadian + cangjing 铁锁门都解锁+开
    dadian = game.world.get(game.room_entities["xueshan/dadian"], RoomComp)
    cangjing = game.world.get(game.room_entities["xueshan/cangjing"], RoomComp)
    assert not dadian.doors["north"].locked
    assert not dadian.doors["north"].closed
    assert not cangjing.doors["south"].locked
    assert not cangjing.doors["south"].closed
    go(game, pid, "north")  # 进藏经阁
    assert game.world.get(pid, Position).room_id == "xueshan/cangjing"


def test_unlock_not_locked_door() -> None:
    """未锁门 unlock 提示没有上锁（对照 LPC do_unlock on unlocked）。"""
    game, pid = _game(start_room="xueshan/wangyou")
    msgs = unlock(game, pid, "north")  # wangyou 北铁门未锁（标准 doors）
    assert any("没有上锁" in m for m in msgs)
