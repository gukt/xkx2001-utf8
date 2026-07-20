#!/usr/bin/env python3
"""M1 Nature 时辰/天气矩阵（默认场景）：一键跑通并打印转录 + PASS/FAIL 摘要。

用法（仓库根）::

    just verify-nature

或::

    cd engine && uv run python scripts/verify_m1_nature.py

不读存档、不写存档；每次 ``build_world()`` 加载 fresh 默认场景。
手测步骤见 ``.scratch/m1-core-engine-skeleton/verify-nature-cli.md``。

相位快进 / 广播 / 天气切换走 ``TickLoop.advance`` seam（与
``tests/test_nature.py`` 一致），不靠墙钟等待。
"""

from __future__ import annotations

import os
import random
import sys
from dataclasses import dataclass, field

from mud_engine.conditions import And, Equals, Predicate, evaluate
from mud_engine.nature import Weather
from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World

_EXPECTED_PHASES = ("dawn", "day", "dusk", "night")
_DAY_DESC = "日正当空，天色晴朗。"
_NIGHT_DESC = "夜深了，四下一片寂静。"
_DAWN_RAIN_DESC = "东方微曦，细雨蒙蒙。"
_PHASE_DAY_MSG = "天光大亮。"
_WEATHER_RAIN_MSG = "天阴了下来，下起了雨。"
_WEATHER_CLEAR_MSG = "雨停了，天空放晴。"


@dataclass(frozen=True)
class Expect:
    """对单条命令输出的期望（子串匹配）。"""

    contains: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()


@dataclass
class StepResult:
    line: str
    messages: list[str]
    ok: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


def _check(messages: list[str], expect: Expect | None) -> tuple[bool, str]:
    if expect is None:
        return True, ""
    combined = "\n".join(messages)
    for needle in expect.contains:
        if needle not in combined:
            return False, f"缺少期望子串：{needle!r}"
    if expect.any_of and not any(n in combined for n in expect.any_of):
        return False, f"未命中任一期望：{expect.any_of!r}"
    for needle in expect.absent:
        if needle in combined:
            return False, f"不应出现子串：{needle!r}"
    return True, ""


def _run_lines(
    world: World,
    player_id: EntityId,
    steps: list[tuple[str, Expect | None]],
) -> list[StepResult]:
    results: list[StepResult] = []
    for line, expect in steps:
        messages = execute_line(world, player_id, line)
        ok, detail = _check(messages, expect)
        results.append(StepResult(line=line, messages=messages, ok=ok, detail=detail))
    return results


def _set_phase(world: World, phase_name: str) -> None:
    nature = world.nature
    if nature is None:
        raise RuntimeError("默认场景应挂 Nature")
    for index, phase in enumerate(nature.phases):
        if phase.name == phase_name:
            nature.phase_index = index
            nature.elapsed = 0
            nature.weather_change_chance = 0.0
            return
    raise RuntimeError(f"场景无相位 {phase_name!r}")


def _advance_once(world: World) -> list[str]:
    """推进一拍并返回（并清空）pending_messages。"""
    world.pending_messages.clear()
    loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
    loop.advance()
    messages = list(world.pending_messages)
    world.pending_messages.clear()
    return messages


def _advance_at_phase_boundary(world: World) -> list[str]:
    """把 elapsed 推到当前相末尾，再 advance 触发相位切换。"""
    nature = world.nature
    if nature is None:
        raise RuntimeError("默认场景应挂 Nature")
    nature.weather_change_chance = 0.0
    nature.elapsed = max(0, nature.current_phase.length - nature.game_minutes_per_tick)
    return _advance_once(world)


def _scenario_attach_and_phases() -> ScenarioResult:
    world, _ = build_world()
    steps: list[StepResult] = []
    nature = world.nature
    ok_attached = nature is not None
    steps.append(
        StepResult(
            line="(assert) world.nature 已挂载",
            messages=[repr(type(nature).__name__) if nature else "None"],
            ok=ok_attached,
            detail="" if ok_attached else "build_world 应挂 Nature",
        )
    )
    if nature is not None:
        names = tuple(p.name for p in nature.phases)
        ok_seq = names == _EXPECTED_PHASES
        steps.append(
            StepResult(
                line="(assert) day_phases 序列",
                messages=[f"{' → '.join(names)}"],
                ok=ok_seq,
                detail="" if ok_seq else f"期望 {_EXPECTED_PHASES}",
            )
        )
    return ScenarioResult(name="挂载与相位序列（B1）", steps=steps)


