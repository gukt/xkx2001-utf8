"""命令管线 + 8 段中间件调度（阶段 1 Wave 2 T4，ADR-0020）。

Command 仅覆盖玩家外部意图；System tick 派生变更不经 Command（02 Q3 裁决）。

**阶段 1 Wave 2 T4 升级**（ADR-0020）：单段命令执行升级为 8 段中间件管线。
本模块保留 10 命令（go/kill/ask/give/quest/take/look/inventory/hp）的终端执行函数
（行为等价，e2e 测试不回归），并新增：

- ``COMMAND_REGISTRY``：verb -> adapter ``(game, ctx) -> list[str]``，adapter 从
  ActionContext 取参数调用原命令函数（原签名不变）。
- ``run_pipeline``：8 段管线调度器（段 0-7 顺序执行，Abort 短路）。
- ``dispatch``：高层入口，从原始命令字符串走完整 8 段管线。

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md)
[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md)
"""

from __future__ import annotations

import random
from typing import Any

from xkx.dsl.layer1 import (
    EvalContext,
    EventRule,
    evaluate,
    evaluate_accept_object,
    evaluate_ask,
)
from xkx.runtime.action_context import Abort, ActionContext, new_context
from xkx.runtime.auto_fight import FightType, auto_fight, initiate_combat
from xkx.runtime.capability import CapabilityToken, PermissionService
from xkx.runtime.components import (
    Attributes,
    CombatState,
    FamilyComp,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.conditions import apply_condition
from xkx.runtime.doors import close_door, knock_door, open_door
from xkx.runtime.ecs import World
from xkx.runtime.middleware.s0_flood_check import FloodState, flood_check
from xkx.runtime.middleware.s1_alias import AliasState, alias_resolve
from xkx.runtime.middleware.s2_permission import permission_check
from xkx.runtime.middleware.s3_find_command import find_command
from xkx.runtime.middleware.s4_direction import direction_shortcut
from xkx.runtime.middleware.s5_parse_args import parse_args
from xkx.runtime.middleware.s6_inject_context import inject_context
from xkx.runtime.middleware.s7_execute_audit import AuditLog, execute_audit
from xkx.runtime.privileged import PrivilegedActionLog
from xkx.runtime.query import query_skill
from xkx.runtime.skill import get_skill_data, improve_skill, is_busy


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
        item_registry: dict[str, dict] | None = None,
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


def _current_tick(game: Game) -> int:
    """M3-1 ADR-0032 决策 3：取当前 tick（world.current_tick 动态属性，Engine.tick 更新）。

    build_world 初始化为 0；Engine.tick 每次推进。time-gate 冷却判定时间源
    （对照 jiamu lama_wage 的 mud_age）。getattr 健壮处理未注入的测试 World。
    """
    return getattr(game.world, "current_tick", 0)


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


def _quest_current_step(world: World, actor_id: int, quest_id: str) -> int:
    """M3-1 ADR-0032 决策 3：获取多步任务当前步骤索引。"""
    log = world.get(actor_id, QuestLog)
    return log.current_step.get(quest_id, 0) if log else 0


def _set_quest_current_step(world: World, actor_id: int, quest_id: str, step: int) -> None:
    """M3-1 ADR-0032 决策 3：设置多步任务当前步骤索引。"""
    log = world.get(actor_id, QuestLog)
    if log is None:
        log = QuestLog()
        world.add(actor_id, log)
    log.current_step[quest_id] = step


def _quest_objectives(q: dict) -> list[dict]:
    """取任务 objectives list（M3-1；向后兼容旧 IR objective 单数）。"""
    objs = q.get("objectives") or []
    if objs:
        return objs
    old = q.get("objective")
    return [old] if old else []


def _advance_objective(
    game: Game,
    actor_id: int,
    kind: str,
    *,
    npc_id: str = "",
    room_id: str = "",
    item_id: str = "",
) -> list[str]:
    """推进匹配当前步骤的 in_progress 任务（M3-1 ADR-0032 决策 3）。

    检查所有 in_progress 任务的当前步骤 objective，kind + 字段匹配则 current_step++。
    全部步骤完成 -> ``_complete_quest`` 发奖。返回推进/完成产生的消息。一次动作只
    推进一个任务（与 S4 give「一次 give 只完成一个任务」一致）。
    """
    world = game.world
    msgs: list[str] = []
    for qid, q in game.quests.items():
        if _quest_status(world, actor_id, qid) != "in_progress":
            continue
        objectives = _quest_objectives(q)
        step = _quest_current_step(world, actor_id, qid)
        if step >= len(objectives):
            continue
        obj = objectives[step]
        if obj.get("kind") != kind:
            continue
        if kind == "give_item" and not (
            obj.get("npc_id") == npc_id and obj.get("item_id") == item_id
        ):
            continue
        if kind in ("kill_npc", "fight_win") and obj.get("npc_id") != npc_id:
            continue
        if kind == "reach_room" and obj.get("room_id") != room_id:
            continue
        # 匹配 -> 推进
        _set_quest_current_step(world, actor_id, qid, step + 1)
        if step + 1 >= len(objectives):
            msgs.extend(_complete_quest(game, actor_id, qid))
        else:
            msgs.append(f"任务「{q['name']}」完成一步，继续努力。")
        break
    return msgs


def _complete_quest(game: Game, actor_id: int, qid: str) -> list[str]:
    """完成任务发奖（S4 + M3-1 ADR-0032 决策 3 time_gate 可重复）。

    time_gate > 0：记 claimed_at = current_tick + 重置 not_started（可再接，ask
    冷却门控，对照 jiamu lama_wage）。time_gate == 0：设 completed（S4 一次性）。
    """
    world = game.world
    q = game.quests.get(qid, {})
    reward = q.get("reward", {})
    msgs: list[str] = []
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
    msg = reward.get("message", "")
    if msg:
        msgs.append(msg)
    time_gate = reward.get("time_gate", 0)
    if time_gate > 0:
        log = world.get(actor_id, QuestLog)
        if log is None:
            log = QuestLog()
            world.add(actor_id, log)
        log.claimed_at[qid] = _current_tick(game)
        log.statuses[qid] = "not_started"
        log.current_step[qid] = 0
        msgs.append(f"任务「{q['name']}」完成，{time_gate} tick 后可再次接取。")
    else:
        _set_quest_status(world, actor_id, qid, "completed")
        msgs.append(f"任务「{q['name']}」完成。")
    return msgs


def go(game: Game, actor_id: int, direction: str) -> list[str]:
    """移动命令：查 exits -> 求 valid_leave -> 移动。"""
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room = world.get(game.room_entities.get(pos.room_id), RoomComp)
    target = room.exits.get(direction) if room else None
    if not target:
        return [f"这里没有「{direction}」的出口。"]
    # C5 ADR-0042：门关着挡路（对照 LPC valid_leave doors status 检查）
    door = room.doors.get(direction) if room else None
    if door is not None and door.closed:
        if door.locked:
            return [f"{door.name}锁着，需要钥匙。"]
        return [f"{door.name}关着，也许敲一敲(knock)或打开(open)会开。"]
    ctx = _eval_ctx(
        world, actor_id, dir=direction, npc_ids_in_room=_npc_ids_in_room(world, pos.room_id)
    )
    allow, msg = evaluate(game.rules, ctx)
    if not allow:
        return [msg] if msg else ["你无法离开这里。"]
    pos.room_id = target
    msgs = [f"你向{direction}走去。"]
    msgs.extend(look(game, actor_id))
    # M3-1 ADR-0032 决策 3：go 移动触发 reach_room objective（对照 shanmen go north）
    msgs.extend(_advance_objective(game, actor_id, "reach_room", room_id=target))
    # B-2 ADR-0039 决策 4：room-enter 触发 aggressive NPC 主动攻击（对照 LPC init()）
    msgs.extend(_trigger_room_enter_fight(game, actor_id))
    return msgs


def _trigger_room_enter_fight(game: Game, actor_id: int) -> list[str]:
    """B-2 ADR-0039 决策 4 + ADR-0045：玩家进房间触发 NPC 主动攻击（对照 LPC init()）。

    遍历房间内所有 NPC，三触发优先级（对齐 LPC attack.c init() if-else 顺序）：
    1. hatred：player_id 在 npc.killer_ids（NPC 记住要杀的玩家）-> HATRED
    2. vendetta：npc.vendetta_mark 且 player 有 vendetta:<mark> flag -> VENDETTA
    3. aggressive：npc.attitude == "aggressive" -> AGGRESSIVE
    每个 NPC 只触发其一（elif 链）。auto_fight 内部 NPC vs NPC 跳过 + 5 防御检查 +
    on_start_fight handler 建敌对关系。若玩家进入战斗，_run_combat 推进。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return []
    # 只玩家进房间触发（对齐 LPC this_player() 是玩家）
    ident = world.get(actor_id, Identity)
    if ident is None or not ident.is_player:
        return []
    player_marks = world.get(actor_id, Marks)
    player_flags = player_marks.flags if player_marks else set()
    for npc_eid in list(world.entities_in_room(pos.room_id)):
        if npc_eid == actor_id:
            continue
        npc_ident = world.get(npc_eid, Identity)
        if npc_ident is None or npc_ident.is_player:
            continue
        behavior = world.get(npc_eid, NpcBehavior)
        if behavior is None:
            continue
        fight_type = _decide_room_enter_fight(world, npc_eid, actor_id, behavior, player_flags)
        if fight_type is not None:
            auto_fight(world, npc_eid, actor_id, fight_type)
    # 若玩家进入战斗，_run_combat 推进（CLI 同步，对齐 kill 命令 _run_combat）
    cs = world.get(actor_id, CombatState)
    if cs is not None and cs.is_fighting:
        msgs = ["你被攻击了！"]
        msgs.extend(_run_combat(game, actor_id))
        return msgs
    return []


def _decide_room_enter_fight(
    world: World,
    npc_eid: int,
    player_id: int,
    behavior: NpcBehavior,
    player_flags: set[str],
) -> FightType | None:
    """三触发优先级判定（B-2 ADR-0045，对照 LPC attack.c init() if-else）。

    hatred > vendetta > aggressive。返回 FightType 或 None（不触发）。
    """
    # 1. hatred：player 在 npc.killer_ids（对齐 LPC is_killing(ob->id)）
    npc_cs = world.get(npc_eid, CombatState)
    if npc_cs is not None and player_id in npc_cs.killer_ids:
        return FightType.HATRED
    # 2. vendetta：npc.vendetta_mark 且 player 有 vendetta:<mark> flag
    if behavior.vendetta_mark and f"vendetta:{behavior.vendetta_mark}" in player_flags:
        return FightType.VENDETTA
    # 3. aggressive：npc.attitude == "aggressive"
    if behavior.attitude == "aggressive":
        return FightType.AGGRESSIVE
    return None


def kill(game: Game, actor_id: int, target_name: str) -> list[str]:
    """战斗命令（ADR-0039 路径统一）：建立敌对关系，CombatBridge tick 驱动持续战斗。

    对齐 LPC kill.c：kill_ob -> fight_ob -> set_heart_beat(1) + 加入 enemy 数组，
    命令返回。后续攻击由 CombatBridge.tick 驱动（cli ``_auto_advance`` 调
    ``advance_combat`` 推进）。战斗结束判定（死亡）+ 死亡处理在 ``advance_combat``，
    不经 Command（CLAUDE.md 不变量：System tick 派生变更不经 Command）。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    _start_combat(world, actor_id, target_eid, to_death=True)
    messages = [f"你向{target_name}发起了攻击！"]
    # ADR-0039：CombatBridge tick 驱动战斗到结束（对齐 LPC heart_beat 持续）
    messages.extend(_run_combat(game, actor_id))
    return messages


def _handle_npc_death(world: World, npc_eid: int, killer_id: int) -> None:
    """NPC 死亡：移除 Position（从房间消失）+ 击杀者加经验 + vendetta 标记写入。

    B-2 ADR-0045：NPC 有 vendetta_mark -> 击杀者获 ``vendetta:<mark>`` flag（对照
    LPC combatd.c killer_reward 的 ``add("vendetta/"+vmark,1)``）。
    """
    world.remove(npc_eid, Position)
    prog = world.get(killer_id, Progression)
    if prog:
        prog.combat_exp += 50
    # B-2 ADR-0045：vendetta 标记写入（killer_reward）
    behavior = world.get(npc_eid, NpcBehavior)
    if behavior and behavior.vendetta_mark:
        marks = world.get(killer_id, Marks)
        if marks is None:
            marks = Marks()
            world.add(killer_id, marks)
        marks.flags.add(f"vendetta:{behavior.vendetta_mark}")


def _handle_player_death(
    world: World, game: Game, player_id: int, killer_id: int
) -> None:
    """玩家死亡：调 die() 走完整死亡轮回（M3-1 ADR-0032 决策 4）。

    die() 设 ghost=1 + move ``theme_config.death_room`` + enter_underworld 启动
    death_stage EffectComp（阴间 5 段剧情，GovernanceSystem tick 推进到还阳）。
    替代 S5a 简化版（传送 spawn_room + 恢复），接入阶段 2 死亡系统。还阳由
    GovernanceSystem 推进 death_stage 到 stage 4 调 reincarnate_at（恢复 +
    move revive_room），不在本函数内完成（CLI 自动推进 / e2e engine.tick）。
    B-2 ADR-0045：玩家死亡清所有 vendetta 标记（对照 LPC combatd.c death_penalty
    的 ``delete("vendetta")``）。
    """
    from xkx.runtime.death import die

    # B-2 ADR-0045：清 vendetta 标记（death_penalty）
    marks = world.get(player_id, Marks)
    if marks:
        marks.flags = {f for f in marks.flags if not f.startswith("vendetta:")}
    die(world, player_id, killer_id, tick=_current_tick(game))


def _qi_ratio(world: World, eid: int) -> int:
    """qi*100/max_qi 百分比（对照 darba.c:109 checking 判定）。"""
    vitals = world.get(eid, Vitals)
    if not vitals or vitals.max_qi <= 0:
        return 100
    return vitals.qi * 100 // vitals.max_qi


def _start_combat(
    world: World, pid: int, target_id: int, *, to_death: bool, win_threshold: int = 0
) -> None:
    """建立双向敌对关系（ADR-0039，对齐 LPC kill_ob/fight_ob + set_heart_beat(1)）。

    委托 ``auto_fight.initiate_combat``（B-2 ADR-0039 决策 4，逻辑下移供 NPC 主动
    攻击 handler 复用，避免循环依赖）。双方 CombatState.enemy_ids 互加 +
    is_fighting=True。to_death 区分 kill/fight，win_threshold 是 fight 模式 qi% 判赢阈值。
    """
    initiate_combat(world, pid, target_id, to_death=to_death, win_threshold=win_threshold)


def _end_combat(world: World, pid: int, target_id: int) -> None:
    """清双方敌对关系（ADR-0039，对齐 LPC remove_enemy + set_heart_beat(0)）。"""
    for a, b in ((pid, target_id), (target_id, pid)):
        cs = world.get(a, CombatState)
        if cs is None:
            continue
        cs.enemy_ids = [e for e in cs.enemy_ids if e != b]
        if not cs.enemy_ids:
            cs.is_fighting = False


def advance_combat(
    game: Game, pid: int, *, combat_round: int = 0
) -> tuple[list[str], bool]:
    """推进 1 回合战斗 + 战斗结束判定 + 死亡处理（ADR-0039 路径统一）。

    只调 CombatBridge 驱动战斗（``combat_round`` 做 seed，不调 HealSystem/不推进
    current_tick），对齐 LPC heart_beat 的 do_attack；heal_up 由命令后
    ``_advance_heartbeat`` 推进（战斗中不治疗，避免伤害被治疗抵消导致战斗过长）。
    返回 (messages, finished)；finished=True 表示战斗结束（NPC 死/玩家死/fight
    认输/无活跃战斗）。战斗派生变更经 System（CombatBridge），不经 Command。
    """
    world = game.world
    cs = world.get(pid, CombatState)
    if cs is None or not cs.is_fighting or not cs.enemy_ids:
        return [], True
    target_id = cs.enemy_ids[0]
    engine = getattr(game, "engine", None)
    if engine is not None:
        bridge = engine.get_system("CombatSystem")
        if bridge is not None:
            bridge.update(world, combat_round)
    # CombatBridge 产生的战斗消息（已收集到 pending_messages）
    messages = list(getattr(world, "pending_messages", []))
    if messages:
        world.pending_messages = []  # type: ignore[attr-defined]
    target_ident = world.get(target_id, Identity)
    target_name = target_ident.name if target_ident else "对手"
    target_pid = target_ident.prototype_id if target_ident else ""
    target_vitals = world.get(target_id, Vitals)
    player_vitals = world.get(pid, Vitals)
    finished = False
    if cs.to_death:
        # kill 模式：致死
        if target_vitals is not None and target_vitals.qi <= 0:
            messages.append(f"{target_name}倒在地上，死了。")
            _handle_npc_death(world, target_id, pid)
            messages.extend(
                _advance_objective(game, pid, "kill_npc", npc_id=target_pid)
            )
            _end_combat(world, pid, target_id)
            finished = True
        elif player_vitals is not None and player_vitals.qi <= 0:
            messages.append("你的眼前一黑，接著什么也不知道了....")
            _handle_player_death(world, game, pid, target_id)
            _end_combat(world, pid, target_id)
            finished = True
    else:
        # fight 模式：点到为止（qi 比例判赢，NPC 不死）
        if _qi_ratio(world, target_id) <= cs.win_threshold:
            if target_vitals and target_vitals.qi <= 0:
                target_vitals.qi = 1
            messages.append(f"{target_name}拱手认输：阁下武功了得，在下佩服。")
            messages.extend(
                _advance_objective(game, pid, "fight_win", npc_id=target_pid)
            )
            _end_combat(world, pid, target_id)
            finished = True
        elif _qi_ratio(world, pid) <= cs.win_threshold:
            messages.append("你气喘吁吁，不得不认输。")
            _end_combat(world, pid, target_id)
            finished = True
    return messages, finished


def _run_combat(game: Game, pid: int) -> list[str]:
    """推进战斗到结束（CombatBridge 驱动每回合），返回战斗消息。

    循环 ``advance_combat`` 直到战斗结束（死亡/认输/无活跃战斗）。CLI 同步模式
    下让战斗在命令内完成（对齐 LPC heart_beat 持续，压缩到同步推进）。战斗中
    不调 HealSystem（heal 由命令后 _advance_heartbeat 推进）。
    """
    messages: list[str] = []
    for round_no in range(60):
        m, finished = advance_combat(game, pid, combat_round=round_no)
        messages.extend(m)
        if finished:
            break
    return messages


def fight(game: Game, actor_id: int, target_name: str) -> list[str]:
    """切磋命令（ADR-0039 路径统一）：建立敌对关系（点到为止），CombatBridge tick 驱动。

    对照 cmds/std/fight.c（accept_fight + fight_ob 点到为止）。win_threshold 从匹配
    的 fight_win objective 取（默认 50%，对照 darba.c checking）。后续攻击由
    CombatBridge.tick 驱动（``advance_combat`` 推进），fight 模式 qi 比例判赢在
    ``advance_combat``（NPC 不死，qi clamp 到 1）。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}。"]
    target_ident = world.get(target_eid, Identity)
    target_pid = target_ident.prototype_id if target_ident else ""
    # 取匹配 fight_win objective 的 win_threshold（默认 50%，对照 darba.c:109）
    win_threshold = 50
    for qid, q in game.quests.items():
        if _quest_status(world, actor_id, qid) != "in_progress":
            continue
        objectives = _quest_objectives(q)
        step = _quest_current_step(world, actor_id, qid)
        if step < len(objectives):
            obj = objectives[step]
            if obj.get("kind") == "fight_win" and obj.get("npc_id") == target_pid:
                win_threshold = obj.get("win_threshold", 50)
                break
    _start_combat(
        world, actor_id, target_eid, to_death=False, win_threshold=win_threshold
    )
    messages = [f"你向{target_name}请教武艺，切磋开始！"]
    # ADR-0039：CombatBridge tick 驱动战斗到结束（fight 模式 qi 比例判赢）
    messages.extend(_run_combat(game, actor_id))
    return messages


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

    # S4 ADR-0007 + M3-1 ADR-0032 决策 3：quest trigger 优先于普通 inquiry
    for qid, q in game.quests.items():
        if q.get("giver") == target_pid and q.get("trigger") == topic:
            status = _quest_status(world, actor_id, qid)
            if status == "not_started":
                # M3-1 time-gate：可重复任务冷却门控（对照 jiamu lama_wage）
                reward = q.get("reward", {})
                time_gate = reward.get("time_gate", 0)
                if time_gate > 0:
                    log = world.get(actor_id, QuestLog)
                    last = log.claimed_at.get(qid) if log else None
                    if last is not None and _current_tick(game) - last < time_gate:
                        remain = time_gate - (_current_tick(game) - last)
                        return [
                            f"任务「{q['name']}」冷却中，约 {remain} tick 后可再次接取。"
                        ]
                _set_quest_status(world, actor_id, qid, "in_progress")
                _set_quest_current_step(world, actor_id, qid, 0)
                desc = q.get("description", "")
                return (
                    [f"你接下任务「{q['name']}」。{desc}"]
                    if desc
                    else [f"你接下任务「{q['name']}」。"]
                )
            if status == "in_progress":
                step = _quest_current_step(world, actor_id, qid)
                total = len(_quest_objectives(q)) or 1
                return [f"任务「{q['name']}」进行中（{step}/{total}）。"]
            return [f"任务「{q['name']}」已完成。"]

    # 普通 inquiry
    behavior = world.get(target_eid, NpcBehavior)
    if not behavior or topic not in behavior.inquiry:
        return [f"{target_name}摇了摇头。"]
    # C4 ADR-0040：求值 ask 规则执行 set_flag 副作用（对照 LPC inquiry 函数指针）
    ctx = _eval_ctx(world, actor_id, npc_id=target_pid, ask_topic=topic)
    ask_result = evaluate_ask(game.rules, ctx)
    if ask_result.set_flag:
        marks = world.get(actor_id, Marks)
        if marks is None:
            marks = Marks()
            world.add(actor_id, marks)
        marks.flags.add(ask_result.set_flag)
    # 消息：规则 message 非空则覆盖 inquiry，否则用 inquiry 字典文本
    message = ask_result.message if ask_result.message else behavior.inquiry[topic]
    return [message]


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
    # set_flag / clear_flag 副作用（S4 set_flag + C4 ADR-0040 clear_flag）
    if result.set_flag or result.clear_flag:
        marks = world.get(actor_id, Marks)
        if marks is None:
            marks = Marks()
            world.add(actor_id, marks)
        if result.set_flag:
            marks.flags.add(result.set_flag)
        if result.clear_flag:
            marks.flags.discard(result.clear_flag)
    # C4 ADR-0040：spawn_items 生成物品到房间（对照 LPC new(obj)->move）
    for spawn in result.spawn_items:
        room_eid = game.room_entities.get(spawn.room_id)
        if room_eid is None:
            continue
        spawn_room = world.get(room_eid, RoomComp)
        if spawn_room is not None:
            spawn_room.items.add(spawn.item_id)

    # S4 ADR-0007 + M3-1 ADR-0032 决策 3：give_item 推进当前步骤（多步 chain）
    msgs.extend(
        _advance_objective(
            game, actor_id, "give_item", npc_id=target_pid, item_id=item_id
        )
    )

    return msgs


def quest(game: Game, actor_id: int, arg: str = "") -> list[str]:
    """任务查询命令（S4 ADR-0007 + M3-1 多步进度）：quest / quest <id>。

    ``quest`` 列出所有任务状态（in_progress 显示 current_step/total）；``quest <id>``
    查单个任务状态。
    """
    world = game.world
    log = world.get(actor_id, QuestLog)
    statuses = log.statuses if log else {}
    if arg:
        q = game.quests.get(arg)
        if not q:
            return [f"没有任务「{arg}」。"]
        status = statuses.get(arg, "not_started")
        return [_quest_brief(q, arg, status, log)]
    if not game.quests:
        return ["当前没有可接任务。"]
    lines = []
    for qid, q in game.quests.items():
        status = statuses.get(qid, "not_started")
        lines.append(_quest_brief(q, qid, status, log))
    return lines


def _quest_brief(q: dict, qid: str, status: str, log: QuestLog | None) -> str:
    """任务简要描述（M3-1：in_progress 显示多步进度 current_step/total）。"""
    total = len(_quest_objectives(q)) or 1
    desc = q.get("description", "")
    if status == "in_progress" and log:
        step = log.current_step.get(qid, 0)
        return f"「{q['name']}」[{status} {step}/{total}]：{desc}"
    return f"「{q['name']}」[{status}]：{desc}"


def _item_name(game: Game, item_id: str) -> str:
    """S5a：通过 item_registry 查物品中文名（无注册则回退 id）。

    C4 ADR-0043：item_registry 存完整 item dict（id -> {name, aliases, consumable}）。
    """
    spec = game.item_registry.get(item_id)
    if isinstance(spec, dict):
        return spec.get("name", item_id)
    return spec or item_id  # 向后兼容旧 {id: name} str 结构


def _resolve_item_id(game: Game, item_query: str, available: set[str]) -> str | None:
    """按 id / 中文名 / 别名在可用物品集中解析出 item_id。

    S5a：id 或中文名。C4 ADR-0043：扩 aliases（对齐 ``_find_npc_in_room`` 别名解析，
    修复 drink/take/give 别名解析 gap；item_registry 存完整 dict）。
    """
    if item_query in available:
        return item_query
    for iid in available:
        if _item_name(game, iid) == item_query:
            return iid
        spec = game.item_registry.get(iid)
        if isinstance(spec, dict) and item_query in spec.get("aliases", []):
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
    room = world.get(game.room_entities.get(pos.room_id), RoomComp)
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


def drop(game: Game, actor_id: int, item_query: str) -> list[str]:
    """丢弃命令（C2）：从玩家物品栏丢物品到房间地面（take 的反向）。

    支持按 id 或中文名查找（对齐 take）。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    inv = world.get(actor_id, Inventory)
    if inv is None or not inv.items:
        return ["你没有物品可丢弃。"]
    item_id = _resolve_item_id(game, item_query, inv.items)
    if item_id is None:
        return [f"你没有「{item_query}」。"]
    inv.items.discard(item_id)
    room = world.get(game.room_entities.get(pos.room_id), RoomComp)
    if room is not None:
        room.items.add(item_id)
    return [f"你丢下{_item_name(game, item_id)}。"]


def drink(game: Game, actor_id: int, item_query: str) -> list[str]:
    """喝命令（C4 ADR-0043，对照 LPC buttertea.c do_drink）。

    通用 drink：resolve 物品 -> 查 consumable（全 0 拒"不能喝"）-> is_busy 拒 ->
    恢复 water/food/jing（jing clamp eff_jing）-> 从物品栏移除（set 语义，喝一次
    消失）。简化（后置）：remaining 多次饮用 / water 上限检查 / fighting
    start_busy(2) / value 清零。
    """
    world = game.world
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]
    inv = world.get(actor_id, Inventory)
    available = inv.items if inv else set()
    item_id = _resolve_item_id(game, item_query, available)
    if item_id is None:
        return [f"你没有「{item_query}」。"]
    spec = game.item_registry.get(item_id, {})
    drink_supply = spec.get("drink_supply", 0) if isinstance(spec, dict) else 0
    food_supply = spec.get("food_supply", 0) if isinstance(spec, dict) else 0
    jing_recover = spec.get("jing_recover", 0) if isinstance(spec, dict) else 0
    if not (drink_supply or food_supply or jing_recover):
        return ["这东西不能喝。"]
    vitals = world.get(actor_id, Vitals)
    if vitals is None:
        return ["你没有状态。"]
    if drink_supply:
        vitals.water += drink_supply
    if food_supply:
        vitals.food += food_supply
    if jing_recover and vitals.eff_jing > 0:
        vitals.jing = min(vitals.eff_jing, vitals.jing + jing_recover)
    inv.items.discard(item_id)  # set 语义，喝一次消失
    return [f"你喝下{_item_name(game, item_id)}，顿觉神清气爽。"]


