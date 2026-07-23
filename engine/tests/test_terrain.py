"""M2-15：Terrain + 骑乘通行校验 / 精力扣减 / 精力耗尽摔落。

Polishing-05：步行亦按 ``Terrain.cost * WALK_JINGLI_PER_TERRAIN_COST`` 扣玩家精力。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import (
    Exits,
    Identity,
    Mount,
    Position,
    Riding,
    Terrain,
    Unconscious,
    Vitals,
)
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


_SCENE = """rooms:
  stable:
    name: 马厩
    exits:
      north: road
      east: cliff
    objects:
      horse: 1
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
    mount:
      ability: 5
      jingli_current: 3
      jingli_max: 80
player:
  name: 你
  start_room: stable
"""

_WALK_SCENE = """rooms:
  a:
    name: 平地
    exits:
      north: b
      east: hard
  b:
    name: 缓坡
    cost: 2
    exits:
      south: a
  hard:
    name: 陡坡
    cost: 5
    exits:
      west: a
npcs: {}
player:
  name: 你
  start_room: a
  vitals:
    qi: 100
    neili: 50
    jingli: 10
    jingli_max: 10
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

    def test_walk_ignores_mount_ability_gate(self, tmp_path: Path) -> None:
        """步行不走坐骑 ability 门禁（无 Vitals 时亦不扣玩家精力）。"""
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "go east")
        assert not any("骑不过去" in line for line in lines)
        assert not any("精力不足" in line for line in lines)
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


class TestWalkingTerrainJingli:
    def test_walk_deducts_jingli_when_enough(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _WALK_SCENE))
        # cost=2 → drain=4；jingli=10 → 剩 6
        lines = execute_line(world, player_id, "go north")
        assert not any("精力不足" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room_by_name(world, "缓坡")
        assert world.require_component(player_id, Vitals).jingli_current == 6

    def test_walk_rejected_when_jingli_insufficient(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _WALK_SCENE))
        vitals = world.require_component(player_id, Vitals)
        vitals.jingli_current = 3  # cost=5 → drain=10，不足
        before = world.require_component(player_id, Position).room
        lines = execute_line(world, player_id, "go east")
        assert any("精力不足" in line for line in lines)
        assert world.require_component(player_id, Position).room == before
        assert vitals.jingli_current == 3

    def test_walk_exact_jingli_allows_and_drains_to_zero(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _WALK_SCENE))
        vitals = world.require_component(player_id, Vitals)
        vitals.jingli_current = 4  # cost=2 → drain=4，恰好
        lines = execute_line(world, player_id, "go north")
        assert not any("精力不足" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room_by_name(world, "缓坡")
        assert vitals.jingli_current == 0

    def test_riding_skips_player_walk_jingli_drain(self, tmp_path: Path) -> None:
        """Riding 存在时只扣坐骑精力，不叠加步行玩家精力消耗。"""
        scene = """rooms:
  stable:
    name: 马厩
    exits:
      north: road
    objects:
      horse: 1
  road:
    name: 官道
    cost: 2
    exits:
      south: stable
npcs:
  horse:
    name: 黄骠马
    mount:
      ability: 5
      jingli_current: 10
      jingli_max: 80
player:
  name: 你
  start_room: stable
  vitals:
    qi: 100
    neili: 50
    jingli: 10
    jingli_max: 10
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        player_before = world.require_component(player_id, Vitals).jingli_current
        mount_before = world.require_component(mount, Mount).jingli_current
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == _room_by_name(world, "官道")
        assert world.require_component(player_id, Vitals).jingli_current == player_before
        assert world.require_component(mount, Mount).jingli_current == mount_before - 2
