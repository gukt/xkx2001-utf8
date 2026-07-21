"""Verify 脚本共用薄壳：Expect / 步骤跑通 / 转录报告 / 常用 seam。

M1 ``verify_m1_*.py`` 与 M2 ``verify_m2_*.py`` 共用，避免每份脚本复制
``Expect`` / ``print_report`` / tick 推进样板。不含场景内容与能力断言。
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from mud_engine.components import Exits, Position
from mud_engine.parsing import execute_line
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


@dataclass(frozen=True)
class Expect:
    """对单条命令输出的期望（子串匹配）。"""

    contains: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()  # 至少命中其一
    absent: tuple[str, ...] = ()  # 合并输出中不得出现


@dataclass
class StepResult:
    line: str
    messages: list[str]
    ok: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


def check(messages: list[str], expect: Expect | None) -> tuple[bool, str]:
    if expect is None:
        return True, ""
    combined = "\n".join(messages)
    for needle in expect.contains:
        if needle not in combined:
            return False, f"缺少期望子串：{needle!r}"
    if expect.any_of and not any(n in combined for n in expect.any_of):
        return False, f"未命中任一期望：{expect.any_of!r}"
    for needle in expect.absent:
        if needle in combined:
            return False, f"不应出现子串：{needle!r}"
    return True, ""


def run_lines(
    world: World,
    player_id: EntityId,
    steps: list[tuple[str, Expect | None]],
) -> list[StepResult]:
    results: list[StepResult] = []
    for line, expect in steps:
        messages = execute_line(world, player_id, line)
        ok, detail = check(messages, expect)
        results.append(StepResult(line=line, messages=messages, ok=ok, detail=detail))
    return results


def assert_step(
    line: str,
    ok: bool,
    *,
    messages: list[str] | None = None,
    detail: str = "",
) -> StepResult:
    """非命令串步骤（组件断言 / tick 结果）统一成 StepResult。"""
    return StepResult(
        line=line,
        messages=messages if messages is not None else [str(ok)],
        ok=ok,
        detail=detail,
    )


def advance_once(world: World) -> list[str]:
    """推进一拍并返回（并清空）pending_messages。"""
    world.pending_messages.clear()
    TickLoop(save_fn=lambda: None, world=world, interval=100).advance()
    messages = list(world.pending_messages)
    world.pending_messages.clear()
    return messages


def room_by_key(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def move_to(world: World, player_id: EntityId, key: str) -> None:
    world.require_component(player_id, Position).room = room_by_key(world, key)


def wait_ferry_across(world: World, dock_key: str, *, ticks: int = 8) -> list[str]:
    """等到渡口出现 across 出口；返回等待期间累计的 pending 消息。"""
    dock = room_by_key(world, dock_key)
    exits = world.require_component(dock, Exits)
    if "across" in exits.by_direction:
        return []
    collected: list[str] = []
    for _ in range(ticks):
        collected.extend(advance_once(world))
        exits = world.require_component(dock, Exits)
        if "across" in exits.by_direction:
            return collected
    raise RuntimeError(f"ferry across never appeared at {dock_key}")


def use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def step_mark(ok: bool) -> str:
    if ok:
        return "\033[32m✔\033[0m" if use_color() else "✔"
    return "\033[31m✖\033[0m" if use_color() else "✖"


def scenario_mark(ok: bool) -> str:
    return step_mark(ok)


def print_report(scenarios: list[ScenarioResult]) -> int:
    for sc in scenarios:
        print(f"\n=== {sc.name} ===")
        for step in sc.steps:
            print(f"> {step.line}  {step_mark(step.ok)}")
            for m in step.messages:
                print(f"  {m}")
            if step.detail:
                print(f"  !! {step.detail}")

    print("\n── 摘要 ──")
    for sc in scenarios:
        print(f"  {scenario_mark(sc.ok)} {sc.name}")
    total_fail_steps = sum(1 for sc in scenarios for s in sc.steps if not s.ok)
    n_ok = sum(1 for sc in scenarios if sc.ok)
    print(f"  场景 {n_ok}/{len(scenarios)} 通过；失败步骤 {total_fail_steps}")
    return 0 if total_fail_steps == 0 else 1


def main_from(all_scenarios: Callable[[], list[ScenarioResult]]) -> int:
    return print_report(all_scenarios())
