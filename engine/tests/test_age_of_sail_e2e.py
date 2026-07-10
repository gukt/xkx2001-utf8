"""大航海微场景 e2e：验证 CombatKernel 跑在非武侠题材（火器）上。

题材无关性硬门禁（源码不含武侠武器硬编码）见 ``test_theme_neutrality.py``；
本文件验证非武侠场景能端到端跑通（go + valid_leave + kill + 确定性重放）。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, kill
from xkx.runtime.components import Attributes, Identity, Position, Vitals
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "age_of_sail_micro"


def _game(player_int: int = 20, seed_base: int = 0) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "水手", "port/dock")
    world.get(pid, Attributes).int_ = player_int
    return Game(world, room_idx, rules, seed_base=seed_base), pid


def _pirate_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("port/dock"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no pirate on dock")


def test_go_allow() -> None:
    game, pid = _game(player_int=20)
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "ship/deck"
    assert any("走去" in m for m in msgs)


def test_go_deny_low_int() -> None:
    game, pid = _game(player_int=8)
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "port/dock"
    assert any("上不得船" in m for m in msgs)


def test_kill_pirate_runs() -> None:
    game, pid = _game(seed_base=42)
    before = game.world.get(_pirate_eid(game), Vitals).qi
    msgs = kill(game, pid, "海盗")
    after = game.world.get(_pirate_eid(game), Vitals).qi
    assert len(msgs) >= 2
    assert after <= before


def test_kill_no_target() -> None:
    game, pid = _game()
    msgs = kill(game, pid, "美人鱼")
    assert any("没有" in m for m in msgs)


def test_kill_deterministic_seed() -> None:
    """同 seed_base 两次 kill 结果一致（combat 确定性穿透到非武侠场景）。"""
    game1, pid1 = _game(seed_base=42)
    game2, pid2 = _game(seed_base=42)
    assert kill(game1, pid1, "海盗") == kill(game2, pid2, "海盗")
