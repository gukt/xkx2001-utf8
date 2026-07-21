#!/usr/bin/env python3
"""M2 交通能力面矩阵（MVP 场景）：坐骑地形 / 渡口 / 短程连通。

用法（仓库根）::

    just verify-m2-travel

或::

    cd engine && uv run python scripts/verify_m2_travel.py

不读存档、不写存档；每次 ``load_mvp_scene()`` 加载 fresh MVP 场景。
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
    room_by_key,
    run_lines,
    wait_ferry_across,
)

from mud_engine.combat_system import clear_engagement
from mud_engine.components import Currency, Engaged, Position, Riding
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene


def _scenario_mount_terrain() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "road_yz_east")
    steps = run_lines(
        world,
        player_id,
        [
            ("ride 矮种马", Expect(contains=("骑上",))),
            ("go east", Expect(contains=("骑不过去",))),
        ],
    )
    still = world.require_component(player_id, Position).room == room_by_key(
        world, "road_yz_east"
    )
    steps.append(assert_step("(assert) 仍在官道", still))
    more = run_lines(
        world,
        player_id,
        [
            ("unride", Expect(contains=("下来",))),
            ("go east", Expect(any_of=("陡坡", "郊外", "野外"))),
        ],
    )
    steps.extend(more)
    at_edge = world.require_component(player_id, Position).room == room_by_key(
        world, "wild_edge"
    )
    steps.append(assert_step("(assert) 步行进入 wild_edge", at_edge))
    return ScenarioResult(name="弱马拒行 + 步行进野外", steps=steps)


def _scenario_stable_buy_ride() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_stable")
    world.require_component(player_id, Currency).amount = 200
    steps = run_lines(
        world,
        player_id,
        [
            ("buy 黄骠马", Expect(contains=("黄骠马",))),
            ("ride 黄骠马", Expect(contains=("骑上",))),
        ],
    )
    steps.append(
        assert_step("(assert) Riding 已挂", world.has_component(player_id, Riding))
    )
    return ScenarioResult(name="马厩买马骑乘", steps=steps)


def _scenario_ferry() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "ferry_west")
    steps: list[StepResult] = []
    look = execute_line(world, player_id, "look")
    ok_look, detail_look = check(look, Expect(contains=("渡船",)))
    steps.append(StepResult(line="look", messages=look, ok=ok_look, detail=detail_look))
    wait_msgs = wait_ferry_across(world, "ferry_west")
    if wait_msgs:
        steps.append(
            StepResult(
                line="(tick) 等船",
                messages=wait_msgs,
                ok=True,
                detail="",
            )
        )
    cross = execute_line(world, player_id, "go across")
    at_east = world.require_component(player_id, Position).room == room_by_key(
        world, "ferry_east"
    )
    ok_c, detail_c = check(cross, Expect(any_of=("岸", "渡")))
    steps.append(
        StepResult(
            line="go across",
            messages=cross,
            ok=at_east and ok_c,
            detail="" if at_east and ok_c else f"{detail_c}; at_east={at_east}",
        )
    )
    return ScenarioResult(name="渡口过河", steps=steps)


def _scenario_huashan_to_yangzhou() -> ScenarioResult:
    """短程冒烟：华山村口 → 官道 → 扬州南门（不穿越整张图）。"""
    world, player_id = load_mvp_scene()
    steps = run_lines(
        world,
        player_id,
        [
            ("go south", Expect(any_of=("官道", "扬州"))),
            ("go south", Expect(any_of=("南门", "扬州"))),
        ],
    )
    at_nanmen = world.require_component(player_id, Position).room == room_by_key(
        world, "yangzhou_nanmen"
    )
    steps.append(assert_step("(assert) 抵达扬州南门", at_nanmen))
    # 清掉可能因路过触发的交战，避免污染后续（本场景南门无 aggro，保险）
    if world.has_component(player_id, Engaged):
        clear_engagement(world, player_id, reason="verify")
    return ScenarioResult(name="华山→扬州短程", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_mount_terrain(),
        _scenario_stable_buy_ride(),
        _scenario_ferry(),
        _scenario_huashan_to_yangzhou(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
