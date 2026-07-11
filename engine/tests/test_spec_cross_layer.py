"""跨层规格一致性属性测试（任务 3 路径 A）。

聚合 9 层 LAYER_SPEC，验证跨层一致性（不依赖被测实现）：
- 9 层完整性（layer_id A-I 唯一、layer_name 不重）
- cross_layer_refs 跨层可解析（每条引用提到的目标层在 9 层范围内）
- 全局函数可索引（hypothesis 任意层 + 函数索引签名完整）
- 跨层共享 lpc_files / 函数名是已知合理模式（同文件多函数分属不同层）
"""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.layer_a_driver import LAYER_SPEC as LAYER_A
from xkx.spec.layer_b_object_base import LAYER_SPEC as LAYER_B
from xkx.spec.layer_c_command import LAYER_SPEC as LAYER_C
from xkx.spec.layer_d_world import LAYER_SPEC as LAYER_D
from xkx.spec.layer_e_combat import LAYER_SPEC as LAYER_E
from xkx.spec.layer_f_death import LAYER_SPEC as LAYER_F
from xkx.spec.layer_g_npc_ai import LAYER_SPEC as LAYER_G
from xkx.spec.layer_h_daemons import LAYER_SPEC as LAYER_H
from xkx.spec.layer_i_character import LAYER_SPEC as LAYER_I

ALL_LAYERS = [
    LAYER_A,
    LAYER_B,
    LAYER_C,
    LAYER_D,
    LAYER_E,
    LAYER_F,
    LAYER_G,
    LAYER_H,
    LAYER_I,
]
EXPECTED_IDS = set("ABCDEFGHI")

_LAYER_REF_RE = re.compile(r"层\s*([A-I])")


# ---------------------------------------------------------------------------
# 9 层完整性
# ---------------------------------------------------------------------------


class TestLayerCompleteness:
    """9 层 LAYER_SPEC 完整性与唯一性。"""

    def test_nine_layers_present(self) -> None:
        assert len(ALL_LAYERS) == 9

    def test_layer_ids_unique_and_complete(self) -> None:
        ids = {layer.layer_id for layer in ALL_LAYERS}
        assert ids == EXPECTED_IDS, f"层 ID 不完整: {EXPECTED_IDS - ids}"

    def test_layer_names_unique(self) -> None:
        names = [layer.layer_name for layer in ALL_LAYERS]
        assert len(names) == len(set(names)), f"层名重复: {names}"

    def test_all_layers_have_function_specs(self) -> None:
        for layer in ALL_LAYERS:
            assert len(layer.function_specs) > 0, (
                f"层 {layer.layer_id} 无 function_specs"
            )

    def test_all_layers_have_lpc_files(self) -> None:
        for layer in ALL_LAYERS:
            assert len(layer.lpc_files) > 0, f"层 {layer.layer_id} 无 lpc_files"

    def test_all_layers_have_cross_layer_refs(self) -> None:
        """每层至少有一条跨层引用（9 层非独立，必有依赖）。"""
        for layer in ALL_LAYERS:
            assert len(layer.cross_layer_refs) > 0, (
                f"层 {layer.layer_id} 无 cross_layer_refs"
            )


# ---------------------------------------------------------------------------
# cross_layer_refs 跨层可解析
# ---------------------------------------------------------------------------


class TestCrossLayerRefs:
    """cross_layer_refs 提到的目标层 ID 在 9 层范围内。"""

    def test_refs_target_existing_layers(self) -> None:
        """每条 cross_layer_refs 提到的层 ID（若有）在 A-I 范围内。"""
        for layer in ALL_LAYERS:
            for ref in layer.cross_layer_refs:
                targets = set(_LAYER_REF_RE.findall(ref))
                if targets:
                    invalid = targets - EXPECTED_IDS
                    assert not invalid, (
                        f"层 {layer.layer_id} ref 提到无效层 ID: {ref} -> {invalid}"
                    )

    def test_refs_reference_other_layers(self) -> None:
        """cross_layer_refs 应引用其他层（非自引用为主）。

        允许自引用，但整层 refs 全自引用则可能是规格提取遗漏跨层依赖。
        """
        for layer in ALL_LAYERS:
            other_refs = 0
            for ref in layer.cross_layer_refs:
                targets = set(_LAYER_REF_RE.findall(ref))
                if targets - {layer.layer_id}:
                    other_refs += 1
            assert other_refs > 0, (
                f"层 {layer.layer_id} cross_layer_refs 无任何跨层引用（全自引用）"
            )


# ---------------------------------------------------------------------------
# 跨层共享文件 / 函数名（已知合理模式）
# ---------------------------------------------------------------------------


class TestCrossLayerSharing:
    """跨层共享 lpc_files / 函数名是合理模式（同文件多函数分属不同层）。

    不强制无重复，但验证共享模式可追踪（每层 lpc_files 内部无重复）。
    """

    def test_no_duplicate_lpc_files_within_layer(self) -> None:
        """单层内 lpc_files 无重复（跨层共享允许）。"""
        for layer in ALL_LAYERS:
            files = layer.lpc_files
            assert len(files) == len(set(files)), (
                f"层 {layer.layer_id} lpc_files 内部重复: "
                f"{[f for f in files if files.count(f) > 1]}"
            )


# ---------------------------------------------------------------------------
# hypothesis 跨层属性
# ---------------------------------------------------------------------------


@given(layer_idx=st.integers(min_value=0, max_value=len(ALL_LAYERS) - 1))
def test_any_layer_structurally_valid(layer_idx: int) -> None:
    """属性：任意层 LAYER_SPEC 结构完整。"""
    layer = ALL_LAYERS[layer_idx]
    assert layer.layer_id in EXPECTED_IDS
    assert layer.layer_name
    assert len(layer.function_specs) > 0


@st.composite
def _global_function(draw: st.DrawFn):
    """跨层随机采样 (layer, FunctionSpec)。"""
    layer = draw(st.sampled_from(ALL_LAYERS))
    spec = draw(st.sampled_from(layer.function_specs))
    return layer, spec


@given(data=_global_function())
def test_global_function_spec_signature_complete(data) -> None:
    """属性：跨层任意函数签名完整（name/return_type/lpc_file 非空）。"""
    layer, spec = data
    assert spec.signature.name, f"层 {layer.layer_id}: 函数名空"
    assert spec.signature.return_type, (
        f"层 {layer.layer_id} {spec.signature.name}: return_type 空"
    )
    assert spec.signature.lpc_file, (
        f"层 {layer.layer_id} {spec.signature.name}: lpc_file 空"
    )


@given(data=_global_function())
def test_global_function_has_side_effects_or_pure(data) -> None:
    """属性：跨层任意函数要么有副作用，要么有 notes 说明纯计算。"""
    layer, spec = data
    has_side_effects = len(spec.side_effects) > 0
    has_notes = spec.notes is not None and len(spec.notes) > 0
    assert has_side_effects or has_notes, (
        f"层 {layer.layer_id} {spec.signature.name}: 无副作用且无 notes"
    )
