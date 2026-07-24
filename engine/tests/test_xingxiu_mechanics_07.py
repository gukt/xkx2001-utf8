"""Pre-M4-07：入室磁力吸铁（复用 ItemTags；播报级，不强制卸除）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from openmud.components import (
    Container,
    Exit,
    Exits,
    Identity,
    ItemTags,
    PlayerSession,
    Position,
    RoomHookBinding,
)
from openmud.parsing import execute_line
from openmud.room_hooks import (
    MagneticIronHook,
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


def _minimal_magnetic_world(
    *, tags: frozenset[str] | None = frozenset({"iron"})
) -> tuple[World, int, int, int | None]:
    """返回 (world, hall, player, item_id|None)。item 在玩家背包内（若 tags 非 None）。"""
    world = World()
    hall = world.create_entity()
    ante = world.create_entity()
    world.add_component(hall, Exits(by_direction={"south": Exit(target=ante)}))
    world.add_component(ante, Exits(by_direction={"north": Exit(target=hall)}))
    world.room_ids = {"magnetic_hall": hall, "ante": ante}
    player = world.create_entity()
    world.add_component(player, Position(room=hall))
    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.add_component(player, Container())
    world.primary_player_id = player
    world.add_component(
        hall,
        RoomHookBinding(
            hook_id="magnetic_iron",
            params={"tag": "iron"},
        ),
    )
    item_id: int | None = None
    if tags is not None:
        item_id = world.create_entity()
        world.add_component(item_id, Identity(name="铁剑"))
        world.add_component(item_id, ItemTags(tags=tags))
        world.require_component(player, Container).items.add(item_id)
    return world, hall, player, item_id


def _ctx(world: World, hall: int, player: int) -> RoomHookContext:
    binding = world.require_component(hall, RoomHookBinding)
    return RoomHookContext(world, hall, actor_id=player, params=binding.params)


class TestMagneticIronS0:
    def test_builtin_hook_registered(self) -> None:
        hook = get_room_hook("magnetic_iron")
        assert hook is not None
        assert isinstance(hook, MagneticIronHook)

    def test_carrying_iron_broadcasts(self) -> None:
        world, hall, player, _item = _minimal_magnetic_world(tags=frozenset({"iron"}))
        MagneticIronHook().on_enter(_ctx(world, hall, player))
        msgs = world.drain_messages(player)
        assert any("磁力" in m or "吸" in m for m in msgs)
        assert any("iron" in m for m in msgs)

    def test_no_iron_no_message(self) -> None:
        world, hall, player, _ = _minimal_magnetic_world(tags=None)
        MagneticIronHook().on_enter(_ctx(world, hall, player))
        assert world.drain_messages(player) == []

    def test_other_tag_no_message(self) -> None:
        world, hall, player, _ = _minimal_magnetic_world(tags=frozenset({"wood"}))
        MagneticIronHook().on_enter(_ctx(world, hall, player))
        assert world.drain_messages(player) == []


class TestMagneticIronCommandS1:
    def test_enter_with_iron_gets_broadcast(self, tmp_path: Path) -> None:
        scene = """rooms:
  ante:
    name: 前厅
    exits:
      north: hall
    objects:
      iron_sword: 1
  hall:
    name: 磁力玉厅
    exits:
      south: ante
    hooks:
      hook_id: magnetic_iron
      params:
        tag: iron
items:
  iron_sword:
    name: 铁剑
    tags: [iron]
player:
  name: 你
  start_room: ante
"""
        path = tmp_path / "mag.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        execute_line(world, player_id, "get 铁剑")
        execute_line(world, player_id, "go north")
        joined = " ".join(world.drain_messages(player_id))
        assert "磁力" in joined or "吸" in joined
        # 不强制卸除：铁剑仍在背包
        bag = world.require_component(player_id, Container)
        names = [world.require_component(i, Identity).name for i in bag.items]
        assert "铁剑" in names

    def test_enter_without_iron_silent(self, tmp_path: Path) -> None:
        scene = """rooms:
  ante:
    name: 前厅
    exits:
      north: hall
  hall:
    name: 磁力玉厅
    exits:
      south: ante
    hooks:
      hook_id: magnetic_iron
      params:
        tag: iron
player:
  name: 你
  start_room: ante
"""
        path = tmp_path / "mag_bare.yaml"
        path.write_text(scene, encoding="utf-8")
        world, player_id = load_scene(path)
        execute_line(world, player_id, "go north")
        joined = " ".join(world.drain_messages(player_id))
        assert "磁力" not in joined
        assert "吸" not in joined


class TestXingxiuMechanics07Slice:
    def test_slice_has_magnetic_hall_binding(self) -> None:
        world, _pid = load_xingxiu_mechanics()
        assert "magnetic_hall" in world.room_ids
        binding = world.require_component(
            world.room_ids["magnetic_hall"], RoomHookBinding
        )
        assert binding.hook_id == "magnetic_iron"
        assert binding.params.get("tag") == "iron"

    def test_slice_magnetic_path_playable(self) -> None:
        world, player_id = load_xingxiu_mechanics()
        execute_line(world, player_id, "go southwest")
        # 先进空厅无磁力
        assert world.drain_messages(player_id) == []
        execute_line(world, player_id, "go northeast")  # 回 dig_base
        execute_line(world, player_id, "get 铁剑")
        world.drain_messages(player_id)  # 清掉 get 文案
        execute_line(world, player_id, "go southwest")
        joined = " ".join(world.drain_messages(player_id))
        assert "磁力" in joined or "吸" in joined
