#!/usr/bin/env python3
"""M2 金钱/商店能力面矩阵（MVP 场景）：buy / sell。

用法（仓库根）::

    just verify-m2-economy

或::

    cd engine && uv run python scripts/verify_m2_economy.py

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
    run_lines,
)

from openmud.components import Currency, Identity
from openmud.parsing import execute_line
from openmud.scenes import load_mvp_scene


def _scenario_bank() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_qianzhuang")
    world.require_component(player_id, Currency).amount = 100
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("钱庄",))),
            ("buy 银票", Expect(contains=("银票",))),
        ],
    )
    after_buy = world.require_component(player_id, Currency).amount
    steps.append(
        assert_step(
            "(assert) buy 后余额减少",
            after_buy < 100,
            messages=[f"currency={after_buy}"],
        )
    )
    sell = execute_line(world, player_id, "sell 银票")
    ok, detail = check(sell, Expect(contains=("银票",)))
    steps.append(StepResult(line="sell 银票", messages=sell, ok=ok, detail=detail))
    return ScenarioResult(name="钱庄 buy/sell", steps=steps)


def _scenario_smith() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_datiepu")
    world.require_component(player_id, Currency).amount = 200
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("铁匠",))),
            ("buy 钢刀", Expect(contains=("钢刀",))),
            ("sell 钢刀", Expect(contains=("钢刀",))),
        ],
    )
    return ScenarioResult(name="打铁铺 buy/sell", steps=steps)


def _scenario_insufficient() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_datiepu")
    world.require_component(player_id, Currency).amount = 0
    steps = run_lines(
        world,
        player_id,
        [
            ("buy 钢刀", Expect(any_of=("不够", "不足", "银两", "钱"))),
        ],
    )
    # 确认没买到
    from openmud.components import Container

    bag = world.get_component(player_id, Container)
    has_blade = False
    if bag is not None:
        has_blade = any(
            world.require_component(item, Identity).name == "钢刀" for item in bag.items
        )
    steps.append(
        assert_step(
            "(assert) 余额不足未购得钢刀",
            not has_blade,
            messages=["无钢刀" if not has_blade else "仍有钢刀"],
        )
    )
    return ScenarioResult(name="余额不足拒绝", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_bank(),
        _scenario_smith(),
        _scenario_insufficient(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
