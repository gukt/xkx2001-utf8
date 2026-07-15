"""层 F-HELL：阴间流程规格测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="F-HELL"、lpc_files 包含预期阴间文件
- 层 ID 不与现有 9 层 A-I 冲突
- FunctionSpec 签名/前置/后置/不变量/副作用结构完整
- 副作用 order 从 1 连续递增（hypothesis）
- 关键领域断言：DEATH_ROOM / REVIVE_ROOM 常量、地狱白名单、死刑室白名单
- 关键函数结构：gate_init 剥离物品、road2_valid_leave 5 步迷宫、
  wgargoyle_death_stage 5 段还阳、hell_block_cmd 白名单、
  logind 登录检查优先级
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_f_hell import (
    DEATH_ROOM,
    EXECUTION_CMD_WHITELIST,
    EXECUTION_ROOM,
    HELL_CMD_WHITELIST,
    LAYER_SPEC,
    REVIVE_ROOM,
    WIZARD_ROOM,
    XKD_START_ROOM,
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
        assert LAYER_SPEC.layer_id == "F-HELL"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "阴间流程"

    def test_lpc_files_complete(self) -> None:
        expected = {
            "d/death/gate.c",
            "d/death/gateway.c",
            "d/death/road1.c",
            "d/death/road2.c",
            "d/death/inn1.c",
            "d/death/inn2.c",
            "d/death/npc/wgargoyle.c",
            "d/death/npc/bgargoyle.c",
            "d/death/hell.c",
            "d/death/death.c",
            "d/death/block.c",
            "d/death/blkbot.c",
            "d/death/noteroom.c",
            "adm/daemons/logind.c",
            "feature/damage.c",
            "include/login.h",
        }
        assert set(LAYER_SPEC.lpc_files) == expected

    def test_function_spec_count(self) -> None:
        assert len(LAYER_SPEC.function_specs) == 35

    def test_expected_function_names(self) -> None:
        names = {spec.signature.name for spec in LAYER_SPEC.function_specs}
        expected = {
            # 房间 create / init / valid_leave / block_cmd / reset
            "create",
            "init",
            "valid_leave",
            "block_cmd",
            "reset",
            # inn1 隐藏还阳
            "redirect_ask",
            "do_stuff",
            # 无常 NPC
            "death_stage",
            # 登录检查
            "enter_world_hell_checks",
            # damage.c 引用
            "is_ghost",
            "reincarnate",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# 层 ID 唯一性
# ---------------------------------------------------------------------------


class TestLayerUniqueness:
    """LayerSpec layer_id 唯一 + 不与现有 9 层重名。"""

    def test_layer_id_not_in_existing_nine(self) -> None:
        assert LAYER_SPEC.layer_id not in EXISTING_LAYER_IDS, (
            f"layer_id {LAYER_SPEC.layer_id} 与现有 9 层冲突"
        )


# ---------------------------------------------------------------------------
# 关键函数签名与结构完整性
# ---------------------------------------------------------------------------


class TestFunctionSpecSignature:
    """核心函数签名与契约结构完整。"""

    @pytest.fixture
    def gate_init(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "init" and s.signature.lpc_file == "d/death/gate.c"
        )

    @pytest.fixture
    def gateway_valid_leave(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "valid_leave"
            and s.signature.lpc_file == "d/death/gateway.c"
        )

    @pytest.fixture
    def road2_valid_leave(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "valid_leave"
            and s.signature.lpc_file == "d/death/road2.c"
        )

    @pytest.fixture
    def inn1_do_stuff(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "do_stuff"
        )

    @pytest.fixture
    def wgargoyle_death_stage(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "death_stage"
            and s.signature.lpc_file == "d/death/npc/wgargoyle.c"
        )

    @pytest.fixture
    def bgargoyle_death_stage(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "death_stage"
            and s.signature.lpc_file == "d/death/npc/bgargoyle.c"
        )

    @pytest.fixture
    def hell_block_cmd(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "block_cmd"
            and s.signature.lpc_file == "d/death/hell.c"
        )

    @pytest.fixture
    def death_block_cmd(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "block_cmd"
            and s.signature.lpc_file == "d/death/death.c"
        )

    @pytest.fixture
    def logind_hell_checks(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "enter_world_hell_checks"
        )

    def test_gate_init_strips_inventory(self, gate_init: FunctionSpec) -> None:
        descs = " ".join(se.description for se in gate_init.side_effects)
        assert "inventory" in descs or "物品" in descs
        assert any("clear_condition" in (se.lpc_call or "") for se in gate_init.side_effects)

    def test_gateway_valid_leave_blocks_south(
        self, gateway_valid_leave: FunctionSpec
    ) -> None:
        assert gateway_valid_leave.signature.return_type == "int"
        descs = " ".join(pc.description for pc in gateway_valid_leave.postconditions)
        assert "south" in descs or "南" in descs

    def test_road2_valid_leave_five_step_maze(
        self, road2_valid_leave: FunctionSpec
    ) -> None:
        descs = " ".join(pc.description for pc in road2_valid_leave.postconditions)
        assert "5" in descs or "五" in descs or "long_road" in descs

    def test_inn1_do_stuff_reincarnates(self, inn1_do_stuff: FunctionSpec) -> None:
        calls = " ".join(se.lpc_call or "" for se in inn1_do_stuff.side_effects)
        assert "reincarnate" in calls
        assert any("/d/city/wumiao" in (se.lpc_call or "") for se in inn1_do_stuff.side_effects)

    def test_wgargoyle_death_stage_five_messages(
        self, wgargoyle_death_stage: FunctionSpec
    ) -> None:
        assert wgargoyle_death_stage.signature.params[1].name == "stage"
        effects = " ".join(pc.description for pc in wgargoyle_death_stage.postconditions)
        assert "reincarnate" in effects

    def test_bgargoyle_death_stage_ghost_check(
        self, bgargoyle_death_stage: FunctionSpec
    ) -> None:
        descs = " ".join(pc.description for pc in bgargoyle_death_stage.postconditions)
        assert "is_ghost" in descs or "鬼魂" in descs or "阳人" in descs

    def test_hell_block_cmd_whitelist(self, hell_block_cmd: FunctionSpec) -> None:
        assert hell_block_cmd.signature.return_type == "int"
        descs = " ".join(inv.description for inv in hell_block_cmd.invariants)
        assert "say" in descs and "goto" in descs

    def test_death_block_cmd_stricter(self, death_block_cmd: FunctionSpec) -> None:
        descs = " ".join(inv.description for inv in death_block_cmd.invariants)
        assert "quit" in descs and "suicide" in descs and "goto" in descs
        # 死刑室不应包含 look（比地狱更严格）
        assert "look" not in descs

    def test_logind_hell_checks_priority(self, logind_hell_checks: FunctionSpec) -> None:
        assert logind_hell_checks.signature.lpc_file == "adm/daemons/logind.c"
        effects = " ".join(se.lpc_call or "" for se in logind_hell_checks.side_effects)
        assert "is_ghost" in effects
        assert "death_count" in effects


# ---------------------------------------------------------------------------
# 领域常量断言
# ---------------------------------------------------------------------------


class TestDomainConstants:
    """层 F-HELL 导出的领域常量与 LPC 源码一致。"""

    def test_death_room(self) -> None:
        assert DEATH_ROOM == "/d/death/gate.c"

    def test_revive_room(self) -> None:
        assert REVIVE_ROOM == "/d/city/wumiao.c"

    def test_xkd_start_room(self) -> None:
        assert XKD_START_ROOM == "/d/xiakedao/shatan"

    def test_execution_room(self) -> None:
        assert EXECUTION_ROOM == "/d/death/block.c"

    def test_wizard_room(self) -> None:
        assert WIZARD_ROOM == "/d/wizard/wizard_room"

    def test_hell_cmd_whitelist(self) -> None:
        assert "say" in HELL_CMD_WHITELIST
        assert "tell" in HELL_CMD_WHITELIST
        assert "reply" in HELL_CMD_WHITELIST
        assert "who" in HELL_CMD_WHITELIST
        assert "look" in HELL_CMD_WHITELIST
        assert "quit" in HELL_CMD_WHITELIST
        assert "suicide" in HELL_CMD_WHITELIST
        assert "goto" in HELL_CMD_WHITELIST
        assert "go" not in HELL_CMD_WHITELIST

    def test_execution_cmd_whitelist(self) -> None:
        assert {"quit", "suicide", "goto"} == EXECUTION_CMD_WHITELIST


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
            if targets - {LAYER_SPEC.layer_id}:
                other_refs += 1
        assert other_refs > 0, "cross_layer_refs 无任何跨层引用"


# ---------------------------------------------------------------------------
# 副作用顺序契约
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 从 1 连续递增。"""

    def test_gate_init_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "init" and s.signature.lpc_file == "d/death/gate.c"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"gate_init order 不连续: {orders}"

    def test_wgargoyle_death_stage_side_effect_order_consecutive(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "death_stage"
            and s.signature.lpc_file == "d/death/npc/wgargoyle.c"
        )
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, f"wgargoyle_death_stage order 不连续: {orders}"


# ---------------------------------------------------------------------------
# hypothesis 属性测试
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
