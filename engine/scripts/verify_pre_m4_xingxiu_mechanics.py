#!/usr/bin/env python3
"""Pre-M4 房间钩子 / 星宿机制：``xingxiu_mechanics`` 十类机关 S3 矩阵（给人看的转录）。

正式门禁仍以 ``tests/test_xingxiu_mechanics_02``–``10`` / ``test_xingxiu_mechanics_closeout``
为准；本脚本侧重全局观察。UGC 禁 hooks 见 ``test_room_hooks.TestUgcRejectsHooksS2``。

用法（仓库根）::

    just verify-xingxiu

或::

    cd engine && uv run python scripts/verify_pre_m4_xingxiu_mechanics.py

不读存档、不写存档；每场景 ``load_xingxiu_mechanics()`` 加载 fresh 切片。
"""

from __future__ import annotations

import random
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

from openmud.combat_system import attach_combat_system
from openmud.components import (
    BaseAttributes,
    Engaged,
    Exits,
    NpcSpawnMeta,
    Position,
    Vitals,
)
from openmud.parsing import execute_line
from openmud.scenes import load_xingxiu_mechanics
from openmud.tick import TickLoop
from openmud.world import EntityId, World


def _force_phase(world: World, name: str) -> None:
    assert world.nature is not None
    world.nature.seek_phase(name)


def _go_with_mailbox(world: World, player_id: EntityId, line: str) -> list[str]:
    """``go`` 回文是 look；进房钩子播报在收件箱——合并两者便于转录断言。"""
    msgs = execute_line(world, player_id, line)
    return [*msgs, *world.drain_messages(player_id)]


def _npc_in_room(world: World, room: EntityId, template_key: str) -> EntityId | None:
    for entity in world.entities_in_room(room):
        meta = world.get_component(entity, NpcSpawnMeta)
        if meta is not None and meta.template_key == template_key:
            return entity
    return None


def _arm_combatant(world: World, entity: EntityId, *, dex: int = 0) -> None:
    if world.get_component(entity, Vitals) is None:
        world.add_component(
            entity,
            Vitals(
                qi_current=100,
                qi_max=100,
                neili_current=50,
                neili_max=50,
                jingli_current=50,
                jingli_max=50,
            ),
        )
    if world.get_component(entity, BaseAttributes) is None:
        world.add_component(entity, BaseAttributes(str_=10, con=10, dex=dex, int_=10))


def _scenario_dig_collapse() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    move_to(world, player_id, "dig_peak")
    steps = run_lines(
        world,
        player_id,
        [
            ("dig", Expect(contains=("洞口",))),
            ("go north", Expect(any_of=("临时洞府", "洞"))),
        ],
    )
    steps.append(
        assert_step(
            "(assert) 抵达临时洞府",
            world.require_component(player_id, Position).room
            == world.room_ids["dig_cave"],
        )
    )
    steps.extend(run_lines(world, player_id, [("go south", Expect(contains=("白玉峰",)))]))
    peak = world.room_ids["dig_peak"]
    loop = TickLoop(lambda: None, world=world, interval=100)
    ttl = 3
    for i in range(ttl):
        loop.advance()
        still_open = "north" in world.require_component(peak, Exits).by_direction
        steps.append(
            assert_step(
                f"(tick {i + 1}) north 出口{'仍在' if still_open else '已崩'}",
                still_open == (i + 1 < ttl),
            )
        )
    steps.extend(
        run_lines(
            world,
            player_id,
            [("go north", Expect(contains=("没有出口",)))],
        )
    )
    return ScenarioResult(name="① dig_collapse 挖洞+时限崩塌", steps=steps)


def _scenario_random_of() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    steps = run_lines(
        world,
        player_id,
        [
            ("go east", Expect(contains=("岔路",))),
            ("go north", Expect(absent=("没有出口",))),
        ],
    )
    dest = world.require_component(player_id, Position).room
    left = world.room_ids["fork_left"]
    right = world.room_ids["fork_right"]
    steps.append(
        assert_step(
            "(assert) 岔路落在左或右",
            dest in (left, right),
            messages=[f"dest={dest}"],
        )
    )
    steps.extend(run_lines(world, player_id, [("go south", Expect(contains=("岔路",)))]))
    again = execute_line(world, player_id, "go north")
    ok, detail = check(again, Expect(absent=("没有出口",)))
    steps.append(StepResult(line="go north (同次运行复走)", messages=again, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 同次运行岔路稳定",
            world.require_component(player_id, Position).room == dest,
        )
    )
    return ScenarioResult(name="② random_of 加载期岔路", steps=steps)


