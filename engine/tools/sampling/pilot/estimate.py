"""pilot 区间承诺推算。

读 effort_records.jsonl -> 分层均值 × 层规模 + 类比基准 -> 全量迁移工时区间。
方法论见 ADR-0048 决策 4 + 17 §六.5。

非窄 t 分布置信区间（ADR-0048 决策 1 降级），输出点估 + 上下界区间。
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.sampling.pilot.schema import EffortMin, EffortRecord

RECORDS_PATH = Path(__file__).parent / "effort_records.jsonl"

# 类比基准（ADR-0048 决策 4）：调研 3 个 high-tier 数据点（分钟）
BENCHMARK_HIGH_TIER_MIN = [190, 120, 130]  # xue.c:main / do_check_menpai_job / do_qingjiao

# 全量层规模（func_dist.json pending：logic 1079 + data 80）。
# tier 交叉粗估，pilot 后按 corrected 回调。
LAYER_SIZES: dict[str, int] = {
    "pending/logic/high": 15,
    "pending/logic/mid": 25,
    "pending/logic/low": 18,
    "pending/data/low": 80,
}


def load_records() -> list[EffortRecord]:
    """读取所有工时记录。"""
    records: list[EffortRecord] = []
    if not RECORDS_PATH.exists():
        return records
    for line in RECORDS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        em = d.pop("effort", {})
        em.pop("subtotal", None)
        records.append(EffortRecord(**d, effort=EffortMin(**em)))
    return records


def misclassification_rate(records: list[EffortRecord]) -> float:
    """误分类率（回调 ADR-0047 阈值的定量触发，ADR-0048 决策 3）。"""
    if not records:
        return 0.0
    return sum(1 for r in records if r.misclassified) / len(records)


def stratified_estimate(records: list[EffortRecord]) -> dict[str, dict]:
    """分层（effective_status × effective_kind × tier）均值 × 层规模 -> 分层点估。"""
    # TODO(pilot): 按层聚合均值，乘 LAYER_SIZES，返回每层 {mean, n, size, total}
    raise NotImplementedError


def interval_commitment(records: list[EffortRecord]) -> dict:
    """区间承诺：点估 + 上下界（类比基准校准）。"""
    # TODO(pilot): 分层点估 + 类比基准校准 + 变异 derive 上下界
    raise NotImplementedError


def main() -> None:
    recs = load_records()
    print(f"记录数: {len(recs)}")
    print(f"误分类率: {misclassification_rate(recs):.1%}")
    if recs:
        print(f"已测样本总工时: {sum(r.effort.subtotal for r in recs)} min")
        # TODO(pilot): 打印分层估计 + 区间承诺


if __name__ == "__main__":
    main()
