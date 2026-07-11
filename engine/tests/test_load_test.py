"""T10 压测脚本回归门禁（类似 test_benchmark.py）。

验证 [tools/load_test.py](../tools/load_test.py) 能跑 + tick p99 < 100ms（宽松阈值
防退化）。小规模（30 tick）快速跑，CI 门禁；完整 300 tick 本地跑。

见 [ADR-0012](../../docs/adr/ADR-0012-performance-microbenchmark.md) 决策 6（宽松阈值
非精确基准）。kill criteria 3 完整判定由本地 ``python tools/load_test.py`` 跑。
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

_LOAD_TEST_PATH = Path(__file__).resolve().parent.parent / "tools" / "load_test.py"

# CI 友好：30 tick 快速跑，宽松阈值防 CI 机器慢导致 flaky
CI_TICKS = 30
CI_P99_THRESHOLD_US = 100_000  # 100ms（kill criteria 3 预算，本地 ~8ms 留 12x 余量）


def _load_module() -> object:
    """importlib 加载 tools/load_test.py（不在 src/xkx/ 包内）。

    注册到 ``sys.modules`` 以便 dataclass ``asdict`` 能通过 ``__module__`` 找到
    模块命名空间（否则 dataclasses.py 在 asdict 时报 AttributeError）。
    """
    spec = importlib.util.spec_from_file_location("load_test", _LOAD_TEST_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["load_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_load_test_runs_and_meets_budget() -> None:
    """小规模压测能跑通 + tick p99 < 100ms 预算（CI 门禁）。"""
    load_test = _load_module()
    config = load_test.LoadTestConfig(ticks=CI_TICKS)  # type: ignore[attr-defined]
    report = asyncio.run(load_test.run_load_test(config))  # type: ignore[attr-defined]
    assert report.tick_count == CI_TICKS
    assert report.tick_p99_us < CI_P99_THRESHOLD_US, (
        f"tick p99 {report.tick_p99_us}μs >= {CI_P99_THRESHOLD_US}μs 阈值"
    )
    assert report.go is True


def test_load_test_report_json_serialization() -> None:
    """报告 JSON 序列化往返（结构完整）。"""
    load_test = _load_module()
    config = load_test.LoadTestConfig(ticks=5)  # type: ignore[attr-defined]
    report = asyncio.run(load_test.run_load_test(config))  # type: ignore[attr-defined]
    data = json.loads(report.to_json())
    assert data["tick_count"] == 5
    assert "per_system" in data
    assert isinstance(data["per_system"], list)
    assert data["go"] is True
    assert "persist_cost_p99_ms" in data


def test_load_test_scaled_config() -> None:
    """scaled(500) 降级配置正确（kill criteria 3 触发时 500+50）。"""
    load_test = _load_module()
    config = load_test.LoadTestConfig.scaled(500)  # type: ignore[attr-defined]
    assert config.n_sessions == 500  # 1000 * 0.5
    assert config.n_players == 500  # 1000 * 0.5
    assert config.n_npcs == 100  # 200 * 0.5
    assert config.total_entities == 650  # (50+200+1000+50) * 0.5


def test_load_test_per_system_covers_all_systems() -> None:
    """per-System 报告覆盖 4 个 System（Condition/Combat/Storage/Connection）。"""
    load_test = _load_module()
    config = load_test.LoadTestConfig(ticks=10)  # type: ignore[attr-defined]
    report = asyncio.run(load_test.run_load_test(config))  # type: ignore[attr-defined]
    names = {s["system_name"] for s in report.per_system}
    assert "ConditionSystem" in names
    assert "CombatSystem" in names
    assert "StorageSystem" in names
    assert "ConnectionSystem" in names
