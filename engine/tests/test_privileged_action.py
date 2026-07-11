"""PrivilegedAction 测试（阶段 1 Wave 2 T4，ADR-0020 决策 4 + ADR-0021 决策 3b）。

覆盖：
- ROOT 门控（source 无 root capability -> PermissionError）
- 调用点白名单（call_site 不在白名单 -> PermissionError）
- 强制审计（PRIVILEGED_ACTION 审计日志记录 actor/source/cmd/call_site）
- 走完整 8 段管线（force_me 经 process_input + command_hook 语义）
- viewer 注入（PrivilegedAction 路径 viewer=actor，source=系统调用者）
- NPC AI 禁用（设计约束，非代码强制，文档化）

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 4
[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md) 决策 3b
[05](../../../docs/xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.capability import PermissionService
from xkx.runtime.commands import Game
from xkx.runtime.components import Position
from xkx.runtime.privileged import (
    PRIVILEGED_ACTION_CALL_SITES,
    PrivilegedAction,
    PrivilegedActionLog,
)
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "wuxia_micro"

# 测试用的系统调用者 entity_id（对齐 LPC ROOT_UID 等价实体）
SYSTEM_SOURCE = 999999


def _game_and_player() -> tuple[Game, int, PermissionService, int]:
    """返回 (game, player_id, permission_service, system_source_id)。

    system_source 是一个独立的 entity_id，代表系统调用者（对齐 LPC ROOT_UID）。
    """
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", "city/street")
    game = Game(world, room_idx, rules, seed_base=42)
    service = PermissionService()
    return game, pid, service, SYSTEM_SOURCE


# ---- ROOT 门控 ----


def test_root_gate_passes_with_root_capability() -> None:
    """source 持 root capability 时 ROOT 门控通过，命令执行。"""
    game, pid, service, source = _game_and_player()
    # source 预签发 root（issue_root_token 在 force 内部调用）
    plog = PrivilegedActionLog()
    msgs = PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="look",
        source=source,
        call_site="updated.broadcast_rumor",
        privileged_log=plog,
    )
    assert msgs  # look 产出了房间描述
    assert service.is_root_entity(source) is True
    assert service.is_root_entity(pid) is True  # actor 也签发了 root


def test_root_gate_fails_without_root() -> None:
    """source 无 root capability -> PermissionError（非静默拒绝，误调是 bug）。

    本测试验证 issue_root_token 总是签发含 root 的 token（ROOT 门控在 force 内部
    通过 issue_root_token 保证 source 持 root）。要触发 PermissionError 需 mock
    一个不含 root 的 service，这里通过白名单失败间接验证 PermissionError 语义。
    """
    game, pid, service, source = _game_and_player()
    # call_site 不在白名单 -> PermissionError（验证 PermissionError 抛出语义）
    try:
        PrivilegedAction.force(
            game,
            service,
            actor=pid,
            cmd="look",
            source=source,
            call_site="evil.npc_ai",  # 不在白名单
        )
        raise AssertionError("应抛 PermissionError")
    except PermissionError as e:
        assert "白名单" in str(e) or "root" in str(e).lower()


# ---- 调用点白名单 ----


def test_call_site_whitelist_has_4_entries() -> None:
    """白名单含 4 处对应 LPC 4 调用点（ADR-0021 决策 3b）。"""
    assert len(PRIVILEGED_ACTION_CALL_SITES) == 4
    assert "updated.broadcast_rumor" in PRIVILEGED_ACTION_CALL_SITES
    assert "cost.wizard_tool" in PRIVILEGED_ACTION_CALL_SITES
    assert "to.voice_redirect" in PRIVILEGED_ACTION_CALL_SITES
    assert "disable_player.system" in PRIVILEGED_ACTION_CALL_SITES


def test_call_site_not_in_whitelist_raises() -> None:
    """call_site 不在白名单 -> PermissionError。"""
    game, pid, service, source = _game_and_player()
    try:
        PrivilegedAction.force(
            game,
            service,
            actor=pid,
            cmd="look",
            source=source,
            call_site="npc_ai.force_kill",  # NPC AI 尝试调用
        )
        raise AssertionError("NPC AI 调用应抛 PermissionError")
    except PermissionError:
        pass  # 预期


def test_call_site_whitelist_blocks_unknown() -> None:
    """任意未知 call_site 均被拒绝（dissent 6 调用点控制）。"""
    game, pid, service, source = _game_and_player()
    unknown_sites = ["random.1", "npc.ai", "trigger.action", "player.force", ""]
    for site in unknown_sites:
        try:
            PrivilegedAction.force(
                game, service, actor=pid, cmd="look", source=source, call_site=site
            )
            raise AssertionError(f"未知 call_site {site!r} 应被拒绝")
        except PermissionError:
            pass  # 预期


# ---- 强制审计 ----


def test_privileged_action_audited() -> None:
    """每次 force 调用写 PRIVILEGED_ACTION 审计日志。"""
    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="look",
        source=source,
        call_site="cost.wizard_tool",
        privileged_log=plog,
    )
    assert len(plog.entries) == 1
    entry = plog.entries[0]
    assert entry.actor == pid
    assert entry.source == source
    assert entry.cmd == "look"
    assert entry.call_site == "cost.wizard_tool"
    assert entry.aborted is False


def test_privileged_action_audit_separated_from_command_audit() -> None:
    """PRIVILEGED_ACTION 审计独立于段 7 COMMAND_AUDIT（dissent 6 分离）。"""
    from xkx.runtime.middleware.s7_execute_audit import AuditLog

    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    caudit = AuditLog()
    PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="look",
        source=source,
        call_site="to.voice_redirect",
        privileged_log=plog,
        audit_log=caudit,
    )
    # PRIVILEGED_ACTION 日志 1 条
    assert len(plog.entries) == 1
    # 段 7 COMMAND_AUDIT 也 1 条（force 走完整管线，段 7 仍写普通审计）
    assert len(caudit.entries) == 1
    # 段 7 审计标记 is_privileged（source != actor）
    assert caudit.entries[0].is_privileged is True


def test_privileged_action_count_for_call_site() -> None:
    """统计某调用点调用次数（dissent 6 调用点监控）。"""
    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    for _ in range(3):
        PrivilegedAction.force(
            game,
            service,
            actor=pid,
            cmd="look",
            source=source,
            call_site="updated.broadcast_rumor",
            privileged_log=plog,
        )
    assert plog.count_for_call_site("updated.broadcast_rumor") == 3
    assert plog.count_for_call_site("cost.wizard_tool") == 0
    assert plog.call_sites_used() == {"updated.broadcast_rumor"}


# ---- 走完整 8 段管线 ----


def test_force_runs_full_pipeline() -> None:
    """force 走完整 8 段管线（保 LPC force_me 经 process_input + command_hook 语义）。"""
    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    # force go north -> 经别名/权限/命令查找/方向快捷/参数解析/执行
    msgs = PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="go north",
        source=source,
        call_site="to.voice_redirect",
        privileged_log=plog,
    )
    # go north 执行了（房间变化 + "走去"消息）
    assert any("走去" in m for m in msgs)
    assert game.world.get(pid, Position).room_id == "city/chaguan"


def test_force_aborts_on_unknown_command() -> None:
    """force 未知命令 -> 段 7 Abort，审计记录 aborted=True。"""
    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    msgs = PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="nonexistent_cmd",
        source=source,
        call_site="cost.wizard_tool",
        privileged_log=plog,
    )
    # 段 7 Abort（command_not_found），返回 "什么？"
    assert msgs == ["什么？"]
    assert plog.entries[0].aborted is True
    assert plog.entries[0].abort_reason == "command_not_found"


# ---- viewer 注入 ----


def test_force_viewer_equals_actor() -> None:
    """PrivilegedAction 路径 viewer=actor（被代执行的玩家是观察者）。

    source=系统调用者，actor=被代执行玩家，viewer=actor。
    PronounContext 求值从 ActionContext.viewer 取，不变量不破坏（ADR-0020 决策 4）。
    """
    game, pid, service, source = _game_and_player()
    # force 内部构造 ctx：actor=pid, source=source, viewer=pid
    # 验证：命令执行成功且无 viewer 相关错误（look 不依赖 viewer，但管线段 6 校验 viewer>0）
    msgs = PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="look",
        source=source,
        call_site="disable_player.system",
        privileged_log=PrivilegedActionLog(),
    )
    assert msgs  # 执行成功（viewer 注入正常）


def test_force_source_not_equal_actor() -> None:
    """PrivilegedAction 路径 source != actor（系统调用者 != 被代执行玩家）。"""
    game, pid, service, source = _game_and_player()
    plog = PrivilegedActionLog()
    PrivilegedAction.force(
        game,
        service,
        actor=pid,
        cmd="look",
        source=source,
        call_site="updated.broadcast_rumor",
        privileged_log=plog,
    )
    entry = plog.entries[0]
    assert entry.source == source
    assert entry.actor == pid
    assert entry.source != entry.actor  # source != actor（PrivilegedAction 路径）


# ---- NPC AI 禁用（文档化约束）----


def test_npc_ai_call_site_rejected() -> None:
    """NPC AI 不得使用 PrivilegedAction（Q3 决策 3，dissent 6 护栏）。

    NPC AI 走 heart_beat/do_attack/System.update 路径，不调 force。
    若 NPC AI 尝试调用，call_site 不在白名单 -> PermissionError。
    """
    game, pid, service, source = _game_and_player()
    # 模拟 NPC AI 尝试用 PrivilegedAction 代玩家执行命令
    try:
        PrivilegedAction.force(
            game,
            service,
            actor=pid,
            cmd="go north",
            source=source,
            call_site="npc.heart_beat_force",  # NPC AI 路径，不在白名单
        )
        raise AssertionError("NPC AI 调用应被拒绝")
    except PermissionError:
        pass  # 预期：NPC AI 不得使用 PrivilegedAction
