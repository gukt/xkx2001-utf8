"""把 scripts/verify_m3_pack_loop.py 接入 pytest，防止手测脚本与引擎行为漂移。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_m3_pack_loop_matrix_all_pass() -> None:
    module = __import__("verify_m3_pack_loop")
    scenarios = module.all_scenarios()
    failed = [
        f"{sc.name} :: {step.line} :: {step.detail or step.messages}"
        for sc in scenarios
        for step in sc.steps
        if not step.ok
    ]
    assert not failed, "矩阵失败：\n" + "\n".join(failed)
