"""Nature 系统测试（M1 扩展块 B，13~17 号票）。

覆盖：时辰循环推进 / 时钟对齐 / 条件谓词 / 户外 look 文案 / 相位广播 /
天气晴雨切换。测试 seam 沿用 ``execute_line`` + ``tick_loop.advance`` +
条件求值器纯函数直测；时钟与 RNG 可注入，不依赖墙钟。
"""

from __future__ import annotations

import random
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mud_engine.components import Container, Description, Exits, Identity, Position
from mud_engine.conditions import (
    ConditionContext,
    Equals,
    Predicate,
    StubContext,
    evaluate,
)
from mud_engine.nature import (
    DEFAULT_PHASES,
    ON_NATURE_CHANGE,
    DayPhase,
    NatureChangeContext,
    NatureState,
    Weather,
    attach_nature,
)
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene, read_nature_config
from mud_engine.scenes import build_world
from mud_engine.tick import TickLoop
from mud_engine.world import World

# 短相位：每相 2 游戏分钟，便于 advance() 快进。
_SHORT_PHASES = (
    DayPhase("dawn", 2, "微曦初现。", "黎明将至。", "黎明细雨。"),
    DayPhase("day", 2, "天光大亮。", "日正当空。", "白天小雨。"),
    DayPhase("dusk", 2, "暮色四合。", "夕阳西下。", "黄昏落雨。"),
    DayPhase("night", 2, "夜幕降临。", "夜深寂静。", "夜雨潇潇。"),
)


def _tick_loop(world: World) -> TickLoop:
    return TickLoop(lambda: None, interval=10_000, world=world)


