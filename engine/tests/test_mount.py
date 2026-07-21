"""M2-10：Mount / Riding + ride/unride + buy mount + 骑乘同步移动。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Currency, Ferry, Mount, Position, Riding
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """
rooms:
  stable:
    name: 马厩
    exits:
      north: road
  road:
    name: 官道
    exits:
      south: stable
npcs:
  horse:
    name: 黄骠马
    in_room: stable
    mount:
      ability: 5
      jingli_current: 80
      jingli_max: 80
  groom:
    name: 马夫
    in_room: stable
    shop:
      - mount: horse
        price: 50
player:
  name: 你
  start_room: stable
  currency: 100
"""


class TestMountAndRiding:
    def test_ride_and_unride(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "ride 黄骠马")
        assert any("骑上" in line for line in lines)
        riding = world.require_component(player_id, Riding)
        mount = riding.mount_id
        assert world.require_component(mount, Mount).ridden_by == player_id
        lines = execute_line(world, player_id, "unride")
        assert any("下来" in line for line in lines)
        assert not world.has_component(player_id, Riding)
        assert world.require_component(mount, Mount).ridden_by is None

    def test_ride_while_already_riding(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        lines = execute_line(world, player_id, "ride 黄骠马")
        assert any("已经" in line for line in lines)

    def test_go_syncs_mount_position(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        lines = execute_line(world, player_id, "go north")
        assert any("骑着" in line for line in lines)
        player_room = world.require_component(player_id, Position).room
        mount_room = world.require_component(mount, Position).room
        assert player_room == mount_room
        # look 坐骑同房
        look = execute_line(world, player_id, "look")
        assert any("黄骠马" in line for line in look)

    def test_buy_mount_spawns_in_room(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        before = world.require_component(player_id, Currency).amount
        lines = execute_line(world, player_id, "buy 黄骠马")
        assert any("50" in line for line in lines)
        assert world.require_component(player_id, Currency).amount == before - 50
        # 新坐骑在房间，可 ride（原展示马 + 新买的马可能同名两匹）
        room = world.require_component(player_id, Position).room
        mounts = [
            e
            for e in world.entities_in_room(room, exclude=player_id)
            if world.has_component(e, Mount)
        ]
        assert len(mounts) >= 2

    def test_mount_riding_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored, rid = restore_world(save_dir)
        assert restored.require_component(rid, Riding).mount_id == mount
        assert restored.require_component(mount, Mount).ridden_by == rid


_MOUNT_FERRY_SCENE = """
rooms:
  road:
    name: 官道
    exits:
      east: west_bank
  west_bank:
    name: 西岸渡口
    cost: 2
    ferry:
      far_bank: east_bank
      cross_interval: 3
      direction: across
    exits:
      west: road
  east_bank:
    name: 东岸渡口
    cost: 2
    ferry:
      far_bank: west_bank
      cross_interval: 3
      direction: across
    exits: {}
npcs:
  horse:
    name: 黄骠马
    in_room: road
    mount:
      ability: 5
      jingli_current: 80
      jingli_max: 80
player:
  name: 你
  start_room: road
"""


class TestMountFerryCross:
    def test_riding_go_across_syncs_mount_and_respects_terrain(self, tmp_path: Path) -> None:
        """B3-4：骑乘沿官道到渡口，船在场时 go 过河；人马同步，Terrain.cost 不误拒。"""
        world, player_id = load_scene(_write_scene(tmp_path, _MOUNT_FERRY_SCENE))
        execute_line(world, player_id, "ride 黄骠马")
        mount = world.require_component(player_id, Riding).mount_id
        road_lines = execute_line(world, player_id, "go east")
        assert not any("骑不过去" in line for line in road_lines)
        west = world.require_component(player_id, Position).room
        assert world.has_component(west, Ferry)
        assert world.require_component(mount, Position).room == west
        lines = execute_line(world, player_id, "go across")
        assert not any("骑不过去" in line for line in lines)
        assert any("东岸" in line for line in lines)
        player_room = world.require_component(player_id, Position).room
        mount_room = world.require_component(mount, Position).room
        assert player_room == mount_room
        assert world.require_component(player_room, Ferry).far_bank != player_room
        assert world.require_component(player_room, Ferry).far_bank == west