def look(game: Game, actor_id: int) -> list[str]:
    """查看命令（S5a）：LPC 风格显示房间描述 + NPC(每行) + 物品 + 出口。"""
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room = world.get(game.room_entities.get(pos.room_id), RoomComp)
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
        # C5 ADR-0042：出口标注门状态（开/关）
        labels = [_dir_label(room, d) for d in dirs]
        if len(labels) == 1:
            lines.append(f"    这里唯一的出口是 {labels[0]}。")
        else:
            lines.append(f"    这里明显的出口是 {'、'.join(labels[:-1])} 和 {labels[-1]}。")
    return lines


def _dir_label(room: RoomComp, direction: str) -> str:
    """C5 ADR-0042：出口标签，标注门状态（如 west(铁门关)）。"""
    door = room.doors.get(direction)
    if door is None:
        return direction
    status = "关" if door.closed else "开"
    return f"{direction}({door.name}{status})"


def knock(game: Game, actor_id: int, direction: str) -> list[str]:
    """敲门命令（C5 ADR-0042，对照 LPC do_knock）。

    敲当前房间指定方向的门：开门（closed=False + 同步对面）+ 触发定时关门
    （door_close EffectComp，DoorSystem 到期关）。无门提示。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room_eid = game.room_entities.get(pos.room_id)
    if room_eid is None:
        return ["这里没有门。"]
    msg = knock_door(world, room_eid, direction, _current_tick(game))
    if msg is None:
        return ["这个方向没有门。"]
    return [msg]


def open(game: Game, actor_id: int, direction: str) -> list[str]:
    """开门命令（C5 ADR-0044，对照 LPC cmds/std/open.c）。

    标准开门：调 ``open_door`` 开门（**无定时关**，区别于 knock 的定时关语义）。
    locked 门提示需钥匙（钥匙系统后置，但 locked 检查就位）。无门提示。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room_eid = game.room_entities.get(pos.room_id)
    if room_eid is None:
        return ["这里没有门。"]
    room = world.get(room_eid, RoomComp)
    door = room.doors.get(direction) if room else None
    status = open_door(world, room_eid, direction)
    if status == "no_door":
        return ["这个方向没有门。"]
    if status == "already_open":
        return [f"{door.name}已经开着了。"] if door else ["门已经开着了。"]
    if status == "locked":
        return [f"{door.name}锁着，需要钥匙。"] if door else ["门锁着，需要钥匙。"]
    return [f"你将{door.name}打开。"] if door else ["你将门打开。"]


