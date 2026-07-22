"""Pre-M4-02：动态出口+时限崩塌（dig_collapse）+ 加载期 random_of（S0/S1/S2）。"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from mud_engine.components import Exits, Position, RoomFreeState, RoomHookBinding
from mud_engine.errors import SceneLoadError
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    DigCollapseHook,
    RoomHookContext,
    clear_room_hooks,
    get_room_hook,
)
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import XINGXIU_MECHANICS_PATH, load_xingxiu_mechanics
from mud_engine.tick import TickLoop
from mud_engine.world import World


@pytest.fixture(autouse=True)
def _clean_hook_registry() -> None:
    clear_room_hooks()
    yield
    clear_room_hooks()


def _minimal_dig_world(*, ttl_ticks: int = 3) -> tuple[World, int, int, int]:
    world = World()
    peak = world.create_entity()
    cave = world.create_entity()
    world.add_component(peak, Exits())
    world.add_component(cave, Exits())
    world.room_ids = {"dig_peak": peak, "dig_cave": cave}
    player = world.create_entity()
    from mud_engine.components import Identity, PlayerSession

    world.add_component(player, Position(room=peak))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    world.add_component(
        peak,
        RoomHookBinding(
            hook_id="dig_collapse",
            params={
                "direction": "north",
                "target": "dig_cave",
                "ttl_ticks": ttl_ticks,
            },
        ),
    )
    return world, peak, cave, player


class TestDigCollapseS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("dig_collapse")
        assert hook is not None
        assert isinstance(hook, DigCollapseHook)

    def test_on_dig_adds_exit_and_schedules(self) -> None:
        world, peak, cave, player = _minimal_dig_world(ttl_ticks=3)
        hook = DigCollapseHook()
        ctx = RoomHookContext(
            world,
            peak,
            actor_id=player,
            params={
                "direction": "north",
                "target": "dig_cave",
                "ttl_ticks": 3,
            },
            tick=world.tick,
        )
        messages = hook.on_dig(ctx)
        assert any("洞口" in m for m in messages)
        exits = world.require_component(peak, Exits)
        assert "north" in exits.by_direction
        assert exits.by_direction["north"].target == cave
        free = world.require_component(peak, RoomFreeState)
        assert DigCollapseHook.SCHEDULE_KEY in free.schedules
        assert free.schedules[DigCollapseHook.SCHEDULE_KEY] == 3

    def test_on_tick_collapses_when_due(self) -> None:
        world, peak, cave, player = _minimal_dig_world(ttl_ticks=2)
        hook = DigCollapseHook()
        ctx = RoomHookContext(
            world,
            peak,
            actor_id=player,
            params={
                "direction": "north",
                "target": "dig_cave",
                "ttl_ticks": 2,
            },
            tick=0,
        )
        hook.on_dig(ctx)
        assert "north" in world.require_component(peak, Exits).by_direction

        # 未到期
        hook.on_tick(RoomHookContext(world, peak, params=ctx.params, tick=1))
        assert "north" in world.require_component(peak, Exits).by_direction

        # 到期崩塌
        hook.on_tick(RoomHookContext(world, peak, params=ctx.params, tick=2))
        assert "north" not in world.require_component(peak, Exits).by_direction
        assert DigCollapseHook.SCHEDULE_KEY not in world.require_component(
            peak, RoomFreeState
        ).schedules
        assert any("塌" in m for m in world.drain_messages(player))


class TestDigCommandS1:
    def test_dig_wrong_room_refuses_not_unknown(self, tmp_path: Path) -> None:
        scene = """rooms:
  plain:
    name: 普通房
    exits: {}
player:
  name: 你
  start_room: plain
"""
        path = tmp_path / "plain.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        messages = execute_line(world, player_id, "dig")
        joined = "".join(messages)
        assert "未知命令" not in joined
        assert "这里不能这么做" in joined

    def test_dig_go_then_collapse(self, tmp_path: Path) -> None:
        scene = """rooms:
  dig_peak:
    name: 峰顶
    exits:
      south: dig_base
    hooks:
      hook_id: dig_collapse
      params:
        direction: north
        target: dig_cave
        ttl_ticks: 2
  dig_cave:
    name: 洞内
    exits:
      south: dig_peak
  dig_base:
    name: 峰脚
    exits:
      north: dig_peak
player:
  name: 你
  start_room: dig_peak
