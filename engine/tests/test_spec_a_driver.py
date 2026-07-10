"""层 A（驱动桥梁）规格属性测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id / layer_name / function_specs 正确
- 结构属性：每个 FunctionSpec 的 signature 字段完整
- 副作用 order 唯一且递增（每个有副作用的函数）
- cross_layer_refs 非空且格式一致
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec
from xkx.spec.layer_a_driver import LAYER_SPEC

# ── smoke ─────────────────────────────────────────────────────────────────


class TestSmoke:
    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert LAYER_SPEC.layer_id == "A"
        assert LAYER_SPEC.layer_name == "驱动桥梁"

    def test_lpc_files_non_empty(self) -> None:
        assert len(LAYER_SPEC.lpc_files) >= 3
        assert "adm/single/master.c" in LAYER_SPEC.lpc_files
        assert "adm/single/simul_efun.c" in LAYER_SPEC.lpc_files
        assert "config.xkx" in LAYER_SPEC.lpc_files

    def test_function_specs_non_empty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_count(self) -> None:
        """层 A 提取了 25 个核心函数规格。"""
        assert len(LAYER_SPEC.function_specs) == 25

    def test_cross_layer_refs_non_empty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0

    def test_notes_contain_config_info(self) -> None:
        assert LAYER_SPEC.notes is not None
        assert "config.xkx" in LAYER_SPEC.notes
        assert "port number" in LAYER_SPEC.notes


# ── 结构属性 ───────────────────────────────────────────────────────────────


class TestFunctionSpecStructure:
    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_signatures_have_name(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.name, f"函数签名 name 为空: {spec}"

    def test_all_signatures_have_return_type(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.return_type, (
                f"{spec.signature.name}: return_type 为空"
            )

    def test_all_signatures_have_lpc_file(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.lpc_file, (
                f"{spec.signature.name}: lpc_file 为空"
            )

    def test_all_function_names_unique(self, all_specs: list[FunctionSpec]) -> None:
        names = [s.signature.name for s in all_specs]
        # valid_seteuid 在 master.c 和 simul_efun 中名称可能不同，检查是否有意重复
        # destruct 在 master.c 没有，但在 simul_efun 有；都应唯一
        assert len(names) == len(set(names)), f"函数名重复: {names}"

    def test_line_range_valid_when_present(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            if spec.signature.line_range is not None:
                lo, hi = spec.signature.line_range
                assert lo > 0, f"{spec.signature.name}: line_range 下界 > 0"
                assert hi >= lo, f"{spec.signature.name}: line_range 上界 >= 下界"

    def test_lpc_file_matches_known_sources(self, all_specs: list[FunctionSpec]) -> None:
        """所有函数的 lpc_file 必须在层 A 声明的文件列表内。"""
        known_files = set(LAYER_SPEC.lpc_files)
        for spec in all_specs:
            assert spec.signature.lpc_file in known_files, (
                f"{spec.signature.name}: lpc_file '{spec.signature.lpc_file}' 不在层 A 文件列表中"
            )


# ── 副作用 order 属性 ─────────────────────────────────────────────────────


class TestSideEffectOrder:
    @pytest.fixture
    def specs_with_side_effects(self) -> list[FunctionSpec]:
        return [s for s in LAYER_SPEC.function_specs if s.side_effects]

    def test_at_least_one_function_has_side_effects(
        self,
        specs_with_side_effects: list[FunctionSpec],
    ) -> None:
        assert len(specs_with_side_effects) > 0, "至少一个函数应有副作用"

    def test_side_effect_orders_unique_per_function(
        self,
        specs_with_side_effects: list[FunctionSpec],
    ) -> None:
        for spec in specs_with_side_effects:
            orders = [se.order for se in spec.side_effects]
            assert len(orders) == len(set(orders)), (
                f"{spec.signature.name}: side_effect order 有重复: {orders}"
            )

    def test_side_effect_orders_consecutive_from_one(
        self,
        specs_with_side_effects: list[FunctionSpec],
    ) -> None:
        """副作用 order 从 1 开始连续递增（交织顺序的完整性保证）。"""
        for spec in specs_with_side_effects:
            orders = sorted(se.order for se in spec.side_effects)
            expected = list(range(1, len(orders) + 1))
            assert orders == expected, (
                f"{spec.signature.name}: side_effect order 应从 1 连续递增: "
                f"got {orders}, expected {expected}"
            )

    def test_all_side_effects_have_kind(
        self,
        specs_with_side_effects: list[FunctionSpec],
    ) -> None:
        for spec in specs_with_side_effects:
            for se in spec.side_effects:
                assert se.kind is not None, (
                    f"{spec.signature.name}: side_effect order={se.order} kind 为空"
                )

    def test_all_side_effects_have_description(
        self,
        specs_with_side_effects: list[FunctionSpec],
    ) -> None:
        for spec in specs_with_side_effects:
            for se in spec.side_effects:
                assert se.description, (
                    f"{spec.signature.name}: side_effect order={se.order} description 为空"
                )


# ── hypothesis 属性测试 ──────────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=len(LAYER_SPEC.function_specs) - 1))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性：任意索引的 FunctionSpec 结构完整。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert spec.signature.name
    assert spec.signature.return_type
    assert spec.signature.lpc_file


@given(
    idx=st.integers(min_value=0, max_value=len(LAYER_SPEC.function_specs) - 1),
)
def test_side_effect_order_monotonic(idx: int) -> None:
    """属性：任意函数的副作用 order 严格递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = [se.order for se in spec.side_effects]
        assert orders == sorted(orders), (
            f"{spec.signature.name}: side_effect order 非递增"
        )


