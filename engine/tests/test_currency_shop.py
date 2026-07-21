"""M2-07：Currency + ShopInventory + buy/sell。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import Container, Currency, Identity
from mud_engine.errors import SceneLoadError
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SHOP_SCENE = """
rooms:
  shop:
    name: 杂货铺
    exits: {}
items:
  bun:
    name: 包子
    placed_in: shop
    valuable: 10
  tea:
    name: 茶叶
    placed_in: shop
    valuable: 20
npcs:
  keeper:
    name: 掌柜
    in_room: shop
    shop:
      - item: bun
        resell_discount: 0.8
      - tea
player:
  name: 你
  start_room: shop
  currency: 50
"""


class TestCurrencyAndShop:
    def test_buy_success(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SHOP_SCENE))
        lines = execute_line(world, player_id, "buy 包子")
        assert any("10" in line and "包子" in line for line in lines)
        assert world.require_component(player_id, Currency).amount == 40
        bag = world.require_component(player_id, Container)
        names = [world.require_component(i, Identity).name for i in bag.items]
        assert "包子" in names

    def test_buy_insufficient_funds(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SHOP_SCENE))
        world.require_component(player_id, Currency).amount = 5
        lines = execute_line(world, player_id, "buy 包子")
        assert any("不足" in line for line in lines)
        assert world.require_component(player_id, Currency).amount == 5

    def test_sell_owned_item(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SHOP_SCENE))
        execute_line(world, player_id, "buy 包子")
        before = world.require_component(player_id, Currency).amount
        lines = execute_line(world, player_id, "sell 包子")
        # 清单内折扣 0.8 → 8 两
        assert any("8" in line for line in lines)
        assert world.require_component(player_id, Currency).amount == before + 8

    def test_sell_missing_item(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SHOP_SCENE))
        lines = execute_line(world, player_id, "sell 包子")
        assert any("没有" in line for line in lines)

    def test_no_shop_in_room(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
  currency: 10
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "buy 包子")
        assert any("没有商店" in line for line in lines)

    def test_shop_item_without_valuable_fails_at_load(self, tmp_path: Path) -> None:
        scene = """
rooms:
  shop:
    name: 店
    exits: {}
items:
  rock:
    name: 石头
    placed_in: shop
npcs:
  keeper:
    name: 掌柜
    in_room: shop
    shop:
      - rock
player:
  name: 你
  start_room: shop
"""
        with pytest.raises(SceneLoadError, match="Valuable"):
            load_scene(_write_scene(tmp_path, scene))

    def test_currency_survives_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SHOP_SCENE))
        world.require_component(player_id, Currency).amount = 77
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        assert restored[0].require_component(restored[1], Currency).amount == 77