def close(game: Game, actor_id: int, direction: str) -> list[str]:
    """关门命令（C5 ADR-0044，对照 LPC cmds/std/close.c）。

    标准关门：调 ``close_door`` 关门 + 取消未到期的定时关 EffectComp。无门提示。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    room_eid = game.room_entities.get(pos.room_id)
    if room_eid is None:
        return ["这里没有门。"]
    room = world.get(room_eid, RoomComp)
    door = room.doors.get(direction) if room else None
    status = close_door(world, room_eid, direction)
    if status == "no_door":
        return ["这个方向没有门。"]
    if status == "already_closed":
        return [f"{door.name}已经关上了。"] if door else ["门已经关上了。"]
    return [f"你将{door.name}关上。"] if door else ["你将门关上。"]


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


# ============================================================================
# M3-1 ADR-0032 决策 1：拜师命令组（bai/kneel/recruit/betrayer）
# 对照 LPC cmds/skill/apprentice.c + feature/apprentice.c + gongcang.c
# ============================================================================


def _is_apprentice_of(world: World, player_eid: int, master_eid: int) -> bool:
    """玩家是否是 master 的徒弟（对照 apprentice.c:8 is_apprentice_of）。

    master_id + master_name 同时匹配 master 的 prototype_id + name。
    """
    player_family = world.get(player_eid, FamilyComp)
    master_ident = world.get(master_eid, Identity)
    if not player_family or not master_ident:
        return False
    return (
        player_family.master_id == master_ident.prototype_id
        and player_family.master_name == master_ident.name
    )


def _eval_apprentice_conditions(
    world: World, player_eid: int, conditions: dict, master_name: str
) -> tuple[bool, str]:
    """求值拜师入门条件（对照 LPC attempt_apprentice 钩子，声明式）。

    返回 (通过, 拒绝消息)。通过时拒绝消息为空。按 ADR-0032 决策 1 实施期
    细化：独立结构化条件模型（非层1 谓词，因 ADR-0016 护栏不引入 attr_ge）。
    """
    attrs = world.get(player_eid, Attributes)
    prog = world.get(player_eid, Progression)
    player_family = world.get(player_eid, FamilyComp)
    marks = world.get(player_eid, Marks)
    combat_exp = prog.combat_exp if prog else 0
    player_fn = player_family.family_name if player_family else ""
    # 1. reject_gender（对照 gongcang.c:66 拒女徒）
    reject_gender = conditions.get("reject_gender", "")
    if reject_gender and attrs and attrs.gender == reject_gender:
        return False, f"{master_name}说道：本门不收{reject_gender}徒，请回吧。"
    # 2. allow_families + other_family_max_combat_exp（对照 gongcang.c:75-81 外派高手）
    allow_families = conditions.get("allow_families", [])
    other_max_exp = conditions.get("other_family_max_combat_exp", 0)
    if (
        allow_families
        and player_fn
        and player_fn not in allow_families
        and other_max_exp
        and combat_exp >= other_max_exp
    ):
        return False, f"{master_name}说道：{player_fn}高手，本派可不敢收留！"
    # 3. min_combat_exp
    min_exp = conditions.get("min_combat_exp", 0)
    if min_exp and combat_exp < min_exp:
        return False, f"{master_name}说道：你的经验还浅，再历练历练吧。"
    # 4. min_skills
    min_skills = conditions.get("min_skills", {})
    if min_skills:
        skills = world.get(player_eid, Skills)
        for sk, lvl in min_skills.items():
            cur = skills.levels.get(sk, 0) if skills else 0
            if cur < lvl:
                return False, f"{master_name}说道：你的{sk}还不够纯熟。"
    # 5. require_flags（对照 darba 打赢设标记解锁拜师，决策 3）
    require_flags = conditions.get("require_flags", [])
    if require_flags:
        flags = marks.flags if marks else set()
        for f in require_flags:
            if f not in flags:
                return False, f"{master_name}说道：你还未证明自己的实力。"
    return True, ""


def _assign_apprentice(
    world: World, player_eid: int, family_name: str, generation: int, title: str
) -> None:
    """设玩家门派头衔（对照 apprentice.c:21-37 assign_apprentice）。

    LPC: sprintf("%s第%s代%s", family_name, chinese_number(generation), title)。
    greenfield 用阿拉伯数字（chinese_number 后置）。
    """
    title_comp = world.get(player_eid, TitleComp)
    if title_comp is None:
        title_comp = TitleComp()
        world.add(player_eid, title_comp)
    title_comp.title = f"{family_name}第{generation}代{title}"


def _recruit_apprentice(
    world: World, master_eid: int, player_eid: int, app_config: dict
) -> list[str]:
    """收徒核心逻辑（对照 apprentice.c:55 recruit_apprentice）。

    含叛师检查（玩家已有不同门派 -> betrayer+1，对照 apprentice.c:63-70）。
    写玩家 FamilyComp + assign_apprentice 设头衔 + 同步 Attributes.family。
    技能减半公式后置（LPC apprentice.c help：所有技能减半 + 评价降到零）。
    """
    master_ident = world.get(master_eid, Identity)
    family_name = app_config["family_name"]
    generation = app_config["generation"] + 1  # 玩家 = 师傅 generation + 1
    enter_title = "弟子"  # LPC recruit_apprentice -> assign_apprentice("弟子", 0)
    msgs: list[str] = []
    player_family = world.get(player_eid, FamilyComp)
    # 叛师检查（玩家已有不同门派）
    if player_family and player_family.family_name and player_family.family_name != family_name:
        player_family.betrayer += 1
        msgs.append(f"你决定背叛师门，改投入{family_name}门下！")
    if player_family is None:
        player_family = FamilyComp()
        world.add(player_eid, player_family)
    # 写玩家 FamilyComp（对照 recruit_apprentice 行 63-67）
    player_family.family_name = family_name
    player_family.generation = generation
    player_family.master_id = master_ident.prototype_id if master_ident else ""
    player_family.master_name = master_ident.name if master_ident else ""
    player_family.title = enter_title
    player_family.privs = 0
    # 同步 Attributes.family（兼容 family_eq 谓词 + FamilyBonus 分发）
    attrs = world.get(player_eid, Attributes)
    if attrs:
        attrs.family = family_name
    # assign_apprentice 设 TitleComp.title
    _assign_apprentice(world, player_eid, family_name, generation, enter_title)
    success_msg = app_config.get("success_message", "")
    if success_msg:
        msgs.append(success_msg)
    msgs.append(f"恭喜您成为{family_name}的第{generation}代弟子。")
    return msgs


def bai(game: Game, actor_id: int, target_name: str) -> list[str]:
    """拜师命令（M3-1 ADR-0032 决策 1，对照 cmds/skill/apprentice.c）。

    玩家拜 NPC 为师。流程：找 NPC -> 已是徒弟则请安 -> 辈分检查 ->
    求值 attempt_apprentice 入门条件 -> 通过则 recruit。pending 二次确认
    机制（LPC pending/recruit）简化为直接求值收徒（NPC 拜师路径）。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, target_name)
    if target_eid is None:
        return [f"这里没有「{target_name}」。"]
    target_ident = world.get(target_eid, Identity)
    target_disp = target_ident.name if target_ident else target_name
    target_family = world.get(target_eid, FamilyComp)
    # 师傅须有 family（create_family 设），无则不能收徒
    if target_family is None or not target_family.family_name:
        return [f"{target_disp}既不属于任何门派，也没有开山立派，不能拜师。"]
    # 已是徒弟 -> 请安（对照 apprentice.c:46）
    if _is_apprentice_of(world, actor_id, target_eid):
        return [f"你恭恭敬敬地向{target_disp}磕头请安，叫道：「师父！」"]
    # 辈分检查：同门派 + 师傅 generation >= 玩家 generation -> 不能拜平辈晚辈
    # （对照 apprentice.c:55-58，special_master 后置）
    player_family = world.get(actor_id, FamilyComp)
    if (
        player_family
        and player_family.family_name == target_family.family_name
        and target_family.generation >= player_family.generation
    ):
        return [f"{target_disp}的辈分不对，你不能拜平辈或晚辈为师。"]
    behavior = world.get(target_eid, NpcBehavior)
    app_config = behavior.apprentice_config if behavior else None
    if app_config is None:
        return [f"{target_disp}似乎不想收徒。"]
    # 求值 attempt_apprentice 入门条件
    ok, reject_msg = _eval_apprentice_conditions(
        world, actor_id, app_config.get("conditions", {}), target_disp
    )
    if not ok:
        return [reject_msg]
    # 通过 -> recruit（含叛师检查）
    msgs = _recruit_apprentice(world, target_eid, actor_id, app_config)
    # gongcang 剃度闭环（M3-1 子任务 5）：收徒后若师傅有 kneel 配置，设 pending
    # 标记让玩家可 kneel 剃度（对照 LPC attempt_apprentice 通过后 set pending/join_lama，
    # do_kneel 检查 pending 后剃度设 class）。samu 无 kneel 配置不触发。
    kneel_def = app_config.get("kneel") or {}
    require_flag = kneel_def.get("require_flag", "")
    if require_flag:
        marks = world.get(actor_id, Marks)
        if marks is None:
            marks = Marks()
            world.add(actor_id, marks)
        marks.flags.add(require_flag)
        msgs.append(f"你得到了{target_disp}的受戒许可，可以跪下(kneel)受戒了。")
    return msgs


