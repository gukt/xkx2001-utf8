"""Polishing-03 / Pre-M4-01：房间风景 details（K2+U+S1+N1）+ look 优先级。

接缝：S1 ``execute_line``；S2 ``load_scene``（字段被消费、不透传）；
单元：``normalize_detail_token`` / ``resolve_detail`` / ``scan_detail_mentions``。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import DetailEntry, Position, RoomDetails
from mud_engine.parsing import execute_line
from mud_engine.room_details import (
    normalize_detail_token,
    resolve_detail,
    scan_detail_mentions,
)
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

_K2_SCENE = """rooms:
  plaza:
    name: 广场
    long: 广场上立着石狮(shi shi)与石碑(bei)。
    details:
      shi_shi:
        text: 一对石狮蹲在旗杆两侧，爪下按着石球(shi_qiu)。
        aliases: [石狮, "shi shi", ss]
      shi_qiu:
        text: 石球圆润光滑。
        aliases: [石球]
    exits: {}
player:
  name: 你
  start_room: plaza
"""


class TestNormalizeDetailToken:
    def test_n1_separator_variants_share_skeleton(self) -> None:
        assert normalize_detail_token("shi shi") == "shishi"
        assert normalize_detail_token("shi_shi") == "shishi"
        assert normalize_detail_token("shi-shi") == "shishi"
        assert normalize_detail_token("shishi") == "shishi"

    def test_case_insensitive(self) -> None:
        assert normalize_detail_token("Shi_Shi") == "shishi"

    def test_chinese_passthrough(self) -> None:
        assert normalize_detail_token("石狮") == "石狮"


class TestRoomDetailsLoad:
    def test_legacy_string_consumed_as_detail_entry(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        room = world.require_component(player_id, Position).room
        details = world.require_component(room, RoomDetails)
        assert details.entries["石狮"] == DetailEntry(
            text="一对石狮蹲在旗杆两侧。",
            aliases=("石狮",),
        )
        assert details.entries["旗杆"] == DetailEntry(
            text="旗杆上旗角猎猎。",
            aliases=("旗杆",),
        )
        extras = world.entity_extension_data(room)
        assert "details" not in extras

    def test_k2_shape_consumed_not_in_extras(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _K2_SCENE))
        room = world.require_component(player_id, Position).room
        details = world.require_component(room, RoomDetails)
        assert details.entries["shi_shi"] == DetailEntry(
            text="一对石狮蹲在旗杆两侧，爪下按着石球(shi_qiu)。",
            aliases=("石狮", "shi shi", "ss"),
        )
        assert details.entries["shi_qiu"].text == "石球圆润光滑。"
        extras = world.entity_extension_data(room)
        assert "details" not in extras


class TestLookDetails:
    def test_look_detail_key_shows_text(self, tmp_path: Path) -> None:
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

    def test_n1_alias_matrix_hits_same_entry(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _K2_SCENE))
        expected = "一对石狮蹲在旗杆两侧"
        for token in ("石狮", "shi shi", "ss", "shi_shi", "shi-shi", "shishi"):
            lines = execute_line(world, player_id, f"look {token}")
            assert any(expected in line for line in lines), token

    def test_look_id_case_insensitive(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _K2_SCENE))
        lines = execute_line(world, player_id, "look Shi_Shi")
        assert any("一对石狮蹲在旗杆两侧" in line for line in lines)

    def test_nested_look_via_flat_registration(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _K2_SCENE))
        lines = execute_line(world, player_id, "look 石球")
        assert any("石球圆润光滑" in line for line in lines)
        lines = execute_line(world, player_id, "look shi_qiu")
        assert any("石球圆润光滑" in line for line in lines)

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


class TestScanDetailMentions:
    def test_registered_mention_is_lookable(self) -> None:
        details = RoomDetails(
            entries={
                "shi_shi": DetailEntry(
                    text="石狮文案",
                    aliases=("石狮", "shi shi", "ss"),
                ),
            }
        )
        hits = scan_detail_mentions("广场上立着石狮(shi shi)。", details)
        assert len(hits) == 1
        assert hits[0].display == "石狮"
        assert hits[0].raw_id == "shi shi"
        assert hits[0].lookable is True
        assert hits[0].detail_key == "shi_shi"

    def test_unregistered_mention_is_plain_text(self) -> None:
        details = RoomDetails(
            entries={
                "shi_shi": DetailEntry(text="石狮文案", aliases=("石狮",)),
            }
        )
        hits = scan_detail_mentions("墙上写着年号(nian hao)。", details)
        assert len(hits) == 1
        assert hits[0].display == "年号"
        assert hits[0].raw_id == "nian hao"
        assert hits[0].lookable is False
        assert hits[0].detail_key is None

    def test_nested_text_scan_uses_same_s1(self) -> None:
        details = RoomDetails(
            entries={
                "shi_shi": DetailEntry(
                    text="爪下按着石球(shi_qiu)。",
                    aliases=("石狮",),
                ),
                "shi_qiu": DetailEntry(text="石球圆润。", aliases=("石球",)),
            }
        )
        hits = scan_detail_mentions(details.entries["shi_shi"].text, details)
        assert len(hits) == 1
        assert hits[0].lookable is True
        assert hits[0].detail_key == "shi_qiu"

    def test_resolve_uses_n1(self) -> None:
        details = RoomDetails(
            entries={
                "shi_shi": DetailEntry(
                    text="一对石狮。",
                    aliases=("石狮", "shi shi", "ss"),
                ),
            }
        )
        for token in ("石狮", "shi shi", "ss", "shi_shi", "shi-shi", "shishi", "SS"):
            entry = resolve_detail(details, token)
            assert entry is not None
            assert entry.text == "一对石狮。"


class TestOfficialYangzhouDetails:
    def test_guangchang_look_shishi(self) -> None:
        world, player_id = load_mvp_scene()
        assert world.room_ids is not None
        world.require_component(player_id, Position).room = world.room_ids[
            "yangzhou_guangchang"
        ]
        lines = execute_line(world, player_id, "look 石狮")
        assert any("石狮" in line and "旗杆" in line for line in lines)

    def test_guangchang_look_qigan_keeps_semantic_color(self) -> None:
        """S3：户外广场 details 带语义色（旗杆）。"""
        world, player_id = load_mvp_scene()
        assert world.room_ids is not None
        world.require_component(player_id, Position).room = world.room_ids[
            "yangzhou_guangchang"
        ]
        lines = execute_line(world, player_id, "look 旗杆")
        assert any("<c:yellow>旗角</c>" in line for line in lines)
        assert not any("\x1b[" in line for line in lines)