def _scenario_outdoor_look() -> ScenarioResult:
    world, player_id = build_world()
    steps: list[StepResult] = []

    _set_phase(world, "day")
    msgs_day = execute_line(world, player_id, "look")
    ok_day, detail_day = _check(msgs_day, Expect(contains=(_DAY_DESC,)))
    steps.append(
        StepResult(
            line="look @ day",
            messages=msgs_day,
            ok=ok_day,
            detail=detail_day,
        )
    )

    _set_phase(world, "night")
    msgs_night = execute_line(world, player_id, "look")
    ok_night, detail_night = _check(
        msgs_night,
        Expect(contains=(_NIGHT_DESC,), absent=(_DAY_DESC,)),
    )
    steps.append(
        StepResult(
            line="look @ night",
            messages=msgs_night,
            ok=ok_night,
            detail=detail_night,
        )
    )
    return ScenarioResult(name="户外 look × 时辰（B3）", steps=steps)


def _scenario_indoor_no_nature() -> ScenarioResult:
    world, player_id = build_world()
    _set_phase(world, "day")
    steps = _run_lines(
        world,
        player_id,
        [
            ("n", Expect(contains=("长廊",))),
            (
                "look",
                Expect(
                    absent=(
                        _DAY_DESC,
                        _NIGHT_DESC,
                        _DAWN_RAIN_DESC,
                        "下着小雨",
                    )
                ),
            ),
        ],
    )
    return ScenarioResult(name="室内不拼 Nature（B3）", steps=steps)


def _scenario_phase_broadcast() -> ScenarioResult:
    world, player_id = build_world()
    steps: list[StepResult] = []

    _set_phase(world, "dawn")
    msgs_out = _advance_at_phase_boundary(world)
    ok_out, detail_out = _check(msgs_out, Expect(contains=(_PHASE_DAY_MSG,)))
    steps.append(
        StepResult(
            line="(tick) 户外 dawn→day 广播",
            messages=msgs_out,
            ok=ok_out,
            detail=detail_out,
        )
    )

    _set_phase(world, "dawn")
    execute_line(world, player_id, "n")  # 室内长廊
    msgs_in = _advance_at_phase_boundary(world)
    ok_in, detail_in = _check(msgs_in, Expect(absent=(_PHASE_DAY_MSG,)))
    steps.append(
        StepResult(
            line="(tick) 室内不收户外广播",
            messages=msgs_in,
            ok=ok_in,
            detail=detail_in,
        )
    )
    return ScenarioResult(name="相位切换广播（B4）", steps=steps)


def _scenario_weather() -> ScenarioResult:
    world, player_id = build_world()
    steps: list[StepResult] = []

    _set_phase(world, "dawn")
    assert world.nature is not None
    world.nature.weather = Weather.RAIN
    msgs_rain_look = execute_line(world, player_id, "look")
    ok_look, detail_look = _check(
        msgs_rain_look, Expect(contains=(_DAWN_RAIN_DESC,))
    )
    steps.append(
        StepResult(
            line="look @ dawn+rain",
            messages=msgs_rain_look,
            ok=ok_look,
            detail=detail_look,
        )
    )

    world.nature.weather = Weather.CLEAR
    world.nature.weather_change_chance = 1.0
    world.nature.rng = random.Random(0)
    was_raining = world.nature.is_raining
    msgs_switch = _advance_once(world)
    now_raining = world.nature.is_raining
    ok_flip = was_raining != now_raining
    ok_msg, detail_msg = _check(
        msgs_switch,
        Expect(any_of=(_WEATHER_RAIN_MSG, _WEATHER_CLEAR_MSG)),
    )
    steps.append(
        StepResult(
            line="(tick) 天气切换广播",
            messages=msgs_switch,
            ok=ok_flip and ok_msg,
            detail="" if ok_flip and ok_msg else f"{detail_msg}; is_raining {was_raining}→{now_raining}",
        )
    )
    return ScenarioResult(name="天气二维文案 + 切换（B5）", steps=steps)


