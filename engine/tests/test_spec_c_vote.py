"""层 C-VOTE：玩家自治投票系统 -- 规格提取测试（ADR-0055 Batch 2）。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="C-VOTE"、lpc_files 完整
- 层 ID 不与现有 9 层 A-I 冲突
- FunctionSpec 签名/前置/后置/不变量/副作用结构完整
- 副作用 order 从 1 连续递增（hypothesis）
- cross_layer_refs 目标层 ID 合法（A-I 范围内）
- 关键领域断言：投票常量、chblk/unchblk 阈值、vote_clear 负 duration 语义
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_c_vote import (
    LAYER_SPEC,
    VOTE_MIN_VOTES,
    VoteReason,
    VoteThreshold,
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
        assert LAYER_SPEC.layer_id == "C-VOTE"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "玩家自治投票系统"

    def test_lpc_files_complete(self) -> None:
        expected = {
            "cmds/std/vote.c",
            "cmds/std/vote/chblk.c",
            "cmds/std/vote/unchblk.c",
            "kungfu/condition/vote_clear.c",
            "kungfu/condition/vote_suspension.c",
            "include/vote.h",
        }
        assert set(LAYER_SPEC.lpc_files) == expected

    def test_function_spec_count(self) -> None:
        assert len(LAYER_SPEC.function_specs) == 6

    def test_expected_function_names(self) -> None:
        names = {spec.signature.name for spec in LAYER_SPEC.function_specs}
        expected = {
            "main",
            "valid_voters",
            "vote",  # chblk.c 与 unchblk.c 同名，按 lpc_file 区分
            "update_condition",  # vote_clear.c 与 vote_suspension.c 同名，按 lpc_file 区分
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# layer_id 唯一性
# ---------------------------------------------------------------------------


class TestLayerUniqueness:
    """LayerSpec layer_id 唯一。"""

    def test_layer_id_not_in_existing_nine(self) -> None:
        assert LAYER_SPEC.layer_id not in EXISTING_LAYER_IDS, (
            f"layer_id {LAYER_SPEC.layer_id} 与现有 9 层冲突"
        )


# ---------------------------------------------------------------------------
# 投票常量断言
# ---------------------------------------------------------------------------


class TestVoteConstants:
    """vote.h 常量与规格一致。"""

    def test_vote_reason_constants(self) -> None:
        assert VoteReason.FAIL == 0
        assert VoteReason.EJECT == 5
        assert VoteReason.CHBLK == 6
        assert VoteReason.UNCHBLK == 7
        assert VoteReason.ROBOT == 8

    def test_vote_threshold_constants(self) -> None:
        assert VoteThreshold.ONETHIRD == 1
        assert VoteThreshold.HALF == 2
        assert VoteThreshold.TWOTHIRD == 3
        assert VoteThreshold.FIVE == 4

    def test_vote_min_votes(self) -> None:
        assert VOTE_MIN_VOTES == 3


# ---------------------------------------------------------------------------
# 关键函数结构完整性
# ---------------------------------------------------------------------------


class TestFunctionSpecSignature:
    """核心函数签名与契约结构完整。"""

    @pytest.fixture
    def vote_main(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "main"
        )

    @pytest.fixture
    def chblk_vote(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "cmds/std/vote/chblk.c"
        )

    @pytest.fixture
    def unchblk_vote(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "cmds/std/vote/unchblk.c"
        )

    @pytest.fixture
    def vote_clear_update(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "kungfu/condition/vote_clear.c"
        )

    def test_vote_main_has_abuse_guard(self, vote_main: FunctionSpec) -> None:
        # abuse 是子命令返回失败后的副作用，不是前置条件
        assert any("abuse" in se.description for se in vote_main.side_effects)
        assert any("vote/deprived" in pc.description for pc in vote_main.preconditions)

    def test_chblk_threshold_invariant(self, chblk_vote: FunctionSpec) -> None:
        assert any("valid_voters/4" in inv.description for inv in chblk_vote.invariants)
        assert any("4" in inv.description for inv in chblk_vote.invariants)

    def test_unchblk_threshold_invariant(self, unchblk_vote: FunctionSpec) -> None:
        assert any(
            "valid_voters/6" in inv.description for inv in unchblk_vote.invariants
        )
        assert any("4" in inv.description for inv in unchblk_vote.invariants)

    def test_vote_clear_negative_duration(self, vote_clear_update: FunctionSpec) -> None:
        assert any("-5" in pc.description for pc in vote_clear_update.postconditions)
        assert any("-5" in inv.description for inv in vote_clear_update.invariants)

    def test_chblk_self_vote_random(self, chblk_vote: FunctionSpec) -> None:
        assert len(chblk_vote.random_specs) == 1
        assert "random(2)" in chblk_vote.random_specs[0].lpc_call


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

    def test_vote_main_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "main"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"main order 不连续: {orders}"

    def test_chblk_vote_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "cmds/std/vote/chblk.c"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"chblk vote order 不连续: {orders}"


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
        assert orders == sorted(orders), (
            f"{spec.signature.name}: side_effect order 非递增"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_consecutive_from_one(idx: int) -> None:
    """属性：任意函数的副作用 order 从 1 连续递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, (
            f"{spec.signature.name}: order 不连续: {orders}"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_kind_and_description_nonempty(idx: int) -> None:
    """属性：任意副作用 kind/description 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for se in spec.side_effects:
        assert se.kind is not None, (
            f"{spec.signature.name}: order={se.order} kind 为空"
        )
        assert se.description, (
            f"{spec.signature.name}: order={se.order} description 为空"
        )


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
    indices = draw(
        st.lists(st.integers(0, n - 1), min_size=1, max_size=n, unique=True)
    )
    subset = [spec.side_effects[i] for i in sorted(indices)]
    return spec, subset


@given(data=_spec_with_subset())
def test_side_effect_subset_order_preserved(
    data: tuple[FunctionSpec, list],
) -> None:
    """属性：任意函数副作用的随机子集，order 仍递增（子集保有序性）。"""
    spec, subset = data
    orders = [se.order for se in subset]
    assert orders == sorted(orders), (
        f"{spec.signature.name}: 子集 order 非递增: {orders}"
    )


# ── invariants-side_effects 对应 ─────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi/state/max_/jing 的函数，副作用含 STATE_MUTATION。"""
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")
    has_state_invariant = any(
        any(kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in state_keywords)
        for inv in spec.invariants
    )
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
