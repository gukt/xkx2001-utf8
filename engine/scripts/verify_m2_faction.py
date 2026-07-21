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

from mud_engine.components import Container, Faction, Position, SkillLevels
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import instantiate_item
from mud_engine.scenes import load_mvp_scene
from mud_engine.world import EntityId, World


def _give_blade(world: World, player_id: EntityId) -> None:
    blade = instantiate_item(world, "steel_blade")
    bag = world.get_component(player_id, Container)
    if bag is None:
        world.add_component(player_id, Container())
        bag = world.require_component(player_id, Container)
    bag.items.add(blade)


def _scenario_entry_guard() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "road_shaolin")
    _give_blade(world, player_id)
    steps = run_lines(
        world,
        player_id,
        [
            ("go east", Expect(any_of=("刀", "刃", "兵器"))),
        ],
    )
    still_outside = world.require_component(player_id, Position).room == room_by_key(
        world, "road_shaolin"
    )
    steps.append(
        assert_step(
            "(assert) 持刃仍在官道",
            still_outside,
            messages=[str(still_outside)],
        )
    )
    drop = execute_line(world, player_id, "drop 钢刀")
    ok_d, detail_d = check(drop, Expect(contains=("放下",)))
    steps.append(StepResult(line="drop 钢刀", messages=drop, ok=ok_d, detail=detail_d))
    entered = execute_line(world, player_id, "go east")
    at_gate = world.require_component(player_id, Position).room == room_by_key(
        world, "shaolin_shanmen"
    )
    ok_e, detail_e = check(entered, Expect(absent=("不得",)))
    steps.append(
        StepResult(
            line="go east（无刃）",
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
