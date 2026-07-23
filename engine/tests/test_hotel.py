"""Polishing-06：客店三件套（sleep / hotel / pay / 睡房拦 practice）。

接缝：S1 ``execute_line``；S2 ``load_scene``（``hotel`` 消费、不透传）。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import (
    Currency,
    HotelRoom,
    Position,
    RentPaid,
    Vitals,
)
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_BASE = """rooms:
  street:
    name: 街道
    long: 客店外的街道。
    exits:
      east: hotel
  hotel:
    name: 客栈大堂
    long: 客官里面请。
    hotel: true
    exits:
      west: street
    objects:
      waiter: 1
  quiet:
    name: 静室
    long: 不许睡觉的地方。
    no_sleep_room: true
    exits: {}
npcs:
  waiter:
    name: 店小二
    aliases:
    - 小二
    short: 店小二
    long: 系着围裙的店小二。
    inquiry:
      default: 客官要开房吗？
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
  start_room: hotel
  currency: 50
  vitals:
    qi: 40
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 20
    jingli_max: 80
  skills:
    basic_fist:
      level: 0
      exp: 20
"""


class TestHotelLoad:
    def test_hotel_consumed_as_component(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _BASE))
        assert world.room_ids is not None
        hotel = world.room_ids["hotel"]
        assert world.has_component(hotel, HotelRoom)
        extras = world.entity_extension_data(hotel)
        assert "hotel" not in extras


class TestSleep:
    def test_sleep_ok_in_ordinary_room(self, tmp_path: Path) -> None:
        scene = _BASE.replace("start_room: hotel", "start_room: street")
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        vitals = world.require_component(player_id, Vitals)
        assert vitals.jingli_current < vitals.jingli_max
        lines = execute_line(world, player_id, "sleep")
        assert any("睡" in line for line in lines)
        vitals = world.require_component(player_id, Vitals)
        assert vitals.jingli_current == vitals.jingli_max
        assert vitals.qi_current == vitals.qi_max

    def test_sleep_rejected_in_no_sleep_room(self, tmp_path: Path) -> None:
        scene = _BASE.replace("start_room: hotel", "start_room: quiet")
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        before = world.require_component(player_id, Vitals).jingli_current
        lines = execute_line(world, player_id, "sleep")
        assert any("睡" in line or "休息" in line for line in lines)
        assert world.require_component(player_id, Vitals).jingli_current == before

    def test_sleep_rejected_in_hotel_without_rent(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        before = world.require_component(player_id, Vitals).jingli_current
        lines = execute_line(world, player_id, "sleep")
        assert any("房钱" in line or "付钱" in line for line in lines)
        assert world.require_component(player_id, Vitals).jingli_current == before
        assert not world.has_component(player_id, RentPaid)


class TestPayAndSleep:
    def test_pay_then_sleep(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        currency = world.require_component(player_id, Currency)
        assert currency.amount == 50
        pay_lines = execute_line(world, player_id, "pay 小二")
        assert any("房钱" in line or "付钱" in line or "银" in line for line in pay_lines)
        assert world.has_component(player_id, RentPaid)
        assert world.require_component(player_id, Currency).amount == 40
        sleep_lines = execute_line(world, player_id, "sleep")
        assert any("睡" in line for line in sleep_lines)
        vitals = world.require_component(player_id, Vitals)
        assert vitals.jingli_current == vitals.jingli_max

    def test_pay_insufficient_funds(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        world.require_component(player_id, Currency).amount = 5
        lines = execute_line(world, player_id, "pay 店小二")
        assert any("银" in line or "钱" in line for line in lines)
        assert not world.has_component(player_id, RentPaid)
        assert world.require_component(player_id, Currency).amount == 5

    def test_pay_rejected_outside_hotel(self, tmp_path: Path) -> None:
        # 街道上放同名店小二，使解析能命中 NPC；执行层因非 HotelRoom 拒绝。
        scene = """rooms:
  street:
    name: 街道
    long: 客店外的街道。
    exits:
      east: hotel
    objects:
      waiter: 1
  hotel:
    name: 客栈大堂
    long: 客官里面请。
    hotel: true
    exits:
      west: street
npcs:
  waiter:
    name: 店小二
    aliases:
    - 小二
    short: 店小二
    long: 系着围裙的店小二。
    inquiry:
      default: 客官要开房吗？
player:
  name: 你
  start_room: street
  currency: 50
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "pay 小二")
        assert any("客店" in line or "这里" in line for line in lines)


class TestLeaveClearsRent:
    def test_leave_hotel_clears_rent_paid(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        execute_line(world, player_id, "pay 小二")
        assert world.has_component(player_id, RentPaid)
        execute_line(world, player_id, "go west")
        assert world.require_component(player_id, Position).room == world.room_ids["street"]
        assert not world.has_component(player_id, RentPaid)
        execute_line(world, player_id, "go east")
        lines = execute_line(world, player_id, "sleep")
        assert any("房钱" in line or "付钱" in line for line in lines)


class TestPracticeBlockedInHotel:
    def test_practice_rejected_in_hotel_room(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        before = world.require_component(player_id, Vitals).neili_current
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("客店" in line or "练功" in line for line in lines)
        assert world.require_component(player_id, Vitals).neili_current == before

    def test_practice_ok_outside_hotel(self, tmp_path: Path) -> None:
        scene = _BASE.replace("start_room: hotel", "start_room: street")
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("练习了" in line for line in lines)
