"""层 E：战斗系统 -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``adm/daemons/combatd.c`` (1098 行) -- do_attack 七步核心 + skill_power +
  fight/auto_fight/select_opponent + death_penalty/killer_reward 框架
- ``feature/attack.c`` (258 行) -- fight_ob/kill_ob/clean_up_enemy/select_opponent/
  attack/reset_action/init（auto_fight 触发）
- ``feature/damage.c`` (331 行) -- receive_damage/receive_wound/receive_heal/
  receive_curing/die/unconcious/revive/heal_up
- ``feature/skill.c`` (183 行) -- skill_power 公式 + query_skill/improve_skill/
  skill_death_penalty
- ``feature/condition.c`` (113 行) -- apply_condition/update_condition/clear_condition 框架

核心契约要点（CLAUDE.md 架构不变量）：
1. **do_attack 七步副作用交织不可分离**（不得"先算后 apply"）--
   SideEffect.order 字段记录 message_output 与 state_mutation 的严格交织顺序。
   这是 dissent 3/01 子系统 5 的核心关注点。七步：
   (0) 选技能 -> (1) 取招式 -> (2) AP/DP 计算 -> (3) 闪避判定 ->
   (4) 招架判定 -> (5) 伤害结算 -> (6) 经验获得 -> (后) 结果消息 + 状态报告 + riposte
2. **三层资源不变量**：0 <= qi <= eff_qi <= max_qi（同样 jing/jingli/neili）
3. **29+ 处 random() 全部提取概率模型**（combat 确定性基础）-- 每处提取为 RandomSpec，
   含概率模型（如"闪避概率 = dp/(ap+dp)"）和 seed_inputs
4. **combat 确定性范围 = combat-only**（CLAUDE.md 架构不变量）-- 全仿真确定性后置 M3 后

不做（边界，违反即违规）：
- riposte 递归（后置，但 do_attack 中触发 riposte 的调用点在副作用里记录）
- s_combatd 阵法合击（后置）
- perform/exert 完整实现（只提取接口规格）
- condition 具体状态类型（蛇毒/醉/失明等后置，只提取 apply/update/clear 框架）
- kungfu/ 门派武学（798 文件，阶段 2）
- 死亡轮回细节（die/death_penalty/make_corpse 属层 F，但 do_attack 中触发死亡的
  调用点要在副作用里记录）
"""

from __future__ import annotations

from enum import StrEnum

from xkx.spec.base import (
    FunctionSignature,
    FunctionSpec,
    Invariant,
    LayerSpec,
    LPCParam,
    Postcondition,
    Precondition,
    RandomSpec,
    SideEffect,
    SideEffectType,
)

# ---------------------------------------------------------------------------
# 层 E 特定模型
# ---------------------------------------------------------------------------


class CombatStep(StrEnum):
    """do_attack 七步管线步骤编号（LPC 注释 (0)-(7) 对应）。"""

    SELECT_SKILL = "select_skill"
    """(0) 选技能：weapon skill_type / prepare / unarmed。"""

    GET_ACTION = "get_action"
    """(1) 取招式：reset_action -> query("actions")。"""

    CALC_AP_DP = "calc_ap_dp"
    """(2) AP/DP 计算：skill_power(attack) / skill_power(dodge)。"""

    DODGE_CHECK = "dodge_check"
    """(3) 闪避判定：random(ap+dp) < dp -> RESULT_DODGE。"""

    PARRY_CHECK = "parry_check"
    """(4) 招架判定：random(ap+pp) < pp -> RESULT_PARRY。"""

    DAMAGE_SETTLE = "damage_settle"
    """(5) 伤害结算：receive_damage + receive_wound + damage_msg。"""

    EXP_GAIN = "exp_gain"
    """(6) 经验获得：combat_exp + potential + improve_skill。"""

    POST_ACTION = "post_action"
    """(后) 结果消息输出 + 状态报告 + riposte 检查。"""


class ResourceType(StrEnum):
    """三层资源类型（LPC damage.c 命名）。"""

    QI = "qi"
    """气：当前值，0 <= qi <= eff_qi。"""

    JING = "jing"
    """精：当前值，0 <= jing <= eff_jing。"""

    JINGLI = "jingli"
    """精力：当前值，0 <= jingli <= max_jingli（无 eff 层）。"""

    NEILI = "neili"
    """内力：当前值，0 <= neili <= max_neili（无 eff 层）。"""


class AttackType(StrEnum):
    """攻击类型（LPC combat.h 定义）。"""

    REGULAR = "0"
    """TYPE_REGULAR=0：常规攻击，可触发 riposte。"""

    RIPOSTE = "1"
    """TYPE_RIPOSTE=1：反击攻击，不触发 riposte。"""

    QUICK = "2"
    """TYPE_QUICK=2：快速攻击，伤害减半，不触发 riposte。"""


# ---------------------------------------------------------------------------
# combatd.c: skill_power()
# ---------------------------------------------------------------------------

_skill_power = FunctionSpec(
    signature=FunctionSignature(
        name="skill_power",
        params=[
            LPCParam(name="ob", lpc_type="object", description="计算对象"),
            LPCParam(name="skill", lpc_type="string", description="技能名（如 unarmed/dodge/parry）"),
            LPCParam(name="usage", lpc_type="int", description="用途：SKILL_USAGE_ATTACK=1 / SKILL_USAGE_DEFENSE=2"),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="adm/daemons/combatd.c",
        line_range=(288, 333),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效 living 对象（!living(ob) 时返回 0）",
            lpc_expr="living(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 ob 在指定用途下的技能战斗力（AP/DP/PP 值）",
            return_value="int（战斗力，>= 0）",
            kind="ensure",
        ),
        Postcondition(
            description="level < 1 时返回 combat_exp/20 * (jingli_bonus/10)（低技能时用经验补偿）",
            state_change="无（纯计算函数）",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="power = (level^3)/3，level = query_skill(skill) + apply 修正",
            lpc_expr="power = (level * level * level) / 3",
            scope="function",
        ),
        Invariant(
            description="jingli_bonus = 50 + jingli/(max_jingli+1)*50，上限 150",
            lpc_expr="jingli_bonus = 50 + query('jingli')/(query('max_jingli')+1)*50; if > 150 then 150",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取 ob 的 query_skill / query_temp / query 等属性（纯查询，不修改）",
            lpc_call="ob->query_skill(skill); ob->query_temp('apply/attack')",
            target="ob（只读）",
        ),
    ],
    random_specs=[],
    notes="ATTACK 用 str 加成，DEFENSE 用 dex 加成。jingli_bonus 上限 150 时封顶。"
    "is_fighting() 时 DEFENSE 额外乘以 (100 + fight/dodge/10) / 100。",
)

# ---------------------------------------------------------------------------
# combatd.c: do_attack() 七步核心
# ---------------------------------------------------------------------------

