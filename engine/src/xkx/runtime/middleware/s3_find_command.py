"""段 3 命令查找（ADR-0020 决策 1，LPC COMMAND_D->find_command 逆序搜索）。

LPC ``find_command`` 从 path 尾部向头部逆序搜索（``while(i--)``），先搜到的优先。
找到命令文件后调 ``SECURITY_D->valid_cmd`` 校验，不通过返回 0（命令视为不存在）。

greenfield 映射：命令注册表（``verb -> 终端执行函数``）替代文件路径搜索。
段 3 在段 2 权限校验通过后查找命令，注入 ``ctx.command_fn``（终端执行函数）。
未找到返回 Abort（对齐 LPC 四分支全未命中返回 0，emote/channel 后置）。

**命令注册表**：由 ``commands.py`` 维护（``COMMAND_REGISTRY``），段 3 通过
``command_table`` 参数接收（避免循环依赖，调用方注入）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from xkx.runtime.action_context import Abort, ActionContext

if TYPE_CHECKING:
    from collections.abc import Callable


def find_command(
    ctx: ActionContext,
    command_table: dict[str, Any] | None = None,
) -> ActionContext | Abort:
    """段 3：命令查找（ADR-0020 决策 1）。

    在 ``command_table`` 中按 verb 查找终端执行函数。命中则注入 ``ctx.command_fn``。
    **未命中不 Abort**（返回 ctx 且 command_fn=None），让段 4 方向快捷有机会回退
    （ADR-0020 决策 1：段 4 是段 3 未命中时的方向快捷回退）。段 4 也未命中时，
    段 7 执行段 command_fn=None 才 Abort（命令不存在）。

    ``command_table`` 是 ``{verb: (game, ctx) -> list[str]}`` 映射，由调用方注入
    （通常来自 ``commands.py`` 的 ``COMMAND_REGISTRY``）。
    """
    import dataclasses

    if command_table is None:
        return ctx  # 无命令表，command_fn 保持 None，段 4/段 7 处理
    fn: Callable[..., list[str]] | None = command_table.get(ctx.verb)
    if fn is None:
        return ctx  # 未命中不短路，让段 4 方向快捷回退
    return dataclasses.replace(ctx, command_fn=fn)
