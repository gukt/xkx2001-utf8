"""端到端：xueshan_micro 场景 -> go(守卫拦截 deny / 放行 allow) -> kill -> 确定性重放。

验证 S3 Agent 生成场景 v1 端到端可跑（基于 d/xueshan/shanmen.c valid_leave 守卫拦截）。
LPC 完整逻辑（门派/物品/AND/allow-wins）受层1 谓词集限制用 present_npc 近似，缺口
见 ADR-0004。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, go, kill
from xkx.runtime.components import Identity, Position, Vitals
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(seed_base: int = 0, start_room: str = "xueshan/shanmen") -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room)
    return Game(world, room_idx, rules, seed_base=seed_base), pid


def _gelun_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("xueshan/shanmen"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no npc in shanmen")


def test_go_north_denied_by_guard() -> None:
    """守卫在场 -> north 被 deny（present_npc 近似 LPC 守卫拦截）。"""
    game, pid = _game()
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/shanmen"
    assert any("供奉" in m for m in msgs)


def test_go_westup_allowed() -> None:
    """dshanlu 无守卫拦截规则 -> 放行进山门。

    shanmen 的守卫规则 present_npc 对所有方向生效（layer1 EventRule 无方向绑定，
    见 ADR-0004 方向绑定缺口），故 allow 路径从无守卫的 dshanlu 起点测。
    """
    game, pid = _game(start_room="xueshan/dshanlu")
    msgs = go(game, pid, "westup")
    assert game.world.get(pid, Position).room_id == "xueshan/shanmen"
    assert any("走去" in m for m in msgs)


def test_kill_combat_runs() -> None:
    """kill 葛伦布触发 resolve_attack 一回合，qi 只减不增。"""
    game, pid = _game(seed_base=42)
    before = game.world.get(_gelun_eid(game), Vitals).qi
    msgs = kill(game, pid, "葛伦布")
    after = game.world.get(_gelun_eid(game), Vitals).qi
    assert len(msgs) >= 2
    assert after <= before


def test_kill_deterministic_seed() -> None:
    """同 seed 两次 kill 结果一致（combat 确定性穿透到命令层）。"""
    g1, p1 = _game(seed_base=42)
    g2, p2 = _game(seed_base=42)
    assert kill(g1, p1, "葛伦布") == kill(g2, p2, "葛伦布")