_do_attack = FunctionSpec(
    signature=FunctionSignature(
        name="do_attack",
        params=[
            LPCParam(name="me", lpc_type="object", description="攻击者"),
            LPCParam(name="victim", lpc_type="object", description="防御者"),
            LPCParam(name="weapon", lpc_type="object", description="武器对象（可为 0/空手）"),
            LPCParam(name="attack_type", lpc_type="int", description="攻击类型 TYPE_REGULAR/RIPOSTE/QUICK"),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="adm/daemons/combatd.c",
        line_range=(340, 780),
    ),
    preconditions=[
        Precondition(
            description="me 和 victim 是有效对象且 living",
            lpc_expr="objectp(me) && objectp(victim) && living(me)",
            kind="require",
        ),
        Precondition(
            description="combat_exp 非负（负值会被修正为 0）",
            lpc_expr="victim->query('combat_exp') >= 0; me->query('combat_exp') >= 0",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="完成一次完整攻击回合，victim 可能受到伤害或闪避/招架",
            return_value="无显式返回值（LPC varargs int，实际不依赖返回值）",
            kind="ensure",
        ),
        Postcondition(
            description="damage > 0 时 victim.qi 已减少，若 wounded=1 则 victim.eff_qi 也减少",
            state_change="victim.receive_damage('qi', damage, me)；条件性 receive_wound",
            kind="effect",
        ),
        Postcondition(
            description="若 victim.qi*2 <= max_qi 且非 kill 模式，双方解除敌对关系（自动停手）",
            state_change="me->remove_enemy(victim); victim->remove_enemy(me)",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="三层资源不变量：0 <= qi <= eff_qi <= max_qi（jing/jingli/neili 同理）",
            lpc_expr="0 <= query('qi') <= query('eff_qi') <= query('max_qi')",
            scope="system",
        ),
        Invariant(
            description="七步副作用交织不可分离：不得先算后 apply，message 与 state mutation 严格按 order 交替",
            lpc_expr="side_effects ordered by CombatStep",
            scope="function",
        ),
        Invariant(
            description="ap/dp/pp 均不小于 1（ap < 1 时 ap=1, dp < 1 时 dp=1, pp < 1 时 pp=1）",
            lpc_expr="ap >= 1 && dp >= 1 && pp >= 1",
            scope="function",
        ),
        Invariant(
            description="TYPE_QUICK 攻击伤害减半",
            lpc_expr="attack_type == TYPE_QUICK => damage /= 2",
            scope="function",
        ),
    ],
    side_effects=[
        # 步骤 0: 选技能
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤0 选技能] 读取 weapon skill_type 或 prepare，确定 attack_skill",
            lpc_call="weapon->query('skill_type') / me->query_skill_prepare()",
            target="attack_skill（局部变量）",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤0] action_flag 交替：双技能 prepare 时按 action_flag 切换",
            lpc_call="me->query_temp('action_flag')",
            target="me.action_flag",
        ),
        # 步骤 1: 取招式
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤1 取招式] reset_action 刷新招式映射，query('actions') 获取当前 action",
            lpc_call="me->reset_action(); action = me->query('actions')",
            target="me.actions",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description='[步骤1] 构造攻击招式描述文本（result 字符串），action_flag==0 时首招，否则追加"紧跟着"',
            lpc_call='result = "\\n" + action["action"] + "！\\n"',
            target="result（局部变量）",
        ),
        # 步骤 2: AP/DP 计算
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤2 AP/DP] 随机选取 victim 攻击部位 limb",
            lpc_call="limb = limbs[random(sizeof(limbs))]",
            target="limb（局部变量）",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤2] 计算 ap = skill_power(me, attack_skill, ATTACK)，ap < 1 时 ap = 1",
            lpc_call="ap = skill_power(me, attack_skill, SKILL_USAGE_ATTACK)",
            target="ap（局部变量）",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤2] 设置 fight/dodge temp（userp(me) 且 action 有 dodge 值时）",
            lpc_call='me->set_temp("fight/dodge", action["dodge"])',
            target="me.temp.fight/dodge",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤2] 计算 dp = skill_power(victim, dodge, DEFENSE)，victim is_busy 时 dp/=3，dp < 1 时 dp = 1",
            lpc_call="dp = skill_power(victim, 'dodge', SKILL_USAGE_DEFENSE)",
            target="dp（局部变量）",
        ),
        # 步骤 3: 闪避判定
        SideEffect(
            order=9,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤3 闪避判定] random(ap+dp) < dp 时闪避成功，输出 dodge_skill 闪避消息",
            lpc_call="SKILL_D(dodge_skill)->query_dodge_msg(limb)",
            target="result（追加闪避文本）",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤3] 闪避成功时 victim 获得经验（dp<=ap 且非 PVP 时）",
            lpc_call='your["combat_exp"] += 1; victim->improve_skill("dodge", 1)',
            target="victim.combat_exp / victim.skills.dodge",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤3] NPC 闪避成功时 me 获得经验（ap<dp 且非 userp(me) 时）",
            lpc_call='my["combat_exp"] += 1; me->improve_skill(attack_skill, random(my["int"]))',
            target="me.combat_exp / me.skills",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤3] 闪避时 victim 消耗 jingli（attacker exp >> defender exp 时）",
            lpc_call='your["jingli"] -= 1',
            target="victim.jingli",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤3] 闪避/招架时 me 消耗 jingli（jiajin 值）",
            lpc_call='my["jingli"] -= my["jiajin"]',
            target="me.jingli",
        ),
        # 步骤 4: 招架判定（仅闪避失败时执行）
        SideEffect(
            order=14,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤4 招架判定] 计算 pp：victim 有武器时 parry，空手时 attack_skill；me 有武器而 victim 无武器时 pp=0",
            lpc_call="pp = skill_power(victim, 'parry'/'attack_skill', SKILL_USAGE_DEFENSE)",
            target="pp（局部变量）",
        ),
        SideEffect(
            order=15,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤4] random(ap+pp) < pp 时招架成功，输出 parry_skill 招架消息",
            lpc_call="SKILL_D(parry_skill)->query_parry_msg(weapon, victim)",
            target="result（追加招架文本）",
        ),
        SideEffect(
            order=16,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤4] 招架成功时 victim 获得经验（pp<=ap 且非 PVP 时）",
            lpc_call='your["combat_exp"] += 1; victim->improve_skill("parry", 1)',
            target="victim.combat_exp / victim.skills.parry",
        ),
        SideEffect(
            order=17,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤4] 招架时 victim 消耗 jingli（attacker exp >> defender exp 时）",
            lpc_call='your["jingli"] -= 1',
            target="victim.jingli",
        ),
        SideEffect(
            order=18,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤4] 招架时 me 消耗 jingli",
            lpc_call='my["jingli"] -= my["jiajin"]',
            target="me.jingli",
        ),
        # 步骤 5: 伤害结算（闪避和招架都失败时）
        SideEffect(
            order=19,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5 伤害结算] 基础伤害 = apply/damage + random(apply/damage) 取半",
            lpc_call="damage = (me->query_temp('apply/damage') + random(damage)) / 2",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=20,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] NPC 额外伤害加成（非 userp(me) 时 apply/attack 加成）",
            lpc_call="damage += ((int)me->query_temp('apply/attack') + 1) / 10 * (damage / 10)",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=21,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] action['damage'] 加成（damage/10 * damage/30）",
            lpc_call='damage += action["damage"] / 10 * (damage / 30)',
            target="damage（局部变量）",
        ),
        SideEffect(
            order=22,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] 技能等级伤害加成（query_skill(attack_skill)/10 * damage/10）",
            lpc_call="damage += ((int)me->query_skill(attack_skill) + 1) / 10 * (damage / 10)",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=23,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤5] 内功 hit_ob 回调：force_skill 的 hit_ob 可能返回 string（追加文本）或 int（damage_bonus 加成）",
            lpc_call="SKILL_D(force_skill)->hit_ob(me, victim, damage_bonus, my['jiali'])",
            target="result / damage_bonus",
        ),
        SideEffect(
            order=24,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] action['force'] 加成到 damage_bonus",
            lpc_call='damage_bonus += action["force"] / 10 * (damage_bonus / 100)',
            target="damage_bonus（局部变量）",
        ),
        SideEffect(
            order=25,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤5] 武学 hit_ob 回调：martial_skill 的 hit_ob 可能返回 string 或 int",
            lpc_call="SKILL_D(martial_skill)->hit_ob(me, victim, damage_bonus)",
            target="result / damage_bonus",
        ),
        SideEffect(
            order=26,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤5] 武器/空手 hit_ob 回调：weapon 或 me 的 hit_ob 返回 string 或 int",
            lpc_call="weapon->hit_ob(me, victim, damage_bonus) / me->hit_ob(me, victim, damage_bonus)",
            target="result / damage_bonus",
        ),
        SideEffect(
            order=27,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] jiajin 效果：jingli/20 + jiajin - victim.jingli/25 > 0 时加成 damage_bonus",
            lpc_call='foo = my["jingli"] / 20 + my["jiajin"] - your["jingli"] / 25',
            target="damage_bonus（局部变量）",
        ),
        SideEffect(
            order=28,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] 消耗 jingli（jiajin 值，jingli > jiajin 时）",
            lpc_call='my["jingli"] -= my["jiajin"]',
            target="me.jingli",
        ),
        SideEffect(
            order=29,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] TYPE_QUICK 伤害减半",
            lpc_call="if(attack_type == TYPE_QUICK) damage /= 2",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=30,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] damage_bonus 随机化加到 damage（正负 bonus 分支）",
            lpc_call="damage += (damage_bonus + random(damage_bonus)) / 2",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=31,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤5] combat_exp 防御削减循环：random(defense_factor) > me.combat_exp 时 damage 减 1/3，defense_factor 折半",
            lpc_call="while(random(defense_factor) > my['combat_exp']) { damage -= damage/3; defense_factor /= 2; }",
            target="damage（局部变量）",
        ),
        SideEffect(
            order=32,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤5] 特殊护甲 hit_by 回调：armor 的 hit_by 可能返回 string/int/mapping",
            lpc_call="armor->hit_by(me, victim, damage, weapon)",
            target="result / damage",
        ),
        SideEffect(
            order=33,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤5] 特殊闪避 hit_by 回调：dodge_skill 的 hit_by 可能返回 string/int/mapping",
            lpc_call="SKILL_D(dodge_skill)->hit_by(me, victim, damage)",
            target="result / damage",
        ),
        # 步骤 6: 伤害施加
        SideEffect(
            order=34,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤6 伤害施加] 调用 victim->receive_damage('qi', damage, me) 扣减 qi",
            lpc_call="victim->receive_damage('qi', damage, me)",
            target="victim.qi",
        ),
        SideEffect(
            order=35,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤6] 条件性 receive_wound：random(damage) > apply/armor 且 kill 模式时触发 wound（eff_qi 扣减）",
            lpc_call="victim->receive_wound('qi', damage - apply/armor, me)",
            target="victim.eff_qi",
        ),
        SideEffect(
            order=36,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[步骤6] 生成伤害描述文本 damage_msg(damage, action['damage_type'])",
            lpc_call="damage_msg(damage, action['damage_type'])",
            target="result（追加伤害文本）",
        ),
        # 步骤 7: 经验获得
        SideEffect(
            order=37,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤7 经验获得] me 获得经验（ap<=dp 且非 yield 且非 PVP 时，随机 jingli/int 判定）",
            lpc_call='my["combat_exp"] += 1; my["potential"] += 1; me->improve_skill(attack_skill, 1)',
            target="me.combat_exp / me.potential / me.skills",
        ),
        SideEffect(
            order=38,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤7] victim 获得经验（random(max_qi+qi) < damage 时，受重创获得经验）",
            lpc_call='your["combat_exp"] += 1; your["potential"] += 1',
            target="victim.combat_exp / victim.potential",
        ),
        SideEffect(
            order=39,
            kind=SideEffectType.STATE_MUTATION,
            description="[步骤7] yield 模式下 victim 获得 parry 经验（random(5)==0 时）",
            lpc_call='victim->improve_skill("parry", random(damage))',
            target="victim.skills.parry",
        ),
        # 后处理：结果消息输出
        SideEffect(
            order=40,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[后处理] 替换 result 中的占位符 $l（部位）/ $w（武器名）",
            lpc_call='replace_string(result, "$l", limb); replace_string(result, "$w", weapon->name())',
            target="result（局部变量）",
        ),
        SideEffect(
            order=41,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[后处理] 输出完整战斗回合消息 message_vision(result, me, victim)",
            lpc_call="message_vision(result, me, victim)",
            target="房间内所有对象",
        ),
        SideEffect(
            order=42,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[后处理] wizard verbose 模式输出 AP/DP/PP/伤害数值",
            lpc_call='tell_object(me, sprintf("AP：%d，DP：%d，PP：%d，伤害力：%d", ...))',
            target="me（仅 wizard）",
        ),
        SideEffect(
            order=43,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[后处理] damage > 0 时输出 victim 状态报告 report_status",
            lpc_call="report_status(victim, wounded)",
            target="victim（房间可见）",
        ),
        SideEffect(
            order=44,
            kind=SideEffectType.STATE_MUTATION,
            description="[后处理] victim is_busy 时触发 interrupt_me(me)",
            lpc_call="victim->interrupt_me(me)",
            target="victim",
        ),
        SideEffect(
            order=45,
            kind=SideEffectType.STATE_MUTATION,
            description="[后处理] 非 kill 模式且 victim.qi*2 <= max_qi 时双方解除敌对（自动停手）",
            lpc_call="me->remove_enemy(victim); victim->remove_enemy(me)",
            target="me.enemies / victim.enemies",
        ),
        SideEffect(
            order=46,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[后处理] 自动停手时输出胜利消息（winner_msg / winner_animal_msg）",
            lpc_call="message_vision(winner_msg[random(sizeof(winner_msg))], me, victim)",
            target="房间内所有对象",
        ),
        SideEffect(
            order=47,
            kind=SideEffectType.STATE_MUTATION,
            description="[后处理] action['post_action'] 回调（如果定义为 functionp）",
            lpc_call="evaluate(action['post_action'], me, victim, weapon, damage)",
            target="me/victim（取决于 post_action 实现）",
        ),
        # riposte 检查
        SideEffect(
            order=48,
            kind=SideEffectType.STATE_MUTATION,
            description="[riposte] TYPE_REGULAR + damage<1 + victim guarding 时检查 riposte 条件",
            lpc_call="victim->set_temp('guarding', 0)",
            target="victim.temp.guarding",
        ),
        SideEffect(
            order=49,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="[riposte] riposte 触发时输出破绽/反击消息，递归调用 do_attack(victim, me, ...)",
            lpc_call="do_attack(victim, me, victim->query_temp('weapon'), TYPE_QUICK/TYPE_RIPOSTE)",
            target="me/victim（递归攻击）",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="limbs[random(sizeof(limbs))]",
            probability_model="均匀分布，1/sizeof(limbs) 概率选取每个部位",
            semantic="随机选取攻击部位",
            seed_inputs=["victim.limbs 数组大小"],
            determinism_note="部位选择不影响伤害计算，仅影响文本 $l 替换",
        ),
        RandomSpec(
            lpc_call="random(ap + dp) < dp",
            probability_model="闪避概率 = dp/(ap+dp)，ap 和 dp 均 >= 1",
            semantic="闪避判定（步骤 3 核心随机）",
            seed_inputs=["ap = skill_power(me, attack_skill, ATTACK)", "dp = skill_power(victim, dodge, DEFENSE)"],
            determinism_note="AP/DP 比例决定闪避概率，combat 确定性基础",
        ),
        RandomSpec(
            lpc_call='random(your["jingli"] * 100 / (your["max_jingli"] + 1) + your["int"]) > 50',
            probability_model="闪避成功后 victim 获经验概率 = (jingli_ratio*100 + int) > 50",
            semantic="闪避时 victim 经验获得判定",
            seed_inputs=["victim.jingli", "victim.max_jingli", "victim.int"],
        ),
        RandomSpec(
            lpc_call="random(my['int']) > 15",
            probability_model="NPC 闪避时 me 获经验概率 = int > 15（int 越高越易触发）",
            semantic="NPC 闪避时攻击者经验获得判定",
            seed_inputs=["me.int"],
        ),
        RandomSpec(
            lpc_call="random(my['int'])",
            probability_model="NPC 闪避时 improve_skill 量 = random(int)",
            semantic="NPC 闪避时技能提升量",
            seed_inputs=["me.int"],
        ),
        RandomSpec(
            lpc_call="random(my['combat_exp']) >= random(your['combat_exp']) * 2",
            probability_model="attacker exp vs defender exp*2 的随机比较",
            semantic="闪避时 victim 是否消耗 jingli",
            seed_inputs=["me.combat_exp", "victim.combat_exp"],
        ),
        RandomSpec(
            lpc_call="random(ap + pp) < pp",
            probability_model="招架概率 = pp/(ap+pp)，ap 和 pp 均 >= 1",
            semantic="招架判定（步骤 4 核心随机）",
            seed_inputs=["ap = skill_power(me, attack_skill, ATTACK)", "pp = skill_power(victim, parry, DEFENSE)"],
            determinism_note="AP/PP 比例决定招架概率，combat 确定性基础",
        ),
        RandomSpec(
            lpc_call='random(your["jingli"] * 100 / (your["max_jingli"] + 1) + your["int"]) > 50',
            probability_model="招架成功后 victim 获经验概率（同闪避判定公式）",
            semantic="招架时 victim 经验获得判定",
            seed_inputs=["victim.jingli", "victim.max_jingli", "victim.int"],
        ),
        RandomSpec(
            lpc_call="random(my['combat_exp']) >= random(your['combat_exp']) * 2",
            probability_model="同闪避时 jingli 消耗判定",
            semantic="招架时 victim 是否消耗 jingli",
            seed_inputs=["me.combat_exp", "victim.combat_exp"],
        ),
        RandomSpec(
            lpc_call="random(damage)",
            probability_model="0 到 damage-1 均匀分布",
            semantic="基础伤害随机化（apply/damage + random(damage)) / 2）",
            seed_inputs=["me.apply/damage"],
        ),
        RandomSpec(
            lpc_call="random(damage_bonus)",
            probability_model="0 到 damage_bonus-1 均匀分布（正 bonus 时）",
            semantic="damage_bonus 随机化加成",
            seed_inputs=["damage_bonus"],
        ),
        RandomSpec(
            lpc_call="random(-damage_bonus)",
            probability_model="0 到 |damage_bonus|-1 均匀分布（负 bonus 时）",
            semantic="负 damage_bonus 随机化扣减",
            seed_inputs=["damage_bonus（负值）"],
        ),
        RandomSpec(
            lpc_call="random(defense_factor) > my['combat_exp']",
            probability_model="每次循环 defense 概率 = combat_exp/(defense_factor)（defense_factor 折半衰减）",
            semantic="combat_exp 防御削减循环",
            seed_inputs=["victim.combat_exp", "me.combat_exp"],
            determinism_note="while 循环，每次 defense_factor/=2，最多削减数次",
        ),
        RandomSpec(
            lpc_call="random(damage) > apply/armor",
            probability_model="伤害超过护甲概率 = 1 - apply_armor/damage",
            semantic="是否造成 wound（内伤）",
            seed_inputs=["damage", "victim.apply/armor"],
        ),
        RandomSpec(
            lpc_call="!random(4)",
            probability_model="空手 kill 模式下 1/4 概率触发 wound",
            semantic="空手 kill 时 wound 概率",
            seed_inputs=["(weapon == null)", "me.is_killing(victim)"],
        ),
        RandomSpec(
            lpc_call="!random(2)",
            probability_model="武器 kill 模式下 1/2 概率触发 wound",
            semantic="武器 kill 时 wound 概率",
            seed_inputs=["(weapon != null)", "me.is_killing(victim)"],
        ),
        RandomSpec(
            lpc_call="!random(7)",
            probability_model="空手非 kill 模式下 1/7 概率触发 wound",
            semantic="空手非 kill 时 wound 概率",
            seed_inputs=["(weapon == null)", "!me.is_killing(victim)"],
        ),
        RandomSpec(
            lpc_call="!random(4)",
            probability_model="武器非 kill 模式下 1/4 概率触发 wound",
            semantic="武器非 kill 时 wound 概率",
            seed_inputs=["(weapon != null)", "!me.is_killing(victim)"],
        ),
        RandomSpec(
            lpc_call="random(my['jingli'] * 100 / my['max_jingli'] + my['int']) > 30",
            probability_model="(jingli_ratio*100 + int) > 30 的概率",
            semantic="me 获得经验判定（步骤 7）",
            seed_inputs=["me.jingli", "me.max_jingli", "me.int"],
        ),
        RandomSpec(
            lpc_call="random(your['max_qi'] + your['qi']) < damage",
            probability_model="damage/(max_qi+qi) 概率",
            semantic="victim 受重创时获得经验",
            seed_inputs=["victim.max_qi", "victim.qi", "damage"],
        ),
        RandomSpec(
            lpc_call="random(my['combat_exp']) >= random(your['combat_exp'])",
            probability_model="attacker exp vs defender exp 随机比较",
            semantic="yield 模式下 victim parry 经验判定",
            seed_inputs=["me.combat_exp", "victim.combat_exp"],
        ),
        RandomSpec(
            lpc_call="random(5) == 0",
            probability_model="1/5 概率",
            semantic="yield 模式下 victim parry 经验获得",
            seed_inputs=[],
        ),
        RandomSpec(
            lpc_call="random(damage)",
            probability_model="0 到 damage-1 均匀分布",
            semantic="yield 模式下 parry 技能提升量",
            seed_inputs=["damage"],
        ),
        RandomSpec(
            lpc_call="winner_msg[random(sizeof(winner_msg))]",
            probability_model="均匀分布，1/6 概率选取每条胜利消息",
            semantic="自动停手时随机胜利消息",
            seed_inputs=["winner_msg 数组大小=6"],
        ),
        RandomSpec(
            lpc_call="winner_animal_msg[random(sizeof(winner_animal_msg))]",
            probability_model="均匀分布，1/3 概率选取每条动物胜利消息",
            semantic="NPC 自动停手时随机胜利消息",
            seed_inputs=["winner_animal_msg 数组大小=3"],
        ),
        RandomSpec(
            lpc_call="random(1 - apply/speed) < random((1 - apply/speed) * 6)",
            probability_model="riposte 触发概率，基于双方 speed 属性",
            semantic="riposte 反击触发判定",
            seed_inputs=["victim.apply/speed", "me.apply/speed"],
            determinism_note="riposte 递归后置，但触发判定需提取",
        ),
        RandomSpec(
            lpc_call="random(my['dex']) < 5",
            probability_model="5/dex 概率（dex 越高越不易露破绽）",
            semantic="riposte 时是否露破绽（TYPE_QUICK）或主动反击（TYPE_RIPOSTE）",
            seed_inputs=["me.dex"],
        ),
    ],
    notes="七步管线是战斗系统核心不变量。步骤 3-4 的 random(ap+dp)<dp / random(ap+pp)<pp 是"
    "combat 确定性的两个核心随机点。步骤 5 的伤害计算涉及多层回调（hit_ob/hit_by），"
    "回调返回 string/int/mapping 三种类型。步骤 6 的 receive_damage 与 receive_wound "
    "是三层资源不变量的写入点。riposte 递归后置但触发点在此记录。"
    "双武器/辟邪剑/双手互博在 fight() 中处理，不在 do_attack 内。",
)

