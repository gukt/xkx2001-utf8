"""层 F：死亡轮回 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="F"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增
- die 与 unconcious 都有规格
- make_corpse 的副作用含 OBJECT_LIFECYCLE（尸体创建）
- death_penalty 无随机性
- die/unconcious 触发条件区别
"""

from __future__ import annotations

import pytest

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_f_death import LAYER_SPEC, DeathState

# ---------------------------------------------------------------------------
# smoke 测试
# ---------------------------------------------------------------------------


class TestSmoke:
    """LAYER_SPEC 基本可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id(self) -> None:
        assert LAYER_SPEC.layer_id == "F"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "死亡轮回"

    def test_lpc_files(self) -> None:
        assert "feature/damage.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/combatd.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/chard.c" in LAYER_SPEC.lpc_files
        assert "inherit/char/char.c" in LAYER_SPEC.lpc_files

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 10 个 FunctionSpec：heart_beat, unconcious, revive, die,
        reincarnate, death_penalty, killer_reward, make_corpse, announce, heal_up。"""
        assert len(LAYER_SPEC.function_specs) == 10

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
            "heart_beat",
            "unconcious",
            "revive",
            "die",
            "reincarnate",
            "death_penalty",
            "killer_reward",
            "make_corpse",
            "announce",
            "heal_up",
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
# die 与 unconcious 规格测试
# ---------------------------------------------------------------------------


class TestDieAndUnconcious:
    """die 与 unconcious 的规格契约。"""

    @pytest.fixture
    def die_spec(self) -> FunctionSpec:
        return next(s for s in LAYER_SPEC.function_specs if s.signature.name == "die")

    @pytest.fixture
    def unconcious_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "unconcious"
        )

    def test_die_has_specs(self, die_spec: FunctionSpec) -> None:
        assert die_spec is not None
        assert die_spec.signature.name == "die"

    def test_unconcious_has_specs(self, unconcious_spec: FunctionSpec) -> None:
        assert unconcious_spec is not None
        assert unconcious_spec.signature.name == "unconcious"

    def test_die_has_many_side_effects(self, die_spec: FunctionSpec) -> None:
        """die 有大量副作用（至少 15 个）。"""
        assert len(die_spec.side_effects) >= 15

    def test_unconcious_has_call_out(self, unconcious_spec: FunctionSpec) -> None:
        """unconcious 有 call_out 副作用（安排 revive 定时器）。"""
        assert any(
            se.kind == SideEffectType.CALL_OUT or "call_out" in (se.lpc_call or "")
            for se in unconcious_spec.side_effects
        )

    def test_unconcious_has_random_spec(self, unconcious_spec: FunctionSpec) -> None:
        """unconcious 有随机性规格（revive 延迟与 con 相关）。"""
        assert len(unconcious_spec.random_specs) >= 1
        rs = unconcious_spec.random_specs[0]
        assert "con" in rs.lpc_call or "con" in rs.seed_inputs

    def test_die_has_persistence(self, die_spec: FunctionSpec) -> None:
        """die 有持久化副作用（save）。"""
        assert any(
            se.kind == SideEffectType.PERSISTENCE for se in die_spec.side_effects
        )

    def test_die_has_object_lifecycle(self, die_spec: FunctionSpec) -> None:
        """die 有对象生命周期副作用（move DEATH_ROOM / destruct NPC）。"""
        assert any(
            se.kind == SideEffectType.OBJECT_LIFECYCLE
            for se in die_spec.side_effects
        )

    def test_die_notes_mention_trigger(self, die_spec: FunctionSpec) -> None:
        """die 的 notes 提到触发条件或昏迷中死亡。"""
        assert die_spec.notes is not None
        assert "昏迷" in die_spec.notes or "trigger" in die_spec.notes.lower()

    def test_unconcious_notes_mention_difference(
        self, unconcious_spec: FunctionSpec
    ) -> None:
        """unconcious 的 notes 提到与 die 的区别。"""
        assert unconcious_spec.notes is not None
        assert "die" in unconcious_spec.notes.lower() or "死亡" in unconcious_spec.notes


# ---------------------------------------------------------------------------
# heart_beat 死亡触发条件测试
# ---------------------------------------------------------------------------


