"""命令管线最小版（S1）：``go``（移动 + valid_leave）+ ``kill``（resolve_attack）。

Command 仅覆盖玩家外部意图；System tick 派生变更不经 Command（02 Q3 裁决）。
S1 不实装 8 段中间件全链路（01 子系统4），仅保留 路由 -> valid_leave/战斗 执行。
"""

from __future__ import annotations

from xkx.combat.context import CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.dsl.layer1 import EvalContext, EventRule, evaluate
from xkx.runtime.components import Attributes, Identity, Position, RoomComp
from xkx.runtime.ecs import World
from xkx.runtime.world import apply_effects, to_snapshot


class Game:
    """运行时游戏状态：world + 房间索引 + 规则 + 战斗 seed 源。"""

    def __init__(
        self,
        world: World,
        room_entities: dict[str, int],
        rules: list[EventRule],
        seed_base: int = 0,
    ) -> None:
        self.world = world
        self.room_entities = room_entities
        self.rules = rules
        self.seed_base = seed_base
        self._combat_count = 0

    def next_seed(self) -> int:
        self._combat_count += 1
        return self.seed_base + self._combat_count


def _actor_attrs(world: World, eid: int) -> dict[str, int]:
    a = world.get(eid, Attributes)
    if not a:
        return {}
    return {"age": a.age, "str": a.str_, "dex": a.dex_, "int": a.int_, "con": a.con_}


def _npc_ids_in_room(world: World, room_id: str) -> set[str]:
    ids: set[str] = set()
    for eid in world.entities_in_room(room_id):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player and ident.prototype_id:
            ids.add(ident.prototype_id)
    return ids


def go(game: Game, actor_id: int, direction: str) -> list[str]:
    """移动命令：查 exits -> 求 valid_leave -> 移动。"""
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room = world.get(game.room_entities[pos.room_id], RoomComp)
    target = room.exits.get(direction) if room else None
    if not target:
        return [f"这里没有「{direction}」的出口。"]
    ctx = EvalContext(
        actor_attrs=_actor_attrs(world, actor_id),
        dir=direction,
        npc_ids_in_room=_npc_ids_in_room(world, pos.room_id),
    )
    allow, msg = evaluate(game.rules, ctx)
    if not allow:
        return [msg] if msg else ["你无法离开这里。"]
    pos.room_id = target
    return [f"你向{direction}走去。"]


def kill(game: Game, actor_id: int, target_name: str) -> list[str]:
    """战斗命令：找目标 -> resolve_attack -> apply effects。"""
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid: int | None = None
    for eid in world.entities_in_room(pos.room_id):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player and target_name in (ident.name, *ident.aliases):
            target_eid = eid
            break
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    ctx = CombatContext(
        attacker=to_snapshot(world, actor_id),
        victim=to_snapshot(world, target_eid),
        seed=game.next_seed(),
    )
    result = resolve_attack(ctx)
    apply_effects(world, result.effects)
    return [*result.messages, f"（本回合伤害：{result.damage}）"]