# ---------------------------------------------------------------------------
# combatd.c: damage_msg()
# ---------------------------------------------------------------------------

_damage_msg = FunctionSpec(
    signature=FunctionSignature(
        name="damage_msg",
        params=[
            LPCParam(name="damage", lpc_type="int", description="伤害值"),
            LPCParam(name="type", lpc_type="string", description="伤害类型（擦伤/割伤/刺伤/跌伤/鞭伤/咬伤/瘀伤/内伤等）"),
        ],
        return_type="string",
        lpc_file="adm/daemons/combatd.c",
        line_range=(68, 228),
    ),
    preconditions=[
        Precondition(
            description='damage >= 0（== 0 时返回"未造成伤害"）',
            lpc_expr="damage >= 0",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回伤害描述文本，含 $n/$p/$l/$w 占位符（由调用方替换）",
            return_value="string（伤害描述，带 ANSI 颜色码）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="伤害分级：<20/<40/<80/<120/<160/>=160 六档文本，类型决定文本模板",
            lpc_expr="damage thresholds: 20, 40, 80, 120, 160",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="根据 damage 值和 type 返回对应伤害描述文本（纯文本生成，无状态修改）",
            lpc_call="return damage_msg_text",
            target="返回值（文本字符串）",
        ),
    ],
    random_specs=[],
    notes="8 种伤害类型 + default 分支。瘀伤/挫伤/内伤有 7 档分级（多一档 <240），其余 6 档。",
)

