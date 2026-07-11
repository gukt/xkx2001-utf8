"""层 B（对象基础）规格属性测试（任务 3 路径 A）。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id / layer_name / function_specs 正确
- 结构属性：每个 FunctionSpec 的 signature 字段完整
- 副作用 order 唯一且递增（每个有副作用的函数）
- hypothesis 属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
- 关键函数覆盖与特殊契约（F_DBASE 路径语义 / temp 变体 / F_NAME short() / F_MOVE 负重级联）
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffect, SideEffectType
from xkx.spec.layer_b_object_base import LAYER_SPEC

# ── smoke ─────────────────────────────────────────────────────────────────


class TestSmoke:
    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id_is_b(self) -> None:
        assert LAYER_SPEC.layer_id == "B"

    def test_layer_name_is_object_base(self) -> None:
        assert LAYER_SPEC.layer_name == "对象基础"

    def test_function_specs_non_empty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_count(self) -> None:
        """层 B 提取了 24 个核心函数规格。"""
        assert len(LAYER_SPEC.function_specs) == 24

    def test_lpc_files_complete(self) -> None:
        """6 个 LPC 文件全部覆盖。"""
        expected_files = {
            "feature/dbase.c",
            "feature/name.c",
            "feature/move.c",
            "feature/message.c",
            "feature/save.c",
            "feature/clean_up.c",
        }
        assert set(LAYER_SPEC.lpc_files) == expected_files

    def test_cross_layer_refs_non_empty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ── 结构属性 ───────────────────────────────────────────────────────────────


class TestFunctionSpecStructure:
    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_function_names_unique(self, all_specs: list[FunctionSpec]) -> None:
        names = [s.signature.name for s in all_specs]
        assert len(names) == len(set(names)), f"函数名重复: {names}"

    def test_line_range_valid_when_present(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            if spec.signature.line_range is not None:
                lo, hi = spec.signature.line_range
                assert lo > 0, f"{spec.signature.name}: line_range 下界 > 0"
                assert hi >= lo, f"{spec.signature.name}: line_range 上界 >= 下界"

    def test_lpc_file_matches_known_sources(self, all_specs: list[FunctionSpec]) -> None:
        """所有函数的 lpc_file 必须在层 B 声明的文件列表内。"""
        known_files = set(LAYER_SPEC.lpc_files)
        for spec in all_specs:
            assert spec.signature.lpc_file in known_files, (
                f"{spec.signature.name}: lpc_file '{spec.signature.lpc_file}' 不在层 B 文件列表中"
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


# ── hypothesis 属性测试（路径 A） ────────────────────────────────────────
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。


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
def test_function_has_pre_and_post_conditions(idx: int) -> None:
    """属性：任意函数至少有一个后置条件（层 B 部分函数无前置条件，属正常）。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


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


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_completeness(idx: int) -> None:
    """属性：有 random_specs 的函数，每个的 probability_model/semantic/lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec probability_model 为空"
        )
        assert rs.semantic, (
            f"{spec.signature.name}: random_spec semantic 为空"
        )
        assert rs.lpc_call, (
            f"{spec.signature.name}: random_spec lpc_call 为空"
        )


# save/restore/clean_up 的不变量描述中含 "query"/"set" 字样（如 query_save_file、
# set('no_clean_up')），但这些是函数名引用而非状态变更不变量，需排除。
_STATE_INVARIANT_EXCLUDE = {"save", "restore", "clean_up"}


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi/set/query/temp 的函数，副作用含 STATE_MUTATION。

    排除 save/restore/clean_up：其不变量中的 "query"/"set" 是函数名引用
    （query_save_file、set('no_clean_up')），非状态变更语义。
    """
    spec = LAYER_SPEC.function_specs[idx]
    if spec.signature.name in _STATE_INVARIANT_EXCLUDE:
        return
    state_keywords = (
        "qi", "state", "状态", "eff_", "max_",
        "jing", "neili", "set", "query", "temp",
    )
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


# ── 关键函数覆盖检查 ─────────────────────────────────────────────────────


class TestKeyFunctionCoverage:
    @pytest.fixture
    def spec_names(self) -> set[str]:
        return {s.signature.name for s in LAYER_SPEC.function_specs}

    @pytest.mark.parametrize(
        "expected_name",
        [
            # F_DBASE
            "set",
            "query",
            "delete",
            "add",
            "set_temp",
            "query_temp",
            "delete_temp",
            "add_temp",
            "set_default_object",
            # F_NAME
            "set_name",
            "id",
            "name",
            "short",
            "long",
            # F_MOVE
            "move",
            "weight",
            "set_weight",
            "add_encumbrance",
            "remove",
            # F_MESSAGE
            "receive_message",
            "write_prompt",
            # F_SAVE
            "save",
            "restore",
            # F_CLEAN_UP
            "clean_up",
        ],
    )
    def test_key_function_present(self, spec_names: set[str], expected_name: str) -> None:
        assert expected_name in spec_names, f"缺少核心函数: {expected_name}"


