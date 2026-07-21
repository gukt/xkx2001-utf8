#!/usr/bin/env python3
"""M1 NPC 命令/行为矩阵（默认场景）：一键跑通并打印转录 + PASS/FAIL 摘要。

用法（仓库根）::

    just verify-npc

或::

    cd engine && uv run python scripts/verify_m1_npc.py

不读存档、不写存档；每次 ``build_world()`` 加载 fresh 默认场景。
手测步骤见 ``.scratch/m1-core-engine-skeleton/verify-npc-cli.md``。

Chatter / Spawn 组走 ``TickLoop.advance`` seam（非纯命令串），与
``tests/test_npc_extension.py`` 一致。
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
    run_lines,
)

from mud_engine.components import AIController, Identity, NpcSpawnMeta, Position
from mud_engine.scenes import build_world
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


class _AlwaysSpeakRng:
    """确定性 rng：random() 恒 0（必触发），choice 取首条。"""

    def random(self) -> float:
        return 0.0

    def choice(self, seq):  # noqa: ANN001
        return seq[0]


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


def _npcs_named(world: World, name: str) -> list[EntityId]:
    return [
        e
        for e in world.entities_with(Identity)
        if world.require_component(e, Identity).name == name
    ]


def _scenario_commands(name: str, steps: list[tuple[str, Expect | None]]) -> ScenarioResult:
    world, player_id = build_world()
    return ScenarioResult(name=name, steps=run_lines(world, player_id, steps))


def _scenario_look_and_spawn() -> ScenarioResult:
    """look 在场 + count=2 实例 + 石像无 AIController。"""
    world, player_id = build_world()
    steps = run_lines(
        world,
        player_id,
        [
            (
                "look",
                Expect(
                    contains=(
                        "起始庭院",
                        "石像守卫",
                        "庭院闲人",
                        "夜猫子",
                        "巡逻兵",
                        "石头",
                    )
                ),
            ),
            ("get 石像守卫", Expect(contains=("这里没有", "石像守卫"))),
        ],
    )
    room = world.require_component(player_id, Position).room
    patrols = [
        e
        for e in _npcs_named(world, "巡逻兵")
        if world.require_component(e, Position).room == room
    ]
    ok_count = len(patrols) == 2
    meta_ok = False
    if patrols:
        meta = world.require_component(patrols[0], NpcSpawnMeta)
        meta_ok = meta.desired_count == 2 and meta.respawn is True
    detail_parts: list[str] = []
    if not ok_count:
        detail_parts.append(f"巡逻兵实例数={len(patrols)}，期望 2")
    if not meta_ok:
        detail_parts.append("NpcSpawnMeta.desired_count/respawn 不符")
    steps.append(
        assert_step(
            "(assert) patrol_pair count=2",
            ok_count and meta_ok,
            messages=[f"巡逻兵×{len(patrols)}"],
            detail="; ".join(detail_parts),
        )
    )
    guards = _npcs_named(world, "石像守卫")
    guard = guards[0] if guards else None
    no_ai = guard is not None and not world.has_component(guard, AIController)
    steps.append(
        assert_step(
            "(assert) stone_guard 无 AIController",
            no_ai,
            messages=["ok" if no_ai else "石像仍挂了 AIController"],
            detail="" if no_ai else "石像守卫不应挂 AIController",
        )
    )
    return ScenarioResult(name="look + spawn 地基", steps=steps)


def _scenario_ask() -> ScenarioResult:
    return _scenario_commands(
        "ask inquiry",
        [
            ("ask 石像守卫 about 天气", Expect(contains=("石像守卫说：", "晴朗"))),
            ("ask 守卫 about 天气", Expect(contains=("石像守卫说：",))),
            ("ask 石像守卫 about 武功", Expect(contains=("没有回答",))),
            ("ask 不存在的人 about 天气", Expect(contains=("没有",))),
            ("ask", Expect(contains=("用法",))),
            ("ask 巡逻兵 about 天气", Expect(contains=("不确定你指的是哪个", "巡逻兵"))),
            ("ask 庭院闲人 about 天气", Expect(contains=("不想和你说话",))),
        ],
    )


def _scenario_say() -> ScenarioResult:
    return _scenario_commands(
        "say 广播",
        [
            ("say 你好", Expect(contains=("你说：你好",))),
            ("say", Expect(contains=("用法",))),
            ("say   ", Expect(contains=("用法",))),
        ],
    )


def _scenario_chatter() -> ScenarioResult:
    """Tick 驱动 Chatter：无条件闲人说话；夜猫 day 静默 / night 开口；石像不闲聊。"""
    world, player_id = build_world()
    assert world.ai is not None
    world.ai.rng = _AlwaysSpeakRng()
    steps: list[StepResult] = []

    _set_phase(world, "day")
    msgs_day = advance_once(world)
    ok_gossip_day, detail_g = check(
        msgs_day, Expect(contains=("庭院闲人说：庭院真清静啊。",))
    )
    ok_owl_silent, detail_o = check(msgs_day, Expect(absent=("夜猫子说：",)))
    steps.append(
        StepResult(
            line="(tick) day：闲人说话",
            messages=msgs_day,
            ok=ok_gossip_day,
            detail=detail_g,
        )
    )
    steps.append(
        StepResult(
            line="(tick) day：夜猫静默",
            messages=msgs_day,
            ok=ok_owl_silent,
            detail=detail_o,
        )
    )

    _set_phase(world, "night")
    msgs_night = advance_once(world)
    ok_owl_night, detail_n = check(
        msgs_night, Expect(contains=("夜猫子说：夜深了，该歇歇了。",))
    )
    steps.append(
        StepResult(
            line="(tick) night：夜猫说话",
            messages=msgs_night,
            ok=ok_owl_night,
            detail=detail_n,
        )
    )

    _set_phase(world, "day")
    world.pending_messages.clear()
    loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
    for _ in range(5):
        loop.advance()
    combined = list(world.pending_messages)
    world.pending_messages.clear()
    ok_guard, detail_guard = check(combined, Expect(absent=("石像守卫说：",)))
    steps.append(
        StepResult(
            line="(tick×5) 石像不闲聊",
            messages=combined,
            ok=ok_guard,
            detail=detail_guard,
        )
    )

    before = len(_npcs_named(world, "巡逻兵"))
    interval = world.ai.spawn_scan_interval
    for _ in range(interval + 1):
        loop.advance()
    after = len(_npcs_named(world, "巡逻兵"))
    ok_spawn = before == after == 2
    steps.append(
        assert_step(
            "(tick) spawn 扫描空转",
            ok_spawn,
            messages=[f"巡逻兵 {before}→{after}"],
            detail="" if ok_spawn else f"实例数变化或非 2：{before}→{after}",
        )
    )
    _ = player_id
    return ScenarioResult(name="Chatter + spawn 扫描", steps=steps)


def _scenario_door_smoke() -> ScenarioResult:
    return _scenario_commands(
        "门钥匙回归",
        [
            ("n", Expect(contains=("长廊", "铁钥匙"))),
            ("get 铁钥匙", Expect(contains=("拿起", "铁钥匙"))),
            ("unlock north", Expect(contains=("解锁",))),
            ("open north", Expect(contains=("打开",))),
            ("n", Expect(contains=("静室",))),
        ],
    )


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_look_and_spawn(),
        _scenario_ask(),
        _scenario_say(),
        _scenario_chatter(),
        _scenario_door_smoke(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
