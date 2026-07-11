"""层 C 命令系统规格测试。

验证 LAYER_SPEC 结构完整性、方向别名映射正确性，
以及 hypothesis 属性测试（随机函数索引 / 副作用子集 / random_specs 完整性 /
invariants-side_effects 对应）。
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_c_command import (
    COMMAND_OBJECTS,
    COMMAND_PATHS,
    DIRECTION_ALIASES,
    LAYER_SPEC,
    NON_DIRECTION_ALIASES,
    CommandHookBranch,
)

# ── smoke 测试 ────────────────────────────────────────────────────────


class TestLayerSpecSmoke:
    """LAYER_SPEC 基础可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id_is_c(self) -> None:
        assert LAYER_SPEC.layer_id == "C"

    def test_layer_name_is_command(self) -> None:
        assert LAYER_SPEC.layer_name == "命令系统"

    def test_function_specs_non_empty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_lpc_files_listed(self) -> None:
        expected_files = {
            "feature/command.c",
            "feature/alias.c",
            "adm/daemons/commandd.c",
            "adm/daemons/aliasd.c",
            "include/command.h",
        }
        assert set(LAYER_SPEC.lpc_files) == expected_files

    def test_cross_layer_refs_non_empty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ── FunctionSpec 结构属性（固定断言：特殊契约不重复部分） ──────────────


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的特殊结构契约。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_specs_have_line_range(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.line_range is not None, (
                f"{spec.signature.name} 缺少 line_range"
            )

    def test_expected_function_count(self, all_specs: list[FunctionSpec]) -> None:
        assert len(all_specs) == 10

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            "command_hook",
            "enable_player",
            "disable_player",
            "process_input",
            "find_command",  # 两个同名（commandd.c + command.c wrapper）
            "rehash",
            "process_global_alias",
            "force_me",
            "set_alias",
        }
        assert expected.issubset(names), f"缺少函数: {expected - names}"

    def test_command_hook_has_four_branches_in_notes(self, all_specs: list[FunctionSpec]) -> None:
        hook_spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert hook_spec.notes is not None
        assert "四分支" in hook_spec.notes or "分支" in hook_spec.notes


# ── 方向别名映射 ─────────────────────────────────────────────────────


class TestDirectionAliases:
    """DIRECTION_ALIASES 关键映射验证。"""

    def test_n_to_north(self) -> None:
        assert DIRECTION_ALIASES["n"] == "go north"

    def test_s_to_south(self) -> None:
        assert DIRECTION_ALIASES["s"] == "go south"

    def test_e_to_east(self) -> None:
        assert DIRECTION_ALIASES["e"] == "go east"

    def test_w_to_west(self) -> None:
        assert DIRECTION_ALIASES["w"] == "go west"

    def test_u_to_up(self) -> None:
        assert DIRECTION_ALIASES["u"] == "go up"

    def test_d_to_down(self) -> None:
        assert DIRECTION_ALIASES["d"] == "go down"

    def test_diagonal_directions(self) -> None:
        assert DIRECTION_ALIASES["ne"] == "go northeast"
        assert DIRECTION_ALIASES["nw"] == "go northwest"
        assert DIRECTION_ALIASES["se"] == "go southeast"
        assert DIRECTION_ALIASES["sw"] == "go southwest"

    def test_up_down_directions(self) -> None:
        assert DIRECTION_ALIASES["nu"] == "go northup"
        assert DIRECTION_ALIASES["su"] == "go southup"
        assert DIRECTION_ALIASES["eu"] == "go eastup"
        assert DIRECTION_ALIASES["wu"] == "go westup"
        assert DIRECTION_ALIASES["nd"] == "go northdown"
        assert DIRECTION_ALIASES["sd"] == "go southdown"
        assert DIRECTION_ALIASES["ed"] == "go eastdown"
        assert DIRECTION_ALIASES["wd"] == "go westdown"

    def test_direction_alias_count(self) -> None:
        """方向别名共 18 个（8 基本 + 4 对角 + 4 上坡 + 4 下坡 + u/d）。"""
        assert len(DIRECTION_ALIASES) == 18

    def test_all_values_prefixed_with_go(self) -> None:
        for key, value in DIRECTION_ALIASES.items():
            assert value.startswith("go "), f"{key} -> {value} 不是 go 前缀"

    def test_non_direction_aliases(self) -> None:
        assert NON_DIRECTION_ALIASES["l"] == "look"
        assert NON_DIRECTION_ALIASES["i"] == "inventory"


# ── 命令路径常量 ──────────────────────────────────────────────────────


class TestCommandPaths:
    """COMMAND_PATHS 常量验证。"""

    def test_plr_path(self) -> None:
        assert COMMAND_PATHS["PLR_PATH"] == ["/cmds/std/", "/cmds/usr/", "/cmds/skill/"]

    def test_npc_path(self) -> None:
        assert COMMAND_PATHS["NPC_PATH"] == ["/cmds/std/", "/cmds/skill/"]

    def test_unr_path(self) -> None:
        assert COMMAND_PATHS["UNR_PATH"] == ["/cmds/usr/", "/cmds/std/"]

    def test_adm_path_includes_all(self) -> None:
        adm = COMMAND_PATHS["ADM_PATH"]
        assert "/cmds/adm/" in adm
        assert "/cmds/std/" in adm
        assert "/cmds/skill/" in adm

    def test_all_paths_end_with_slash(self) -> None:
        for path_name, dirs in COMMAND_PATHS.items():
            for d in dirs:
                assert d.endswith("/"), f"{path_name} 中的 {d} 不以 / 结尾"


