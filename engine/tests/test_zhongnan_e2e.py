"""端到端：zhongnan_micro 场景 -> go(守门 deny / 放行 allow) -> kill -> 确定性重放。

验证 S3 Agent 生成场景 v1 端到端可跑（基于 d/zhongnan/gate.c valid_leave 守门拦截）。
LPC 完整逻辑（门派/物品/OR/allow-wins/门状态机）受层1 谓词集限制用 present_npc 近似，
缺口见 ADR-0004。
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


def _game(seed_base: int = 0, start_room: str = "zhongnan/gate") -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room)
    return Game(world, room_idx, rules, seed_base=seed_base), pid


def _pi_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("zhongnan/gate"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no npc in gate")


def test_go_north_denied_by_guard() -> None:
    """皮清玄在场 -> north 被 deny（present_npc 近似 LPC 守门拦截）。"""
    game, pid = _game()
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "zhongnan/gate"
    assert any("请回" in m for m in msgs)


def test_go_northup_allowed() -> None:
    """dajiaochang 无守门拦截规则 -> 放行进大门。

    gate 的守门规则 present_npc 对所有方向生效（layer1 EventRule 无方向绑定，
    见 ADR-0004 方向绑定缺口），故 allow 路径从无守卫的 dajiaochang 起点测。
    """
    game, pid = _game(start_room="zhongnan/dajiaochang")
    msgs = go(game, pid, "northup")
    assert game.world.get(pid, Position).room_id == "zhongnan/gate"
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
