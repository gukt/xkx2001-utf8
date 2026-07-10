"""层 D：世界构建 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="D"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增
- go 命令副作用交织顺序验证
- valid_leave override 模式分类完整性
- 跨层引用非空
"""

from __future__ import annotations

import pytest

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
# 结构属性测试
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_signatures_have_name(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.name, f"函数名不能为空: {spec}"

    def test_all_signatures_have_return_type(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.return_type, (
                f"返回类型不能为空: {spec.signature.name}"
            )

    def test_all_signatures_have_lpc_file(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.lpc_file, (
                f"lpc_file 不能为空: {spec.signature.name}"
            )

    def test_all_specs_have_preconditions(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert len(spec.preconditions) > 0, (
                f"应至少有一个前置条件: {spec.signature.name}"
            )

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
# 副作用 order 测试
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 唯一且递增。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_order_unique_per_function(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            orders = [se.order for se in spec.side_effects]
            assert len(orders) == len(set(orders)), (
                f"副作用 order 不唯一: {spec.signature.name} orders={orders}"
            )

    def test_order_starts_from_1(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            orders = sorted(se.order for se in spec.side_effects)
            assert orders[0] == 1, (
                f"order 应从 1 开始: {spec.signature.name} first={orders[0]}"
            )

    def test_order_consecutive(self, all_specs: list[FunctionSpec]) -> None:
        """order 应连续递增（1, 2, 3, ... 无跳号）。"""
        for spec in all_specs:
            orders = sorted(se.order for se in spec.side_effects)
            expected = list(range(1, len(orders) + 1))
            assert orders == expected, (
                f"order 不连续: {spec.signature.name} orders={orders}"
            )


# ---------------------------------------------------------------------------
# go 命令副作用交织顺序测试
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
# valid_leave 契约测试
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
# 门机制测试
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
# follow_me 测试
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
# do_flee 测试
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