"""
        path = tmp_path / "dig.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        dig_msgs = execute_line(world, player_id, "dig")
        assert any("洞口" in m for m in dig_msgs)

        go_msgs = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids["dig_cave"]
        assert not any("没有出口" in m for m in go_msgs)

        execute_line(world, player_id, "go south")  # 回到峰顶
        loop = TickLoop(lambda: None, world=world, interval=100)
        loop.advance()  # tick=1，未到期（due=2）
        peak_exits = world.require_component(world.room_ids["dig_peak"], Exits)
        assert "north" in peak_exits.by_direction
        loop.advance()  # tick=2，崩塌
        peak_exits = world.require_component(world.room_ids["dig_peak"], Exits)
        assert "north" not in peak_exits.by_direction

        blocked = execute_line(world, player_id, "go north")
        assert any("没有出口" in m for m in blocked)


_FORK_SCENE = """rooms:
  hub:
    name: 岔路口
    exits:
      north:
        random_of:
          - left
          - right
        aliases:
          - 北
  left:
    name: 左岔
    exits:
      south: hub
  right:
    name: 右岔
    exits:
      south: hub
player:
  name: 你
  start_room: hub
"""


class TestRandomOfS2:
    def test_load_resolves_to_ordinary_exit(self, tmp_path: Path) -> None:
        path = tmp_path / "fork.yaml"
        path.write_text(_FORK_SCENE, encoding="utf-8")
        world, _pid = load_scene(path, rng=random.Random(0))
        hub = world.room_ids["hub"]
        exits = world.require_component(hub, Exits)
        assert "north" in exits.by_direction
        target = exits.by_direction["north"].target
        assert target in (world.room_ids["left"], world.room_ids["right"])
        # 落地后是普通 Exit，无运行时随机字段
        assert exits.by_direction["north"].aliases == ("北",)

    def test_same_seed_stable_across_go(self, tmp_path: Path) -> None:
        path = tmp_path / "fork.yaml"
        path.write_text(_FORK_SCENE, encoding="utf-8")
        world, player_id = load_scene(path, rng=random.Random(1))
        first = execute_line(world, player_id, "go north")
        assert not any("没有出口" in m for m in first)
        dest1 = world.require_component(player_id, Position).room
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go north")
        dest2 = world.require_component(player_id, Position).room
        assert dest1 == dest2

    def test_reload_can_differ_with_different_seeds(self, tmp_path: Path) -> None:
        path = tmp_path / "fork.yaml"
        path.write_text(_FORK_SCENE, encoding="utf-8")
        targets: set[int] = set()
        for seed in range(20):
            world, _ = load_scene(path, rng=random.Random(seed))
            target = world.require_component(world.room_ids["hub"], Exits).by_direction[
                "north"
            ].target
            targets.add(target)
            if len(targets) > 1:
                break
        assert len(targets) > 1

    def test_random_of_empty_fails(self, tmp_path: Path) -> None:
        bad = """rooms:
  hub:
    name: 岔
    exits:
      north:
        random_of: []
  left:
    name: 左
player:
  name: 你
  start_room: hub
"""
        path = tmp_path / "bad.yaml"
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(SceneLoadError, match="random_of"):
            load_scene(path)

    def test_random_of_and_to_mutually_exclusive(self, tmp_path: Path) -> None:
        bad = """rooms:
  hub:
    name: 岔
    exits:
      north:
        to: left
        random_of:
          - left
          - right
  left:
    name: 左
  right:
    name: 右
player:
  name: 你
  start_room: hub
"""
        path = tmp_path / "bad.yaml"
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(SceneLoadError, match="random_of|to"):
            load_scene(path)


class TestXingxiuMechanicsSceneS2:
    def test_official_slice_loads(self) -> None:
        assert XINGXIU_MECHANICS_PATH.is_file()
        world, player_id = load_xingxiu_mechanics()
        assert world.pack_manifest is None
        assert player_id is not None
        assert "dig_peak" in world.room_ids
        assert "fork_hub" in world.room_ids
        peak = world.room_ids["dig_peak"]
        binding = world.require_component(peak, RoomHookBinding)
        assert binding.hook_id == "dig_collapse"
        hub = world.room_ids["fork_hub"]
        north = world.require_component(hub, Exits).by_direction["north"]
        assert north.target in (
            world.room_ids["fork_left"],
            world.room_ids["fork_right"],
        )

    def test_slice_dig_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        # 走到挖洞房
        while world.require_component(player_id, Position).room != world.room_ids["dig_peak"]:
            msgs = execute_line(world, player_id, "go north")
            assert not any("没有出口" in m for m in msgs), msgs
        dig_msgs = execute_line(world, player_id, "dig")
        assert any("洞口" in m for m in dig_msgs)
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids["dig_cave"]
