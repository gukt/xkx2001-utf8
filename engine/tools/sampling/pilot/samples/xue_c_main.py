"""pilot 样本 id=1：cmds/skill/xue.c:main 迁移代码。

对照 LPC cmds/skill/xue.c L16-151，在 engine 现有 learn() 基础上补 8 项后置分支
到行为等价。本文件为一次性测量代码，不污染 src/xkx（ADR-0048 决策 8）。
"""

from __future__ import annotations

import random

from tools.sampling.pilot.stubs import (
    is_spouse_of,
    prevent_learn,
    query_env_no_teach,
    query_married_times,
    query_skill_name,
    query_spouse_title,
    receive_damage,
    recognize_apprentice,
    to_chinese,
)

from xkx.runtime.commands import Game, _find_npc_in_room, _is_apprentice_of
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

# LPC xue.c L8-12 拒绝消息表，random(sizeof) 等价为 random.choice
_REJECT_MSG = (
    "说道：您太客气了，这怎么敢当？\n",
    "像是受宠若惊一样，说道：请教？这怎么敢当？\n",
    "笑着说道：您见笑了，我这点雕虫小技怎够资格「指点」您什么？\n",
)


def _teacher_name(world, teacher_eid: int, fallback: str) -> str:
    """取教师显示名（无 Identity 时回退参数）。"""
    ident = world.get(teacher_eid, Identity)
    return ident.name if ident else fallback


