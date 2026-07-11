"""段 4 方向快捷（ADR-0020 决策 1，LPC command_hook 分支 A）。

LPC ``command_hook`` 分支 A：``arg==""`` 且房间有对应 exit -> 隐式 ``go``。
玩家输入方向名（如 ``north``）且无参数时，若房间有对应 exit，直接执行 ``go`` 命令。

新引擎将其拆为段 4（独立于段 3 命令查找）：段 3 未命中普通命令时，段 4 检查 verb
是否是方向名且无参，若是则重写为 ``go <direction>`` 并重新查找 ``go`` 命令。

**段顺序**（ADR-0020 决策 1 分段理由）：段 4 在段 3 后、段 5 参数解析前。方向快捷
本质是"verb 是方向名且无参时重写为 go"的别名变体，与段 1 全局方向别名语义连贯。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from xkx.runtime.action_context import Abort, ActionContext

if TYPE_CHECKING:
    from xkx.runtime.commands import Game

# 方向名集合（LPC go.c default_dirs + 常见方向）
DIRECTION_NAMES: frozenset[str] = frozenset({
    "north", "south", "east", "west", "northup", "southup",
    "eastup", "westup", "northdown", "southdown", "eastdown",
    "westdown", "northeast", "northwest", "southeast", "southwest",
    "up", "down", "out", "enter",
})


def direction_shortcut(
    ctx: ActionContext,
    game: Game | None = None,
    command_table: dict[str, Any] | None = None,
) -> ActionContext | Abort:
    """段 4：方向快捷（ADR-0020 决策 1，LPC command_hook 分支 A）。

    段 3 已查找命令（``ctx.command_fn`` 可能已注入）。若段 3 已命中（command_fn 非空），
    本段直接放行（普通命令优先于方向快捷）。

    若段 3 未命中（command_fn 为 None）且 verb 是方向名且无参：
    - 重写为 ``go <direction>``，重新查 ``go`` 命令

    阶段 1 最小：不查房间 exit（go 命令自身会校验），直接重写 + 重查命令表。
    """
    import dataclasses

    # 段 3 已命中普通命令 -> 放行
    if ctx.command_fn is not None:
        return ctx

    # verb 不是方向名 -> 放行（段 3 未命中 + 非方向，段 7 会 Abort）
    if ctx.verb not in DIRECTION_NAMES:
        return ctx

    # 方向快捷：无参方向名重写为 go <direction>
    if ctx.raw_args:
        # 有参数的方向名（如 "north foo"）不是方向快捷，放行
        return ctx

    # 重写为 go <direction>
    direction = ctx.verb
    new_ctx = dataclasses.replace(
        ctx, verb="go", raw_args=direction, command_fn=None
    )

    # 重新查 go 命令（若 command_table 可用）
    if command_table is not None:
        go_fn = command_table.get("go")
        if go_fn is not None:
            return dataclasses.replace(new_ctx, command_fn=go_fn)
    return new_ctx
