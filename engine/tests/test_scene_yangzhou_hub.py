"""M2-22：扬州枢纽 + 四街四门 + 同名官兵消歧验收。

Seam：``load_mvp_scene`` + ``execute_line``。
"""

from __future__ import annotations

from mud_engine.components import Description, Exits, Identity, Position
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene
from mud_engine.world import EntityId, World


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _move_to(world: World, player_id: EntityId, key: str) -> None:
    world.require_component(player_id, Position).room = _room(world, key)


class TestYangzhouHubAndGates:
    def test_nine_plus_rooms_and_yangzhou_prefix(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        keys = [k for k in world.room_ids if k.startswith("yangzhou_")]
        expected = {
            "yangzhou_guangchang",
            "yangzhou_beidajie",
            "yangzhou_nandajie",
            "yangzhou_dongdajie",
            "yangzhou_xidajie",
            "yangzhou_beimen",
            "yangzhou_nanmen",
            "yangzhou_dongmen",
            "yangzhou_ximen",
        }
        assert expected <= set(keys)
        assert len(expected) >= 9

    def test_square_is_hub_connected_to_four_streets(self) -> None:
        world, _ = load_mvp_scene()
        square = _room(world, "yangzhou_guangchang")
        exits = world.require_component(square, Exits).by_direction
        assert exits["north"].target == _room(world, "yangzhou_beidajie")
        assert exits["south"].target == _room(world, "yangzhou_nandajie")
        assert exits["east"].target == _room(world, "yangzhou_dongdajie")
        assert exits["west"].target == _room(world, "yangzhou_xidajie")

    def test_dongmen_reserves_east_to_official_road(self) -> None:
        world, _ = load_mvp_scene()
        dongmen = _room(world, "yangzhou_dongmen")
        exits = world.require_component(dongmen, Exits).by_direction
        assert "east" in exits
        assert exits["east"].target == _room(world, "road_yz_east")

    def test_look_descriptions_are_substantive(self) -> None:
        world, player_id = load_mvp_scene()
        for key, needle in (
            ("yangzhou_guangchang", "广场"),
            ("yangzhou_beidajie", "北大街"),
            ("yangzhou_dongmen", "东门"),
        ):
            _move_to(world, player_id, key)
            room = _room(world, key)
            desc = world.require_component(room, Description)
            assert desc.long and len(desc.long) > 20
            lines = execute_line(world, player_id, "look")
            assert any(needle in line or desc.long[:8] in line for line in lines)

    def test_ximen_two_guards_disambiguation(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "yangzhou_ximen")
        ambiguous = execute_line(world, player_id, "ask 官兵 about 城防")
        assert any("不确定" in line for line in ambiguous)
        a = execute_line(world, player_id, "ask 官兵 1 about 城防")
        b = execute_line(world, player_id, "ask 官兵 2 about 城防")
        assert any("城门" in line or "官兵" in line for line in a)
        assert any("城门" in line or "官兵" in line for line in b)
        # 确认确实有两名同名实例
        guards = [
            e
            for e in world.entities_with(Identity)
            if e != player_id and world.require_component(e, Identity).name == "官兵"
        ]
        assert len(guards) == 2
