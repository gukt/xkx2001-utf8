#!/usr/bin/env python3
"""M2 战斗能力面矩阵（MVP 场景）：交战 / flee / aggro / 击杀 / 战败复活。

用法（仓库根）::

    just verify-m2-combat

或::

    cd engine && uv run python scripts/verify_m2_combat.py

不读存档、不写存档；每次 ``load_mvp_scene()`` 加载 fresh MVP 场景。
"""

from __future__ import annotations

import sys

from verify_harness import (
    Expect,
    ScenarioResult,
    StepResult,
    advance_once,
    assert_step,
    check,
    main_from,
    move_to,
    room_by_key,
    run_lines,
)

from openmud.combat_system import attach_combat_system, clear_engagement
from openmud.components import Currency, Engaged, Identity, Position, Unconscious, Vitals
from openmud.death_flow import handle_vitals_depleted
from openmud.parsing import execute_line
from openmud.scenes import load_mvp_scene
from openmud.tick import TickLoop
from openmud.world import EntityId, World


def _npc_named(world: World, name: str, *, exclude: EntityId) -> EntityId:
    for entity in world.entities_with(Identity):
        if entity == exclude:
            continue
        if world.require_component(entity, Identity).name == name:
            return entity
    raise RuntimeError(f"{name!r} not found")


def _scenario_training_dummy() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    steps = run_lines(
        world,
        player_id,
        [
            ("go north", Expect(contains=("向导",))),
            ("go east", Expect(contains=("稻草人",))),
            ("attack 稻草人", Expect(contains=("交战",))),
        ],
    )
    dummy = _npc_named(world, "稻草人", exclude=player_id)
    before = world.require_component(dummy, Vitals).qi_current
    msgs = advance_once(world)
    after = world.require_component(dummy, Vitals).qi_current
    ok_dmg = after < before
    ok_msg, detail_msg = check(msgs, Expect(any_of=("气血", "稻草人")))
    steps.append(
        StepResult(
            line="(tick) 教学木桩回合",
            messages=msgs,
            ok=ok_dmg and ok_msg,
            detail="" if ok_dmg and ok_msg else f"qi {before}→{after}; {detail_msg}",
        )
    )
    return ScenarioResult(name="教学木桩交战", steps=steps)


def _scenario_flee() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    steps = run_lines(
        world,
        player_id,
        [
            ("flee", Expect(contains=("没有在交战",))),
            ("go north", None),
            ("go east", None),
            ("attack 稻草人", Expect(contains=("交战",))),
        ],
    )
    attach_combat_system(world)
    assert world.combat is not None
    world.combat.flee_success_chance = 1.0
    flee = execute_line(world, player_id, "flee")
    ok, detail = check(flee, Expect(contains=("成功脱离",)))
    steps.append(StepResult(line="flee", messages=flee, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 已脱离 Engaged",
            not world.has_component(player_id, Engaged),
        )
    )
    return ScenarioResult(name="flee 未交战 / 必成脱离", steps=steps)


def _scenario_aggro_and_kill() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "wild_forest")
    bandit = _npc_named(world, "山贼", exclude=player_id)
    steps: list[StepResult] = []

    msgs = advance_once(world)
    engaged = world.has_component(player_id, Engaged) or world.has_component(
        bandit, Engaged
    )
    if not world.has_component(player_id, Engaged):
        attack = execute_line(world, player_id, "attack 山贼")
        ok_a, detail_a = check(attack, Expect(contains=("交战",)))
        steps.append(StepResult(line="attack 山贼", messages=attack, ok=ok_a, detail=detail_a))
        engaged = True
    else:
        steps.append(
            StepResult(
                line="(tick) aggro 交战",
                messages=msgs,
                ok=engaged,
                detail="" if engaged else "山贼未建立交战",
            )
        )

    world.require_component(player_id, Vitals).qi_current = 200
    world.require_component(player_id, Vitals).qi_max = 200
    money_before = world.require_component(player_id, Currency).amount
    world.pending_messages.clear()
    for _ in range(50):
        if not world.has_component(bandit, Vitals):
            break
        if world.require_component(bandit, Vitals).qi_current <= 0:
            break
        TickLoop(lambda: None, world=world).advance()
    pending = list(world.pending_messages)
    money_after = world.require_component(player_id, Currency).amount
    dead = (not world.has_component(bandit, Vitals)) or (
        world.require_component(bandit, Vitals).qi_current <= 0
    )
    loot_ok = money_after > money_before or any(
        "打倒" in m or "银" in m or "经验" in m for m in pending
    )
    steps.append(
        assert_step(
            "(tick×N) 击杀山贼",
            dead and loot_ok,
            messages=pending[-8:] if pending else [f"money {money_before}→{money_after}"],
            detail=""
            if dead and loot_ok
            else f"dead={dead} money {money_before}→{money_after}",
        )
    )
    if world.has_component(player_id, Engaged):
        clear_engagement(world, player_id, reason="verify")
    return ScenarioResult(name="野外 aggro + 击杀", steps=steps)


def _scenario_defeat_revive() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "wild_forest")
    steps: list[StepResult] = []

    vitals = world.require_component(player_id, Vitals)
    vitals.qi_current = 0
    world.pending_messages.clear()
    handle_vitals_depleted(world, player_id)
    msgs1 = list(world.pending_messages)
    world.pending_messages.clear()
    ok_u = world.has_component(player_id, Unconscious)
    ok_msg, detail = check(msgs1, Expect(contains=("昏迷",)))
    steps.append(
        StepResult(
            line="(assert) 气血归零 → 昏迷",
            messages=msgs1,
            ok=ok_u and ok_msg,
            detail="" if ok_u and ok_msg else detail,
        )
    )

    handle_vitals_depleted(world, player_id)
    msgs2 = list(world.pending_messages)
    world.pending_messages.clear()
    ok_alive = not world.has_component(player_id, Unconscious)
    at_birth = world.require_component(player_id, Position).room == room_by_key(
        world, "huashan_birth"
    )
    ok_msg2, detail2 = check(msgs2, Expect(contains=("死而复生",)))
    qi_ok = world.require_component(player_id, Vitals).qi_current > 0
    steps.append(
        StepResult(
            line="(assert) 再归零 → 死而复生",
            messages=msgs2,
            ok=ok_alive and at_birth and ok_msg2 and qi_ok,
            detail=""
            if ok_alive and at_birth and ok_msg2 and qi_ok
            else f"{detail2}; birth={at_birth}",
        )
    )
    return ScenarioResult(name="战败昏迷复活", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_training_dummy(),
        _scenario_flee(),
        _scenario_aggro_and_kill(),
        _scenario_defeat_revive(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
