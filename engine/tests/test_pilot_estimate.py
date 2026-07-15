"""pilot estimate 推算单测：分层估计 + 区间承诺 + 层规模读取。

方法论见 ADR-0048 决策 4 + 17 §六.5。守 greenfield 工时语义（ADR-0047 决策 1）：
外推只计 pending 层，implemented 层仅记偏差工时、不外推。
"""

from __future__ import annotations

import pytest
from tools.sampling.pilot.estimate import (
    interval_commitment,
    load_layer_sizes,
    misclassification_rate,
    stratified_estimate,
)
from tools.sampling.pilot.schema import EffortMin, EffortRecord


def _rec(
    file: str,
    func: str,
    status: str,
    func_kind: str,
    tier: str,
    effort_min: int,
    *,
    call_count: int = 10,
    corrected_status: str = "",
    corrected_kind: str = "",
    misclassified: bool = False,
    subsystem: str = "cmds",
) -> EffortRecord:
    return EffortRecord(
        file=file,
        func=func,
        subsystem=subsystem,
        status=status,
        func_kind=func_kind,
        tier=tier,
        call_count=call_count,
        corrected_status=corrected_status,
        corrected_kind=corrected_kind,
        misclassified=misclassified,
        effort=EffortMin(read_spec=effort_min),
    )


def test_load_layer_sizes_reads_func_dist() -> None:
    sizes = load_layer_sizes()
    assert sizes["pending/logic/high"] == 21
    assert sizes["pending/logic/mid"] == 186
    assert sizes["pending/logic/low"] == 872
    assert sizes["pending/data/low"] == 75
    assert sum(sizes.values()) == 1159
    # 仅 pending 层纳入外推（implemented 不外推）
    assert all(k.startswith("pending/") for k in sizes)


def test_stratified_estimate_mean_times_size() -> None:
    recs = [
        _rec("a.c", "f1", "pending", "logic", "high", 120),
        _rec("b.c", "f2", "pending", "logic", "high", 180),
    ]
    strat = stratified_estimate(recs)
    s = strat["pending/logic/high"]
    assert s["n"] == 2
    assert s["mean_min"] == 150.0
    assert s["size"] == 21
    assert s["total_min"] == 150.0 * 21


def test_interval_commitment_point_and_bounds() -> None:
    recs = [
        _rec("a.c", "f1", "pending", "logic", "high", 120),
        _rec("b.c", "f2", "pending", "logic", "high", 180),
    ]
    commit = interval_commitment(recs)
    # 点估 = 均值 150 × 层规模 21 = 3150 min
    assert commit["point_min"] == 3150.0
    assert commit["pilot_high_mean_min"] == 150.0
    assert commit["benchmark_high_mean_min"] == pytest.approx(440 / 3)
    # 展幅 = max(180/150-1, 1-120/150) = 0.2
    assert commit["spread_pct"] == pytest.approx(0.2)
    assert commit["lower_min"] == pytest.approx(3150 * 0.8)
    assert commit["upper_min"] == pytest.approx(3150 * 1.2)
    assert commit["implemented_drift_min"] == 0


def test_interval_commitment_implemented_drift_not_extrapolated() -> None:
    recs = [
        _rec("a.c", "f1", "implemented", "logic", "high", 7),  # 后置分支偏差
        _rec("b.c", "f2", "pending", "logic", "high", 120),
    ]
    commit = interval_commitment(recs)
    # implemented 偏差记实测工时和（7min），不计入全量外推
    assert commit["implemented_drift_min"] == 7
    # pending 点估只含 pending 层：120 × 21
    assert commit["point_min"] == 120 * 21


def test_interval_commitment_no_high_tier_default_spread() -> None:
    # 无 pending high-tier 样本 -> 默认 30% 展幅
    recs = [_rec("c.c", "f3", "pending", "logic", "mid", 40)]
    commit = interval_commitment(recs)
    assert commit["spread_pct"] == 0.3
    assert commit["pilot_high_mean_min"] == 0.0


def test_corrected_kind_changes_stratum() -> None:
    # 误分类纠偏：原 data 实为 logic，corrected_kind 后进入 logic 层
    recs = [
        _rec(
            "s.c", "init", "pending", "data", "low", 40,
            corrected_kind="logic", misclassified=True,
        ),
    ]
    strat = stratified_estimate(recs)
    assert "pending/logic/low" in strat
    assert "pending/data/low" not in strat


def test_misclassification_rate() -> None:
    recs = [
        _rec("a.c", "f1", "pending", "logic", "high", 120, misclassified=False),
        _rec("b.c", "f2", "pending", "logic", "high", 180, misclassified=True),
        _rec("c.c", "f3", "pending", "data", "low", 40, misclassified=True),
        _rec("d.c", "f4", "pending", "data", "low", 10, misclassified=False),
    ]
    assert misclassification_rate(recs) == 0.5


def test_empty_records_graceful() -> None:
    commit = interval_commitment([])
    assert commit["point_min"] == 0
    assert commit["spread_pct"] == 0.3
    assert commit["implemented_drift_min"] == 0
    assert misclassification_rate([]) == 0.0
