#!/usr/bin/env python3
"""M1 物品命令矩阵（默认场景）：一键跑通并打印转录 + PASS/FAIL 摘要。

用法（仓库根）::

    just verify-items

或::

    cd engine && uv run python scripts/verify_m1_items.py

不读存档、不写存档；每次 ``build_world()`` 加载 fresh 默认场景。
手测步骤见 ``.scratch/m1-core-engine-skeleton/verify-items-cli.md``。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world
from mud_engine.world import EntityId, World


@dataclass(frozen=True)
class Expect:
    """对单条命令输出的期望（子串匹配）。"""

    contains: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()  # 至少命中其一（用于拒绝类提示）


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


ENTER_STORAGE = (
    ("open south", Expect(contains=("打开",))),
    ("s", Expect(contains=("储藏室",))),
)


def _check(messages: list[str], expect: Expect | None) -> tuple[bool, str]:
    if expect is None:
        return True, ""
    combined = "\n".join(messages)
    for needle in expect.contains:
        if needle not in combined:
            return False, f"缺少期望子串：{needle!r}"
    if expect.any_of and not any(n in combined for n in expect.any_of):
        return False, f"未命中任一期望：{expect.any_of!r}"
    return True, ""


def _run_lines(
    world: World,
    player_id: EntityId,
    steps: list[tuple[str, Expect | None]],
) -> list[StepResult]:
    results: list[StepResult] = []
    for line, expect in steps:
        messages = execute_line(world, player_id, line)
        ok, detail = _check(messages, expect)
        results.append(StepResult(line=line, messages=messages, ok=ok, detail=detail))
    return results


def _scenario(name: str, steps: list[tuple[str, Expect | None]]) -> ScenarioResult:
    world, player_id = build_world()
    return ScenarioResult(name=name, steps=_run_lines(world, player_id, steps))


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario(
            "基线",
            [
                ("look", Expect(contains=("起始庭院", "石头"))),
                ("i", Expect(contains=("你什么都没带",))),
                ("get 石头", Expect(contains=("拿起", "石头"))),
                ("i", Expect(contains=("石头",))),
                ("drop 石头", Expect(contains=("放下", "石头"))),
                ("take 石头", Expect(contains=("拿起", "石头"))),
                ("drop 石头", Expect(contains=("放下", "石头"))),
            ],
        ),
        _scenario(
            "堆叠+容器+look",
            [
                *ENTER_STORAGE,
                ("look", Expect(contains=("铜钱", "木箱", "宝石"))),
                ("look 铜钱", Expect(contains=("数量：", "价值：", "重量："))),
                ("get 铜钱", Expect(contains=("拿起", "铜钱"))),
                ("i", Expect(contains=("铜钱×8",))),
                ("look 铜钱", Expect(contains=("数量：8",))),
                ("drop 铜钱 2", Expect(contains=("放下", "2"))),
                ("i", Expect(contains=("铜钱×6",))),
                ("get 铜钱 2", Expect(contains=("拿起", "2"))),
                ("get 宝石", Expect(contains=("拿起", "宝石"))),
                ("put 宝石 in 木箱", Expect(contains=("放进", "木箱"))),
                ("look 木箱", Expect(contains=("宝石",))),
                ("get 宝石 from 木箱", Expect(contains=("拿起", "宝石"))),
            ],
        ),
        _scenario(
            "标志",
            [
                *ENTER_STORAGE,
                ("get 石碑", Expect(contains=("拿不起来",))),
                ("get 令牌", Expect(contains=("拿起", "令牌"))),
                ("drop 令牌", Expect(contains=("任务物品", "不能丢弃"))),
                ("put 令牌 in 木箱", Expect(contains=("任务物品", "不能丢弃"))),
            ],
        ),
        _scenario(
            "容量重量",
            [
                *ENTER_STORAGE,
                ("get 宝石", Expect(contains=("拿起", "宝石"))),
                ("get 大石块", Expect(contains=("拿起", "大石块"))),
                ("put 大石块 in 小布袋", Expect(contains=("太重",))),
                ("put 宝石 in 小布袋", Expect(contains=("放进", "小布袋"))),
            ],
        ),
        _scenario(
            "get all / drop all",
            [
                *ENTER_STORAGE,
                ("get all", Expect(contains=("捡好了",))),
                ("i", Expect(contains=("令牌", "铜钱"))),
                ("drop all", Expect(contains=("放下了",))),
                ("i", Expect(contains=("令牌",))),
                ("look", Expect(contains=("石碑", "铜钱"))),
            ],
        ),
        _scenario(
            "门钥匙回归",
            [
                ("n", Expect(contains=("长廊", "铁钥匙"))),
                ("get 铁钥匙", Expect(contains=("拿起", "铁钥匙"))),
                ("unlock north", Expect(contains=("解锁",))),
                ("open north", Expect(contains=("打开",))),
                ("n", Expect(contains=("静室",))),
                ("look", Expect(contains=("静室",))),
            ],
        ),
    ]


def _use_color() -> bool:
    """终端且未强制无色时用 ANSI；无额外依赖。"""
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _step_mark(ok: bool) -> str:
    if ok:
        return f"\033[32m✔\033[0m" if _use_color() else "✔"
    return f"\033[31m✖\033[0m" if _use_color() else "✖"


def _scenario_mark(ok: bool) -> str:
    if ok:
        return f"\033[32m✔\033[0m" if _use_color() else "✔"
    return f"\033[31m✖\033[0m" if _use_color() else "✖"


def print_report(scenarios: list[ScenarioResult]) -> int:
    for sc in scenarios:
        print(f"\n=== {sc.name} ===")
        for step in sc.steps:
            print(f"> {step.line}  {_step_mark(step.ok)}")
            for m in step.messages:
                print(f"  {m}")
            if step.detail:
                print(f"  !! {step.detail}")

    print("\n── 摘要 ──")
    for sc in scenarios:
        print(f"  {_scenario_mark(sc.ok)} {sc.name}")
    total_fail_steps = sum(1 for sc in scenarios for s in sc.steps if not s.ok)
    n_ok = sum(1 for sc in scenarios if sc.ok)
    print(f"  场景 {n_ok}/{len(scenarios)} 通过；失败步骤 {total_fail_steps}")
    return 0 if total_fail_steps == 0 else 1


def main() -> int:
    return print_report(all_scenarios())


if __name__ == "__main__":
    sys.exit(main())
