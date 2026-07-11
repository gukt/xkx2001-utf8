"""Tick Profiler：tick 级性能采集器（ADR-0013 PRD 2）。

per-System compute 统计 + ``enabled=False`` 零开销 contextmanager + ring buffer。
阶段 1 最小：per-System 统计 + CLI 报告 + 开关 + 滑动窗口
（[10-引擎工具链PRD-tick-profiler]
(../../../docs/xkx-arch/10-引擎工具链PRD-tick-profiler.md) §六）。

与 [ADR-0012](../../../docs/adr/ADR-0012-performance-microbenchmark.md) benchmark
分工：benchmark 是 μs 级微基准（单 resolve_attack），profiler 是 tick 级宏观
（1s tick 内多 System 聚合），两者互补构成 kill criteria 3 完整 go/no-go 判定。
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class TickSample:
    """单次 tick 内一个 System 的采样记录。"""

    tick_id: int
    system_name: str
    compute_us: int


@dataclass(slots=True)
class SystemStats:
    """System 级聚合统计（PRD §四.2）。"""

    system_name: str
    mean_us: float
    p99_us: float
    max_us: int
    total_us: int
    ticks: int
    pct_tick: float


class TickProfiler:
    """Tick 级性能采集器（PRD §三.2）。

    ``enabled=False`` 时 ``measure_system`` 为空 contextmanager，零开销
    （生产环境关闭，调试/压测开启）。
    """

    def __init__(self, *, enabled: bool = False, window: int = 500) -> None:
        self._enabled = enabled
        self._window = window
        self._samples: deque[TickSample] = deque(maxlen=window)
        self._tick_id = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @contextmanager
    def measure_system(self, system_name: str) -> Iterator[None]:
        """System.update 前后插桩，记录 compute 时间（μs）。

        ``enabled=False`` 时直接 yield，无计时无记录（零开销）。
        """
        if not self._enabled:
            yield
            return
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            elapsed_us = (time.perf_counter_ns() - start) // 1000
            self._samples.append(TickSample(self._tick_id, system_name, elapsed_us))

    def next_tick(self) -> int:
        """推进 tick 编号（调用方每 tick 调一次）。"""
        self._tick_id += 1
        return self._tick_id

    def report(self) -> TickReport:
        """生成报告对象。"""
        return TickReport(list(self._samples))

    def reset(self) -> None:
        """清空滑动窗口，重新采集。"""
        self._samples.clear()
        self._tick_id = 0


class TickReport:
    """Tick 性能报告（PRD §三.2 TickReport）。"""

    budget_ms: int = 100  # tick 预算 100ms（CLAUDE.md 不变量 compute<100ms）

    def __init__(self, samples: list[TickSample]) -> None:
        self._samples = samples

    def system_summary(self) -> list[SystemStats]:
        """per-System 统计摘要（mean/p99/max/total/ticks/%tick）。"""
        by_system: dict[str, list[int]] = {}
        for s in self._samples:
            by_system.setdefault(s.system_name, []).append(s.compute_us)
        result: list[SystemStats] = []
        for name, times in by_system.items():
            times_sorted = sorted(times)
            n = len(times_sorted)
            total = sum(times_sorted)
            mean = total / n if n else 0.0
            p99_idx = min(n - 1, int(n * 0.99)) if n else 0
            p99 = float(times_sorted[p99_idx]) if n else 0.0
            mx = times_sorted[-1] if n else 0
            pct = (total / 1000) / self.budget_ms * 100 if total else 0.0
            result.append(SystemStats(name, mean, p99, mx, total, n, pct))
        result.sort(key=lambda x: x.total_us, reverse=True)
        return result

    def to_table(self) -> str:
        """CLI 表格格式（PRD §二.1 示例输出）。"""
        lines = [
            f"{'System':<20} {'mean(us)':>10} {'p99(us)':>10} {'max(us)':>10} "
            f"{'total(ms)':>10} {'ticks':>6} {'%tick':>6}"
        ]
        for s in self.system_summary():
            lines.append(
                f"{s.system_name:<20} {s.mean_us:>10.0f} {s.p99_us:>10.0f} "
                f"{s.max_us:>10} {s.total_us / 1000:>10.1f} {s.ticks:>6} {s.pct_tick:>5.0f}%"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        """JSON 序列化（--json 选项，供脚本消费）。"""
        return json.dumps(
            [asdict(s) for s in self.system_summary()], ensure_ascii=False
        )


def main(argv: list[str] | None = None) -> int:
    """profile CLI（独立运行时演示报告格式；实际采样需嵌入引擎 tick 循环）。"""
    args = argv if argv is not None else sys.argv[1:]
    profiler = TickProfiler(enabled=True)
    # 演示：模拟 10 tick 采样
    for _ in range(10):
        profiler.next_tick()
        with profiler.measure_system("CombatSystem"):
            pass
    report = profiler.report()
    if "--json" in args:
        print(report.to_json())
    else:
        print(report.to_table())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
