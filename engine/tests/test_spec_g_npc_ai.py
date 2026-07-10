"""层 G：NPC AI -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="G"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增
- heart_beat 七步管线副作用覆盖
- auto_fight 三触发条件都在规格中
- chat 自动恢复 + 随机对话副作用交织
"""

from __future__ import annotations

import pytest

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
            if not spec.side_effects:
                continue
            orders = sorted(se.order for se in spec.side_effects)
            assert orders[0] == 1, (
                f"order 应从 1 开始: {spec.signature.name} first={orders[0]}"
            )

    def test_order_consecutive(self, all_specs: list[FunctionSpec]) -> None:
        """order 应连续递增（1, 2, 3, ... 无跳号）。"""
        for spec in all_specs:
            if not spec.side_effects:
                continue
            orders = sorted(se.order for se in spec.side_effects)
            expected = list(range(1, len(orders) + 1))
            assert orders == expected, (
                f"order 不连续: {spec.signature.name} orders={orders}"
            )


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