# ---------------------------------------------------------------------------
# combatd.c: eff_status_msg() / status_msg()
# ---------------------------------------------------------------------------

_eff_status_msg = FunctionSpec(
    signature=FunctionSignature(
        name="eff_status_msg",
        params=[
            LPCParam(name="ratio", lpc_type="int", description="eff_qi/max_qi * 100 的百分比"),
        ],
        return_type="string",
        lpc_file="adm/daemons/combatd.c",
        line_range=(230, 253),
    ),
    preconditions=[
        Precondition(
            description="ratio 是 0-100 的整数百分比",
            lpc_expr="0 <= ratio <= 100",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回有效伤势描述文本（带颜色码）",
            return_value="string（伤势描述）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description='ratio==100 时"气血充盈"，ratio<=5 时"风中残烛"',
            lpc_expr="ratio==100 => HIG; ratio<=5 => RED",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="根据 ratio 区间返回伤势描述文本（纯文本生成）",
            lpc_call="return eff_status_msg_text",
            target="返回值（文本字符串）",
        ),
    ],
    random_specs=[],
)

# ---------------------------------------------------------------------------
# combatd.c: report_status()
# ---------------------------------------------------------------------------

_report_status = FunctionSpec(
    signature=FunctionSignature(
        name="report_status",
        params=[
            LPCParam(name="ob", lpc_type="object", description="状态报告对象"),
            LPCParam(name="effective", lpc_type="int", description="1=显示 eff_qi 伤势, 0=显示 qi 疲惫度"),
        ],
        return_type="void",
        is_varargs=True,
        lpc_file="adm/daemons/combatd.c",
        line_range=(278, 284),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效对象",
            lpc_expr="objectp(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="已通过 message_vision 输出 ob 的状态描述",
            state_change="message_vision 已输出",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="ratio = query(eff_qi or qi) * 100 / query(max_qi)",
            lpc_expr="(int)ob->query('eff_qi') * 100 / (int)ob->query('max_qi')",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="计算 ratio 并调用 eff_status_msg/status_msg，通过 message_vision 输出",
            lpc_call='message_vision("( $N" + eff_status_msg(...) + " )\\n", ob)',
            target="房间内所有对象",
        ),
    ],
    random_specs=[],
)

# ---------------------------------------------------------------------------
# combatd.c: fight()
# ---------------------------------------------------------------------------