def kneel(game: Game, actor_id: int) -> list[str]:
    """剃度命令（M3-1 ADR-0032 决策 1，对照 gongcang.c:114 do_kneel）。

    在房间内有 apprentice_config.kneel 的师傅 NPC 时触发剃度：检查
    require_flag（pending 标记）-> 设 class -> 清标记 -> 输出 message。
    gongcang 专属行为通过声明式配置驱动，源码无硬编码。
    """
    world = game.world
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    master_eid = None
    kneel_def = None
    for eid in world.entities_in_room(pos.room_id):
        ident = world.get(eid, Identity)
        if not ident or ident.is_player:
            continue
        behavior = world.get(eid, NpcBehavior)
        if behavior and behavior.apprentice_config:
            kd = behavior.apprentice_config.get("kneel")
            if kd:
                master_eid = eid
                kneel_def = kd
                break
    if master_eid is None or kneel_def is None:
        return ["你跪了下来，但似乎没人理会。"]
    # 检查 require_flag（pending 标记，对照 gongcang do_kneel:117）
    require_flag = kneel_def.get("require_flag", "")
    marks = world.get(actor_id, Marks)
    if require_flag and (not marks or require_flag not in marks.flags):
        return ["你还没有得到受戒的许可。"]
    # 设 class（对照 gongcang do_kneel:127 set("class","lama")）
    set_class = kneel_def.get("set_class", "")
    if set_class:
        title_comp = world.get(actor_id, TitleComp)
        if title_comp is None:
            title_comp = TitleComp()
            world.add(actor_id, title_comp)
        title_comp.char_class = set_class
    # 清除标记
    clear_flag = kneel_def.get("clear_flag", "") or require_flag
    if clear_flag and marks:
        marks.flags.discard(clear_flag)
    message = kneel_def.get("message", "")
    if message:
        # C6：$N/$n 占位符经 PronounContext 渲染（speaker=玩家/viewer=玩家/target=师傅）
        from xkx.runtime.pronoun import PronounService

        ctx = PronounService.build_context(world, actor_id, master_eid)
        return [PronounService.render(message, ctx)]
    return ["你双手合十，恭恭敬敬地跪了下来。"]


