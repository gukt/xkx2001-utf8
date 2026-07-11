"""combat-sim：离线行为等价验证工具（ADR-0011 + ADR-0023 + T9）。

加载 ``CombatSnapshot`` + seed + input log -> ``replay`` -> ``ConformanceChecker``
8 项检查。greenfield 主门禁（[04](../../../docs/xkx-arch/04-迁移路径与避坑清单.md)
§三阶段 1 M1-9），不依赖运行 LPC。

T9 验收（[12](../../../docs/xkx-arch/12-阶段1-核心循环实施计划.md) T9）：
- combat-sim 重放结果与规格一致（同 snapshot+seed+input_log -> 同输出）
- impl_map 三状态（implemented/simplified/postponed）自动区分
- 无 violation（行为等价验证通过）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from xkx.combat.conformance import ConformanceReport, check_conformance
from xkx.combat.replay import CombatSnapshot, InputEntry, replay_with_context
from xkx.spec.impl_map import DO_ATTACK_IMPL_MAP, ImplStatus


class RoundReport(BaseModel):
    """单回合符合性报告。"""

    round_index: int
    conformance: ConformanceReport


class CombatSimReport(BaseModel):
    """combat-sim 完整运行报告。"""

    total_rounds: int = 0
    total_violations: int = 0
    round_reports: list[RoundReport] = Field(default_factory=list)
    impl_status_summary: dict[str, int] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """行为等价验证通过（无 violation）。"""
        return self.total_violations == 0

    @property
    def passed_checks(self) -> int:
        """所有回合累计的 passed 检查数。"""
        return sum(len(r.conformance.passed) for r in self.round_reports)


def summarize_impl_status() -> dict[str, int]:
    """汇总 impl_map 三状态统计（implemented/simplified/postponed）。"""
    counts: dict[str, int] = {
        ImplStatus.IMPLEMENTED.value: 0,
        ImplStatus.SIMPLIFIED.value: 0,
        ImplStatus.POSTPONED.value: 0,
    }
    for entry in DO_ATTACK_IMPL_MAP.values():
        counts[entry.status.value] = counts.get(entry.status.value, 0) + 1
    return counts


def run_combat_sim(
    snapshot: CombatSnapshot,
    seed: int,
    input_log: list[InputEntry],
) -> CombatSimReport:
    """运行 combat-sim：replay + ConformanceChecker 8 项检查。

    greenfield 主门禁（M1-9）：combat-sim 调 resolve_attack 纯函数重放，
    ConformanceChecker 8 项检查无 violation 则行为等价验证通过。

    重放不依赖运行时 ECS（ADR-0023 决策 2），只依赖快照 + seed + input log。
    """
    pairs = replay_with_context(snapshot, seed, input_log)
    round_reports: list[RoundReport] = []
    total_violations = 0
    for i, (ctx, result) in enumerate(pairs):
        report = check_conformance(ctx, result)
        round_reports.append(RoundReport(round_index=i, conformance=report))
        total_violations += len(report.violations)
    return CombatSimReport(
        total_rounds=len(pairs),
        total_violations=total_violations,
        round_reports=round_reports,
        impl_status_summary=summarize_impl_status(),
    )


# ---------------------------------------------------------------------------
# JSON 序列化辅助（combat-sim 离线工具加载/保存战报用）
# ---------------------------------------------------------------------------


def snapshot_to_json(snapshot: CombatSnapshot) -> str:
    """CombatSnapshot 序列化为 JSON 字符串。"""
    return snapshot.model_dump_json()


def snapshot_from_json(json_str: str) -> CombatSnapshot:
    """从 JSON 字符串加载 CombatSnapshot。"""
    return CombatSnapshot.model_validate_json(json_str)


def input_log_to_json(input_log: list[InputEntry]) -> str:
    """input log 序列化为 JSON 字符串。"""
    return json.dumps([e.model_dump() for e in input_log], ensure_ascii=False)


def input_log_from_json(json_str: str) -> list[InputEntry]:
    """从 JSON 字符串加载 input log。"""
    return [InputEntry.model_validate(d) for d in json.loads(json_str)]


# ---------------------------------------------------------------------------
# CLI 入口（python -m xkx.combat.combat_sim <snapshot.json> <input_log.json> [seed]）
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """combat-sim CLI：加载战报文件 -> 重放 -> 打印报告。

    退出码：0=通过（无 violation）/ 1=参数错误 / 2=行为等价验证失败。
    """
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(
            "用法: python -m xkx.combat.combat_sim "
            "<snapshot.json> <input_log.json> [seed]"
        )
        return 1
    snapshot = snapshot_from_json(Path(args[0]).read_text(encoding="utf-8"))
    input_log = input_log_from_json(Path(args[1]).read_text(encoding="utf-8"))
    seed = int(args[2]) if len(args) > 2 else 0
    report = run_combat_sim(snapshot, seed, input_log)
    print(f"combat-sim 报告：{report.total_rounds} 回合，{report.total_violations} 违规")
    print(f"impl_map 状态：{report.impl_status_summary}")
    if report.ok:
        print("✓ 行为等价验证通过（无 violation）")
        return 0
    print("✗ 行为等价验证失败（有 violation）")
    for r in report.round_reports:
        for v in r.conformance.violations:
            print(f"  回合 {r.round_index} {v.check_name}: {v.detail}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
