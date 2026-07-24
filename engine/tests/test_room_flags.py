"""Pre-M4-03：房间旗标 + 藏书阅读房禁练。

接缝：S1 ``execute_line``；S2 ``load_scene``（旗标消费、inert 可声明）。
"""

from __future__ import annotations

from pathlib import Path

from openmud.components import Engaged, LibraryRoom, Position, RoomFlags, Vitals
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_BASE = """rooms:
  yard:
    name: 院子
    long: 练武的院子。
    exits:
      north: library
  library:
    name: 藏书阁
    long: 满是书架。
    no_fight: true
    no_steal: true
    no_sleep_room: true
    library: true
    exits:
      south: yard
    objects:
      dummy: 1
npcs:
  dummy:
    name: 木人
    vitals:
      qi_current: 100
      qi_max: 100
      neili_current: 50
      neili_max: 50
      jingli_current: 50
      jingli_max: 50
skills:
  basic_fist:
    type: martial
    level_req: 0
    practice:
      neili: 10
      jingli: 5
      exp: 15
    exp_thresholds: [30, 60]
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 40
    jingli_max: 40
  skills:
    basic_fist:
      level: 0
      exp: 20
"""


class TestRoomFlagsLoad:
    def test_flags_and_library_consumed(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        assert world.room_ids is not None
        lib = world.room_ids["library"]
        flags = world.require_component(lib, RoomFlags)
        assert flags.no_fight is True
        assert flags.no_steal is True
        assert flags.no_sleep_room is True
        assert world.has_component(lib, LibraryRoom)
        extras = world.entity_extension_data(lib)
        assert "no_fight" not in extras
        assert "library" not in extras
        # 院子无旗标组件
        yard = world.room_ids["yard"]
        assert world.get_component(yard, RoomFlags) is None
        assert world.get_component(yard, LibraryRoom) is None
        _ = player_id


class TestNoFight:
    def test_attack_rejected_in_no_fight_room(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "attack 木人")
        assert any("动手" in line or "打架" in line or "比武" in line for line in lines)
        assert world.get_component(player_id, Engaged) is None

    def test_kill_alias_also_rejected(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "kill 木人")
        assert any("动手" in line or "打架" in line or "比武" in line for line in lines)
        assert world.get_component(player_id, Engaged) is None

    def test_attack_ok_outside_no_fight(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    long: 练武的院子。
    exits: {}
    objects:
      dummy: 1
npcs:
  dummy:
    name: 木人
    vitals:
      qi_current: 100
      qi_max: 100
      neili_current: 50
      neili_max: 50
      jingli_current: 50
      jingli_max: 50
    attributes:
      str: 10
      con: 10
      dex: 0
      int: 5
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
  attributes:
    str: 20
    con: 10
    dex: 0
    int: 10
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "attack 木人")
        assert any("交战" in line for line in lines)
        assert world.get_component(player_id, Engaged) is not None


class TestNoPracticeInLibrary:
    def test_practice_rejected_in_library_room(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        execute_line(world, player_id, "go north")
        before = world.require_component(player_id, Vitals).neili_current
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("读书" in line or "练功" in line for line in lines)
        assert world.require_component(player_id, Vitals).neili_current == before
        assert world.require_component(player_id, Position).room == world.room_ids["library"]

    def test_practice_ok_outside_library(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("练习了" in line for line in lines)
