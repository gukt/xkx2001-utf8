"""层 E：战斗系统 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="E"、function_specs 非空
- 枚举完整性：CombatStep / ResourceType / AttackType
- do_attack 七步副作用交织验证（state_mutation 与 message_output 交替）
- 三层资源不变量验证
- receive_damage/wound 契约
- condition 框架
- skill_power 公式
- 26 函数名完整性
- cross_layer_refs 非空
- hypothesis 属性测试（路径 A）：随机函数索引 / 副作用子集 /
  random_specs 完整性 / invariants-side_effects 对应
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
# 26 函数名完整性
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """26 函数名完整性（签名完整性由 hypothesis 属性测试覆盖）。"""

    def test_expected_function_names(self) -> None:
        all_specs = LAYER_SPEC.function_specs
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
    """31 处 random() 提取为 RandomSpec 的特定验证。

    通用完整性（semantic/probability_model 非空）由 hypothesis 属性测试覆盖。
    """

    def test_total_random_specs_count(self) -> None:
        """所有函数的 RandomSpec 总数应 >= 20。"""
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


# ---------------------------------------------------------------------------
# hypothesis 属性测试（路径 A）
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。
# 层 E 特点：26 函数、31 random_specs（最多）、do_attack 49 副作用严格交织。
#


_N = len(LAYER_SPEC.function_specs) - 1


# ── 第 1 类：随机函数索引 ──────────────────────────────────────────────────


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


# ── 第 3 类：random_specs 完整性 ──────────────────────────────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_fields_nonempty(idx: int) -> None:
    """属性：任意有 random_specs 的函数，每个 random_spec 的
    probability_model/semantic/lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec '{rs.lpc_call}' 缺少 probability_model"
        )
        assert rs.semantic, (
            f"{spec.signature.name}: random_spec '{rs.lpc_call}' 缺少 semantic"
        )
        assert rs.lpc_call, (
            f"{spec.signature.name}: random_spec 缺少 lpc_call"
        )


# ── 第 4 类：invariants-side_effects 对应（层 E 最关键） ──────────────────


@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi/state/状态/eff_/max_/jing/neili 的函数 -> 副作用含 STATE_MUTATION。

    层 E 最关键：do_attack 七步 state+message 交织是 dissent 3/01 子系统 5 核心关注点。
    排除纯查询不变量（lpc_expr 仅含 query() 无 set()），如 report_status 只读计算 ratio。
    """
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")

    def _is_state_mutation_invariant(inv: object) -> bool:
        has_kw = any(
            kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in state_keywords
        )
        if not has_kw:
            return False
        expr = (inv.lpc_expr or "").lower()
        # 纯查询不变量（如 report_status 的 ratio 计算公式）不算状态修改
        return not ("query(" in expr and "set(" not in expr)

    has_state_invariant = any(_is_state_mutation_invariant(inv) for inv in spec.invariants)
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_message_invariant_implies_message_output(idx: int) -> None:
    """属性：不变量提到消息/message/vision 的函数 -> 副作用含 MESSAGE_OUTPUT。"""
    spec = LAYER_SPEC.function_specs[idx]
    message_keywords = ("message", "消息", "vision")
    has_message_invariant = any(
        any(kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in message_keywords)
        for inv in spec.invariants
    )
    if has_message_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.MESSAGE_OUTPUT in kinds, (
            f"{spec.signature.name}: 有消息不变量但无 MESSAGE_OUTPUT 副作用"
        )
