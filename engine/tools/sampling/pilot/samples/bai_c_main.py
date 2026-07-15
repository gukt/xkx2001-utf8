"""pilot 样本 id=13：cmds/skill/bai.c:main 迁移代码。

对照 LPC cmds/skill/bai.c L8-103，在 engine 现有 bai() 简化版基础上补 6 项
被简化跳过的后置分支到行为等价。本文件为一次性测量代码，不污染 src/xkx
（ADR-0048 决策 8）。

补全分支（commands.py:1283 简化版跳过的）：
1. cancel 分支（L23-31）：读 pending/apprentice + 改主意消息 + 通知 old_app
2. possessed 检查（L21）：被附体者不能拜师，静默返回
3. 玩家拜玩家门控（L43-44）：userp(ob) && !wizardp(ob) -> 拒绝（补 wizardp）
4. add 第 3 个死亡原因参数（L47）：磕头扣 50 jing 致死时死因「磕死」（reason）
5. pending 二次确认双向握手（L62-102）：
   - pending/recruit == me -> 立即收徒（含叛师 score/death_count/betrayer）
   - 否则 set pending/apprentice，玩家目标通知 recruit，NPC 目标 attempt_apprentice
6. chinese_number（L83）：第 N 代弟子的中文数字（用阿拉伯数字占位）

后置 dbase key（score/death_count/possessed/special_master/family/* 路径）无法
经 query/set 走（raise DbaseKeyError），用 monkeypatch 桩在测试注入，或直访
FamilyComp 组件绕过路径 key。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.stubs import (
    tell_object,
    wizardp,
)

from xkx.runtime.commands import (
    Game,
    _is_apprentice_of,
    _recruit_apprentice,
)
from xkx.runtime.components import (
    FamilyComp,
    Identity,
    NpcBehavior,
    Position,
    Vitals,
)
from xkx.runtime.skill import is_busy


def _entity_name(world: Any, eid: int, fallback: str = "") -> str:
    """取实体显示名（无 Identity 时回退参数，对照 LPC ob->name()）。"""
    ident = world.get(eid, Identity)
    return ident.name if ident else fallback


def chinese_number(n: int) -> str:
    """数字转中文（对照 LPC L83 chinese_number，第 N 代弟子）。

    runtime 无实现（仅 spec layer_h_daemons.py:2562 CHINESE_D）。桩用阿拉伯
    数字 str 占位（commands.py:1232 注释对齐）；测试可 monkeypatch 注入中文
    断言。真实需 CHINESE_D daemon（后置内容生产）。
    """
    return str(n)


def _query_possessed(world: Any, eid: int) -> bool:
    """读 possessed 标记（L21，被附体者不能拜师）。

    dbase key "possessed" 为 unknown（query raise）。桩默认 False；测试可
    monkeypatch 本函数返回 True 触发 L21 静默分支。真实需 PossessionComp。
    """
    return False


def _query_special_master(world: Any, eid: int) -> bool:
    """读 special_master 标记（L57，特殊师傅不受辈分限制）。

    dbase key "special_master" 为 unknown（query raise）。桩默认 False；
    测试可 monkeypatch 返回 True 绕过辈分检查。真实需师傅侧配置字段。
    """
    return False


def _set_score(world: Any, eid: int, val: int) -> None:
    """set("score", 0)（L68，叛师时评价归零）。

    dbase key "score" 为 unknown（set raise）。桩 no-op；测试可 monkeypatch
    注入副作用断言。真实需 TitleComp 或 Progression.score 字段。
    """


def _set_death_count(world: Any, eid: int, val: int) -> None:
    """set("death_count", 0)（L69，叛师时死亡计数归零）。

    dbase key "death_count" 在 POSTPONED_KEYS（set raise）。桩 no-op；测试
    可 monkeypatch 注入副作用断言。真实需 TitleComp.death_count（2.5 激活）。
    """


def _pending_apprentice(world: Any, eid: int) -> int | None:
    """读 pending/apprentice（L24/L87，玩家待拜师的师傅 eid）。

    路径 key "pending/apprentice" 为 unknown（query_temp raise）。greenfield
    用 marks/ 前缀存 flag（commands.py:1288 注释），本桩改存 marks/
    pending-apprentice 以复用 Marks 组件，值用 flag 存在性表达（有=在拜）。
    因 flag 不带 eid，用模块级 dict 暂存 eid->master_eid（测试一次性，不污染
    src/xkx）。真实需 pending 握手子系统（apprentice/recruit 双向）。
    """
    return _PENDING_APPRENTICE.get(eid)


def _set_pending_apprentice(world: Any, eid: int, master_eid: int) -> None:
    """set_temp('pending/apprentice', ob)（L96）。"""
    _PENDING_APPRENTICE[eid] = master_eid


def _clear_pending_apprentice(world: Any, eid: int) -> None:
    """delete_temp('pending/apprentice')（L29）。"""
    _PENDING_APPRENTICE.pop(eid, None)


def _pending_recruit(world: Any, eid: int) -> int | None:
    """读 pending/recruit（L62，师傅待收的徒弟 eid）。

    路径 key "pending/recruit" 为 unknown（query_temp raise）。同
    pending/apprentice，用模块级 dict 暂存。
    """
    return _PENDING_RECRUIT.get(eid)


def _clear_pending_recruit(world: Any, eid: int) -> None:
    """delete_temp('pending/recruit')（L77）。"""
    _PENDING_RECRUIT.pop(eid, None)


# pending 握手状态：玩家 eid -> 待拜师傅 eid（apprentice）/ 师傅 eid -> 待收徒弟 eid（recruit）
_PENDING_APPRENTICE: dict[int, int] = {}
_PENDING_RECRUIT: dict[int, int] = {}


def _attempt_apprentice(world: Any, master_eid: int, player_eid: int) -> list[str]:
    """ob->attempt_apprentice(me)（L100，NPC 师傅侧入门条件钩子）。

    引擎 _eval_apprentice_conditions 是声明式简化（commands.py:1175），返回
    (通过, 拒绝消息)。本函数包装为 LPC call_other 语义：返回消息列表（空=通过
    继续等 recruit，非空=拒绝消息直接反馈玩家）。NPC 无 app_config 时走
    「不收徒」分支。
    """
    from xkx.runtime.commands import _eval_apprentice_conditions

    behavior = world.get(master_eid, NpcBehavior)
    app_config = behavior.apprentice_config if behavior else None
    master_name = _entity_name(world, master_eid)
    if app_config is None:
        return [f"{master_name}似乎不想收徒。"]
    ok, reject_msg = _eval_apprentice_conditions(
        world, player_eid, app_config.get("conditions", {}), master_name
    )
    if not ok:
        return [reject_msg]
    return []


def _do_recruit(
    world: Any, master_eid: int, player_eid: int, betray: bool
) -> tuple[list[str], list[str]]:
    """收徒核心（L62-84 pending/recruit 命中后的收徒）。

    返回 (actor_msgs, master_msgs)。actor_msgs 给玩家，master_msgs 给师傅
    （tell_object 副作用，引擎消息系统后置 M3，仅以注释标出）。
    对照 LPC L64-83：叛师分支额外 score=0/death_count=0/betrayer+1，否则普通拜师。
    """
    master_name = _entity_name(world, master_eid)
    behavior = world.get(master_eid, NpcBehavior)
    app_config = behavior.apprentice_config if behavior else None
    if app_config is None:
        # 无 app_config 无法收徒（simplified bai 走「似乎不想收徒」，此处等价）
        return [f"{master_name}似乎不想收徒。"], []
    # L76：recruit_apprentice（含叛师 betrayer+1 + 写 FamilyComp + 设头衔）
    recruit_msgs = _recruit_apprentice(world, master_eid, player_eid, app_config)
    # L68-70：叛师分支额外副作用（score=0 / death_count=0 / betrayer+1）
    # _recruit_apprentice 已处理 betrayer+1；score/death_count 后置 key 走桩
    if betray:
        _set_score(world, player_eid, 0)
        _set_death_count(world, player_eid, 0)
    # L77：清师傅侧 pending/recruit
    _clear_pending_recruit(world, master_eid)
    # L79：tell_object(ob, "恭喜你新收了一名弟子！\n") 副作用（后置 M3）
    master_msgs = ["恭喜你新收了一名弟子！\n"]
    # L81-83：printf 给玩家（成为第 N 代弟子）
    family = world.get(player_eid, FamilyComp)
    family_name = family.family_name if family else ""
    generation = family.generation if family else 0
    # chinese_number 后置，用阿拉伯数字占位
    gen_str = chinese_number(generation)
    recruit_msgs.append(f"恭喜您成为{family_name}的第{gen_str}代弟子。\n")
    return recruit_msgs, master_msgs


def bai_c_main(game: Game, actor_id: int, arg: str = "") -> list[str]:
    """bai.c:main 迁移（对照 cmds/skill/bai.c L8-103）。

    返回 actor 可见消息列表。LPC tell_object(ob, ...) / message_vision 给师傅
    与房间其他人的副作用因引擎消息系统后置 M3，未进入返回值，仅以注释标出
    （message_vision 仅作字符串占位，房间广播未实现）。

    arg 对齐 LPC ``apprentice | bai [cancel]|<对象>``：``""``=无参，
    ``"cancel"``=取消，其余=目标名称。
    """
    world = game.world

    # L15：busy 检查
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]

    # L18-19：无参 -> 指令格式
    if not arg:
        return ["指令格式：apprentice | bai [cancel]|<对象>"]

    # L21：possessed 检查（被附体者静默返回，对照 LPC return 0）
    if _query_possessed(world, actor_id):
        return []

    # L23-31：cancel 分支
    if arg == "cancel":
        old_app = _pending_apprentice(world, actor_id)
        if old_app is None:
            return ["你现在并没有拜任何人为师的意思。"]
        old_name = _entity_name(world, old_app, "某人")
        msgs = [f"你改变主意不想拜{old_name}为师了。"]
        # L28：tell_object(old_app, me->name() + "改变主意不想拜你为师了。\n")
        # 引擎消息推送后置 M3；tell_object 桩写 pending_messages（不进返回值）
        my_name = _entity_name(world, actor_id, "某人")
        tell_object(world, old_app, f"{my_name}改变主意不想拜你为师了。\n")
        _clear_pending_apprentice(world, actor_id)
        return msgs

    # L33-35：present(arg, environment(me)) + is_character
    pos = world.get(actor_id, Position)
    if pos is None:
        return ["你想拜谁为师？"]
    # _find_npc_in_room 仅查 NPC（Identity 且 !is_player）；LPC present 还查房间地面
    # 物品但被 is_character 拒（无影响）。玩家目标（is_player）走 L43 门控，
    # 此处用 find_player_in_room 单独查玩家实体。
    ob = _find_target_in_room(world, pos.room_id, arg)
    if ob is None or not _is_character(world, ob):
        return ["你想拜谁为师？"]

    # L37-38：living 检查（引擎无公开 living()，用无 disabled mark 近似；
    # _find_target_in_room 已保证有 Identity，disabled 后置 2.5，此处跳过）

    # L40-41：拜自己
    if ob == actor_id:
        return ["拜自己为师？好主意....不过没有用。"]

    # L43-44：玩家拜玩家门控（补 wizardp）
    ob_ident = world.get(ob, Identity)
    if ob_ident and ob_ident.is_player and not wizardp(world, ob):
        return ["你不能够拜其他玩家为师。"]

    # L46-50：已是徒弟 -> 请安（磕头扣 50 jing，第 3 参数「磕死」死因）
    if _is_apprentice_of(world, actor_id, ob):
        # L47：add("jing", -50, "一头磕在地上磕死了。")
        # 引擎 add 无第 3 死亡原因参数；reason 用 _add_jing_with_reason 桩记死因
        _add_jing_with_reason(world, actor_id, -50, "一头磕在地上磕死了。")
        # L48：message_vision("$N恭恭敬敬地向$n磕头请安，叫道：「师父！」\n", me, ob)
        # 房间广播后置 M3；返回玩家可见消息
        ob_name = _entity_name(world, ob, "某人")
        return [f"你恭恭敬敬地向{ob_name}磕头请安，叫道：「师父！」"]

    # L52-53：师傅须有 family（mapp 检查）
    ob_family = world.get(ob, FamilyComp)
    if ob_family is None or not ob_family.family_name:
        ob_name = _entity_name(world, ob, "某人")
        return [f"{ob_name}既不属於任何门派，也没有开山立派，不能拜师。"]

    # L55-58：辈分检查（同门派 + 师傅辈分 >= 玩家 + 非 special_master）
    my_family = world.get(actor_id, FamilyComp)
    my_gen = my_family.generation if my_family else 0
    my_fn = my_family.family_name if my_family else ""
    if (
        ob_family.family_name == my_fn
        and ob_family.generation >= my_gen
        and not _query_special_master(world, ob)
    ):
        ob_name = _entity_name(world, ob, "某人")
        return [f"{ob_name}的辈分不对，你不能拜平辈或晚辈为师。"]

    # L62：pending/recruit == me -> 师傅已愿收，立即行拜师礼
    pending_recruit_target = _pending_recruit(world, ob)
    if pending_recruit_target == actor_id:
        # L63-75：叛师 vs 普通拜师分支
        ob_fn = ob_family.family_name
        betray = my_fn != "" and my_fn != ob_fn
        if betray:
            # L64-67：叛师 message_vision
            ob_name = _entity_name(world, ob, "某人")
            recruit_msgs, _master_msgs = _do_recruit(world, ob, actor_id, betray=True)
            # 叛师首条消息（L65-66 两段合并）
            recruit_msgs = [
                f"你决定背叛师门，改投入{ob_name}门下！！\n"
                f"你跪了下来向{ob_name}恭恭敬敬地磕了四个响头，叫道：「师父！」\n",
                *recruit_msgs,
            ]
        else:
            # L72-75：普通拜师 message_vision
            ob_name = _entity_name(world, ob, "某人")
            recruit_msgs, _master_msgs = _do_recruit(world, ob, actor_id, betray=False)
            recruit_msgs = [
                f"你决定拜{ob_name}为师。\n"
                f"你跪了下来向{ob_name}恭恭敬敬地磕了四个响头，叫道：「师父！」\n",
                *recruit_msgs,
            ]
        # L79：tell_object(ob, "恭喜你新收了一名弟子！\n") 副作用（后置 M3）
        # L81-83：printf 已并入 recruit_msgs
        return recruit_msgs

    # L86-101：else 分支 -> 设 pending/apprentice，通知/钩子
    old_app = _pending_apprentice(world, actor_id)
    if ob == old_app:
        # L88-89：还在等同一个师傅答应
        ob_name = _entity_name(world, ob, "某人")
        return [f"你想拜{ob_name}为师，但是对方还没有答应。"]
    if old_app is not None:
        # L90-93：改主意换人，先取消旧的
        old_name = _entity_name(world, old_app, "某人")
        # L91：write 给玩家
        msgs = [f"你改变主意不想拜{old_name}为师了。"]
        # L92：tell_object(old_app, me->name() + "改变主意不想拜你为师了。\n")
        my_name = _entity_name(world, actor_id, "某人")
        tell_object(world, old_app, f"{my_name}改变主意不想拜你为师了。\n")
        _clear_pending_apprentice(world, actor_id)
    else:
        msgs = []

    # L95：message_vision("$N想要拜$n为师。\n", me, ob)
    ob_name = _entity_name(world, ob, "某人")
    msgs.append(f"你想要拜{ob_name}为师。")
    # L96：set_temp("pending/apprentice", ob)
    _set_pending_apprentice(world, actor_id, ob)

    # L97-100：玩家目标通知 recruit，NPC 目标 attempt_apprentice
    if ob_ident and ob_ident.is_player:
        # L98：tell_object(ob, YEL "如果你愿意收...为弟子，用 recruit 指令。\n" NOR)
        my_name = _entity_name(world, actor_id, "某人")
        tell_object(
            world,
            ob,
            f"如果你愿意收{my_name}为弟子，用 recruit 指令。\n",
        )
    else:
        # L100：ob->attempt_apprentice(me)
        reject_msgs = _attempt_apprentice(world, ob, actor_id)
        if reject_msgs:
            # NPC 拒绝（条件不满足），清 pending 并返回拒绝消息
            _clear_pending_apprentice(world, actor_id)
            return reject_msgs

    return msgs


def _find_target_in_room(world: Any, room_id: str, name: str) -> int | None:
    """present(arg, environment(me))（L33）。

    查房间内任意角色实体（含玩家与 NPC），按 name/alias 匹配。
    _find_npc_in_room 仅查 NPC；本函数扩展查玩家实体（L43 玩家拜玩家门控
    需先 present 到玩家目标）。
    """
    for eid in world.entities_in_room(room_id):
        ident = world.get(eid, Identity)
        if ident and name in (ident.name, *ident.aliases):
            return eid
    return None


def _is_character(world: Any, eid: int) -> bool:
    """ob->is_character()（L34）。greenfield 无独立谓词，用 Identity 存在判定。"""
    return world.get(eid, Identity) is not None


def _add_jing_with_reason(world: Any, eid: int, delta: int, reason: str) -> None:
    """add("jing", delta, reason)（L47 第 3 个死亡原因参数）。

    引擎 add(world,eid,key,val) 仅 2 参值，无 reason。本桩内联扣 jing 并记录
    reason（磕头扣 50 jing 致死时死因「一头磕在地上磕死了。」）。clamp >=0；
    真实需 receive_damage 通用化 + 死亡触发钩子（后置，桩5）。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return
    vitals.jing = max(0, vitals.jing + delta)
    # 死因记录（测试可读 _JING_DEATH_REASONS 断言 reason 传递）
    if vitals.jing <= 0 and reason:
        _JING_DEATH_REASONS[eid] = reason


# 死因记录：玩家 eid -> 磕死 reason（供测试断言第 3 参数传递）
_JING_DEATH_REASONS: dict[int, str] = {}
