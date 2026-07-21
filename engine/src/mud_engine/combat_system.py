"""交战调度：Engaged + tick 自动回合 + 战斗事件点（M2-12 / spec A1）。

把 02 号票 ``resolve_attack`` 接入真实 ECS。``attach_combat_system`` 与
``attach_ai_system`` / ``attach_ferries`` 同构（幂等 + on_tick + 可注入 RNG）。
本票不处理气血归零后的死亡判定（17 号票）、SkillBehavior 真实副作用（16 号票）、
NPC 主动 aggro（19 号票，仅复用 ``try_engage``）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mud_engine.combat import (
    CombatContext,
    CombatMoveSnapshot,
    CombatRoundResult,
    attach_power_model,
    resolve_attack,
)
from mud_engine.components import (
    BaseAttributes,
    Engaged,
    Identity,
    SkillLevels,
    Vitals,
)
from mud_engine.events import ON_TICK, TickContext, run_vetoable
from mud_engine.skills import SKILLS, SkillData, SkillMove

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World

Rng = random.Random

ON_BEFORE_COMBAT_ROUND = "on_before_combat_round"
ON_COMBAT_ROUND = "on_combat_round"
ON_COMBAT_END = "on_combat_end"

# 无可用招式时的兜底（题材无关裸拳头；具体招式名仍来自 SkillData）。
_DEFAULT_MOVE = CombatMoveSnapshot(name="拳头", force=5, dodge=0, damage_type="blunt", damage=5)


@dataclass(frozen=True)
class CombatRoundContext:
    """战斗回合事件上下文（before 可否决；round 为结算后播报）。"""

    attacker_id: EntityId
    defender_id: EntityId
    world: World
    result: CombatRoundResult | None = None


@dataclass(frozen=True)
class CombatEndContext:
    """交战结束事件上下文。"""

    entity_a: EntityId
    entity_b: EntityId
    world: World
    reason: str  # "flee" / "disengage" / "invalid"


@dataclass
class CombatSystem:
    """战斗子系统运行时态（纯内存，不进存档）。"""

    rng: Rng
    flee_success_chance: float = 0.5


def attach_combat_system(
    world: World,
    *,
    rng: Rng | None = None,
    flee_success_chance: float = 0.5,
) -> None:
    """挂战斗 on_tick + 确保 PowerModel；幂等。"""
    attach_power_model(world)
    if _on_combat_tick not in world.events.handlers_for(ON_TICK):
        world.events.register(ON_TICK, _on_combat_tick)
    world.combat = CombatSystem(
        rng=rng if rng is not None else random.Random(),
        flee_success_chance=flee_success_chance,
    )


def try_engage(world: World, attacker: EntityId, defender: EntityId) -> str | None:
    """建立双向交战。成功返回 None；失败返回提示文案。

    供 ``attack`` 命令与未来 aggro（19 号票）共用。
    """
    if attacker == defender:
        return "你不能攻击自己。"
    if world.has_component(attacker, Engaged):
        current = world.require_component(attacker, Engaged).opponent
        if current == defender:
            return "你已经在与对方交战了。"
        return "你正在和其他人交战，分不开身。"
    if world.has_component(defender, Engaged):
        return "对方正在和别人交战。"
    if (
        world.get_component(attacker, Vitals) is None
        or world.get_component(defender, Vitals) is None
    ):
        return "对方无法交战。"
    world.add_component(attacker, Engaged(opponent=defender))
    world.add_component(defender, Engaged(opponent=attacker))
    return None


def clear_engagement(world: World, entity: EntityId, *, reason: str = "disengage") -> None:
    """清除实体及其对手的 Engaged，并分发 ``on_combat_end``。"""
    engaged = world.get_component(entity, Engaged)
    if engaged is None:
        return
    opponent = engaged.opponent
    world.remove_component(entity, Engaged)
    if world.has_component(opponent, Engaged):
        other = world.require_component(opponent, Engaged)
        if other.opponent == entity:
            world.remove_component(opponent, Engaged)
    world.events.dispatch(
        ON_COMBAT_END,
        CombatEndContext(entity_a=entity, entity_b=opponent, world=world, reason=reason),
    )


def resolve_one_strike(
    world: World,
    attacker: EntityId,
    defender: EntityId,
    *,
    rng: Rng,
) -> CombatRoundResult | None:
    """单次攻击：veto → resolve_attack → apply → 事件。失败/否决返回 None。"""
    ctx_before = CombatRoundContext(attacker_id=attacker, defender_id=defender, world=world)
    denial = run_vetoable(world, ON_BEFORE_COMBAT_ROUND, ctx_before)
    if denial is not None:
        world.pending_messages.append(denial)
        return None
    combat_ctx = build_combat_context(world, attacker, defender)
    if combat_ctx is None:
        return None
    power = world.power_model
    result = resolve_attack(combat_ctx, rng, power_model=power)
    apply_combat_result(world, defender, result, attacker=attacker)
    world.events.dispatch(
        ON_COMBAT_ROUND,
        CombatRoundContext(
            attacker_id=attacker,
            defender_id=defender,
            world=world,
            result=result,
        ),
    )
    _broadcast_round(world, attacker, defender, result)
    return result


def build_combat_context(
    world: World, attacker: EntityId, defender: EntityId
) -> CombatContext | None:
    """从真实组件构造 CombatContext；缺 Vitals 时返回 None。"""
    a_vitals = world.get_component(attacker, Vitals)
    d_vitals = world.get_component(defender, Vitals)
    if a_vitals is None or d_vitals is None:
        return None
    a_attrs = world.get_component(attacker, BaseAttributes) or BaseAttributes()
    d_attrs = world.get_component(defender, BaseAttributes) or BaseAttributes()
    move = select_move(world, attacker)
    return CombatContext(
        attacker_qi_current=a_vitals.qi_current,
        attacker_neili_current=a_vitals.neili_current,
        attacker_str=a_attrs.str_,
        attacker_con=a_attrs.con,
        attacker_dex=a_attrs.dex,
        attacker_int=a_attrs.int_,
        defender_qi_current=d_vitals.qi_current,
        defender_neili_current=d_vitals.neili_current,
        defender_str=d_attrs.str_,
        defender_con=d_attrs.con,
        defender_dex=d_attrs.dex,
        defender_int=d_attrs.int_,
        move=move,
    )


def select_move(world: World, attacker: EntityId) -> CombatMoveSnapshot:
    """从已学技能中选最高 force 且等级达标的招式；否则兜底拳头。"""
    skill_levels = world.get_component(attacker, SkillLevels)
    if skill_levels is None or not skill_levels.levels:
        return _DEFAULT_MOVE
    best: SkillMove | None = None
    best_skill_id: str | None = None
    for skill_id, progress in skill_levels.levels.items():
        data: SkillData | None = SKILLS.get(skill_id)
        if data is None:
            continue
        for move in data.moves:
            if progress.level < move.lvl:
                continue
            if best is None or move.force > best.force:
                best = move
                best_skill_id = skill_id
    if best is None:
        return _DEFAULT_MOVE
    return CombatMoveSnapshot(
        name=best.name,
        force=best.force,
        dodge=best.dodge,
        damage_type=best.damage_type,
        damage=best.damage,
        skill_id=best_skill_id,
    )


def apply_combat_result(
    world: World,
    defender: EntityId,
    result: CombatRoundResult,
    *,
    attacker: EntityId | None = None,
) -> None:
    """把伤害写回防御方 Vitals；气血归零时分流玩家/NPC 死亡流程（M2-17/18）。"""
    if result.damage <= 0:
        return
    vitals = world.get_component(defender, Vitals)
    if vitals is None:
        return
    vitals.qi_current = max(0, vitals.qi_current - result.damage)
    if vitals.qi_current <= 0:
        from mud_engine.death_flow import handle_vitals_depleted

        rng = getattr(getattr(world, "combat", None), "rng", None)
        handle_vitals_depleted(world, defender, killer_id=attacker, rng=rng)


def _on_combat_tick(context: TickContext) -> None:
    world = context.world
    combat = getattr(world, "combat", None)
    if combat is None:
        return
    processed: set[frozenset[EntityId]] = set()
    for entity in list(world.entities_with(Engaged)):
        engaged = world.get_component(entity, Engaged)
        if engaged is None:
            continue
        opponent = engaged.opponent
        if not world.has_component(opponent, Engaged):
            clear_engagement(world, entity, reason="invalid")
            continue
        other = world.require_component(opponent, Engaged)
        if other.opponent != entity:
            clear_engagement(world, entity, reason="invalid")
            continue
        pair = frozenset({entity, opponent})
        if pair in processed:
            continue
        processed.add(pair)
        # 每对双方各出手一次（unordered pair 只处理一次，避免双向重复）。
        resolve_one_strike(world, entity, opponent, rng=combat.rng)
        if world.has_component(entity, Engaged) and world.has_component(opponent, Engaged):
            resolve_one_strike(world, opponent, entity, rng=combat.rng)


def _broadcast_round(
    world: World,
    attacker: EntityId,
    defender: EntityId,
    result: CombatRoundResult,
) -> None:
    a_name = _name(world, attacker)
    d_name = _name(world, defender)
    frag = "；".join(result.message_fragments) if result.message_fragments else result.move_name
    d_vitals = world.get_component(defender, Vitals)
    qi_hint = ""
    if d_vitals is not None:
        qi_hint = f"（{d_name}气血 {d_vitals.qi_current}/{d_vitals.qi_max}）"
    world.pending_messages.append(f"{a_name}对{d_name}：{frag}{qi_hint}")


def _name(world: World, entity: EntityId) -> str:
    identity = world.get_component(entity, Identity)
    return identity.name if identity is not None else str(entity)


__all__ = [
    "ON_BEFORE_COMBAT_ROUND",
    "ON_COMBAT_END",
    "ON_COMBAT_ROUND",
    "CombatEndContext",
    "CombatRoundContext",
    "CombatSystem",
    "Rng",
    "apply_combat_result",
    "attach_combat_system",
    "build_combat_context",
    "clear_engagement",
    "resolve_one_strike",
    "select_move",
    "try_engage",
]
