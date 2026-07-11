"""``resolve_attack`` 纯函数：从 LPC ``combatd.c`` ``do_attack`` 七步提取。

输入 ``CombatContext`` 快照 + seed -> 输出 ``CombatRoundResult``。
所有副作用产出为 ``Effect``，按"文本与状态交织真实顺序"入账本，不 mutate
现场状态。确定性：同 seed + 同快照 -> 同输出（hypothesis 验证）。

T6（ADR-0023）补全 6 项简化台账：
1. hit_ob/hit_by mapping 分支：读 ``HitCallbackResult`` 做返回类型分发
   （message 入 LEDGER_MESSAGE，damage 修正入 KIND_DAMAGE，按规格 order 交织）。
2. riposte 递归：TYPE_REGULAR + damage<1 + victim guarding 时递归调
   ``resolve_attack``，子回合嵌入父回合 ledger（非独立账本），深度限制防死循环。
3. 武器类型：不在内核枚举，attack_skill/weapon_label 由题材数据声明。
4. skill_power 完整公式：level³/3 + jingli_bonus + str/dex 加成 + is_fighting
   折减 + 低技能经验补偿（LPC ``_skill_power`` invariants）。
5. combat_exp 防御折减：defense_factor 折半自然终止（每次循环消耗 rng.rand）。
6. 技能 action：从 SkillData 取值（快照字段），post_action 声明式副作用。

保持七步交织（CLAUDE.md 不变量）：message 与 effect 按规格 side_effects order
交织入 ledger，不得"先算后 apply"。
"""

from __future__ import annotations

from xkx.combat.context import (
    TYPE_QUICK,
    TYPE_REGULAR,
    CombatantSnapshot,
    CombatContext,
    HitCallbackResult,
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
    embed_subresult,
    msg,
)
from xkx.combat.rng import DeterministicRNG

# skill_power 用途（对应 LPC SKILL_USAGE_*；字符串形式向后兼容现有测试）
ATTACK = "attack"
DEFENSE = "defense"

# riposte 递归深度硬上限（防死循环，ADR-0023 决策 4 第 2 项）
# LPC 无显式限制但由 guarding temp 消耗自然终止；T6 加硬上限兜底
_RIPOSTE_MAX_DEPTH = 4


