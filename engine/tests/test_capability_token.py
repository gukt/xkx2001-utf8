"""CapabilityToken + PermissionService 测试（阶段 1 Wave 2 T4，ADR-0020 决策 3）。

覆盖：
- HS256 签发/验签（合法 token 验证通过）
- 内存吊销（revoke 后 verify_token False）
- fail-closed（None/伪造/已吊销/已过期 token 拒绝）
- 能力集映射 LPC 权限模型（PLAYER -> cmd.std/skill/usr；ADMIN -> cmd.adm/root）
- exclude 优先 authorized（exclude 掉的能力不出现）
- hypothesis 不可伪造性（随机篡改 token 字段后验签失败）

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 3
[02](../../../docs/xkx-arch/02-三个开放架构问题裁决.md) Q3
"""

from __future__ import annotations

import time
from dataclasses import replace

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime.capability import (
    CAP_CMD_ADM,
    CAP_CMD_SKILL,
    CAP_CMD_STD,
    CAP_CMD_USR,
    CAP_ROOT,
    DEFAULT_SESSION_TTL,
    PermissionService,
    WizLevel,
    capabilities_for_status,
)

# ---- HS256 签发/验签 ----


def test_issue_and_verify_token() -> None:
    """合法 token 验签通过。"""
    service = PermissionService()
    token = service.issue_token(42, WizLevel.PLAYER)
    assert service.verify_token(token) is True
    assert token.subject == 42
    assert token.status == WizLevel.PLAYER
    assert token.signature  # 非空


def test_two_services_different_secrets() -> None:
    """不同 PermissionService 的 secret 不同，token 互不通用。"""
    s1 = PermissionService()
    s2 = PermissionService()
    token = s1.issue_token(1, WizLevel.PLAYER)
    assert s1.verify_token(token) is True
    # s2 的 secret 不同，签名校验失败
    assert s2.verify_token(token) is False


# ---- 内存吊销 ----


def test_revoke_token_rejected() -> None:
    """revoke 后 token 验签失败（内存吊销集合）。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.PLAYER)
    assert service.verify_token(token) is True
    service.revoke(token)
    assert service.verify_token(token) is False


# ---- fail-closed ----


def test_verify_none_token_fail_closed() -> None:
    """None token fail-closed 拒绝。"""
    service = PermissionService()
    assert service.verify_token(None) is False
    assert service.has_capability(None, CAP_CMD_STD) is False


def test_verify_forged_token_fail_closed() -> None:
    """伪造签名 fail-closed 拒绝（hmac.compare_digest 不等）。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.PLAYER)
    # 篡改签名
    forged_sig = bytes(b ^ 0xFF for b in token.signature)
    forged = replace(token, signature=forged_sig)
    assert service.verify_token(forged) is False


def test_verify_expired_token_fail_closed() -> None:
    """过期 token fail-closed 拒绝。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.PLAYER, ttl=0.01)
    assert service.verify_token(token) is True
    time.sleep(0.02)
    assert service.verify_token(token) is False


def test_has_capability_fail_closed_on_invalid_token() -> None:
    """无效 token 的 has_capability 返回 False（fail-closed）。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.PLAYER)
    service.revoke(token)
    assert service.has_capability(token, CAP_CMD_STD) is False


# ---- 能力集映射 LPC 权限模型 ----


def test_player_capabilities() -> None:
    """PLAYER 能力集含 cmd.std/skill/usr（对齐 valid_cmd cmds/std/skill/usr 开放）。"""
    caps = capabilities_for_status(WizLevel.PLAYER)
    assert CAP_CMD_STD in caps
    assert CAP_CMD_SKILL in caps
    assert CAP_CMD_USR in caps
    assert CAP_CMD_ADM not in caps
    assert CAP_ROOT not in caps


def test_admin_capabilities() -> None:
    """ADMIN 能力集含 cmd.adm + root（对齐 ROOT_UID 直接返回 1）。"""
    caps = capabilities_for_status(WizLevel.ADMIN)
    assert CAP_CMD_ADM in caps
    assert CAP_ROOT in caps
    # ADMIN 包含 PLAYER 的能力
    assert CAP_CMD_STD in caps
    assert CAP_CMD_SKILL in caps
    assert CAP_CMD_USR in caps


