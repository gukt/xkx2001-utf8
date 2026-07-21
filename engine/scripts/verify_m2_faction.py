#!/usr/bin/env python3
"""M2 门派能力面矩阵（MVP 场景）：门禁 / join / learn / practice。

用法（仓库根）::

    just verify-m2-faction

或::

    cd engine && uv run python scripts/verify_m2_faction.py

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
)

from mud_engine.components import Faction, Position, SkillLevels
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene


def _scenario_entry_guard() -> ScenarioResult:
    """山门只验性别 + 门派；持刃不再拒绝。本场景用他派身份验证拒绝文案。"""
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "road_shaolin")
    if not world.has_component(player_id, Faction):
        world.add_component(player_id, Faction(faction_id="beggars"))
    else:
        world.require_component(player_id, Faction).faction_id = "beggars"
    steps = run_lines(
        world,
        player_id,
        [
            ("go east", Expect(any_of=("他派", "门派", "男子"))),
        ],
    )
    still_outside = world.require_component(player_id, Position).room == room_by_key(
        world, "road_shaolin"
    )
    steps.append(
        assert_step(
            "(assert) 他派仍在官道",
            still_outside,
            messages=[str(still_outside)],
        )
    )
    # 清掉门派后再进（默认男）
    world.remove_component(player_id, Faction)
    entered = execute_line(world, player_id, "go east")
    at_gate = world.require_component(player_id, Position).room == room_by_key(
        world, "shaolin_shanmen"
    )
    ok_e, detail_e = check(entered, Expect(absent=("不得",)))
    steps.append(
        StepResult(
            line="go east（无门派）",
            messages=entered,
            ok=at_gate and ok_e,
            detail="" if at_gate and ok_e else f"{detail_e}; at_gate={at_gate}",
        )
    )
    return ScenarioResult(name="山门门禁拒绝/通过", steps=steps)


def _scenario_join_learn_practice() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "shaolin_shanmen")
    steps = run_lines(
        world,
        player_id,
        [
            ("go north", Expect(contains=("广场",))),
            ("join 少林", Expect(contains=("加入了少林",))),
        ],
    )
    fac = world.require_component(player_id, Faction).faction_id == "shaolin"
    steps.append(assert_step("(assert) Faction=shaolin", fac))

    more = run_lines(
        world,
        player_id,
        [
            ("go east", Expect(contains=("武场",))),
            ("learn martial", Expect(contains=("学会了",))),
            ("status", Expect(any_of=("气血", "力量"))),
            ("skills", Expect(contains=("luohan_quan",))),
        ],
    )
    steps.extend(more)
    skills = world.require_component(player_id, SkillLevels)
    has_skill = "luohan_quan" in skills.levels
    steps.append(assert_step("(assert) 已学 luohan_quan", has_skill))
    exp_before = skills.levels["luohan_quan"].exp if has_skill else 0
    practice = execute_line(world, player_id, "practice luohan_quan")
    exp_after = world.require_component(player_id, SkillLevels).levels["luohan_quan"].exp
    ok_p, detail_p = check(practice, Expect(any_of=("经验", "升到了")))
    gained = exp_after > exp_before or any("升到了" in line for line in practice)
    steps.append(
        StepResult(
            line="practice luohan_quan",
            messages=practice,
            ok=ok_p and gained,
            detail="" if ok_p and gained else f"{detail_p}; exp {exp_before}→{exp_after}",
        )
    )
    return ScenarioResult(name="join → learn → practice", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_entry_guard(),
        _scenario_join_learn_practice(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
