"""pilot 样本 id=4：clone/npc/murong.c:do_copy 迁移代码。

对照 LPC clone/npc/murong.c L192-284，慕容博"以彼之道还施彼身"技能复制例程：
①清自身 force/dodge/parry 之外技能 + 全部 map/prepare；
②复制 ob(玩家) 的 unarmed/force/dodge 类技能(经 is_unarmed + SKILL_D->valid_enable
筛选)设为 200；
③重设 map/prepare（含 valid_combine 双组合分支）；
④reset_action 重算动作集。

do_copy 非 NPC 命令，是 NPC 行为例程（LPC void do_copy(object ob)，无返回值）。
签名重构为 do_copy(world, me_eid, ob_eid)，me/ob 改为显式 eid（ECS 范式，对照
triage this_object 条目）。返回 None，行为等价验证靠查 Skills 组件副作用。

本文件为一次性测量代码，不污染 src/xkx（ADR-0048 决策 8）。
"""

from __future__ import annotations

from tools.sampling.pilot.stubs import (
    delete_skill,
    map_skill,
    prepare_skill,
    query_skill_map,
    query_skill_prepare,
    query_skills,
    reset_action,
    set_skill,
)

from xkx.runtime.query import query_skill
from xkx.runtime.skill import get_skill_data

# 对照 murong.c L347-354 is_unarmed 内 unarmed_types 常量
_UNARMED_TYPES = ("finger", "hand", "cuff", "claw", "strike", "kick")


def _valid_enable(skill_id: str, category: str) -> bool:
    """SKILL_D(skill)->valid_enable(category)（对照 murong.c L240-241/L261/L266）。

    SkillData.valid_enable 为 list[str]，空=不限制（context.py:66 stub 默认空）。
    对 do_copy 语义：valid_enable 返回真表示该 skill 可 enable 到 category。
    空 valid_enable 在原 LPC 真实武学下不会发生（do_copy 仅复制真实武学），
    stub 空表下本函数恒 False -> 复制空集（triage 已注明此行为缺口）。
    """
    sd = get_skill_data(skill_id)
    return bool(sd.valid_enable) and category in sd.valid_enable


def is_unarmed(skill: str) -> list[str]:
    """判 skill 是否徒手系并返回 enable 序列（对照 murong.c L342-369）。

    - skill 本身是基础 unarmed_type -> 返回 [skill]（长度 1）
    - 否则遍历 unarmed_types，valid_enable 命中则追加 [type, skill]；
      可能命中多个 type -> 长度 >2
    - 调用方用 sizeof()==2 判定"恰好一个 type + skill"的双组合分支（L252）
    """
    result: list[str] = []
    if skill in _UNARMED_TYPES:
        result.append(skill)
    else:
        for utype in _UNARMED_TYPES:
            if _valid_enable(skill, utype):
                result.append(utype)
                result.append(skill)
    return result


def valid_combine(skill_a: str, skill_b: str) -> bool:
    """SKILL_D(skill_a)->valid_combine(skill_b)（对照 murong.c L260）。

    SkillData 无 valid_combine 字段，全引擎未实现（triage 注明）。
    桩默认 False（无双组合）。样本特有桩，测试用 monkeypatch 注入真值，
    不进 stubs.py（红线：样本特有桩用测试 monkeypatch）。
    """
    return False


def do_copy(world, me_eid: int, ob_eid: int) -> None:
    """murong.c:do_copy 迁移（对照 L192-284）。

    me=慕容博 NPC（this_object），ob=被复制目标玩家。返回 None（LPC void）。
    """
    # L200-211：清自身 force/dodge/parry 之外技能
    skill_status = query_skills(world, me_eid)
    for sname in list(skill_status):
        if sname != "force" and sname != "dodge" and sname != "parry":
            delete_skill(world, me_eid, sname)

    # L213-222：清全部技能映射
    map_status = query_skill_map(world, me_eid)
    for mname in list(map_status):
        map_skill(world, me_eid, mname)

    # L224-232：清全部技能准备
    prepare_status = query_skill_prepare(world, me_eid)
    for pname in list(prepare_status):
        prepare_skill(world, me_eid, pname)

    # L234-244：复制 ob 的 unarmed/force/dodge 类技能，设为 200
    ob_skills = query_skills(world, ob_eid)
    for sname in ob_skills:
        if (
            len(is_unarmed(sname))
            or _valid_enable(sname, "force")
            or _valid_enable(sname, "dodge")
        ):
            set_skill(world, me_eid, sname, 200)

    # L246-269：重设技能映射与准备（仅 dodge/force/unarmed 类）
    # 注意 pre1 在 LPC 是上一轮循环的残留值（L259 用到 pre1），属 LPC 隐式状态。
    # 为行为等价照搬：pre1 在双组合分支复用上一轮赋值，初值 None。
    pre1: str | None = None
    my_skills = query_skills(world, me_eid)
    for sname in my_skills:
        umname = is_unarmed(sname)
        if len(umname) == 2:
            # umname[0]=enable 的基础 type，umname[1]=sname 本身
            base = umname[0]
            # L253：若基础技能未学则补设 200
            if query_skill(world, me_eid, base, raw=True) < 1:
                set_skill(world, me_eid, base, 200)
            # L255-264：按当前 prepare 数量决定单/双组合
            prepare_count = len(query_skill_prepare(world, me_eid))
            if prepare_count == 0:
                pre1 = sname
                map_skill(world, me_eid, base, pre1)
                prepare_skill(world, me_eid, base, pre1)
            elif (
                prepare_count == 1
                and pre1 is not None
                and valid_combine(pre1, sname)
            ):
                # L260-263：双组合，改用 sname 覆盖
                pre2 = sname
                map_skill(world, me_eid, base, pre2)
                prepare_skill(world, me_eid, base, pre2)
        elif _valid_enable(sname, "force"):
            # L265：force 类映射
            map_skill(world, me_eid, "force", sname)
        elif _valid_enable(sname, "dodge"):
            # L266-267：dodge 类映射
            map_skill(world, me_eid, "dodge", sname)

    # L271-281：仍无 prepare 时设默认指法/掌法/散花掌/一指禅组合
    if len(query_skill_prepare(world, me_eid)) == 0:
        set_skill(world, me_eid, "finger", 200)
        set_skill(world, me_eid, "strike", 200)
        set_skill(world, me_eid, "sanhua-zhang", 200)
        set_skill(world, me_eid, "yizhi-chan", 200)
        map_skill(world, me_eid, "finger", "yizhi-chan")
        map_skill(world, me_eid, "strike", "sanhua-zhang")
        prepare_skill(world, me_eid, "strike", "sanhua-zhang")
        prepare_skill(world, me_eid, "finger", "yizhi-chan")
        map_skill(world, me_eid, "parry", "sanhua-zhang")

    # L283：重算动作集（stubs.reset_action 为 no-op，完整重算后置 2.3）
    reset_action(world, me_eid)
