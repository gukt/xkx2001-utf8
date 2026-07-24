"""Polishing-13 / ADR-0013：房间级 LocalNature 贴纸。

接缝：S2 ``load_scene``（``local_nature`` → 组件）；S1 户外 ``look`` 文案；
条件 DSL ``is_raining`` / ``is_night`` / ``phase`` 按演员所在房合成读数。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openmud.components import LocalNature, Position
from openmud.conditions import Equals, Predicate, evaluate
from openmud.entity_gate import EntityGateContext
from openmud.errors import SceneLoadError
from openmud.nature import Weather, attach_nature, resolve_effective_nature
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene
from openmud.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """rooms:
  plain:
    name: 平原
    short: 平原
    long: 开阔的平原。
    outdoors: true
    exits:
      north: peak
  peak:
    name: 山顶
    short: 山顶
    long: 终年云雾缭绕。
    outdoors: true
    local_nature:
      weather: rain
      phase: night
    exits:
      south: plain
player:
  name: 你
  start_room: plain
"""


def _load(tmp_path: Path, *, weather: Weather = Weather.CLEAR, phase: str = "day"):
    world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
    nature = attach_nature(world, weather=weather)
    nature.seek_phase(phase)
    return world, player_id


class TestLocalNatureLoad:
    def test_local_nature_consumed_as_component(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _SCENE))
        assert world.room_ids is not None
        peak = world.room_ids["peak"]
        plain = world.room_ids["plain"]
        local = world.require_component(peak, LocalNature)
        assert local.weather == "rain"
        assert local.phase == "night"
        assert not world.has_component(plain, LocalNature)
        extras = world.entity_extension_data(peak)
        assert "local_nature" not in extras

    def test_partial_override_weather_only(self, tmp_path: Path) -> None:
        scene = _SCENE.replace(
            "local_nature:\n      weather: rain\n      phase: night",
            "local_nature:\n      weather: rain",
        )
        world, _ = load_scene(_write_scene(tmp_path, scene))
        local = world.require_component(world.room_ids["peak"], LocalNature)
        assert local.weather == "rain"
        assert local.phase is None

    def test_reject_unknown_weather(self, tmp_path: Path) -> None:
        scene = _SCENE.replace("weather: rain", "weather: fog")
        with pytest.raises(SceneLoadError, match="local_nature.weather"):
            load_scene(_write_scene(tmp_path, scene))

    def test_reject_unknown_phase(self, tmp_path: Path) -> None:
        scene = _SCENE.replace("phase: night", "phase: tea_time")
        with pytest.raises(SceneLoadError, match="local_nature.phase"):
            load_scene(_write_scene(tmp_path, scene))


class TestEffectiveNature:
    def test_plain_falls_back_to_world(self, tmp_path: Path) -> None:
        world, player_id = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        plain = world.require_component(player_id, Position).room
        eff = resolve_effective_nature(world, plain)
        assert eff is not None
        assert eff.phase == "day"
        assert eff.is_raining is False
        assert eff.is_day is True

    def test_peak_uses_sticker(self, tmp_path: Path) -> None:
        world, _ = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        peak = world.room_ids["peak"]
        eff = resolve_effective_nature(world, peak)
        assert eff is not None
        assert eff.phase == "night"
        assert eff.is_raining is True
        assert eff.is_night is True
        assert eff.is_day is False

    def test_partial_weather_keeps_world_phase(self, tmp_path: Path) -> None:
        scene = _SCENE.replace(
            "local_nature:\n      weather: rain\n      phase: night",
            "local_nature:\n      weather: rain",
        )
        world, _ = load_scene(_write_scene(tmp_path, scene))
        attach_nature(world, weather=Weather.CLEAR).seek_phase("day")
        eff = resolve_effective_nature(world, world.room_ids["peak"])
        assert eff is not None
        assert eff.phase == "day"
        assert eff.is_raining is True
        assert eff.is_day is True


class TestOutdoorLookLocalNature:
    def test_peak_look_uses_sticker_rain_night(self, tmp_path: Path) -> None:
        world, player_id = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        execute_line(world, player_id, "go north")
        look = execute_line(world, player_id, "look")
        # World 相位表 night × rain 文案（DEFAULT_PHASES），非 World 当前 day×clear
        assert any("夜雨潇潇" in line for line in look)
        assert not any("日正当空" in line for line in look)

    def test_plain_look_unaffected_by_neighbor_sticker(self, tmp_path: Path) -> None:
        world, player_id = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        look = execute_line(world, player_id, "look")
        assert any("日正当空" in line for line in look)
        assert not any("夜雨潇潇" in line for line in look)


class TestConditionPredicatesLocalNature:
    def test_gate_context_uses_actor_room_sticker(self, tmp_path: Path) -> None:
        world, player_id = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        execute_line(world, player_id, "go north")
        gate = EntityGateContext(world, player_id)
        assert gate.is_raining is True
        assert gate.is_night is True
        assert gate.phase == "night"
        assert evaluate(Predicate("is_raining"), gate) is True
        assert evaluate(Predicate("is_night"), gate) is True
        assert evaluate(Equals("phase", "night"), gate) is True

    def test_gate_context_plain_matches_world(self, tmp_path: Path) -> None:
        world, player_id = _load(tmp_path, weather=Weather.CLEAR, phase="day")
        gate = EntityGateContext(world, player_id)
        assert gate.is_raining is False
        assert gate.is_night is False
        assert gate.phase == "day"
        assert evaluate(Predicate("is_day"), gate) is True

    def test_entry_guard_uses_destination_room_sticker(self, tmp_path: Path) -> None:
        """World 白天时，目标房贴纸 is_night 仍拒入 day_shop 式门禁。"""
        scene = """rooms:
  plain:
    name: 平原
    outdoors: true
    exits:
      north: shrine
  shrine:
    name: 夜祠
    outdoors: true
    local_nature:
      phase: night
    entry_guard:
      condition:
        predicate: is_day
      deny_message: 夜祠白日不开。
    exits:
      south: plain
player:
  name: 你
  start_room: plain
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        attach_nature(world, weather=Weather.CLEAR).seek_phase("day")
        lines = execute_line(world, player_id, "go north")
        assert any("夜祠白日不开" in line for line in lines)
        look = execute_line(world, player_id, "look")
        assert any("平原" in line for line in look)


class TestAiWhenLocalNature:
    def test_chatter_when_uses_npc_room_sticker(self, tmp_path: Path) -> None:
        """World 白天时，贴纸夜房里的 is_night chatter 仍应说话。"""
        scene = """rooms:
  plain:
    name: 平原
    outdoors: true
    exits:
      north: peak
  peak:
    name: 山顶
    outdoors: true
    local_nature:
      phase: night
    exits:
      south: plain
    objects:
      owl: 1
npcs:
  owl:
    name: 夜枭
    short: 夜枭
    long: 一只夜枭。
    behaviors:
      - kind: chatter
        chat_msgs:
          - 夜深了。
        chat_chance: 1.0
        when:
          predicate: is_night
player:
  name: 你
  start_room: peak
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        attach_nature(world, weather=Weather.CLEAR).seek_phase("day")
        assert world.ai is not None
        world.ai.rng = _AlwaysSpeakRng()
        # 玩家须在同房才能从 pending 收到 room_say；已 start_room: peak。
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        world.pending_messages.clear()
        loop.advance()
        assert any("夜枭说：夜深了。" in m for m in world.pending_messages)


class _AlwaysSpeakRng:
    """chat_chance / choice 恒命中。"""

    def random(self) -> float:
        return 0.0

    def choice(self, seq):  # noqa: ANN001
        return seq[0]
