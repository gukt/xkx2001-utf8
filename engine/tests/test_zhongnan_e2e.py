"""端到端：zhongnan_micro 场景 -> go(方向绑定守门 deny/放行) -> kill -> 确定性重放。

S4 ADR-0005：方向绑定 + 组合谓词完整表达 d/zhongnan/gate.c valid_leave：
  dir==north + NOT(全真教 OR 持香) -> deny。
方向绑定前守门规则锁死所有出口（ADR-0004 缺口），S4 后 north 受守门、southdown 放行。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, kill
from xkx.runtime.components import Identity, Position, Vitals
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "zhongnan_micro"


def _game(
    seed_base: int = 0,
    start_room: str = "zhongnan/gate",
    family: str = "",
    items: set[str] | None = None,
) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", start_room, family=family, items=items)
    return Game(world, room_idx, rules, seed_base=seed_base), pid


def _pi_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("zhongnan/gate"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no npc in gate")


def test_go_north_denied_by_guard() -> None:
    """无门派无香 -> north 被 deny（皮清玄守门）。"""
    game, pid = _game()
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "zhongnan/gate"
    assert any("请回" in m for m in msgs)


def test_go_southdown_allowed() -> None:
    """southdown 方向不受 north 守门规则拦截（方向绑定，S4 ADR-0005）。

    方向绑定前守门规则全方向锁死，玩家无法从 gate 离开（ADR-0004 缺口）。
    """
    game, pid = _game()
    msgs = go(game, pid, "southdown")
    assert game.world.get(pid, Position).room_id == "zhongnan/dajiaochang"
    assert any("走去" in m for m in msgs)


def test_go_north_allowed_quanzhen() -> None:
    """全真教玩家 -> north 放行（family_eq 谓词，LPC 道兄放行）。"""
    game, pid = _game(family="全真教")
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "zhongnan/gate1"
    assert any("走去" in m for m in msgs)


def test_go_north_allowed_incense() -> None:
    """持香 -> north 放行（has_item 谓词，LPC 进香放行）。"""
    game, pid = _game(items={"incense"})
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "zhongnan/gate1"
    assert any("走去" in m for m in msgs)


def test_kill_combat_runs() -> None:
    """kill 皮清玄触发 resolve_attack 一回合，qi 只减不增。"""
    game, pid = _game(seed_base=42)
    before = game.world.get(_pi_eid(game), Vitals).qi
    msgs = kill(game, pid, "皮清玄")
    after = game.world.get(_pi_eid(game), Vitals).qi
    assert len(msgs) >= 2
    assert after <= before


def test_kill_deterministic_seed() -> None:
    """同 seed 两次 kill 结果一致（combat 确定性穿透到命令层）。"""
    g1, p1 = _game(seed_base=42)
    g2, p2 = _game(seed_base=42)
    assert kill(g1, p1, "皮清玄") == kill(g2, p2, "皮清玄")
