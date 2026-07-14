"""书院微场景 e2e：验证 CombatKernel 跑在非武侠题材（戒尺）上。

用 ``present_npc`` 谓词（监生看守藏书阁），与武侠（age_lt）/大航海（attr_lt）
形成题材 + 谓词双重差异化，证明层1 规则与战斗内核均不绑武侠语义。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, kill
from xkx.runtime.components import Identity, Position, Vitals
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "academy_micro"


def _game(seed_base: int = 0) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "书生", "academy/courtyard")
    game = Game(world, room_idx, rules, seed_base=seed_base)
    # ADR-0039：接入 Engine + CombatBridge（战斗 tick 驱动）+ 治理/恢复 System
    from xkx.runtime.conditions import ConditionSystem
    from xkx.runtime.engine import CombatBridge, Engine
    from xkx.runtime.governance import GovernanceSystem
    from xkx.runtime.heal import HealSystem

    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    game.engine = engine  # type: ignore[attr-defined]
    return game, pid


def _student_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("academy/library"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no student in library")


def test_go_to_library_allow() -> None:
    game, pid = _game()
    msgs = go(game, pid, "east")
    assert game.world.get(pid, Position).room_id == "academy/library"
    assert any("走去" in m for m in msgs)


def test_go_blocked_by_student() -> None:
    """藏书阁有监生时不得擅离（present_npc 谓词，非武侠题材）。"""
    game, pid = _game()
    go(game, pid, "east")  # 进藏书阁
    msgs = go(game, pid, "west")  # 监生拦路
    assert game.world.get(pid, Position).room_id == "academy/library"
    assert any("戒尺" in m for m in msgs)


def test_kill_student_runs() -> None:
    game, pid = _game(seed_base=42)
    go(game, pid, "east")  # 进藏书阁
    student_eid = _student_eid(game)
    before = game.world.get(student_eid, Vitals).qi
    msgs = kill(game, pid, "监生")
    after = game.world.get(student_eid, Vitals).qi
    assert len(msgs) >= 2
    assert after <= before


def test_kill_deterministic_seed() -> None:
    """同 seed_base 两次 kill 结果一致（combat 确定性穿透到非武侠场景）。"""
    game1, pid1 = _game(seed_base=42)
    game2, pid2 = _game(seed_base=42)
    go(game1, pid1, "east")
    go(game2, pid2, "east")
    assert kill(game1, pid1, "监生") == kill(game2, pid2, "监生")
