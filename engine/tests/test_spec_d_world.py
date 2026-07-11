"""层 D：世界构建 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="D"、function_specs 非空
- go 命令副作用交织顺序验证（14 副作用特殊契约）
- valid_leave override 模式分类完整性（8 种模式分类）
- 门机制 / follow_me / do_flee 特殊契约
- 跨层引用非空

路径 A hypothesis 属性测试（4 类）：
1. 随机函数索引：签名完整 / 副作用 order 递增+连续 / kind+description 非空 / pre+post 条件
2. 副作用子集：随机子集 order 仍递增
3. random_specs 完整性：probability_model / semantic / lpc_call 非空
4. invariants-side_effects 对应：状态不变量 -> STATE_MUTATION
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_d_world import (
    LAYER_SPEC,
    DoorStatus,
    ValidLeaveOverridePattern,
)

# ---------------------------------------------------------------------------
# smoke 测试
# ---------------------------------------------------------------------------


class TestSmoke:
    """LAYER_SPEC 基本可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id(self) -> None:
        assert LAYER_SPEC.layer_id == "D"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "世界构建"

    def test_lpc_files(self) -> None:
        assert "inherit/room/room.c" in LAYER_SPEC.lpc_files
        assert "cmds/std/go.c" in LAYER_SPEC.lpc_files
        assert "feature/team.c" in LAYER_SPEC.lpc_files

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 9 个 FunctionSpec：valid_leave, make_inventory, reset,
        create_door, open_door, close_door, go main, do_flee, follow_me。"""
        assert len(LAYER_SPEC.function_specs) == 9

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# 结构属性测试（仅保留 hypothesis 未覆盖的特殊契约）
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性（hypothesis 未覆盖部分）。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_specs_have_side_effects(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert len(spec.side_effects) > 0, (
                f"应至少有一个副作用: {spec.signature.name}"
            )

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            "valid_leave",
            "make_inventory",
            "reset",
            "create_door",
            "open_door",
            "close_door",
            "main",
            "do_flee",
            "follow_me",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"


# ---------------------------------------------------------------------------
# go 命令副作用交织顺序测试（14 副作用特殊契约，保留）
# ---------------------------------------------------------------------------


class TestGoMainInterleaving:
    """go main() 的副作用交织顺序是核心契约。"""

    @pytest.fixture
    def go_main(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "main"
        )

    def test_go_has_many_side_effects(self, go_main: FunctionSpec) -> None:
        """go main 有大量副作用（至少 10 个）。"""
        assert len(go_main.side_effects) >= 10

    def test_valid_leave_before_move(self, go_main: FunctionSpec) -> None:
        """valid_leave 调用必须在 move 之前。"""
        vl = next(
            se for se in go_main.side_effects if "valid_leave" in se.description
        )
        move = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.OBJECT_LIFECYCLE and "move" in se.description
        )
        assert vl.order < move.order

    def test_mout_message_before_move(self, go_main: FunctionSpec) -> None:
        """旧房间离开消息 (mout) 在 move 之前输出。"""
        mout = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.MESSAGE_OUTPUT and "离开消息" in se.description
        )
        move = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.OBJECT_LIFECYCLE and "move" in se.description
        )
        assert mout.order < move.order

    def test_move_before_min_message(self, go_main: FunctionSpec) -> None:
        """新房间到达消息 (min) 在 move 之后输出。"""
        move = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.OBJECT_LIFECYCLE and "move" in se.description
        )
        min_msg = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.MESSAGE_OUTPUT and "到达消息" in se.description
        )
        assert move.order < min_msg.order

    def test_move_before_follow_me(self, go_main: FunctionSpec) -> None:
        """follow_me 调用在 move 之后。"""
        move = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.OBJECT_LIFECYCLE and "move" in se.description
        )
        follow = next(
            se for se in go_main.side_effects if "follow_me" in se.description
        )
        assert move.order < follow.order

    def test_full_interleaving_sequence(self, go_main: FunctionSpec) -> None:
        """完整交织顺序：valid_leave -> mout -> move -> min -> follow_me。"""
        vl = next(
            se for se in go_main.side_effects if "valid_leave" in se.description
        )
        mout = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.MESSAGE_OUTPUT and "离开消息" in se.description
        )
        move = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.OBJECT_LIFECYCLE and "move" in se.description
        )
        min_msg = next(
            se
            for se in go_main.side_effects
            if se.kind == SideEffectType.MESSAGE_OUTPUT and "到达消息" in se.description
        )
        follow = next(
            se for se in go_main.side_effects if "follow_me" in se.description
        )
        assert vl.order < mout.order < move.order < min_msg.order < follow.order

    def test_go_has_random_specs(self, go_main: FunctionSpec) -> None:
        """go main 有随机性规格（逃跑判定等）。"""
        assert len(go_main.random_specs) >= 1

    def test_go_has_invariants(self, go_main: FunctionSpec) -> None:
        """go main 有不变量（move 原子性 + 交织顺序）。"""
        assert len(go_main.invariants) >= 2


# ---------------------------------------------------------------------------
# valid_leave 契约测试（8 种 override 模式分类，保留）
# ---------------------------------------------------------------------------


class TestValidLeaveContract:
    """valid_leave 基类契约是 dissent 4 的核心。"""

    @pytest.fixture
    def valid_leave(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "valid_leave"
        )

    def test_return_value_semantics(self, valid_leave: FunctionSpec) -> None:
        """返回值语义明确：1=允许, 0=拒绝。"""
        post = next(
            p for p in valid_leave.postconditions if p.return_value is not None
        )
        assert "1" in post.return_value and "0" in post.return_value

    def test_has_door_check_invariant(self, valid_leave: FunctionSpec) -> None:
        """有门关闭时拒绝离开的不变量。"""
        assert any(
            "DOOR_CLOSED" in inv.lpc_expr or "门关闭" in inv.description
            for inv in valid_leave.invariants
        )

    def test_has_notes_about_overrides(self, valid_leave: FunctionSpec) -> None:
        """notes 中提到 override 模式分类。"""
        assert valid_leave.notes is not None
        assert "override" in valid_leave.notes.lower() or "模式" in valid_leave.notes

    def test_valid_leave_override_patterns(self) -> None:
        """ValidLeaveOverridePattern 枚举覆盖关键模式。"""
        patterns = list(ValidLeaveOverridePattern)
        assert len(patterns) == 8
        assert ValidLeaveOverridePattern.DOOR_CHECK == "door_check"
        assert ValidLeaveOverridePattern.HOSTILE_NPC == "hostile_npc"
        assert ValidLeaveOverridePattern.FACTION_GATE == "faction_gate"
        assert ValidLeaveOverridePattern.QUEST_FLAG == "quest_flag"
        assert ValidLeaveOverridePattern.COMPOSITE == "composite"


# ---------------------------------------------------------------------------
# 门机制测试（保留）
# ---------------------------------------------------------------------------


class TestDoorMechanism:
    """门机制：create_door / open_door / close_door 契约。"""

    def test_door_status_constants(self) -> None:
        assert DoorStatus.CLOSED == "1"
        assert DoorStatus.LOCKED == "2"
        assert DoorStatus.SMASHED == "4"

    def test_create_door_has_cross_room_sync(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "create_door"
        )
        assert any(
            se.kind == SideEffectType.EXTERNAL and "check_door" in se.description
            for se in spec.side_effects
        )

    def test_open_door_has_cross_room_sync(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "open_door"
        )
        assert any(
            se.kind == SideEffectType.EXTERNAL and "递归" in se.description
            for se in spec.side_effects
        )

    def test_close_door_has_cross_room_sync(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "close_door"
        )
        assert any(
            se.kind == SideEffectType.EXTERNAL and "递归" in se.description
            for se in spec.side_effects
        )

    def test_open_door_state_change(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "open_door"
        )
        assert any(
            "DOOR_CLOSED" in (se.lpc_call or "")
            for se in spec.side_effects
            if se.kind == SideEffectType.STATE_MUTATION
        )

    def test_close_door_state_change(self) -> None:
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "close_door"
        )
        assert any(
            "DOOR_CLOSED" in (se.lpc_call or "")
            for se in spec.side_effects
            if se.kind == SideEffectType.STATE_MUTATION
        )


# ---------------------------------------------------------------------------
# follow_me 测试（保留）
# ---------------------------------------------------------------------------


class TestFollowMe:
    """follow_me 组队跟随契约。"""

    @pytest.fixture
    def follow_me(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "follow_me"
        )

    def test_has_random_spec(self, follow_me: FunctionSpec) -> None:
        """follow_me 有移动技能判定的随机性。"""
        assert len(follow_me.random_specs) >= 1
        rs = follow_me.random_specs[0]
        assert "move" in rs.lpc_call.lower() or "move" in rs.semantic

    def test_has_call_out_side_effect(self, follow_me: FunctionSpec) -> None:
        """follow_me 有延迟跟随的副作用（call_out 或 follow_path）。"""
        assert any(
            "call_out" in (se.lpc_call or "") or "follow_path" in (se.lpc_call or "")
            for se in follow_me.side_effects
        )

    def test_leader_check_precondition(self, follow_me: FunctionSpec) -> None:
        """有 leader 或 pursuer 检查的前置条件。"""
        assert any(
            "leader" in pre.lpc_expr or "leader" in pre.description
            for pre in follow_me.preconditions
        )


# ---------------------------------------------------------------------------
# do_flee 测试（保留）
# ---------------------------------------------------------------------------


class TestDoFlee:
    """do_flee 逃跑契约。"""

    @pytest.fixture
    def do_flee(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_flee"
        )

    def test_delegates_to_go_main(self, do_flee: FunctionSpec) -> None:
        """do_flee 委托 go main() 执行移动。"""
        assert any(
            "main" in (se.lpc_call or "") for se in do_flee.side_effects
        )

    def test_has_random_direction(self, do_flee: FunctionSpec) -> None:
        """有随机选择方向的随机性规格。"""
        assert len(do_flee.random_specs) >= 1


# ---------------------------------------------------------------------------
# hypothesis 属性测试（路径 A）
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。
# ---------------------------------------------------------------------------

_N = len(LAYER_SPEC.function_specs) - 1


# ── 类 1：随机函数索引 ──────────────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性：任意索引的 FunctionSpec 签名完整（name/return_type/lpc_file 非空）。"""
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
    """属性：任意函数至少有一个前置条件和一个后置条件。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.preconditions) > 0, f"{spec.signature.name}: 无前置条件"
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


# ── 类 2：副作用子集 ────────────────────────────────────────────────────────


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


# ── 类 3：random_specs 完整性 ───────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_fields_nonempty(idx: int) -> None:
    """属性：任意有 random_specs 的函数，每个 random_spec 的
    probability_model / semantic / lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.lpc_call, f"{spec.signature.name}: random_spec lpc_call 为空"
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec probability_model 为空"
        )
        assert rs.semantic, f"{spec.signature.name}: random_spec semantic 为空"


# ── 类 4：invariants-side_effects 对应 ─────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态（qi/state/状态/eff_/max_/jing/neili）的函数，
    副作用含 STATE_MUTATION。"""
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
