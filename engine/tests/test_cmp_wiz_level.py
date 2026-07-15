"""cmp_wiz_level 单测（ADR-0057 + ADR-0020 决策 3）。

覆盖：
- fail-closed（None token 返回 -1，未授权视为最低等级不放过）
- 等级序比较（PLAYER<IMMORTAL<...<ADMIN，负数/0/正数）
- 非法 level_str 降级 PLAYER（对照 pilot 样本桩 L80-81）
- 返回差值符合 LPC ``securityd.c:173`` 语义（非规整 -1/0/1）
- do_read 门控场景（wizard_only 板 PLAYER 拒绝 / IMMORTAL 放行）
- BoardLastRead 组件 ECS 往返（bboard 迁移用法验证）

用 ``PermissionService().issue_token`` 构造真实 token（HS256 签名，非手搓）。
``cmp_wiz_level`` 是纯等级比较，不做验签/吊销/过期检查（那是 ``verify_token``
职责）；调用方需先 ``verify_token`` 再比较。

[ADR-0057](../../../docs/adr/ADR-0057-daemon-store-per-object-save.md)
[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) 决策 3
"""

from __future__ import annotations

from xkx.runtime.capability import (
    CapabilityToken,
    PermissionService,
    WizLevel,
    cmp_wiz_level,
)
from xkx.runtime.components import BoardLastRead
from xkx.runtime.ecs import World


def _token(status: WizLevel, subject: int = 1) -> CapabilityToken:
    """用 PermissionService 签发真实 token（HS256 签名，非手搓签名）。"""
    return PermissionService().issue_token(subject, status)


# ──────────────────────── fail-closed ────────────────────────


def test_none_token_returns_minus_one() -> None:
    """None token fail-closed 返回 -1（未授权视为最低等级，不放过）。"""
    assert cmp_wiz_level(None, "(immortal)") == -1
    assert cmp_wiz_level(None, "(player)") == -1


# ──────────────────────── 等级序比较 ────────────────────────


def test_player_below_immortal_negative() -> None:
    """PLAYER 等级低于 IMMORTAL -> 返回负数（不达 immortal 门槛）。"""
    token = _token(WizLevel.PLAYER)
    assert cmp_wiz_level(token, "(immortal)") < 0


def test_admin_above_player_positive() -> None:
    """ADMIN 等级高于 PLAYER -> 返回正数（超 player 门槛）。"""
    token = _token(WizLevel.ADMIN)
    assert cmp_wiz_level(token, "(player)") > 0


def test_same_level_zero() -> None:
    """同级返回 0（恰好达到门槛）。"""
    for status in WizLevel:
        token = _token(status)
        assert cmp_wiz_level(token, status.value) == 0


def test_signed_difference_matches_lpc_semantics() -> None:
    """返回差值（非规整 -1/0/1），对齐 LPC ``get_wiz_level - member_array``。

    ADMIN(9) vs PLAYER(0) -> 9；PLAYER(0) vs ADMIN(9) -> -9。
    """
    admin = _token(WizLevel.ADMIN)
    player = _token(WizLevel.PLAYER)
    assert cmp_wiz_level(admin, "(player)") == 9
    assert cmp_wiz_level(player, "(admin)") == -9


# ──────────────────────── 非法 level_str 降级 ────────────────────────


def test_invalid_level_str_degrades_to_player() -> None:
    """非法 level_str 降级 PLAYER：PLAYER vs "bogus" 等价于 PLAYER vs "(player)"。

    对照 pilot 样本桩 bboard_c_do_read.py:80-81 行为。
    """
    token = _token(WizLevel.PLAYER)
    assert cmp_wiz_level(token, "bogus") == cmp_wiz_level(token, "(player)")
    assert cmp_wiz_level(token, "bogus") == 0


def test_invalid_level_str_immortal_still_above_player() -> None:
    """非法 level_str 降级 PLAYER：IMMORTAL 仍高于降级后的 PLAYER 门槛。"""
    token = _token(WizLevel.IMMORTAL)
    assert cmp_wiz_level(token, "bogus") > 0


# ──────────────────────── do_read 门控场景 ────────────────────────


def test_do_read_gate_mortal_blocked() -> None:
    """wizard_only 板门控：PLAYER 比较 immortal 门槛 < 0 -> 拒绝窥视。

    对照 bboard.c:184 ``if (wizard_only && cmp_wiz_level(this_player(),
    "(immortal)") < 0)``：cmp<0 即"非 immortal 拒绝"。
    """
    player_token = _token(WizLevel.PLAYER)
    blocked = cmp_wiz_level(player_token, "(immortal)") < 0
    assert blocked is True


def test_do_read_gate_immortal_allowed() -> None:
    """wizard_only 板门控：IMMORTAL 比较 immortal 门槛 >= 0 -> 放行读帖。"""
    immortal_token = _token(WizLevel.IMMORTAL)
    allowed = cmp_wiz_level(immortal_token, "(immortal)") >= 0
    assert allowed is True


def test_do_read_gate_admin_allowed() -> None:
    """wizard_only 板门控：ADMIN 远高于 immortal 门槛 -> 放行。"""
    admin_token = _token(WizLevel.ADMIN)
    assert cmp_wiz_level(admin_token, "(immortal)") > 0


# ──────────────────────── BoardLastRead 组件 ECS 往返 ────────────────────────


def test_board_last_read_default_empty() -> None:
    """BoardLastRead 默认 records 为空 dict。"""
    rec = BoardLastRead()
    assert rec.records == {}


def test_board_last_read_world_roundtrip() -> None:
    """BoardLastRead 经 world.add/get 往返一致（bboard 迁移用法）。

    对照 pilot 样本桩 bboard_c_do_read.py:119/128 用法：先 get 判 None，
    无则 add 新建，再写 records。
    """
    world = World()
    eid = world.new_entity()
    # 初始无组件
    assert world.get(eid, BoardLastRead) is None
    # 写入读帖记录
    world.add(eid, BoardLastRead(records={"city_board": 1000}))
    rec = world.get(eid, BoardLastRead)
    assert rec is not None
    assert rec.records == {"city_board": 1000}


def test_board_last_read_records_mutable_update() -> None:
    """BoardLastRead.records 可原地更新（bboard 读帖后写回新时间戳）。"""
    world = World()
    eid = world.new_entity()
    world.add(eid, BoardLastRead(records={"b1": 100}))
    rec = world.get(eid, BoardLastRead)
    assert rec is not None
    # 读更新的帖后写回更大时间戳
    rec.records["b1"] = 2000
    rec.records["b2"] = 500
    assert world.get(eid, BoardLastRead).records == {"b1": 2000, "b2": 500}
