"""层 E：战斗系统 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="E"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增（连续）
- do_attack 七步副作用交织验证（state_mutation 与 message_output 交替）
- random_specs 数量验证（>= 20）
- 三层资源不变量验证
- cross_layer_refs 非空
"""

from __future__ import annotations

import pytest

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_e_combat import (
    LAYER_SPEC,
    AttackType,
    CombatStep,
    ResourceType,
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
        assert LAYER_SPEC.layer_id == "E"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "战斗系统"

    def test_lpc_files(self) -> None:
        assert "adm/daemons/combatd.c" in LAYER_SPEC.lpc_files
        assert "feature/attack.c" in LAYER_SPEC.lpc_files
        assert "feature/damage.c" in LAYER_SPEC.lpc_files
        assert "feature/skill.c" in LAYER_SPEC.lpc_files
        assert "feature/condition.c" in LAYER_SPEC.lpc_files

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 26 个 FunctionSpec。"""
        assert len(LAYER_SPEC.function_specs) == 26

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0

    def test_layer_notes_mentions_combat_determinism(self) -> None:
        """LAYER_SPEC.notes 提到 combat 确定性范围。"""
        assert LAYER_SPEC.notes is not None
        assert "combat" in LAYER_SPEC.notes.lower()
        assert "确定性" in LAYER_SPEC.notes


# ---------------------------------------------------------------------------
# 枚举测试
# ---------------------------------------------------------------------------


class TestEnums:
    """层 E 特定枚举完整性。"""

    def test_combat_step_has_seven_steps(self) -> None:
        """CombatStep 枚举应有 8 个值（0-6 + post_action）。"""
        steps = list(CombatStep)
        assert len(steps) == 8

    def test_combat_step_select_skill(self) -> None:
        assert CombatStep.SELECT_SKILL == "select_skill"

    def test_combat_step_damage_settle(self) -> None:
        assert CombatStep.DAMAGE_SETTLE == "damage_settle"

    def test_resource_type_has_four(self) -> None:
        assert len(list(ResourceType)) == 4
        assert ResourceType.QI == "qi"
        assert ResourceType.JING == "jing"
        assert ResourceType.JINGLI == "jingli"
        assert ResourceType.NEILI == "neili"

    def test_attack_type_constants(self) -> None:
        assert AttackType.REGULAR == "0"
        assert AttackType.RIPOSTE == "1"
        assert AttackType.QUICK == "2"


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
            "skill_power",
            "do_attack",
            "damage_msg",
            "eff_status_msg",
            "report_status",
            "fight",
            "auto_fight",
            "death_penalty",
            "fight_ob",
            "kill_ob",
            "select_opponent",
            "attack",
            "reset_action",
            "receive_damage",
            "receive_wound",
            "receive_heal",
            "receive_curing",
            "die",
            "unconcious",
            "apply_condition",
            "update_condition",
            "clear_condition",
            "query_skill",
            "improve_skill",
            "skill_death_penalty",
            "heal_up",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"


# ---------------------------------------------------------------------------
# 副作用 order 测试
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 唯一且连续递增。"""

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
# do_attack 七步副作用交织测试（核心）
# ---------------------------------------------------------------------------


class TestDoAttackInterleaving:
    """do_attack 七步副作用交织是核心契约。

    验证 state_mutation 与 message_output 严格交替（非全 state 后全 message）。
    这是 dissent 3/01 子系统 5 的核心关注点。
    """

    @pytest.fixture
    def do_attack(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_attack"
        )

    def test_do_attack_has_many_side_effects(self, do_attack: FunctionSpec) -> None:
        """do_attack 有大量副作用（至少 30 个）。"""
        assert len(do_attack.side_effects) >= 30

    def test_do_attack_has_state_and_message_interleaved(
        self, do_attack: FunctionSpec
    ) -> None:
        """state_mutation 与 message_output 必须交织（非全 state 后全 message）。"""
        kinds = [se.kind for se in do_attack.side_effects]
        state_indices = [
            i for i, k in enumerate(kinds) if k == SideEffectType.STATE_MUTATION
        ]
        msg_indices = [
            i for i, k in enumerate(kinds) if k == SideEffectType.MESSAGE_OUTPUT
        ]
        assert len(state_indices) > 0, "do_attack 应有 state_mutation 副作用"
        assert len(msg_indices) > 0, "do_attack 应有 message_output 副作用"

        # 验证交织：message 出现在 state 之间，而非全部在 state 之后
        first_msg = msg_indices[0]
        last_state = state_indices[-1]
        assert first_msg < last_state, (
            "message_output 应出现在 state_mutation 之间（交织），"
            f"但第一个 message 在 index {first_msg}，最后一个 state 在 index {last_state}"
        )

    def test_do_attack_select_skill_before_damage(self, do_attack: FunctionSpec) -> None:
        """步骤 0 选技能必须在步骤 5 伤害结算之前。"""
        select_skill = next(
            se for se in do_attack.side_effects if "步骤0" in se.description
        )
        damage_settle = next(
            se for se in do_attack.side_effects
            if "步骤5" in se.description and "伤害结算" in se.description
        )
        assert select_skill.order < damage_settle.order

    def test_do_attack_dodge_before_parry(self, do_attack: FunctionSpec) -> None:
        """步骤 3 闪避判定必须在步骤 4 招架判定之前。"""
        dodge = next(
            se for se in do_attack.side_effects
            if "步骤3" in se.description and "闪避" in se.description
        )
        parry = next(
            se for se in do_attack.side_effects
            if "步骤4" in se.description and "招架" in se.description
        )
        assert dodge.order < parry.order

    def test_do_attack_parry_before_damage(self, do_attack: FunctionSpec) -> None:
        """步骤 4 招架判定必须在步骤 5 伤害结算之前。"""
        parry = next(
            se for se in do_attack.side_effects if "步骤4" in se.description
        )
        damage = next(
            se for se in do_attack.side_effects if "步骤5" in se.description
        )
        assert parry.order < damage.order

    def test_do_attack_damage_before_exp(self, do_attack: FunctionSpec) -> None:
        """步骤 6 经验获得必须在步骤 5 伤害结算之后。"""
        damage = next(
            se
            for se in do_attack.side_effects
            if "步骤5" in se.description and "伤害结算" in se.description
        )
        exp = next(
            se for se in do_attack.side_effects if "步骤7" in se.description
        )
        assert damage.order < exp.order

    def test_do_attack_receive_damage_before_damage_msg(
        self, do_attack: FunctionSpec
    ) -> None:
        """receive_damage 调用必须在 damage_msg 文本生成之前（状态先变再描述）。"""
        recv_dmg = next(
            se for se in do_attack.side_effects if "receive_damage" in (se.lpc_call or "")
        )
        dmg_msg = next(
            se for se in do_attack.side_effects if "damage_msg" in (se.lpc_call or "")
        )
        assert recv_dmg.order < dmg_msg.order

    def test_do_attack_damage_msg_before_message_vision(
        self, do_attack: FunctionSpec
    ) -> None:
        """damage_msg 文本生成在 message_vision 最终输出之前。"""
        dmg_msg = next(
            se
            for se in do_attack.side_effects
            if se.kind == SideEffectType.MESSAGE_OUTPUT and "damage_msg" in (se.lpc_call or "")
        )
        vision = next(
            se
            for se in do_attack.side_effects
            if "message_vision(result" in (se.lpc_call or "")
        )
        assert dmg_msg.order < vision.order

    def test_do_attack_has_call_out_for_riposte(self, do_attack: FunctionSpec) -> None:
        """do_attack 有 riposte 相关副作用（触发点记录，递归后置）。"""
        riposte_ses = [
            se for se in do_attack.side_effects if "riposte" in se.description.lower()
        ]
        assert len(riposte_ses) >= 2

    def test_do_attack_has_invariants(self, do_attack: FunctionSpec) -> None:
        """do_attack 有不变量（三层资源 + 七步交织 + ap/dp/pp 下限 + QUICK 减半）。"""
        assert len(do_attack.invariants) >= 4

    def test_do_attack_has_three_resource_invariant(
        self, do_attack: FunctionSpec
    ) -> None:
        """do_attack 不变量中包含三层资源不变量。"""
        assert any(
            "qi" in inv.description and "eff_qi" in inv.description and "max_qi" in inv.description
            for inv in do_attack.invariants
        )


# ---------------------------------------------------------------------------
# 随机性规格测试
# ---------------------------------------------------------------------------


class TestRandomSpecs:
    """29 处 random() 提取为 RandomSpec 的完整性验证。"""

    def test_total_random_specs_count(self) -> None:
        """所有函数的 RandomSpec 总数应 >= 20（29 处可能合并相近的）。"""
        total = sum(len(spec.random_specs) for spec in LAYER_SPEC.function_specs)
        assert total >= 20, f"RandomSpec 总数 {total} 少于 20"

    def test_do_attack_random_specs_count(self) -> None:
        """do_attack 应有大量 RandomSpec（>= 20）。"""
        do_attack = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_attack"
        )
        assert len(do_attack.random_specs) >= 20, (
            f"do_attack RandomSpec 数量 {len(do_attack.random_specs)} 少于 20"
        )

    def test_dodge_random_has_probability_model(self) -> None:
        """闪避判定 RandomSpec 有概率模型 dp/(ap+dp)。"""
        do_attack = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_attack"
        )
        dodge_rs = next(
            rs for rs in do_attack.random_specs if "闪避" in rs.semantic
        )
        assert "dp" in dodge_rs.probability_model.lower()
        assert "ap" in dodge_rs.probability_model.lower()

    def test_parry_random_has_probability_model(self) -> None:
        """招架判定 RandomSpec 有概率模型 pp/(ap+pp)。"""
        do_attack = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_attack"
        )
        parry_rs = next(
            rs for rs in do_attack.random_specs if "招架" in rs.semantic and "判定" in rs.semantic
        )
        assert "pp" in parry_rs.probability_model.lower()

    def test_select_opponent_has_random(self) -> None:
        """select_opponent 有 random(MAX_OPPONENT)。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "select_opponent"
        )
        assert len(spec.random_specs) >= 1
        assert "MAX_OPPONENT" in spec.random_specs[0].lpc_call

    def test_fight_has_random(self) -> None:
        """fight 有主动性判定随机性。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "fight"
        )
        assert len(spec.random_specs) >= 1

    def test_unconcious_has_random(self) -> None:
        """unconcious 有昏迷时间随机性。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "unconcious"
        )
        assert len(spec.random_specs) >= 1
        assert "con" in spec.random_specs[0].lpc_call

    def test_all_random_specs_have_semantic(self) -> None:
        """每个 RandomSpec 都有语义描述。"""
        for spec in LAYER_SPEC.function_specs:
            for rs in spec.random_specs:
                assert rs.semantic, (
                    f"{spec.signature.name} 的 RandomSpec 缺少 semantic"
                )

    def test_all_random_specs_have_probability_model(self) -> None:
        """每个 RandomSpec 都有概率模型。"""
        for spec in LAYER_SPEC.function_specs:
            for rs in spec.random_specs:
                assert rs.probability_model, (
                    f"{spec.signature.name} 的 RandomSpec 缺少 probability_model"
                )


# ---------------------------------------------------------------------------
# 三层资源不变量测试
# ---------------------------------------------------------------------------


class TestThreeLayerResourceInvariant:
    """三层资源不变量 0 <= qi <= eff_qi <= max_qi 是核心契约。"""

    def test_do_attack_has_resource_invariant(self) -> None:
        """do_attack 不变量包含三层资源。"""
        do_attack = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "do_attack"
        )
        assert any(
            "qi" in inv.description and "eff_qi" in inv.description
            for inv in do_attack.invariants
        )

    def test_receive_damage_has_resource_invariant(self) -> None:
        """receive_damage 不变量包含三层资源。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_damage"
        )
        assert any(
            "qi" in inv.description and "eff_qi" in inv.description
            for inv in spec.invariants
        )

    def test_receive_wound_has_resource_invariant(self) -> None:
        """receive_wound 不变量包含 qi <= eff_qi。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_wound"
        )
        assert any(
            "eff" in inv.description or "eff" in (inv.lpc_expr or "")
            for inv in spec.invariants
        )

    def test_receive_heal_has_eff_limit(self) -> None:
        """receive_heal 不变量包含 eff 层上限。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_heal"
        )
        assert any(
            "eff" in inv.description or "eff" in (inv.lpc_expr or "")
            for inv in spec.invariants
        )

    def test_receive_curing_has_max_limit(self) -> None:
        """receive_curing 不变量包含 max 层上限。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_curing"
        )
        assert any(
            "max" in inv.description or "max" in (inv.lpc_expr or "")
            for inv in spec.invariants
        )

    def test_heal_up_has_resource_invariant(self) -> None:
        """heal_up 不变量包含三层资源。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "heal_up"
        )
        assert any(
            "eff_qi" in inv.description or "eff_qi" in (inv.lpc_expr or "")
            for inv in spec.invariants
        )


