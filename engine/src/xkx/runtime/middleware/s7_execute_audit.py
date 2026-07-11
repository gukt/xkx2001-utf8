"""段 7 执行 + 审计（ADR-0020 决策 1 + 5）。

LPC ``call_other(file, "main", this_object(), arg)`` 同步执行命令 main 函数
（保 LPC 同步语义，68771 处调用栈）+ ``CMD_LOG`` 审计日志。

段 7 执行 ``ctx.command_fn``（段 3/段 4 注入的终端执行函数），返回结果消息写入
``ctx.result``，并写一条 ``COMMAND_AUDIT`` 审计日志（内存 ring buffer，阶段 1 不持久化）。

**审计日志**（ADR-0020 决策 5）：

- ``COMMAND_AUDIT``：普通命令审计（actor/verb/args/target/result 摘要/timestamp/seq）。
- 与 ``PRIVILEGED_ACTION`` 审计分离（PrivilegedAction 路径独立审计，便于 dissent 6
  监控"系统代执行"与"玩家意图"）。
- 内存 ring buffer，阶段 1 不持久化（外部玩家测试前才需持久化审计轨迹，04 §六后置）。

**同步执行**（ADR-0020 不做清单）：段 7 同步返回结果（保 LPC ``call_other`` 同步语义），
不做异步命令队列（Q3 裁决"反对默认异步化"）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xkx.runtime.action_context import Abort, ActionContext

if TYPE_CHECKING:
    from xkx.runtime.commands import Game


@dataclass(frozen=True, slots=True)
class CommandAudit:
    """段 7 普通命令审计日志条目（ADR-0020 决策 5）。

    内存 ring buffer，阶段 1 不持久化。
    """

    seq: int
    actor: int
    verb: str
    args: str
    target: int | None
    result_summary: str
    timestamp: float
    is_privileged: bool = False
    """是否 PrivilegedAction 路径（系统代执行），dissent 6 监控用。"""


@dataclass
class AuditLog:
    """命令审计日志（内存 ring buffer，ADR-0020 决策 5）。

    阶段 1 不持久化，外部玩家测试前才需持久化审计轨迹（04 §六后置）。
    """

    entries: list[CommandAudit] = field(default_factory=list)
    max_size: int = 1024

    def append(self, entry: CommandAudit) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_size:
            self.entries.pop(0)

    def clear(self) -> None:
        self.entries.clear()

    def latest(self, n: int = 10) -> list[CommandAudit]:
        return self.entries[-n:]


def _summarize_result(messages: list[str], max_len: int = 80) -> str:
    """结果摘要（首条消息截断，便于审计日志可读）。"""
    if not messages:
        return ""
    first = messages[0]
    if len(first) <= max_len:
        return first
    return first[:max_len] + "..."


def execute_audit(
    ctx: ActionContext,
    game: Game | None = None,
    audit_log: AuditLog | None = None,
) -> ActionContext | Abort:
    """段 7：执行 + 审计（ADR-0020 决策 1 + 5）。

    执行流程：
    1. ``ctx.command_fn`` 为 None -> Abort（命令未找到，段 3/段 4 未命中）
    2. 调用 ``command_fn(game, ctx)`` 同步执行（保 LPC ``call_other`` 同步语义）
    3. 结果消息写入 ``ctx.result``
    4. 写 ``COMMAND_AUDIT`` 审计日志（actor/verb/args/target/result 摘要/timestamp/seq）

    执行异常捕获为 Abort（阶段 1 最小：命令函数不应抛异常，抛异常视为命令失败）。
    """
    import dataclasses

    if ctx.command_fn is None:
        # 命令未找到（段 3 未命中 + 段 4 非方向快捷）
        # 对齐 LPC notify_fail 默认提示（非 fail-closed 空消息，因命令查找失败非权限问题）
        return Abort(reason="command_not_found", messages=["什么？"])
    if game is None:
        return Abort(reason="no_game", messages=[])

    try:
        # 终端执行函数签名：(game, ctx) -> list[str]
        # commands.py 的 COMMAND_REGISTRY 注册的是适配后的 (game, ctx) -> list[str]
        # （原始 (game, pid, arg) 签名通过 adapter 转换为 (game, ctx) -> list[str]）
        messages: list[str] = ctx.command_fn(game, ctx)
    except Exception as exc:  # noqa: BLE001 - 阶段 1 最小：命令异常视为失败
        return Abort(
            reason="execution_error",
            messages=[f"命令执行出错：{exc}"],
        )

    new_ctx = dataclasses.replace(ctx, result=list(messages))

    # 审计日志（内存 ring buffer，ADR-0020 决策 5）
    if audit_log is not None:
        audit_log.append(
            CommandAudit(
                seq=ctx.seq,
                actor=ctx.actor,
                verb=ctx.verb,
                args=ctx.raw_args,
                target=ctx.target,
                result_summary=_summarize_result(messages),
                timestamp=time.time(),
                is_privileged=ctx.source != ctx.actor,
            )
        )

    return new_ctx
