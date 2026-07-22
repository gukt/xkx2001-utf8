"""Pre-M4-01：房间风景 details + look 优先级。

接缝：S1 ``execute_line``；S2 ``load_scene``（字段被消费、不透传）。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Position, RoomDetails
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_mvp_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """rooms:
  yard:
    name: 院子
    long: 青砖铺地的院子。
    outdoors: true
    details:
      石狮: 一对石狮蹲在旗杆两侧。
      旗杆: 旗杆上旗角猎猎。
    exits: {}
    objects:
      pebble: 1
      guard: 1
items:
  pebble:
    name: 石狮
    short: 一枚石子
    long: 一枚圆润的石子。
npcs:
  guard:
    name: 旗杆
    short: 守院卫兵
    long: 一名守院卫兵立在门口。
    inquiry:
      default: 哼。
player:
  name: 你
  start_room: yard
"""


class TestRoomDetailsLoad:
    def test_details_consumed_as_component(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        room = world.require_component(player_id, Position).room
        details = world.require_component(room, RoomDetails)
        assert details.entries["石狮"] == "一对石狮蹲在旗杆两侧。"
        assert details.entries["旗杆"] == "旗杆上旗角猎猎。"
        extras = world.entity_extension_data(room)
        assert "details" not in extras


class TestLookDetails:
    def test_look_detail_key_shows_text(self, tmp_path: Path) -> None:
        # 无同名实体时：换一间只有风景的房
        scene = """rooms:
  plaza:
    name: 广场
    long: 空旷广场。
    details:
      石狮: 一对石狮蹲在旗杆两侧。
    exits: {}
player:
  name: 你
  start_room: plaza
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "look 石狮")
        assert any("一对石狮蹲在旗杆两侧" in line for line in lines)

    def test_item_wins_over_same_named_detail(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "look 石狮")
        assert any("圆润的石子" in line for line in lines)
        assert not any("一对石狮蹲在旗杆两侧" in line for line in lines)

    def test_npc_wins_over_same_named_detail(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "look 旗杆")
        assert any("守院卫兵" in line for line in lines)
        assert not any("旗角猎猎" in line for line in lines)

    def test_get_detail_key_fails(self, tmp_path: Path) -> None:
        scene = """rooms:
  plaza:
    name: 广场
    long: 空旷广场。
    details:
      石狮: 一对石狮蹲在旗杆两侧。
    exits: {}
player:
  name: 你
  start_room: plaza
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "get 石狮")
        assert any("这里没有" in line for line in lines)
        look = execute_line(world, player_id, "look")
        assert not any("这里有：" in line and "石狮" in line for line in look)

    def test_unknown_look_still_fails(self, tmp_path: Path) -> None:
        scene = """rooms:
  plaza:
    name: 广场
    long: 空旷广场。
    details:
      石狮: 一对石狮蹲在旗杆两侧。
    exits: {}
player:
  name: 你
  start_room: plaza
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "look 石碑")
        assert any("这里没有" in line for line in lines)


class TestOfficialYangzhouDetails:
    def test_guangchang_look_shishi(self) -> None:
        world, player_id = load_mvp_scene()
        assert world.room_ids is not None
        world.require_component(player_id, Position).room = world.room_ids[
            "yangzhou_guangchang"
        ]
        lines = execute_line(world, player_id, "look 石狮")
        assert any("石狮" in line and "旗杆" in line for line in lines)
