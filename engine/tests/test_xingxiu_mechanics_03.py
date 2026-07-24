"""Pre-M4-03：多步房间状态机（scrape → pull → push → 开出口）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from openmud.components import (
    Exits,
    Identity,
    PlayerSession,
    Position,
    RoomFreeState,
    RoomHookBinding,
)
from openmud.parsing import execute_line
from openmud.room_hooks import (
    MultiStepGateHook,
    RoomHookContext,
    clear_room_hooks,
    get_room_hook,
)
from openmud.scene_loader import load_scene
from openmud.scenes import load_xingxiu_mechanics
from openmud.world import World


@pytest.fixture(autouse=True)
def _clean_hook_registry() -> None:
    clear_room_hooks()
    yield
    clear_room_hooks()


def _minimal_gate_world() -> tuple[World, int, int, int]:
    world = World()
    gate = world.create_entity()
    chamber = world.create_entity()
    world.add_component(gate, Exits())
    world.add_component(chamber, Exits())
    world.room_ids = {"jade_gate": gate, "jade_chamber": chamber}
    player = world.create_entity()
    world.add_component(player, Position(room=gate))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    world.add_component(
        gate,
        RoomHookBinding(
            hook_id="multi_step_gate",
            params={"direction": "north", "target": "jade_chamber"},
        ),
    )
    return world, gate, chamber, player


def _ctx(world: World, gate: int, player: int) -> RoomHookContext:
    binding = world.require_component(gate, RoomHookBinding)
    return RoomHookContext(
        world, gate, actor_id=player, params=binding.params, tick=world.tick
    )


class TestMultiStepGateS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("multi_step_gate")
        assert hook is not None
        assert isinstance(hook, MultiStepGateHook)

    def test_skip_push_rejected_and_ordered_opens_exit(self) -> None:
        world, gate, chamber, player = _minimal_gate_world()
        hook = MultiStepGateHook()
        ctx = _ctx(world, gate, player)

        skip = hook.on_push(ctx)
        assert any("先" in m or "步骤" in m or "顺序" in m for m in skip)
        assert "north" not in world.require_component(gate, Exits).by_direction
        assert world.require_component(gate, RoomFreeState).data.get("step", 0) == 0

        assert any("锈" in m or "刮" in m for m in hook.on_scrape(ctx))
        assert world.require_component(gate, RoomFreeState).data["step"] == 1

        # 中间跳步：刮锈后直接推门
        mid_skip = hook.on_push(ctx)
        assert any("斧" in m or "先" in m for m in mid_skip)
        assert world.require_component(gate, RoomFreeState).data["step"] == 1

        assert any("斧" in m or "拔" in m for m in hook.on_pull(ctx))
        assert world.require_component(gate, RoomFreeState).data["step"] == 2

        opened = hook.on_push(ctx)
        assert any("门" in m or "开" in m for m in opened)
        exits = world.require_component(gate, Exits)
        assert "north" in exits.by_direction
        assert exits.by_direction["north"].target == chamber
        assert world.require_component(gate, RoomFreeState).data["step"] == 3


class TestMultiStepCommandS1:
    def test_verbs_wrong_room_refuse(self, tmp_path: Path) -> None:
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
        for verb in ("scrape", "pull", "push", "刮锈", "拔斧", "推门"):
            joined = "".join(execute_line(world, player_id, verb))
            assert "未知命令" not in joined, verb
            assert "这里不能这么做" in joined, verb

    def test_skip_then_ordered_sequence_opens_exit(self, tmp_path: Path) -> None:
        scene = """rooms:
  jade_gate:
    name: 玉石甬道
    exits:
      south: hub
    hooks:
      hook_id: multi_step_gate
      params:
        direction: north
        target: jade_chamber
  jade_chamber:
    name: 玉室
    exits:
      south: jade_gate
  hub:
    name: 入口
    exits:
      north: jade_gate
player:
  name: 你
  start_room: jade_gate
"""
        path = tmp_path / "jade.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)

        skip = execute_line(world, player_id, "push")
        assert any("先" in m or "步骤" in m or "顺序" in m for m in skip)
        blocked = execute_line(world, player_id, "go north")
        assert any("没有出口" in m for m in blocked)

        execute_line(world, player_id, "scrape")
        execute_line(world, player_id, "pull")
        opened = execute_line(world, player_id, "push")
        assert any("门" in m or "开" in m for m in opened)

        go_msgs = execute_line(world, player_id, "go north")
        assert not any("没有出口" in m for m in go_msgs), go_msgs
        assert world.require_component(player_id, Position).room == world.room_ids[
            "jade_chamber"
        ]


class TestXingxiuMechanics03Slice:
    def test_slice_has_jade_gate_binding(self) -> None:
        world, _pid = load_xingxiu_mechanics()
        assert "jade_gate" in world.room_ids
        binding = world.require_component(world.room_ids["jade_gate"], RoomHookBinding)
        assert binding.hook_id == "multi_step_gate"

    def test_slice_multi_step_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        # dig_base → jade_gate
        execute_line(world, player_id, "go west")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "jade_gate"
        ]
        execute_line(world, player_id, "刮锈")
        execute_line(world, player_id, "拔斧")
        execute_line(world, player_id, "推门")
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "jade_chamber"
        ]
