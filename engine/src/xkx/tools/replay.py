"""Combat Replay Viewer：战斗回放查看器（ADR-0013 PRD 3）。

非侵入消费 ``CombatRoundResult.ledger``，支持逐回合回放 + 交织时序展示 +
确定性 diff + ConformanceChecker 集成。可离线回放（仅依赖 ``xkx.combat``
模块，[10-引擎工具链PRD-combat-replay-viewer]
(../../../docs/xkx-arch/10-引擎工具链PRD-combat-replay-viewer.md)）。

战报归档格式（CombatLog JSON = snapshot + seed + input_log + output_frames）
直接衔接 M1 开源交付物（[04] §二 M1）。
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, Field

from xkx.combat.conformance import ConformanceReport, check_conformance
from xkx.combat.context import CombatContext
from xkx.combat.replay import CombatSnapshot, InputEntry, replay_with_context
from xkx.combat.result import (
    LEDGER_EFFECT,
    LEDGER_MESSAGE,
    LEDGER_SUBRESULT,
    RESULT_DODGE,
    RESULT_HIT,
    RESULT_PARRY,
    CombatRoundResult,
)

_CODE_NAMES = {RESULT_HIT: "HIT", RESULT_DODGE: "DODGE", RESULT_PARRY: "PARRY"}


class CombatLog(BaseModel):
    """战报归档格式（PRD §二.4，M1 开源交付物前身）。

    ``output_frames`` 可选：离线回放时为空（实时重放生成），战报归档时填充。
    """

    version: str = "1"
    snapshot: CombatSnapshot
    seed: int = 0
    input_log: list[InputEntry] = Field(default_factory=list)
    output_frames: list[CombatRoundResult] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> CombatLog:
        """从 JSON 文件加载战报。"""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        """保存战报到 JSON 文件。"""
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: CombatSnapshot,
        seed: int,
        input_log: list[InputEntry],
    ) -> CombatLog:
        """从 snapshot + seed + input_log 构造（output_frames 实时重放填充）。"""
        pairs = replay_with_context(snapshot, seed, input_log)
        return cls(
            snapshot=snapshot,
            seed=seed,
            input_log=input_log,
            output_frames=[r for _, r in pairs],
        )


class ReplayFrame(BaseModel):
    """单回合回放帧（ctx + result + conformance）。"""

    round_index: int
    ctx: CombatContext
    result: CombatRoundResult
    conformance: ConformanceReport


class DivergenceDetail(BaseModel):
    """单回合分歧详情。"""

    round_index: int
    field: str
    value_a: str
    value_b: str


class DiffReport(BaseModel):
    """两份日志的确定性 diff 报告。"""

    rounds_compared: int = 0
    first_divergence: int | None = None
    divergences: list[DivergenceDetail] = Field(default_factory=list)

    @property
    def deterministic(self) -> bool:
        """两份日志是否确定性一致（无分歧）。"""
        return self.first_divergence is None


class ReplayViewer:
    """战斗回放查看器（PRD §三.2 程序化 API）。"""

    def __init__(self, log: CombatLog) -> None:
        self._log = log
        self._frames: list[ReplayFrame] = self._build_frames()

    def _build_frames(self) -> list[ReplayFrame]:
        """从 snapshot + seed + input_log 实时重放生成帧（调 resolve_attack 纯函数）。"""
        pairs = replay_with_context(
            self._log.snapshot, self._log.seed, self._log.input_log
        )
        return [
            ReplayFrame(
                round_index=i,
                ctx=ctx,
                result=result,
                conformance=check_conformance(ctx, result),
            )
            for i, (ctx, result) in enumerate(pairs)
        ]

    @property
    def log(self) -> CombatLog:
        return self._log

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def iter_frames(self) -> Iterator[ReplayFrame]:
        """逐回合迭代。"""
        return iter(self._frames)

    def get_round(self, n: int) -> ReplayFrame:
        """跳转到第 N 回合（0-based）。"""
        if 0 <= n < len(self._frames):
            return self._frames[n]
        raise IndexError(f"回合 {n} 超出范围 [0, {len(self._frames)})")

    def diff(self, other: ReplayViewer) -> DiffReport:
        """确定性 diff：逐回合对比，定位首次分歧回合 + 分歧详情。"""
        n = min(len(self._frames), len(other._frames))
        divergences: list[DivergenceDetail] = []
        first_div: int | None = None
        for i in range(n):
            a = self._frames[i].result
            b = other._frames[i].result
            if a.model_dump_json() == b.model_dump_json():
                continue
            if first_div is None:
                first_div = i
            divergences.append(
                DivergenceDetail(
                    round_index=i,
                    field="result",
                    value_a=f"code={a.result_code} damage={a.damage}",
                    value_b=f"code={b.result_code} damage={b.damage}",
                )
            )
        return DiffReport(
            rounds_compared=n,
            first_divergence=first_div,
            divergences=divergences,
        )


def render_frame(frame: ReplayFrame, *, ledger_only: bool = False) -> str:
    """渲染单回合帧为人类可读文本（PRD §二.2 交织时序展示）。"""
    code = _CODE_NAMES.get(frame.result.result_code, str(frame.result.result_code))
    lines = [f"Round {frame.round_index} [{code}]  damage={frame.result.damage}"]
    if not ledger_only:
        lines.append("  ── 交织时序 ──")
    for i, entry in enumerate(frame.result.ledger):
        if entry.entry_type == LEDGER_MESSAGE:
            lines.append(f"  [{i}] msg  {entry.text}")
        elif entry.entry_type == LEDGER_EFFECT and entry.effect is not None:
            eff = entry.effect
            lines.append(
                f"  [{i}] eff  {eff.kind}  target={eff.target_id}  amount={eff.amount}"
            )
        elif entry.entry_type == LEDGER_SUBRESULT and entry.sub_result is not None:
            lines.append(f"  [{i}] sub  (riposte 子回合)")
    status = "PASS" if frame.conformance.ok else "FAIL"
    lines.append(f"  交织验证: {status}")
    return "\n".join(lines)


def render_conformance(frame: ReplayFrame) -> str:
    """渲染 ConformanceChecker 8 项检查结果。"""
    lines = [f"Round {frame.round_index} ConformanceChecker:"]
    for name in frame.conformance.passed:
        lines.append(f"  {name}: PASS")
    for v in frame.conformance.violations:
        lines.append(f"  {v.check_name}: FAIL - {v.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """replay CLI：python -m xkx.tools.replay <log.json> [options]。"""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "用法: python -m xkx.tools.replay <log.json> "
            "[--round N] [--diff other] [--conformance] [--json]"
        )
        return 1
    log_path = args[0]
    opts = args[1:]
    viewer = ReplayViewer(CombatLog.load(log_path))

    if "--json" in opts:
        frames_data = [
            {
                "round": f.round_index,
                "result_code": f.result.result_code,
                "damage": f.result.damage,
                "conformance_ok": f.conformance.ok,
            }
            for f in viewer.iter_frames()
        ]
        print(json.dumps(frames_data, ensure_ascii=False))
        return 0

    if "--diff" in opts:
        idx = opts.index("--diff")
        if idx + 1 >= len(opts):
            print("--diff 需要参数")
            return 1
        other = ReplayViewer(CombatLog.load(opts[idx + 1]))
        diff = viewer.diff(other)
        print(f"Determinism diff: {log_path} vs {opts[idx + 1]}")
        print(f"  Rounds compared: {diff.rounds_compared}")
        if diff.deterministic:
            print("  Result: DETERMINISTIC (一致)")
            return 0
        print(f"  First divergence: Round {diff.first_divergence}")
        print("  Result: NON-DETERMINISTIC")
        return 2

    if "--round" in opts:
        idx = opts.index("--round")
        n = int(opts[idx + 1])
        frame = viewer.get_round(n)
        print(render_frame(frame))
        if "--conformance" in opts:
            print(render_conformance(frame))
        return 0

    # 默认快进回放
    for frame in viewer.iter_frames():
        print(render_frame(frame))
        if "--conformance" in opts:
            print(render_conformance(frame))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
