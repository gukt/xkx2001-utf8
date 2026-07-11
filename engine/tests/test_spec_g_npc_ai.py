"""层 G：NPC AI -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="G"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增
- heart_beat 七步管线副作用覆盖
- auto_fight 三触发条件都在规格中
- chat 自动恢复 + 随机对话副作用交织
- hypothesis 属性测试（路径 A）：4 类属性验证规格模型自身一致性
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_g_npc_ai import (
    LAYER_SPEC,
    AutoFightTrigger,
    HeartBeatStep,
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
        assert LAYER_SPEC.layer_id == "G"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "NPC AI"

    def test_lpc_files(self) -> None:
        assert "inherit/char/char.c" in LAYER_SPEC.lpc_files
        assert "inherit/char/npc.c" in LAYER_SPEC.lpc_files
        assert "feature/attack.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/combatd.c" in LAYER_SPEC.lpc_files

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 12 个 FunctionSpec。"""
        assert len(LAYER_SPEC.function_specs) == 12

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# 结构属性测试
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性。

    签名 name/return_type/lpc_file 非空已由 hypothesis 属性
    test_function_spec_by_index_valid 覆盖，此处仅保留层 G 特有的固定断言。
    """

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            "heart_beat",
            "setup",
            "chat",
            "random_move",
            "return_home",
            "init",
            "auto_fight",
            "start_hatred",
            "start_vendetta",
            "start_aggressive",
            "select_opponent",
            "clean_up_enemy",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"


# ---------------------------------------------------------------------------
# heart_beat 七步管线测试
# ---------------------------------------------------------------------------


class TestHeartBeat:
    """heart_beat 七步管线的规格覆盖。"""

    @pytest.fixture
    def heart_beat(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "heart_beat"
        )

    def test_has_many_side_effects(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 有大量副作用（至少 10 个，覆盖七步管线）。"""
        assert len(heart_beat.side_effects) >= 10

    def test_has_state_mutation(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 副作用包含 STATE_MUTATION。"""
        assert any(
            se.kind == SideEffectType.STATE_MUTATION
            for se in heart_beat.side_effects
        )

    def test_has_message_output(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 副作用包含 MESSAGE_OUTPUT（频道刷屏消息）。"""
        assert any(
            se.kind == SideEffectType.MESSAGE_OUTPUT
            for se in heart_beat.side_effects
        )

    def test_has_object_lifecycle(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 副作用包含 OBJECT_LIFECYCLE（chat 可能 destruct）。"""
        assert any(
            se.kind == SideEffectType.OBJECT_LIFECYCLE
            for se in heart_beat.side_effects
        )

    def test_has_call_out_or_external(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 副作用包含 EXTERNAL（chat/attack/update_condition 等外部调用）。"""
        assert any(
            se.kind == SideEffectType.EXTERNAL
            for se in heart_beat.side_effects
        )

    def test_has_random_spec(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 有随机性规格（tick = 5+random(10)）。"""
        assert len(heart_beat.random_specs) >= 1
        rs = heart_beat.random_specs[0]
        assert "random(10)" in rs.lpc_call or "random" in rs.lpc_call

    def test_has_tick_invariant(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 有 tick=1s + 非均匀 tick 不变量。"""
        assert any(
            "tick" in inv.description.lower() or "1s" in inv.description
            for inv in heart_beat.invariants
        )

    def test_has_seven_step_invariant(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 有七步顺序不可重排的不变量。"""
        assert any(
            "七步" in inv.description or "顺序不可重排" in inv.description
            for inv in heart_beat.invariants
        )

    def test_has_destruct_check_invariant(self, heart_beat: FunctionSpec) -> None:
        """heart_beat 有 chat() 后检查 this_object() 存在性的不变量。"""
        assert any(
            "destruct" in inv.description and "this_object" in inv.description
            for inv in heart_beat.invariants
        )

    def test_notes_mention_seven_steps(self, heart_beat: FunctionSpec) -> None:
        """notes 中提到七步管线。"""
        assert heart_beat.notes is not None
        assert "七步" in heart_beat.notes

    def test_heart_beat_step_enum(self) -> None:
        """HeartBeatStep 枚举有 7 个步骤。"""
        steps = list(HeartBeatStep)
        assert len(steps) == 7
        assert HeartBeatStep.CHANNEL_CLEANUP == "channel_cleanup"
        assert HeartBeatStep.ATTRIBUTE_CAP == "attribute_cap"
        assert HeartBeatStep.MORTAL_WOUND_CHECK == "mortal_wound_check"
        assert HeartBeatStep.UNCONSCIOUS_CHECK == "unconscious_check"
        assert HeartBeatStep.COMBAT_ACTION == "combat_action"
        assert HeartBeatStep.NPC_CHAT == "npc_chat"
        assert HeartBeatStep.TICK_DECAY == "tick_decay"


# ---------------------------------------------------------------------------
# auto_fight 三触发测试
# ---------------------------------------------------------------------------


class TestAutoFightTriggers:
    """auto_fight 三触发条件的规格覆盖。"""

    @pytest.fixture
    def init_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "init"
        )

    @pytest.fixture
    def auto_fight(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "auto_fight"
        )

    def test_auto_fight_trigger_enum(self) -> None:
        """AutoFightTrigger 枚举有三触发。"""
        triggers = list(AutoFightTrigger)
        assert len(triggers) == 3
        assert AutoFightTrigger.HATRED == "hatred"
        assert AutoFightTrigger.VENDETTA == "vendetta"
        assert AutoFightTrigger.AGGRESSIVE == "aggressive"

    def test_init_has_three_triggers(self, init_spec: FunctionSpec) -> None:
        """init 的副作用覆盖三触发。"""
        descriptions = " ".join(se.description for se in init_spec.side_effects)
        assert "hatred" in descriptions.lower()
        assert "vendetta" in descriptions.lower()
        assert "aggressive" in descriptions.lower()

    def test_init_has_priority_invariant(self, init_spec: FunctionSpec) -> None:
        """init 有三触发优先级不变量（hatred > vendetta > aggressive）。"""
        assert any(
            "hatred" in inv.description and "vendetta" in inv.description
            and "aggressive" in inv.description
            for inv in init_spec.invariants
        )

    def test_init_has_guard_precondition(self, init_spec: FunctionSpec) -> None:
        """init 有前置守卫（is_fighting/living/同房间等）。"""
        assert any(
            "is_fighting" in (pre.lpc_expr or "") or "living" in (pre.lpc_expr or "")
            for pre in init_spec.preconditions
        )

    def test_auto_fight_has_call_out(self, auto_fight: FunctionSpec) -> None:
        """auto_fight 通过 call_out 延迟执行 start_<type>。"""
        assert any(
            se.kind == SideEffectType.CALL_OUT
            or "call_out" in (se.lpc_call or "")
            for se in auto_fight.side_effects
        )

    def test_auto_fight_has_npc_guard(self, auto_fight: FunctionSpec) -> None:
        """auto_fight 有 NPC 不攻击 NPC 的守卫不变量。"""
        assert any(
            "NPC" in inv.description and "NPC" in inv.description
            for inv in auto_fight.invariants
        )

    def test_auto_fight_has_looking_for_trouble(self, auto_fight: FunctionSpec) -> None:
        """auto_fight 有 looking_for_trouble 防重入不变量。"""
        assert any(
            "looking_for_trouble" in inv.description
            or "looking_for_trouble" in (inv.lpc_expr or "")
            for inv in auto_fight.invariants
        )

    def test_start_hatred_has_kill_ob(self) -> None:
        """start_hatred 调用 kill_ob 启动杀戮。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "start_hatred"
        )
        assert any(
            "kill_ob" in (se.lpc_call or "")
            for se in spec.side_effects
        )

    def test_start_vendetta_has_kill_ob(self) -> None:
        """start_vendetta 调用 kill_ob 启动杀戮。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "start_vendetta"
        )
        assert any(
            "kill_ob" in (se.lpc_call or "")
            for se in spec.side_effects
        )

    def test_start_aggressive_has_kill_ob(self) -> None:
        """start_aggressive 调用 kill_ob 启动杀戮。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "start_aggressive"
        )
        assert any(
            "kill_ob" in (se.lpc_call or "")
            for se in spec.side_effects
        )

    def test_start_hatred_has_random_message(self) -> None:
        """start_hatred 有随机追猎消息。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "start_hatred"
        )
        assert len(spec.random_specs) >= 1
        assert any("catch_hunt" in rs.lpc_call for rs in spec.random_specs)

    def test_start_vendetta_no_random_message(self) -> None:
        """start_vendetta 无随机追猎消息。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "start_vendetta"
        )
        assert len(spec.random_specs) == 0

    def test_start_aggressive_no_random_message(self) -> None:
        """start_aggressive 无随机追猎消息。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "start_aggressive"
        )
        assert len(spec.random_specs) == 0

    def test_all_starts_have_four_guard_invariant(self) -> None:
        """所有 start_<type> 都有四重守卫不变量。"""
        for name in ("start_hatred", "start_vendetta", "start_aggressive"):
            spec = next(
                s for s in LAYER_SPEC.function_specs if s.signature.name == name
            )
            assert any(
                "is_fighting" in (inv.lpc_expr or "")
                and "living" in (inv.lpc_expr or "")
                and "no_fight" in (inv.lpc_expr or "")
                for inv in spec.invariants
            ), f"{name} 缺少四重守卫不变量"


# ---------------------------------------------------------------------------
# chat() 测试
# ---------------------------------------------------------------------------


class TestChat:
    """chat() 自动恢复 + 随机对话的规格覆盖。"""

    @pytest.fixture
    def chat(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "chat"
        )

    def test_has_auto_heal_side_effects(self, chat: FunctionSpec) -> None:
        """chat 有自动恢复副作用（exert_function）。"""
        descriptions = " ".join(se.description for se in chat.side_effects)
        assert "refresh" in descriptions
        assert "recover" in descriptions
        assert "regenerate" in descriptions

    def test_has_random_dialogue(self, chat: FunctionSpec) -> None:
        """chat 有随机对话（random(100) < chance + random(sizeof(msg))）。"""
        assert len(chat.random_specs) >= 2
        assert any("random(100)" in rs.lpc_call for rs in chat.random_specs)
        assert any("random(sizeof" in rs.lpc_call for rs in chat.random_specs)

    def test_has_combat_vs_noncombat_invariant(self, chat: FunctionSpec) -> None:
        """chat 有战斗/非战斗状态使用不同 chat_chance 的不变量。"""
        assert any(
            "chat_chance_combat" in (inv.lpc_expr or "")
            or "chat_chance_combat" in inv.description
            for inv in chat.invariants
        )

    def test_has_destruct_invariant(self, chat: FunctionSpec) -> None:
        """chat 有可能 destruct 的不变量说明。"""
        assert any(
            "destruct" in inv.description
            for inv in chat.invariants
        )

    def test_heal_before_dialogue(self, chat: FunctionSpec) -> None:
        """自动恢复优先于随机对话（副作用 order 前后关系）。"""
        heal_effects = [
            se for se in chat.side_effects
            if "exert_function" in (se.lpc_call or "")
        ]
        dialogue_effects = [
            se for se in chat.side_effects
            if "random(100)" in (se.lpc_call or "") or "say" in (se.lpc_call or "")
        ]
        if heal_effects and dialogue_effects:
            assert min(se.order for se in heal_effects) < max(
                se.order for se in dialogue_effects
            )


# ---------------------------------------------------------------------------
# random_move() 测试
# ---------------------------------------------------------------------------


class TestRandomMove:
    """random_move() 随机移动的规格覆盖。"""

    @pytest.fixture
    def random_move(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "random_move"
        )

    def test_has_jingli_precondition(self, random_move: FunctionSpec) -> None:
        """random_move 有精力 >= max_jingli/2 的前置条件。"""
        assert any(
            "jingli" in pre.description and "max_jingli" in pre.description
            for pre in random_move.preconditions
        )

    def test_has_random_direction(self, random_move: FunctionSpec) -> None:
        """random_move 有随机选择方向的随机性规格。"""
        assert len(random_move.random_specs) >= 1
        assert any("random(sizeof" in rs.lpc_call for rs in random_move.random_specs)

    def test_delegates_to_go_command(self, random_move: FunctionSpec) -> None:
        """random_move 委托 command('go '+dir) 执行移动。"""
        assert any(
            "command" in (se.lpc_call or "") and "go" in (se.lpc_call or "")
            for se in random_move.side_effects
        )

    def test_has_door_open_side_effect(self, random_move: FunctionSpec) -> None:
        """random_move 有关门时自动开门的副作用。"""
        assert any(
            "open" in se.description and "门" in se.description
            for se in random_move.side_effects
        )


# ---------------------------------------------------------------------------
# select_opponent() 测试
# ---------------------------------------------------------------------------


class TestSelectOpponent:
    """select_opponent() 选择攻击目标的规格覆盖。"""

    @pytest.fixture
    def select_opponent(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "select_opponent"
        )

    def test_has_random_spec(self, select_opponent: FunctionSpec) -> None:
        """select_opponent 有随机性规格（random(MAX_OPPONENT)）。"""
        assert len(select_opponent.random_specs) >= 1
        assert any("MAX_OPPONENT" in rs.lpc_call for rs in select_opponent.random_specs)

    def test_has_max_opponent_invariant(self, select_opponent: FunctionSpec) -> None:
        """select_opponent 有 MAX_OPPONENT(4) 限制不变量。"""
        assert any(
            "MAX_OPPONENT" in (inv.lpc_expr or "") or "MAX_OPPONENT" in inv.description
            for inv in select_opponent.invariants
        )


# ---------------------------------------------------------------------------
# clean_up_enemy() 测试
# ---------------------------------------------------------------------------


class TestCleanUpEnemy:
    """clean_up_enemy() 敌人清理的规格覆盖。"""

    @pytest.fixture
    def clean_up_enemy(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs
            if s.signature.name == "clean_up_enemy"
        )

    def test_has_killing_invariant(self, clean_up_enemy: FunctionSpec) -> None:
        """clean_up_enemy 有 killing 关系敌人不清除的不变量。"""
        assert any(
            "killing" in inv.description.lower()
            for inv in clean_up_enemy.invariants
        )

    def test_has_clear_condition_invariant(self, clean_up_enemy: FunctionSpec) -> None:
        """clean_up_enemy 有清除条件不变量。"""
        assert any(
            "objectp" in (inv.lpc_expr or "") or "environment" in (inv.lpc_expr or "")
            for inv in clean_up_enemy.invariants
        )


# ---------------------------------------------------------------------------
# setup() 测试
# ---------------------------------------------------------------------------


class TestSetup:
    """setup() 初始化的规格覆盖。"""

    @pytest.fixture
    def setup(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "setup"
        )

    def test_has_heart_beat_invariant(self, setup: FunctionSpec) -> None:
        """setup 有 set_heart_beat(1) 不变量。"""
        assert any(
            "set_heart_beat(1)" in (inv.lpc_expr or "")
            or "set_heart_beat(1)" in inv.description
            for inv in setup.invariants
        )

    def test_has_heart_beat_side_effect(self, setup: FunctionSpec) -> None:
        """setup 有 set_heart_beat(1) 副作用。"""
        assert any(
            "set_heart_beat" in (se.lpc_call or "")
            for se in setup.side_effects
        )

    def test_has_random_tick(self, setup: FunctionSpec) -> None:
        """setup 有 tick 随机性规格。"""
        assert len(setup.random_specs) >= 1
        assert any("random(10)" in rs.lpc_call for rs in setup.random_specs)


# ---------------------------------------------------------------------------
# 层级规格测试
# ---------------------------------------------------------------------------


class TestLayerNotes:
    """层规格的 notes 覆盖关键信息。"""

    def test_notes_mention_seven_steps(self) -> None:
        """notes 中提到七步管线。"""
        assert LAYER_SPEC.notes is not None
        assert "七步" in LAYER_SPEC.notes

    def test_notes_mention_three_triggers(self) -> None:
        """notes 中提到三触发。"""
        assert LAYER_SPEC.notes is not None
        assert "hatred" in LAYER_SPEC.notes
        assert "vendetta" in LAYER_SPEC.notes
        assert "aggressive" in LAYER_SPEC.notes

    def test_notes_mention_audit(self) -> None:
        """notes 中提到派生变更审计。"""
        assert LAYER_SPEC.notes is not None
        assert "审计" in LAYER_SPEC.notes or "dissent" in LAYER_SPEC.notes.lower()

    def test_cross_layer_refs_include_combat(self) -> None:
        """跨层引用包含层 E combat。"""
        refs = " ".join(LAYER_SPEC.cross_layer_refs)
        assert "层 E" in refs or "combat" in refs.lower()


# ---------------------------------------------------------------------------
# hypothesis 属性测试（路径 A）
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。
# ---------------------------------------------------------------------------

_N = len(LAYER_SPEC.function_specs) - 1


# ── 第 1 类：随机函数索引 ──────────────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性：任意索引的 FunctionSpec 签名 name/return_type/lpc_file 非空。"""
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


# ── 第 2 类：副作用子集 ────────────────────────────────────────────────────


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


# ── 第 3 类：random_specs 完整性 ───────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_fields_nonempty(idx: int) -> None:
    """属性：任意有 random_specs 的函数，每个 random_spec 的
    probability_model/semantic/lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.lpc_call, (
            f"{spec.signature.name}: random_spec.lpc_call 为空"
        )
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec.probability_model 为空"
        )
        assert rs.semantic, (
            f"{spec.signature.name}: random_spec.semantic 为空"
        )


# ── 第 4 类：invariants-side_effects 对应 ─────────────────────────────────


_STATE_KW_RE = re.compile(
    r"\b(qi|state|状态|eff_|max_qi|max_jing|max_jingli|max_neili|jing|neili)\b",
    re.IGNORECASE,
)


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态（qi/state/状态/eff_/max_qi 等/jing/neili）的函数，
    副作用含 STATE_MUTATION。"""
    spec = LAYER_SPEC.function_specs[idx]
    has_state_invariant = any(
        _STATE_KW_RE.search(inv.description) or _STATE_KW_RE.search(inv.lpc_expr or "")
        for inv in spec.invariants
    )
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
