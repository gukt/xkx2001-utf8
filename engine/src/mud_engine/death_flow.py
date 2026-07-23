"""玩家死亡流程 + NPC 击杀处理（M2-17 / M2-18 / spec C1）。

``apply_combat_result`` 在气血归零后调用 ``handle_vitals_depleted``：
有 ``PlayerSession`` → 昏迷/死亡状态机 + DeathPolicy；无 → NPC 消失/掉落/经验。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mud_engine.combat_system import clear_engagement, select_move
from mud_engine.components import (
    DEFAULT_UNCONSCIOUS_RECOVERY_TICKS,
    Container,
    Currency,
    Dead,
    Description,
    Engaged,
    Identity,
    NoDeathZone,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    SkillLevels,
    SkillProgress,
    Unconscious,
    Vitals,
)
from mud_engine.death import DeathState, next_death_state
from mud_engine.events import ON_TICK, TickContext, run_vetoable
from mud_engine.transfer import transfer

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World

Rng = random.Random

ON_BEFORE_DEATH = "on_before_death"
ON_DEATH = "on_death"
ON_REVIVE = "on_revive"

# 昏迷态至少禁止主动战斗与移动（to-tickets 决策 4 / US23）。
UNCONSCIOUS_BLOCKED_VERBS: frozenset[str] = frozenset(
    {
        "go",
        "attack",
        "kill",
        "flee",
        "ride",
        "unride",
        "practice",
        "learn",
        "get",
        "take",
        "drop",
        "give",
        "buy",
        "sell",
        "ask",
        "pay",
        "sleep",
        "join",
        "open",
        "close",
        "unlock",
        "knock",
        "say",
    }
)


@dataclass(frozen=True)
class DeathPolicy:
    """死亡惩罚/复活纯数据参数（题材包可声明，缺省给 MVP 默认）。"""

    penalty_ratio: float = 0.1
    revive_room_key: str = "huashan_village"
    drop_items: bool = True
    drop_currency: bool = True
    unconscious_recovery_ticks: int = DEFAULT_UNCONSCIOUS_RECOVERY_TICKS
    recovery_vitals_ratio: float = 0.2


@dataclass(frozen=True)
class LootTable:
    """NPC 战利品纯数据（YAML ``loot:``；未声明则死亡无掉落）。"""

    currency_min: int = 0
    currency_max: int = 0
    item_template_keys: tuple[str, ...] = ()
    kill_exp: int = 10


@dataclass(frozen=True)
class DeathContext:
    """死亡/复活事件上下文。"""

    entity_id: EntityId
    world: World
    death_room: EntityId | None = None
    killer_id: EntityId | None = None


def default_death_policy() -> DeathPolicy:
    return DeathPolicy()


def _world_death_policy(world: World) -> DeathPolicy:
    """取世界挂载的 DeathPolicy；未挂时回退默认。"""
    return world.death_policy if world.death_policy is not None else default_death_policy()


def parse_death_policy(raw: object | None) -> DeathPolicy:
    """解析顶层 ``death_policy:``；缺省 / 非法形状回退默认。"""
    if raw is None:
        return default_death_policy()
    if not isinstance(raw, dict):
        return default_death_policy()
    base = default_death_policy()
    revive = raw.get("revive_room", raw.get("revive_room_key", base.revive_room_key))
    return DeathPolicy(
        penalty_ratio=float(raw.get("penalty_ratio", base.penalty_ratio)),
        revive_room_key=str(revive),
        drop_items=bool(raw.get("drop_items", base.drop_items)),
        drop_currency=bool(raw.get("drop_currency", base.drop_currency)),
        unconscious_recovery_ticks=int(
            raw.get("unconscious_recovery_ticks", base.unconscious_recovery_ticks)
        ),
        recovery_vitals_ratio=float(
            raw.get("recovery_vitals_ratio", base.recovery_vitals_ratio)
        ),
    )


def parse_loot_table(raw: object | None) -> LootTable | None:
    """``loot: {currency: N|[lo,hi], items: [...], kill_exp: N}``；缺省 None。"""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    cur = raw.get("currency", 0)
    if isinstance(cur, (list, tuple)) and len(cur) >= 2:
        cmin, cmax = int(cur[0]), int(cur[1])
    else:
        cmin = cmax = int(cur or 0)
    items_raw = raw.get("items") or ()
    if not isinstance(items_raw, (list, tuple)):
        items_raw = ()
    kill_exp = int(raw.get("kill_exp", 10))
    return LootTable(
        currency_min=min(cmin, cmax),
        currency_max=max(cmin, cmax),
        item_template_keys=tuple(str(x) for x in items_raw),
        kill_exp=kill_exp,
    )


def current_death_state(world: World, entity: EntityId) -> DeathState:
    if world.has_component(entity, Dead):
        return DeathState.DEAD
    if world.has_component(entity, Unconscious):
        return DeathState.UNCONSCIOUS
    return DeathState.ALIVE


def handle_vitals_depleted(
    world: World,
    entity: EntityId,
    *,
    killer_id: EntityId | None = None,
    rng: Rng | None = None,
) -> None:
    """气血归零后的分流入口（玩家昏迷/死亡 vs NPC 消失）。"""
    vitals = world.get_component(entity, Vitals)
    if vitals is None or vitals.qi_current > 0:
        return
    if world.has_component(entity, PlayerSession):
        _handle_player_depleted(world, entity, killer_id=killer_id)
    else:
        _handle_npc_death(world, entity, killer_id=killer_id, rng=rng)


def _handle_player_depleted(
    world: World, player_id: EntityId, *, killer_id: EntityId | None
) -> None:
    pos = world.get_component(player_id, Position)
    if pos is None:
        return
    in_safe = world.has_component(pos.room, NoDeathZone)
    current = current_death_state(world, player_id)
    nxt = next_death_state(current, in_no_death_zone=in_safe, vitals_depleted=True)
    policy = _world_death_policy(world)
    if nxt is DeathState.UNCONSCIOUS:
        if not world.has_component(player_id, Unconscious):
            world.add_component(
                player_id,
                Unconscious(ticks_remaining=policy.unconscious_recovery_ticks),
            )
        if world.has_component(player_id, Engaged):
            clear_engagement(world, player_id, reason="unconscious")
        world.push_message(player_id, "你伤势过重，昏迷了过去。")
        return
    if nxt is DeathState.DEAD:
        _execute_player_death(world, player_id, death_room=pos.room, killer_id=killer_id)


def _execute_player_death(
    world: World,
    player_id: EntityId,
    *,
    death_room: EntityId,
    killer_id: EntityId | None,
) -> None:
    if not world.has_component(player_id, Dead):
        world.add_component(player_id, Dead())
    ctx = DeathContext(
        entity_id=player_id, world=world, death_room=death_room, killer_id=killer_id
    )
    denial = run_vetoable(world, ON_BEFORE_DEATH, ctx)
    if denial is not None:
        # 否决：去掉 Dead，保持昏迷（气血仍为 0）。
        if world.has_component(player_id, Dead):
            world.remove_component(player_id, Dead)
        if not world.has_component(player_id, Unconscious):
            deny_policy = _world_death_policy(world)
            world.add_component(
                player_id,
                Unconscious(ticks_remaining=deny_policy.unconscious_recovery_ticks),
            )
        world.push_message(player_id, denial)
        return

    policy = _world_death_policy(world)
    world.events.dispatch(ON_DEATH, ctx)

    if world.has_component(player_id, Engaged):
        clear_engagement(world, player_id, reason="death")

    if policy.drop_items:
        _drop_inventory_to_room(world, player_id, death_room)

    if policy.drop_currency:
        _apply_currency_penalty(world, player_id, policy.penalty_ratio)
    _apply_skill_exp_penalty(world, player_id, policy.penalty_ratio)

    if world.has_component(player_id, Dead):
        world.remove_component(player_id, Dead)
    if world.has_component(player_id, Unconscious):
        world.remove_component(player_id, Unconscious)

    revive_room = _resolve_revive_room(world, policy.revive_room_key)
    if revive_room is not None:
        world.require_component(player_id, Position).room = revive_room

    vitals = world.get_component(player_id, Vitals)
    if vitals is not None:
        vitals.qi_current = vitals.qi_max
        vitals.neili_current = vitals.neili_max
        vitals.jingli_current = vitals.jingli_max

    world.events.dispatch(
        ON_REVIVE,
        DeathContext(entity_id=player_id, world=world, death_room=death_room, killer_id=killer_id),
    )
    world.push_message(player_id, "你死而复生，回到了安全之地。")


def _resolve_revive_room(world: World, key: str) -> EntityId | None:
    room_ids: dict[str, EntityId] = getattr(world, "room_ids", {}) or {}
    if key in room_ids:
        return room_ids[key]
    # 缺省键不存在时：退回第一个房间（测试夹具可自建复活点）。
    if room_ids:
        return next(iter(room_ids.values()))
    return None


def _drop_inventory_to_room(world: World, player_id: EntityId, room: EntityId) -> None:
    bag = world.get_component(player_id, Container)
    if bag is None:
        return
    for item in list(bag.items):
        transfer(world, item, player_id, room, player_id=None)


def _apply_currency_penalty(world: World, player_id: EntityId, ratio: float) -> None:
    currency = world.get_component(player_id, Currency)
    if currency is None:
        return
    loss = int(currency.amount * ratio)
    currency.amount = max(0, currency.amount - loss)


def _apply_skill_exp_penalty(world: World, player_id: EntityId, ratio: float) -> None:
    skills = world.get_component(player_id, SkillLevels)
    if skills is None:
        return
    for sid, prog in list(skills.levels.items()):
        loss = int(prog.exp * ratio)
        skills.levels[sid] = SkillProgress(level=prog.level, exp=max(0, prog.exp - loss))


def _handle_npc_death(
    world: World,
    npc_id: EntityId,
    *,
    killer_id: EntityId | None,
    rng: Rng | None,
) -> None:
    if world.has_component(npc_id, Engaged):
        clear_engagement(world, npc_id, reason="death")

    pos = world.get_component(npc_id, Position)
    death_room = pos.room if pos is not None else None
    meta = world.get_component(npc_id, NpcSpawnMeta)
    template_key = meta.template_key if meta is not None else None
    loot = _loot_for_npc(world, npc_id, template_key)

    if death_room is not None and loot is not None:
        _grant_loot(world, loot, death_room=death_room, killer_id=killer_id, rng=rng)

    # 击杀经验：有 loot 用其 kill_exp；无 loot 仍给默认经验（票 18 / US26）。
    if killer_id is not None:
        exp_amount = loot.kill_exp if loot is not None else LootTable().kill_exp
        if exp_amount > 0:
            _grant_kill_exp(world, killer_id, exp_amount)

    # 从存活查询语义消失（destroy；respawn 靠下次 spawn_scan）。
    world.destroy_entity(npc_id)
    if killer_id is not None and world.has_component(killer_id, PlayerSession):
        world.push_message(killer_id, "你打倒了对手。")


def _loot_for_npc(
    world: World, npc_id: EntityId, template_key: str | None
) -> LootTable | None:
    if template_key:
        bp = world.spawners.get(template_key)
        if bp is not None:
            raw = bp.extras.get("loot")
            if isinstance(raw, LootTable):
                return raw
    ext = world.entity_extension_data(npc_id)
    return parse_loot_table(ext.get("loot"))


def _grant_loot(
    world: World,
    loot: LootTable,
    *,
    death_room: EntityId,
    killer_id: EntityId | None,
    rng: Rng | None,
) -> None:
    roll = rng if rng is not None else random.Random()
    if loot.currency_max > 0 and killer_id is not None:
        amount = roll.randint(loot.currency_min, loot.currency_max)
        if amount > 0:
            currency = world.get_component(killer_id, Currency)
            if currency is None:
                world.add_component(killer_id, Currency(amount=0))
                currency = world.require_component(killer_id, Currency)
            currency.amount += amount
    for key in loot.item_template_keys:
        _spawn_loot_item(world, key, death_room)


def _spawn_loot_item(world: World, template_key: str, room: EntityId) -> None:
    """按 item_templates 在地面生成一件掉落物（无模板则跳过）。"""
    from mud_engine.capabilities import CAPABILITIES

    raw = world.item_templates.get(template_key)
    if raw is None:
        return
    item = world.create_entity()
    name = str(raw.get("name", template_key))
    world.add_component(item, Identity(name=name, aliases=tuple(raw.get("aliases") or ())))
    world.add_component(
        item,
        Description(short=str(raw.get("short", name)), long=str(raw.get("long", ""))),
    )
    attached: dict[type, object] = {}
    scene_path = getattr(world, "scene_path", None) or Path(".")
    for spec in CAPABILITIES:
        component = spec.from_yaml(raw, f"loot '{template_key}'", scene_path, attached)
        if component is not None:
            world.add_component(item, component)
            attached[type(component)] = component
    floor = world.require_component(room, Container)
    floor.items.add(item)


def _grant_kill_exp(world: World, killer_id: EntityId, amount: int) -> None:
    """把击杀经验写入当前交战招式所属技能；无技能则写入第一个已学技能。"""
    skills = world.get_component(killer_id, SkillLevels)
    if skills is None or not skills.levels:
        return
    move = select_move(world, killer_id)
    sid = move.skill_id
    if sid is None or sid not in skills.levels:
        sid = next(iter(skills.levels))
    prog = skills.levels[sid]
    skills.levels[sid] = SkillProgress(level=prog.level, exp=prog.exp + amount)


def attach_unconscious_recovery(world: World) -> None:
    """挂载昏迷 tick 苏醒（幂等）。与 ``attach_ai_system`` / ``attach_ferries`` 同构。"""
    if _on_unconscious_tick not in world.events.handlers_for(ON_TICK):
        world.events.register(ON_TICK, _on_unconscious_tick)


def _on_unconscious_tick(context: TickContext) -> None:
    world = context.world
    policy = _world_death_policy(world)
    for entity in list(world.entities_with(Unconscious)):
        unc = world.require_component(entity, Unconscious)
        unc.ticks_remaining -= 1
        if unc.ticks_remaining > 0:
            continue
        world.remove_component(entity, Unconscious)
        vitals = world.get_component(entity, Vitals)
        if vitals is not None:
            vitals.qi_current = max(1, int(vitals.qi_max * policy.recovery_vitals_ratio))
        world.push_message(entity, "你悠悠转醒")


__all__ = [
    "DeathContext",
    "DeathPolicy",
    "LootTable",
    "ON_BEFORE_DEATH",
    "ON_DEATH",
    "ON_REVIVE",
    "UNCONSCIOUS_BLOCKED_VERBS",
    "attach_unconscious_recovery",
    "current_death_state",
    "default_death_policy",
    "handle_vitals_depleted",
    "parse_death_policy",
    "parse_loot_table",
]
