"""M2-15：Terrain + 骑乘通行校验 / 精力扣减 / 精力耗尽摔落。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Exits, Identity, Mount, Position, Riding, Terrain, Unconscious
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _room_by_name(world: World, name: str) -> EntityId:
    for entity in world.entities_with(Exits):
        ident = world.get_component(entity, Identity)
        if ident is not None and ident.name == name:
            return entity
    raise AssertionError(f"room named {name!r} not found")


_SCENE = """
rooms:
  stable:
    name: 马厩
    exits:
      north: road
      east: cliff
  road:
    name: 官道
    cost: 2
    exits:
      south: stable
  cliff:
    name: 悬崖
    cost: 10
    exits:
      west: stable
npcs:
  horse:
    name: 黄骠马
    in_room: stable
    mount:
      ability: 5
      jingli_current: 3
      jingli_max: 80
player:
  name: 你
  start_room: stable
"""


class TestTerrainMountLimits:
    def test_ride_rejected_when_terrain_cost_exceeds_ability(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        jingli_before = world.require_component(mount, Mount).jingli_current
        lines = execute_line(world, player_id, "go east")
        assert any("骑不过去" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room_by_name(world, "马厩")
        assert world.require_component(mount, Mount).jingli_current == jingli_before
        assert world.has_component(player_id, Riding)

    def test_walk_ignores_terrain_cost(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "go east")
        assert not any("骑不过去" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room_by_name(world, "悬崖")

    def test_riding_deducts_mount_jingli_by_terrain_cost(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        jingli_before = world.require_component(mount, Mount).jingli_current
        execute_line(world, player_id, "go north")
        # 扣减量 = Terrain.cost * MOUNT_JINGLI_PER_TERRAIN_COST（系数 1）
        assert world.require_component(mount, Mount).jingli_current == jingli_before - 2
        assert world.has_component(player_id, Riding)
        assert world.require_component(player_id, Position).room == _room_by_name(world, "官道")

    def test_jingli_exhaustion_dismounts_in_destination(self, tmp_path: Path) -> None:
        """人马一起进目标房后马倒：坐骑留在目标房，骑手摔下，移动完成。"""
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        # jingli=3，road cost=2 → 扣后 1，仍骑乘；再回 stable cost 默认 1 → 归零摔落
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "go south")
        assert any("摔" in line or "倒" in line or "精力" in line for line in lines)
        assert not world.has_component(player_id, Riding)
        mount_c = world.require_component(mount, Mount)
        assert mount_c.ridden_by is None
        assert mount_c.jingli_current == 0
        assert world.has_component(mount, Unconscious)
        dest = _room_by_name(world, "马厩")
        assert world.require_component(player_id, Position).room == dest
        assert world.require_component(mount, Position).room == dest

    def test_terrain_and_dismount_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        road = _room_by_name(world, "官道")
        assert world.require_component(road, Terrain).cost == 2
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go south")  # 摔落
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored, rid = restore_world(save_dir)
        road_r = _room_by_name(restored, "官道")
        assert restored.require_component(road_r, Terrain).cost == 2
        assert not restored.has_component(rid, Riding)
        assert restored.has_component(mount, Unconscious)
        assert restored.require_component(mount, Mount).jingli_current == 0