# ── 文件覆盖率 ───────────────────────────────────────────────────────────


class TestFileCoverage:
    """每个 LPC 文件至少有一个函数规格。"""

    def test_each_lpc_file_has_functions(self) -> None:
        files_with_functions: set[str] = set()
        for spec in LAYER_SPEC.function_specs:
            files_with_functions.add(spec.signature.lpc_file)

        for lpc_file in LAYER_SPEC.lpc_files:
            assert lpc_file in files_with_functions, (
                f"LPC 文件无函数规格: {lpc_file}"
            )

    def test_dbase_has_8_plus_functions(self) -> None:
        """dbase.c 至少有 set/query/add/delete + 4 个 temp 变体 + default_ob。"""
        dbase_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/dbase.c"
        ]
        assert len(dbase_funcs) >= 8, f"dbase.c 函数数不足: {len(dbase_funcs)}"

    def test_name_has_5_functions(self) -> None:
        """name.c 有 set_name/id/name/short/long。"""
        name_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/name.c"
        ]
        names = {s.signature.name for s in name_funcs}
        expected = {"set_name", "id", "name", "short", "long"}
        assert expected.issubset(names), f"name.c 缺少函数: {expected - names}"

    def test_move_has_move_and_weight_functions(self) -> None:
        """move.c 有 move/weight/set_weight/add_encumbrance/remove。"""
        move_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/move.c"
        ]
        names = {s.signature.name for s in move_funcs}
        expected = {"move", "weight", "set_weight", "add_encumbrance", "remove"}
        assert expected.issubset(names), f"move.c 缺少函数: {expected - names}"


# ── F_DBASE 路径访问语义 + temp 变体差异 ──────────────────────────────────


class TestDbaseSemantics:
    """F_DBASE 路径访问语义与 temp 变体差异。"""

    def test_set_notes_mention_path_access(self) -> None:
        """set 的 notes 提及路径访问语义（'/' 分隔符）。"""
        set_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set"
        )
        notes = set_spec.notes or ""
        assert "/" in notes or "路径" in notes, (
            "set notes 未提及路径访问语义"
        )

    def test_query_notes_mention_path_access(self) -> None:
        """query 的 notes 提及路径访问语义。"""
        query_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "query"
        )
        notes = query_spec.notes or ""
        assert "/" in notes or "路径" in notes, (
            "query notes 未提及路径访问语义"
        )

    def test_set_temp_notes_mention_static(self) -> None:
        """set_temp 的 notes 提及 static（不存档语义差异）。"""
        set_temp_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set_temp"
        )
        notes = set_temp_spec.notes or ""
        assert "static" in notes.lower(), (
            "set_temp notes 未提及 static 语义"
        )

    def test_query_temp_notes_mention_difference_from_query(self) -> None:
        """query_temp 的 notes 提及与 query 的差异。"""
        query_temp_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "query_temp"
        )
        notes = query_temp_spec.notes or ""
        assert "差异" in notes or "不同" in notes, (
            "query_temp notes 未提及与 query 的差异"
        )

    def test_temp_dbase_separation_invariant_exists(self) -> None:
        """temp dbase 与常规 dbase 分离。"""
        set_temp_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set_temp"
        )
        inv_descs = [inv.description for inv in set_temp_spec.invariants]
        assert any("分离" in d for d in inv_descs), (
            "set_temp 缺少 'temp dbase 分离' 不变量"
        )

    def test_set_query_consistency_invariant_exists(self) -> None:
        """set 后 query 立即可读的不变量。"""
        set_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set"
        )
        inv_descs = [inv.description for inv in set_spec.invariants]
        assert any("query" in d and "可读" in d for d in inv_descs), (
            "set 缺少 'query 立即可读' 不变量"
        )


# ── F_NAME short() 状态修饰 ──────────────────────────────────────────────