class TestHeartBeatDeathTrigger:
    """heart_beat 中的死亡触发条件是核心契约。"""

    @pytest.fixture
    def heart_beat(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "heart_beat"
        )

    def test_has_die_trigger_invariant(self, heart_beat: FunctionSpec) -> None:
        """有死亡判定优先级的不变量。"""
        assert any(
            "eff_qi" in (inv.lpc_expr or "") or "致命伤" in inv.description
            for inv in heart_beat.invariants
        )

    def test_has_unconcious_upgrade_invariant(self, heart_beat: FunctionSpec) -> None:
        """有昏迷升级为死亡的不变量。"""
        assert any(
            "昏迷" in inv.description and "die" in inv.description.lower()
            for inv in heart_beat.invariants
        )

    def test_has_wimpy_invariant(self, heart_beat: FunctionSpec) -> None:
        """有 wimpy 自动逃跑不变量。"""
        assert any(
            "wimpy" in inv.description.lower() or "wimpy" in (inv.lpc_expr or "").lower()
            for inv in heart_beat.invariants
        )

    def test_notes_explain_trigger_conditions(self, heart_beat: FunctionSpec) -> None:
        """notes 中解释了触发条件区别。"""
        assert heart_beat.notes is not None
        assert "eff_qi" in heart_beat.notes or "eff_jing" in heart_beat.notes


# ---------------------------------------------------------------------------
# death_penalty 确定性测试
# ---------------------------------------------------------------------------


class TestDeathPenalty:
    """death_penalty 死亡惩罚规格。"""

    @pytest.fixture
    def death_penalty(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "death_penalty"
        )

    def test_no_random_specs(self, death_penalty: FunctionSpec) -> None:
        """death_penalty 无随机性规格（完全确定性）。"""
        assert len(death_penalty.random_specs) == 0

    def test_has_determinism_invariant(self, death_penalty: FunctionSpec) -> None:
        """有确定性不变量（无 random 调用）。"""
        assert any(
            "random" in inv.description.lower() or "确定性" in inv.description
            for inv in death_penalty.invariants
        )

    def test_has_cap_invariant(self, death_penalty: FunctionSpec) -> None:
        """有 combat_exp 扣减上限保护不变量。"""
        assert any(
            "上限" in inv.description or "5000" in (inv.lpc_expr or "")
            for inv in death_penalty.invariants
        )

    def test_has_persistence(self, death_penalty: FunctionSpec) -> None:
        """有持久化副作用（save）。"""
        assert any(
            se.kind == SideEffectType.PERSISTENCE
            for se in death_penalty.side_effects
        )

    def test_has_skill_death_penalty_ref(self, death_penalty: FunctionSpec) -> None:
        """有 skill_death_penalty 引用（跨层 H）。"""
        assert any(
            "skill_death_penalty" in se.description or "skill_death_penalty" in (se.lpc_call or "")
            for se in death_penalty.side_effects
        )


# ---------------------------------------------------------------------------
# killer_reward 测试
# ---------------------------------------------------------------------------


class TestKillerReward:
    """killer_reward 击杀者奖励规格。"""

    @pytest.fixture
    def killer_reward(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "killer_reward"
        )

    def test_no_random_specs(self, killer_reward: FunctionSpec) -> None:
        """killer_reward 无随机性规格（完全确定性）。"""
        assert len(killer_reward.random_specs) == 0

    def test_has_free_rider_invariant(self, killer_reward: FunctionSpec) -> None:
        """有 free_rider 机制不变量。"""
        assert any(
            "free_rider" in inv.description.lower() or "free_rider" in (inv.lpc_expr or "")
            for inv in killer_reward.invariants
        )

    def test_has_message_output(self, killer_reward: FunctionSpec) -> None:
        """有消息输出副作用（谣言频道）。"""
        assert any(
            se.kind == SideEffectType.MESSAGE_OUTPUT
            for se in killer_reward.side_effects
        )


# ---------------------------------------------------------------------------
# make_corpse 测试
# ---------------------------------------------------------------------------


class TestMakeCorpse:
    """make_corpse 尸体生成规格。"""

    @pytest.fixture
    def make_corpse(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "make_corpse"
        )

    def test_has_object_lifecycle(self, make_corpse: FunctionSpec) -> None:
        """make_corpse 的副作用含 OBJECT_LIFECYCLE（尸体创建）。"""
        assert any(
            se.kind == SideEffectType.OBJECT_LIFECYCLE
            for se in make_corpse.side_effects
        )

    def test_has_new_corpse_side_effect(self, make_corpse: FunctionSpec) -> None:
        """有创建尸体对象的副作用（new(CORPSE_OB)）。"""
        assert any(
            "new" in (se.lpc_call or "") or "CORPSE" in (se.lpc_call or "")
            for se in make_corpse.side_effects
        )

    def test_has_item_transfer_invariant(self, make_corpse: FunctionSpec) -> None:
        """有物品转移完整性不变量。"""
        assert any(
            "inventory" in inv.description
            and ("空" in inv.description or "完整" in inv.description)
            for inv in make_corpse.invariants
        )

    def test_has_ghost_handling(self, make_corpse: FunctionSpec) -> None:
        """有 ghost 死者处理逻辑（不生成尸体，物品掉落）。"""
        assert any(
            "ghost" in se.description.lower() or "ghost" in (se.lpc_call or "").lower()
            for se in make_corpse.side_effects
        )

    def test_has_equipment_transfer(self, make_corpse: FunctionSpec) -> None:
        """有装备转移副作用（equipped 物品处理）。"""
        assert any(
            "equipped" in se.description or "wear" in (se.lpc_call or "")
            for se in make_corpse.side_effects
        )