# ---------------------------------------------------------------------------
# receive_damage / receive_wound 契约测试
# ---------------------------------------------------------------------------


class TestReceiveDamageContract:
    """receive_damage / receive_wound 契约验证。"""

    def test_receive_damage_validates_type(self) -> None:
        """receive_damage 前置条件验证 type 只能是 qi/jing/jingli。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_damage"
        )
        assert any(
            "jing" in pre.description and "qi" in pre.description and "jingli" in pre.description
            for pre in spec.preconditions
        )

    def test_receive_wound_validates_type(self) -> None:
        """receive_wound 前置条件验证 type 只能是 qi/jing（不含 jingli）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_wound"
        )
        type_pre = next(
            pre for pre in spec.preconditions
            if "type" in pre.description.lower()
            or "type" in (pre.lpc_expr or "").lower()
        )
        assert "jingli" not in (type_pre.lpc_expr or "") or "不含" in type_pre.description

    def test_receive_damage_records_last_damage_from(self) -> None:
        """receive_damage 记录 last_damage_from。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_damage"
        )
        assert any(
            "last_damage_from" in se.description or "last_damage_from" in (se.lpc_call or "")
            for se in spec.side_effects
        )

    def test_receive_wound_syncs_qi_to_eff(self) -> None:
        """receive_wound 同步 qi 到 eff 值（保持 qi <= eff_qi 不变量）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "receive_wound"
        )
        assert any(
            "同步" in se.description or "不超过" in se.description
            for se in spec.side_effects
        )


