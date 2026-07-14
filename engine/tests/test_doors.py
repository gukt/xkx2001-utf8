"""C5 ADR-0042：门状态机端到端测试。

标准 doors 状态模式：knock 开门 + call_out 定时关 + 跨房间双向同步 + go 挡路。
对照 LPC d/zhongnan/gate.c do_knock + call_out("close_door", 10) + 双向同步。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, knock, look
from xkx.runtime.components import Position, RoomComp
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(start_room: str = "xueshan/shanmen") -> tuple[Game, int]:
    """加载场景 + 接入 Engine（含 DoorSystem），返回 (game, player_id)。"""
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs, quests)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room)
    game = Game(world, room_idx, rules, quests=quest_idx)
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