def _attach(
    world: World,
    *,
    clock_minutes: int = 0,
    phases: tuple[DayPhase, ...] = _SHORT_PHASES,
    weather: Weather = Weather.CLEAR,
    weather_change_chance: float = 0.0,
    rng: random.Random | None = None,
    game_minutes_per_tick: int = 1,
) -> NatureState:
    """挂 Nature：clock 按「游戏分钟」对齐（clock 返回 minute 当秒用）。"""
    return attach_nature(
        world,
        phases=phases,
        clock=lambda: float(clock_minutes),
        rng=rng if rng is not None else random.Random(0),
        weather=weather,
        weather_change_chance=weather_change_chance,
        game_minutes_per_tick=game_minutes_per_tick,
    )


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestDayPhaseLoop:
    """13 号票：时辰循环引擎。"""

    def test_build_world_attaches_nature_state(self) -> None:
        world, _ = build_world()
        assert world.nature is not None
        assert isinstance(world.nature, NatureState)

    def test_nature_is_not_serialized_as_component(self) -> None:
        # Nature 是 world 级态，不在 entities/components 里，故不进存档。
        world, _ = build_world()
        assert world.nature is not None
        for entity in world.all_entities():
            for ctype, _ in world.components_of(entity):
                assert ctype is not NatureState

    def test_default_phases_are_dawn_day_dusk_night(self) -> None:
        assert [p.name for p in DEFAULT_PHASES] == ["dawn", "day", "dusk", "night"]
        assert sum(p.length for p in DEFAULT_PHASES) == 1440

    def test_advance_switches_phase_after_length_minutes(self) -> None:
        world, _ = build_world()
        nature = _attach(world, clock_minutes=0)
        loop = _tick_loop(world)
        assert nature.phase == "dawn"
        loop.advance()  # elapsed 1
        assert nature.phase == "dawn"
        loop.advance()  # elapsed 2 -> wrap to day
        assert nature.phase == "day"

    def test_clock_alignment_is_injectable(self) -> None:
        world, _ = build_world()
        # 短相位各 2 分钟：minute=3 落在 day（dawn 0-1, day 2-3）
        nature = _attach(world, clock_minutes=3)
        assert nature.phase == "day"
        assert nature.elapsed == 1

    def test_custom_phase_sequence_from_yaml(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    outdoors: true
    long: 院子
player:
  name: 你
  start_room: yard
nature:
  day_phases:
    - name: morning
      length: 10
      time_msg: 早了。
      desc_msg: 清晨。
    - name: evening
      length: 10
      time_msg: 晚了。
      desc_msg: 傍晚。
"""
        world, _ = load_scene(_write_scene(tmp_path, scene))
        assert world.nature is not None
        assert [p.name for p in world.nature.phases] == ["morning", "evening"]
        # 透传仍保留
        assert "nature" in world.extension_data

    def test_restore_reattach_keeps_custom_phases_from_scene_file(self, tmp_path: Path) -> None:
        """崩溃恢复后 extension_data 为空，须从场景文件重读 nature 配置。"""
        scene = """
rooms:
  yard:
    name: 院子
    outdoors: true
    long: 院子
player:
  name: 你
  start_room: yard
nature:
  day_phases:
    - name: morning
      length: 10
      time_msg: 早了。
      desc_msg: 清晨。
    - name: evening
      length: 10
      time_msg: 晚了。
      desc_msg: 傍晚。
"""
        scene_path = _write_scene(tmp_path, scene)
        world, player_id = load_scene(scene_path)
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored = restore_world(save_dir)
        assert restored is not None
        world2, _ = restored
        assert world2.scene_path == scene_path.resolve()
        # 模拟 __main__ restore 路径：从场景文件重挂，而非裸 attach_nature。
        attach_nature(
            world2,
            config_from_yaml=read_nature_config(world2.scene_path),
            clock=lambda: 0.0,
        )
        assert world2.nature is not None
        assert [p.name for p in world2.nature.phases] == ["morning", "evening"]


class TestQueryPredicates:
    """14 号票：结构化查询谓词 + ConditionContext。

    高阶谓词语义（对齐 research「夜里」条件，含 dawn / midnight）：
    - ``is_night``：phase ∈ {night, midnight, dawn}
    - ``is_day``：phase ∈ {day, dusk}
    """

    def test_nature_implements_condition_context_protocol(self) -> None:
        nature = NatureState(_SHORT_PHASES)
        assert isinstance(nature, ConditionContext)

    def test_stub_context_still_works_for_unit_tests(self) -> None:
        # 14 验收：现有 StubContext 测试不破。
        stub = StubContext(phase="night", is_night=True, is_day=False, is_raining=False)
        assert evaluate(Predicate("is_night"), stub) is True

    class WhenDawn:
        def test_dawn_is_night_not_day(self) -> None:
            nature = NatureState(_SHORT_PHASES, phase_index=0)  # dawn
            assert nature.phase == "dawn"
            assert nature.is_night is True
            assert nature.is_day is False

        def test_evaluate_phase_equals(self) -> None:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=0)
            assert evaluate(Equals("phase", "dawn"), nature) is True

        def test_evaluate_is_night(self) -> None:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=0)
            assert evaluate(Predicate("is_night"), nature) is True

    class WhenDay:
        def test_day_is_day_not_night(self) -> None:
            nature = NatureState(_SHORT_PHASES, phase_index=1)  # day
            assert nature.is_day is True
            assert nature.is_night is False

    class WhenDusk:
        def test_dusk_is_day_not_night(self) -> None:
            nature = NatureState(_SHORT_PHASES, phase_index=2)  # dusk
            assert nature.phase == "dusk"
            assert nature.is_day is True
            assert nature.is_night is False

    class WhenNight:
        def test_night_is_night_not_day(self) -> None:
            nature = NatureState(_SHORT_PHASES, phase_index=3)  # night
            assert nature.is_night is True
            assert nature.is_day is False

    class WhenMidnight:
        def test_midnight_counts_as_night(self) -> None:
            # 题材包可自定义 midnight；research 夜条件含 midnight。
            phases = (
                DayPhase("day", 2, "", ""),
                DayPhase("midnight", 2, "", ""),
            )
            nature = NatureState(phases, phase_index=1)
            assert nature.phase == "midnight"
            assert nature.is_night is True
            assert nature.is_day is False

    class WhenAdvancedFromDawnToDay:
        def _nature_after_advance(self) -> NatureState:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=0)
            loop = _tick_loop(world)
            loop.advance()
            loop.advance()  # dawn(2) → day
            return nature

        def test_phase_is_day(self) -> None:
            assert self._nature_after_advance().phase == "day"

        def test_is_day_true(self) -> None:
            assert self._nature_after_advance().is_day is True

        def test_evaluate_is_day(self) -> None:
            assert evaluate(Predicate("is_day"), self._nature_after_advance()) is True

    class WhenAdvancedToNight:
        def _nature_after_advance(self) -> NatureState:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=0)
            loop = _tick_loop(world)
            # dawn(2) → day；再 day(2)+dusk(2)=4 ticks → night
            for _ in range(6):
                loop.advance()
            return nature

        def test_phase_is_night(self) -> None:
            assert self._nature_after_advance().phase == "night"

        def test_is_night_true(self) -> None:
            assert self._nature_after_advance().is_night is True

        def test_evaluate_is_night(self) -> None:
            assert evaluate(Predicate("is_night"), self._nature_after_advance()) is True

    class WhenPhaseIsDay:
        def test_game_time_str_contains_day_label(self) -> None:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=2)  # day
            assert "白天" in nature.game_time_str

    class WhenPhaseIsDawn:
        def test_game_time_str_contains_dawn_label(self) -> None:
            world, _ = build_world()
            nature = _attach(world, clock_minutes=0)
            assert "黎明" in nature.game_time_str


class TestOutdoorLook:
    """15 号票：户外房间文案动态拼接。"""

    def test_description_has_outdoors_field_default_false(self) -> None:
        d = Description(short="s", long="l")
        assert d.outdoors is False

    def test_default_scene_start_yard_is_outdoors(self) -> None:
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        assert world.require_component(room, Description).outdoors is True

    def test_look_outdoors_appends_phase_desc(self) -> None:
        world, player_id = build_world()
        _attach(world, clock_minutes=0)  # dawn
        messages = execute_line(world, player_id, "look")
        assert any("黎明将至" in m for m in messages)

    def test_go_indoors_does_not_append_nature_desc(self) -> None:
        # 进入室内：go 响应本身不带 Nature 时辰/天气文案。
        world, player_id = build_world()
        _attach(world, clock_minutes=0)
        execute_line(world, player_id, "open south")
        messages = execute_line(world, player_id, "go south")
        assert not any("黎明将至" in m for m in messages)
        assert not any("日正当空" in m for m in messages)

    def test_look_indoors_does_not_append_nature_desc(self) -> None:
        # 室内 look：不追加户外才有的 Nature 时辰/天气描述。
        world, player_id = build_world()
        _attach(world, clock_minutes=0)
        execute_line(world, player_id, "open south")
        execute_line(world, player_id, "go south")  # 室内
        look = execute_line(world, player_id, "look")
        assert not any("黎明将至" in m for m in look)

    def test_look_desc_changes_after_phase_advance(self) -> None:
        world, player_id = build_world()
        _attach(world, clock_minutes=0)
        loop = _tick_loop(world)
        before = execute_line(world, player_id, "look")
        assert any("黎明将至" in m for m in before)
        loop.advance()
        loop.advance()  # -> day
        after = execute_line(world, player_id, "look")
        assert any("日正当空" in m for m in after)
        assert not any("黎明将至" in m for m in after)


class TestPhaseBroadcast:
    """16 号票：时辰切换广播 + on_nature_change。"""

    def test_phase_change_dispatches_on_nature_change(self) -> None:
        world, _ = build_world()
        _attach(world, clock_minutes=0)
        seen: list[NatureChangeContext] = []
        world.events.register(ON_NATURE_CHANGE, lambda ctx: seen.append(ctx))
        loop = _tick_loop(world)
        loop.advance()
        assert seen == []  # 未切换
        loop.advance()  # dawn -> day
        assert len(seen) == 1
        assert seen[0].old_phase == "dawn"
        assert seen[0].new_phase == "day"
        assert seen[0].time_msg == "天光大亮。"

    def test_nature_change_context_is_frozen(self) -> None:
        world, _ = build_world()
        ctx = NatureChangeContext(
            world=world,
            old_phase="dawn",
            new_phase="day",
            old_weather=Weather.CLEAR,
            new_weather=Weather.CLEAR,
            time_msg="x",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.old_phase = "night"  # type: ignore[misc]

    def test_outdoor_player_receives_time_msg_on_pending_messages(self) -> None:
        world, _ = build_world()
        _attach(world, clock_minutes=0)
        world.pending_messages.clear()
        loop = _tick_loop(world)
        loop.advance()
        loop.advance()  # phase change
        assert "天光大亮。" in world.pending_messages

    def test_indoor_player_does_not_receive_outdoor_broadcast(self) -> None:
        world, player_id = build_world()
        _attach(world, clock_minutes=0)
        execute_line(world, player_id, "open south")
        execute_line(world, player_id, "go south")  # 室内
        world.pending_messages.clear()
        loop = _tick_loop(world)
        loop.advance()
        loop.advance()
        assert world.pending_messages == []

    def test_container_npc_does_not_receive_phase_broadcast(self) -> None:
        """户外 Position+Container 但无 PlayerSession 的实体不应触发广播副本。"""
        world, player_id = build_world()
        _attach(world, clock_minutes=0)
        room = world.require_component(player_id, Position).room
        decoy = world.create_entity()
        world.add_component(decoy, Identity(name="背包石像"))
        world.add_component(decoy, Position(room=room))
        world.add_component(decoy, Container())
        world.pending_messages.clear()
        loop = _tick_loop(world)
        loop.advance()
        loop.advance()  # phase change
        # 仅真玩家一份；若仍用 Container 启发式会得到两份。
        assert world.pending_messages.count("天光大亮。") == 1


class TestWeather:
    """17 号票：天气晴雨骨架。"""

    def test_weather_field_and_is_raining(self) -> None:
        world, _ = build_world()
        nature = _attach(world, weather=Weather.CLEAR)
        assert nature.is_raining is False
        nature.weather = Weather.RAIN
        assert nature.is_raining is True
        assert evaluate(Predicate("is_raining"), nature) is True

    def test_weather_switches_with_injectable_rng(self) -> None:
        world, _ = build_world()
        # random() < 1.0 恒真 -> 每 tick 翻转
        nature = _attach(
            world,
            weather=Weather.CLEAR,
            weather_change_chance=1.0,
            rng=random.Random(0),
        )
        loop = _tick_loop(world)
        loop.advance()
        assert nature.weather is Weather.RAIN
        loop.advance()
        assert nature.weather is Weather.CLEAR

    def test_outdoor_look_is_phase_times_weather(self) -> None:
        world, player_id = build_world()
        _attach(world, clock_minutes=0, weather=Weather.RAIN)
        messages = execute_line(world, player_id, "look")
        assert any("黎明细雨" in m for m in messages)

    def test_weather_change_fires_on_nature_change(self) -> None:
        world, _ = build_world()
        _attach(
            world,
            clock_minutes=0,
            weather=Weather.CLEAR,
            weather_change_chance=1.0,
            # 相位 length=2，第一 tick 不切相位只切天气
            rng=random.Random(0),
        )
        seen: list[NatureChangeContext] = []
        world.events.register(ON_NATURE_CHANGE, lambda ctx: seen.append(ctx))
        _tick_loop(world).advance()
        assert len(seen) == 1
        assert seen[0].old_weather is Weather.CLEAR
        assert seen[0].new_weather is Weather.RAIN
        assert seen[0].old_phase == seen[0].new_phase == "dawn"

    def test_game_time_str_mentions_rain(self) -> None:
        world, _ = build_world()
        nature = _attach(world, clock_minutes=2, weather=Weather.RAIN)
        assert "雨" in nature.game_time_str


class TestYamlOutdoorsField:
    def test_room_outdoors_from_yaml(self, tmp_path: Path) -> None:
        scene = """
rooms:
  out:
    name: 户外
    outdoors: true
    long: 外面
  inn:
    name: 客栈
    long: 里面
    exits:
      north: { to: out }
player:
  name: 你
  start_room: inn
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        inn = world.require_component(player_id, Position).room
        assert world.require_component(inn, Description).outdoors is False
        out = world.require_component(inn, Exits).by_direction["north"].target
        assert world.require_component(out, Description).outdoors is True
