"""``resolve_attack`` 纯函数：从 LPC ``combatd.c`` ``do_attack`` 七步提取。

输入 ``CombatContext`` 快照 + seed -> 输出 ``CombatRoundResult``。
所有副作用产出为 ``Effect``，按"文本与状态交织真实顺序"入账本，不 mutate
现场状态。确定性：同 seed + 同快照 -> 同输出（hypothesis 验证）。

S1 简化（见 ADR-0002）：
- dodge/parry/hit 三分支；riposte 仅标记不递归（后置）；
- hit_ob/hit_by 仅 int 加成/覆盖，mapping 分支后置；
- skill_power 用简化公式（真实 DamageFormula 三段式管线后置）；
- 武器到技能/标签的映射由题材数据声明（attack_skill/weapon_label），
  内核不解释武器名（见 ADR-0003）。
"""

from __future__ import annotations

from xkx.combat.context import (
    TYPE_QUICK,
    CombatantSnapshot,
    CombatContext,
)
from xkx.combat.result import (
    KIND_DAMAGE,
    KIND_EXP,
    KIND_JINGLI,
    KIND_POTENTIAL,
    KIND_SKILL_IMPROVE,
    KIND_WOUND,
    RESULT_DODGE,
    RESULT_HIT,
    RESULT_PARRY,
    CombatRoundResult,
    eff,
    msg,
)
from xkx.combat.rng import DeterministicRNG

ATTACK = "attack"
DEFENSE = "defense"


def skill_power(c: CombatantSnapshot, skill_id: str, mode: str) -> int:
    """简化 skill_power（LPC ``level³/3`` + 属性 + apply）。

    TODO(ADR-0002): 真实公式是 DamageFormula 三段式管线（基础幂 + 状态修饰链
    + 属性系数与封顶，见 01 子系统5），S1 用简化版。
    """
    level = c.skills.get(skill_id, 0)
    base = (level**3) // 3 if level > 0 else 0
    if mode == ATTACK:
        return base + c.apply_attack + c.str_ * 2
    return base + c.apply_dodge + c.dex_ * 2


def _render(
    template: str,
    attacker: CombatantSnapshot,
    victim: CombatantSnapshot,
    limb: str,
) -> str:
    """最小占位符替换（$N/$n/$w/$l）。

    完整代词求值（10 变量 + viewer 三元组）见子系统 9/13，S1 不做。
    $w 取 attacker.weapon_label（题材数据声明，见 ADR-0003）。
    """
    return (
        template.replace("$N", attacker.name)
        .replace("$n", victim.name)
        .replace("$w", attacker.weapon_label)
        .replace("$l", limb)
    )


def resolve_attack(ctx: CombatContext) -> CombatRoundResult:
    """七步战斗管线（从 ``combatd.c`` ``do_attack`` 提取）。纯函数。"""
    rng = DeterministicRNG(ctx.seed)
    attacker = ctx.attacker
    victim = ctx.victim
    result = CombatRoundResult(result_code=RESULT_HIT)

    # (0) 取本回合招式技能（题材数据声明，见 ADR-0003）
    attack_skill = attacker.attack_skill

    # (1) 取 action + 拼招式描述
    limb = rng.choice(ctx.limbs) or "身体"
    msg(result, _render(attacker.action_message, attacker, victim, limb))

    # (2) 算 AP / DP
    ap = skill_power(attacker, attack_skill, ATTACK)
    dp = skill_power(victim, "dodge", DEFENSE)

    # (3) dodge 判定：random(ap+dp) < dp
    if rng.rand(ap + dp) < dp:
        result.result_code = RESULT_DODGE
        msg(result, f"{victim.name}一个闪身，躲开了这一击。")
        if rng.rand(victim.jingli * 100 // (victim.max_jingli + 1) + victim.int_) > 50:
            eff(result, KIND_EXP, victim.entity_id, 1)
        if rng.rand(attacker.int_) > 15:
            eff(result, KIND_EXP, attacker.entity_id, 1)
        if rng.rand(attacker.combat_exp) >= rng.rand(victim.combat_exp) * 2:
            eff(result, KIND_JINGLI, victim.entity_id, -1)
        eff(result, KIND_JINGLI, attacker.entity_id, -1)
        return result

    # (4) parry 判定：random(ap+pp) < pp
    parry_skill = "parry" if "parry" in victim.skills else attack_skill
    pp = skill_power(victim, parry_skill, DEFENSE)
    if rng.rand(ap + pp) < pp:
        result.result_code = RESULT_PARRY
        msg(result, f"{victim.name}格挡住了这一击。")
        if rng.rand(victim.jingli * 100 // (victim.max_jingli + 1) + victim.int_) > 50:
            eff(result, KIND_EXP, victim.entity_id, 1)
            eff(result, KIND_POTENTIAL, victim.entity_id, 1)
        if rng.rand(attacker.combat_exp) >= rng.rand(victim.combat_exp) * 2:
            eff(result, KIND_JINGLI, victim.entity_id, -1)
        eff(result, KIND_JINGLI, attacker.entity_id, -1)
        return result

    # (5) hit：算伤害
    action_damage = attacker.action_damage
    damage = action_damage + rng.rand(action_damage) + attacker.str_ // 2
    if ctx.attack_type == TYPE_QUICK:
        damage //= 2
    # hit_ob 回调叠 damage_bonus（S1: 仅 int 加成）
    damage += attacker.hit_ob_bonus
    # combat_exp 防御折减循环（victim 防御系数）
    defense_factor = victim.con_ * 10 + 100
    for _ in range(5):  # 限 5 次防死循环
        if damage <= 0:
            break
        if rng.rand(defense_factor) > attacker.combat_exp:
            damage -= damage // 3
        else:
            break
    if damage < 0:
        damage = 0
    # hit_by 回调覆盖最终 damage（S1: 仅 int 覆盖）
    if victim.hit_by_override is not None:
        damage = victim.hit_by_override
    result.damage = damage

    # (6) inflict：产出 DamageEffect + WoundEffect（交织顺序）
    eff(result, KIND_DAMAGE, victim.entity_id, damage, attacker.action_damage_type)
    if damage > 0 and rng.chance(4):
        eff(result, KIND_WOUND, victim.entity_id, damage, attacker.action_damage_type)
    msg(result, f"{victim.name}受到{damage}点{attacker.action_damage_type}。")

    # (7) exp：双方条件 +exp/potential/improve_skill
    if rng.rand(attacker.jingli * 100 // (attacker.max_jingli + 1) + attacker.int_) > 30:
        eff(result, KIND_EXP, attacker.entity_id, 1)
    if rng.rand(victim.max_qi + victim.qi) < damage:
        eff(result, KIND_EXP, victim.entity_id, 1)
        eff(result, KIND_POTENTIAL, victim.entity_id, 1)
    eff(result, KIND_JINGLI, attacker.entity_id, -1)
    if attack_skill in attacker.skills:
        eff(result, KIND_SKILL_IMPROVE, attacker.entity_id, 1, attack_skill)

    # 尾部：riposte 标记（S1 不递归；combatd.c:766-779 后置）
    result.riposte_triggered = False
    return result
