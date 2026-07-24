#!/usr/bin/env python3
"""Pre-M4 引擎房间保真：官方扬州 S3 四锚点矩阵（给人看的转录 + PASS/FAIL）。

覆盖：户外 details+语义色、藏书阁、日间店、翰林剧情门三件套。
正式门禁仍以 ``tests/test_room_details.py`` / ``test_library.py`` /
``test_day_shop.py`` / ``test_story_doors.py`` 为准；本脚本侧重全局观察。

用法（仓库根）::

    just verify-room-fidelity

或::

    cd engine && uv run python scripts/verify_pre_m4_room_fidelity.py

不读存档、不写存档；每次 ``load_mvp_scene()`` 加载 fresh MVP。
"""

from __future__ import annotations

import sys

from verify_harness import (
    Expect,
    ScenarioResult,
    StepResult,
    assert_step,
    check,
    main_from,
    move_to,
    run_lines,
)

from openmud.components import Container, Currency, Exits, Identity, Position
from openmud.parsing import execute_line
from openmud.scenes import load_mvp_scene
from openmud.world import World


def _force_phase(world: World, name: str) -> None:
    assert world.nature is not None
    world.nature.seek_phase(name)


def _scenario_outdoor_details_color() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_guangchang")
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("中央广场", "石狮(shi_shi)", "旗杆(qi_gan)"))),
            ("look 石狮", Expect(contains=("石狮",))),
            ("look shi_shi", Expect(contains=("石狮",))),
            (
                "look 旗杆",
                Expect(contains=("<c:yellow>旗角</c>",), absent=("\x1b[",)),
            ),
        ],
    )
    return ScenarioResult(name="户外风景+语义色（广场）", steps=steps)


def _scenario_cangshuge() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_cangshuge")
    before = world.require_component(player_id, Currency).amount
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("藏书阁",))),
            ("look 书架", Expect(contains=("侠客行入门",))),
            ("read xkxr", Expect(contains=("侠客行入门",))),
            ("read 1", Expect(any_of=("第一回", "初入江湖", "天下风云"))),
            ("practice", Expect(contains=("读书", "练功"))),
        ],
    )
    after = world.require_component(player_id, Currency).amount
    steps.append(
        assert_step(
            "(assert) 读章扣银两",
            after == before - 1,
            messages=[f"currency {before} -> {after}"],
        )
    )
    return ScenarioResult(name="藏书阁主路径", steps=steps)


def _scenario_day_shop() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_xidajie")
    shop = world.room_ids["yangzhou_datiepu"]
    street = world.room_ids["yangzhou_xidajie"]
    steps: list[StepResult] = []

    _force_phase(world, "day")
    day_enter = execute_line(world, player_id, "go north")
    ok, detail = check(day_enter, Expect(any_of=("打铁铺", "铁匠")))
    steps.append(StepResult(line="(day) go north", messages=day_enter, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 白天进入打铁铺",
            world.require_component(player_id, Position).room == shop,
        )
    )
    steps.extend(run_lines(world, player_id, [("go south", Expect(contains=("西大街",)))]))

    _force_phase(world, "night")
    night_enter = execute_line(world, player_id, "go north")
    ok, detail = check(night_enter, Expect(contains=("晚上",)))
    steps.append(
        StepResult(line="(night) go north", messages=night_enter, ok=ok, detail=detail)
    )
    steps.append(
        assert_step(
            "(assert) 夜间仍在西大街",
            world.require_component(player_id, Position).room == street,
        )
    )
    return ScenarioResult(name="日间店（打铁铺）", steps=steps)


def _scenario_hanlin() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_hanlin")
    hanlin = world.room_ids["yangzhou_hanlin"]
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("翰林",))),
            ("go west", Expect(contains=("挡",))),
            ("go east", Expect(contains=("没有出口",))),
            ("get 闺房钥匙", Expect(contains=("拿起",))),
            ("unlock east", Expect(any_of=("解锁", "打开"))),
        ],
    )
    bag = [
        world.require_component(i, Identity).name
        for i in world.require_component(player_id, Container).items
    ]
    steps.append(
        assert_step(
            "(assert) 耗钥后钥匙已销毁",
            "闺房钥匙" not in bag,
            messages=[f"bag={bag}"],
        )
    )
    steps.append(
        assert_step(
            "(assert) 东出口已揭出",
            "east" in world.require_component(hanlin, Exits).by_direction,
        )
    )
    enter = execute_line(world, player_id, "go east")
    ok, detail = check(enter, Expect(any_of=("闺房", "翰林闺房")))
    steps.append(StepResult(line="go east", messages=enter, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 抵达翰林闺房",
            world.require_component(player_id, Position).room
            == world.room_ids["yangzhou_hanlin_neiyuan"],
        )
    )
    return ScenarioResult(name="剧情门翰林三件套", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_outdoor_details_color(),
        _scenario_cangshuge(),
        _scenario_day_shop(),
        _scenario_hanlin(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
