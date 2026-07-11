"""层 F：死亡轮回 -- 规格属性测试（任务 3 路径 A）。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="F"、function_specs 非空
- 层 F 特殊契约：die vs unconcious 触发区别、death_penalty 确定性、make_corpse 物品转移
- hypothesis 属性（路径 A，4 类）：
  1. 随机函数索引：签名完整 / 副作用 order 递增+连续 / kind+description 非空 / 有 pre+post 条件
  2. 副作用子集：随机非空子集 order 仍递增
  3. random_specs 完整性：probability_model / semantic / lpc_call 非空
  4. invariants-side_effects 对应：有状态不变量 -> 副作用含 STATE_MUTATION
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
# 结构属性测试（仅保留层 F 特有检查，签名/order/kind 完整性由 hypothesis 覆盖）
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """层 F 特有结构检查。"""

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
# die 与 unconcious 规格测试（层 F 特殊契约，保留）
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
# heart_beat 死亡触发条件测试（层 F 特殊契约，保留）
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
# death_penalty 确定性测试（层 F 特殊契约，保留）
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
# killer_reward 测试（层 F 特殊契约，保留）
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
# make_corpse 测试（层 F 特殊契约，保留）
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
# reincarnate 测试（层 F 特殊契约，保留）
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
# revive 测试（层 F 特殊契约，保留）
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
# DeathState 枚举测试（层 F 特有，保留）
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
# announce 测试（层 F 特殊契约，保留）
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
# heal_up 测试（层 F 特殊契约，保留）
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


# ── hypothesis 属性测试（路径 A） ────────────────────────────────────────
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。
# 层 F 有 10 个函数、2 个 random_specs（heart_beat + unconcious）。


_N = len(LAYER_SPEC.function_specs) - 1


# ── 第 1 类：随机函数索引 ──


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
    """属性：任意函数至少有一个前置条件和一个后置条件。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.preconditions) > 0, f"{spec.signature.name}: 无前置条件"
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


# ── 第 2 类：副作用子集 ──


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


# ── 第 3 类：random_specs 完整性 ──


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_complete(idx: int) -> None:
    """属性：任意有 random_specs 的函数，每个 random_spec 的
    probability_model / semantic / lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.lpc_call, f"{spec.signature.name}: random_spec lpc_call 为空"
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec probability_model 为空"
        )
        assert rs.semantic, f"{spec.signature.name}: random_spec semantic 为空"


# ── 第 4 类：invariants-side_effects 对应 ──


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi 的函数，副作用含 STATE_MUTATION。

    排除否定语境（如 announce 的 '不修改任何状态'）——这类不变量描述的是
    约束而非状态变更契约，不应要求 STATE_MUTATION 副作用。
    """
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")
    negation_markers = ("不修改", "不涉及", "不恢复", "无 random")
    has_state_invariant = any(
        any(kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in state_keywords)
        and not any(neg in inv.description for neg in negation_markers)
        for inv in spec.invariants
    )
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
