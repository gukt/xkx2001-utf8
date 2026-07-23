"""Pre-M4-09：杀令介入简化（Faction 条件 + 房间自由状态防重复）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import (
    Engaged,
    Exit,
    Exits,
    Faction,
    Identity,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    RoomFreeState,
    RoomHookBinding,
    Vitals,
)
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    KillOrderHook,
    RoomHookContext,
    clear_room_hooks,
    get_room_hook,
)
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_xingxiu_mechanics
from mud_engine.world import World


@pytest.fixture(autouse=True)
def _clean_hook_registry() -> None:
    clear_room_hooks()
    yield
    clear_room_hooks()


_KILL_ORDER_SCENE = """factions:
  shaolin:
    display_name: 少林
    skill_pool: []
rooms:
  ante:
    name: 洞外
    exits:
      north: sun_moon_cave
  sun_moon_cave:
    name: 日月洞
    exits:
      south: ante
    objects:
      cave_guard: 1
    hooks:
      hook_id: kill_order
      params:
        faction: shaolin
        npc: cave_guard
npcs:
  cave_guard:
    name: 洞卫
    respawn: false
    vitals:
      qi_current: 50
      qi_max: 50
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
player:
  name: 你
  start_room: ante
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
"""


def _minimal_kill_order_world(
    *, faction_id: str | None = "shaolin"
) -> tuple[World, int, int, int]:
    """返回 (world, cave, player, guard)。"""
    from mud_engine.ai import SpawnerBlueprint, spawn_from_blueprint

    world = World()
    cave = world.create_entity()
    ante = world.create_entity()
    world.add_component(cave, Exits(by_direction={"south": Exit(target=ante)}))
    world.add_component(ante, Exits(by_direction={"north": Exit(target=cave)}))
    world.room_ids = {"sun_moon_cave": cave, "ante": ante}
    world.spawners["cave_guard"] = SpawnerBlueprint(
        template_key="cave_guard",
        name="洞卫",
        aliases=(),
        short="洞卫",
        long="洞口守卫。",
        startroom=cave,
        desired_count=1,
        respawn=False,
        extras={
            "capabilities": (
                Vitals(
                    qi_current=50,
                    qi_max=50,
                    neili_current=0,
                    neili_max=0,
                    jingli_current=10,
                    jingli_max=10,
                ),
            )
        },
    )
    guard = spawn_from_blueprint(world, world.spawners["cave_guard"], room=cave)
    world.spawners["cave_guard"].slots.append(guard)

    player = world.create_entity()
    world.add_component(player, Position(room=cave))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.add_component(
        player,
        Vitals(
            qi_current=100,
            qi_max=100,
            neili_current=50,
            neili_max=50,
            jingli_current=50,
            jingli_max=50,
        ),
    )
    if faction_id is not None:
        world.add_component(player, Faction(faction_id=faction_id))
    world.primary_player_id = player
    world.add_component(
        cave,
        RoomHookBinding(
            hook_id="kill_order",
            params={"faction": "shaolin", "npc": "cave_guard"},
        ),
    )
    return world, cave, player, guard


def _ctx(world: World, cave: int, player: int) -> RoomHookContext:
    binding = world.require_component(cave, RoomHookBinding)
    return RoomHookContext(world, cave, actor_id=player, params=binding.params)


class TestKillOrderS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("kill_order")
        assert hook is not None
        assert isinstance(hook, KillOrderHook)

    def test_matching_faction_triggers_once(self) -> None:
        world, cave, player, guard = _minimal_kill_order_world(faction_id="shaolin")
        KillOrderHook().on_enter(_ctx(world, cave, player))
        msgs = world.drain_messages(player)
        assert any("杀令" in m or "杀气" in m or "敌意" in m for m in msgs)
        assert world.has_component(player, Engaged)
        assert world.require_component(player, Engaged).opponent == guard
        assert world.require_component(cave, RoomFreeState).data.get("triggered") is True

        world.drain_messages(player)
        KillOrderHook().on_enter(_ctx(world, cave, player))
        assert world.drain_messages(player) == []

    def test_wrong_faction_silent(self) -> None:
        world, cave, player, _guard = _minimal_kill_order_world(faction_id="beggars")
        KillOrderHook().on_enter(_ctx(world, cave, player))
        assert world.drain_messages(player) == []
        assert not world.has_component(player, Engaged)

    def test_no_faction_silent(self) -> None:
        world, cave, player, _guard = _minimal_kill_order_world(faction_id=None)
        KillOrderHook().on_enter(_ctx(world, cave, player))
        assert world.drain_messages(player) == []

    def test_leave_resets_trigger_flag(self) -> None:
        world, cave, player, _guard = _minimal_kill_order_world(faction_id="shaolin")
        KillOrderHook().on_enter(_ctx(world, cave, player))
        free = world.require_component(cave, RoomFreeState)
        free.data["other"] = "keep"
        assert free.data.get("triggered") is True
        KillOrderHook().on_leave(_ctx(world, cave, player))
        state = world.require_component(cave, RoomFreeState).data
        assert state.get("triggered") is not True
        assert state.get("other") == "keep"


class TestKillOrderCommandS1:
    def test_enter_triggers_once_same_visit(self, tmp_path: Path) -> None:
        path = tmp_path / "kill_order.yaml"
        path.write_text(_KILL_ORDER_SCENE, encoding="utf-8")
        world, player_id = load_scene(path)
        world.add_component(player_id, Faction(faction_id="shaolin"))

        execute_line(world, player_id, "go north")
        joined = " ".join(world.drain_messages(player_id))
        assert "杀令" in joined or "杀气" in joined or "敌意" in joined
        assert world.has_component(player_id, Engaged)

        # 同次在场：再走一遍 leave+enter 会重置；这里用 look 不应再触发
        world.drain_messages(player_id)
        execute_line(world, player_id, "look")
        look_joined = " ".join(world.drain_messages(player_id))
        assert "杀令" not in look_joined
        assert "杀气" not in look_joined

        # 离房再进：可再次介入
        execute_line(world, player_id, "go south")
        world.drain_messages(player_id)
        # 清交战以免 try_engage 失败
        if world.has_component(player_id, Engaged):
            from mud_engine.combat_system import clear_engagement

            clear_engagement(world, player_id)
        execute_line(world, player_id, "go north")
        again = " ".join(world.drain_messages(player_id))
        assert "杀令" in again or "杀气" in again or "敌意" in again

    def test_wrong_faction_no_intervention(self, tmp_path: Path) -> None:
        path = tmp_path / "kill_order2.yaml"
        path.write_text(_KILL_ORDER_SCENE, encoding="utf-8")
        world, player_id = load_scene(path)
        world.add_component(player_id, Faction(faction_id="beggars"))
        execute_line(world, player_id, "go north")
        joined = " ".join(world.drain_messages(player_id))
        assert "杀令" not in joined
        assert "杀气" not in joined
        assert not world.has_component(player_id, Engaged)


class TestXingxiuMechanics09Slice:
    def test_slice_has_kill_order_binding(self) -> None:
        world, _pid = load_xingxiu_mechanics()
        assert "sun_moon_cave" in world.room_ids
        room = world.room_ids["sun_moon_cave"]
        binding = world.require_component(room, RoomHookBinding)
        assert binding.hook_id == "kill_order"
        assert binding.params.get("faction") == "shaolin"
        assert binding.params.get("npc") == "cave_guard"
        assert any(
            (m := world.get_component(e, NpcSpawnMeta))
            and m.template_key == "cave_guard"
            for e in world.entities_in_room(room)
        )

    def test_slice_kill_order_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        assert world.require_component(player_id, Faction).faction_id == "shaolin"
        cave = world.room_ids["sun_moon_cave"]
        execute_line(world, player_id, "go cave")
        assert world.require_component(player_id, Position).room == cave
        joined = " ".join(world.drain_messages(player_id))
        assert "杀令" in joined or "杀气" in joined or "敌意" in joined
        assert world.has_component(player_id, Engaged)
