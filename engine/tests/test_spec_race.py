"""层 H-RACE：race daemon 种族初始化 -- 规格提取测试（ADR-0030 开放问题 1）。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="H-RACE"、function_specs 含 2 个
- 结构属性：setup_race / apply_family_bonuses 签名完整（name/lpc_file/
  lpc_signature/preconditions/postconditions/invariants/side_effects 都非空）
- 副作用 order 递增连续（hypothesis 随机子集仍递增）
- invariants 非空
- cross_layer_refs 目标层 ID 合法（A-I 范围内）
- LayerSpec layer_id 唯一（不与现有 9 层 A-I 冲突）
- 不与现有 layer_h_daemons.py 的 FunctionSpec 重名
- ADR-0030 主题无关性契约断言（setup_race / apply_family_bonuses 不硬编码门派名）
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_h_daemons import LAYER_SPEC as LAYER_H_DAEMONS
from xkx.spec.layer_h_race import LAYER_SPEC

# 现有 9 层 layer_id 集合（A-I），用于验证 H-RACE 不与之冲突
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
        assert LAYER_SPEC.layer_id == "H-RACE"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "race daemon 种族初始化"

    def test_lpc_files_complete(self) -> None:
        """human.c 在 lpc_files 中。"""
        assert "adm/daemons/race/human.c" in LAYER_SPEC.lpc_files
        assert len(LAYER_SPEC.lpc_files) == 1

    def test_function_spec_count(self) -> None:
        """应有 2 个 FunctionSpec（setup_race + apply_family_bonuses）。"""
        assert len(LAYER_SPEC.function_specs) == 2

    def test_expected_function_names(self) -> None:
        names = {spec.signature.name for spec in LAYER_SPEC.function_specs}
        expected = {"setup_race", "apply_family_bonuses"}
        assert names == expected, f"函数名不匹配: {names ^ expected}"

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# layer_id 唯一性 + 不与现有 layer_h_daemons.py FunctionSpec 重名
# ---------------------------------------------------------------------------


class TestLayerUniqueness:
    """LayerSpec layer_id 唯一 + 不与现有 layer_h_daemons.py 重名。"""

    def test_layer_id_not_in_existing_nine(self) -> None:
        """H-RACE 不在现有 9 层 A-I 范围内（独立子层，不混入 ALL_LAYERS）。"""
        assert LAYER_SPEC.layer_id not in EXISTING_LAYER_IDS, (
            f"layer_id {LAYER_SPEC.layer_id} 与现有 9 层冲突"
        )

    def test_layer_id_unique_vs_h_daemons(self) -> None:
        """H-RACE 与层 H（CHAR_D 等守护进程）layer_id 不同。"""
        assert LAYER_SPEC.layer_id != LAYER_H_DAEMONS.layer_id

    def test_no_function_name_collision_with_h_daemons(self) -> None:
        """不与现有 layer_h_daemons.py 的 FunctionSpec 重名。

        layer_h_daemons.py 有 setup_char（CHAR_D 种族分派入口），本层是
        setup_race（race daemon 通用基础）+ apply_family_bonuses（门派加成分发），
        两者是不同函数，不应重名。
        """
        h_daemons_names = {
            s.signature.name for s in LAYER_H_DAEMONS.function_specs
        }
        race_names = {s.signature.name for s in LAYER_SPEC.function_specs}
        collision = h_daemons_names & race_names
        assert not collision, (
            f"与 layer_h_daemons.py FunctionSpec 重名: {collision}"
        )


# ---------------------------------------------------------------------------
# FunctionSpec 签名完整性
# ---------------------------------------------------------------------------


class TestFunctionSpecSignature:
    """setup_race / apply_family_bonuses 签名完整。"""

    @pytest.fixture
    def setup_race(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "setup_race"
        )

    @pytest.fixture
    def apply_family_bonuses(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "apply_family_bonuses"
        )

    def test_setup_race_signature_complete(self, setup_race: FunctionSpec) -> None:
        """setup_race 签名字段非空。"""
        sig = setup_race.signature
        assert sig.name == "setup_race"
        assert sig.return_type == "void"
        assert sig.lpc_file == "adm/daemons/race/human.c"
        assert len(sig.params) == 2  # entity + profile
        assert sig.params[0].name == "entity"
        assert sig.params[1].name == "profile"

    def test_apply_bonuses_signature_complete(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        """apply_family_bonuses 签名字段非空。"""
        sig = apply_family_bonuses.signature
        assert sig.name == "apply_family_bonuses"
        assert sig.return_type == "void"
        assert sig.lpc_file == "adm/daemons/race/human.c"
        assert len(sig.params) == 3  # entity + family_name + bonuses
        assert sig.params[0].name == "entity"
        assert sig.params[1].name == "family_name"
        assert sig.params[2].name == "bonuses"
        assert sig.params[2].is_varargs_tail  # FamilyBonus 列表可变长度

    def test_setup_race_preconditions_nonempty(self, setup_race: FunctionSpec) -> None:
        assert len(setup_race.preconditions) > 0

    def test_setup_race_postconditions_nonempty(
        self, setup_race: FunctionSpec
    ) -> None:
        assert len(setup_race.postconditions) > 0

    def test_setup_race_invariants_nonempty(self, setup_race: FunctionSpec) -> None:
        assert len(setup_race.invariants) > 0

    def test_setup_race_side_effects_nonempty(self, setup_race: FunctionSpec) -> None:
        assert len(setup_race.side_effects) > 0

    def test_apply_bonuses_preconditions_nonempty(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        assert len(apply_family_bonuses.preconditions) > 0

    def test_apply_bonuses_postconditions_nonempty(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        assert len(apply_family_bonuses.postconditions) > 0

    def test_apply_bonuses_invariants_nonempty(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        assert len(apply_family_bonuses.invariants) > 0

    def test_apply_bonuses_side_effects_nonempty(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        assert len(apply_family_bonuses.side_effects) > 0


# ---------------------------------------------------------------------------
# cross_layer_refs 目标层 ID 合法
# ---------------------------------------------------------------------------


class TestCrossLayerRefs:
    """cross_layer_refs 提到的目标层 ID 在 A-I 范围内。"""

    def test_refs_target_existing_layers(self) -> None:
        """每条 cross_layer_refs 提到的层 ID（若有）在 A-I 范围内。"""
        for ref in LAYER_SPEC.cross_layer_refs:
            targets = set(_LAYER_REF_RE.findall(ref))
            if targets:
                invalid = targets - EXISTING_LAYER_IDS
                assert not invalid, (
                    f"层 {LAYER_SPEC.layer_id} ref 提到无效层 ID: {ref} -> {invalid}"
                )

    def test_refs_reference_other_layers(self) -> None:
        """cross_layer_refs 应引用其他层（H-RACE 是子层，引用层 H/B/E 等）。"""
        other_refs = 0
        for ref in LAYER_SPEC.cross_layer_refs:
            targets = set(_LAYER_REF_RE.findall(ref))
            if targets:
                other_refs += 1
        assert other_refs > 0, "cross_layer_refs 无任何跨层引用"

    def test_refs_include_char_d_setup_char(self) -> None:
        """跨层引用包含 setup_char（层 H CHAR_D 种族分派入口）。"""
        refs = " ".join(LAYER_SPEC.cross_layer_refs)
        assert "setup_char" in refs or "层 H" in refs

    def test_refs_include_query_skill(self) -> None:
        """跨层引用包含 query_skill（层 B F_SKILL）。"""
        refs = " ".join(LAYER_SPEC.cross_layer_refs)
        assert "query_skill" in refs or "层 B" in refs


# ---------------------------------------------------------------------------
# ADR-0030 主题无关性契约断言
# ---------------------------------------------------------------------------


class TestThemeNeutrality:
    """ADR-0030 决策 1/4 主题无关性契约。"""

    @pytest.fixture
    def setup_race(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "setup_race"
        )

    @pytest.fixture
    def apply_family_bonuses(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "apply_family_bonuses"
        )

    def test_setup_race_has_theme_neutrality_invariant(
        self, setup_race: FunctionSpec
    ) -> None:
        """setup_race 有'不硬编码门派名/技能名'不变量。"""
        assert any(
            "门派名" in inv.description and "技能名" in inv.description
            for inv in setup_race.invariants
        )

    def test_setup_race_has_param_thresholds_invariant(
        self, setup_race: FunctionSpec
    ) -> None:
        """setup_race 有年龄分层阈值参数化不变量（14/30/70）。"""
        assert any(
            "14" in inv.description and "30" in inv.description and "70" in inv.description
            for inv in setup_race.invariants
        )

    def test_setup_race_has_three_layer_resource_invariant(
        self, setup_race: FunctionSpec
    ) -> None:
        """setup_race 有三层资源不变量（0 <= qi <= eff_qi <= max_qi）。"""
        assert any(
            "qi" in inv.description and "eff_qi" in inv.description and "max_qi" in inv.description
            for inv in setup_race.invariants
        )

    def test_apply_bonuses_has_monotonic_invariant(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        """apply_family_bonuses 有'加成单调非递减'不变量。"""
        assert any(
            "单调" in inv.description or "非递减" in inv.description
            for inv in apply_family_bonuses.invariants
        )

    def test_apply_bonuses_has_theme_neutrality_invariant(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        """apply_family_bonuses 有'不认识具体门派名'不变量。"""
        assert any(
            "不认识" in inv.description or "字符串匹配" in inv.description
            for inv in apply_family_bonuses.invariants
        )

    def test_setup_race_notes_mention_adr_0030(self, setup_race: FunctionSpec) -> None:
        """setup_race notes 引用 ADR-0030 决策 1。"""
        assert setup_race.notes is not None
        assert "ADR-0030" in setup_race.notes
        assert "决策 1" in setup_race.notes

    def test_apply_bonuses_notes_mention_m3_postponed(
        self, apply_family_bonuses: FunctionSpec
    ) -> None:
        """apply_family_bonuses notes 标注 13 门派全量公式后置 M3。"""
        assert apply_family_bonuses.notes is not None
        assert "M3" in apply_family_bonuses.notes


# ---------------------------------------------------------------------------
# 副作用顺序契约
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 从 1 连续递增。"""

    def test_setup_race_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "setup_race"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"setup_race order 不连续: {orders}"

    def test_apply_bonuses_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "apply_family_bonuses"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"apply_family_bonuses order 不连续: {orders}"


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
