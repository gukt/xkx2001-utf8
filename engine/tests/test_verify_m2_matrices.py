"""把 scripts/verify_m2_*.py 矩阵接入 pytest，防止手测脚本与引擎行为漂移。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _assert_all_pass(module_name: str) -> None:
    module = __import__(module_name)
    scenarios = module.all_scenarios()
    failed = [
        f"{sc.name} :: {step.line} :: {step.detail or step.messages}"
        for sc in scenarios
        for step in sc.steps
        if not step.ok
    ]
    assert not failed, "矩阵失败：\n" + "\n".join(failed)


def test_m2_combat_matrix_all_pass() -> None:
    _assert_all_pass("verify_m2_combat")


def test_m2_economy_matrix_all_pass() -> None:
    _assert_all_pass("verify_m2_economy")


def test_m2_faction_matrix_all_pass() -> None:
    _assert_all_pass("verify_m2_faction")


def test_m2_travel_matrix_all_pass() -> None:
    _assert_all_pass("verify_m2_travel")


def test_m2_journey_matrix_all_pass() -> None:
    _assert_all_pass("verify_m2_journey")
