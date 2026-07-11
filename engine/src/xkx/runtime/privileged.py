"""PrivilegedAction.force：force_me 保真让步（阶段 1 Wave 2 T4，ADR-0020 决策 4）。

LPC ``force_me`` 是特权操作（``geteuid(previous_object())==ROOT_UID`` 门控），4 个真实
调用点：``updated.c:177`` 强制传闻广播、``cost.c:18`` 巫师工具、``to.c:20-21`` 语音重定向。

greenfield 映射为 ``PrivilegedAction.force``（Command 变体，02 Q3 决策 6 + 最强反论回应），
显式承认是保真让步--边界在 force_me 处妥协以保 LPC 保真。

**设计**（ADR-0020 决策 4）：

- **ROOT 门控**：``source`` 必须持 ``root`` capability（对齐 LPC
  ``geteuid(previous_object())==ROOT_UID``），否则 raise ``PermissionError``（非静默拒绝，
  因 PrivilegedAction 是系统级 API，误调是 bug）。
- **强制审计**：每次调用写一条 ``PRIVILEGED_ACTION`` 审计日志（actor/source/cmd/
  timestamp/result 摘要），独立于段 7 普通审计，便于 dissent 6 "靠审计/限制调用点"监控。
- **走完整 8 段管线**：不绕过管线，构造 ``capability_token=ROOT_TOKEN`` 的 ActionContext
  注入段 0，走完整 8 段（保 LPC ``force_me`` 经 ``process_input`` + ``command_hook`` 语义）。
- **viewer 注入**：PrivilegedAction 路径下 viewer=actor（被代执行的玩家是观察者），
  source=系统调用者。PronounContext 求值仍从 ActionContext.viewer 取，不变量不破坏。

**dissent 6 护栏**（ADR-0020 决策 4 + ADR-0021 决策 3b）：

- 调用点白名单：``PRIVILEGED_ACTION_CALL_SITES`` 登记 4 处对应 LPC 4 调用点。
  阶段 1 验收时 grep 代码库 ``PrivilegedAction.force`` 调用点数量，与白名单比对。
- NPC AI 不得使用（Q3 决策 3）：NPC AI 走 heart_beat/do_attack/System.update 路径。
- 触发器不得使用（Q3 决策 5）：DSL 层1 触发器的 action 是 Effect 账本附加到父 Command。

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 4
[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md) 决策 3b
[05](../../../docs/xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xkx.runtime.action_context import Abort, ActionContext, new_context
from xkx.runtime.capability import (
    CAP_ROOT,
    PermissionService,
)

if TYPE_CHECKING:
    from xkx.runtime.commands import Game
    from xkx.runtime.middleware.s7_execute_audit import AuditLog


# PrivilegedAction.force 调用点白名单（ADR-0021 决策 3b，对应 LPC 4 调用点）
# 新增调用点需 ADR 记录理由（为何不能用 System.update 替代）
PRIVILEGED_ACTION_CALL_SITES: frozenset[str] = frozenset({
    "updated.broadcast_rumor",  # LPC updated.c:177 强制传闻广播
    "cost.wizard_tool",  # LPC cost.c:18 巫师工具
    "to.voice_redirect",  # LPC to.c:20-21 语音重定向
    "disable_player.system",  # LPC disable_player 等价（系统禁用玩家）
})


@dataclass(frozen=True, slots=True)
class PrivilegedActionAudit:
    """PrivilegedAction 审计日志条目（ADR-0020 决策 4，独立于 COMMAND_AUDIT）。

    dissent 6 "靠审计/限制调用点"监控用：查此日志可区分"系统代执行"与"玩家意图"。
    """

    actor: int
    source: int
    cmd: str
    call_site: str
    timestamp: float
    result_summary: str
    aborted: bool
    abort_reason: str = ""


@dataclass
class PrivilegedActionLog:
    """PrivilegedAction 审计日志（内存 ring buffer，ADR-0020 决策 4）。

    独立于段 7 ``AuditLog``，便于 dissent 6 监控 force_me 调用点增长侵蚀边界。
    """

    entries: list[PrivilegedActionAudit] = field(default_factory=list)
    max_size: int = 256

    def append(self, entry: PrivilegedActionAudit) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_size:
            self.entries.pop(0)

    def count_for_call_site(self, call_site: str) -> int:
        """统计某调用点的调用次数（dissent 6 调用点监控）。"""
        return sum(1 for e in self.entries if e.call_site == call_site)

    def call_sites_used(self) -> set[str]:
        """已使用的调用点集合（验收时与白名单比对）。"""
        return {e.call_site for e in self.entries}


class PrivilegedAction:
    """force_me 保真让步（ADR-0020 决策 4，ROOT 门控 + 强制审计）。

    系统级 API，非玩家路径。NPC AI / 触发器不得调用（dissent 6 护栏）。
    """

    @staticmethod
    def force(
        game: Game,
        permission_service: PermissionService,
        actor: int,
        cmd: str,
        source: int,
        *,
        call_site: str,
        privileged_log: PrivilegedActionLog | None = None,
        audit_log: AuditLog | None = None,
        seq: int = 0,
    ) -> list[str]:
        """强制执行命令（对齐 LPC force_me，ROOT 门控 + 强制审计）。

        ``actor`` 是被代执行的玩家（viewer=actor），``source`` 是系统调用者（须持 root）。
        ``call_site`` 必须在 ``PRIVILEGED_ACTION_CALL_SITES`` 白名单中。

        走完整 8 段管线（注入 ROOT_TOKEN），不绕过刷屏检测/别名/权限校验/命令查找/审计。
        """
        # 1. ROOT 门控：source 必须持 root capability（对齐 LPC geteuid==ROOT_UID）
        source_token = permission_service.issue_root_token(
            source, caller=call_site
        )
        if not permission_service.has_capability(source_token, CAP_ROOT):
            raise PermissionError(
                f"PrivilegedAction.force ROOT 门控失败：source={source} "
                f"无 root capability（call_site={call_site}）"
            )

        # 2. 调用点白名单校验（dissent 6 护栏）
        if call_site not in PRIVILEGED_ACTION_CALL_SITES:
            raise PermissionError(
                f"PrivilegedAction.force 调用点 {call_site!r} 未在白名单中"
                f"（合法: {sorted(PRIVILEGED_ACTION_CALL_SITES)}），"
                "新增调用点需 ADR 记录理由"
            )

        # 3. 构造 ActionContext（ROOT_TOKEN 注入，viewer=actor，source=系统调用者）
        # 拆分 cmd 为 verb + raw_args
        cmd_stripped = cmd.strip()
        parts = cmd_stripped.split(None, 1)
        verb = parts[0] if parts else ""
        raw_args = parts[1] if len(parts) > 1 else ""

        # 为 actor 签发临时 token（PrivilegedAction 路径下 actor 走 ROOT 权限）
        actor_token = permission_service.issue_root_token(actor, caller=call_site)
        ctx = new_context(
            verb=verb,
            raw_args=raw_args,
            actor=actor,
            source=source,  # 系统调用者（不等 actor）
            viewer=actor,  # 被代执行的玩家是观察者
            capability_token=actor_token,
            seq=seq,
        )

        # 4. 走完整 8 段管线（保 LPC force_me 经 process_input + command_hook 语义）
        from xkx.runtime.commands import run_pipeline

        result_ctx = run_pipeline(
            game,
            ctx,
            permission_service=permission_service,
            privileged_log=privileged_log,
            audit_log=audit_log,
            privileged_call_site=call_site,
        )

        # 5. 强制审计（PRIVILEGED_ACTION，独立于段 7 COMMAND_AUDIT）
        aborted = isinstance(result_ctx, Abort)
        result_summary = ""
        abort_reason = ""
        if aborted:
            assert isinstance(result_ctx, Abort)  # narrowing
            abort_reason = result_ctx.reason
            result_summary = " ".join(result_ctx.messages)
            messages: list[str] = list(result_ctx.messages)
        else:
            assert isinstance(result_ctx, ActionContext)
            messages = list(result_ctx.result)
            result_summary = " ".join(messages)[:80]

        if privileged_log is not None:
            privileged_log.append(
                PrivilegedActionAudit(
                    actor=actor,
                    source=source,
                    cmd=cmd,
                    call_site=call_site,
                    timestamp=time.time(),
                    result_summary=result_summary,
                    aborted=aborted,
                    abort_reason=abort_reason,
                )
            )

        return messages