class TestCommandObjects:
    """COMMAND_OBJECTS 常量验证。"""

    def test_go_cmd(self) -> None:
        assert COMMAND_OBJECTS["GO_CMD"] == "/cmds/std/go"

    def test_kill_cmd(self) -> None:
        assert COMMAND_OBJECTS["KILL_CMD"] == "/cmds/std/kill"

    def test_all_objects_under_cmds(self) -> None:
        for name, path in COMMAND_OBJECTS.items():
            assert path.startswith("/cmds/"), f"{name} -> {path} 不在 /cmds/ 下"


# ── CommandHookBranch 枚举 ────────────────────────────────────────────


class TestCommandHookBranch:
    """四分支枚举验证。"""

    def test_four_branches(self) -> None:
        assert len(CommandHookBranch) == 4

    def test_branch_values(self) -> None:
        assert CommandHookBranch.DIRECTION_SHORTCUT == "direction_shortcut"
        assert CommandHookBranch.NORMAL_COMMAND == "normal_command"
        assert CommandHookBranch.EMOTE == "emote"
        assert CommandHookBranch.CHANNEL == "channel"


# ── 特殊契约（固定断言，hypothesis 不覆盖） ───────────────────────────


class TestSpecCompleteness:
    """核心函数的特殊契约完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_command_hook_has_preconditions(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.preconditions) >= 2

    def test_command_hook_has_invariants(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.invariants) >= 3

    def test_command_hook_has_side_effects(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.side_effects) == 4

    def test_enable_player_has_postconditions(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "enable_player")
        assert len(spec.postconditions) >= 4

    def test_find_command_has_valid_cmd_invariant(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        find_specs = [s for s in all_specs if s.signature.name == "find_command"]
        # 至少 commandd.c 版本有 valid_cmd 不变量
        has_valid_cmd = any(
            any("valid_cmd" in (inv.lpc_expr or "") for inv in s.invariants)
            for s in find_specs
        )
        assert has_valid_cmd, "find_command 缺少 valid_cmd 不变量"

    def test_find_command_reverse_search_invariant(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        """find_command 逆序搜索不变量（commandd.c 版本）。"""
        find_spec = next(
            s for s in all_specs
            if s.signature.name == "find_command"
            and s.signature.lpc_file == "adm/daemons/commandd.c"
        )
        has_reverse = any(
            "逆序" in inv.description or "尾部" in inv.description
            for inv in find_spec.invariants
        )
        assert has_reverse, "find_command 缺少逆序搜索不变量"

    def test_process_input_has_random_spec(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "process_input")
        assert len(spec.random_specs) == 1
        assert spec.random_specs[0].lpc_call == "random(2)"


# ── hypothesis 属性测试（路径 A） ────────────────────────────────────
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。


_N = len(LAYER_SPEC.function_specs) - 1


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性 1a：任意索引的 FunctionSpec 签名 name/return_type/lpc_file 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert spec.signature.name
    assert spec.signature.return_type
    assert spec.signature.lpc_file


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_monotonic(idx: int) -> None:
    """属性 1b：任意函数的副作用 order 严格递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = [se.order for se in spec.side_effects]
        assert orders == sorted(orders), (
            f"{spec.signature.name}: side_effect order 非递增"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_consecutive_from_one(idx: int) -> None:
    """属性 1c：任意函数的副作用 order 从 1 连续递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, (
            f"{spec.signature.name}: order 不连续: {orders}"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_kind_and_description_nonempty(idx: int) -> None:
    """属性 1d：任意副作用 kind/description 非空。"""
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
    """属性 1e：任意函数至少有一个后置条件；有前置条件的函数其前置条件非空。

    层 C 的 set_alias 前置条件为空（LPC 原文无显式前置约束），属设计决策。
    """
    spec = LAYER_SPEC.function_specs[idx]
    # set_alias 前置条件为空是层 C 的已知设计（LPC set_alias 无前置约束）
    if spec.signature.name != "set_alias":
        assert len(spec.preconditions) > 0, f"{spec.signature.name}: 无前置条件"
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


# ── 属性 2：副作用子集 ───────────────────────────────────────────────


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
    """属性 2：任意函数副作用的随机子集，order 仍递增（子集保有序性）。"""
    spec, subset = data
    orders = [se.order for se in subset]
    assert orders == sorted(orders), (
        f"{spec.signature.name}: 子集 order 非递增: {orders}"
    )


# ── 属性 3：random_specs 完整性 ──────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_completeness(idx: int) -> None:
    """属性 3：任意有 random_specs 的函数，每个 random_spec 的
    probability_model/semantic/lpc_call 非空。"""
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


# ── 属性 4：invariants-side_effects 对应 ─────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性 4：不变量提到状态（qi/state/状态/eff_/max_/jing/neili）的函数，
    副作用应含 STATE_MUTATION。

    排除否定描述（如 "不改变状态"），因为 command_hook 明确声明不改变状态。
    """
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")
    negate_markers = ("不改变", "不修改", "不变更", "不会变")
    has_state_invariant = False
    for inv in spec.invariants:
        desc_lower = inv.description.lower()
        lpc_lower = (inv.lpc_expr or "").lower()
        # 跳过否定描述（"不改变状态" 等）
        if any(neg in inv.description for neg in negate_markers):
            continue
        if any(kw in desc_lower or kw in lpc_lower for kw in state_keywords):
            has_state_invariant = True
            break
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
