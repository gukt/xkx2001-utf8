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
FUNC_DIST_PATH = Path(__file__).resolve().parents[1] / "output" / "func_dist.json"

# 类比基准（ADR-0048 决策 4）：调研 3 个 high-tier 数据点（分钟）
BENCHMARK_HIGH_TIER_MIN = [190, 120, 130]  # xue.c:main / do_check_menpai_job / do_qingjiao

# pending 层规模 fallback（func_dist.json 未生成时用）。
# 真值由 load_layer_sizes() 从 func_dist.json status_kind_tier 读（scan 重跑可复现）。
LAYER_SIZES: dict[str, int] = {
    "pending/logic/high": 21,
    "pending/logic/mid": 186,
    "pending/logic/low": 872,
    "pending/data/mid": 5,
    "pending/data/low": 75,
}


def load_layer_sizes() -> dict[str, int]:
    """从 func_dist.json status_kind_tier 读 pending 层规模（可复现）。

    func_dist 未生成时 fallback 到 LAYER_SIZES 常量。
    纠偏改分类后重跑 scan 即刷新层规模（ADR-0048 决策 3）。
    """
    if not FUNC_DIST_PATH.exists():
        return dict(LAYER_SIZES)
    fd = json.loads(FUNC_DIST_PATH.read_text(encoding="utf-8"))
    skt = fd.get("status_kind_tier", {})
    return {k: v for k, v in skt.items() if k.startswith("pending/")}


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
    """分层（effective_status × effective_kind × tier）均值 × 层规模 -> 分层点估。

    implemented 层仅记偏差，不计入全量迁移工时外推。
    层规模从 func_dist.json 读（load_layer_sizes），pilot 样本不足的层 mean=0。
    """
    sizes = load_layer_sizes()
    by_stratum: dict[str, list[EffortRecord]] = {}
    for r in records:
        by_stratum.setdefault(r.stratum, []).append(r)
    result: dict[str, dict] = {}
    for stratum, recs in by_stratum.items():
        efforts = [r.effort.subtotal for r in recs]
        mean = sum(efforts) / len(efforts) if efforts else 0.0
        size = sizes.get(stratum, 0)
        result[stratum] = {
            "mean_min": mean,
            "n": len(recs),
            "size": size,
            "total_min": mean * size,
        }
    return result


def interval_commitment(records: list[EffortRecord]) -> dict:
    """区间承诺：点估 + 上下界（high-tier 变异 + 类比基准校准）。

    非窄 t 分布置信区间（ADR-0048 决策 1 降级）。外推只计 pending 层；
    implemented 层若 total>0 提示"已实现但有后置分支偏差"。
    展幅由 pilot high-tier 样本极值偏移推导（无 high-tier 样本时默认 30%）。
    """
    strat = stratified_estimate(records)
    pending_total = sum(
        v["total_min"] for k, v in strat.items() if k.startswith("pending/")
    )
    # implemented 层不外推（已实现），仅记实测工时和作为"后置分支偏差"提示
    implemented_drift = sum(
        r.effort.subtotal for r in records if r.effective_status == "implemented"
    )
    high_efforts = [
        r.effort.subtotal
        for r in records
        if r.tier == "high" and r.effective_status == "pending"
    ]
    if high_efforts:
        hmean = sum(high_efforts) / len(high_efforts)
        hmin, hmax = min(high_efforts), max(high_efforts)
        spread = max(
            (hmax / hmean - 1) if hmean else 0.0,
            (1 - hmin / hmean) if hmean else 0.0,
        )
    else:
        hmean = 0.0
        spread = 0.3
    benchmark_mean = sum(BENCHMARK_HIGH_TIER_MIN) / len(BENCHMARK_HIGH_TIER_MIN)
    lower = pending_total * (1 - spread)
    upper = pending_total * (1 + spread)
    return {
        "point_min": pending_total,
        "lower_min": lower,
        "upper_min": upper,
        "spread_pct": spread,
        "hours": {
            "point": pending_total / 60,
            "lower": lower / 60,
            "upper": upper / 60,
        },
        "benchmark_high_mean_min": benchmark_mean,
        "pilot_high_mean_min": hmean,
        "implemented_drift_min": implemented_drift,
        "by_stratum": strat,
    }


def main() -> None:
    recs = load_records()
    print(f"记录数: {len(recs)}")
    print(f"误分类率: {misclassification_rate(recs):.1%}")
    if recs:
        print(f"已测样本总工时: {sum(r.effort.subtotal for r in recs)} min")
    strat = stratified_estimate(recs)
    print("\n分层估计:")
    for stratum, v in sorted(strat.items()):
        print(
            f"  {stratum}: mean={v['mean_min']:.1f}min "
            f"n={v['n']} size={v['size']} total={v['total_min']:.0f}min"
        )
    commit = interval_commitment(recs)
    print("\n区间承诺（全量迁移工时）:")
    print(f"  点估: {commit['hours']['point']:.1f}h ({commit['point_min']:.0f}min)")
    print(
        f"  区间: [{commit['hours']['lower']:.1f}h, "
        f"{commit['hours']['upper']:.1f}h] (展幅 {commit['spread_pct']:.0%})"
    )
    print(
        f"  类比基准 high-tier 均值: {commit['benchmark_high_mean_min']:.0f}min | "
        f"pilot high-tier 均值: {commit['pilot_high_mean_min']:.0f}min"
    )
    if commit["implemented_drift_min"] > 0:
        print(
            f"  ⚠ implemented 层偏差工时: {commit['implemented_drift_min']:.0f}min"
            "（已实现但有后置分支未补）"
        )


if __name__ == "__main__":
    main()
