"""combat-sim 测试：离线行为等价验证（T9，ADR-0011 + ADR-0023）。

验证：
- run_combat_sim 端到端：合法 snapshot + input_log -> 无 violation
- 确定性：同 snapshot + seed + input_log -> 同报告
- impl_map 三状态汇总（14 implemented + 0 simplified）
- JSON 序列化往返（snapshot + input_log）
- CLI 入口（main）
"""

from __future__ import annotations

from xkx.combat.combat_sim import (
    CombatSimReport,
    RoundReport,
    input_log_from_json,
    input_log_to_json,
    main,
    run_combat_sim,
    snapshot_from_json,
    snapshot_to_json,
    summarize_impl_status,
)
from xkx.combat.context import CombatantSnapshot
from xkx.combat.replay import CombatSnapshot, InputEntry


def _attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"unarmed": 80},
        max_qi=600,
        qi=600,
        eff_qi=600,
        max_jingli=300,
        jingli=300,
    )


def _victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=10,
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=100,
        qi=100,
        eff_qi=100,
        max_jingli=50,
        jingli=50,
    )


def _two_combatant_snapshot() -> CombatSnapshot:
    return CombatSnapshot(combatants={1: _attacker(), 2: _victim()}, seed=42)


def _input_log() -> list[InputEntry]:
    return [
        InputEntry(attacker_id=1, victim_id=2, attack_type=0, seq=0),
        InputEntry(attacker_id=2, victim_id=1, attack_type=0, seq=1),
    ]


# ---------------------------------------------------------------------------
# run_combat_sim 端到端
# ---------------------------------------------------------------------------


def test_run_combat_sim_no_violation() -> None:
    """合法 snapshot + input_log -> run_combat_sim -> ok=True（无 violation）。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=_input_log())
    assert report.ok, f"违规 {report.total_violations} 条"
    assert report.total_rounds == 2
    assert report.total_violations == 0


def test_run_combat_sim_empty_input_log() -> None:
    """空 input_log -> 0 回合 -> ok=True（无 violation）。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=[])
    assert report.ok
    assert report.total_rounds == 0
    assert report.total_violations == 0
    assert report.round_reports == []


def test_run_combat_sim_determinism() -> None:
    """同 snapshot + seed + input_log -> 同报告（combat 确定性）。"""
    snapshot = _two_combatant_snapshot()
    input_log = _input_log()
    r1 = run_combat_sim(snapshot, seed=42, input_log=input_log)
    r2 = run_combat_sim(snapshot, seed=42, input_log=input_log)
    assert r1 == r2


def test_run_combat_sim_multi_round() -> None:
    """多回合 input_log -> total_rounds 正确。"""
    input_log = [
        InputEntry(attacker_id=1, victim_id=2, attack_type=0, seq=i) for i in range(5)
    ]
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=input_log)
    assert report.total_rounds == 5
    assert len(report.round_reports) == 5
    for i, r in enumerate(report.round_reports):
        assert r.round_index == i


def test_run_combat_sim_all_checks_passed() -> None:
    """每回合 8 项检查全 passed（ConformanceChecker 全覆盖）。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=_input_log())
    for r in report.round_reports:
        assert len(r.conformance.passed) == 8, (
            f"回合 {r.round_index} passed={r.conformance.passed}"
        )
        assert len(r.conformance.violations) == 0


def test_run_combat_sim_skips_missing_combatant() -> None:
    """input_log 引用不存在的 combatant -> 跳过（replay 防御性）。"""
    input_log = [InputEntry(attacker_id=99, victim_id=2, attack_type=0, seq=0)]
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=input_log)
    assert report.total_rounds == 0
    assert report.ok


# ---------------------------------------------------------------------------
# impl_map 三状态汇总
# ---------------------------------------------------------------------------


def test_summarize_impl_status() -> None:
    """impl_map 三状态汇总：14 implemented + 0 simplified（T6 升级后）。"""
    counts = summarize_impl_status()
    assert counts["implemented"] == 14
    assert counts["simplified"] == 0


def test_run_combat_sim_report_has_impl_status() -> None:
    """报告含 impl_status_summary 字段。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=_input_log())
    assert report.impl_status_summary["implemented"] == 14
    assert report.impl_status_summary["simplified"] == 0


# ---------------------------------------------------------------------------
# JSON 序列化往返
# ---------------------------------------------------------------------------


def test_snapshot_json_roundtrip() -> None:
    """CombatSnapshot JSON 序列化往返。"""
    snapshot = _two_combatant_snapshot()
    restored = snapshot_from_json(snapshot_to_json(snapshot))
    assert restored == snapshot


def test_input_log_json_roundtrip() -> None:
    """input log JSON 序列化往返。"""
    input_log = _input_log()
    restored = input_log_from_json(input_log_to_json(input_log))
    assert restored == input_log


def test_run_combat_sim_from_json() -> None:
    """从 JSON 加载 snapshot + input_log -> run_combat_sim -> ok=True。"""
    snapshot = snapshot_from_json(snapshot_to_json(_two_combatant_snapshot()))
    input_log = input_log_from_json(input_log_to_json(_input_log()))
    report = run_combat_sim(snapshot, seed=42, input_log=input_log)
    assert report.ok
    assert report.total_rounds == 2


# ---------------------------------------------------------------------------
# 报告结构
# ---------------------------------------------------------------------------


def test_combat_sim_report_ok_property() -> None:
    """CombatSimReport.ok 属性（无 violation 时 True）。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=_input_log())
    assert report.ok is True
    assert report.passed_checks > 0


def test_round_report_structure() -> None:
    """RoundReport 结构完整（round_index + conformance）。"""
    report = run_combat_sim(_two_combatant_snapshot(), seed=42, input_log=_input_log())
    for i, r in enumerate(report.round_reports):
        assert isinstance(r, RoundReport)
        assert r.round_index == i
        assert r.conformance.ok
    assert isinstance(report, CombatSimReport)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def test_main_no_args_returns_1(capsys: object) -> None:
    """CLI 无参数返回 1（用法提示）。"""
    ret = main([])
    assert ret == 1
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "用法" in out


def test_main_ok(tmp_path: object, capsys: object) -> None:
    """CLI 正常运行返回 0（行为等价验证通过）。"""
    p = tmp_path  # type: ignore[attr-defined]
    snapshot_path = p / "snapshot.json"
    input_log_path = p / "input_log.json"
    snapshot_path.write_text(snapshot_to_json(_two_combatant_snapshot()), encoding="utf-8")
    input_log_path.write_text(input_log_to_json(_input_log()), encoding="utf-8")
    ret = main([str(snapshot_path), str(input_log_path), "42"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "通过" in out


def test_main_default_seed(tmp_path: object, capsys: object) -> None:
    """CLI 不传 seed 时默认 0。"""
    p = tmp_path  # type: ignore[attr-defined]
    snapshot_path = p / "snapshot.json"
    input_log_path = p / "input_log.json"
    snapshot_path.write_text(snapshot_to_json(_two_combatant_snapshot()), encoding="utf-8")
    input_log_path.write_text(input_log_to_json(_input_log()), encoding="utf-8")
    ret = main([str(snapshot_path), str(input_log_path)])
    assert ret == 0
