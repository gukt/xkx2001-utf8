"""把 scripts/verify_pre_m4_xingxiu_mechanics.py 矩阵接入 pytest，防手测脚本漂移。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import verify_pre_m4_xingxiu_mechanics as matrix  # noqa: E402


def test_pre_m4_xingxiu_mechanics_matrix_all_pass() -> None:
    scenarios = matrix.all_scenarios()
    failed = [
        f"{sc.name} :: {step.line} :: {step.detail or step.messages}"
        for sc in scenarios
        for step in sc.steps
        if not step.ok
    ]
    assert not failed, "矩阵失败：\n" + "\n".join(failed)
