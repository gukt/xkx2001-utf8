"""命令 8 段中间件管线（阶段 1 Wave 2 T4，ADR-0020 决策 1）。

8 段中间件按 LPC 命令分发管线真实顺序分段，每段是纯函数
``(ctx) -> ActionContext | Abort``，短路求值（任一段 Abort 则管线终止）。

| 段 | 名称 | LPC 对照 | 职责 |
|---|---|---|---|
| 0 | 刷屏检测 | ``process_input`` cnt 计数 + CMDS_PER_TICK=20 | tick 内命令计数，超阈值扣气/精 |
| 1 | 别名解析 | ``process_input`` 历史替换 + 自定义别名 + 全局方向别名 | 历史替换 + 全局方向别名 |
| 2 | 权限校验 | ``SECURITY_D->valid_cmd`` fail-closed | CapabilityToken 校验 |
| 3 | 命令查找 | ``COMMAND_D->find_command`` 逆序搜索 | 按命令表查找终端执行函数 |
| 4 | 方向快捷 | ``command_hook`` 分支 A | 无参方向名重写为 ``go <direction>`` |
| 5 | 参数解析 | 命令 main 函数入参 | 引号感知 tokenizer |
| 6 | previous_object 注入 | ``this_player()`` 信任链 | actor/source/target 就位 |
| 7 | 执行 + 审计 | ``call_other`` + CMD_LOG | 同步执行 + 审计日志 |

**段顺序不变量**（ADR-0020）：

- 段 0 刷屏检测必须最先（防刷屏命令绕过权限校验）
- 段 2 权限校验在段 3 命令查找前（fail-closed，未授权命令视为不存在）
- 段 6 previous_object 注入在段 7 执行前（执行段依赖 actor/source/target）

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 1
"""

from __future__ import annotations

from xkx.runtime.middleware.s0_flood_check import flood_check
from xkx.runtime.middleware.s1_alias import alias_resolve
from xkx.runtime.middleware.s2_permission import permission_check
from xkx.runtime.middleware.s3_find_command import find_command
from xkx.runtime.middleware.s4_direction import direction_shortcut
from xkx.runtime.middleware.s5_parse_args import parse_args
from xkx.runtime.middleware.s6_inject_context import inject_context
from xkx.runtime.middleware.s7_execute_audit import execute_audit

# 8 段管线顺序（不变量，ADR-0020 决策 1）
PIPELINE: list = [
    flood_check,  # 段 0 刷屏检测
    alias_resolve,  # 段 1 别名解析
    permission_check,  # 段 2 权限校验
    find_command,  # 段 3 命令查找
    direction_shortcut,  # 段 4 方向快捷
    parse_args,  # 段 5 参数解析
    inject_context,  # 段 6 previous_object 注入
    execute_audit,  # 段 7 执行 + 审计
]

__all__ = [
    "PIPELINE",
    "flood_check",
    "alias_resolve",
    "permission_check",
    "find_command",
    "direction_shortcut",
    "parse_args",
    "inject_context",
    "execute_audit",
]
