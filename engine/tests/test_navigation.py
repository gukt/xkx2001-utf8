"""出口导航黑盒：execute_line 覆盖内置同义词 / 地名回退 / look 展示（Polishing A1+A2）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import Identity, Position
from mud_engine.directions import DIRECTION_FORMS
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import build_world, load_mvp_scene


def _room_name(world, player_id) -> str:
    room = world.require_component(player_id, Position).room
    return world.require_component(room, Identity).name


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


_TEN_HUB_SCENE = """
rooms:
  hub:
    name: 枢纽
    exits:
      north: n_room
      south: s_room
      east: e_room
      west: w_room
      northeast: ne_room
      northwest: nw_room
      southeast: se_room
      southwest: sw_room
      up: u_room
      down: d_room
  n_room: {name: 北房, exits: {south: hub}}
  s_room: {name: 南房, exits: {north: hub}}
  e_room: {name: 东房, exits: {west: hub}}
  w_room: {name: 西房, exits: {east: hub}}
  ne_room: {name: 东北房, exits: {southwest: hub}}
  nw_room: {name: 西北房, exits: {southeast: hub}}
  se_room: {name: 东南房, exits: {northwest: hub}}
  sw_room: {name: 西南房, exits: {northeast: hub}}
  u_room: {name: 上层, exits: {down: hub}}
  d_room: {name: 下层, exits: {up: hub}}
player:
  name: 你
  start_room: hub
"""


class TestBuiltinDirectionNavigation:
    @pytest.mark.parametrize(
        "direction,short,chinese,dest",
        [
            (d, short, zh, f"{zh}房" if d not in ("up", "down") else ("上层" if d == "up" else "下层"))
            for d, (short, zh) in DIRECTION_FORMS.items()
        ],
    )
    def test_ten_direction_forms_move(
        self, tmp_path: Path, direction: str, short: str, chinese: str, dest: str
    ) -> None:
        scene = _write(tmp_path, _TEN_HUB_SCENE)
        for line in (f"go {direction}", direction, short, f"go {chinese}"):
            world, player_id = load_scene(scene)
            msgs = execute_line(world, player_id, line)
            assert _room_name(world, player_id) == dest, (line, msgs)

    def test_bare_chinese_cardinal_is_rejected_with_requires_go_wording(self) -> None:
        world, player_id = build_world()
        before = _room_name(world, player_id)
        msgs = execute_line(world, player_id, "北")
        assert _room_name(world, player_id) == before
        assert any("须写成 go" in m for m in msgs)
        assert not any("未知命令" in m for m in msgs)

    def test_bare_english_exit_nickname_is_unknown_not_requires_go(
        self, tmp_path: Path
    ) -> None:
        scene = _write(
            tmp_path,
            """
rooms:
  a:
    name: 甲
    exits:
      north:
        to: b
        aliases: [secret]
  b:
    name: 乙
player:
  name: 你
  start_room: a
""",
        )
        world, player_id = load_scene(scene)
        msgs = execute_line(world, player_id, "secret")
        assert _room_name(world, player_id) == "甲"
        assert any("未知命令" in m for m in msgs)
        assert not any("须写成 go" in m for m in msgs)
        msgs = execute_line(world, player_id, "go secret")
        assert _room_name(world, player_id) == "乙", msgs

    def test_unknown_verb_still_says_unknown(self) -> None:
        world, player_id = build_world()
        msgs = execute_line(world, player_id, "fly")
        assert any("未知命令" in m for m in msgs)


class TestTargetRoomNameFallback:
    def test_go_place_name_hits_target_room(self, tmp_path: Path) -> None:
        scene = _write(
            tmp_path,
            """
rooms:
  square:
    name: 广场
    exits:
      northeast: temple
  temple:
    name: 武庙
    aliases: [武圣庙]
    exits:
      southwest: square
player:
  name: 你
  start_room: square
""",
        )
        world, player_id = load_scene(scene)
        msgs = execute_line(world, player_id, "go 武庙")
        assert _room_name(world, player_id) == "武庙", msgs

        world, player_id = load_scene(scene)
        msgs = execute_line(world, player_id, "go 武圣庙")
        assert _room_name(world, player_id) == "武庙", msgs

        world, player_id = load_scene(scene)
        execute_line(world, player_id, "go 武庙")
        msgs = execute_line(world, player_id, "go 广场")
        assert _room_name(world, player_id) == "广场", msgs

    def test_bare_place_name_requires_go(self, tmp_path: Path) -> None:
        scene = _write(
            tmp_path,
            """
rooms:
  square:
    name: 广场
    exits:
      northeast: temple
  temple:
    name: 武庙
player:
  name: 你
  start_room: square
""",
        )
        world, player_id = load_scene(scene)
        msgs = execute_line(world, player_id, "武庙")
        assert _room_name(world, player_id) == "广场"
        assert any("须写成 go" in m for m in msgs)

    def test_ambiguous_shared_place_name(self, tmp_path: Path) -> None:
        scene = _write(
            tmp_path,
            """
rooms:
  hub:
    name: 路口
    exits:
      north: a
      east: b
  a:
    name: 侧室
    aliases: [门]
  b:
    name: 厢房
    aliases: [门]
player:
  name: 你
  start_room: hub
""",
        )
        world, player_id = load_scene(scene)
        msgs = execute_line(world, player_id, "go 门")
        assert _room_name(world, player_id) == "路口"
        assert any("不确定" in m for m in msgs)


class TestLookExitDisplay:
    def test_look_lists_chinese_english_and_door_suffix(self) -> None:
        world, player_id = build_world()
        combined = "\n".join(execute_line(world, player_id, "look"))
        assert "北(north)" in combined
        assert "南(south)（关）" in combined

    def test_mvp_go_wumiao_via_room_or_exit_alias(self) -> None:
        # 官方范本在票 02 清理前：武庙仍可能挂在出口 aliases；清理后靠目标房 name。
        world, player_id = load_mvp_scene()
        # 出生在华山村口；先走到扬州广场再测。
        execute_line(world, player_id, "go south")  # 官道
        execute_line(world, player_id, "go south")  # 南门
        execute_line(world, player_id, "go north")  # 南大街
        execute_line(world, player_id, "go north")  # 广场
        assert _room_name(world, player_id) == "中央广场"
        msgs = execute_line(world, player_id, "go 武庙")
        assert _room_name(world, player_id) == "武庙", msgs