def recruit(game: Game, actor_id: int, target_name: str) -> list[str]:
    """收徒命令（M3-1 ADR-0032 决策 1，对照 cmds/skill/recruit.c）。

    NPC 收徒的 PrivilegedAction 入口（NPC AI force_me 调用，ADR-0020）。
    M3-1 NPC AI 后置，玩家路径返回提示；bai 命令内部已实现 recruit 逻辑
    （_recruit_apprentice）。NPC AI 落地后由 force_me 走完整 8 段管线。
    """
    return ["收徒需由师傅 NPC 发起（NPC AI 后置），玩家请用 bai 拜师。"]


def betrayer(game: Game, actor_id: int) -> list[str]:
    """叛师命令（M3-1 ADR-0032 决策 1，最小实现）。

    betrayer+1 + family 清空（FamilyComp 重置 + Attributes.family="" +
    TitleComp.title 清）。技能减半公式 + score=0 后置（LPC apprentice.c help：
    所有技能减半 + 评价降到零）。
    """
    world = game.world
    family = world.get(actor_id, FamilyComp)
    if family is None or not family.family_name:
        return ["你还没有加入任何门派。"]
    family.betrayer += 1
    family_name = family.family_name
    family.family_name = ""
    family.generation = 0
    family.master_id = ""
    family.master_name = ""
    family.title = ""
    family.privs = 0
    attrs = world.get(actor_id, Attributes)
    if attrs:
        attrs.family = ""
    title_comp = world.get(actor_id, TitleComp)
    if title_comp:
        title_comp.title = ""
    return [f"你背叛了{family_name}，从此沦为弃徒。"]