_fight = FunctionSpec(
    signature=FunctionSignature(
        name="fight",
        params=[
            LPCParam(name="me", lpc_type="object", description="攻击者"),
            LPCParam(name="victim", lpc_type="object", description="防御者"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(787, 845),
    ),
    preconditions=[
        Precondition(
            description="me 是 living 对象（!living(me) 时直接返回）",
            lpc_expr="living(me)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="根据主动性判定结果：攻击（do_attack）/ 防御（guarding）/ 无动作",
            state_change="可能调用 do_attack 或设置 me.guarding",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="victim is_busy 或 !living(victim) 时 me 必定攻击（TYPE_QUICK）",
            lpc_expr="victim->is_busy() || !living(victim) => do_attack(TYPE_QUICK)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查 victim 是否 busy/unconcious，若是则 me 清除 guarding 并发起 TYPE_QUICK 攻击",
            lpc_call='me->set_temp("guarding", 0); do_attack(me, victim, weapon, TYPE_QUICK)',
            target="me.temp.guarding",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="双武器/辟邪剑/双手互博判定：action_flag=1 后追加第二次 do_attack",
            lpc_call='me->set_temp("action_flag", 1); do_attack(me, victim, weapon, TYPE_QUICK); me->set_temp("action_flag", 0)',
            target="me.temp.action_flag",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="双手互博消息（double_attack 且 prepare < 2 时）",
            lpc_call='message_vision(CYN "\\n$N双手分使，灵活异常，好象变成了两个人似的！\\n" NOR, me)',
            target="房间内所有对象",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="主动性判定：random(victim.dex*3) < me.str*2 + apply/speed 时发起 TYPE_REGULAR 攻击",
            lpc_call="do_attack(me, victim, weapon, TYPE_REGULAR)",
            target="调用 do_attack",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="非攻击且未 guarding 时设置 guarding=1",
            lpc_call='me->set_temp("guarding", 1)',
            target="me.temp.guarding",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="guarding 时输出防御姿态消息（guard_msg 随机选取）",
            lpc_call="message_vision(guard_msg[random(sizeof(guard_msg))], me, victim)",
            target="房间内所有对象",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(victim->query_dex() * 3) < me->query_str() * 2 + me->query_temp('apply/speed')",
            probability_model="攻击主动性概率 = (str*2 + speed) / (dex*3)，超过则攻击",
            semantic="攻击主动性判定（攻击 vs 防御）",
            seed_inputs=["victim.dex", "me.str", "me.apply/speed"],
            determinism_note="决定每 tick 是否发起攻击还是防御",
        ),
        RandomSpec(
            lpc_call="guard_msg[random(sizeof(guard_msg))]",
            probability_model="均匀分布，1/5 概率选取每条防御消息",
            semantic="防御姿态随机消息",
            seed_inputs=["guard_msg 数组大小=5"],
        ),
    ],
    notes="fight() 由 attack() (feature/attack.c) 在 heart_beat 中调用。"
    "双武器/辟邪剑/双手互博的二次攻击在此函数内处理。",
)

# ---------------------------------------------------------------------------
# combatd.c: auto_fight() 及 start_* 系列
# ---------------------------------------------------------------------------

_auto_fight = FunctionSpec(
    signature=FunctionSignature(
        name="auto_fight",
        params=[
            LPCParam(name="me", lpc_type="object", description="攻击者"),
            LPCParam(name="obj", lpc_type="object", description="目标对象"),
            LPCParam(name="type", lpc_type="string", description="自动战斗类型：berserk/hatred/vendetta/aggressive"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(852, 867),
    ),
    preconditions=[
        Precondition(
            description="me 或 obj 至少一方是 player（NPC-NPC 不自动战斗）",
            lpc_expr="userp(me) || userp(obj)",
            kind="require",
        ),
        Precondition(
            description="me 未在 looking_for_trouble 状态（防止重复触发）",
            lpc_expr='!me->query_temp("looking_for_trouble")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="设置 looking_for_trouble=1 并 call_out 延迟启动对应类型的自动战斗",
            state_change='me->set_temp("looking_for_trouble", 1); call_out("start_"+type, 0, me, obj)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="call_out 延迟 0 秒执行，给 victim 一个逃脱机会",
            lpc_expr='call_out("start_" + type, 0, me, obj)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 looking_for_trouble 标记防止重复触发",
            lpc_call='me->set_temp("looking_for_trouble", 1)',
            target="me.temp.looking_for_trouble",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.CALL_OUT,
            description="延迟调用 start_berserk/hatred/vendetta/aggressive",
            lpc_call='call_out("start_" + type, 0, me, obj)',
            target="call_out 队列",
        ),
    ],
    random_specs=[],
    notes="auto_fight 是 init() 中触发的入口，实际战斗逻辑在 start_* 系列函数中。"
    "start_berserk 有 neili vs shen 随机判定决定是否 kill 或 fight。"
    "start_hatred 按 race 输出不同的 catch_hunt 消息。"
    "start_vendetta/start_aggressive 直接 kill_ob。",
)

# ---------------------------------------------------------------------------
# combatd.c: death_penalty() / killer_reward() / winner_reward()
# ---------------------------------------------------------------------------

_death_penalty = FunctionSpec(
    signature=FunctionSignature(
        name="death_penalty",
        params=[
            LPCParam(name="victim", lpc_type="object", description="死亡的玩家对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(987, 1025),
    ),
    preconditions=[
        Precondition(
            description="victim 是 userp 且非 wizard",
            lpc_expr="userp(victim) && !wizardp(victim)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="victim 清除所有 condition，combat_exp/behavior_exp/shen/potential/balance 被扣减",
            state_change="victim.clear_condition(); victim.combat_exp -= amount; ...",
            kind="effect",
        ),
        Postcondition(
            description="victim.death_times += 1（若 combat_exp >= 10000 * death_times）",
            state_change='victim->add("death_times", 1)',
            kind="observable",
        ),
        Postcondition(
            description="victim.skill_death_penalty() 已调用，victim.save() 已调用",
            state_change="victim->skill_death_penalty(); victim->save()",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="combat_exp 扣减上限 5000，最低扣 20（若 combat_exp > 20）",
            lpc_expr="amount = combat_exp/100; if(amount>5000) amount=5000; if(amount<=50 && combat_exp>20) amount=20",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清除所有 condition",
            lpc_call="victim->clear_condition()",
            target="victim.conditions",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="death_times +1（若满足条件）",
            lpc_call='victim->add("death_times", 1)',
            target="victim.death_times",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="shen 扣减 1/20",
            lpc_call='victim->add("shen", -(int)victim->query("shen") / 20)',
            target="victim.shen",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="behavior_exp 扣减 1/20",
            lpc_call='victim->add("behavior_exp", -(int)victim->query("behavior_exp") / 20)',
            target="victim.behavior_exp",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="combat_exp 扣减（amount = combat_exp/100，上限 5000）",
            lpc_call='victim->add("combat_exp", -amount)',
            target="victim.combat_exp",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="potential 扣减 1/2（若 amount > 50）",
            lpc_call='victim->add("potential", -(int)victim->query("potential") / 2)',
            target="victim.potential",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="balance 扣减（超过 10000 部分减半）",
            lpc_call='victim->add("balance", -amount/2)',
            target="victim.balance",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="death_count +1",
            lpc_call='victim->add("death_count", 1)',
            target="victim.death_count",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="清除 vendetta 和 temp 标记",
            lpc_call='victim->delete("vendetta"); victim->delete_temp("rob_victim"); victim->delete_temp("initiator")',
            target="victim.vendetta / victim.temp",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="thief 标记减半",
            lpc_call='victim->set("thief", (int)victim->query("thief") / 2)',
            target="victim.thief",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="技能死亡惩罚（所有技能等级下降）",
            lpc_call="victim->skill_death_penalty()",
            target="victim.skills",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.PERSISTENCE,
            description="保存玩家数据",
            lpc_call="victim->save()",
            target="victim 存档",
        ),
    ],
    random_specs=[],
    notes="death_penalty 属层 F（死亡轮回）的调用点，但在 combatd.c 中定义。"
    "do_attack 不直接调用 death_penalty，而是通过 victim->die() -> COMBAT_D->death_penalty() 链触发。"
    "此处提取因为 do_attack 步骤 6 的 receive_damage 可能导致 victim.qi <= 0 触发 die()。",
)

# ---------------------------------------------------------------------------
# attack.c: fight_ob() / kill_ob()
# ---------------------------------------------------------------------------

_fight_ob = FunctionSpec(
    signature=FunctionSignature(
        name="fight_ob",
        params=[
            LPCParam(name="ob", lpc_type="object", description="敌对对象"),
        ],
        return_type="void",
        lpc_file="feature/attack.c",
        line_range=(40, 48),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效对象且不等于 this_object()",
            lpc_expr="ob && ob != this_object()",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="ob 被加入 enemy 列表（若尚未存在），set_heart_beat(1) 已触发",
            state_change="enemy += ({ ob }); set_heart_beat(1)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="enemy 列表不重复（member_array 检查）",
            lpc_expr="member_array(ob, enemy) == -1",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="启动 heart_beat（tick=1s 的驱动核心）",
            lpc_call="set_heart_beat(1)",
            target="this_object().heart_beat",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="将 ob 加入 enemy 列表",
            lpc_call="enemy += ({ ob })",
            target="enemy 数组",
        ),
    ],
    random_specs=[],
    notes="fight_ob 只加入 enemy 列表，不通知对方。kill_ob 会额外通知 victim。",
)

_kill_ob = FunctionSpec(
    signature=FunctionSignature(
        name="kill_ob",
        params=[
            LPCParam(name="ob", lpc_type="object", description="追杀目标"),
        ],
        return_type="void",
        lpc_file="feature/attack.c",
        line_range=(51, 62),
    ),
    preconditions=[
        Precondition(
            description="当前环境允许战斗（!no_fight）",
            lpc_expr='!environment()->query("no_fight")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="ob 的 id 被加入 killer 列表，ob 收到被追杀通知，fight_ob(ob) 已调用",
            state_change="killer += ({ ob->query('id') }); fight_ob(ob)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="killer 列表不重复（member_array 检查）",
            lpc_expr="member_array(ob->query('id'), killer) == -1",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="no_fight 房间检查：环境 no_fight 时直接返回",
            lpc_call='if(environment()->query("no_fight")) return',
            target="environment",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="将 ob 的 id 加入 killer 列表",
            lpc_call='killer += ({ ob->query("id") })',
            target="killer 数组",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="通知 victim 被追杀",
            lpc_call='tell_object(ob, HIR "看起来" + name() + "想杀死你！\\n" NOR)',
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 fight_ob(ob) 加入 enemy 列表并启动 heart_beat",
            lpc_call="fight_ob(ob)",
            target="enemy 数组 / heart_beat",
        ),
    ],
    random_specs=[],
    notes="kill_ob 在 no_fight 房间直接返回（不追杀）。fight_ob 是 kill_ob 的子集。",
)

# ---------------------------------------------------------------------------
# attack.c: select_opponent()
# ---------------------------------------------------------------------------

_select_opponent = FunctionSpec(
    signature=FunctionSignature(
        name="select_opponent",
        params=[],
        return_type="object",
        lpc_file="feature/attack.c",
        line_range=(79, 88),
    ),
    preconditions=[
        Precondition(
            description="enemy 列表非空（空时返回 0）",
            lpc_expr="sizeof(enemy) > 0",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 enemy 列表中的随机一个对象（或 enemy[0]）",
            return_value="object（选中的对手）或 0（无敌人）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="最多从前 MAX_OPPONENT=4 个敌人中选取",
            lpc_expr="which = random(MAX_OPPONENT); which < sizeof(enemy) ? enemy[which] : enemy[0]",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="随机选取对手索引（最多 MAX_OPPONENT=4）",
            lpc_call="which = random(MAX_OPPONENT)",
            target="which（局部变量）",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(MAX_OPPONENT)",
            probability_model="1/4 概率选取前 4 个敌人之一（不足 4 个时回退到 enemy[0]）",
            semantic="对手选择随机化",
            seed_inputs=["MAX_OPPONENT=4", "sizeof(enemy)"],
            determinism_note="MAX_OPPONENT=4 限制多对一时被攻击的频率",
        ),
    ],
)

# ---------------------------------------------------------------------------
# attack.c: attack()
# ---------------------------------------------------------------------------

_attack = FunctionSpec(
    signature=FunctionSignature(
        name="attack",
        params=[],
        return_type="int",
        lpc_file="feature/attack.c",
        line_range=(208, 224),
    ),
    preconditions=[
        Precondition(
            description="由 heart_beat 调用，this_object 是 living 且有 enemy",
            lpc_expr="living(this_object()) && sizeof(enemy) > 0",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示执行了攻击动作，0 表示无对手",
            return_value="1=有对手并攻击, 0=无对手",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="yield 模式下不发起攻击但仍返回 1",
            lpc_expr='this_object()->query_temp("yield") => return 1',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清理无效敌人（已销毁/不在同房间/昏迷且非 kill）",
            lpc_call="clean_up_enemy()",
            target="enemy 数组",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="选取对手 select_opponent()",
            lpc_call="opponent = select_opponent()",
            target="opponent（局部变量）",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_opponent",
            lpc_call='set_temp("last_opponent", opponent)',
            target="this_object().temp.last_opponent",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="yield 检查：yield 模式时跳过攻击",
            lpc_call='if(this_object()->query_temp("yield")) return 1',
            target="this_object().temp.yield",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="special_attack 检查（阵法合击等，后置）；否则调用 COMBAT_D->fight()",
            lpc_call="COMBAT_D->fight(this_object(), opponent)",
            target="调用 fight / do_attack",
        ),
    ],
    random_specs=[],
    notes="attack() 是 heart_beat 中每 tick 调用的入口。"
    "special_attack（s_combatd 阵法合击）后置，但调用点在此记录。",
)

# ---------------------------------------------------------------------------
# attack.c: reset_action()
# ---------------------------------------------------------------------------

_reset_action = FunctionSpec(
    signature=FunctionSignature(
        name="reset_action",
        params=[],
        return_type="void",
        lpc_file="feature/attack.c",
        line_range=(143, 171),
    ),
    preconditions=[
        Precondition(
            description="this_object 有技能或默认 unarmed 技能",
            lpc_expr="query_skill_prepare() 或 query_temp('weapon')",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="actions 已更新为当前武器/技能对应的招式映射",
            state_change='set("actions", ...)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="有 mapped skill 时用 SKILL_D(skill)->query_action；否则用 weapon->query('actions') 或 default_actions",
            lpc_expr="skill_map[type] ? SKILL_D(skill)->query_action : weapon->query('actions') / query('default_actions')",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="确定当前技能类型（weapon skill_type / prepare / unarmed）",
            lpc_call="type = ob->query('skill_type') / prepare / 'unarmed'",
            target="type（局部变量）",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="查询 mapped skill 并设置 actions",
            lpc_call='set("actions", (: call_other, SKILL_D(skill), "query_action", me, ob :))',
            target="this_object().actions",
        ),
    ],
    random_specs=[],
    notes="reset_action 是 do_attack 步骤 1 的前置。actions 是 functionp 或 mapping，"
    "在 do_attack 中被 query('actions') 读取。",
)

# ---------------------------------------------------------------------------
# damage.c: receive_damage()
# ---------------------------------------------------------------------------

_receive_damage = FunctionSpec(
    signature=FunctionSignature(
        name="receive_damage",
        params=[
            LPCParam(name="type", lpc_type="string", description="资源类型：qi/jing/jingli"),
            LPCParam(name="damage", lpc_type="int", description="伤害值（>= 0）"),
            LPCParam(name="who", lpc_type="mixed", description="伤害来源对象或 id", is_varargs_tail=True),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="feature/damage.c",
        line_range=(13, 37),
    ),
    preconditions=[
        Precondition(
            description="damage >= 0（负值 error）",
            lpc_expr="damage >= 0",
            kind="input_constraint",
        ),
        Precondition(
            description="type 只能是 jing/qi/jingli（其他 error）",
            lpc_expr='type == "jing" || type == "qi" || type == "jingli"',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="query(type) 减少 damage，不低于 -1；返回 damage 值",
            return_value="damage（传入的伤害值）",
            kind="ensure",
        ),
        Postcondition(
            description="last_damage_from 已记录伤害来源",
            state_change='set_temp("last_damage_from", who)',
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="三层资源不变量：0 <= qi <= eff_qi <= max_qi（receive_damage 只扣 qi，不扣 eff_qi）",
            lpc_expr="query('qi') >= 0（减后 >= -1，但 -1 表示溢出）",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="记录伤害来源 last_damage_from",
            lpc_call='set_temp("last_damage_from", who)',
            target="this_object().temp.last_damage_from",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_eff_damage_from（living 且 who 是 user 时）",
            lpc_call='set_temp("last_eff_damage_from", who->query("id"))',
            target="this_object().temp.last_eff_damage_from",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="扣减资源：val = query(type) - damage；val >= 0 时 set(type, val)，否则 set(type, -1)",
            lpc_call="set(type, query(type) - damage)",
            target="this_object().{type}",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="启动 heart_beat（确保恢复循环运行）",
            lpc_call="set_heart_beat(1)",
            target="this_object().heart_beat",
        ),
    ],
    random_specs=[],
    notes="receive_damage 是三层资源的 qi 层写入点。val < 0 时设为 -1（LPC 惯例：-1 表示溢出/即将死亡）。"
    "调用方（do_attack 步骤 6）通过返回值获取实际伤害值。",
)

# ---------------------------------------------------------------------------
# damage.c: receive_wound()
# ---------------------------------------------------------------------------

_receive_wound = FunctionSpec(
    signature=FunctionSignature(
        name="receive_wound",
        params=[
            LPCParam(name="type", lpc_type="string", description="资源类型：qi/jing（不含 jingli）"),
            LPCParam(name="damage", lpc_type="int", description="伤口伤害值（>= 0）"),
            LPCParam(name="who", lpc_type="mixed", description="伤害来源", is_varargs_tail=True),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="feature/damage.c",
        line_range=(39, 66),
    ),
    preconditions=[
        Precondition(
            description="damage >= 0（负值 error）",
            lpc_expr="damage >= 0",
            kind="input_constraint",
        ),
        Precondition(
            description="type 只能是 qi/jing（不含 jingli）",
            lpc_expr='type == "jing" || type == "qi"',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="query('eff_'+type) 减少 damage，不低于 -1；query(type) 也被同步降低到不超过新的 eff 值",
            return_value="damage（传入的伤口伤害值）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="三层资源不变量：receive_wound 后 qi <= eff_qi（eff 降低时 qi 同步降低）",
            lpc_expr="if(query(type) > val) set(type, val)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="记录伤害来源",
            lpc_call='set_temp("last_damage_from", who)',
            target="this_object().temp.last_damage_from",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_eff_damage_from（living 且 who 是 user 时）",
            lpc_call='set_temp("last_eff_damage_from", who->query("id"))',
            target="this_object().temp.last_eff_damage_from",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="扣减 eff 层：val = query('eff_'+type) - damage；set('eff_'+type, max(val, -1))",
            lpc_call='set("eff_" + type, query("eff_" + type) - damage)',
            target="this_object().eff_{type}",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="同步 qi/jing 到不超过新的 eff 值",
            lpc_call='if(query(type) > val) set(type, val)',
            target="this_object().{type}",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="启动 heart_beat",
            lpc_call="set_heart_beat(1)",
            target="this_object().heart_beat",
        ),
    ],
    random_specs=[],
    notes="receive_wound 是三层资源的 eff 层写入点。eff 降低时 qi 同步降低（保持 qi <= eff_qi 不变量）。"
    "do_attack 步骤 6 在条件满足时调用（random(damage) > apply/armor 且 kill 模式时）。",
)

# ---------------------------------------------------------------------------
# damage.c: receive_heal() / receive_curing()
# ---------------------------------------------------------------------------

_receive_heal = FunctionSpec(
    signature=FunctionSignature(
        name="receive_heal",
        params=[
            LPCParam(name="type", lpc_type="string", description="资源类型：qi/jing/jingli"),
            LPCParam(name="heal", lpc_type="int", description="恢复值（>= 0）"),
        ],
        return_type="int",
        lpc_file="feature/damage.c",
        line_range=(68, 83),
    ),
    preconditions=[
        Precondition(
            description="heal >= 0（负值 error）",
            lpc_expr="heal >= 0",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="query(type) 增加 heal，但不超过 eff_{type}（jingli 不超过 max_jingli）；返回 heal",
            return_value="heal（传入的恢复值）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="恢复后 qi <= eff_qi（jingli <= max_jingli）",
            lpc_expr="val > query('eff_'+type) && type!='jingli' => set(type, eff); type=='jingli' && val > max_jingli => set(type, max_jingli)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="增加资源值并限制在 eff 层上限内",
            lpc_call="set(type, min(query(type)+heal, query('eff_'+type)))",
            target="this_object().{type}",
        ),
    ],
    random_specs=[],
    notes="receive_heal 恢复当前值层（qi/jing），上限为 eff 层。jingli 无 eff 层，上限为 max_jingli。",
)

_receive_curing = FunctionSpec(
    signature=FunctionSignature(
        name="receive_curing",
        params=[
            LPCParam(name="type", lpc_type="string", description="资源类型：qi/jing（不含 jingli）"),
            LPCParam(name="heal", lpc_type="int", description="恢复值（>= 0）"),
        ],
        return_type="int",
        lpc_file="feature/damage.c",
        line_range=(85, 103),
    ),
    preconditions=[
        Precondition(
            description="heal >= 0（负值 error）",
            lpc_expr="heal >= 0",
            kind="input_constraint",
        ),
        Precondition(
            description="type 只能是 qi/jing",
            lpc_expr='type == "qi" || type == "jing"',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="query('eff_'+type) 增加 heal，但不超过 max_{type}；返回实际恢复量",
            return_value="heal（或 max-val，若超过上限）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="恢复后 eff_qi <= max_qi",
            lpc_expr="val + heal > max => set('eff_'+type, max)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="增加 eff 层值并限制在 max 层上限内",
            lpc_call='set("eff_" + type, min(query("eff_"+type)+heal, query("max_"+type)))',
            target="this_object().eff_{type}",
        ),
    ],
    random_specs=[],
    notes="receive_curing 恢复有效值层（eff_qi/eff_jing），上限为 max 层。",
)

# ---------------------------------------------------------------------------
# damage.c: die() / unconcious() / revive()
# ---------------------------------------------------------------------------

_die = FunctionSpec(
    signature=FunctionSignature(
        name="die",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(152, 253),
    ),
    preconditions=[
        Precondition(
            description="this_object 的 qi/eff_qi 已降至 0 以下（或被特殊机制触发死亡）",
            lpc_expr="query('qi') <= 0 || query('eff_qi') <= 0",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="no_death 房间+userp 时转为 unconcious；否则执行死亡流程",
            state_change="clear_condition / death_penalty / killer_reward / make_corpse / move(DEATH_ROOM)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="死亡后 user 的 qi/eff_qi/jing/eff_jing/jingli 均设为 1（非 0）",
            lpc_expr="set('qi',1); set('eff_qi',1); set('jing',1); set('eff_jing',1); set('jingli',1)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="no_death 房间检查：userp 且 no_death 时转为 unconcious 并返回",
            lpc_call='if(environment()->query("no_death") && userp(this_object())) { unconcious(); return; }',
            target="this_object()",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="若已昏迷则先静默 revive(1)",
            lpc_call='if(!living(this_object())) revive(1)',
            target="this_object()",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="清除所有 condition 和 poisoner",
            lpc_call="clear_condition(); delete('poisoner')",
            target="this_object().conditions / poisoner",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="输出死亡消息",
            lpc_call='COMBAT_D->announce(this_object(), "dead")',
            target="房间内所有对象",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="userp 且非 no_death 时调用 death_penalty（属层 F，但触发点在此记录）",
            lpc_call="COMBAT_D->death_penalty(this_object())",
            target="this_object() 各属性",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="killer_reward：记录 my_killer，调用 killer_reward",
            lpc_call='set_temp("my_killer", killer->query("id")); COMBAT_D->killer_reward(killer, this_object())',
            target="this_object().temp.my_killer / killer",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="PKILL_DATA / PLAYER_DEATH 日志记录（userp 时）",
            lpc_call='log_file("PKILL_DATA", ...); log_file("PLAYER_DEATH", ...)',
            target="日志文件",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="生成尸体 make_corpse 并 move 到房间",
            lpc_call="corpse = CHAR_D->make_corpse(this_object(), killer); corpse->move(environment())",
            target="corpse 对象",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="清除所有 killer/enemy 关系",
            lpc_call="remove_all_killer(); all_inventory(environment())->remove_killer(this_object())",
            target="this_object() / 房间内对象",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="userp 时：qi/eff_qi/jing/eff_jing 设为 1，jingli 设为 1",
            lpc_call='set("jing",1); set("eff_jing",1); set("qi",1); set("eff_qi",1); set("jingli",1)',
            target="this_object() 资源属性",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.PERSISTENCE,
            description="userp 且非 no_death 时保存并移至 DEATH_ROOM",
            lpc_call="this_object()->save(); this_object()->move(DEATH_ROOM); DEATH_ROOM->start_death(this_object())",
            target="this_object() 存档 / 位置",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="NPC 死亡时 destruct(this_object())",
            lpc_call="destruct(this_object())",
            target="this_object()（NPC）",
        ),
    ],
    random_specs=[],
    notes="die() 属层 F（死亡轮回），但 do_attack 步骤 6 的 receive_damage 可能导致 qi<=0 触发 die()。"
    "此处提取死亡触发链和副作用顺序，轮回细节（DEATH_ROOM/start_death）属层 F。",
)

_unconcious = FunctionSpec(
    signature=FunctionSignature(
        name="unconcious",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(105, 135),
    ),
    preconditions=[
        Precondition(
            description="this_object 是 living（已昏迷则直接返回）",
            lpc_expr="living(this_object())",
            kind="require",
        ),
        Precondition(
            description="非 wizard immortal 模式",
            lpc_expr='!(wizardp(this_object()) && query("env/immortal"))',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="winner_reward 已调用，remove_all_enemy 已调用，qi/jing/jingli 归零",
            state_change="qi=0; jing=0; jingli=0; disable_player",
            kind="effect",
        ),
        Postcondition(
            description="call_out revive 延迟唤醒（random(100-con)+30 秒后）",
            state_change='call_out("revive", random(100-query("con"))+30)',
            kind="observable",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="winner_reward：若有 last_damage_from 则调用",
            lpc_call='COMBAT_D->winner_reward(defeater, this_object())',
            target="defeater / this_object()",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="清除所有敌人关系并中断当前动作",
            lpc_call="remove_all_enemy(); interrupt_me(); dismiss_team()",
            target="this_object().enemy / team",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="输出昏迷消息给 victim",
            lpc_call='message("system", HIR "\\n你的眼前一黑，接著什么也不知道了....\\n\\n" NOR, this_object())',
            target="this_object()",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="disable_player + 资源归零 + 屏蔽消息",
            lpc_call='disable_player(" <昏迷不醒>"); set("jing",0); set("qi",0); set("jingli",0); set_temp("block_msg/all", 1)',
            target="this_object() 资源 / 消息屏蔽",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="输出昏迷公告消息",
            lpc_call='COMBAT_D->announce(this_object(), "unconcious")',
            target="房间内所有对象",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.CALL_OUT,
            description="延迟唤醒：call_out revive",
            lpc_call='call_out("revive", random(100 - query("con")) + 30)',
            target="call_out 队列",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call='random(100 - query("con")) + 30',
            probability_model="昏迷时间 = 30 + random(100-con) 秒，con 越高醒来越快",
            semantic="昏迷持续时间随机化",
            seed_inputs=["this_object().con"],
            determinism_note="con 属性影响昏迷恢复速度",
        ),
    ],
)

# ---------------------------------------------------------------------------
# condition.c: apply_condition() / update_condition() / clear_condition()
# ---------------------------------------------------------------------------

_apply_condition = FunctionSpec(
    signature=FunctionSignature(
        name="apply_condition",
        params=[
            LPCParam(name="cnd", lpc_type="string", description="状态标识名（如 poison/busy/killer）"),
            LPCParam(name="info", lpc_type="mixed", description="状态信息（可为 int/mapping/string，由 condition daemon 定义）"),
        ],
        return_type="void",
        lpc_file="feature/condition.c",
        line_range=(79, 85),
    ),
    preconditions=[
        Precondition(
            description="cnd 是合法字符串",
            lpc_expr="stringp(cnd)",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="conditions[cnd] 已设为 info（覆盖旧值，不检查是否已存在）",
            state_change="conditions[cnd] = info",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="apply 不检查重复，覆盖旧值（condition giver 负责检查是否覆盖）",
            lpc_expr="直接 conditions[cnd] = info",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 condition 映射（若 conditions 为 NULL 则初始化）",
            lpc_call="conditions = ([ cnd : info ]) 或 conditions[cnd] = info",
            target="this_object().conditions",
        ),
    ],
    random_specs=[],
    notes="apply_condition 是 condition 框架的写入接口。具体状态类型（蛇毒/醉/失明/killer/pker 等）后置。"
    "info 的结构由 CONDITION_D(cnd) 的 update_condition 定义。",
)

_update_condition = FunctionSpec(
    signature=FunctionSignature(
        name="update_condition",
        params=[],
        return_type="int",
        lpc_file="feature/condition.c",
        line_range=(21, 69),
    ),
    preconditions=[
        Precondition(
            description="由 heart_beat 调用",
            lpc_expr="heart_beat 调用链",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="所有已注册 condition 的 daemon update_condition 已调用；过期的 condition 已移除",
            state_change="过期 condition 已 map_delete",
            kind="effect",
        ),
        Postcondition(
            description="返回 update_flag（CND_CONTINUE 等位掩码）",
            return_value="int（update_flag 位掩码）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="condition daemon 返回 0（或无 CND_CONTINUE）时移除该 condition",
            lpc_expr="if(!(flag & CND_CONTINUE)) map_delete(conditions, cnd[i])",
            scope="function",
        ),
        Invariant(
            description="condition daemon 加载失败时移除该 condition 并记录 condition.err",
            lpc_expr="if(err || !cnd_d) { log_file('condition.err', ...); map_delete(conditions, cnd[i]); }",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="遍历所有 condition，加载并调用 CONDITION_D(cnd)->update_condition(this_object(), conditions[cnd])",
            lpc_call="call_other(cnd_d, 'update_condition', this_object(), conditions[cnd[i]])",
            target="this_object() / condition daemon",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="移除过期 condition（daemon 返回值不含 CND_CONTINUE）",
            lpc_call="map_delete(conditions, cnd[i])",
            target="this_object().conditions",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="daemon 加载失败时记录 condition.err 日志并移除",
            lpc_call='log_file("condition.err", sprintf(...))',
            target="日志文件",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="conditions 为空时置 NULL",
            lpc_call='if(!sizeof(conditions)) conditions = 0',
            target="this_object().conditions",
        ),
    ],
    random_specs=[],
    notes="update_condition 是 condition 框架的 tick 驱动接口。"
    "每个 condition 由独立的 CONDITION_D daemon 处理，update_condition 只做调度和生命周期管理。"
    "nomask 修饰确保不可被 override。",
)

_clear_condition = FunctionSpec(
    signature=FunctionSignature(
        name="clear_condition",
        params=[],
        return_type="void",
        lpc_file="feature/condition.c",
        line_range=(105, 108),
    ),
    preconditions=[
        Precondition(
            description="this_object 是有效对象（通常由 die/death_penalty 调用）",
            lpc_expr="objectp(this_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="conditions 已置为 0（NULL）",
            state_change="conditions = 0",
            kind="ensure",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清除所有 condition",
            lpc_call="conditions = 0",
            target="this_object().conditions",
        ),
    ],
    random_specs=[],
    notes="clear_condition 清除所有状态。die()/death_penalty() 中调用。"
    "clear_one_condition(cnd) 清除单个，clear_all_condition() 是 nomask 版本。",
)

# ---------------------------------------------------------------------------
# skill.c: query_skill() / improve_skill()
# ---------------------------------------------------------------------------

_query_skill = FunctionSpec(
    signature=FunctionSignature(
        name="query_skill",
        params=[
            LPCParam(name="skill", lpc_type="string", description="技能名"),
            LPCParam(name="raw", lpc_type="int", description="1=原始值, 0=含 temp 加成", is_varargs_tail=True),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="feature/skill.c",
        line_range=(94, 109),
    ),
    preconditions=[
        Precondition(
            description="skill 是合法技能名",
            lpc_expr="stringp(skill)",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="raw=0 时返回 skills[skill]/2 + apply/{skill} + skills[skill_map[skill]]；raw=1 时返回 skills[skill]",
            return_value="int（技能等级）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="非 raw 模式：技能有效值 = temp 加成 + skills/2 + mapped skill 全值",
            lpc_expr="s = query_temp('apply/'+skill) + skills[skill]/2 + skills[skill_map[skill]]",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取技能值（纯查询，不修改状态）",
            lpc_call="query_temp('apply/' + skill); skills[skill]; skill_map[skill]",
            target="this_object()（只读）",
        ),
    ],
    random_specs=[],
)

_improve_skill = FunctionSpec(
    signature=FunctionSignature(
        name="improve_skill",
        params=[
            LPCParam(name="skill", lpc_type="string", description="技能名"),
            LPCParam(name="amount", lpc_type="int", description="提升量"),
            LPCParam(name="weak_mode", lpc_type="int", description="弱模式（不初始化新技能）", is_varargs_tail=True),
        ],
        return_type="void",
        is_varargs=True,
        lpc_file="feature/skill.c",
        line_range=(149, 182),
    ),
    preconditions=[
        Precondition(
            description="this_object 是 userp（NPC 不提升技能）",
            lpc_expr="userp(this_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="learned[skill] 增加 amount；若超过 (skills[skill]+1)^2 则技能等级 +1",
            state_change="learned[skill] += amount; 条件性 skills[skill]++",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="学习惩罚：已学技能数 > spi(=30) 时 amount /= (sizeof(learned) - spi)",
            lpc_expr="if(sizeof(learned) > 30) amount /= sizeof(learned) - 30",
            scope="function",
        ),
        Invariant(
            description="技能升级阈值 = (当前等级+1)^2",
            lpc_expr="learned[skill] > (skills[skill]+1)^2 => skills[skill]++",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="学习惩罚计算（已学技能数 > 30 时）",
            lpc_call="if(sizeof(learned) > spi) amount /= sizeof(learned) - spi",
            target="amount（局部变量）",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="增加 learned[skill]",
            lpc_call="learned[skill] += amount",
            target="this_object().learned[skill]",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="条件性技能升级：learned > (level+1)^2 时 skills[skill]++，learned 清零",
            lpc_call="if(learned[skill] > (skills[skill]+1)^2) { skills[skill]++; learned[skill]=0; }",
            target="this_object().skills[skill] / learned[skill]",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="技能升级时通知玩家",
            lpc_call='tell_object(this_object(), HIC "你的「" + to_chinese(skill) + "」进步了！\\n" NOR)',
            target="this_object()",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.CALL_OUT,
            description="触发 skill_improved 回调",
            lpc_call="SKILL_D(skill)->skill_improved(this_object())",
            target="skill daemon",
        ),
    ],
    random_specs=[],
    notes="improve_skill 被 do_attack 步骤 7 调用。学习惩罚机制限制多技能角色的成长速度。"
    "spi 硬编码为 30（CLEANSWORD 修改）。",
)

# ---------------------------------------------------------------------------
# skill.c: skill_death_penalty()
# ---------------------------------------------------------------------------

_skill_death_penalty = FunctionSpec(
    signature=FunctionSignature(
        name="skill_death_penalty",
        params=[],
        return_type="int",
        lpc_file="feature/skill.c",
        line_range=(121, 147),
    ),
    preconditions=[
        Precondition(
            description="非 wizard 且有 skills mapping",
            lpc_expr="!wizardp(this_object()) && mapp(skills)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="所有技能等级下降（learned 不足时直接 skills--），skill_map 清除",
            state_change="skills[sk]--; skill_map = 0",
            kind="effect",
        ),
        Postcondition(
            description="返回 1 表示已执行",
            return_value="1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="技能等级降到 0 以下时删除该技能",
            lpc_expr="if(skills[sk[i]]<0) map_delete(skills, sk[i])",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="遍历所有技能，learned 不足时 skills--，否则 learned 扣减阈值",
            lpc_call="skills[sk[i]]--; learned[sk[i]] += (skills[sk[i]]+1)^2/2",
            target="this_object().skills / learned",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="清除技能映射 skill_map = 0",
            lpc_call="skill_map = 0",
            target="this_object().skill_map",
        ),
    ],
    random_specs=[],
    notes="skill_death_penalty 由 death_penalty() 调用。死亡后所有技能等级下降 1 级，skill_map 清空。",
)

# ---------------------------------------------------------------------------
# damage.c: heal_up()
# ---------------------------------------------------------------------------

_heal_up = FunctionSpec(
    signature=FunctionSignature(
        name="heal_up",
        params=[],
        return_type="int",
        lpc_file="feature/damage.c",
        line_range=(270, 331),
    ),
    preconditions=[
        Precondition(
            description="由 heart_beat 调用（tick=1s）",
            lpc_expr="heart_beat 调用链",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="water/food 递减；jing/qi/jingli/neili 按公式恢复；返回 update_flag",
            return_value="int（update_flag，>0 表示有状态变化）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="三层资源不变量：恢复后 qi <= eff_qi <= max_qi，jing <= eff_jing <= max_jing",
            lpc_expr="if(qi >= eff_qi) qi = eff_qi; if(eff_qi < max_qi) eff_qi++",
            scope="function",
        ),
        Invariant(
            description="战斗中恢复速率降低（jing: con/9 vs con/3; qi: con/9 vs con/3）",
            lpc_expr="is_fighting() ? con/9 : con/3",
            scope="function",
        ),
        Invariant(
            description="water/food 为 0 时 userp 不恢复（停止 jing/qi 恢复）",
            lpc_expr='if(my["water"]<1 && userp) return update_flag; if(my["food"]<1 && userp) return update_flag',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="water/food 递减 1",
            lpc_call='my["water"] -= 1; my["food"] -= 1',
            target="this_object().water / food",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="jing 恢复（战斗 con/9+max_jingli/30，非战斗 con/3+max_jingli/10），上限 eff_jing",
            lpc_call='my["jing"] += con/3 + max_jingli/10',
            target="this_object().jing",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="jing 达到 eff_jing 时 eff_jing 缓慢恢复（+1/tick）直到 max_jing",
            lpc_call='if(my["jing"] >= my["eff_jing"]) { my["jing"] = my["eff_jing"]; if(my["eff_jing"] < my["max_jing"]) my["eff_jing"]++; }',
            target="this_object().eff_jing",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="qi 恢复（战斗 con/9+max_neili/30，非战斗 con/3+max_neili/10），上限 eff_qi",
            lpc_call='my["qi"] += con/3 + max_neili/10',
            target="this_object().qi",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="qi 达到 eff_qi 时 eff_qi 缓慢恢复（+1/tick）直到 max_qi",
            lpc_call='if(my["qi"] >= my["eff_qi"]) { my["qi"] = my["eff_qi"]; if(my["eff_qi"] < my["max_qi"]) my["eff_qi"]++; }',
            target="this_object().eff_qi",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="jingli 恢复（战斗 (str+dex)/12，非战斗 (str+dex)/4），上限 max_jingli*2",
            lpc_call='my["jingli"] += (str+dex)/4',
            target="this_object().jingli",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="neili 恢复（战斗 force/6，非战斗 force/2），上限 max_neili",
            lpc_call='my["neili"] += query_skill("force",1)/2',
            target="this_object().neili",
        ),
    ],
    random_specs=[],
    notes="heal_up 是三层资源的恢复机制，每 tick 调用。战斗中恢复速率大幅降低。"
    "eff 层（eff_qi/eff_jing）缓慢自愈（+1/tick），是三层资源模型的核心恢复路径。",
)

# ---------------------------------------------------------------------------
# LayerSpec 组装
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="E",
    layer_name="战斗系统",
    lpc_files=[
        "adm/daemons/combatd.c",
        "feature/attack.c",
        "feature/damage.c",
        "feature/skill.c",
        "feature/condition.c",
    ],
    function_specs=[
        _skill_power,
        _do_attack,
        _damage_msg,
        _eff_status_msg,
        _report_status,
        _fight,
        _auto_fight,
        _death_penalty,
        _fight_ob,
        _kill_ob,
        _select_opponent,
        _attack,
        _reset_action,
        _receive_damage,
        _receive_wound,
        _receive_heal,
        _receive_curing,
        _die,
        _unconcious,
        _apply_condition,
        _update_condition,
        _clear_condition,
        _query_skill,
        _improve_skill,
        _skill_death_penalty,
        _heal_up,
    ],
    cross_layer_refs=[
        "set / query / add / set_temp / query_temp (层 B)",
        "move (层 B)",
        "receive_message / message_vision (层 B)",
        "save / restore (层 B)",
        "clean_up / destruct (层 A)",
        "living / heart_beat / set_heart_beat (层 A)",
        "command_hook / enable_player / disable_player (层 C)",
        "valid_leave / reset (层 D)",
        "make_corpse / DEATH_ROOM / start_death (层 F)",
        "CHAR_D / CHANNEL_D / RANK_D / SKILL_D (系统 daemon)",
    ],
    notes=(
        "combat 确定性范围 = combat-only（CLAUDE.md 架构不变量）：do_attack 中的 29+ 处 "
        "random() 是 combat 确定性的核心，全仿真确定性后置 M3 后。"
        "do_attack 七步副作用交织不可分离（dissent 3/01 子系统 5 核心关注点）："
        "SideEffect.order 字段记录 message_output 与 state_mutation 的严格交织顺序。"
        "三层资源不变量 0 <= qi <= eff_qi <= max_qi 是 damage.c 的核心契约。"
        "riposte 递归 / s_combatd 阵法合击 / perform/exert / condition 具体状态类型 / "
        "kungfu 门派武学 均后置。"
        "die()/death_penalty()/make_corpse 属层 F，但 do_attack 步骤 6 触发死亡的调用点"
        "在副作用里记录。"
    ),
)
