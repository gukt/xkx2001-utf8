#!/usr/bin/env python3
"""M2 轻量全程旅程（MVP 场景）：给人看的一键转录，断言保持宽松。

用法（仓库根）::

    just verify-m2-journey

或::

    cd engine && uv run python scripts/verify_m2_journey.py

正式门禁仍以 ``tests/test_m2_e2e_script.py`` 为准；本脚本侧重可读转录。
不读存档、不写存档。
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
    room_by_key,
    wait_ferry_across,
)

from mud_engine.combat_system import clear_engagement
from mud_engine.components import (
    Container,
    Currency,
    Engaged,
    Faction,
    Identity,
    Position,
    Riding,
    SkillLevels,
    Vitals,
)
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


def _npc_named(world: World, name: str, *, exclude: EntityId) -> EntityId:
    for entity in world.entities_with(Identity):
        if entity == exclude:
            continue
        if world.require_component(entity, Identity).name == name:
            return entity
    raise RuntimeError(f"{name!r} not found")


def _step(
    world: World,
    player_id: EntityId,
    line: str,
    expect: Expect | None = None,
) -> StepResult:
    messages = execute_line(world, player_id, line)
    ok, detail = check(messages, expect)
    return StepResult(line=line, messages=messages, ok=ok, detail=detail)


def _scenario_full_journey() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    steps: list[StepResult] = []

    steps.append(
        assert_step(
            "(assert) 出生华山村",
            world.require_component(player_id, Position).room
            == room_by_key(world, "huashan_birth"),
        )
    )

    # 教程
    steps.append(_step(world, player_id, "go north", Expect(contains=("向导",))))
    steps.append(
        _step(world, player_id, "ask 向导 about 战斗", Expect(any_of=("attack", "战斗")))
    )
    steps.append(
        _step(world, player_id, "ask 向导 about 去哪", Expect(contains=("扬州",)))
    )

    # 木桩教学
    steps.append(_step(world, player_id, "go east", Expect(contains=("稻草人",))))
    steps.append(_step(world, player_id, "attack 稻草人", Expect(contains=("交战",))))
    TickLoop(lambda: None, world=world).advance()
    pending = list(world.pending_messages)
    world.pending_messages.clear()
    ok_tick, detail_tick = check(pending, Expect(any_of=("气血", "稻草人")))
    steps.append(
        StepResult(line="(tick) 木桩回合", messages=pending, ok=ok_tick, detail=detail_tick)
    )
    if world.has_component(player_id, Engaged):
        clear_engagement(world, player_id, reason="journey")

    # 前往扬州
    steps.append(_step(world, player_id, "go west", None))
    steps.append(_step(world, player_id, "go south", None))
    steps.append(_step(world, player_id, "go south", Expect(any_of=("官道", "扬州"))))
    steps.append(
        assert_step(
            "(assert) road_huashan_yz",
            world.require_component(player_id, Position).room
            == room_by_key(world, "road_huashan_yz"),
        )
    )
    steps.append(_step(world, player_id, "go south", Expect(any_of=("南门", "扬州"))))

    # 钱庄
    steps.append(_step(world, player_id, "go north", None))
    steps.append(_step(world, player_id, "go north", None))
    steps.append(_step(world, player_id, "go east", None))
    steps.append(_step(world, player_id, "go north", Expect(contains=("钱庄",))))
    money_before = world.require_component(player_id, Currency).amount
    steps.append(_step(world, player_id, "buy 银票", Expect(contains=("银票",))))
    steps.append(
        assert_step(
            "(assert) buy 后余额减少",
            world.require_component(player_id, Currency).amount < money_before,
        )
    )
    steps.append(_step(world, player_id, "sell 银票", Expect(contains=("银票",))))

    # 打铁铺留一把钢刀
    steps.append(_step(world, player_id, "go south", None))
    steps.append(_step(world, player_id, "go west", None))
    steps.append(_step(world, player_id, "go west", None))
    steps.append(_step(world, player_id, "go north", Expect(contains=("铁匠",))))
    steps.append(_step(world, player_id, "buy 钢刀", Expect(contains=("钢刀",))))
    steps.append(_step(world, player_id, "buy 钢刀", Expect(contains=("钢刀",))))
    steps.append(_step(world, player_id, "sell 钢刀", Expect(contains=("钢刀",))))

    # 马厩
    steps.append(_step(world, player_id, "go south", None))
    steps.append(_step(world, player_id, "go south", Expect(contains=("马厩",))))
    steps.append(_step(world, player_id, "buy 黄骠马", Expect(contains=("黄骠马",))))
    steps.append(_step(world, player_id, "ride 黄骠马", Expect(contains=("骑上",))))
    steps.append(
        assert_step("(assert) Riding", world.has_component(player_id, Riding))
    )

    # 官道骑乘 → 陡坡拒行
    steps.append(_step(world, player_id, "go north", None))
    steps.append(_step(world, player_id, "go east", None))
    steps.append(_step(world, player_id, "go east", None))
    steps.append(_step(world, player_id, "go east", None))
    steps.append(_step(world, player_id, "go east", Expect(any_of=("官道", "东门"))))
    steps.append(_step(world, player_id, "go east", Expect(contains=("骑不过去",))))
    steps.append(_step(world, player_id, "unride", Expect(contains=("下来",))))
    steps.append(_step(world, player_id, "go east", None))  # wild_edge
    steps.append(_step(world, player_id, "go east", None))  # wild_forest

    # 野外胜仗
    bandit = _npc_named(world, "山贼", exclude=player_id)
    TickLoop(lambda: None, world=world).advance()
    if not world.has_component(player_id, Engaged):
        steps.append(_step(world, player_id, "attack 山贼", Expect(contains=("交战",))))
    else:
        steps.append(assert_step("(tick) aggro 已交战", True, messages=["Engaged"]))
    world.require_component(player_id, Vitals).qi_current = 200
    world.require_component(player_id, Vitals).qi_max = 200
    money_fight = world.require_component(player_id, Currency).amount
    world.pending_messages.clear()
    for _ in range(50):
        if not world.has_component(bandit, Vitals):
            break
        if world.require_component(bandit, Vitals).qi_current <= 0:
            break
        TickLoop(lambda: None, world=world).advance()
    pending_fight = list(world.pending_messages)
    world.pending_messages.clear()
    dead = (not world.has_component(bandit, Vitals)) or (
        world.require_component(bandit, Vitals).qi_current <= 0
    )
    loot = world.require_component(player_id, Currency).amount > money_fight or any(
        "打倒" in m or "银" in m or "经验" in m for m in pending_fight
    )
    steps.append(
        assert_step(
            "(tick×N) 击杀山贼",
            dead and loot,
            messages=pending_fight[-6:] if pending_fight else [],
        )
    )
    if world.has_component(player_id, Engaged):
        clear_engagement(world, player_id, reason="journey")

    # 渡口
    steps.append(_step(world, player_id, "go east", None))
    steps.append(_step(world, player_id, "go east", Expect(any_of=("渡", "船"))))
    wait_ferry_across(world, "ferry_west")
    steps.append(_step(world, player_id, "go across", Expect(any_of=("岸", "渡"))))
    steps.append(
        assert_step(
            "(assert) ferry_east",
            world.require_component(player_id, Position).room
            == room_by_key(world, "ferry_east"),
        )
    )

    # 少林门禁：持刃可进（默认男、无门派）
    steps.append(_step(world, player_id, "go east", None))  # road_shaolin
    bag = world.require_component(player_id, Container)
    has_blade = any(
        world.require_component(item, Identity).name == "钢刀" for item in bag.items
    )
    steps.append(assert_step("(assert) 仍持钢刀", has_blade))
    steps.append(_step(world, player_id, "go east", Expect(absent=("不得", "刃"))))
    steps.append(
        assert_step(
            "(assert) shaolin_shanmen",
            world.require_component(player_id, Position).room
            == room_by_key(world, "shaolin_shanmen"),
        )
    )

    # join / learn / practice
    steps.append(_step(world, player_id, "go north", None))
    steps.append(_step(world, player_id, "join 少林", Expect(contains=("加入了少林",))))
    steps.append(
        assert_step(
            "(assert) Faction=shaolin",
            world.require_component(player_id, Faction).faction_id == "shaolin",
        )
    )
    steps.append(_step(world, player_id, "go east", Expect(contains=("武场",))))
    steps.append(_step(world, player_id, "learn martial", Expect(contains=("学会了",))))
    skills = world.require_component(player_id, SkillLevels)
    steps.append(assert_step("(assert) luohan_quan", "luohan_quan" in skills.levels))
    exp_before = skills.levels["luohan_quan"].exp
    practice = execute_line(world, player_id, "practice luohan_quan")
    exp_after = world.require_component(player_id, SkillLevels).levels["luohan_quan"].exp
    ok_p, detail_p = check(practice, Expect(any_of=("经验", "升到了")))
    steps.append(
        StepResult(
            line="practice luohan_quan",
            messages=practice,
            ok=ok_p and (exp_after > exp_before or any("升到了" in line for line in practice)),
            detail=detail_p,
        )
    )

    return ScenarioResult(name="MVP 全程旅程", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [_scenario_full_journey()]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