# ---------------------------------------------------------------------------
# reincarnate 测试
# ---------------------------------------------------------------------------


class TestReincarnate:
    """reincarnate 重生/复活规格。"""

    @pytest.fixture
    def reincarnate(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "reincarnate"
        )

    def test_has_ghost_clear_postcondition(self, reincarnate: FunctionSpec) -> None:
        """有 ghost 标志清除的后置条件。"""
        assert any(
            "ghost" in post.description.lower() or "ghost" in (post.state_change or "").lower()
            for post in reincarnate.postconditions
        )

    def test_has_full_restore_invariant(self, reincarnate: FunctionSpec) -> None:
        """有完整恢复不变量（所有属性恢复到 max）。"""
        assert any(
            "max" in inv.description or "完整恢复" in inv.description
            for inv in reincarnate.invariants
        )

    def test_notes_mention_revive_difference(self, reincarnate: FunctionSpec) -> None:
        """notes 提到与 revive 的区别。"""
        assert reincarnate.notes is not None
        assert "revive" in reincarnate.notes.lower() or "苏醒" in reincarnate.notes


# ---------------------------------------------------------------------------
# revive 测试
# ---------------------------------------------------------------------------


class TestRevive:
    """revive 昏迷苏醒规格。"""

    @pytest.fixture
    def revive(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "revive"
        )

    def test_has_enable_player(self, revive: FunctionSpec) -> None:
        """有 enable_player 副作用。"""
        assert any(
            "enable_player" in (se.lpc_call or "") or "enable_player" in se.description
            for se in revive.side_effects
        )

    def test_has_block_msg_clear(self, revive: FunctionSpec) -> None:
        """有清除 block_msg 的副作用。"""
        assert any(
            "block_msg" in (se.lpc_call or "") or "block_msg" in se.description
            for se in revive.side_effects
        )

    def test_has_no_attr_restore_invariant(self, revive: FunctionSpec) -> None:
        """有不变量说明 revive 不恢复 qi/jing（需 heal_up 渐进恢复）。"""
        assert any(
            "不恢复" in inv.description or "heal_up" in inv.description
            for inv in revive.invariants
        )


# ---------------------------------------------------------------------------
# DeathState 枚举测试
# ---------------------------------------------------------------------------


class TestDeathStateEnum:
    """DeathState 枚举覆盖关键状态。"""

    def test_has_alive(self) -> None:
        assert DeathState.ALIVE == "alive"

    def test_has_unconscious(self) -> None:
        assert DeathState.UNCONSCIOUS == "unconscious"

    def test_has_dying(self) -> None:
        assert DeathState.DYING == "dying"

    def test_has_dead(self) -> None:
        assert DeathState.DEAD == "dead"

    def test_has_ghost(self) -> None:
        assert DeathState.GHOST == "ghost"

    def test_count(self) -> None:
        assert len(list(DeathState)) == 5


# ---------------------------------------------------------------------------
# announce 测试
# ---------------------------------------------------------------------------


class TestAnnounce:
    """announce 死亡/昏迷/苏醒事件消息广播。"""

    @pytest.fixture
    def announce(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "announce"
        )

    def test_only_message_output(self, announce: FunctionSpec) -> None:
        """announce 仅输出消息，所有副作用均为 MESSAGE_OUTPUT。"""
        for se in announce.side_effects:
            assert se.kind == SideEffectType.MESSAGE_OUTPUT

    def test_has_no_mutation_invariant(self, announce: FunctionSpec) -> None:
        """有不变量说明 announce 不修改状态。"""
        assert any(
            "不修改" in inv.description or "纯消息" in inv.description
            for inv in announce.invariants
        )


# ---------------------------------------------------------------------------
# heal_up 测试
# ---------------------------------------------------------------------------


class TestHealUp:
    """heal_up 恢复系统规格。"""

    @pytest.fixture
    def heal_up(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "heal_up"
        )

    def test_no_random_specs(self, heal_up: FunctionSpec) -> None:
        """heal_up 无随机性规格（完全确定性）。"""
        assert len(heal_up.random_specs) == 0

    def test_has_combate_rate_invariant(self, heal_up: FunctionSpec) -> None:
        """有战斗状态影响恢复速率的不变量。"""
        assert any(
            "战斗" in inv.description and "恢复" in inv.description
            for inv in heal_up.invariants
        )

    def test_has_cap_invariant(self, heal_up: FunctionSpec) -> None:
        """有属性上限不变量（jing<=eff_jing<=max_jing）。"""
        assert any(
            "eff_jing" in (inv.lpc_expr or "") or "上限" in inv.description
            for inv in heal_up.invariants
        )
