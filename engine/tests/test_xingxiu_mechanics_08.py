"""Pre-M4-08：劫匪刷拦（编排 spawn + 复用 block_exits）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import (
    BlockExits,
    Exit,
    Exits,
    Identity,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    RoomHookBinding,
)
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    BanditAmbushHook,
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


_AMBUSH_SCENE = """rooms:
  trail:
    name: 山脚小径
    exits:
      north: road_end
      south: ante
    block_exits:
      north:
        npc: road_bandit
    objects:
      road_bandit: 0
    hooks:
      hook_id: bandit_ambush
      params:
        npc: road_bandit
  ante:
    name: 入口
    exits:
      north: trail
  road_end:
    name: 路尽头
    exits:
      south: trail
npcs:
  road_bandit:
    name: 劫匪
    respawn: false
    vitals:
      qi_current: 30
      qi_max: 30
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
player:
  name: 你
  start_room: ante
"""


def _minimal_ambush_world() -> tuple[World, int, int]:
    """手工 World：蓝图已登记、房间空、绑定 bandit_ambush。"""
    from mud_engine.ai import SpawnerBlueprint

    world = World()
    trail = world.create_entity()
    ante = world.create_entity()
    end = world.create_entity()
    world.add_component(
        trail,
        Exits(
            by_direction={
                "north": Exit(target=end),
                "south": Exit(target=ante),
            }
        ),
    )
    world.add_component(ante, Exits(by_direction={"north": Exit(target=trail)}))
    world.add_component(end, Exits(by_direction={"south": Exit(target=trail)}))
    world.add_component(trail, BlockExits(by_direction={"north": "road_bandit"}))
    world.room_ids = {"trail": trail, "ante": ante, "road_end": end}
    world.spawners["road_bandit"] = SpawnerBlueprint(
        template_key="road_bandit",
        name="劫匪",
        aliases=(),
        short="劫匪",
        long="拦路劫匪。",
        startroom=trail,
        desired_count=0,
        respawn=False,
    )
    player = world.create_entity()
    world.add_component(player, Position(room=trail))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    world.add_component(
        trail,
        RoomHookBinding(hook_id="bandit_ambush", params={"npc": "road_bandit"}),
    )
    return world, trail, player


def _ctx(world: World, room: int, player: int) -> RoomHookContext:
    binding = world.require_component(room, RoomHookBinding)
    return RoomHookContext(world, room, actor_id=player, params=binding.params)


def _bandit_in_room(world: World, room: int) -> int | None:
    for entity in world.entities_in_room(room):
        meta = world.get_component(entity, NpcSpawnMeta)
        if meta is not None and meta.template_key == "road_bandit":
            return entity
    return None


class TestBanditAmbushS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("bandit_ambush")
        assert hook is not None
        assert isinstance(hook, BanditAmbushHook)

    def test_on_enter_spawns_npc_and_broadcasts(self) -> None:
        world, trail, player = _minimal_ambush_world()
        assert _bandit_in_room(world, trail) is None
        BanditAmbushHook().on_enter(_ctx(world, trail, player))
        assert _bandit_in_room(world, trail) is not None
        msgs = world.drain_messages(player)
        assert any("劫匪" in m or "拦" in m for m in msgs)

    def test_on_enter_idempotent_when_already_present(self) -> None:
        world, trail, player = _minimal_ambush_world()
        BanditAmbushHook().on_enter(_ctx(world, trail, player))
        first = _bandit_in_room(world, trail)
        world.drain_messages(player)
        BanditAmbushHook().on_enter(_ctx(world, trail, player))
        assert _bandit_in_room(world, trail) == first
        assert world.drain_messages(player) == []


class TestBanditAmbushCommandS1:
    def test_enter_spawns_blocks_then_clear_after_npc_gone(self, tmp_path: Path) -> None:
        path = tmp_path / "ambush.yaml"
        path.write_text(_AMBUSH_SCENE, encoding="utf-8")
        world, player_id = load_scene(path)
        trail = world.room_ids["trail"]
        assert _bandit_in_room(world, trail) is None

        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == trail
        assert _bandit_in_room(world, trail) is not None
        joined = " ".join(world.drain_messages(player_id))
        assert "劫匪" in joined or "拦" in joined

        before = world.require_component(player_id, Position).room
        blocked = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == before
        assert any("挡" in line for line in blocked)

        npc = _bandit_in_room(world, trail)
        assert npc is not None
        world.destroy_entity(npc)
        execute_line(world, player_id, "go north")
        assert (
            world.require_component(player_id, Position).room
            == world.room_ids["road_end"]
        )


class TestXingxiuMechanics08Slice:
    def test_slice_has_ambush_binding(self) -> None:
        world, _pid = load_xingxiu_mechanics()
        assert "ambush_trail" in world.room_ids
        room = world.room_ids["ambush_trail"]
        binding = world.require_component(room, RoomHookBinding)
        assert binding.hook_id == "bandit_ambush"
        assert binding.params.get("npc") == "road_bandit"
        block = world.require_component(room, BlockExits)
        assert block.by_direction.get("north") == "road_bandit"
        assert "road_bandit" in world.spawners
        assert world.spawners["road_bandit"].desired_count == 0
        assert _bandit_in_room(world, room) is None

    def test_slice_ambush_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        ambush = world.room_ids["ambush_trail"]
        execute_line(world, player_id, "go path")
        assert world.require_component(player_id, Position).room == ambush
        assert _bandit_in_room(world, ambush) is not None
        joined = " ".join(world.drain_messages(player_id))
        assert "劫匪" in joined or "拦" in joined
        blocked = execute_line(world, player_id, "go north")
        assert any("挡" in line for line in blocked)
