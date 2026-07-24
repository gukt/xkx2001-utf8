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

import sys

from verify_harness import Expect, ScenarioResult, main_from, run_lines

from openmud.scenes import build_world

ENTER_STORAGE = (
    ("open south", Expect(contains=("打开",))),
    ("s", Expect(contains=("储藏室",))),
)


def _scenario(name: str, steps: list[tuple[str, Expect | None]]) -> ScenarioResult:
    world, player_id = build_world()
    return ScenarioResult(name=name, steps=run_lines(world, player_id, steps))


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


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