def xue_c_main(
    game: Game, actor_id: int, teacher_name: str, skill_id: str, times: int = 1
) -> list[str]:
    """xue.c:main 迁移（对照 cmds/skill/xue.c L16-151）。

    补 8 项后置分支：
    1. 峨嵋减速（L58-68）
    2. spouse 检查（L80-88）
    3. recognize_apprentice 付费认可（L50-56）
    4. prevent_learn 师傅侧门控（L74）
    5. query_skill_name 招式名文本分支（L124）
    6. to_chinese 技能中文名（L102,107）
    7. teacher jing 消耗（L109-115）
    8. env/no_teach 教学开关（L104-105）

    返回 actor 可见消息列表。LPC tell_object(ob, ...) 给 teacher 的副作用
    因引擎消息系统后置 M3，未进入返回值，仅以注释标出。
    """
    world = game.world

    # L24：busy 检查
    if is_busy(world, actor_id):
        return ["你现在正忙着呢。"]

    # L28-36：参数解析已在命令 adapter 完成；times<1 兜底
    if times < 1:
        return ["指令格式：learn|xue <某人> <技能> [次数]"]

    # L41：present(teacher, environment(me))
    pos = world.get(actor_id, Position)
    if pos is None:
        return ["你要向谁求教？"]
    teacher_eid = _find_npc_in_room(world, pos.room_id, teacher_name)
    if teacher_eid is None:
        return ["你要向谁求教？"]

    # L38：is_fighting
    combat = world.get(actor_id, CombatState)
    if combat and combat.is_fighting:
        return ["临阵磨枪？来不及啦。"]

    # L47：potential 检查
    prog = world.get(actor_id, Progression)
    if prog is None or prog.potential < times:
        return ["你的潜能不够，没有办法再成长了。"]

    # L50-56：认可链（is_apprentice_of / recognize_apprentice / is_spouse_of）
    for _ in range(times):
        if (
            not _is_apprentice_of(world, actor_id, teacher_eid)
            and not recognize_apprentice(world, actor_id, teacher_eid)
            and not is_spouse_of(world, actor_id, teacher_eid)
        ):
            display = _teacher_name(world, teacher_eid, teacher_name)
            return [display + random.choice(_REJECT_MSG)]

    # L58-68：峨嵋派男徒减速分支
    actor_family = query(world, actor_id, "family") or ""
    teacher_family = query(world, teacher_eid, "family") or ""
    gender = query(world, actor_id, "gender") or ""
    attrs = world.get(actor_id, Attributes)
    int_val = attrs.int_ if attrs else 20
    if (
        actor_family == "峨嵋派"
        and teacher_family == "峨嵋派"
        and gender != "女性"
        and int_val < 20 + random.randint(0, 24)
    ):
        slow_factor = 2
        slow_msg = "想了良久，"
    else:
        slow_factor = 1
        slow_msg = ""

    # L70：教师技能等级
    master_skill = query_skill(world, teacher_eid, skill_id, raw=True)
    if master_skill <= 0:
        return ["这项技能你恐怕必须找别人学了。"]

    # L73-74：prevent_learn 师傅侧门控
    if prevent_learn(world, teacher_eid, actor_id, skill_id):
        display = _teacher_name(world, teacher_eid, teacher_name)
        return [display + "不愿意教你这项技能。"]

    # L76-78：玩家技能不超过教师
    my_skill = query_skill(world, actor_id, skill_id, raw=True)
    if my_skill >= master_skill:
        return ["这项技能你的程度已经不输你师父了。"]

    # L80-88：配偶互教门控
    if is_spouse_of(world, actor_id, teacher_eid):
        married_times = query_married_times(world, actor_id)
        if my_skill >= master_skill - 20 * (married_times - 1):
            display = _teacher_name(world, teacher_eid, teacher_name)
            spouse_title = query_spouse_title(world, actor_id)
            return [
                display
                + "想到你和以前"
                + spouse_title
                + "在一起的情形，有点不大愿意教你这项技能。"
            ]
        teacher_exp = query(world, teacher_eid, "combat_exp") or 0
        actor_exp = query(world, actor_id, "combat_exp") or 0
        skill_data = get_skill_data(skill_id)
        if (
            (teacher_exp < 10000 or actor_exp < 10000)
            and skill_data.skill_type == "martial"
        ):
            return ["你们夫妇实战经验还不足，不能互相传授武艺！"]

    # L90-92：valid_learn
    skill_data = get_skill_data(skill_id)
    if not skill_data.valid_learn:
        return ["依你目前的能力，没有办法学习这种技能。"]

    # L95-100：基础精力消耗；初学加倍
    gin_cost = 150 // int_val if int_val > 0 else 150
    if not my_skill:
        gin_cost *= 2

    display = _teacher_name(world, teacher_eid, teacher_name)
    skill_display = to_chinese(skill_id)

    # L102：主消息
    msgs = [f"你向{display}请教有关「{skill_display}」的疑问。"]

    # L104-105：env/no_teach 教学开关
    if query_env_no_teach(world, teacher_eid):
        msgs.append(f"但是{display}现在并不准备回答你的问题。")
        return msgs

    # L107：tell_object(teacher, ...) 副作用（引擎消息系统后置 M3，未实现推送）
    # 等价消息：f"{actor_name}向你请教有关「{skill_display}」的问题。"

    # L109-115：教师精力消耗
    teacher_vitals = world.get(teacher_eid, Vitals)
    teacher_jing_cost = times * gin_cost // 5 + 1
    if teacher_vitals is None or teacher_vitals.jing <= teacher_jing_cost:
        msgs.append(f"但是{display}显然太累了，没有办法教你什么。")
        return msgs
    teacher_ident = world.get(teacher_eid, Identity)
    if teacher_ident and teacher_ident.is_player:
        receive_damage(world, teacher_eid, "jing", teacher_jing_cost)

    # L117：玩家总消耗
    total_gin_cost = times * gin_cost * 3 // 2

    # L119-122 / L143-146：玩家精力是否足够
    actor_vitals = world.get(actor_id, Vitals)
    if actor_vitals is None:
        return ["你没有状态。"]
    if actor_vitals.jing <= total_gin_cost:
        actor_vitals.jing = 0
        msgs.append("你今天太累了，结果什么也没有学到。")
        return msgs

    # L120-122：martial 技能实战经验门控（注意：被门控时不扣潜能，仅扣精力）
    actor_exp = query(world, actor_id, "combat_exp") or 0
    blocked_by_exp = (
        skill_data.skill_type == "martial" and my_skill ** 3 // 10 > actor_exp
    )
    if blocked_by_exp:
        receive_damage(world, actor_id, "jing", total_gin_cost)
        msgs.append(f"也许是缺乏实战经验，你对{display}的回答总是无法领会。")
        return msgs

    # L135：扣潜能
    prog.potential -= times

    # L137-138：gain = Σ random(int)
    gain = sum(random.randint(0, max(0, int_val - 1)) for _ in range(times))

    # L124-133：招式名消息分支
    skill_name = query_skill_name(skill_id, my_skill)
    if skill_name:
        if skill_id == "linji-zhuang":
            msgs.append(
                f"你听了{display}的指导，{slow_msg}"
                f"对「{skill_name}」的修养似乎有所提高。"
            )
        else:
            msgs.append(
                f"你听了{display}的指导，{slow_msg}"
                f"对「{skill_name}」这一招似乎有些心得。"
            )
    else:
        msgs.append(f"你听了{display}的指导，{slow_msg}似乎有些心得。")

    # L140：提升技能（减速生效）
    improve_skill(world, actor_id, skill_id, gain // slow_factor)

    # L148：玩家扣精力
    receive_damage(world, actor_id, "jing", total_gin_cost)

    return msgs