def skill_power(
    c: CombatantSnapshot,
    skill_id: str,
    mode: str,
    *,
    apply_parry_path: bool = False,
) -> int:
    """LPC ``skill_power`` 完整公式（T6 补全 ADR-0023 决策 4 第 4 项）。

    公式（规格 ``layer_e_combat.py`` ``_skill_power`` invariants）：
    - ``level = query_skill(skill) + apply 修正``（ATTACK 用 apply_attack，DEFENSE
      dodge 用 apply_dodge，DEFENSE parry 用 apply_parry）
    - ``power = (level^3) / 3``
    - ``jingli_bonus = 50 + jingli/(max_jingli+1)*50``，上限 150
    - ATTACK 用 str 加成，DEFENSE 用 dex 加成
    - ``is_fighting()`` 时 DEFENSE 额外乘 ``(100 + fight_dodge/10) / 100``
    - ``level < 1`` 时用 ``combat_exp/20 * (jingli_bonus/10)`` 经验补偿

    ``apply_parry_path``：DEFENSE 路径 parry 技能用 apply_parry（规格 order=14），
    默认 False（dodge 路径用 apply_dodge，order=8）。

    ``mode`` 接受 ATTACK/DEFENSE 字符串（向后兼容）或 SKILL_USAGE_* int。
    """
    is_attack = mode in (ATTACK, 1)
    if is_attack:
        apply_mod = c.apply_attack
        attr_bonus = c.str_ * 2
    else:
        apply_mod = c.apply_parry if apply_parry_path else c.apply_dodge
        attr_bonus = c.dex_ * 2

    level = c.skills.get(skill_id, 0) + apply_mod

    # jingli_bonus = 50 + jingli/(max_jingli+1)*50，上限 150（规格 invariant）
    max_jl = c.max_jingli + 1
    jingli_bonus = 50 + (c.jingli * 50 // max_jl) if max_jl > 0 else 50
    if jingli_bonus > 150:
        jingli_bonus = 150

    # 低技能经验补偿（level < 1 时，规格 postconditions[1]）
    if level < 1:
        return (c.combat_exp // 20) * (jingli_bonus // 10)

    power = (level**3) // 3

    # is_fighting 时 DEFENSE 额外乘 (100 + fight_dodge/10) / 100（规格 notes）
    if not is_attack and c.is_fighting:
        fight_factor = 100 + c.fight_dodge // 10
        power = power * fight_factor // 100

    return power + attr_bonus


def _render(
    template: str,
    attacker: CombatantSnapshot,
    victim: CombatantSnapshot,
    limb: str,
) -> str:
    """最小占位符替换（$N/$n/$w/$l）。

    完整代词求值（10 变量 + viewer 三元组）见子系统 9/13，T6 不做。
    $w 取 attacker.weapon_label（题材数据声明，见 ADR-0003）。
    """
    return (
        template.replace("$N", attacker.name)
        .replace("$n", victim.name)
        .replace("$w", attacker.weapon_label)
        .replace("$l", limb)
    )


def _apply_hit_callback(
    result: CombatRoundResult,
    cb: HitCallbackResult | None,
    target_id: int,
    damage_type: str,
) -> int:
    """hit_ob/hit_by 回调的返回类型分发（ADR-0023 决策 4 第 1 项）。

    内核只做返回类型分发（主题无关）：
    - ``message`` 非空 -> 入 ledger 为 LEDGER_MESSAGE（对应 string 返回）
    - ``damage_delta`` != 0 -> 入 ledger 为 KIND_DAMAGE 副作用（对应 mapping damage 键）
    - ``override`` 非 None -> 仅 hit_by 用，覆盖最终 damage（对应 int 返回）

    返回 damage_delta（hit_ob 叠加用）；override 由调用方单独读 cb.override 处理。
    保持交织：message 与 damage 按声明顺序入账本（先 message 后 damage，对齐规格
    side_effects order=23/25/26 的 result->damage 顺序）。
    """
    if cb is None:
        return 0
    if cb.message:
        msg(result, cb.message)
    if cb.damage_delta != 0:
        eff(result, KIND_DAMAGE, target_id, cb.damage_delta, damage_type)
    return cb.damage_delta


def resolve_attack(ctx: CombatContext) -> CombatRoundResult:
    """七步战斗管线（从 ``combatd.c`` ``do_attack`` 提取）。纯函数。"""
    rng = DeterministicRNG(ctx.seed)
    attacker = ctx.attacker
    victim = ctx.victim
    result = CombatRoundResult(result_code=RESULT_HIT)

    # (0) 取本回合招式技能（题材数据声明，见 ADR-0003）
    attack_skill = attacker.attack_skill

    # (1) 取 action + 拼招式描述（T6：从 SkillData 取值，决策 4 第 6 项）
    limb = rng.choice(ctx.limbs) or "身体"
    msg(result, _render(attacker.action_message, attacker, victim, limb))

    # (2) 算 AP / DP（T6：完整公式，决策 4 第 4 项）
    ap = skill_power(attacker, attack_skill, ATTACK)
    dp = skill_power(victim, "dodge", DEFENSE)
    # ap/dp >= 1（do_attack invariants[2]）
    ap = max(1, ap)
    dp = max(1, dp)

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
    pp = skill_power(
        victim, parry_skill, DEFENSE, apply_parry_path=(parry_skill == "parry")
    )
    pp = max(1, pp)
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
    # hit_ob 回调（T6：mapping 分支补全，决策 4 第 1 项；规格 order=23/25/26）
    # 先叠 S1 int 加成（向后兼容），再分发 HitCallbackResult
    damage_bonus = attacker.hit_ob_bonus
    damage_bonus += _apply_hit_callback(
        result, attacker.hit_ob, victim.entity_id, attacker.action_damage_type
    )
    damage += damage_bonus
    # combat_exp 防御折减循环（T6：defense_factor 折半自然终止，决策 4 第 5 项）
    # 规格 side_effects order=31：while(random(defense_factor) > me.combat_exp)
    # { damage -= damage/3; defense_factor /= 2; }
    defense_factor = victim.con_ * 10 + 100
    while defense_factor > 0 and damage > 0:
        if rng.rand(defense_factor) > attacker.combat_exp:
            damage -= damage // 3
            defense_factor //= 2
        else:
            break
    if damage < 0:
        damage = 0
    # hit_by 回调（T6：mapping 分支补全，决策 4 第 1 项；规格 order=32/33）
    # 先处理 S1 int 覆盖（向后兼容），再分发 HitCallbackResult
    if victim.hit_by_override is not None:
        damage = victim.hit_by_override
    if victim.hit_by is not None:
        delta = _apply_hit_callback(
            result, victim.hit_by, victim.entity_id, attacker.action_damage_type
        )
        # hit_by 的 damage_delta 是修正（叠加），override 是覆盖
        if victim.hit_by.override is not None:
            damage = victim.hit_by.override
        else:
            damage += delta
    result.damage = damage

    # (6) inflict：产出 DamageEffect + WoundEffect（交织顺序，规格 order=34/35/36）
    eff(result, KIND_DAMAGE, victim.entity_id, damage, attacker.action_damage_type)
    if damage > 0 and rng.chance(4):
        eff(result, KIND_WOUND, victim.entity_id, damage, attacker.action_damage_type)
    msg(result, f"{victim.name}受到{damage}点{attacker.action_damage_type}。")

    # (7) exp：双方条件 +exp/potential/improve_skill（规格 order=37/38/39）
    if rng.rand(attacker.jingli * 100 // (attacker.max_jingli + 1) + attacker.int_) > 30:
        eff(result, KIND_EXP, attacker.entity_id, 1)
    if rng.rand(victim.max_qi + victim.qi) < damage:
        eff(result, KIND_EXP, victim.entity_id, 1)
        eff(result, KIND_POTENTIAL, victim.entity_id, 1)
    eff(result, KIND_JINGLI, attacker.entity_id, -1)
    if attack_skill in attacker.skills:
        eff(result, KIND_SKILL_IMPROVE, attacker.entity_id, 1, attack_skill)

    # 后处理：post_action 声明式副作用（T6：决策 4 第 6 项；规格 order=47）
    if attacker.action_post_action_result is not None:
        msg(result, attacker.action_post_action_result)

    # riposte 检查（T6：递归补全，决策 4 第 2 项；规格 order=48/49）
    # 触发条件：TYPE_REGULAR + damage<1 + victim guarding，且未超深度上限
    if (
        ctx.attack_type == TYPE_REGULAR
        and damage < 1
        and victim.guarding
        and ctx.riposte_depth < _RIPOSTE_MAX_DEPTH
    ):
        result.riposte_triggered = True
        # riposte 子回合：victim 反击 attacker，TYPE_QUICK（规格 order=49）
        # 子回合 seed 由父回合 rng 当前状态派生（确定性：同 seed 链推进）
        sub_seed = rng.derive_seed()
        sub_ctx = CombatContext(
            attacker=victim.model_copy(update={"is_fighting": True}),
            victim=attacker.model_copy(update={"is_fighting": True}),
            seed=sub_seed,
            attack_type=TYPE_QUICK,
            limbs=ctx.limbs,
            riposte_depth=ctx.riposte_depth + 1,
        )
        sub_result = resolve_attack(sub_ctx)
        result.riposte_sub_result = sub_result
        # 子回合整体嵌入父回合 ledger（交织位置：父回合尾部，规格 order=49）
        embed_subresult(result, sub_result)

    return result
