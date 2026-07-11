"""最小 ECS + 场景加载 + 战斗桥接测试。"""

from __future__ import annotations

from xkx.combat.result import KIND_DAMAGE, KIND_EXP, Effect
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import NpcDef, RoomDef
from xkx.runtime.components import Identity, Position, Progression, Vitals
from xkx.runtime.world import apply_effects, build_world, spawn_player, to_snapshot


def _ir() -> dict:
    rooms = [
        RoomDef(
            id="city/street",
            short="街道",
            long="一条街。",
            exits={"e": "city/chaguan"},
            objects={"city/npc/bing": 1},
        )
    ]
    npcs = [
        NpcDef(
            id="city/npc/bing",
            name="官兵",
            attitude="heroism",
            str_=24,
            dex_=16,
            combat_exp=10000,
            skills={"unarmed": 40, "blade": 40},
            weapon="blade",
            attack_skill="blade",
            weapon_label="刀",
        )
    ]
    return compile_scene(rooms, npcs)


def test_build_world_rooms_and_npcs() -> None:
    world, room_idx, _ = build_world(_ir())
    assert "city/street" in room_idx
    npcs = list(world.entities_in_room("city/street"))
    assert len(npcs) == 1
    eid = npcs[0]
    assert world.get(eid, Identity).name == "官兵"
    assert world.get(eid, Position).room_id == "city/street"


def test_spawn_player() -> None:
    world, _, _ = build_world(_ir())
    pid = spawn_player(world, "玩家", "city/street")
    assert world.get(pid, Identity).is_player
    assert world.get(pid, Position).room_id == "city/street"


def test_to_snapshot() -> None:
    world, _, _ = build_world(_ir())
    eid = next(world.entities_in_room("city/street"))
    snap = to_snapshot(world, eid)
    assert snap.name == "官兵"
    assert snap.str_ == 24
    assert snap.weapon == "blade"
    assert snap.attack_skill == "blade"
    assert snap.weapon_label == "刀"
    assert snap.skills["blade"] == 40


def test_apply_effects_damage() -> None:
    world, _, _ = build_world(_ir())
    pid = spawn_player(world, "玩家", "city/street")
    before = world.get(pid, Vitals).qi
    apply_effects(world, [Effect(kind=KIND_DAMAGE, target_id=pid, amount=30)])
    assert world.get(pid, Vitals).qi == before - 30


def test_apply_effects_exp() -> None:
    world, _, _ = build_world(_ir())
    pid = spawn_player(world, "玩家", "city/street")
    before = world.get(pid, Progression).combat_exp
    apply_effects(world, [Effect(kind=KIND_EXP, target_id=pid, amount=1)])
    assert world.get(pid, Progression).combat_exp == before + 1
