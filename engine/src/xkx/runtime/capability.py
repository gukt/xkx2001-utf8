"""CapabilityToken + PermissionService（阶段 1 Wave 2 T4，ADR-0020 决策 3）。

LPC euid/uid 字符串模型映射为不可伪造的 CapabilityToken（HS256 对称签名 + 内存吊销集合）。

**实现决策**（ADR-0020 + 02 裁决）：

- HS256 对称签名：引擎启动时生成一次性 secret（``secrets.token_bytes(32)``），进程内持有，
  不持久化（重启后所有 token 失效，玩家需重新登录）。HS256 而非 RS256：单进程无需非对称
  密钥分发，02 裁决明确不引入 JWT RS256 + Redis 黑名单。
- 不可伪造：``CapabilityToken`` 是 frozen dataclass，``signature`` 由 secret 对
  ``(subject, status, capabilities, issued_at, expires_at)`` 做 HMAC-SHA256 生成。
  段 2 权限校验先验签（``hmac.compare_digest``），签名不符则 fail-closed 拒绝。
- 内存吊销集合：``set[bytes]``（token 的 signature 哈希），玩家断线/quit/被封禁时加入。
  段 2 校验时检查 signature 是否在吊销集合中，命中则拒绝。重启后吊销集合清空（但所有
  token 也失效，等价全量吊销）。
- 能力集映射 LPC 权限模型：PLAYER -> ``cmd.std``/``cmd.skill``/``cmd.usr``；
  ADMIN -> ``cmd.adm``/``root``。exclude 优先于 authorized。
- fail-closed：token None/签名无效/已吊销/已过期/能力不足时返回拒绝，命令视为不存在。

CLAUDE.md 要求安全模块类型完整，本模块全部类型注解。

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 3
[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md) 决策 1
[02](../../../docs/xkx-arch/02-三个开放架构问题裁决.md) Q3
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WizLevel(StrEnum):
    """巫师等级（对齐 LPC securityd.c wiz_levels，从低到高）。

    高等级包含低等级权限。权限校验基于此层次。
    """

    PLAYER = "(player)"
    """普通玩家：可执行 cmds/std、cmds/skill、cmds/usr 目录命令。"""

    IMMORTAL = "(immortal)"
    APPRENTICE = "(apprentice)"
    VIRTUOSO = "(virtuoso)"
    CARETAKER = "(caretaker)"
    CREATOR = "(creator)"
    DESIGNER = "(designer)"
    WIZARD = "(wizard)"
    ARCH = "(arch)"
    ADMIN = "(admin)"
    """最高管理员：可执行 cmds/adm 目录命令，拥有全部权限。"""


# 能力常量（对齐 LPC valid_cmd 目录权限模型）
CAP_CMD_STD = "cmd.std"
CAP_CMD_SKILL = "cmd.skill"
CAP_CMD_USR = "cmd.usr"
CAP_CMD_IMM = "cmd.imm"
CAP_CMD_WIZ = "cmd.wiz"
CAP_CMD_ARCH = "cmd.arch"
CAP_CMD_ADM = "cmd.adm"
CAP_ROOT = "root"

# WizLevel -> 默认能力集（对齐 valid_cmd authorized_cmds + cmds/std/skill/usr 开放）
# 高等级包含低等级能力（LPC 权限层次）
_WIZ_CAPABILITIES: dict[WizLevel, frozenset[str]] = {
    WizLevel.PLAYER: frozenset({CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR}),
    WizLevel.IMMORTAL: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.APPRENTICE: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.VIRTUOSO: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.CARETAKER: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.CREATOR: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.DESIGNER: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM}
    ),
    WizLevel.WIZARD: frozenset(
        {CAP_CMD_STD, CAP_CMD_SKILL, CAP_CMD_USR, CAP_CMD_IMM, CAP_CMD_WIZ}
    ),
    WizLevel.ARCH: frozenset(
        {
            CAP_CMD_STD,
            CAP_CMD_SKILL,
            CAP_CMD_USR,
            CAP_CMD_IMM,
            CAP_CMD_WIZ,
            CAP_CMD_ARCH,
        }
    ),
    WizLevel.ADMIN: frozenset(
        {
            CAP_CMD_STD,
            CAP_CMD_SKILL,
            CAP_CMD_USR,
            CAP_CMD_IMM,
            CAP_CMD_WIZ,
            CAP_CMD_ARCH,
            CAP_CMD_ADM,
            CAP_ROOT,
        }
    ),
}

# 默认 session 时长（秒），对齐 LPC 玩家 session 生命周期
DEFAULT_SESSION_TTL = 3600.0


@dataclass(frozen=True, slots=True)
class CapabilityToken:
    """不可伪造的能力令牌（HS256 签名，ADR-0020 决策 3）。

    frozen dataclass，``signature`` 由 secret 对
    ``(subject, status, capabilities, issued_at, expires_at)`` 做 HMAC-SHA256 生成。
    仅由 ``PermissionService`` 构造（构造时计算签名），外部不可伪造。
    """

    subject: int
    """entity_id（LPC euid 等价）。"""

    status: WizLevel
    """巫师等级（LPC ``get_status()``）。"""

    capabilities: frozenset[str]
    """能力集（如 ``cmd.adm`` / ``root`` / ``valid_write./u/``）。"""

    issued_at: float
    """签发时间（time.time()）。"""

    expires_at: float
    """过期时间（issued_at + session_ttl）。"""

    signature: bytes
    """HS256 签名（对 subject+status+capabilities+issued_at+expires_at 的 HMAC-SHA256）。"""


class PermissionError_(PermissionError):
    """权限错误（PrivilegedAction ROOT 门控失败等）。

    复用内置 PermissionError 语义，别名便于显式捕获区分。
    """


# 审计日志条目类型（内存 ring buffer，阶段 1 不持久化）
@dataclass(frozen=True, slots=True)
class RootIssueAudit:
    """ROOT capability 签发审计（ADR-0021 决策 3c）。"""

    subject: int
    timestamp: float
    caller: str


@dataclass
class PermissionService:
    """能力令牌签发 + 校验服务（ADR-0020 决策 3 + ADR-0014 决策 1）。

    引擎启动时构造（``PermissionService()``），生成一次性 secret。进程内持有，
    不持久化。玩家登录时 ``issue_token`` 签发，断线/quit 时 ``revoke`` 吊销。

    CLAUDE.md 要求安全模块类型完整。
    """

    _secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    """HS256 对称密钥（启动期生成，进程内持有，不持久化）。"""

    _revoked: set[bytes] = field(default_factory=set)
    """内存吊销集合（token.signature 的集合，命中即拒绝）。重启后清空。"""

    _root_audit_log: list[RootIssueAudit] = field(default_factory=list)
    """ROOT capability 签发审计（ADR-0021 决策 3c，内存 ring buffer）。"""

    _root_entities: set[int] = field(default_factory=set)
    """已签发 ROOT 的实体集合（启动期固定，运行期不新增，ADR-0021 决策 3c）。"""

    def _sign(
        self,
        subject: int,
        status: WizLevel,
        capabilities: frozenset[str],
        issued_at: float,
        expires_at: float,
    ) -> bytes:
        """对 token 字段做 HMAC-SHA256 签名。"""
        # capabilities 排序后拼接，保证签名确定性（frozenset 无序）
        caps_str = ",".join(sorted(capabilities))
        msg = (
            f"{subject}|{status.value}|{caps_str}|{issued_at:.6f}|{expires_at:.6f}"
        ).encode()
        return hmac.new(self._secret, msg, hashlib.sha256).digest()

    def _token_signature(self, token: CapabilityToken) -> bytes:
        """重算 token 应有的签名（验签用）。"""
        return self._sign(
            token.subject,
            token.status,
            token.capabilities,
            token.issued_at,
            token.expires_at,
        )

    def issue_token(
        self,
        subject: int,
        status: WizLevel,
        *,
        ttl: float = DEFAULT_SESSION_TTL,
        extra_capabilities: frozenset[str] | None = None,
        exclude: frozenset[str] | None = None,
    ) -> CapabilityToken:
        """签发能力令牌。

        能力集 = ``_WIZ_CAPABILITIES[status]`` | ``extra_capabilities`` - ``exclude``。
        ``exclude`` 优先（对齐 LPC valid_cmd exclude 优先 authorized 不变量）。
        """
        caps = set(_WIZ_CAPABILITIES.get(status, frozenset()))
        if extra_capabilities:
            caps |= extra_capabilities
        if exclude:
            caps -= exclude  # exclude 优先
        now = time.time()
        token = CapabilityToken(
            subject=subject,
            status=status,
            capabilities=frozenset(caps),
            issued_at=now,
            expires_at=now + ttl,
            signature=b"",  # 占位，下面计算
        )
        sig = self._sign(subject, status, token.capabilities, now, now + ttl)
        return dataclasses.replace(token, signature=sig)

    def issue_root_token(
        self,
        subject: int,
        *,
        caller: str = "",
        ttl: float = DEFAULT_SESSION_TTL,
    ) -> CapabilityToken:
        """签发 ROOT 等价 token（ADR-0021 决策 3c，运行期仅启动期调用）。

        写一条 ``RootIssueAudit`` 审计日志。``subject`` 加入 ``_root_entities``
        （启动期固定，运行期不新增 ROOT 实体）。
        """
        token = self.issue_token(subject, WizLevel.ADMIN, ttl=ttl)
        self._root_entities.add(subject)
        self._root_audit_log.append(
            RootIssueAudit(subject=subject, timestamp=time.time(), caller=caller)
        )
        return token

    def verify_token(self, token: CapabilityToken | None) -> bool:
        """验签 + 吊销 + 过期检查（fail-closed，任一失败返回 False）。

        - None -> False（未授权）
        - 签名不符 -> False（伪造）
        - 已吊销 -> False
        - 已过期 -> False
        """
        if token is None:
            return False
        expected = self._token_signature(token)
        if not hmac.compare_digest(expected, token.signature):
            return False
        if token.signature in self._revoked:
            return False
        return time.time() < token.expires_at

    def has_capability(
        self, token: CapabilityToken | None, capability: str
    ) -> bool:
        """校验 token 有效且含指定能力（fail-closed）。

        段 2 权限校验用：先 ``verify_token``，再查 ``capabilities``。
        """
        if not self.verify_token(token):
            return False
        return capability in token.capabilities

    def revoke(self, token: CapabilityToken) -> None:
        """吊销 token（加入内存吊销集合）。玩家断线/quit/被封禁时调用。"""
        self._revoked.add(token.signature)

    def revoke_subject(self, subject: int) -> None:
        """按 subject 吊销（无法直接拿到 token 时用，遍历失效）。

        注：内存吊销集合按 signature 索引，按 subject 吊销需调用方持有 token。
        本方法为接口预留，当前实现依赖调用方在登录态维护 subject->token 映射。
        """
        # 阶段 1 最小实现：接口预留，实际吊销靠 revoke(token)
        # （subject->token 映射由登录服务维护，本模块不持有）
        return

    def is_root_entity(self, subject: int) -> bool:
        """subject 是否已签发 ROOT（ADR-0021 决策 3c，启动期固定）。"""
        return subject in self._root_entities

    def root_audit_log(self) -> list[RootIssueAudit]:
        """ROOT 签发审计日志副本（dissent 6 调用点监控）。"""
        return list(self._root_audit_log)

    def _reset_for_test(self: Any) -> None:  # noqa: PLR6301 - 测试辅助
        """测试辅助：清空吊销集合 + ROOT 审计（不影响 secret）。"""
        # type: ignore[attr-defined] - duck typing on self
        self._revoked.clear()  # type: ignore[attr-defined]
        self._root_audit_log.clear()  # type: ignore[attr-defined]
        self._root_entities.clear()  # type: ignore[attr-defined]


def capabilities_for_status(status: WizLevel) -> frozenset[str]:
    """查询某 WizLevel 的默认能力集（对齐 LPC valid_cmd 权限模型）。"""
    return _WIZ_CAPABILITIES.get(status, frozenset())