# ── 随机性规格 ────────────────────────────────────────────────────────────


class TestRandomSpecs:
    def test_no_random_specs_expected(self) -> None:
        """层 A（驱动桥梁）不含 random() 调用，random_specs 应为空。

        combat 确定性范围 = combat-only（层 E），驱动桥梁无随机性。
        """
        for spec in LAYER_SPEC.function_specs:
            assert len(spec.random_specs) == 0, (
                f"{spec.signature.name}: 层 A 不应有 random_specs"
            )


# ── 关键函数覆盖检查 ─────────────────────────────────────────────────────


class TestKeyFunctionCoverage:
    @pytest.fixture
    def spec_names(self) -> set[str]:
        return {s.signature.name for s in LAYER_SPEC.function_specs}

    @pytest.mark.parametrize(
        "expected_name",
        [
            "connect",
            "crash",
            "epilog",
            "preload",
            "error_handler",
            "log_error",
            "valid_seteuid",
            "valid_override",
            "valid_write",
            "valid_read",
            "valid_shadow",
            "valid_hide",
            "valid_object",
            "valid_bind",
            "get_root_uid",
            "get_bb_uid",
            "destruct",
            "getoid",
            "file_owner",
            "domain_file",
            "creator_file",
            "base_name",
            "resolve_path",
            "living",
        ],
    )
    def test_key_function_present(self, spec_names: set[str], expected_name: str) -> None:
        assert expected_name in spec_names, f"缺少核心函数: {expected_name}"


# ── 前置条件/后置条件/不变量完整性 ──────────────────────────────────────


class TestContractCompleteness:
    def test_all_specs_have_at_least_one_precondition(self) -> None:
        """每个函数至少有一个前置条件（至少描述何时被调用）。"""
        for spec in LAYER_SPEC.function_specs:
            assert len(spec.preconditions) > 0, (
                f"{spec.signature.name}: 无前置条件"
            )

    def test_all_specs_have_at_least_one_postcondition(self) -> None:
        """每个函数至少有一个后置条件。"""
        for spec in LAYER_SPEC.function_specs:
            assert len(spec.postconditions) > 0, (
                f"{spec.signature.name}: 无后置条件"
            )

    def test_security_functions_have_invariants(self) -> None:
        """安全校验钩子应有不变量描述权限规则。"""
        security_funcs = {
            "valid_seteuid",
            "valid_override",
            "valid_write",
            "valid_read",
            "valid_shadow",
            "valid_hide",
            "valid_object",
            "valid_bind",
        }
        for spec in LAYER_SPEC.function_specs:
            if spec.signature.name in security_funcs:
                assert len(spec.invariants) > 0, (
                    f"{spec.signature.name}: 安全校验函数应有不变量"
                )
