"""Pre-M4-06：时段耦合秘道（复用 is_day/is_night + HiddenExits 揭示）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import (
    Exit,
    Exits,
    HiddenExits,
    Identity,
    PlayerSession,
    Position,
    RoomHookBinding,
)
from mud_engine.nature import attach_nature
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    RoomHookContext,
    TimeOfDayPassageHook,
    clear_room_hooks,
    get_room_hook,
)
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_xingxiu_mechanics
from mud_engine.tick import TickLoop
from mud_engine.world import World


@pytest.fixture(autouse=True)
def _clean_hook_registry() -> None:
    clear_room_hooks()
    yield
    clear_room_hooks()


def _minimal_passage_world(
    *, when: str = "day"
) -> tuple[World, int, int, int]:
    world = World()
    chamber = world.create_entity()
    tunnel = world.create_entity()
    world.add_component(
        chamber,
        Exits(by_direction={"north": Exit(target=tunnel, aliases=("北", "秘道"))}),
    )
    world.add_component(tunnel, Exits(by_direction={"south": Exit(target=chamber)}))
    world.room_ids = {"sunlit_room": chamber, "secret_tunnel": tunnel}
    player = world.create_entity()
    world.add_component(player, Position(room=chamber))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    world.add_component(
        chamber,
        RoomHookBinding(
            hook_id="time_of_day_passage",
            params={"direction": "north", "when": when},
        ),
    )
    attach_nature(world)
    return world, chamber, tunnel, player


def _ctx(world: World, room: int, player: int) -> RoomHookContext:
    binding = world.require_component(room, RoomHookBinding)
    return RoomHookContext(world, room, actor_id=player, params=binding.params)


class TestTimeOfDayPassageS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("time_of_day_passage")
        assert hook is not None
        assert isinstance(hook, TimeOfDayPassageHook)

    def test_night_hides_daytime_passage(self) -> None:
        world, chamber, _tunnel, player = _minimal_passage_world(when="day")
        world.nature.seek_phase("night")
        hook = TimeOfDayPassageHook()
        hook.on_enter(_ctx(world, chamber, player))

        assert "north" not in world.require_component(chamber, Exits).by_direction
        assert "north" in world.require_component(chamber, HiddenExits).by_direction

    def test_day_reveals_after_night_hide(self) -> None:
        world, chamber, tunnel, player = _minimal_passage_world(when="day")
        hook = TimeOfDayPassageHook()
        world.nature.seek_phase("night")
        hook.on_enter(_ctx(world, chamber, player))
        assert "north" not in world.require_component(chamber, Exits).by_direction

        world.nature.seek_phase("day")
        hook.on_enter(_ctx(world, chamber, player))
        assert "north" in world.require_component(chamber, Exits).by_direction
        assert world.require_component(chamber, Exits).by_direction["north"].target == tunnel
        hidden = world.get_component(chamber, HiddenExits)
        assert hidden is None or "north" not in hidden.by_direction


class TestTimeOfDayPassageCommandS1:
    def test_night_look_go_cannot_use_passage(self, tmp_path: Path) -> None:
        scene = """rooms:
  ante:
    name: 前厅
    exits:
      north: sunlit
  sunlit:
    name: 日光玉室
    exits:
      south: ante
      north:
        to: tunnel
        aliases: [北, 秘道]
    hooks:
      hook_id: time_of_day_passage
      params:
        direction: north
        when: day
  tunnel:
    name: 秘道
    exits:
      south: sunlit
player:
  name: 你
  start_room: ante
"""
        path = tmp_path / "tod.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        assert world.nature is not None
        world.nature.seek_phase("night")

        execute_line(world, player_id, "go north")
        look = " ".join(execute_line(world, player_id, "look"))
        assert "秘道" not in look
        before = world.require_component(player_id, Position).room
        go = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == before
        assert any("没有出口" in line or "不能" in line for line in go)

    def test_day_passage_visible_and_walkable(self, tmp_path: Path) -> None:
        scene = """rooms:
  ante:
    name: 前厅
    exits:
      north: sunlit
  sunlit:
    name: 日光玉室
    exits:
      south: ante
      north:
        to: tunnel
        aliases: [北, 秘道]
    hooks:
      hook_id: time_of_day_passage
      params:
        direction: north
        when: day
  tunnel:
    name: 秘道
    exits:
      south: sunlit
player:
  name: 你
  start_room: ante
"""
        path = tmp_path / "tod_day.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        assert world.nature is not None
        world.nature.seek_phase("night")
        execute_line(world, player_id, "go north")
        # 夜间已藏；切白天后靠心跳同步揭示
        world.nature.seek_phase("day")
        TickLoop(lambda: None, world=world, interval=100).advance()

        look = " ".join(execute_line(world, player_id, "look"))
        assert "秘道" in look or "north" in look
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "tunnel"
        ]


class TestXingxiuMechanics06Slice:
    def test_slice_has_sunlit_room_binding(self) -> None:
        world, _pid = load_xingxiu_mechanics()
        assert "sunlit_room" in world.room_ids
        binding = world.require_component(
            world.room_ids["sunlit_room"], RoomHookBinding
        )
        assert binding.hook_id == "time_of_day_passage"
        assert binding.params.get("direction") == "north"
        assert binding.params.get("when") == "day"

    def test_slice_daytime_passage_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        assert world.nature is not None
        world.nature.seek_phase("day")
        execute_line(world, player_id, "go northwest")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "sunlit_room"
        ]
        # 进房同步；白天应已揭示
        look = " ".join(execute_line(world, player_id, "look"))
        assert "秘道" in look or "north" in look
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "secret_tunnel"
        ]
