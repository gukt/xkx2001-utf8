"""pre-m4-channels-spawn-quest-04：物品/NPC 槽位补刷（S2）。

seam：``load_scene`` + ``spawn_scan`` + 命令面 get/drop；存活判定按登记实例 id。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openmud.ai import spawn_scan
from openmud.components import Container, ItemSpawnMeta, NpcSpawnMeta, Position
from openmud.parsing import execute_line
from openmud.scene_loader import SceneLoadError, load_scene
from openmud.world import World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _item_entities(world: World, template_key: str) -> list[int]:
    return [
        e
        for e in world.entities_with(ItemSpawnMeta)
        if world.require_component(e, ItemSpawnMeta).template_key == template_key
    ]


def _npc_entities(world: World, template_key: str) -> list[int]:
    return [
        e
        for e in world.entities_with(NpcSpawnMeta)
        if world.require_component(e, NpcSpawnMeta).template_key == template_key
    ]


_SCENE_ITEM = """rooms:
  yard:
    name: 院子
    exits:
      north:
        to: shed
    objects:
      pebble: 1
  shed:
    name: 棚屋
    exits:
      south:
        to: yard
items:
  pebble:
    name: 石子
    short: 一颗石子
    respawn: true
npcs: {}
player:
  name: 你
  start_room: yard
"""


class TestItemSlotRespawn:
    class WhenObjectsLoad:
        def test_loads_expected_item_count(self, tmp_path: Path) -> None:
            world, _ = load_scene(_write_scene(tmp_path, _SCENE_ITEM))
            assert len(_item_entities(world, "pebble")) == 1
            assert ("yard", "pebble") in world.item_spawners
            assert world.item_spawners[("yard", "pebble")].desired_count == 1

    class WhenPlayerPicksUpSlotItem:
        def test_scan_does_not_refill_while_in_inventory(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _SCENE_ITEM))
            yard = world.room_ids["yard"]
            assert len(world.require_component(yard, Container).items) == 1
            execute_line(world, player_id, "get 石子")
            assert len(world.require_component(yard, Container).items) == 0
            assert len(_item_entities(world, "pebble")) == 1
            spawn_scan(world)
            assert len(_item_entities(world, "pebble")) == 1
            assert len(world.require_component(yard, Container).items) == 0

    class WhenPlayerDropsSlotItemInOtherRoom:
        def test_scan_does_not_refill_origin_room(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _SCENE_ITEM))
            yard = world.room_ids["yard"]
            shed = world.room_ids["shed"]
            execute_line(world, player_id, "get 石子")
            execute_line(world, player_id, "go north")
            execute_line(world, player_id, "drop 石子")
            assert len(world.require_component(shed, Container).items) == 1
            spawn_scan(world)
            assert len(_item_entities(world, "pebble")) == 1
            assert len(world.require_component(yard, Container).items) == 0

    class WhenSlotItemDestroyedAndRespawnTrue:
        def test_scan_refills_origin_room(self, tmp_path: Path) -> None:
            world, _ = load_scene(_write_scene(tmp_path, _SCENE_ITEM))
            yard = world.room_ids["yard"]
            old = _item_entities(world, "pebble")[0]
            world.destroy_entity(old)
            spawn_scan(world)
            rebuilt = _item_entities(world, "pebble")
            assert len(rebuilt) == 1
            assert rebuilt[0] != old
            assert rebuilt[0] in world.require_component(yard, Container).items

    class WhenSlotItemDestroyedAndRespawnFalse:
        def test_scan_does_not_refill(self, tmp_path: Path) -> None:
            scene = _SCENE_ITEM.replace("respawn: true", "respawn: false")
            world, _ = load_scene(_write_scene(tmp_path, scene))
            old = _item_entities(world, "pebble")[0]
            world.destroy_entity(old)
            spawn_scan(world)
            assert _item_entities(world, "pebble") == []


class TestNpcSlotPointerSemantics:
    class WhenNpcMovedAwayFromStartroom:
        def test_scan_does_not_spawn_extra_while_alive(self, tmp_path: Path) -> None:
            """槽位指针：实体换房仍占名额；旧「全图存活数」在此场景结果相同，
            但登记的是具体实例，商店另造同模板不得占名额（见物品侧）。"""
            scene = """rooms:
  yard:
    name: 院子
    exits:
      north:
        to: shed
    objects:
      guard: 1
  shed:
    name: 棚屋
    exits:
      south:
        to: yard
npcs:
  guard:
    name: 守卫
    respawn: true
player:
  name: 你
  start_room: yard
"""
            world, _ = load_scene(_write_scene(tmp_path, scene))
            npc = _npc_entities(world, "guard")[0]
            shed = world.room_ids["shed"]
            world.require_component(npc, Position).room = shed
            spawn_scan(world)
            assert len(_npc_entities(world, "guard")) == 1

    class WhenNpcDestroyed:
        def test_respawn_true_refills_startroom(self, tmp_path: Path) -> None:
            scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      guard: 1
npcs:
  guard:
    name: 守卫
    respawn: true
player:
  name: 你
  start_room: yard
"""
            world, _ = load_scene(_write_scene(tmp_path, scene))
            old = _npc_entities(world, "guard")[0]
            world.destroy_entity(old)
            spawn_scan(world)
            rebuilt = _npc_entities(world, "guard")
            assert len(rebuilt) == 1
            assert rebuilt[0] != old
            assert world.require_component(rebuilt[0], Position).room == world.room_ids["yard"]


class TestDoorKeyUniqueReference:
    class WhenKeyItemHasCountGreaterThanOne:
        def test_load_rejects(self, tmp_path: Path) -> None:
            scene = """rooms:
  yard:
    name: 院子
    exits:
      north:
        to: shed
        door: locked
        key: yard_key
    objects:
      yard_key: 2
  shed:
    name: 棚屋
    exits:
      south:
        to: yard
items:
  yard_key:
    name: 钥匙
npcs: {}
player:
  name: 你
  start_room: yard
"""
            with pytest.raises(SceneLoadError, match="唯一引用|门锁|key"):
                load_scene(_write_scene(tmp_path, scene))

    class WhenKeyItemAllowsRespawn:
        def test_load_rejects(self, tmp_path: Path) -> None:
            scene = """rooms:
  yard:
    name: 院子
    exits:
      north:
        to: shed
        door: locked
        key: yard_key
    objects:
      yard_key: 1
  shed:
    name: 棚屋
    exits:
      south:
        to: yard
items:
  yard_key:
    name: 钥匙
    respawn: true
npcs: {}
player:
  name: 你
  start_room: yard
"""
            with pytest.raises(SceneLoadError, match="唯一引用|门锁|key|respawn"):
                load_scene(_write_scene(tmp_path, scene))