# ============================================================================
# M3-1 ADR-0032 决策 2：练功命令组（learn/practice/dazuo/tuna/enable）
# 对照 cmds/skill/learn.c / practice.c / dazuo.c / tuna.c / enable.c
# ============================================================================

# LPC enable.c:8-38 valid_types（技能种类集合）
_VALID_SKILL_TYPES: frozenset[str] = frozenset({
    "unarmed", "sword", "blade", "stick", "staff", "club", "force",
    "parry", "dodge", "magic", "whip", "hammer", "kick", "hook",
    "pike", "finger", "hand", "cuff", "claw", "strike",
})


def learn(
    game: Game, actor_id: int, teacher_name: str, skill_id: str, times: int = 1
) -> list[str]:
    """learn|xue 命令（M3-1 ADR-0032 决策 2，对照 cmds/skill/learn.c:16-151）。

    请教 NPC 学习技能。消耗 potential + jing，improve_skill(skill, gain)。
    combat_exp 门控：martial 技能 my_skill³/10 > combat_exp 阻止提升（仍消耗 jing）。
    gain = Σ random(int) for times 次（系统 RNG，非 combat 确定性范围）。

    简化（后置）：峨嵋减速 / spouse 检查 / recognize_apprentice 付费副作用 /
    prevent_learn 师傅侧门控后置（M3-1 雪山派无峨嵋/spouse，recognize 后置）。
    """
    world = game.world
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]
    if times < 1:
        return ["你要请教几次？"]
    pos = world.get(actor_id, Position)
    if not pos:
        return ["你没有位置。"]
    target_eid = _find_npc_in_room(world, pos.room_id, teacher_name)
    if target_eid is None:
        return [f"这里没有「{teacher_name}」。"]
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["临阵磨枪？来不及啦。"]
    prog = world.get(actor_id, Progression)
    if prog is None or prog.potential < times:
        return ["你的潜能不够。"]
    # 拜师/认可检查（对照 learn.c:52-56，spouse/recognize_apprentice 后置）
    if not _is_apprentice_of(world, actor_id, target_eid):
        return [f"你不是「{teacher_name}」的弟子，不能请教。"]
    master_skill = query_skill(world, target_eid, skill_id, raw=True)
    if master_skill <= 0:
        return [f"「{teacher_name}」似乎不会这个。"]
    my_skill = query_skill(world, actor_id, skill_id, raw=True)
    if my_skill >= master_skill:
        return ["你的程度已经不输师父了。"]
    skill_data = get_skill_data(skill_id)
    if not skill_data.valid_learn:
        return [f"你无法学习「{skill_id}」。"]
    attrs = world.get(actor_id, Attributes)
    int_val = attrs.int_ if attrs else 20
    # gin_cost = 150/int（对照 learn.c:95），初学加倍（learn.c:97-100）
    gin_cost = 150 // int_val if int_val > 0 else 150
    if not my_skill:
        gin_cost *= 2
    gin_cost = times * gin_cost * 3 // 2  # 玩家总消耗（learn.c:117）
    vitals = world.get(actor_id, Vitals)
    if vitals is None:
        return ["你没有状态。"]
    # combat_exp 门控：martial 且 my_skill³/10 > combat_exp -> 不提升（learn.c:120-122）
    blocked_by_exp = (
        skill_data.skill_type == "martial"
        and my_skill ** 3 // 10 > (prog.combat_exp if prog else 0)
    )
    if vitals.jing <= gin_cost:
        # jing 不足：不提升，仍消耗剩余 jing（learn.c:143-146 + :148 无条件消耗）
        vitals.jing = 0
        return ["你今天太累了，什么也没学到。"]
    # gain = Σ random(int) for times 次（learn.c:137-138，系统 RNG）
    gain = sum(random.randint(0, max(0, int_val - 1)) for _ in range(times))
    prog.potential -= times  # 扣潜能（learn.c:135）
    vitals.jing -= gin_cost  # 扣 jing（learn.c:148 receive_damage）
    msgs = [f"你向「{teacher_name}」请教了「{skill_id}」。"]
    if blocked_by_exp:
        msgs.append("你缺乏实战经验，无法领会这种武功。")
        return msgs
    if improve_skill(world, actor_id, skill_id, gain):
        msgs.append(f"你的「{skill_id}」进步了！")
    return msgs


def practice(
    game: Game, actor_id: int, skill_arg: str, times: int = 1
) -> list[str]:
    """practice|lian 命令（M3-1 ADR-0032 决策 2，对照 cmds/skill/practice.c:9-81）。

    练习特殊技能（须先 enable）。improve_skill(skillname, skill_basic/5+1, weak_mode)。
    weak_mode = skill_basic > skill ? 0 : 1（基础>特殊可升级，否则弱模式只攒点）。
    无 random（amount 固定）。practice_skill 武器检查用 SkillData stub（后置内容生产）。
    """
    world = game.world
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]
    if not skill_arg:
        return ["你要练什么？"]
    if skill_arg == "parry":
        return ["你不能通过练习招架来提高。"]
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["你已经在战斗中了。"]
    skills = world.get(actor_id, Skills)
    if skills is None:
        return ["你什么都不会。"]
    # 必须先 enable（query_skill_mapped，对照 practice.c:49-50）
    skillname = skills.skill_map.get(skill_arg, "")
    if not skillname:
        return [f"你还没有 enable 任何「{skill_arg}」方面的特殊技能。"]
    skill_basic = skills.levels.get(skill_arg, 0)  # 基础技能原始等级
    skill = skills.levels.get(skillname, 0)  # 特殊技能原始等级
    if skill < 1:
        return [f"你的「{skillname}」还不够熟练，无法练习。"]
    if skill_basic < 1:
        return [f"你的「{skill_arg}」基本功还不够，无法练习。"]
    # 基础门槛：skill_basic/2 > skill/3（对照 practice.c:59-60）
    if skill_basic // 2 <= skill // 3:
        return ["你的基本功火候未到，无法继续练习。"]
    skill_data = get_skill_data(skillname)
    if not skill_data.valid_learn:
        return [f"你无法练习「{skillname}」。"]
    # weak_mode + amount 循环外算（对照 practice.c:69-73，循环内不重查 skill）
    weak_mode = 0 if skill_basic > skill else 1
    amount = skill_basic // 5 + 1
    msgs = [f"你反复练习「{skillname}」。"]
    for _ in range(times):
        if not skill_data.practice_skill:
            msgs.append("你无法继续练习了。")
            break
        if improve_skill(world, actor_id, skillname, amount, weak_mode=weak_mode):
            msgs.append(f"你的「{skillname}」进步了！")
    return msgs


def dazuo(game: Game, actor_id: int, exercise_cost: int) -> list[str]:
    """dazuo|exercise 命令（M3-1 ADR-0032 决策 2，对照 cmds/skill/dazuo.c:12-72）。

    打坐练 neili/max_neili。须先 enable force。消耗 qi（exercise_cost），启动 busy
    EffectComp（exercise condition），每 tick neili 增长，结束判定 max_neili 提升。
    duration = ceil(exercise_cost / neili_gain) tick（neili_gain = 1+有效force/10）。
    """
    world = game.world
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["战斗中不能练内功，会走火入魔。"]
    skills = world.get(actor_id, Skills)
    if skills is None or not skills.skill_map.get("force"):
        return ["你必须先用 enable 选择你要用的内功心法。"]
    if exercise_cost < 10:
        return ["你的内功还没有达到那个境界！"]
    vitals = world.get(actor_id, Vitals)
    if vitals is None:
        return ["你没有状态。"]
    if vitals.qi < exercise_cost:
        return ["你现在的气太少了，无法产生内息运行全身经脉。"]
    if vitals.max_jing > 0 and vitals.jing * 100 // vitals.max_jing < 70:
        return ["你现在精不够，无法控制内息的流动！"]
    # neili 钳制 max_neili*2（对照 dazuo.c:59-62）
    if vitals.max_neili > 0 and vitals.neili > vitals.max_neili * 2:
        vitals.neili = vitals.max_neili * 2
    # duration = ceil(exercise_cost / neili_gain) tick
    force_level = query_skill(world, actor_id, "force")  # 有效 force（dazuo.c:77）
    neili_gain = 1 + force_level // 10
    if neili_gain < 1:
        neili_gain = 1
    duration = (exercise_cost + neili_gain - 1) // neili_gain  # ceil
    # 设 pending/exercise mark（对照 dazuo.c:66 set_temp("pending/exercise", 1)）
    marks = world.get(actor_id, Marks)
    if marks is None:
        marks = Marks()
        world.add(actor_id, marks)
    marks.flags.add("pending/exercise")
    apply_condition(world, actor_id, "exercise", duration, detail="force")
    return ["你盘膝坐下，开始修炼内力，一股内息开始在体内流动。"]