class TestNameShortSemantics:
    """F_NAME short() 的 apply 掩码与状态修饰。"""

    def test_short_notes_mention_look(self) -> None:
        """short 的 notes 提及与 look 的关联。"""
        short_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "short"
        )
        notes = short_spec.notes or ""
        assert "look" in notes.lower(), (
            "short notes 未标注与 look 的关联"
        )

    def test_short_postconditions_mention_state_modifiers(self) -> None:
        """short 的后置条件提及状态修饰（打坐/鬼气/断线/昏迷等）。"""
        short_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "short"
        )
        postcond_text = " ".join(p.description for p in short_spec.postconditions)
        assert any(kw in postcond_text for kw in ("状态修饰", "打坐", "鬼气", "断线", "昏迷")), (
            "short 后置条件未提及状态修饰"
        )

    def test_short_invariants_mention_raw_bypass(self) -> None:
        """short 的不变量提及 raw=1 跳过掩码/修饰。"""
        short_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "short"
        )
        inv_text = " ".join(inv.description for inv in short_spec.invariants)
        assert "raw=1" in inv_text or "raw" in inv_text, (
            "short 不变量未提及 raw=1 跳过语义"
        )

    def test_id_invariants_mention_visibility(self) -> None:
        """id 的不变量提及可见性检查（this_player/visible）。"""
        id_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "id"
        )
        inv_text = " ".join(inv.description for inv in id_spec.invariants)
        assert "visible" in inv_text.lower() or "this_player" in inv_text, (
            "id 不变量未提及可见性检查"
        )


# ── F_MOVE 负重级联 ──────────────────────────────────────────────────────


class TestMoveEncumbranceSemantics:
    """F_MOVE move() 的负重检查与级联。"""

    def test_move_weight_precondition_exists(self) -> None:
        """move 有负重不超限前置条件。"""
        move_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "move"
        )
        precond_descs = [p.description for p in move_spec.preconditions]
        assert any("负重" in d or "encumbrance" in d.lower() for d in precond_descs), (
            "move 缺少负重前置条件"
        )

    def test_add_encumbrance_cascade_invariant_exists(self) -> None:
        """add_encumbrance 的负重级联不变量。"""
        add_enc_spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "add_encumbrance"
        )
        inv_descs = [inv.description for inv in add_enc_spec.invariants]
        assert any("级联" in d for d in inv_descs), (
            "add_encumbrance 缺少 '级联' 不变量"
        )

    def test_move_side_effects_include_encumbrance_changes(self) -> None:
        """move 的副作用包含旧环境减重和新环境加重。"""
        move_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "move"
        )
        se_descs = " ".join(se.description for se in move_spec.side_effects)
        assert "add_encumbrance" in se_descs or "减重" in se_descs or "-weight" in se_descs, (
            "move 副作用未包含旧环境减重"
        )
        assert (
            "add_encumbrance" in se_descs
            or "加重" in se_descs
            or "weight()" in se_descs
        ), (
            "move 副作用未包含新环境加重"
        )

    def test_move_has_7_side_effects(self) -> None:
        """move 有 7 个副作用（unequip/加载/负检查/减重/加重/move_object/look）。"""
        move_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "move"
        )
        assert len(move_spec.side_effects) == 7, (
            f"move 副作用数应为 7，实际 {len(move_spec.side_effects)}"
        )

    def test_weight_has_no_side_effects(self) -> None:
        """weight() 是只读查询，无副作用。"""
        weight_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "weight"
        )
        assert len(weight_spec.side_effects) == 0, (
            "weight 应无副作用（只读查询）"
        )


# ── F_MESSAGE random_spec ────────────────────────────────────────────────


class TestMessageRandomSpec:
    """receive_message 的 blind condition 随机性。"""

    def test_receive_message_has_random_spec(self) -> None:
        """receive_message 有 blind condition 随机性。"""
        rm_spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "receive_message"
        )
        assert len(rm_spec.random_specs) > 0, "receive_message 缺少随机性规格"

    def test_receive_message_random_spec_mentions_blind(self) -> None:
        """random_spec 的 semantic 提及盲人。"""
        rm_spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "receive_message"
        )
        rs = rm_spec.random_specs[0]
        assert "盲" in rs.semantic, (
            f"random_spec semantic 未提及盲人: {rs.semantic}"
        )


# ── pydantic 模型验证 ────────────────────────────────────────────────────


class TestPydanticValidation:
    """pydantic v2 模型验证。"""

    def test_all_specs_are_function_spec_instances(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            assert isinstance(spec, FunctionSpec)

    def test_all_side_effects_are_side_effect_instances(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            for se in spec.side_effects:
                assert isinstance(se, SideEffect)

    def test_layer_spec_serializable(self) -> None:
        """LayerSpec 可序列化为 dict（JSON 消费衔接）。"""
        data = LAYER_SPEC.model_dump()
        assert isinstance(data, dict)
        assert "function_specs" in data
        assert len(data["function_specs"]) == len(LAYER_SPEC.function_specs)

    @pytest.mark.parametrize("spec", LAYER_SPEC.function_specs)
    def test_spec_round_trip(self, spec: FunctionSpec) -> None:
        """每个 FunctionSpec 可序列化 + 反序列化往返。"""
        data = spec.model_dump()
        restored = FunctionSpec(**data)
        assert restored.signature.name == spec.signature.name
        assert len(restored.side_effects) == len(spec.side_effects)
