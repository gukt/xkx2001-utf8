"""性能 micro-benchmark：resolve_attack μs + GC + PYTHONHASHSEED 验证。

见 [ADR-0012](../../docs/adr/ADR-0012-performance-microbenchmark.md)。阶段 0 任务 4
go/no-go 硬门禁的前置数据点。

用法::

    python tools/benchmark.py              # 跑全部基准
    python tools/benchmark.py --us         # 只跑 μs 基准
    python tools/benchmark.py --gc         # 只跑 GC 基准
    python tools/benchmark.py --hashseed   # 只跑 PYTHONHASHSEED 验证
    python tools/benchmark.py --seed-output 42  # 打印单次输出 JSON（内部用）
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import timeit
import tracemalloc
from pathlib import Path
from statistics import median

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from xkx.combat.context import CombatantSnapshot, CombatContext  # noqa: E402
from xkx.combat.resolve_attack import resolve_attack  # noqa: E402
from xkx.combat.result import RESULT_DODGE, RESULT_HIT, RESULT_PARRY  # noqa: E402

N_PER_RUN = 1000
REPEAT = 20
TOTAL_CALLS = N_PER_RUN * REPEAT

THRESHOLD_MEDIAN_US = 50
THRESHOLD_P99_US = 200


def _attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20, dex_=15, int_=12, con_=14,
        combat_exp=2000,
        skills={"unarmed": 40},
        max_qi=600, qi=600,
        max_jingli=300, jingli=300,
    )


def _victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=15, dex_=20, int_=12, con_=14,
        combat_exp=1500,
        skills={"dodge": 35, "parry": 30},
        max_qi=500, qi=500,
        max_jingli=280, jingli=280,
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


def _stats(per_call_us: list[float]) -> dict:
    s = sorted(per_call_us)
    n = len(s)
    return {
        "min_us": round(s[0], 2),
        "median_us": round(median(s), 2),
        "p99_us": round(s[min(int(n * 0.99), n - 1)], 2),
        "max_us": round(s[-1], 2),
    }


def _bench_branch(ctx: CombatContext) -> dict:
    glb = {"resolve_attack": resolve_attack, "ctx": ctx}
    per_call: list[float] = []
    for _ in range(REPEAT):
        t = timeit.timeit("resolve_attack(ctx)", globals=glb, number=N_PER_RUN)
        per_call.append(t / N_PER_RUN * 1e6)
    return _stats(per_call)


def bench_us() -> dict:
    """resolve_attack μs 基准（三分支 + GC on/off）。"""
    branches = _find_branch_seeds()
    results: dict[str, dict] = {}
    for branch, seed in branches.items():
        ctx = _ctx(seed)
        results[f"{branch}_gc_on"] = _bench_branch(ctx)

        gc_was = gc.isenabled()
        gc.disable()
        try:
            results[f"{branch}_gc_off"] = _bench_branch(ctx)
        finally:
            if gc_was:
                gc.enable()
    return results


def bench_gc() -> dict:
    """GC 基准：单次分配峰值 + 20k 次 gen0 回收次数。"""
    ctx = _ctx(42)

    tracemalloc.start()
    r = resolve_attack(ctx)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    gc.collect()
    before = gc.get_stats()[0]["collections"]
    for _ in range(TOTAL_CALLS):
        resolve_attack(ctx)
    after = gc.get_stats()[0]["collections"]

    return {
        "single_call_peak_bytes": peak,
        "single_call_effects_count": len(r.effects),
        "single_call_messages_count": len(r.messages),
        "gen0_collections_per_20k_calls": after - before,
    }


def _seed_output(seed: int) -> str:
    """打印单次输出 JSON（PYTHONHASHSEED 验证用）。"""
    r = resolve_attack(_ctx(seed))
    return r.model_dump_json()


def bench_hashseed() -> dict:
    """PYTHONHASHSEED 跨进程确定性验证。"""
    seed = 42
    script = Path(__file__).resolve()
    outputs: dict[str, list[str]] = {}
    for hs in ["0", "1", "random"]:
        runs = []
        for _ in range(3):
            env = {**os.environ, "PYTHONHASHSEED": hs, "PYTHONPATH": str(_SRC)}
            r = subprocess.run(
                [sys.executable, str(script), "--seed-output", str(seed)],
                capture_output=True, text=True, env=env,
                check=True,
            )
            runs.append(r.stdout.strip())
        outputs[f"PYTHONHASHSEED={hs}"] = runs

    all_outputs = [o for runs in outputs.values() for o in runs]
    consistent = len(set(all_outputs)) == 1
    return {
        "consistent_across_processes": consistent,
        "sample_output_prefix": all_outputs[0][:200] if all_outputs else "",
        "details": outputs,
    }


def _print_go_nogo(report: dict) -> None:
    """对照阈值判定 go/no-go。"""
    if "us" not in report:
        return
    print("\n--- go/no-go 判定（ADR-0012 阈值）---")
    all_pass = True
    for key, stats in report["us"].items():
        med_ok = stats["median_us"] <= THRESHOLD_MEDIAN_US
        p99_ok = stats["p99_us"] <= THRESHOLD_P99_US
        status = "[OK]" if (med_ok and p99_ok) else "[FAIL]"
        if not (med_ok and p99_ok):
            all_pass = False
        print(
            f"  {status} {key}: median={stats['median_us']}us "
            f"(<={THRESHOLD_MEDIAN_US}) p99={stats['p99_us']}us (<={THRESHOLD_P99_US})"
        )
    verdict = "GO" if all_pass else "NO-GO"
    note = "达标" if all_pass else "超标，需优化热路径（见 ADR-0012 超标应对）"
    print(f"\n  {verdict}: us 基准{note}")

    if "hashseed" in report:
        if report["hashseed"].get("consistent_across_processes"):
            print("  [OK] PYTHONHASHSEED 跨进程一致（combat 确定性基础）")
        else:
            print("  [FAIL] PYTHONHASHSEED 跨进程不一致（combat 确定性破坏）")


def main() -> None:
    parser = argparse.ArgumentParser(description="resolve_attack 性能 micro-benchmark")
    parser.add_argument("--us", action="store_true", help="只跑 us 基准")
    parser.add_argument("--gc", action="store_true", help="只跑 GC 基准")
    parser.add_argument("--hashseed", action="store_true", help="只跑 PYTHONHASHSEED 验证")
    parser.add_argument("--seed-output", type=int, default=None, help="打印单次输出 JSON（内部用）")
    args = parser.parse_args()

    if args.seed_output is not None:
        print(_seed_output(args.seed_output))
        return

    run_all = not (args.us or args.gc or args.hashseed)

    report: dict = {}
    if run_all or args.us:
        print("跑 resolve_attack us 基准...")
        report["us"] = bench_us()
    if run_all or args.gc:
        print("跑 GC 基准...")
        report["gc"] = bench_gc()
    if run_all or args.hashseed:
        print("跑 PYTHONHASHSEED 验证...")
        report["hashseed"] = bench_hashseed()

    print("\n" + json.dumps(report, indent=2, ensure_ascii=False))
    _print_go_nogo(report)


if __name__ == "__main__":
    main()
