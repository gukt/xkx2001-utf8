"""benchmark 回归门禁：防 resolve_attack 性能严重退化。

见 [ADR-0012](../../docs/adr/ADR-0012-performance-microbenchmark.md) 决策 6。宽松阈值
（非精确基准），精确基准由 [tools/benchmark.py](../tools/benchmark.py) 本地跑。
"""

from __future__ import annotations

import gc
import timeit
import tracemalloc
from statistics import median

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import RESULT_DODGE, RESULT_HIT, RESULT_PARRY

N_PER_RUN = 200
REPEAT = 5

PERF_MEDIAN_THRESHOLD_US = 200  # ADR-0012 决策 6：4x 阈值余量防退化
ALLOCATION_THRESHOLD_BYTES = 100 * 1024  # 100KB（单次调用峰值上界）
GEN0_COLLECTIONS_THRESHOLD = 1000  # 5k 次调用 gen0 回收上界
GC_TEST_CALLS = 5000


def _attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1, name="甲",
        str_=20, dex_=15, int_=12, con_=14,
        combat_exp=2000, skills={"unarmed": 40},
        max_qi=600, qi=600, max_jingli=300, jingli=300,
    )


def _victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2, name="乙",
        str_=15, dex_=20, int_=12, con_=14,
        combat_exp=1500, skills={"dodge": 35, "parry": 30},
        max_qi=500, qi=500, max_jingli=280, jingli=280,
    )


def _ctx(seed: int) -> CombatContext:
    return CombatContext(attacker=_attacker(), victim=_victim(), seed=seed)


def _find_branch_seeds() -> dict[str, int]:
    code_to_name = {RESULT_HIT: "hit", RESULT_DODGE: "dodge", RESULT_PARRY: "parry"}
    found: dict[str, int] = {}
    for seed in range(10000):
        r = resolve_attack(_ctx(seed))
        name = code_to_name.get(r.result_code)
        if name and name not in found:
            found[name] = seed
        if len(found) == 3:
            break
    return found


def test_perf_regression_median_under_threshold() -> None:
    """三分支中位数 < 200us（ADR-0012 决策 6，4x 阈值余量防退化）。"""
    branches = _find_branch_seeds()
    for branch, seed in branches.items():
        ctx = _ctx(seed)
        glb = {"resolve_attack": resolve_attack, "ctx": ctx}
        per_call = [
            timeit.timeit("resolve_attack(ctx)", globals=glb, number=N_PER_RUN) / N_PER_RUN * 1e6
            for _ in range(REPEAT)
        ]
        med = median(per_call)
        assert med < PERF_MEDIAN_THRESHOLD_US, (
            f"{branch} median {med:.1f}us > {PERF_MEDIAN_THRESHOLD_US}us"
        )


def test_single_call_allocation_under_threshold() -> None:
    """单次调用内存峰值 < 100KB。"""
    ctx = _ctx(42)
    tracemalloc.start()
    resolve_attack(ctx)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < ALLOCATION_THRESHOLD_BYTES, f"peak {peak}B > {ALLOCATION_THRESHOLD_BYTES}B"


def test_gc_gen0_collections_low() -> None:
    """5k 次调用 gen0 回收 < 1000（宽松上界，验证 GC 压力小）。"""
    ctx = _ctx(42)
    gc.collect()
    before = gc.get_stats()[0]["collections"]
    for _ in range(GC_TEST_CALLS):
        resolve_attack(ctx)
    after = gc.get_stats()[0]["collections"]
    assert after - before < GEN0_COLLECTIONS_THRESHOLD, (
        f"gen0 collections {after - before} > {GEN0_COLLECTIONS_THRESHOLD}"
    )


def test_determinism_within_process() -> None:
    """同 seed 多次调用输出一致（combat 确定性基础）。"""
    ctx = _ctx(42)
    outputs = [resolve_attack(ctx).model_dump_json() for _ in range(100)]
    assert len(set(outputs)) == 1
