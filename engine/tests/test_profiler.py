"""Tick Profiler 测试（ADR-0013 PRD 2）。"""

from __future__ import annotations

import time

from xkx.runtime.profiler import (
    SystemStats,
    TickProfiler,
    TickReport,
    TickSample,
    main,
)

# ---------------------------------------------------------------------------
# enabled=False 零开销
# ---------------------------------------------------------------------------


def test_disabled_profiler_no_samples() -> None:
    """enabled=False 时不记录采样。"""
    p = TickProfiler(enabled=False)
    p.next_tick()
    with p.measure_system("CombatSystem"):
        pass
    assert p.sample_count == 0


def test_disabled_profiler_zero_overhead() -> None:
    """enabled=False 时 measure_system 近似零开销（< 0.1ms）。

    PRD §六验收：空操作 contextmanager 开销 <0.1ms/tick。
    """
    p = TickProfiler(enabled=False)
    p.next_tick()
    start = time.perf_counter_ns()
    for _ in range(10000):
        with p.measure_system("CombatSystem"):
            pass
    elapsed_us = (time.perf_counter_ns() - start) // 1000
    # 10000 次空 contextmanager 开销：PRD §六 <0.1ms/tick（100μs/次），本断言
    # <50ms（5μs/次）仍远严于 PRD；放宽自原 10ms 以容 WSL2 timing 抖动偶发超标。
    assert elapsed_us < 50_000, f"零开销模式耗时 {elapsed_us}μs，超 50ms"


def test_enabled_toggle() -> None:
    """enabled 属性可运行时切换。"""
    p = TickProfiler(enabled=False)
    assert p.enabled is False
    p.enabled = True
    assert p.enabled is True
    p.next_tick()
    with p.measure_system("CombatSystem"):
        pass
    assert p.sample_count == 1


# ---------------------------------------------------------------------------
# 采样与统计
# ---------------------------------------------------------------------------


def test_measure_system_records_sample() -> None:
    """enabled=True 时 measure_system 记录采样。"""
    p = TickProfiler(enabled=True)
    p.next_tick()
    with p.measure_system("CombatSystem"):
        pass
    assert p.sample_count == 1
    report = p.report()
    stats = report.system_summary()
    assert len(stats) == 1
    assert stats[0].system_name == "CombatSystem"
    assert stats[0].ticks == 1
    assert stats[0].compute_us >= 0 if hasattr(stats[0], "compute_us") else True


def test_multiple_systems_multiple_ticks() -> None:
    """多 System 多 tick 采样正确聚合。"""
    p = TickProfiler(enabled=True)
    for _ in range(5):
        p.next_tick()
        with p.measure_system("CombatSystem"):
            pass
        with p.measure_system("HealSystem"):
            pass
    report = p.report()
    stats = report.system_summary()
    assert len(stats) == 2
    by_name = {s.system_name: s for s in stats}
    assert by_name["CombatSystem"].ticks == 5
    assert by_name["HealSystem"].ticks == 5


def test_system_summary_stats_fields() -> None:
    """SystemStats 含 mean/p99/max/total/ticks/pct_tick。"""
    p = TickProfiler(enabled=True)
    for _ in range(10):
        p.next_tick()
        with p.measure_system("CombatSystem"):
            pass
    stats = p.report().system_summary()[0]
    assert isinstance(stats, SystemStats)
    assert stats.system_name == "CombatSystem"
    assert stats.mean_us >= 0.0
    assert stats.p99_us >= 0.0
    assert stats.max_us >= 0
    assert stats.total_us >= 0
    assert stats.ticks == 10
    assert stats.pct_tick >= 0.0


def test_system_summary_sorted_by_total() -> None:
    """system_summary 按 total_us 降序。"""
    p = TickProfiler(enabled=True)
    p.next_tick()
    with p.measure_system("SlowSystem"):
        time.sleep(0.001)  # 1ms
    with p.measure_system("FastSystem"):
        pass
    stats = p.report().system_summary()
    assert stats[0].system_name == "SlowSystem"
    assert stats[0].total_us >= stats[1].total_us


# ---------------------------------------------------------------------------
# ring buffer 滑动窗口
# ---------------------------------------------------------------------------


def test_ring_buffer_drops_old_samples() -> None:
    """ring buffer 满后丢弃旧采样（window=500）。"""
    p = TickProfiler(enabled=True, window=10)
    for _ in range(15):
        p.next_tick()
        with p.measure_system("CombatSystem"):
            pass
    assert p.sample_count == 10  # 窗口上限


def test_reset_clears_samples() -> None:
    """reset 清空采样 + tick 编号。"""
    p = TickProfiler(enabled=True)
    p.next_tick()
    with p.measure_system("CombatSystem"):
        pass
    assert p.sample_count == 1
    p.reset()
    assert p.sample_count == 0


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------


def test_to_table_contains_system_name() -> None:
    """to_table 包含 System 名称列。"""
    p = TickProfiler(enabled=True)
    p.next_tick()
    with p.measure_system("CombatSystem"):
        pass
    table = p.report().to_table()
    assert "CombatSystem" in table
    assert "mean(us)" in table


def test_to_json_parseable() -> None:
    """to_json 输出可被 json.loads 解析。"""
    import json

    p = TickProfiler(enabled=True)
    for _ in range(3):
        p.next_tick()
        with p.measure_system("CombatSystem"):
            pass
    data = json.loads(p.report().to_json())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["system_name"] == "CombatSystem"
    assert data[0]["ticks"] == 3


def test_empty_report() -> None:
    """无采样时 report 返回空统计。"""
    p = TickProfiler(enabled=True)
    report = p.report()
    assert report.system_summary() == []
    assert "System" in report.to_table()  # 表头仍输出


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_default(capsys: object) -> None:
    """profile CLI 默认输出表格。"""
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "CombatSystem" in out


def test_main_json(capsys: object) -> None:
    """profile --json 输出 JSON。"""
    ret = main(["--json"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    import json

    data = json.loads(out)
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# TickSample / SystemStats 数据模型
# ---------------------------------------------------------------------------


def test_tick_sample_slots() -> None:
    """TickSample 用 __slots__（PRD §四.1，减少分配开销）。"""
    s = TickSample(tick_id=1, system_name="CombatSystem", compute_us=100)
    assert s.tick_id == 1
    assert s.system_name == "CombatSystem"
    assert s.compute_us == 100
    assert not hasattr(s, "__dict__")  # slots=True 无 __dict__


def test_tick_report_from_samples() -> None:
    """TickReport 从采样列表构造。"""
    samples = [
        TickSample(1, "CombatSystem", 100),
        TickSample(2, "CombatSystem", 200),
    ]
    report = TickReport(samples)
    stats = report.system_summary()
    assert len(stats) == 1
    assert stats[0].ticks == 2
    assert stats[0].max_us == 200
