"""层 B：对象基础规格测试。

验证 LAYER_SPEC 的结构完整性、六要素覆盖率和跨文件完整性。
"""

from __future__ import annotations

import pytest

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffect
from xkx.spec.layer_b_object_base import LAYER_SPEC

# ──────────────────────── smoke 测试 ────────────────────────


class TestSmoke:
    """LAYER_SPEC 基础可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id_is_b(self) -> None:
        assert LAYER_SPEC.layer_id == "B"

    def test_layer_name_is_object_base(self) -> None:
        assert LAYER_SPEC.layer_name == "对象基础"

    def test_function_specs_non_empty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

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


# ──────────────────────── 结构属性 ────────────────────────


class TestStructure:
    """每个 FunctionSpec 的结构完整性。"""

    def test_all_signatures_have_name(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            assert spec.signature.name, f"函数签名 name 为空: {spec}"

    def test_all_signatures_have_lpc_file(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            assert spec.signature.lpc_file, f"lpc_file 为空: {spec.signature.name}"

    def test_all_signatures_have_return_type(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            assert spec.signature.return_type, (
                f"return_type 为空: {spec.signature.name}"
            )

    def test_function_names_unique(self) -> None:
        """函数名唯一（同层内不重复提取）。"""
        names = [s.signature.name for s in LAYER_SPEC.function_specs]
        assert len(names) == len(set(names)), f"函数名重复: {names}"

    def test_each_spec_has_at_least_one_postcondition(self) -> None:
        """每个函数至少有一个后置条件。"""
        for spec in LAYER_SPEC.function_specs:
            assert len(spec.postconditions) > 0, (
                f"无后置条件: {spec.signature.name}"
            )


# ──────────────────────── 副作用 order 唯一且递增 ────────────────────────


class TestSideEffects:
    """副作用 order 在每个函数内唯一且递增。"""

    def test_side_effect_order_unique_per_function(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            orders = [se.order for se in spec.side_effects]
            if orders:
                assert len(orders) == len(set(orders)), (
                    f"副作用 order 重复: {spec.signature.name} orders={orders}"
                )

    def test_side_effect_order_sequential(self) -> None:
        """副作用 order 从 1 开始连续递增。"""
        for spec in LAYER_SPEC.function_specs:
            orders = sorted(se.order for se in spec.side_effects)
            if orders:
                assert orders == list(range(1, len(orders) + 1)), (
                    f"副作用 order 非连续递增: {spec.signature.name} orders={orders}"
                )

    def test_all_side_effects_have_kind(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            for se in spec.side_effects:
                assert se.kind is not None, (
                    f"副作用 kind 为空: {spec.signature.name}"
                )

    def test_all_side_effects_have_description(self) -> None:
        for spec in LAYER_SPEC.function_specs:
            for se in spec.side_effects:
                assert se.description, (
                    f"副作用 description 为空: {spec.signature.name}"
                )


# ──────────────────────── 文件覆盖率 ────────────────────────


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

    def test_message_has_receive_message(self) -> None:
        msg_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/message.c"
        ]
        names = {s.signature.name for s in msg_funcs}
        assert "receive_message" in names

    def test_save_has_save_and_restore(self) -> None:
        save_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/save.c"
        ]
        names = {s.signature.name for s in save_funcs}
        assert {"save", "restore"}.issubset(names)

    def test_clean_up_has_clean_up(self) -> None:
        cu_funcs = [
            s for s in LAYER_SPEC.function_specs
            if s.signature.lpc_file == "feature/clean_up.c"
        ]
        names = {s.signature.name for s in cu_funcs}
        assert "clean_up" in names


# ──────────────────────── 关键不变量验证 ────────────────────────


class TestKeyInvariants:
    """验证从 LPC 源码提取的关键不变量。"""

    def test_set_query_consistency_invariant_exists(self) -> None:
        """set 后 query 立即可读的不变量。"""
        set_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set"
        )
        inv_descs = [inv.description for inv in set_spec.invariants]
        assert any("query" in d and "可读" in d for d in inv_descs), (
            "set 缺少 'query 立即可读' 不变量"
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

    def test_move_encumbrance_cascade_invariant_exists(self) -> None:
        """move 的负重级联不变量。"""
        add_enc_spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "add_encumbrance"
        )
        inv_descs = [inv.description for inv in add_enc_spec.invariants]
        assert any("级联" in d for d in inv_descs), (
            "add_encumbrance 缺少 '级联' 不变量"
        )

    def test_move_weight_precondition_exists(self) -> None:
        """move 有负重不超限前置条件。"""
        move_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "move"
        )
        precond_descs = [p.description for p in move_spec.preconditions]
        assert any("负重" in d or "encumbrance" in d.lower() for d in precond_descs), (
            "move 缺少负重前置条件"
        )

    def test_receive_message_has_random_spec(self) -> None:
        """receive_message 有 blind condition 随机性。"""
        rm_spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "receive_message"
        )
        assert len(rm_spec.random_specs) > 0, "receive_message 缺少随机性规格"

    def test_cross_layer_refs_non_empty(self) -> None:
        """跨层引用列表非空。"""
        assert len(LAYER_SPEC.cross_layer_refs) > 0

    def test_short_is_look_base(self) -> None:
        """short 的 notes 或 postconditions 提及 look 关联。"""
        short_spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "short"
        )
        all_text = (
            short_spec.notes or ""
            + " ".join(p.description for p in short_spec.postconditions)
        )
        assert "look" in all_text.lower() or "look" in (short_spec.notes or "").lower(), (
            "short 未标注与 look 的关联"
        )


# ──────────────────────── FunctionSpec 类型验证 ────────────────────────


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