def tuna(game: Game, actor_id: int, respirate_cost: int) -> list[str]:
    """tuna|respirate 命令（M3-1 ADR-0032 决策 2，对照 cmds/skill/tuna.c:11-58）。

    吐纳炼 jingli/max_jingli/eff_jingli。消耗 jing（respirate_cost），启动 busy
    EffectComp（respirate condition），每 tick jingli 增长，结束判定 max_jingli/
    eff_jingli 提升。不要求 enable force（与 dazuo 不同，对照 tuna.c）。
    jingli_gain = 1+原始force/10（与 dazuo 有效 force 不对称，tuna.c:63）。
    """
    world = game.world
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["战斗中不能吐纳，会走火入魔。"]
    if respirate_cost < 10:
        return ["你的内功还没有达到那个境界！"]
    vitals = world.get(actor_id, Vitals)
    if vitals is None:
        return ["你没有状态。"]
    if vitals.jing < respirate_cost:
        return ["你现在的精太少了，无法产生精力运行全身经脉。"]
    if vitals.max_qi > 0 and vitals.qi * 100 // vitals.max_qi < 70:
        return ["你现在气不够，无法控制精力的流动！"]
    # jingli 钳制 max_jingli*2（对照 tuna 启动前）
    if vitals.max_jingli > 0 and vitals.jingli > vitals.max_jingli * 2:
        vitals.jingli = vitals.max_jingli * 2
    # duration = ceil(respirate_cost / jingli_gain)，gain 用原始 force（tuna.c:63）
    force_raw = query_skill(world, actor_id, "force", raw=True)
    jingli_gain = 1 + force_raw // 10
    if jingli_gain < 1:
        jingli_gain = 1
    duration = (respirate_cost + jingli_gain - 1) // jingli_gain
    marks = world.get(actor_id, Marks)
    if marks is None:
        marks = Marks()
        world.add(actor_id, marks)
    marks.flags.add("pending/respirate")
    apply_condition(world, actor_id, "respirate", duration, detail="force")
    return ["你盘膝坐下，开始吐故纳新，一股精力开始在体内流动。"]


def enable(
    game: Game, actor_id: int, skill_type: str = "", map_to: str = ""
) -> list[str]:
    """enable|jifa 命令（M3-1 ADR-0032 决策 2，对照 cmds/skill/enable.c:40-128）。

    无参：列当前 skill_map。``<type> <map_to>``：设置映射。map_to=="none" 取消。
    切换 force 清 neili（对照 enable.c:116-119）。valid_enable 用 SkillData stub。
    """
    world = game.world
    skills = world.get(actor_id, Skills)
    if skills is None:
        return ["你什么技能都不会。"]
    if not skill_type:
        # 无参：列 skill_map（对照 enable.c:48-69）
        msgs = ["你目前启用以下特殊技能："]
        has = False
        for st in _VALID_SKILL_TYPES:
            mapped = skills.skill_map.get(st)
            if mapped:
                eff = query_skill(world, actor_id, st)
                msgs.append(f"  {st}（有效等级 {eff}）：{mapped}")
                has = True
        if not has:
            msgs.append("  （暂无）")
        return msgs
    if skill_type not in _VALID_SKILL_TYPES:
        return [f"「{skill_type}」不是有效的技能种类。"]
    if not map_to:
        return ["指令格式：enable <技能种类> <技能名称>（如 enable sword 雪山剑法）"]
    if map_to == "none":
        skills.skill_map.pop(skill_type, None)
        return ["好吧，你以后只用基本功夫了。"]
    if map_to == skill_type:
        return [f"「{map_to}」是基础技能，不需要 enable。"]
    # 须会该特殊技能（raw 等级 > 0，对照 enable.c:96-97）
    if skills.levels.get(map_to, 0) <= 0:
        return [f"你不会「{map_to}」这种技能。"]
    # valid_enable 检查（SkillData stub，对照 enable.c:103-104；空列表=不限制）
    skill_data = get_skill_data(map_to)
    if skill_data.valid_enable and skill_type not in skill_data.valid_enable:
        return [f"「{map_to}」不能作为「{skill_type}」方面的特殊技能。"]
    skills.skill_map[skill_type] = map_to
    # 切换 force 清 neili（对照 enable.c:116-119）
    if skill_type == "force":
        vitals = world.get(actor_id, Vitals)
        if vitals:
            vitals.neili = 0
    return [f"你从现在起用「{map_to}」作为「{skill_type}」方面的特殊技能。"]


# ============================================================================
# 阶段 1 Wave 2 T4：8 段中间件管线集成（ADR-0020）
# ============================================================================


def _adapter_go(game: Game, ctx: ActionContext) -> list[str]:
    """go 命令适配器：从 ctx 取 direction（raw_args 或 parsed_args[0]）。"""
    direction = ctx.raw_args.strip()
    if not direction and ctx.parsed_args:
        direction = ctx.parsed_args[0]
    return go(game, ctx.actor, direction)


def _adapter_kill(game: Game, ctx: ActionContext) -> list[str]:
    """kill 命令适配器：target_name = parsed_args[0]（或 raw_args）。"""
    target_name = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return kill(game, ctx.actor, target_name)


def _adapter_fight(game: Game, ctx: ActionContext) -> list[str]:
    """fight 命令适配器（M3-1 ADR-0032 决策 3）：fight <NPC> 切磋。"""
    target_name = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return fight(game, ctx.actor, target_name)


def flee(game: Game, actor_id: int) -> list[str]:
    """逃跑命令（ADR-0039）：清敌对关系中断战斗（对齐 LPC remove_enemy）。

    玩家可在战斗 tick 间逃跑（对齐 LPC heart_beat 间的命令窗口）。基础实现：
    清双方 enemy_ids + is_fighting=False。完整 flee/surrender 语义后置。
    """
    world = game.world
    cs = world.get(actor_id, CombatState)
    if cs is None or not cs.is_fighting or not cs.enemy_ids:
        return ["你没有在战斗中。"]
    for target_id in list(cs.enemy_ids):
        _end_combat(world, actor_id, target_id)
    return ["你转身逃走了。"]


def _adapter_flee(game: Game, ctx: ActionContext) -> list[str]:
    """flee 命令适配器：逃跑中断战斗。"""
    return flee(game, ctx.actor)


def _adapter_ask(game: Game, ctx: ActionContext) -> list[str]:
    """ask 命令适配器：ask <NPC> about <话题> 或 ask <NPC> <话题>。

    对齐 cli.parse_and_run：优先按 about 拆分，否则首个 token 为 NPC，其余为话题。
    """
    args = ctx.parsed_args
    if not args:
        return ["如：ask 葛伦布 about 还愿"]
    if "about" in args:
        idx = args.index("about")
        npc = " ".join(args[:idx])
        topic = " ".join(args[idx + 1 :])
    elif len(args) >= 2:
        npc, topic = args[0], " ".join(args[1:])
    else:
        return ["如：ask 葛伦布 about 还愿"]
    return ask(game, ctx.actor, npc, topic)


def _adapter_give(game: Game, ctx: ActionContext) -> list[str]:
    """give 命令适配器：give <NPC> <物品>（最后一个 token 为物品）。"""
    args = ctx.parsed_args
    if len(args) < 2:
        return ["如：give 葛伦布 suyou_guan"]
    npc = " ".join(args[:-1])
    item = args[-1]
    return give(game, ctx.actor, npc, item)


def _adapter_quest(game: Game, ctx: ActionContext) -> list[str]:
    """quest 命令适配器：quest 或 quest <id>。"""
    arg = ctx.raw_args.strip()
    return quest(game, ctx.actor, arg)


def _adapter_take(game: Game, ctx: ActionContext) -> list[str]:
    """take 命令适配器：take <物品>。"""
    item_query = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return take(game, ctx.actor, item_query)


def _adapter_get(game: Game, ctx: ActionContext) -> list[str]:
    """get 命令适配器（take 别名）。"""
    item_query = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return take(game, ctx.actor, item_query)


def _adapter_drop(game: Game, ctx: ActionContext) -> list[str]:
    """drop 命令适配器（C2）：drop <物品>。"""
    item_query = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return drop(game, ctx.actor, item_query)


def _adapter_drink(game: Game, ctx: ActionContext) -> list[str]:
    """drink 命令适配器（C4 ADR-0043）：drink <物品>。"""
    item_query = ctx.parsed_args[0] if ctx.parsed_args else ctx.raw_args.strip()
    return drink(game, ctx.actor, item_query)


def _adapter_knock(game: Game, ctx: ActionContext) -> list[str]:
    """knock 命令适配器（C5 ADR-0042）：knock <方向>。"""
    direction = ctx.raw_args.strip()
    if not direction and ctx.parsed_args:
        direction = ctx.parsed_args[0]
    return knock(game, ctx.actor, direction)


