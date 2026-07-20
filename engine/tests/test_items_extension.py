"""块 C 物品系统扩展测试（18–24 号票）。

覆盖能力组件、transfer 原语、堆叠、no_take/no_drop、嵌套容器 put/take from、
look 物品增强、重量/容量上限。测试 seam：``execute_line`` + 直接调 ``transfer``。
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mud_engine.components import (
    Consumable,
    Container,
    Description,
    Equippable,
    Identity,
    ItemFlags,
    Position,
    Stackable,
    Valuable,
)
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import build_world
from mud_engine.transfer import TransferFailReason, TransferResult, item_weight, transfer
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_BASE = """
rooms:
  yard:
    name: 院子
    long: 院子
player:
  name: 你
  start_room: yard
"""


def _load(tmp_path: Path, items_yaml: str) -> tuple[World, EntityId]:
    scene = _BASE + "\nitems:\n" + items_yaml
    return load_scene(_write_scene(tmp_path, scene))


def _item_by_name(world: World, holder: EntityId, name: str) -> EntityId:
    container = world.require_component(holder, Container)
    for item in container.items:
        if world.require_component(item, Identity).name == name:
            return item
    raise AssertionError(f"在 {holder} 找不到 {name}")


def _player_room(world: World, player_id: EntityId) -> EntityId:
    return world.require_component(player_id, Position).room


class TestCapabilityComponents:
    """18 号票：按需挂载能力组件。"""

    def test_yaml_attaches_stackable_valuable_equippable_consumable(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  coin:
    name: 铜钱
    placed_in: yard
    stackable: {amount: 5, unit_weight: 0.1}
    value: 1
    equippable: {slot: hand}
    consumable: {uses: 2}
""",
        )
        room = _player_room(world, player_id)
        coin = _item_by_name(world, room, "铜钱")
        assert world.require_component(coin, Stackable).amount == 5
        assert world.require_component(coin, Stackable).unit_weight == pytest.approx(0.1)
        assert world.require_component(coin, Valuable).value == 1
        assert world.require_component(coin, Equippable).slot == "hand"
        assert world.require_component(coin, Consumable).uses == 2

    def test_plain_item_has_no_capability_components(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        stone = _item_by_name(world, room, "石头")
        assert world.get_component(stone, Stackable) is None
        assert world.get_component(stone, Valuable) is None
        assert world.get_component(stone, Equippable) is None
        assert world.get_component(stone, Consumable) is None
        assert world.get_component(stone, ItemFlags) is None


class TestTransferPrimitive:
    """19 号票：transfer 原语 + take/drop 收敛。"""

    def test_transfer_result_shape_is_frozen(self) -> None:
        ok = TransferResult(success=True)
        assert ok.reason is None and ok.message is None
        with pytest.raises(FrozenInstanceError):
            ok.success = False  # type: ignore[misc]

    def test_take_and_drop_still_work_via_transfer(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "take 石头")
        assert any("拿" in m and "石头" in m for m in messages)
        inv = world.require_component(player_id, Container)
        assert any(world.require_component(i, Identity).name == "石头" for i in inv.items)
        messages = execute_line(world, player_id, "drop 石头")
        assert any("放下" in m and "石头" in m for m in messages)

    def test_on_take_deny_still_blocks(self) -> None:
        from mud_engine.commands import ON_TAKE, Deny

        world, player_id = build_world()
        world.events.register(ON_TAKE, lambda ctx: Deny(message="诅咒挡住了你。"))
        messages = execute_line(world, player_id, "take 石头")
        assert any("诅咒" in m for m in messages)
        room = _player_room(world, player_id)
        assert any(
            world.require_component(i, Identity).name == "石头"
            for i in world.require_component(room, Container).items
        )


class TestStacking:
    """20 号票：堆叠合并与拆分。"""

    def test_take_merges_same_name_stackables(self, tmp_path: Path) -> None:
        # 地面同时放两堆同名会歧义；先拿一堆，再往地面补一堆后第二次 take 合并。
        world, player_id = _load(
            tmp_path,
            """
  a:
    name: 铜钱
    placed_in: yard
    stackable: {amount: 3, unit_weight: 0.1}
""",
        )
        execute_line(world, player_id, "take 铜钱")
        room = _player_room(world, player_id)
        extra = world.create_entity()
        world.add_component(extra, Identity(name="铜钱"))
        world.add_component(extra, Description(short="铜钱", long=""))
        world.add_component(extra, Stackable(amount=2, unit_weight=0.1))
        world.require_component(room, Container).items.add(extra)
        execute_line(world, player_id, "take 铜钱")
        inv = world.require_component(player_id, Container)
        coins = [
            i
            for i in inv.items
            if world.require_component(i, Identity).name == "铜钱"
        ]
        assert len(coins) == 1
        assert world.require_component(coins[0], Stackable).amount == 5

    def test_take_with_quantity_splits_stack(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  pile:
    name: 铜钱
    placed_in: yard
    stackable: {amount: 10, unit_weight: 0.1}
""",
        )
        messages = execute_line(world, player_id, "take 铜钱 3")
        assert any("3" in m and "铜钱" in m for m in messages)
        room = _player_room(world, player_id)
        floor_coin = _item_by_name(world, room, "铜钱")
        assert world.require_component(floor_coin, Stackable).amount == 7
        inv_coin = _item_by_name(world, player_id, "铜钱")
        assert world.require_component(inv_coin, Stackable).amount == 3

    def test_invalid_quantity_is_rejected(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  pile:
    name: 铜钱
    placed_in: yard
    stackable: {amount: 2}
""",
        )
        messages = execute_line(world, player_id, "take 铜钱 5")
        assert any("没有那么多" in m or "数量" in m for m in messages)
        room = _player_room(world, player_id)
        assert world.require_component(_item_by_name(world, room, "铜钱"), Stackable).amount == 2


class TestNoTakeNoDrop:
    """21 号票：标志位。"""

    def test_no_take_rejects_take(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  statue:
    name: 石碑
    placed_in: yard
    no_take: true
""",
        )
        messages = execute_line(world, player_id, "take 石碑")
        assert any("拿不起来" in m for m in messages)
        room = _player_room(world, player_id)
        assert any(
            world.require_component(i, Identity).name == "石碑"
            for i in world.require_component(room, Container).items
        )

    def test_no_drop_custom_message(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  token:
    name: 令牌
    placed_in: yard
    no_drop: true
    no_drop_message: 这是任务物品，不能丢弃
""",
        )
        execute_line(world, player_id, "take 令牌")
        messages = execute_line(world, player_id, "drop 令牌")
        assert any("这是任务物品，不能丢弃" in m for m in messages)
        assert any(
            world.require_component(i, Identity).name == "令牌"
            for i in world.require_component(player_id, Container).items
        )


class TestNestedContainers:
    """22 号票：put / take from。"""

    def test_put_and_take_from_box(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  box:
    name: 木箱
    aliases: [箱子]
    placed_in: yard
    container: true
  gem:
    name: 宝石
    placed_in: yard
""",
        )
        execute_line(world, player_id, "take 宝石")
        messages = execute_line(world, player_id, "put 宝石 in 木箱")
        assert any("放进" in m and "木箱" in m for m in messages)
        box = _item_by_name(world, _player_room(world, player_id), "木箱")
        assert any(
            world.require_component(i, Identity).name == "宝石"
            for i in world.require_component(box, Container).items
        )
        messages = execute_line(world, player_id, "take 宝石 from 木箱")
        assert any("拿" in m and "宝石" in m for m in messages)
        assert any(
            world.require_component(i, Identity).name == "宝石"
            for i in world.require_component(player_id, Container).items
        )


class TestLookItem:
    """23 号票：look 物品增强。"""

    def test_look_item_shows_long_and_stats(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  coin:
    name: 铜钱
    long: 圆圆的铜钱。
    placed_in: yard
    stackable: {amount: 4, unit_weight: 0.5}
    value: 2
""",
        )
        messages = execute_line(world, player_id, "look 铜钱")
        combined = "\n".join(messages)
        assert "圆圆的铜钱" in combined
        assert "数量：4" in combined
        assert "价值：2" in combined
        assert "重量：" in combined

    def test_look_container_lists_contents(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  box:
    name: 木箱
    long: 一只旧木箱。
    placed_in: yard
    container: true
  gem:
    name: 宝石
    placed_in: yard
""",
        )
        execute_line(world, player_id, "take 宝石")
        execute_line(world, player_id, "put 宝石 in 木箱")
        messages = execute_line(world, player_id, "look 木箱")
        combined = "\n".join(messages)
        assert "旧木箱" in combined
        assert "宝石" in combined

    def test_room_look_without_target_unchanged(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "look")
        assert "起始庭院" in messages[0]
        assert any("出口" in m for m in messages)


class TestWeightCapacity:
    """24 号票：重量与容量上限。"""

    def test_over_capacity_put_fails(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  box:
    name: 小盒
    placed_in: yard
    container: {max_capacity: 1}
  a:
    name: 甲
    placed_in: yard
  b:
    name: 乙
    placed_in: yard
""",
        )
        execute_line(world, player_id, "take 甲")
        execute_line(world, player_id, "take 乙")
        assert any("放进" in m for m in execute_line(world, player_id, "put 甲 in 小盒"))
        messages = execute_line(world, player_id, "put 乙 in 小盒")
        assert any("装不下" in m for m in messages)

    def test_over_weight_put_fails(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  box:
    name: 布袋
    placed_in: yard
    container: {max_weight: 1.0}
  rock:
    name: 大石
    placed_in: yard
    weight: 5
""",
        )
        execute_line(world, player_id, "take 大石")
        messages = execute_line(world, player_id, "put 大石 in 布袋")
        assert any("太重" in m for m in messages)

    def test_transfer_reports_over_weight_reason(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  box:
    name: 布袋
    placed_in: yard
    container: {max_weight: 1.0}
  rock:
    name: 大石
    placed_in: yard
    weight: 5
""",
        )
        room = _player_room(world, player_id)
        rock = _item_by_name(world, room, "大石")
        box = _item_by_name(world, room, "布袋")
        # 先放到玩家栏再 transfer 进袋
        assert transfer(world, rock, room, player_id, player_id=player_id).success
        result = transfer(world, rock, player_id, box, player_id=player_id)
        assert not result.success
        assert result.reason == TransferFailReason.OVER_WEIGHT

    def test_item_weight_from_stackable(self, tmp_path: Path) -> None:
        world, player_id = _load(
            tmp_path,
            """
  pile:
    name: 铜钱
    placed_in: yard
    stackable: {amount: 4, unit_weight: 0.25}
""",
        )
        room = _player_room(world, player_id)
        coin = _item_by_name(world, room, "铜钱")
        assert item_weight(world, coin) == pytest.approx(1.0)
