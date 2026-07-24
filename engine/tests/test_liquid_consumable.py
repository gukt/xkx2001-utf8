"""Polishing-08：液体灌装 / drink / eat（一次性数值效果）。

接缝：S1 ``execute_line``；S2 ``load_scene``（``resource`` / ``liquid_container`` 消费）。
"""

from __future__ import annotations

from pathlib import Path

from openmud.components import (
    Consumable,
    Container,
    Identity,
    LiquidContainer,
    RoomResources,
    Vitals,
)
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """rooms:
  riverside:
    name: 河边
    long: 河水清澈。
    resource:
      water: true
    exits:
      east: dry
    objects:
      waterskin: 1
      ration: 1
  dry:
    name: 旱地
    long: 没有水源。
    exits:
      west: riverside
items:
  waterskin:
    name: 水袋
    aliases:
    - 皮水袋
    liquid_container: true
  ration:
    name: 干粮
    aliases:
    - 饼
    consumable:
      uses: 2
player:
  name: 你
  start_room: riverside
  vitals:
    qi: 40
    qi_max: 100
    neili: 10
    neili_max: 50
    jingli: 10
    jingli_max: 80
"""


def _item_in_bag(world, player_id, name: str):
    bag = world.require_component(player_id, Container)
    for item in bag.items:
        if world.require_component(item, Identity).name == name:
            return item
    return None


class TestRoomResourceLoad:
    def test_resource_water_consumed(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _SCENE))
        river = world.room_ids["riverside"]
        dry = world.room_ids["dry"]
        res = world.require_component(river, RoomResources)
        assert res.water is True
        assert world.get_component(dry, RoomResources) is None
        assert "resource" not in world.entity_extension_data(river)

    def test_liquid_container_consumed_not_extension(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 水袋")
        skin = _item_in_bag(world, player_id, "水袋")
        assert skin is not None
        assert world.has_component(skin, LiquidContainer)
        extras = world.entity_extension_data(skin)
        assert "liquid_container" not in extras
        assert "filled_liquid" not in extras

    def test_unknown_resource_key_fails_load(self, tmp_path: Path) -> None:
        from openmud.scene_loader import SceneLoadError

        bad = _SCENE.replace("water: true", "grass: true")
        try:
            load_scene(_write_scene(tmp_path, bad))
        except SceneLoadError as exc:
            assert "grass" in str(exc)
        else:
            raise AssertionError("expected SceneLoadError for resource.grass")


class TestFill:
    def test_fill_ok_at_water_room(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 水袋")
        lines = execute_line(world, player_id, "fill 水袋")
        assert any("灌" in line or "装满" in line or "水" in line for line in lines)
        skin = _item_in_bag(world, player_id, "水袋")
        assert skin is not None
        assert world.require_component(skin, LiquidContainer).filled_liquid == "water"

    def test_fill_rejected_without_water(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 水袋")
        execute_line(world, player_id, "go east")
        lines = execute_line(world, player_id, "fill 水袋")
        assert any("水" in line or "这里" in line for line in lines)
        skin = _item_in_bag(world, player_id, "水袋")
        assert skin is not None
        assert world.require_component(skin, LiquidContainer).filled_liquid is None


class TestDrink:
    def test_drink_restores_jingli_and_empties(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 水袋")
        execute_line(world, player_id, "fill 水袋")
        before = world.require_component(player_id, Vitals).jingli_current
        lines = execute_line(world, player_id, "drink 水袋")
        assert any("喝" in line for line in lines)
        after = world.require_component(player_id, Vitals).jingli_current
        assert after > before
        skin = _item_in_bag(world, player_id, "水袋")
        assert skin is not None
        assert world.require_component(skin, LiquidContainer).filled_liquid is None

    def test_drink_rejected_when_empty(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 水袋")
        before = world.require_component(player_id, Vitals).jingli_current
        lines = execute_line(world, player_id, "drink 水袋")
        assert any("空" in line or "没有" in line or "水" in line for line in lines)
        assert world.require_component(player_id, Vitals).jingli_current == before


class TestEat:
    def test_eat_restores_and_decrements_uses(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 干粮")
        food = _item_in_bag(world, player_id, "干粮")
        assert world.require_component(food, Consumable).uses == 2
        before_qi = world.require_component(player_id, Vitals).qi_current
        lines = execute_line(world, player_id, "eat 干粮")
        assert any("吃" in line for line in lines)
        assert world.require_component(player_id, Vitals).qi_current > before_qi
        assert world.require_component(food, Consumable).uses == 1
        assert _item_in_bag(world, player_id, "干粮") is not None

    def test_eat_destroys_when_uses_exhausted(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "get 干粮")
        execute_line(world, player_id, "eat 干粮")
        execute_line(world, player_id, "eat 干粮")
        assert _item_in_bag(world, player_id, "干粮") is None