# ---------------------------------------------------------------------------
# condition 框架测试
# ---------------------------------------------------------------------------


class TestConditionFramework:
    """condition 框架 apply/update/clear 接口验证。"""

    def test_apply_condition_overwrites(self) -> None:
        """apply_condition 覆盖旧值（不检查重复）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "apply_condition"
        )
        assert any(
            "覆盖" in inv.description or "不检查" in inv.description
            for inv in spec.invariants
        )

    def test_update_condition_removes_expired(self) -> None:
        """update_condition 移除过期 condition（daemon 返回 0 时）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "update_condition"
        )
        assert any(
            "移除" in inv.description or "map_delete" in (inv.lpc_expr or "")
            for inv in spec.invariants
        )

    def test_clear_condition_nulls_mapping(self) -> None:
        """clear_condition 将 conditions 置为 0。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "clear_condition"
        )
        assert any(
            "0" in (se.lpc_call or "") or "NULL" in se.description
            for se in spec.side_effects
        )


# ---------------------------------------------------------------------------
# skill_power 公式测试
# ---------------------------------------------------------------------------


class TestSkillPower:
    """skill_power AP/DP 计算公式验证。"""

    @pytest.fixture
    def skill_power_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "skill_power"
        )

    def test_has_cube_formula_invariant(self, skill_power_spec: FunctionSpec) -> None:
        """skill_power 不变量包含 level^3/3 公式。"""
        assert any(
            "level" in inv.lpc_expr and "3" in inv.lpc_expr
            for inv in skill_power_spec.invariants
        )

    def test_has_jingli_bonus_invariant(self, skill_power_spec: FunctionSpec) -> None:
        """skill_power 不变量包含 jingli_bonus 公式。"""
        assert any(
            "jingli_bonus" in (inv.lpc_expr or "") or "jingli_bonus" in inv.description
            for inv in skill_power_spec.invariants
        )

    def test_no_random_specs(self, skill_power_spec: FunctionSpec) -> None:
        """skill_power 是纯计算函数，无随机性。"""
        assert len(skill_power_spec.random_specs) == 0
