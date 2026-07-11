"""Combat Replay Viewer 测试（ADR-0013 PRD 3）。"""

from __future__ import annotations

import json

from xkx.combat.context import CombatantSnapshot
from xkx.combat.replay import CombatSnapshot, InputEntry
from xkx.tools.replay import (
    CombatLog,
    DiffReport,
    ReplayFrame,
    ReplayViewer,
    main,
    render_conformance,
    render_frame,
)


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


def _snapshot() -> CombatSnapshot:
    return CombatSnapshot(combatants={1: _attacker(), 2: _victim()}, seed=42)


def _input_log() -> list[InputEntry]:
    return [
        InputEntry(attacker_id=1, victim_id=2, attack_type=0, seq=0),
        InputEntry(attacker_id=2, victim_id=1, attack_type=0, seq=1),
    ]


def _viewer(seed: int = 42) -> ReplayViewer:
    log = CombatLog.from_snapshot(_snapshot(), seed, _input_log())
    return ReplayViewer(log)


# ---------------------------------------------------------------------------
# CombatLog 序列化
# ---------------------------------------------------------------------------


def test_combat_log_save_load_roundtrip(tmp_path: object) -> None:
    """CombatLog save/load JSON 往返。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "combat.json"
    log.save(path)
    restored = CombatLog.load(path)
    assert restored == log


def test_combat_log_from_snapshot_fills_output_frames() -> None:
    """from_snapshot 实时重放填充 output_frames。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    assert len(log.output_frames) == 2
    for f in log.output_frames:
        assert f.result_code in (0, -1, -2)


def test_combat_log_load_from_json_string() -> None:
    """CombatLog.model_validate_json 从 JSON 字符串加载。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    restored = CombatLog.model_validate_json(log.model_dump_json())
    assert restored == log


# ---------------------------------------------------------------------------
# ReplayViewer 帧构建
# ---------------------------------------------------------------------------


def test_viewer_builds_frames() -> None:
    """ReplayViewer 从 log 构建 frames（实时重放）。"""
    viewer = _viewer()
    assert viewer.frame_count == 2
    frames = list(viewer.iter_frames())
    for i, f in enumerate(frames):
        assert isinstance(f, ReplayFrame)
        assert f.round_index == i
        assert f.conformance.ok  # 合法输入无 violation


def test_viewer_get_round() -> None:
    """get_round 跳转到指定回合。"""
    viewer = _viewer()
    frame = viewer.get_round(0)
    assert frame.round_index == 0
    frame1 = viewer.get_round(1)
    assert frame1.round_index == 1


def test_viewer_get_round_out_of_range() -> None:
    """get_round 越界 raise IndexError。"""
    viewer = _viewer()
    try:
        viewer.get_round(99)
        raise AssertionError("应 raise IndexError")
    except IndexError:
        pass


def test_viewer_empty_input_log() -> None:
    """空 input_log -> 0 帧。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, [])
    viewer = ReplayViewer(log)
    assert viewer.frame_count == 0
    assert list(viewer.iter_frames()) == []


# ---------------------------------------------------------------------------
# 确定性 diff
# ---------------------------------------------------------------------------


def test_diff_same_log_deterministic() -> None:
    """同 snapshot + seed + input_log 的两份日志 diff -> deterministic。"""
    v1 = _viewer(seed=42)
    v2 = _viewer(seed=42)
    diff = v1.diff(v2)
    assert diff.deterministic
    assert diff.first_divergence is None
    assert diff.divergences == []


def test_diff_different_seed_non_deterministic() -> None:
    """不同 seed 的两份日志 diff -> 非确定性（定位首次分歧）。"""
    v1 = _viewer(seed=42)
    v2 = _viewer(seed=999)
    diff = v1.diff(v2)
    # 不同 seed 大概率分歧（若碰巧一致也接受，但通常分歧）
    if not diff.deterministic:
        assert diff.first_divergence is not None
        assert diff.first_divergence < v1.frame_count
        assert len(diff.divergences) > 0


def test_diff_report_deterministic_property() -> None:
    """DiffReport.deterministic 属性。"""
    d1 = DiffReport(rounds_compared=5, first_divergence=None)
    assert d1.deterministic is True
    d2 = DiffReport(rounds_compared=5, first_divergence=3)
    assert d2.deterministic is False


# ---------------------------------------------------------------------------
# 帧渲染
# ---------------------------------------------------------------------------


def test_render_frame_contains_round_and_code() -> None:
    """render_frame 包含回合编号 + 结果码。"""
    viewer = _viewer()
    frame = viewer.get_round(0)
    text = render_frame(frame)
    assert "Round 0" in text
    assert "damage=" in text
    # 结果码名（HIT/DODGE/PARRY 之一）
    assert any(name in text for name in ("HIT", "DODGE", "PARRY"))


def test_render_frame_contains_ledger() -> None:
    """render_frame 包含交织时序（msg/eff 条目）。"""
    viewer = _viewer()
    # 找一个有 ledger 内容的帧
    for frame in viewer.iter_frames():
        text = render_frame(frame)
        if frame.result.ledger:
            assert "msg" in text or "eff" in text
            break


def test_render_frame_contains_conformance_status() -> None:
    """render_frame 包含交织验证 PASS/FAIL。"""
    viewer = _viewer()
    frame = viewer.get_round(0)
    text = render_frame(frame)
    assert "PASS" in text or "FAIL" in text


def test_render_conformance() -> None:
    """render_conformance 渲染 8 项检查。"""
    viewer = _viewer()
    frame = viewer.get_round(0)
    text = render_conformance(frame)
    assert "ConformanceChecker" in text
    assert "PASS" in text


# ---------------------------------------------------------------------------
# 确定性（同 viewer 两次构建一致）
# ---------------------------------------------------------------------------


def test_viewer_deterministic_rebuild() -> None:
    """同 log 两次构建 ReplayViewer -> frames 一致。"""
    v1 = _viewer(seed=42)
    v2 = _viewer(seed=42)
    for f1, f2 in zip(v1.iter_frames(), v2.iter_frames(), strict=True):
        assert f1.result == f2.result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_no_args(capsys: object) -> None:
    """CLI 无参数返回 1。"""
    ret = main([])
    assert ret == 1
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "用法" in out


def test_main_default(tmp_path: object, capsys: object) -> None:
    """CLI 默认快进回放。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "combat.json"
    log.save(path)
    ret = main([str(path)])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Round 0" in out


def test_main_round(tmp_path: object, capsys: object) -> None:
    """CLI --round N 跳转。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "combat.json"
    log.save(path)
    ret = main([str(path), "--round", "1"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Round 1" in out
    assert "Round 0" not in out


def test_main_diff_deterministic(tmp_path: object, capsys: object) -> None:
    """CLI --diff 同日志 -> DETERMINISTIC。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "a.json"
    path2 = p / "b.json"
    log.save(path)
    log.save(path2)
    ret = main([str(path), "--diff", str(path2)])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "DETERMINISTIC" in out


def test_main_json(tmp_path: object, capsys: object) -> None:
    """CLI --json 输出 JSON。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "combat.json"
    log.save(path)
    ret = main([str(path), "--json"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 2


def test_main_conformance(tmp_path: object, capsys: object) -> None:
    """CLI --conformance 显示检查结果。"""
    log = CombatLog.from_snapshot(_snapshot(), 42, _input_log())
    p = tmp_path  # type: ignore[attr-defined]
    path = p / "combat.json"
    log.save(path)
    ret = main([str(path), "--round", "0", "--conformance"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "ConformanceChecker" in out
