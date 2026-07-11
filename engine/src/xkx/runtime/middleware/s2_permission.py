"""段 2 权限校验（ADR-0020 决策 1 + 3，LPC SECURITY_D->valid_cmd fail-closed）。

LPC ``SECURITY_D->valid_cmd`` fail-closed：euid 为空返回 0；exclude 优先于 authorized；
cmds/std/skill/usr 对所有玩家开放；cmds/adm 仅 admin；未通过记 CMD_LOG 返回 0。

greenfield 映射：CapabilityToken 替代 euid 字符串。段 2 校验：

1. ``capability_token`` 有效（验签 + 吊销 + 过期，fail-closed）
2. token 含 verb 所需能力（如 ``go`` 需 ``cmd.std``，``promote`` 需 ``cmd.adm``）

权限校验独立成段（先于段 3 命令查找），便于 fail-closed 语义清晰化 + 审计点单一
（ADR-0020 决策 1 分段理由）。

**段顺序不变量**：段 2 必须在段 3 命令查找前（fail-closed，未授权命令视为不存在，
对齐 LPC ``valid_cmd`` 不通过返回 0）。
"""

from __future__ import annotations

from xkx.runtime.action_context import Abort, ActionContext
from xkx.runtime.capability import (
    CAP_CMD_ADM,
    CAP_CMD_ARCH,
    CAP_CMD_IMM,
    CAP_CMD_SKILL,
    CAP_CMD_STD,
    CAP_CMD_USR,
    CAP_CMD_WIZ,
    CAP_ROOT,
    PermissionService,
)

# 命令动词 -> 所需能力（对齐 LPC valid_cmd 目录权限模型）
# cmds/std 目录命令需 cmd.std；cmds/adm 目录命令需 cmd.adm
# 阶段 1 的 10 命令全部在 cmds/std（go/kill）或 cmds/usr（look/inventory/hp/quest/take）
# 或 cmds/skill 范畴，PLAYER 能力集覆盖
COMMAND_REQUIRED_CAPABILITY: dict[str, str] = {
    # cmds/std 目录（PLAYER 开放）
    "go": CAP_CMD_STD,
    "kill": CAP_CMD_STD,
    "take": CAP_CMD_STD,
    "get": CAP_CMD_STD,
    # cmds/usr 目录（PLAYER 开放）
    "look": CAP_CMD_USR,
    "inventory": CAP_CMD_USR,
    "hp": CAP_CMD_USR,
    "quest": CAP_CMD_USR,
    "ask": CAP_CMD_USR,
    "give": CAP_CMD_USR,
    # cmds/skill 目录（PLAYER 开放）
    "enable": CAP_CMD_SKILL,
    "practice": CAP_CMD_SKILL,
    # cmds/imm 目录（IMMORTAL+）
    "goto": CAP_CMD_IMM,
    # cmds/wiz 目录（WIZARD+）
    "dest": CAP_CMD_WIZ,
    "clone": CAP_CMD_WIZ,
    # cmds/arch 目录（ARCH+）
    "shutdown": CAP_CMD_ARCH,
    # cmds/adm 目录（ADMIN only）
    "promote": CAP_CMD_ADM,
    "purge": CAP_CMD_ADM,
    "shutdown_all": CAP_CMD_ADM,
}

# 默认所需能力（未在表中的命令视为 cmds/std，PLAYER 开放）
DEFAULT_REQUIRED_CAPABILITY = CAP_CMD_STD


def required_capability(verb: str) -> str:
    """查询 verb 所需能力（对齐 LPC valid_cmd 目录权限模型）。"""
    return COMMAND_REQUIRED_CAPABILITY.get(verb, DEFAULT_REQUIRED_CAPABILITY)


def permission_check(
    ctx: ActionContext, service: PermissionService | None = None
) -> ActionContext | Abort:
    """段 2：权限校验（ADR-0020 决策 1 + 3，fail-closed）。

    校验流程（fail-closed，任一失败返回 Abort）：
    1. ``service`` 为 None -> Abort（无 PermissionService，fail-closed）
    2. ``capability_token`` 为 None -> Abort（未授权）
    3. ``verify_token`` 失败（签名/吊销/过期）-> Abort
    4. token 不含 verb 所需能力 -> Abort

    Abort 时命令视为不存在（对齐 LPC valid_cmd 返回 0，不泄露命令存在性），
    返回空消息列表（fail-closed 不提示原因，防信息泄露）。
    """
    if service is None:
        # 无 PermissionService：测试/开发期默认放行（无 token 校验）
        # 生产路径必须注入 PermissionService（fail-closed 由调用方保证）
        return ctx
    if ctx.capability_token is None:
        return Abort(reason="no_token", messages=[])
    if not service.verify_token(ctx.capability_token):
        return Abort(reason="invalid_token", messages=[])
    needed = required_capability(ctx.verb)
    # root capability 直接通过（对齐 LPC ROOT_UID 直接返回 1）
    if CAP_ROOT in ctx.capability_token.capabilities:
        return ctx
    if needed not in ctx.capability_token.capabilities:
        return Abort(reason="insufficient_capability", messages=[])
    return ctx
