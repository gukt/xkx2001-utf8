"""层 H-2：第二梯队守护进程 -- 规格提取测试（ADR-0055 Batch 1）。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="H-2"、lpc_files 含 4 个 daemon 文件
- 层 ID 不与现有 9 层 A-I 冲突
- FunctionSpec 签名/前置/后置/不变量/副作用结构完整
- 副作用 order 从 1 连续递增（hypothesis）
- cross_layer_refs 目标层 ID 合法（A-I 范围内）
- 关键领域断言：货币换算、频道配置驱动、反作弊随机性、别名纯字符串转换
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_h_daemons import LAYER_SPEC as LAYER_H_DAEMONS
from xkx.spec.layer_h_daemons2 import (
    CURRENCY_RATES,
    GLOBAL_ALIASES,
    LAYER_SPEC,
    MAX_CASHFLOW_ALLOWED,
)

# 现有 9 层 layer_id 集合（A-I）
EXISTING_LAYER_IDS = set("ABCDEFGHI")
# cross_layer_refs 中 "层 X" 模式的正则
_LAYER_REF_RE = re.compile(r"层\s*([A-I])")


# ---------------------------------------------------------------------------
# smoke 测试
# ---------------------------------------------------------------------------


class TestSmoke:
    """LAYER_SPEC 基本可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id(self) -> None:
        assert LAYER_SPEC.layer_id == "H-2"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "第二梯队守护进程"

    def test_lpc_files_complete(self) -> None:
        expected = {
            "adm/daemons/channeld.c",
            "adm/daemons/moneyd.c",
            "adm/daemons/updated.c",
            "adm/daemons/aliasd.c",
            "adm/daemons/fingerd.c",
            "adm/daemons/band.c",
            "adm/daemons/regband.c",
            "adm/daemons/regid.c",
            "adm/daemons/marryd.c",
            "adm/daemons/emoted.c",
            "adm/daemons/inquiryd.c",
            "adm/daemons/pigd.c",
            "adm/daemons/profiled.c",
            "adm/daemons/adsd.c",
            "adm/daemons/editord.c",
            "adm/daemons/weapond.c",
            "adm/daemons/languaged.c",
            "adm/daemons/virtuald.c",
        }
        assert set(LAYER_SPEC.lpc_files) == expected

    def test_function_spec_count(self) -> None:
        assert len(LAYER_SPEC.function_specs) == 81

    def test_expected_function_names(self) -> None:
        names = {spec.signature.name for spec in LAYER_SPEC.function_specs}
        expected = {
            # CHANNEL_D
            "do_channel",
            "filter_listener",
            "register_relay_channel",
            "remove_addresses",
            # MONEY_D
            "money_str",
            "price_str",
            "pay_player",
            "player_pay",
            "player_dealer_pay",
            "player_bank_pay",
            "player_job_pay",
            "query_avalible_xkx_cashflow",
            "query_total_xkx_cashflow",
            # UPDATE_D
            "login_check",
            "inventory_check",
            # ALIAS_D
            "get_current_alias",
            "process_global_alias",
            # FINGER_D
            "ip_cmp",
            "age_string",
            "finger_all",
            "finger_user",
            "remote_finger_user",
            "acquire_login_ob",
            "get_killer",
            # BAN_D
            "load_sites",
            "is_banned",
            "print",
            "add",
            "remove",
            # REGBAN_D
            # load_sites/is_banned/print/add/remove 与 BAN_D 同名，按 LPC 文件区分
            "check",
            # REGI_D
            "is_banned_email",
            "random_password",
            "register_char",
            "change_password",
            "change_name",
            "change_id",
            # MARRY_D
            "setup_marriage",
            "break_marriage",
            "validate_marriage",
            # EMOTE_D
            "query_save_file",
            "normal_color",
            "do_emote",
            "do_intermud_emote",
            "set_emote",
            "delete_emote",
            "query_emote",
            "query_all_emote",
            # INQUIRY_D
            "parse_inquiry",
            # PIG_D
            "is_validcard",
            "is_validbid",
            "is_special",
            "card_str",
            "refresh",
            "has_suit",
            "has_card",
            "shuffle",
            "card_cmp4",
            "order_turn",
            "count_score",
            # PROFILE_D
            "log_command",
            "make_profile",
            "sort_entry",
            # ADS_D
            "init_ads_phase",
            "update_ads_phase",
            "read_table",
            "query_ads_phase",
            # EDITOR_D (add 已在 BAN_D 中枚举，集合去重)
            "get_file_num",
            # WEAPON_D
            "query_action",
            "throw_weapon",
            "bash_weapon",
            # LANGUAGE_D
            "GB2Big5",
            "Big52GB",
            "toBig5",
            "toGB",
            # VIRTUAL_D
            "compile_object",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# layer_id 唯一性
# ---------------------------------------------------------------------------


class TestLayerUniqueness:
    """LayerSpec layer_id 唯一 + 不与现有层 H 重名。"""

    def test_layer_id_not_in_existing_nine(self) -> None:
        assert LAYER_SPEC.layer_id not in EXISTING_LAYER_IDS, (
            f"layer_id {LAYER_SPEC.layer_id} 与现有 9 层冲突"
        )

    def test_layer_id_unique_vs_h_daemons(self) -> None:
        assert LAYER_SPEC.layer_id != LAYER_H_DAEMONS.layer_id

    def test_no_function_name_collision_with_h_daemons(self) -> None:
        h_daemons_names = {s.signature.name for s in LAYER_H_DAEMONS.function_specs}
        h2_names = {s.signature.name for s in LAYER_SPEC.function_specs}
        collision = h_daemons_names & h2_names
        assert not collision, f"与 layer_h_daemons.py FunctionSpec 重名: {collision}"


# ---------------------------------------------------------------------------
# 关键函数签名与结构完整性
# ---------------------------------------------------------------------------


class TestFunctionSpecSignature:
    """核心函数签名与契约结构完整。"""

    @pytest.fixture
    def do_channel(self) -> FunctionSpec:
        return next(s for s in LAYER_SPEC.function_specs if s.signature.name == "do_channel")

    @pytest.fixture
    def player_pay(self) -> FunctionSpec:
        return next(s for s in LAYER_SPEC.function_specs if s.signature.name == "player_pay")

    @pytest.fixture
    def login_check(self) -> FunctionSpec:
        return next(s for s in LAYER_SPEC.function_specs if s.signature.name == "login_check")

    @pytest.fixture
    def inventory_check(self) -> FunctionSpec:
        return next(s for s in LAYER_SPEC.function_specs if s.signature.name == "inventory_check")

    @pytest.fixture
    def process_global_alias(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "process_global_alias"
        )

    def test_do_channel_signature_complete(self, do_channel: FunctionSpec) -> None:
        sig = do_channel.signature
        assert sig.name == "do_channel"
        assert sig.return_type == "int"
        assert sig.lpc_file == "adm/daemons/channeld.c"
        assert len(sig.params) == 4
        assert sig.is_varargs

    def test_do_channel_has_side_effects(self, do_channel: FunctionSpec) -> None:
        assert len(do_channel.side_effects) > 0

    def test_player_pay_return_tri_state(self, player_pay: FunctionSpec) -> None:
        sig = player_pay.signature
        assert sig.return_type == "int"
        assert any("返回 1" in pc.description for pc in player_pay.postconditions)
        assert any("返回 0" in pc.description for pc in player_pay.postconditions)
        assert any("返回 2" in pc.description for pc in player_pay.postconditions)

    def test_login_check_side_effects_order(self, login_check: FunctionSpec) -> None:
        orders = [se.order for se in login_check.side_effects]
        assert orders == sorted(orders)
        assert orders[0] == 1

    def test_inventory_check_has_random_specs(self, inventory_check: FunctionSpec) -> None:
        assert len(inventory_check.random_specs) == 3

    def test_process_global_alias_pure_string(self, process_global_alias: FunctionSpec) -> None:
        assert process_global_alias.signature.return_type == "string"
        # 纯字符串转换函数不应有 STATE_MUTATION 以外的副作用
        state_mutations = [
            se
            for se in process_global_alias.side_effects
            if se.kind == SideEffectType.STATE_MUTATION
        ]
        assert len(state_mutations) == 1
        assert "current_alias" in state_mutations[0].description


# ---------------------------------------------------------------------------
# 领域常量断言
# ---------------------------------------------------------------------------


class TestDomainConstants:
    """层 H-2 导出的领域常量与 LPC 源码一致。"""

    def test_currency_rates(self) -> None:
        assert CURRENCY_RATES["gold"] == 10000
        assert CURRENCY_RATES["silver"] == 100
        assert CURRENCY_RATES["coin"] == 1

    def test_max_cashflow(self) -> None:
        assert MAX_CASHFLOW_ALLOWED == 400000

    def test_global_aliases_include_directions(self) -> None:
        assert GLOBAL_ALIASES["n"] == "go north"
        assert GLOBAL_ALIASES["s"] == "go south"
        assert GLOBAL_ALIASES["e"] == "go east"
        assert GLOBAL_ALIASES["w"] == "go west"
        assert GLOBAL_ALIASES["l"] == "look"
        assert GLOBAL_ALIASES["i"] == "inventory"

    def test_global_aliases_say_prefix(self) -> None:
        """process_global_alias 将 ' 前缀展开为 say。"""
        assert GLOBAL_ALIASES.get("'") is None  # 不在映射中，由代码特判


# ---------------------------------------------------------------------------
# cross_layer_refs 目标层 ID 合法
# ---------------------------------------------------------------------------


class TestCrossLayerRefs:
    """cross_layer_refs 提到的目标层 ID 在 A-I 范围内。"""

    def test_refs_target_existing_layers(self) -> None:
        for ref in LAYER_SPEC.cross_layer_refs:
            targets = set(_LAYER_REF_RE.findall(ref))
            if targets:
                invalid = targets - EXISTING_LAYER_IDS
                assert not invalid, (
                    f"层 {LAYER_SPEC.layer_id} ref 提到无效层 ID: {ref} -> {invalid}"
                )

    def test_refs_reference_other_layers(self) -> None:
        other_refs = 0
        for ref in LAYER_SPEC.cross_layer_refs:
            targets = set(_LAYER_REF_RE.findall(ref))
            if targets:
                other_refs += 1
        assert other_refs > 0, "cross_layer_refs 无任何跨层引用"


# ---------------------------------------------------------------------------
# 副作用顺序契约
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 从 1 连续递增。"""

    def test_do_channel_side_effect_order_consecutive(self) -> None:
        spec = next(s for s in LAYER_SPEC.function_specs if s.signature.name == "do_channel")
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"do_channel order 不连续: {orders}"

    def test_pay_player_side_effect_order_consecutive(self) -> None:
        spec = next(s for s in LAYER_SPEC.function_specs if s.signature.name == "pay_player")
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"pay_player order 不连续: {orders}"


# ---------------------------------------------------------------------------
# hypothesis 属性测试（路径 A）
# ---------------------------------------------------------------------------

_N = len(LAYER_SPEC.function_specs) - 1


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性：任意索引的 FunctionSpec 签名完整。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert spec.signature.name
    assert spec.signature.return_type
    assert spec.signature.lpc_file


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_monotonic(idx: int) -> None:
    """属性：任意函数的副作用 order 严格递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = [se.order for se in spec.side_effects]
        assert orders == sorted(orders), f"{spec.signature.name}: side_effect order 非递增"


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_consecutive_from_one(idx: int) -> None:
    """属性：任意函数的副作用 order 从 1 连续递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"{spec.signature.name}: order 不连续: {orders}"


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_kind_and_description_nonempty(idx: int) -> None:
    """属性：任意副作用 kind/description 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for se in spec.side_effects:
        assert se.kind is not None, f"{spec.signature.name}: order={se.order} kind 为空"
        assert se.description, f"{spec.signature.name}: order={se.order} description 为空"


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_has_invariants(idx: int) -> None:
    """属性：任意函数至少有一个不变量。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.invariants) > 0, f"{spec.signature.name}: 无不变量"


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_has_post_conditions(idx: int) -> None:
    """属性：任意函数至少有一个后置条件。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


# ── 副作用子集 order 保持性 ──────────────────────────────────────────────────


@st.composite
def _spec_with_subset(draw: st.DrawFn) -> tuple[FunctionSpec, list]:
    """生成 (函数, 非空副作用子集)，子集保持原顺序。"""
    specs_with_se = [s for s in LAYER_SPEC.function_specs if s.side_effects]
    spec = draw(st.sampled_from(specs_with_se))
    n = len(spec.side_effects)
    indices = draw(st.lists(st.integers(0, n - 1), min_size=1, max_size=n, unique=True))
    subset = [spec.side_effects[i] for i in sorted(indices)]
    return spec, subset


@given(data=_spec_with_subset())
def test_side_effect_subset_order_preserved(
    data: tuple[FunctionSpec, list],
) -> None:
    """属性：任意函数副作用的随机子集，order 仍递增（子集保有序性）。"""
    spec, subset = data
    orders = [se.order for se in subset]
    assert orders == sorted(orders), f"{spec.signature.name}: 子集 order 非递增: {orders}"


# ── invariants-side_effects 对应 ─────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi/state/max_/jing 的函数，副作用含 STATE_MUTATION。"""
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")
    has_state_invariant = any(
        any(
            kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in state_keywords
        )
        for inv in spec.invariants
    )
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
