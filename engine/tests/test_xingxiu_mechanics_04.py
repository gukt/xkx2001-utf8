"""Pre-M4-04：valid_leave 步数迷途（ON_BEFORE_LEAVE_ROOM 可否决）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.commands import ON_BEFORE_LEAVE_ROOM
from mud_engine.components import (
    Exit,
    Exits,
    Identity,
    PlayerSession,
    Position,
    RoomFreeState,
    RoomHookBinding,
)
from mud_engine.events import Deny
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    LostInMazeHook,
    RoomHookContext,
    attach_room_hooks,
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


def _minimal_maze_world(*, required_steps: int = 3) -> tuple[World, int, int, int]:
    world = World()
    maze = world.create_entity()
    exit_room = world.create_entity()
    world.add_component(maze, Exits())
    world.require_component(maze, Exits).by_direction["east"] = Exit(target=exit_room)
    world.add_component(exit_room, Exits())
    world.require_component(exit_room, Exits).by_direction["west"] = Exit(target=maze)
    world.room_ids = {"desert_maze": maze, "desert_edge": exit_room}
    player = world.create_entity()
    world.add_component(player, Position(room=maze))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    world.add_component(
        maze,
        RoomHookBinding(
            hook_id="lost_in_maze",
            params={"required_steps": required_steps},
        ),
    )
    attach_room_hooks(world)
    return world, maze, exit_room, player


class TestLostInMazeS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("lost_in_maze")
        assert hook is not None
        assert isinstance(hook, LostInMazeHook)

    def test_veto_until_steps_then_allow(self) -> None:
        world, maze, exit_room, player = _minimal_maze_world(required_steps=3)
        hook = LostInMazeHook()
        ctx = RoomHookContext(
            world,
            maze,
            actor_id=player,
            params={"required_steps": 3},
        )
        hook.on_enter(ctx)
        assert world.require_component(maze, RoomFreeState).data.get("steps") == 0

        for _ in range(3):
            denial = hook.veto_leave(ctx, to_room=exit_room)
            assert isinstance(denial, Deny)
            assert "迷" in denial.message or "方向" in denial.message or "走" in denial.message

        assert world.require_component(maze, RoomFreeState).data["steps"] == 3
        assert hook.veto_leave(ctx, to_room=exit_room) is None

    def test_non_escape_leave_not_gated(self) -> None:
        world, maze, exit_room, player = _minimal_maze_world(required_steps=3)
        hub = world.create_entity()
        world.add_component(hub, Exits())
        world.room_ids["desert_hub"] = hub
        binding = world.require_component(maze, RoomHookBinding)
        binding.params = {
            "required_steps": 3,
            "escape_target": "desert_edge",
        }
        hook = LostInMazeHook()
        ctx = RoomHookContext(world, maze, actor_id=player, params=binding.params)
        hook.on_enter(ctx)
        assert hook.veto_leave(ctx, to_room=hub) is None
        assert world.require_component(maze, RoomFreeState).data["steps"] == 0
        assert isinstance(hook.veto_leave(ctx, to_room=exit_room), Deny)


class TestBeforeLeaveRoomEvent:
    def test_constant_stable(self) -> None:
        assert ON_BEFORE_LEAVE_ROOM == "on_before_leave_room"

    def test_go_denied_until_steps(self, tmp_path: Path) -> None:
        scene = """rooms:
  desert_maze:
    name: 大沙漠
    exits:
      east: desert_edge
    hooks:
      hook_id: lost_in_maze
      params:
        required_steps: 2
  desert_edge:
    name: 沙漠边缘
    exits:
      west: desert_maze
player:
  name: 你
  start_room: desert_maze
"""
        path = tmp_path / "maze.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        maze = world.room_ids["desert_maze"]

        first = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == maze
        assert any("迷" in m or "方向" in m or "走" in m for m in first)

        second = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == maze
        assert any("迷" in m or "方向" in m or "走" in m for m in second)

        third = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "desert_edge"
        ]
        assert not any("迷" in m for m in third)


class TestXingxiuMechanics04Slice:
    def test_slice_maze_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        assert "desert_maze" in world.room_ids
        binding = world.require_component(world.room_ids["desert_maze"], RoomHookBinding)
        assert binding.hook_id == "lost_in_maze"
        required = int(binding.params["required_steps"])

        execute_line(world, player_id, "go south")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "desert_maze"
        ]
        # 非 escape 方向可自由离开（回峰脚）
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "dig_base"
        ]
        execute_line(world, player_id, "go south")
        for _ in range(required):
            msgs = execute_line(world, player_id, "go south")
            assert world.require_component(player_id, Position).room == world.room_ids[
                "desert_maze"
            ]
            assert any("迷" in m or "方向" in m or "走" in m for m in msgs)
        execute_line(world, player_id, "go south")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "desert_edge"
        ]