def _scenario_multi_step_gate() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    steps = run_lines(
        world,
        player_id,
        [
            ("go west", Expect(contains=("玉石",))),
            ("push", Expect(any_of=("先", "步骤", "顺序"))),
            ("刮锈", Expect(any_of=("锈", "刮"))),
            ("拔斧", Expect(any_of=("斧", "拔"))),
            ("推门", Expect(any_of=("门", "开"))),
            ("go north", Expect(any_of=("玉室",))),
        ],
    )
    steps.append(
        assert_step(
            "(assert) 抵达玉室",
            world.require_component(player_id, Position).room
            == world.room_ids["jade_chamber"],
        )
    )
    return ScenarioResult(name="③ multi_step_gate 刮锈→拔斧→推门", steps=steps)


def _scenario_lost_in_maze() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    maze = world.room_ids["desert_maze"]
    steps = run_lines(
        world,
        player_id,
        [
            ("go south", Expect(contains=("沙漠",))),
            ("go north", Expect(contains=("峰脚",))),  # 非 escape 方向可走
            ("go south", Expect(contains=("沙漠",))),
        ],
    )
    for i in range(3):
        msgs = execute_line(world, player_id, "go south")
        ok_stay = world.require_component(player_id, Position).room == maze
        ok_msg, detail = check(msgs, Expect(any_of=("迷", "方向", "走")))
        steps.append(
            StepResult(
                line=f"go south (迷途拒 {i + 1}/3)",
                messages=msgs,
                ok=ok_stay and ok_msg,
                detail=detail if not ok_msg else ("" if ok_stay else "未留在沙漠"),
            )
        )
    escape = execute_line(world, player_id, "go south")
    ok, detail = check(escape, Expect(absent=("迷",)))
    steps.append(StepResult(line="go south (达步数放行)", messages=escape, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 抵达沙漠边缘",
            world.require_component(player_id, Position).room
            == world.room_ids["desert_edge"],
        )
    )
    return ScenarioResult(name="④ lost_in_maze 步数迷途", steps=steps)


def _scenario_skill_gate() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    # 切片玩家 dodge:50，刚好过 jump(50) 与 climb(30)
    steps = run_lines(
        world,
        player_id,
        [
            ("go northeast", Expect(contains=("峭壁",))),
            ("jump", Expect(any_of=("跃", "跳", "过去"))),
        ],
    )
    steps.append(
        assert_step(
            "(assert) jump 抵达涧对岸",
            world.require_component(player_id, Position).room
            == world.room_ids["cliff_far"],
        )
    )
    move_to(world, player_id, "dig_base")
    steps.extend(
        run_lines(
            world,
            player_id,
            [
                ("go southeast", Expect(contains=("崖底",))),
                ("climb", Expect(any_of=("爬", "攀", "过去"))),
            ],
        )
    )
    steps.append(
        assert_step(
            "(assert) climb 抵达崖顶",
            world.require_component(player_id, Position).room
            == world.room_ids["cliff_top"],
        )
    )
    return ScenarioResult(name="⑤ skill_gate jump/climb", steps=steps)


def _scenario_time_of_day_passage() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    _force_phase(world, "day")
    enter = _go_with_mailbox(world, player_id, "go northwest")
    ok, detail = check(enter, Expect(any_of=("日光", "玉室")))
    steps = [
        StepResult(line="go northwest (白天)", messages=enter, ok=ok, detail=detail),
    ]
    steps.extend(
        run_lines(
            world,
            player_id,
            [
                ("look", Expect(any_of=("秘道", "north", "北"))),
                ("go north", Expect(any_of=("秘道",))),
            ],
        )
    )
    steps.append(
        assert_step(
            "(assert) 白天走入秘道",
            world.require_component(player_id, Position).room
            == world.room_ids["secret_tunnel"],
        )
    )
    return ScenarioResult(name="⑥ time_of_day_passage 日间秘道", steps=steps)


