#!/usr/bin/env python3
"""M3 内容包闭环转录：废弃探测站示例包走通一遍。

用法（仓库根）::

    just verify-m3

或::

    cd engine && uv run python scripts/verify_m3_pack_loop.py

正式门禁仍以 ``tests/test_m3_pack_loop.py`` 为准；本脚本侧重可读转录。
不读存档、不写存档；每次 ``load_pack`` 加载 fresh 示例包。
"""

from __future__ import annotations

import sys
from pathlib import Path

from verify_harness import (
    Expect,
    ScenarioResult,
    StepResult,
    assert_step,
    check,
    main_from,
    room_by_key,
)

from mud_engine.components import Currency, Position
from mud_engine.pack import load_pack
from mud_engine.parsing import execute_line
from mud_engine.world import EntityId, World

_EXAMPLE_PACK = (
    Path(__file__).resolve().parents[2]
    / ".scratch"
    / "m3-ugc-loop-creation-surface"
    / "example-pack"
)


def _step(
    world: World,
    player_id: EntityId,
    line: str,
    expect: Expect | None = None,
) -> StepResult:
    messages = execute_line(world, player_id, line)
    ok, detail = check(messages, expect)
    return StepResult(line=line, messages=messages, ok=ok, detail=detail)


def _scenario_pack_loop() -> ScenarioResult:
    world, player_id = load_pack(_EXAMPLE_PACK)
    steps: list[StepResult] = []

    steps.append(
        assert_step(
            "(assert) 出生气闸舱",
            world.require_component(player_id, Position).room
            == room_by_key(world, "outpost_airlock"),
        )
    )
    steps.append(_step(world, player_id, "look", Expect(contains=("气闸舱",))))
    steps.append(_step(world, player_id, "go east", Expect(contains=("补给舱",))))
    steps.append(_step(world, player_id, "get 通行卡", Expect(contains=("通行卡",))))
    steps.append(_step(world, player_id, "unlock east", Expect(contains=("解锁",))))
    steps.append(_step(world, player_id, "open east", Expect(contains=("打开",))))
    steps.append(_step(world, player_id, "go east", Expect(contains=("主控室",))))
    steps.append(
        assert_step(
            "(assert) 主控室",
            world.require_component(player_id, Position).room
            == room_by_key(world, "outpost_control"),
        )
    )
    steps.append(
        _step(
            world,
            player_id,
            "ask 维修机器人 about 站点",
            Expect(contains=("废弃探测站",)),
        )
    )
    steps.append(
        _step(
            world,
            player_id,
            "ask 维修机器人 about 未知话题xyz",
            Expect(contains=("可询问",)),
        )
    )
    money_before = world.require_component(player_id, Currency).amount
    steps.append(
        _step(world, player_id, "buy 备用能量芯", Expect(contains=("备用能量芯",)))
    )
    steps.append(
        assert_step(
            "(assert) 买后余额 -25",
            world.require_component(player_id, Currency).amount == money_before - 25,
        )
    )
    steps.append(_step(world, player_id, "look", Expect(contains=("主控室",))))

    return ScenarioResult(name="废弃探测站内容包闭环", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [_scenario_pack_loop()]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