def _adapter_open(game: Game, ctx: ActionContext) -> list[str]:
    """open 命令适配器（C5 ADR-0044）：open <方向>。"""
    direction = ctx.raw_args.strip()
    if not direction and ctx.parsed_args:
        direction = ctx.parsed_args[0]
    return open(game, ctx.actor, direction)


def _adapter_close(game: Game, ctx: ActionContext) -> list[str]:
    """close 命令适配器（C5 ADR-0044）：close <方向>。"""
    direction = ctx.raw_args.strip()
    if not direction and ctx.parsed_args:
        direction = ctx.parsed_args[0]
    return close(game, ctx.actor, direction)


def _adapter_look(game: Game, ctx: ActionContext) -> list[str]:
    """look 命令适配器（无参，查看当前房间）。"""
    return look(game, ctx.actor)


def _adapter_inventory(game: Game, ctx: ActionContext) -> list[str]:
    """inventory 命令适配器（无参）。"""
    return inventory(game, ctx.actor)


def _adapter_hp(game: Game, ctx: ActionContext) -> list[str]:
    """hp 命令适配器（无参）。"""
    return hp(game, ctx.actor)


def _adapter_bai(game: Game, ctx: ActionContext) -> list[str]:
    """bai 命令适配器：bai <NPC>（NPC 名可含空格，取 raw_args）。"""
    target_name = ctx.raw_args.strip()
    if not target_name:
        return ["如：bai 贡藏"]
    return bai(game, ctx.actor, target_name)


def _adapter_kneel(game: Game, ctx: ActionContext) -> list[str]:
    """kneel 命令适配器（无参，剃度当前房间师傅）。"""
    return kneel(game, ctx.actor)


def _adapter_recruit(game: Game, ctx: ActionContext) -> list[str]:
    """recruit 命令适配器：recruit <player>（PrivilegedAction，玩家路径提示）。"""
    target_name = ctx.raw_args.strip()
    if not target_name:
        return ["如：recruit 玩家名"]
    return recruit(game, ctx.actor, target_name)


def _adapter_betrayer(game: Game, ctx: ActionContext) -> list[str]:
    """betrayer 命令适配器（无参，叛师）。"""
    return betrayer(game, ctx.actor)


def _adapter_learn(game: Game, ctx: ActionContext) -> list[str]:
    """learn|xue 命令适配器：learn <师傅> <技能> [次数]。"""
    args = ctx.raw_args.strip().split()
    if len(args) < 2:
        return ["指令格式：learn|xue <师傅> <技能> [次数]"]
    times = 1
    if len(args) >= 3:
        try:
            times = int(args[2])
        except ValueError:
            return ["请教次数必须是数字。"]
    return learn(game, ctx.actor, args[0], args[1], times)


def _adapter_practice(game: Game, ctx: ActionContext) -> list[str]:
    """practice|lian 命令适配器：practice <技能> [次数]。"""
    args = ctx.raw_args.strip().split()
    if not args or not args[0]:
        return ["指令格式：practice|lian <技能> [次数]"]
    times = 1
    if len(args) >= 2:
        try:
            times = int(args[1])
        except ValueError:
            return ["练习次数必须是数字。"]
    return practice(game, ctx.actor, args[0], times)


def _adapter_dazuo(game: Game, ctx: ActionContext) -> list[str]:
    """dazuo|exercise 命令适配器：dazuo <气量>。"""
    raw = ctx.raw_args.strip()
    if not raw:
        return ["你要花多少气练功？（如：dazuo 100）"]
    try:
        cost = int(raw)
    except ValueError:
        return ["你要花多少气练功？"]
    return dazuo(game, ctx.actor, cost)


def _adapter_tuna(game: Game, ctx: ActionContext) -> list[str]:
    """tuna|respirate 命令适配器：tuna <精量>。"""
    raw = ctx.raw_args.strip()
    if not raw:
        return ["你要花多少精练功？（如：tuna 100）"]
    try:
        cost = int(raw)
    except ValueError:
        return ["你要花多少精练功？"]
    return tuna(game, ctx.actor, cost)


def _adapter_enable(game: Game, ctx: ActionContext) -> list[str]:
    """enable|jifa 命令适配器：enable [种类] [技能名]。"""
    args = ctx.raw_args.strip().split()
    if not args or not args[0]:
        return enable(game, ctx.actor)  # 无参：列 skill_map
    if len(args) == 1:
        return enable(game, ctx.actor, args[0])
    return enable(game, ctx.actor, args[0], args[1])


# 命令注册表：verb -> adapter (game, ctx) -> list[str]
# 阶段 1 的 10 命令 + get（take 别名），全部 cmds/std/cmds/usr 范畴
COMMAND_REGISTRY: dict[str, Any] = {
    "go": _adapter_go,
    "kill": _adapter_kill,
    "fight": _adapter_fight,
    "flee": _adapter_flee,
    "ask": _adapter_ask,
    "give": _adapter_give,
    "quest": _adapter_quest,
    "take": _adapter_take,
    "get": _adapter_get,
    "drop": _adapter_drop,
    "drink": _adapter_drink,
    "knock": _adapter_knock,
    "open": _adapter_open,
    "close": _adapter_close,
    "look": _adapter_look,
    "inventory": _adapter_inventory,
    "hp": _adapter_hp,
    "bai": _adapter_bai,
    "kneel": _adapter_kneel,
    "recruit": _adapter_recruit,
    "betrayer": _adapter_betrayer,
    "learn": _adapter_learn,
    "xue": _adapter_learn,
    "practice": _adapter_practice,
    "lian": _adapter_practice,
    "dazuo": _adapter_dazuo,
    "exercise": _adapter_dazuo,
    "tuna": _adapter_tuna,
    "respirate": _adapter_tuna,
    "enable": _adapter_enable,
    "jifa": _adapter_enable,
}


def run_pipeline(
    game: Game,
    ctx: ActionContext,
    *,
    permission_service: PermissionService | None = None,
    flood_state: FloodState | None = None,
    alias_state: AliasState | None = None,
    audit_log: AuditLog | None = None,
    privileged_log: PrivilegedActionLog | None = None,
    privileged_call_site: str = "",
) -> ActionContext | Abort:
    """8 段中间件管线调度器（ADR-0020 决策 1）。

    段 0-7 顺序执行，任一段返回 Abort 则短路终止。段 2/3/4/7 需要额外参数
    （permission_service / command_table / game / audit_log），通过参数注入。

    ``privileged_call_site`` 非空时表示 PrivilegedAction 路径（审计日志标记 is_privileged）。
    """
    command_table = COMMAND_REGISTRY
    current: ActionContext | Abort = ctx

    # 段 0 刷屏检测
    current = flood_check(current, flood_state)
    if isinstance(current, Abort):
        return current
    # 段 1 别名解析
    current = alias_resolve(current, alias_state)
    if isinstance(current, Abort):
        return current
    # 段 2 权限校验
    current = permission_check(current, permission_service)
    if isinstance(current, Abort):
        return current
    # 段 3 命令查找
    current = find_command(current, command_table)
    if isinstance(current, Abort):
        return current
    # 段 4 方向快捷
    current = direction_shortcut(current, game, command_table)
    if isinstance(current, Abort):
        return current
    # 段 5 参数解析
    current = parse_args(current)
    if isinstance(current, Abort):
        return current
    # 段 6 previous_object 注入
    current = inject_context(current)
    if isinstance(current, Abort):
        return current
    # 段 7 执行 + 审计
    return execute_audit(current, game, audit_log)


def dispatch(
    game: Game,
    actor: int,
    line: str,
    *,
    permission_service: PermissionService | None = None,
    capability_token: CapabilityToken | None = None,
    flood_state: FloodState | None = None,
    alias_state: AliasState | None = None,
    audit_log: AuditLog | None = None,
    seq: int = 0,
    source: int | None = None,
) -> list[str]:
    """高层命令入口：原始字符串 -> 8 段管线 -> 结果消息（ADR-0020）。

    玩家命令路径默认 source=actor（source/viewer=actor 三者相同）。
    PrivilegedAction 路径通过 ``PrivilegedAction.force`` 调 ``run_pipeline``，不走本函数。

    无 ``permission_service`` 时段 2 跳过校验（测试/开发期）；生产路径必须注入
    （fail-closed 由调用方保证）。无 ``capability_token`` 时段 2 fail-closed Abort。
    """
    line = line.strip()
    parts = line.split(None, 1)
    if not parts:
        return []
    verb = parts[0]
    raw_args = parts[1] if len(parts) > 1 else ""
    ctx = new_context(
        verb=verb,
        raw_args=raw_args,
        actor=actor,
        source=source,
        capability_token=capability_token,
        seq=seq,
    )
    result = run_pipeline(
        game,
        ctx,
        permission_service=permission_service,
        flood_state=flood_state,
        alias_state=alias_state,
        audit_log=audit_log,
    )
    if isinstance(result, Abort):
        return list(result.messages)
    return list(result.result)