def _scenario_magnetic_iron() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    # 房间 long 本身含「吸」字；钩子播报特征是「磁力将你」/「牢牢吸住」
    _hook_msg = ("磁力将你", "牢牢吸住")
    empty = _go_with_mailbox(world, player_id, "go southwest")
    steps = [
        assert_step(
            "(assert) 空手进厅无钩子磁力播报",
            not any(frag in m for m in empty for frag in _hook_msg),
            messages=empty,
        )
    ]
    steps.extend(
        run_lines(
            world,
            player_id,
            [
                ("go northeast", Expect(contains=("峰脚",))),
                ("get 铁剑", Expect(contains=("拿起",))),
            ],
        )
    )
    world.drain_messages(player_id)
    with_iron = _go_with_mailbox(world, player_id, "go southwest")
    ok, detail = check(with_iron, Expect(any_of=_hook_msg))
    steps.append(
        StepResult(line="go southwest (携铁)", messages=with_iron, ok=ok, detail=detail)
    )
    return ScenarioResult(name="⑦ magnetic_iron 磁力吸铁", steps=steps)


def _scenario_bandit_ambush() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    ambush = world.room_ids["ambush_trail"]
    # C12：须先持有达阈值贵重物（峰脚铁剑 value=100）才触发刷怪
    get_msgs = execute_line(world, player_id, "get 铁剑")
    enter = _go_with_mailbox(world, player_id, "go path")
    ok, detail = check(enter, Expect(any_of=("劫匪", "拦")))
    steps = [
        StepResult(line="get 铁剑", messages=get_msgs, ok=True, detail="ok"),
        StepResult(line="go path", messages=enter, ok=ok, detail=detail),
        assert_step(
            "(assert) 劫匪已生成",
            _npc_in_room(world, ambush, "road_bandit") is not None,
        ),
    ]
    blocked = execute_line(world, player_id, "go north")
    ok_b, detail_b = check(blocked, Expect(contains=("挡",)))
    steps.append(StepResult(line="go north (被挡)", messages=blocked, ok=ok_b, detail=detail_b))
    npc = _npc_in_room(world, ambush, "road_bandit")
    assert npc is not None
    world.destroy_entity(npc)
    steps.append(assert_step("(assert) 击退劫匪（destroy）", True, messages=["ok"]))
    steps.extend(
        run_lines(
            world,
            player_id,
            [("go north", Expect(any_of=("尽头", "空地")))],
        )
    )
    steps.append(
        assert_step(
            "(assert) 抵达小径尽头",
            world.require_component(player_id, Position).room
            == world.room_ids["ambush_end"],
        )
    )
    return ScenarioResult(name="⑧ bandit_ambush 劫匪刷拦", steps=steps)


def _scenario_kill_order() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    enter = _go_with_mailbox(world, player_id, "go cave")
    ok, detail = check(enter, Expect(any_of=("杀令", "杀气", "敌意")))
    steps = [
        StepResult(line="go cave", messages=enter, ok=ok, detail=detail),
        assert_step(
            "(assert) 少林进洞触发交战",
            world.has_component(player_id, Engaged),
        ),
    ]
    return ScenarioResult(name="⑨ kill_order 杀令介入", steps=steps)


def _scenario_silk_rope() -> ScenarioResult:
    world, capturer = load_xingxiu_mechanics()
    yard = world.room_ids["silk_yard"]
    prison = world.room_ids["silk_prison"]
    move_to(world, capturer, "silk_yard")
    victim = world.spawn_player_session(name="乙", room=yard)
    _arm_combatant(world, victim, dex=0)
    # 固定 RNG，保证命中走 silk_rope 招式
    attach_combat_system(world, rng=random.Random(42))
    engage = execute_line(world, capturer, "attack 乙")
    ok, detail = check(engage, Expect(contains=("交战",)))
    steps = [
        StepResult(line="attack 乙", messages=engage, ok=ok, detail=detail),
    ]
    TickLoop(lambda: None, world=world, interval=100).advance()
    drained = world.drain_messages(capturer) + world.drain_messages(victim)
    steps.append(
        assert_step(
            "(tick) 柔丝索捕获",
            world.require_component(victim, Position).room == prison
            and world.require_component(capturer, Position).room == yard,
            messages=drained or ["(无额外播报)"],
        )
    )
    return ScenarioResult(name="⑩ silk_rope 跨玩家捕获", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_dig_collapse(),
        _scenario_random_of(),
        _scenario_multi_step_gate(),
        _scenario_lost_in_maze(),
        _scenario_skill_gate(),
        _scenario_time_of_day_passage(),
        _scenario_magnetic_iron(),
        _scenario_bandit_ambush(),
        _scenario_kill_order(),
        _scenario_silk_rope(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