def _scenario_predicates() -> ScenarioResult:
    world, _ = build_world()
    nature = world.nature
    if nature is None:
        return ScenarioResult(
            name="谓词 / 求值器（B2+A2）",
            steps=[
                StepResult(
                    line="(assert) nature",
                    messages=[],
                    ok=False,
                    detail="无 NatureState",
                )
            ],
        )

    steps: list[StepResult] = []

    def _assert_eval(label: str, ok: bool, detail: str = "") -> None:
        steps.append(
            StepResult(line=label, messages=[str(ok)], ok=ok, detail=detail)
        )

    _set_phase(world, "dawn")
    _assert_eval(
        "evaluate phase==dawn @ dawn",
        evaluate(Equals("phase", "dawn"), nature) is True,
    )
    _assert_eval(
        "evaluate is_night @ dawn",
        evaluate(Predicate("is_night"), nature) is True,
    )
    _assert_eval(
        "evaluate is_day @ dawn",
        evaluate(Predicate("is_day"), nature) is False,
    )

    _set_phase(world, "day")
    _assert_eval(
        "evaluate is_day @ day",
        evaluate(Predicate("is_day"), nature) is True,
    )
    _assert_eval(
        "evaluate is_night @ day",
        evaluate(Predicate("is_night"), nature) is False,
    )
    _assert_eval(
        "evaluate phase==dawn @ day",
        evaluate(Equals("phase", "dawn"), nature) is False,
    )
    _assert_eval(
        "game_time_str @ day",
        "白天" in nature.game_time_str,
    )

    _set_phase(world, "night")
    _assert_eval(
        "evaluate is_night @ night",
        evaluate(Predicate("is_night"), nature) is True,
    )
    _assert_eval(
        "And(is_night, not is_day) @ night",
        evaluate(
            And((Predicate("is_night"), Predicate("is_day"))),
            nature,
        )
        is False
        and evaluate(Predicate("is_night"), nature) is True,
    )

    return ScenarioResult(name="谓词 / 求值器（B2+A2）", steps=steps)


def _scenario_chatter_cross() -> ScenarioResult:
    """旁证：Nature is_night 驱动夜猫 Chatter（完整 NPC 矩阵见 verify-npc）。"""
    world, player_id = build_world()
    assert world.ai is not None

    class _AlwaysSpeakRng:
        def random(self) -> float:
            return 0.0

        def choice(self, seq):  # noqa: ANN001
            return seq[0]

    world.ai.rng = _AlwaysSpeakRng()
    _set_phase(world, "night")
    msgs = _advance_once(world)
    ok, detail = _check(
        msgs, Expect(contains=("夜猫子说：夜深了，该歇歇了。",))
    )
    _ = player_id
    return ScenarioResult(
        name="Chatter is_night 旁证",
        steps=[
            StepResult(
                line="(tick) night：夜猫开口",
                messages=msgs,
                ok=ok,
                detail=detail,
            )
        ],
    )


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_attach_and_phases(),
        _scenario_outdoor_look(),
        _scenario_indoor_no_nature(),
        _scenario_phase_broadcast(),
        _scenario_weather(),
        _scenario_predicates(),
        _scenario_chatter_cross(),
    ]


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _step_mark(ok: bool) -> str:
    if ok:
        return f"\033[32m✔\033[0m" if _use_color() else "✔"
    return f"\033[31m✖\033[0m" if _use_color() else "✖"


def _scenario_mark(ok: bool) -> str:
    if ok:
        return f"\033[32m✔\033[0m" if _use_color() else "✔"
    return f"\033[31m✖\033[0m" if _use_color() else "✖"


def print_report(scenarios: list[ScenarioResult]) -> int:
    for sc in scenarios:
        print(f"\n=== {sc.name} ===")
        for step in sc.steps:
            print(f"> {step.line}  {_step_mark(step.ok)}")
            for m in step.messages:
                print(f"  {m}")
            if step.detail:
                print(f"  !! {step.detail}")

    print("\n── 摘要 ──")
    for sc in scenarios:
        print(f"  {_scenario_mark(sc.ok)} {sc.name}")
    total_fail_steps = sum(1 for sc in scenarios for s in sc.steps if not s.ok)
    n_ok = sum(1 for sc in scenarios if sc.ok)
    print(f"  场景 {n_ok}/{len(scenarios)} 通过；失败步骤 {total_fail_steps}")
    return 0 if total_fail_steps == 0 else 1


def main() -> int:
    return print_report(all_scenarios())


if __name__ == "__main__":
    sys.exit(main())
