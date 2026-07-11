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
    Progression,
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
        spawn_room: str = "",
        item_registry: dict[str, str] | None = None,
    ) -> None:
        self.world = world
        self.room_entities = room_entities
        self.rules = rules
        self.quests = quests or {}
        self.seed_base = seed_base
        self.spawn_room = spawn_room
        self.item_registry = item_registry or {}
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
    msgs = [f"你向{direction}走去。"]
    msgs.extend(look(game, actor_id))
    return msgs


def kill(game: Game, actor_id: int, target_name: str, max_rounds: int = 30) -> list[str]:
    """战斗命令（S5a 多回合）：循环 resolve_attack 直到一方死亡或回合上限。

    每回合 player 攻 npc + npc 反击（若 NPC 存活）。NPC 死亡从房间移除 + 玩家加经验；
    玩家死亡传送回 spawn_room + 恢复 qi/jingli。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    messages: list[str] = [f"你向{target_name}发起了攻击！"]
    for _ in range(max_rounds):
        ctx = CombatContext(
            attacker=to_snapshot(world, actor_id),
            victim=to_snapshot(world, target_eid),
            seed=game.next_seed(),
        )
        result = resolve_attack(ctx)
        apply_effects(world, result.effects)
        messages.extend(result.messages)
        if _is_dead(world, target_eid):
            messages.append(f"{target_name}倒在地上，死了。")
            _handle_npc_death(world, target_eid, actor_id)
            break
        ctx = CombatContext(
            attacker=to_snapshot(world, target_eid),
            victim=to_snapshot(world, actor_id),
            seed=game.next_seed(),
        )
        result = resolve_attack(ctx)
        apply_effects(world, result.effects)
        messages.extend(result.messages)
        if _is_dead(world, actor_id):
            messages.append("你的眼前一黑，接著什么也不知道了....")
            _handle_player_death(world, game, actor_id)
            messages.append("慢慢地你终于又有了知觉....")
            break
    else:
        messages.append(f"战斗持续了{max_rounds}回合，双方暂时停手。")
    return messages


def _is_dead(world: World, eid: int) -> bool:
    vitals = world.get(eid, Vitals)
    return vitals is not None and vitals.qi <= 0


def _handle_npc_death(world: World, npc_eid: int, killer_id: int) -> None:
    """NPC 死亡：移除 Position（从房间消失）+ 击杀者加经验。"""
    world.remove(npc_eid, Position)
    prog = world.get(killer_id, Progression)
    if prog:
        prog.combat_exp += 50


def _handle_player_death(world: World, game: Game, player_id: int) -> None:
    """玩家死亡：传送回 spawn_room + 恢复 qi/jingli。"""
    pos = world.get(player_id, Position)
    if pos and game.spawn_room:
        pos.room_id = game.spawn_room
    vitals = world.get(player_id, Vitals)
    if vitals:
        vitals.qi = vitals.max_qi
        vitals.jingli = vitals.max_jingli


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


def give(game: Game, actor_id: int, target_name: str, item_query: str) -> list[str]:
    """给物品命令（S4 ADR-0006 + ADR-0007）。

    对齐 LPC ``accept_object(who, ob)``。``item_query`` 支持按 id 或中文名查找
    （对齐 LPC ``present``）。命中规则按 action 返回
    （set_flag=接受+设标记 / deny=拒绝 / allow=接受）；无匹配默认接受。
    接受时物品从 actor 物品栏移除（LPC 物品被 NPC 拿走）；set_flag 时设标记。
    若物品交付同时匹配 in_progress 任务的 give_item objective，则完成任务并发放 reward。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    inv = world.get(actor_id, Inventory)
    available = inv.items if inv else set()
    item_id = _resolve_item_id(game, item_query, available)
    if item_id is None:
        return [f"你没有「{item_query}」。"]
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
    item_name = _item_name(game, item_id)
    msgs: list[str] = (
        [result.message] if result.message else [f"你把{item_name}给了{target_name}。"]
    )
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
                prog = world.get(actor_id, Progression)
                if prog:
                    prog.combat_exp += exp
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


def _item_name(game: Game, item_id: str) -> str:
    """S5a：通过 item_registry 查物品中文名（无注册则回退 id）。"""
    return game.item_registry.get(item_id, item_id)


def _resolve_item_id(game: Game, item_query: str, available: set[str]) -> str | None:
    """S5a：按 id 或中文名在可用物品集中解析出 item_id。"""
    if item_query in available:
        return item_query
    for iid in available:
        if _item_name(game, iid) == item_query:
            return iid
    return None


def take(game: Game, actor_id: int, item_query: str) -> list[str]:
    """拾取命令（S5a）：从房间地面拿物品到玩家物品栏。

    支持按 id 或中文名查找（对齐 LPC ``present(arg, env)``）。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room = world.get(game.room_entities[pos.room_id], RoomComp)
    if not room:
        return [f"这里没有「{item_query}」。"]
    item_id = _resolve_item_id(game, item_query, room.items)
    if item_id is None:
        return [f"这里没有「{item_query}」。"]
    room.items.discard(item_id)
    inv = world.get(actor_id, Inventory)
    if inv is None:
        inv = Inventory()
        world.add(actor_id, inv)
    inv.items.add(item_id)
    return [f"你捡起了{_item_name(game, item_id)}。"]


def look(game: Game, actor_id: int) -> list[str]:
    """查看命令（S5a）：LPC 风格显示房间描述 + NPC(每行) + 物品 + 出口。"""
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room = world.get(game.room_entities[pos.room_id], RoomComp)
    if not room:
        return ["这里什么也没有。"]
    lines = [f"【{room.short}】", room.long]
    for eid in world.entities_in_room(pos.room_id):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player:
            id_str = ident.aliases[0] if ident.aliases else ident.prototype_id
            lines.append(f"  {ident.name}({id_str})")
    for item_id in sorted(room.items):
        lines.append(f"  {_item_name(game, item_id)}({item_id})")
    if room.exits:
        dirs = sorted(room.exits.keys())
        if len(dirs) == 1:
            lines.append(f"    这里唯一的出口是 {dirs[0]}。")
        else:
            lines.append(f"    这里明显的出口是 {'、'.join(dirs[:-1])} 和 {dirs[-1]}。")
    return lines


def inventory(game: Game, actor_id: int) -> list[str]:
    """物品栏命令（S5a）：显示玩家持有的物品（中文名(id) 格式）。"""
    world = game.world
    inv = world.get(actor_id, Inventory)
    items = inv.items if inv else set()
    if not items:
        return ["你身上没有任何物品。"]
    return [f"  {_item_name(game, iid)}({iid})" for iid in sorted(items)]


def hp(game: Game, actor_id: int) -> list[str]:
    """状态命令（S5a）：显示玩家气/精力/经验。"""
    world = game.world
    vitals = world.get(actor_id, Vitals)
    if not vitals:
        return ["你没有状态。"]
    prog = world.get(actor_id, Progression)
    return [
        f"气：{vitals.qi}/{vitals.max_qi}  精力：{vitals.jingli}/{vitals.max_jingli}"
        f"  经验：{prog.combat_exp if prog else 0}"
    ]
