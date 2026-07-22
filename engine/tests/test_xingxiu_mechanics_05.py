"""Pre-M4-05：jump/climb 技能门槛（复用 SkillLevels）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import (
    Exit,
    Exits,
    Identity,
    PlayerSession,
    Position,
    RoomHookBinding,
    SkillLevels,
    SkillProgress,
)
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    RoomHookContext,
    SkillGateHook,
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


def _minimal_gate_world(
    *,
    verb: str = "jump",
    skill_id: str = "dodge",
    min_level: int = 50,
    player_level: int = 0,
) -> tuple[World, int, int, int]:
    world = World()
    edge = world.create_entity()
    far = world.create_entity()
    world.add_component(edge, Exits())
    world.add_component(far, Exits())
    world.require_component(far, Exits).by_direction["south"] = Exit(target=edge)
    world.room_ids = {"cliff_edge": edge, "cliff_far": far}
    player = world.create_entity()
    world.add_component(player, Position(room=edge))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    if player_level > 0:
        world.add_component(
            player, SkillLevels(levels={skill_id: SkillProgress(level=player_level)})
        )
    world.primary_player_id = player
    world.add_component(
        edge,
        RoomHookBinding(
            hook_id="skill_gate",
            params={
                "verb": verb,
                "skill_id": skill_id,
                "min_level": min_level,
                "direction": "north",
                "target": "cliff_far",
            },
        ),
    )
    return world, edge, far, player


class TestSkillGateS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("skill_gate")
        assert hook is not None
        assert isinstance(hook, SkillGateHook)

    def test_low_skill_refuses_high_skill_moves(self) -> None:
        world, edge, far, player = _minimal_gate_world(player_level=10)
        hook = SkillGateHook()
        binding = world.require_component(edge, RoomHookBinding)
        ctx = RoomHookContext(world, edge, actor_id=player, params=binding.params)

        refused = hook.on_jump(ctx)
        assert any("轻功" in m or "不够" in m or "等级" in m for m in refused)
        assert world.require_component(player, Position).room == edge

        world.require_component(player, SkillLevels).levels["dodge"] = SkillProgress(
            level=50
        )
        ok = hook.on_jump(ctx)
        assert any("跳" in m or "跃" in m for m in ok)
        assert world.require_component(player, Position).room == far


class TestSkillGateCommandS1:
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
        for verb in ("jump", "climb", "跳", "爬"):
            joined = "".join(execute_line(world, player_id, verb))
            assert "未知命令" not in joined, verb
            assert "这里不能这么做" in joined, verb

    def test_jump_level_gate(self, tmp_path: Path) -> None:
        scene = """rooms:
  cliff_edge:
    name: 峭壁边
    exits: {}
    hooks:
      hook_id: skill_gate
      params:
        verb: jump
        skill_id: dodge
        min_level: 50
        direction: north
        target: cliff_far
  cliff_far:
    name: 对岸
    exits:
      south: cliff_edge
skills:
  dodge:
    type: martial
    level_req: 0
player:
  name: 你
  start_room: cliff_edge
  skills:
    dodge: 20
"""
        path = tmp_path / "cliff.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)

        low = execute_line(world, player_id, "jump")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "cliff_edge"
        ]
        assert any("轻功" in m or "不够" in m or "等级" in m for m in low)

        world.require_component(player_id, SkillLevels).levels["dodge"] = SkillProgress(
            level=50
        )
        high = execute_line(world, player_id, "jump")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "cliff_far"
        ]
        assert any("跳" in m or "跃" in m for m in high)

    def test_climb_level_gate(self, tmp_path: Path) -> None:
        scene = """rooms:
  cliff_base:
    name: 崖底
    exits: {}
    hooks:
      hook_id: skill_gate
      params:
        verb: climb
        skill_id: dodge
        min_level: 30
        direction: up
        target: cliff_top
  cliff_top:
    name: 崖顶
    exits:
      down: cliff_base
skills:
  dodge:
    type: martial
    level_req: 0
player:
  name: 你
  start_room: cliff_base
  skills:
    dodge: 30
"""
        path = tmp_path / "climb.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        msgs = execute_line(world, player_id, "climb")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "cliff_top"
        ]
        assert any("爬" in m or "攀" in m for m in msgs)


class TestXingxiuMechanics05Slice:
    def test_slice_jump_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        assert "cliff_edge" in world.room_ids
        binding = world.require_component(world.room_ids["cliff_edge"], RoomHookBinding)
        assert binding.hook_id == "skill_gate"
        assert binding.params["verb"] == "jump"

        execute_line(world, player_id, "go northeast")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "cliff_edge"
        ]
        # 切片玩家 dodge 达标
        msgs = execute_line(world, player_id, "jump")
        assert world.require_component(player_id, Position).room == world.room_ids[
            "cliff_far"
        ]
        assert any("跳" in m or "跃" in m for m in msgs)
