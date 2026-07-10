"""端到端：加载场景 -> go(触发 valid_leave) -> kill(触发 resolve_attack)。"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, kill
from xkx.runtime.components import Attributes, Identity, Position, Vitals
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "wuxia_micro"


def _game(player_age: int = 22, seed_base: int = 0) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx = build_world(ir)
    pid = spawn_player(world, "玩家", "city/street")
    world.get(pid, Attributes).age = player_age
    return Game(world, room_idx, rules, seed_base=seed_base), pid


def _bing_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("city/street"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no npc in street")


def test_go_allow() -> None:
    game, pid = _game(player_age=22)
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "city/chaguan"
    assert any("走去" in m for m in msgs)


def test_go_deny_age() -> None:
    game, pid = _game(player_age=15)
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "city/street"
    assert any("小毛孩子" in m for m in msgs)


def test_go_no_exit() -> None:
    game, pid = _game()
    msgs = go(game, pid, "up")
    assert game.world.get(pid, Position).room_id == "city/street"
    assert any("没有" in m for m in msgs)


def test_kill_combat_runs() -> None:
    game, pid = _game(seed_base=42)
    before = game.world.get(_bing_eid(game), Vitals).qi
    msgs = kill(game, pid, "官兵")
    after = game.world.get(_bing_eid(game), Vitals).qi
    # 战斗消息非空（招式描述 + 结果 + 伤害汇总）
    assert len(msgs) >= 2
    # qi 只会减少或不变（dodge/parry 时不变，HIT 时减）
    assert after <= before


def test_kill_no_target() -> None:
    game, pid = _game()
    msgs = kill(game, pid, "路人")
    assert any("没有" in m for m in msgs)


def test_kill_uses_deterministic_seed() -> None:
    """同 seed_base 两次 kill 结果一致（combat 确定性穿透到命令层）。"""
    game1, pid1 = _game(seed_base=42)
    game2, pid2 = _game(seed_base=42)
    msgs1 = kill(game1, pid1, "官兵")
    msgs2 = kill(game2, pid2, "官兵")
    assert msgs1 == msgs2
