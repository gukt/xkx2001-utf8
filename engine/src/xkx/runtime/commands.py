"""命令管线最小版（S1）：go / kill + ask / give（S4 ADR-0006）+ quest（S4 ADR-0007）。

Command 仅覆盖玩家外部意图；System tick 派生变更不经 Command（02 Q3 裁决）。
S1 不实装 8 段中间件全链路（01 子系统4），仅保留 路由 -> valid_leave/战斗/对话/物品/任务 执行。
"""

from __future__ import annotations

from xkx.combat.context import CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.dsl.layer1 import (
    EvalContext,
    EventRule,
    evaluate,
    evaluate_accept_object,
)
from xkx.runtime.components import (
    Attributes,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    QuestLog,
    RoomComp,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.world import apply_effects, to_snapshot


class Game:
    """运行时游戏状态：world + 房间索引 + 规则 + 任务 + 战斗 seed 源。"""

    def __init__(
        self,
        world: World,
        room_entities: dict[str, int],
        rules: list[EventRule],
        quests: dict[str, dict] | None = None,
        seed_base: int = 0,
    ) -> None:
        self.world = world
        self.room_entities = room_entities
        self.rules = rules
        self.quests = quests or {}
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


def _actor_family(world: World, eid: int) -> str:
    """S4 ADR-0005：actor 门派（LPC family/family_name -> family_eq 谓词）。"""
    a = world.get(eid, Attributes)
    return a.family if a else ""


def _actor_items(world: World, eid: int) -> set[str]:
    """S4 ADR-0005：actor 物品栏（LPC present(obj, me) -> has_item 谓词）。"""
    inv = world.get(eid, Inventory)
    return inv.items if inv else set()


def _actor_marks(world: World, eid: int) -> set[str]:
    """S4 ADR-0006：actor 临时标记（LPC set_temp("marks/X") -> has_flag 谓词）。"""
    marks = world.get(eid, Marks)
    return marks.flags if marks else set()


def _npc_ids_in_room(world: World, room_id: str) -> set[str]:
    ids: set[str] = set()
    for eid in world.entities_in_room(room_id):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player and ident.prototype_id:
            ids.add(ident.prototype_id)
    return ids


def _find_npc_in_room(world: World, room_id: str, name: str) -> int | None:
    """按名称/别名找房间内 NPC 实体。"""
    for eid in world.entities_in_room(room_id):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player and name in (ident.name, *ident.aliases):
            return eid
    return None


def _eval_ctx(world: World, actor_id: int, **extra):  # type: ignore[no-untyped-def]
    """构造 EvalContext（valid_leave / accept_object 共用基础上下文 + 事件特定字段）。"""
    return EvalContext(
        actor_attrs=_actor_attrs(world, actor_id),
        actor_flags=_actor_marks(world, actor_id),
        actor_family=_actor_family(world, actor_id),
        actor_items=_actor_items(world, actor_id),
        **extra,
    )


def _quest_status(world: World, actor_id: int, quest_id: str) -> str:
    """S4 ADR-0007：获取玩家某任务状态。"""
    log = world.get(actor_id, QuestLog)
    return log.statuses.get(quest_id, "not_started") if log else "not_started"


def _set_quest_status(world: World, actor_id: int, quest_id: str, status: str) -> None:
    """S4 ADR-0007：设置玩家某任务状态。"""
    log = world.get(actor_id, QuestLog)
    if log is None:
        log = QuestLog()
        world.add(actor_id, log)
    log.statuses[quest_id] = status


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
    ctx = _eval_ctx(
        world, actor_id, dir=direction, npc_ids_in_room=_npc_ids_in_room(world, pos.room_id)
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
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
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


def ask(game: Game, actor_id: int, target_name: str, topic: str) -> list[str]:
    """对话命令（S4 ADR-0006 + ADR-0007）。

    先检查 topic 是否是某 quest 的 trigger（任务触发话题优先）；否则查 NPC inquiry。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    target_ident = world.get(target_eid, Identity)
    target_pid = target_ident.prototype_id if target_ident else ""

    # S4 ADR-0007：quest trigger 优先于普通 inquiry
    for qid, q in game.quests.items():
        if q.get("giver") == target_pid and q.get("trigger") == topic:
            status = _quest_status(world, actor_id, qid)
            if status == "not_started":
                _set_quest_status(world, actor_id, qid, "in_progress")
                desc = q.get("description", "")
                return (
                    [f"你接下任务「{q['name']}」。{desc}"]
                    if desc
                    else [f"你接下任务「{q['name']}」。"]
                )
            if status == "in_progress":
                return [f"任务「{q['name']}」进行中。"]
            return [f"任务「{q['name']}」已完成。"]

    # 普通 inquiry
    behavior = world.get(target_eid, NpcBehavior)
    if not behavior or topic not in behavior.inquiry:
        return [f"{target_name}摇了摇头。"]
    return [behavior.inquiry[topic]]


def give(game: Game, actor_id: int, target_name: str, item_id: str) -> list[str]:
    """给物品命令（S4 ADR-0006 + ADR-0007）。

    对齐 LPC ``accept_object(who, ob)``。命中规则按 action 返回
    （set_flag=接受+设标记 / deny=拒绝 / allow=接受）；无匹配默认接受。
    接受时物品从 actor 物品栏移除（LPC 物品被 NPC 拿走）；set_flag 时设标记。
    若物品交付同时匹配 in_progress 任务的 give_item objective，则完成任务并发放 reward。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    inv = world.get(actor_id, Inventory)
    if not inv or item_id not in inv.items:
        return [f"你没有「{item_id}」。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    target_ident = world.get(target_eid, Identity)
    target_pid = target_ident.prototype_id if target_ident else ""
    ctx = _eval_ctx(
        world,
        actor_id,
        npc_id=target_pid,
        item_id=item_id,
    )
    result = evaluate_accept_object(game.rules, ctx)
    if not result.accepted:
        return [result.message] if result.message else [f"{target_name}不肯接受。"]
    # 接受：物品移出 actor 物品栏
    inv.items.discard(item_id)
    msgs: list[str] = [result.message] if result.message else [f"你把{item_id}给了{target_name}。"]
    # set_flag 副作用
    if result.set_flag:
        marks = world.get(actor_id, Marks)
        if marks is None:
            marks = Marks()
            world.add(actor_id, marks)
        marks.flags.add(result.set_flag)

    # S4 ADR-0007：检查并完成任务
    for qid, q in game.quests.items():
        if _quest_status(world, actor_id, qid) != "in_progress":
            continue
        obj = q.get("objective", {})
        if (
            obj.get("kind") == "give_item"
            and obj.get("npc_id") == target_pid
            and obj.get("item_id") == item_id
        ):
            reward = q.get("reward", {})
            exp = reward.get("exp", 0)
            if exp:
                vitals = world.get(actor_id, Vitals)
                if vitals:
                    vitals.combat_exp += exp
            flag = reward.get("flag", "")
            if flag:
                marks = world.get(actor_id, Marks)
                if marks is None:
                    marks = Marks()
                    world.add(actor_id, marks)
                marks.flags.add(flag)
            _set_quest_status(world, actor_id, qid, "completed")
            msg = reward.get("message", "")
            if msg:
                msgs.append(msg)
            msgs.append(f"任务「{q['name']}」完成。")
            break  # 一次 give 只完成一个任务

    return msgs


def quest(game: Game, actor_id: int, arg: str = "") -> list[str]:
    """任务查询命令（S4 ADR-0007）：quest / quest <id>。

    ``quest`` 列出所有任务状态；``quest <id>`` 查单个任务状态。
    """
    world = game.world
    log = world.get(actor_id, QuestLog)
    statuses = log.statuses if log else {}
    if arg:
        q = game.quests.get(arg)
        if not q:
            return [f"没有任务「{arg}」。"]
        status = statuses.get(arg, "not_started")
        return [f"「{q['name']}」：{status}"]
    if not game.quests:
        return ["当前没有可接任务。"]
    lines = []
    for qid, q in game.quests.items():
        status = statuses.get(qid, "not_started")
        lines.append(f"「{q['name']}」[{status}]：{q.get('description', '')}")
    return lines