def test_admin_token_passes_adm_check() -> None:
    """ADMIN token 含 root capability，has_capability(cmd.adm) True。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.ADMIN)
    assert service.has_capability(token, CAP_CMD_ADM) is True
    assert service.has_capability(token, CAP_ROOT) is True


def test_player_token_fails_adm_check() -> None:
    """PLAYER token 不含 cmd.adm，has_capability(cmd.adm) False。"""
    service = PermissionService()
    token = service.issue_token(1, WizLevel.PLAYER)
    assert service.has_capability(token, CAP_CMD_ADM) is False
    assert service.has_capability(token, CAP_CMD_STD) is True


# ---- exclude 优先 authorized ----


def test_exclude_overrides_authorized() -> None:
    """exclude 优先 authorized：exclude 掉的能力不出现（对齐 valid_cmd exclude 优先）。"""
    service = PermissionService()
    token = service.issue_token(
        1,
        WizLevel.PLAYER,
        exclude=frozenset({CAP_CMD_USR}),
    )
    assert CAP_CMD_USR not in token.capabilities  # exclude 生效
    assert CAP_CMD_STD in token.capabilities  # 其他能力保留
    assert service.has_capability(token, CAP_CMD_USR) is False
    assert service.has_capability(token, CAP_CMD_STD) is True


def test_extra_capabilities_merged() -> None:
    """extra_capabilities 合并到能力集。"""
    service = PermissionService()
    token = service.issue_token(
        1,
        WizLevel.PLAYER,
        extra_capabilities=frozenset({"custom.cap"}),
    )
    assert "custom.cap" in token.capabilities
    assert CAP_CMD_STD in token.capabilities  # 默认能力保留


# ---- ROOT 签发审计 ----


def test_issue_root_token_audited() -> None:
    """issue_root_token 写 ROOT_ISSUE 审计日志（ADR-0021 决策 3c）。"""
    service = PermissionService()
    token = service.issue_root_token(99, caller="updated.broadcast_rumor")
    assert service.is_root_entity(99) is True
    assert CAP_ROOT in token.capabilities
    log = service.root_audit_log()
    assert len(log) == 1
    assert log[0].subject == 99
    assert log[0].caller == "updated.broadcast_rumor"


def test_root_audit_log_multiple_issues() -> None:
    """多次 ROOT 签发均记审计。"""
    service = PermissionService()
    service.issue_root_token(1, caller="site_a")
    service.issue_root_token(2, caller="site_b")
    service.issue_root_token(1, caller="site_a")  # 重复 subject
    log = service.root_audit_log()
    assert len(log) == 3
    assert service.is_root_entity(1) is True
    assert service.is_root_entity(2) is True
    assert service.is_root_entity(999) is False  # 未签发


# ---- 签名确定性 ----


def test_signature_deterministic() -> None:
    """同 service + 同字段签名一致（HS256 对称签名确定性）。"""
    service = PermissionService()
    # 用相同 issued_at/expires_at 确保签名一致
    token1 = service.issue_token(1, WizLevel.PLAYER)
    # issue_token 用 time.time()，两次调用时间几乎相同但可能差微秒
    # 核心验证：同 service 对同 token 重算签名一致
    from xkx.runtime.capability import capabilities_for_status

    caps = capabilities_for_status(WizLevel.PLAYER)
    sig = service._sign(  # noqa: SLF001 - 测试内部签名
        1, WizLevel.PLAYER, caps, token1.issued_at, token1.expires_at
    )
    assert sig == token1.signature


# ---- hypothesis：不可伪造性 ----


@given(
    subject=st.integers(min_value=1, max_value=10000),
    status=st.sampled_from(list(WizLevel)),
    flip_byte=st.integers(min_value=0, max_value=31),
)
@settings(max_examples=50)
def test_forged_signature_rejected(
    subject: int, status: WizLevel, flip_byte: int
) -> None:
    """hypothesis：篡改 signature 任一字节后验签失败（不可伪造性）。"""
    service = PermissionService()
    token = service.issue_token(subject, status)
    assert service.verify_token(token) is True
    # 翻转 signature 的某一位
    sig_list = bytearray(token.signature)
    sig_list[flip_byte % len(sig_list)] ^= 0x01
    forged = replace(token, signature=bytes(sig_list))
    assert service.verify_token(forged) is False


@given(
    subject=st.integers(min_value=1, max_value=10000),
    status=st.sampled_from(list(WizLevel)),
)
@settings(max_examples=30)
def test_cross_service_token_rejected(subject: int, status: WizLevel) -> None:
    """hypothesis：A service 签发的 token 在 B service 验签失败（secret 隔离）。"""
    s1 = PermissionService()
    s2 = PermissionService()
    token = s1.issue_token(subject, status)
    # s1 验证通过
    assert s1.verify_token(token) is True
    # s2 验证失败（secret 不同）
    assert s2.verify_token(token) is False


@given(
    subject=st.integers(min_value=1, max_value=10000),
)
@settings(max_examples=20)
def test_token_ttl_expiry(subject: int) -> None:
    """hypothesis：ttl=0 的 token 立即过期（fail-closed）。"""
    service = PermissionService()
    token = service.issue_token(subject, WizLevel.PLAYER, ttl=0.0)
    # expires_at = issued_at + 0，time.time() 已 >= expires_at
    assert service.verify_token(token) is False


def test_default_session_ttl_positive() -> None:
    """DEFAULT_SESSION_TTL 为正数（session 时长合理）。"""
    assert DEFAULT_SESSION_TTL > 0
