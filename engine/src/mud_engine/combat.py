"""战斗结算核心：CombatContext 快照 + resolve_attack 七步管线 + PowerModel（M2-02 / ADR-0004）。

纯函数 seam：不读写 World，不依赖 tick/命令。调用方（12 号票）负责把
``CombatRoundResult`` apply 回真实组件。``hit_ob``/``hit_by``/``post_action``
三个钩子调用点本票留空占位（16 号票接入真实 SkillBehavior）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mud_engine.world import World

Rng = random.Random


@dataclass(frozen=True)
class CombatMoveSnapshot:
    """本回合选用的招式只读快照（裸数值；12 号票再从 SkillData 构造）。"""

    name: str
    force: int
    dodge: int
    damage_type: str = "blunt"
    damage: int | None = None  # 固定伤害；None 表示按 force/力量公式结算


@dataclass(frozen=True)
class CombatContext:
    """参战双方只读快照：气血/内力/属性/当前招式。不含任何活组件引用。"""

    attacker_qi_current: int
    attacker_neili_current: int
    attacker_str: int
    attacker_con: int
    attacker_dex: int
    attacker_int: int
    defender_qi_current: int
    defender_neili_current: int
    defender_str: int
    defender_con: int
    defender_dex: int
    defender_int: int
    move: CombatMoveSnapshot


@dataclass(frozen=True)
class CombatRoundResult:
    """单回合结算结构化结果（供 tick/命令层 apply + 播报）。"""

    hit: bool
    dodged: bool
    parried: bool
    damage: int
    fatal: bool
    move_name: str
    message_fragments: tuple[str, ...]


@runtime_checkable
class PowerModel(Protocol):
    """AP/DP/PP/伤害求值策略：题材包可整体替换（ADR-0004）。"""

    def attack_power(self, ctx: CombatContext) -> int: ...

    def defense_power(self, ctx: CombatContext) -> int: ...

    def parry_power(self, ctx: CombatContext) -> int: ...

    def base_damage(self, ctx: CombatContext) -> int: ...


@dataclass(frozen=True)
class DefaultWuxiaPowerModel:
    """默认武侠公式：自洽可测，不追求 LPC 还原（ADR-0001）。

    AP = force × (1 + str × str_factor)
    DP = defender_dex × dex_factor + move.dodge
    PP = DP（MVP 招架与闪避共用同一防御势，避免引入无题材包数据支撑的第二套系数）
    非固定伤害 = AP 同公式（force × (1 + str × str_factor)），下限 1
    """

    str_factor: float = 0.02
    dex_factor: float = 1.0

    def attack_power(self, ctx: CombatContext) -> int:
        raw = ctx.move.force * (1.0 + ctx.attacker_str * self.str_factor)
        return max(0, int(raw))

    def defense_power(self, ctx: CombatContext) -> int:
        raw = ctx.defender_dex * self.dex_factor + ctx.move.dodge
        return max(0, int(raw))

    def parry_power(self, ctx: CombatContext) -> int:
        return self.defense_power(ctx)

    def base_damage(self, ctx: CombatContext) -> int:
        """固定伤害招式用 ``move.damage``；否则与 AP 同力量修正公式。"""
        if ctx.move.damage is not None:
            return max(0, int(ctx.move.damage))
        return max(1, self.attack_power(ctx))


_DEFAULT_POWER_MODEL = DefaultWuxiaPowerModel()


def attach_power_model(world: World, power_model: PowerModel | None = None) -> None:
    """把 PowerModel 挂到 ``world.power_model``（纯内存，不进存档；与 attach_ai_system 同构）。

    幂等：重复调用覆盖为最新实例。``power_model is None`` 时挂默认武侠实现。
    """
    world.power_model = power_model if power_model is not None else _DEFAULT_POWER_MODEL


def register_power_model(world: World, power_model: PowerModel) -> None:
    """``attach_power_model`` 的别名（spec A2 用词）；行为相同。"""
    attach_power_model(world, power_model)


def resolve_attack(
    ctx: CombatContext,
    rng: Rng,
    *,
    power_model: PowerModel | None = None,
) -> CombatRoundResult:
    """七步战斗结算纯函数。

    顺序（ADR-0004 / spec A1）：选技能 → 取招式 → 算 AP/DP → dodge
    （``random(ap+dp) < dp``）→ parry（``random(ap+pp) < pp``）→ 算伤害
    （``hit_ob``/``hit_by`` 占位）→ inflict → exp+riposte（二者本 MVP 均为 no-op）。

    本票 CombatContext 已携带选定招式快照，"选技能/取招式"两步退化为读取
    ``ctx.move``（12 号票再从真实 SkillLevels + SKILLS 选型填入）。
    """
    model = power_model if power_model is not None else _DEFAULT_POWER_MODEL
    move = ctx.move  # 步骤 1–2：已由调用方选定

    ap = model.attack_power(ctx)  # 步骤 3
    dp = model.defense_power(ctx)
    pp = model.parry_power(ctx)

    # 步骤 4：闪避。``random(ap+dp) < dp``；合为 0 时视为不闪。
    if _roll_opposed(rng, ap, dp):
        return CombatRoundResult(
            hit=False,
            dodged=True,
            parried=False,
            damage=0,
            fatal=False,
            move_name=move.name,
            message_fragments=(f"{move.name}被闪避",),
        )

    # 步骤 5：招架。
    if _roll_opposed(rng, ap, pp):
        return CombatRoundResult(
            hit=False,
            dodged=False,
            parried=True,
            damage=0,
            fatal=False,
            move_name=move.name,
            message_fragments=(f"{move.name}被招架",),
        )

    # 步骤 6：算伤害（走注入的 PowerModel；钩子占位对结果无影响）。
    damage = model.base_damage(ctx)
    damage = _invoke_hit_ob(ctx, damage)
    _invoke_hit_by(ctx)

    damage = max(0, int(damage))

    # 步骤 7：inflict（纯函数只报告结果，不改 World）。
    remaining = ctx.defender_qi_current - damage
    fatal = remaining <= 0

    # 步骤 8：exp + riposte —— 二者本 MVP 均为 no-op（spec Out of Scope / 票 02）。
    _invoke_exp_gain(ctx)
    _invoke_riposte(ctx)
    _invoke_post_action(ctx)

    return CombatRoundResult(
        hit=True,
        dodged=False,
        parried=False,
        damage=damage,
        fatal=fatal,
        move_name=move.name,
        message_fragments=(f"{move.name}命中，造成 {damage} 点伤害",),
    )


def _roll_opposed(rng: Rng, attack: int, defense: int) -> bool:
    """``random(attack+defense) < defense`` → True 表示防御方成功（闪/架）。"""
    total = attack + defense
    if total <= 0 or defense <= 0:
        return False
    return rng.randrange(total) < defense


def _invoke_hit_ob(ctx: CombatContext, damage: int) -> int:
    """命中后钩子占位（16 号票接入 SkillBehavior.hit_ob）。"""
    return damage


def _invoke_hit_by(ctx: CombatContext) -> None:
    """被击中钩子占位（16 号票接入 SkillBehavior.hit_by）。"""
    return None


def _invoke_exp_gain(ctx: CombatContext) -> None:
    """经验结算占位（后续成长票接线；本 MVP no-op，保留七步调用点）。"""
    return None


def _invoke_riposte(ctx: CombatContext) -> None:
    """反击占位（spec Out of Scope：riposte 机制本 MVP no-op）。"""
    return None


def _invoke_post_action(ctx: CombatContext) -> None:
    """招式收尾钩子占位（16 号票接入 SkillBehavior.post_action）。"""
    return None


__all__ = [
    "CombatContext",
    "CombatMoveSnapshot",
    "CombatRoundResult",
    "DefaultWuxiaPowerModel",
    "PowerModel",
    "Rng",
    "attach_power_model",
    "register_power_model",
    "resolve_attack",
]
