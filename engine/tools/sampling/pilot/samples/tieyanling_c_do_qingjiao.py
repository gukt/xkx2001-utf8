"""pilot 样本 id=3：d/kunlun/obj/tieyanling.c:do_qingjiao 迁移代码。

对照 LPC d/kunlun/obj/tieyanling.c L36-167，结构与 xue.c:main 高度同构，
差异点：明教门派门控、teach_skillsname 白名单、literate 拒绝、
prevent_learn 成功静默返回、玩家精力不足消息不同。本文件为一次性测量代码
（ADR-0048 决策 8）。
"""

from __future__ import annotations

import random

from tools.sampling.pilot.stubs import (
    prevent_learn,
    query_env_no_teach,
    query_skill_name,
    query_teach_skillsname,
    receive_damage,
    to_chinese,
)

from xkx.runtime.commands import Game, _find_npc_in_room
from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Position,
    Progression,
    Vitals,
)
from xkx.runtime.query import query, query_skill
from xkx.runtime.skill import get_skill_data, improve_skill, is_busy


def _teacher_name(world, teacher_eid: int, fallback: str) -> str:
    """取教师显示名（无 Identity 时回退参数）。"""
    ident = world.get(teacher_eid, Identity)
    return ident.name if ident else fallback


def tieyanling_c_do_qingjiao(
    game: Game, actor_id: int, teacher_name: str, skill_id: str, times: int = 1
) -> list[str]:
    """tieyanling.c:do_qingjiao 迁移（对照 L36-167）。

    返回 actor 可见消息列表。LPC tell_object(ob, ...) 给 teacher 的副作用
    因引擎消息系统后置 M3，未进入返回值。
    """
    world = game.world

    # L50：busy 检查
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]

    # L53-62：参数解析已在命令 adapter 完成；times<1 兜底
    if times < 1:
        return ["指令格式：qingjiao <某人> <技能> [次数]"]

    # L66：present(teacher, environment(me))
    pos = world.get(actor_id, Position)
    if pos is None:
        return ["你要向谁求教？"]
    teacher_eid = _find_npc_in_room(world, pos.room_id, teacher_name)
    if teacher_eid is None:
        return ["你要向谁求教？"]

    # L63-64：is_fighting
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["临阵磨枪？来不及啦。"]

    # L69-70：living 检查（引擎无公开 living()，用 Identity 存在+无 disabled 近似）
    # _find_npc_in_room 已保证有 Identity；disabled 标记后置 2.5，此处跳过

    # L71-73：教师须为明教
    teacher_family = query(world, teacher_eid, "family") or ""
    if teacher_family != "明教":
        return ["你只能向明教中的兄弟请教武功。"]

    # L76-77：potential 检查
    prog = world.get(actor_id, Progression)
    if prog is None or prog.potential < times:
        return ["你的潜能不够，没有办法再成长了。"]

    # L79-80：不能向自己请教
    if teacher_eid == actor_id:
        return ["自己向自己请教？"]

    # L81-82：玩家须为明教
    actor_family = query(world, actor_id, "family") or ""
    if actor_family != "明教":
        return ["你非我明教兄弟，如何搞得这铁焰令，居然还来向我讨教功夫？"]

    # L84-98：teach_skillsname 白名单
    teach_list = query_teach_skillsname(world, teacher_eid)
    if not teach_list:
        display = _teacher_name(world, teacher_eid, teacher_name)
        return [display + "没什么可以请教的武功。"]
    if skill_id == "literate":
        display = _teacher_name(world, teacher_eid, teacher_name)
        return [display + "说道：读书写字只能靠你平时自己在书院学习，我不能传授你。"]
    if skill_id not in teach_list:
        display = _teacher_name(world, teacher_eid, teacher_name)
        return [display + "不能传授你这项武功。"]

    # L100：prevent_learn 返回 1 表示静默成功（桩默认 False，真实需师傅侧逻辑）
    if prevent_learn(world, teacher_eid, actor_id, skill_id):
        return []

    # L103-106：玩家技能不超过教师
    my_skill = query_skill(world, actor_id, skill_id, raw=True)
    master_skill = query_skill(world, teacher_eid, skill_id, raw=True)
    if my_skill >= master_skill:
        display = _teacher_name(world, teacher_eid, teacher_name)
        return [display + "呵呵一笑：这项技能你已经不输与我，我那里还敢教阁下什么？"]

    # L109：valid_learn
    skill_data = get_skill_data(skill_id)
    if not skill_data.valid_learn:
        return ["依你目前的能力，没有办法学习这种技能。"]

    # L111-112：无峨嵋减速
    slow_factor = 1
    slow_msg = ""

    # L115-120：基础精力消耗；初学加倍
    attrs = world.get(actor_id, Attributes)
    int_val = attrs.int_ if attrs else 20
    gin_cost = 150 // int_val if int_val > 0 else 150
    if not my_skill:
        gin_cost *= 2

    display = _teacher_name(world, teacher_eid, teacher_name)
    skill_display = to_chinese(skill_id)

    # L121：主消息
    msgs = [f"你向{display}请教有关「{skill_display}」的疑问。"]

    # L123-124：env/no_teach 教学开关
    if query_env_no_teach(world, teacher_eid):
        msgs.append(f"但是{display}现在并不准备回答你什么。")
        return msgs

    # L126：tell_object(teacher, ...) 副作用（引擎消息系统后置 M3，未实现推送）

    # L128-134：教师精力消耗
    teacher_vitals = world.get(teacher_eid, Vitals)
    teacher_jing_cost = times * gin_cost // 5 + 1
    if teacher_vitals is None or teacher_vitals.jing <= teacher_jing_cost:
        msgs.append(f"但是{display}显然太累了，没有办法教你什么。")
        return msgs
    teacher_ident = world.get(teacher_eid, Identity)
    if teacher_ident and teacher_ident.is_player:
        receive_damage(world, teacher_eid, "jing", teacher_jing_cost)

    # L136：玩家总消耗
    total_gin_cost = times * gin_cost * 3 // 2

    # L138-162：玩家精力是否足够
    actor_vitals = world.get(actor_id, Vitals)
    if actor_vitals is None:
        return ["你没有状态。"]
    if actor_vitals.jing <= total_gin_cost:
        msgs.append(
            f"你现在精神不够，无法向{display}请教{skill_display}。"
        )
        return msgs

    # L139-141：martial 技能实战经验门控（被门控时不扣潜能，仅扣精力）
    actor_exp = query(world, actor_id, "combat_exp") or 0
    blocked_by_exp = (
        skill_data.skill_type == "martial" and my_skill ** 3 // 10 > actor_exp
    )
    if blocked_by_exp:
        receive_damage(world, actor_id, "jing", total_gin_cost)
        msgs.append(f"也许是缺乏实战经验，你对{display}的回答总是无法领会。")
        return msgs

    # L150：扣潜能
    prog.potential -= times

    # L152-153：gain = Σ random(int)
    gain = sum(random.randint(0, max(0, int_val - 1)) for _ in range(times))

    # L143-148：招式名消息分支（无 linji-zhuang 特例）
    skill_name = query_skill_name(skill_id, my_skill)
    if skill_name:
        msgs.append(
            f"你听了{display}的指导，{slow_msg}"
            f"对「{skill_name}」这一招似乎有些心得。"
        )
    else:
        msgs.append(f"你听了{display}的指导，{slow_msg}似乎有些心得。")

    # L155：提升技能
    improve_skill(world, actor_id, skill_id, gain // slow_factor)

    # L164：玩家扣精力
    receive_damage(world, actor_id, "jing", total_gin_cost)

    return msgs
