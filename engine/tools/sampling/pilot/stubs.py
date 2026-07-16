"""pilot 共享桩：新引擎缺失的 LPC 等价行为占位。

ADR-0048 决策 2：多个 pending/logic 样本共用这些缺口 API，pilot 前
一次性补建最小可用桩，避免每样本重复建。

桩为"最小等价行为占位"：满足调用契约（参数/返回/副作用语义），行为
按首个依赖样本（xue.c:main）的需求补全，不追求完整，仅保证调用通过 +
主路径行为等价。后续样本实测时按需细化。

注意：这是测量用桩，不是 src/xkx 正式实现。落一次性目录
（ADR-0048 决策 8），测完即丢，不污染 src/xkx。

桩清单（xue.c:main 实读 + ADR-0048 点名，6 桩 + 3 个 A 类回落桩；
SKILL_D.type/valid_learn 已有简化版见 combat/context.py，不重建）：
- is_spouse_of(me, ob) -> bool              （xue L53,80,91,93 配偶链）
- recognize_apprentice(me) -> bool           （xue L53 ob 侧付费认可）
- prevent_learn(me, skill) -> bool          （xue L74 师傅侧门控）
- query_skill_name(skill, level) -> str     （xue L124 招式名）
- to_chinese(skill) -> str                  （xue L102,107 技能中文名）
- receive_damage(entity, vital, amount)     （xue L110,148 通用 vital 扣减）
- query_env_no_teach(world, eid) -> bool       （xue L104，env/ 路径未映射）
- query_married_times(world, eid) -> int       （xue L81，spouse 系统未迁移）
- query_spouse_title(world, eid) -> str        （xue L83，spouse 系统未迁移）
- query_teach_skillsname(world, eid) -> list   （tieyanling L84，NPC 可教白名单）

阶段一预建共享桩（剩余样本 id=2,4-13 多样本共用，ADR-0048 决策 2；
一次性预建消除阶段二并行写冲突，各样本只读用，不再改本文件）：
- wizardp(world, eid) -> bool              （2,6,7,12,13 巫师判定，回落 False）
- start_more(msg) -> list[str]             （2,9 分页，全引擎无 pager，返回 [msg]）
- ANSI 颜色常量 + strip_ansi(s)            （5,7 颜色码砍掉，常量空串）
- query_jiali(world, eid) -> int           （5,8 加力，回落 0）
- query_str(world, eid) -> int             （5,8 派生膂力，回落 Attributes.str_）
- set_skill/delete_skill/map_skill/        （4,5,8,11 skill-feature 变更 API，
  prepare_skill/reset_action/query_skills   薄包装 Skills 组件已就绪 dict）
- tell_object/tell_room/message_vision     （5,6,7 消息 facade，写 pending_messages）
"""

from __future__ import annotations

import re
from typing import Any

from xkx.runtime.components import Attributes, Vitals

# reset_action 已正式化到 runtime.equipment（B 类补全，对照 feature/attack.c）。
from xkx.runtime.equipment import reset_action  # noqa: F401  re-export 供 pilot 样本

# skill 读写 API 已正式化到 runtime.skill（B 类补全，对照 feature/skill.c）。
# 此处 re-export 保持 pilot 样本 import 路径不变（ADR-0048 决策 8）。
from xkx.runtime.skill import (  # noqa: F401  re-export 供 pilot 样本使用
    delete_skill,
    map_skill,
    prepare_skill,
    query_skill_map,
    query_skill_prepare,
    query_skills,
    set_skill,
)


def is_spouse_of(world: Any, me_id: int, ob_id: int) -> bool:
    """双向配偶校验（对照 xue.c L53,80,91,93）。

    桩：默认 False（新引擎无 MarriageComp）。
    真实：需 MarriageComp + 双向校验 + married_times/spouse/title
    （xue.c L80-88 配偶婚次惩罚 + 实战经验门控）。
    """
    return False


def recognize_apprentice(world: Any, me_id: int, ob_id: int) -> bool:
    """ob 侧付费认可学徒（对照 xue.c L50-53）。

    桩：默认 False。真实含 mark/朱 事务性 add/回滚（L91-93）+
    potential 扣费。xue.c L50-51 注释：recognize_apprentice 内部
    处理 literate 付费，learn_times 次循环外部已处理（L52）。
    """
    return False


def prevent_learn(world: Any, ob_id: int, me_id: int, skill_id: str) -> bool:
    """师傅侧可教白/黑名单门控（对照 xue.c L74）。

    桩：默认 False（可教）。返回 True = 拒绝教。
    真实：师傅 NPC 的可教技能白名单/黑名单逻辑。
    """
    return False


def query_skill_name(skill_id: str, level: int) -> str | None:
    """技能招式名（对照 xue.c L124 SKILL_D->query_skill_name）。

    桩：默认 None（无招式名表，xue.c L132-133 走"似乎有些心得"兜底）。
    真实：SkillData 增招式表字段，按 level 返回招式名。
    """
    return None


def to_chinese(skill_id: str) -> str:
    """技能 id -> 中文名（对照 xue.c L102,107 to_chinese）。

    桩：默认返回 skill_id（占位，无中文名映射表）。
    真实：技能 id -> 中文名映射表。
    """
    return skill_id


def receive_damage(world: Any, entity_id: int, vital: str, amount: int) -> None:
    """通用 vital 扣减（对照 xue.c L110,148 receive_damage）。

    新引擎当前仅 combat apply 有 damage，runtime 无通用扣减
    （learn() 直接 vitals.jing -= gin_cost，无 clamp）。
    桩：扣 Vitals.<vital>，clamp >=0（行为等价 learn.c receive_damage）。
    """
    vitals = world.get(entity_id, Vitals)
    if vitals is None:
        return
    cur = getattr(vitals, vital, None)
    if cur is None:
        return
    setattr(vitals, vital, max(0, cur - amount))


def query_env_no_teach(world: Any, entity_id: int) -> bool:
    """NPC 教学开关 env/no_teach（对照 xue.c L104）。

    桩：默认 False（可教）。新引擎 "env" 在 POSTPONED_KEYS，query 会
    返回 None + warning；用本桩回落避免噪音。
    """
    return False


def query_married_times(world: Any, entity_id: int) -> int:
    """婚次计数（对照 xue.c L81 配偶分支惩罚）。

    桩：默认 0。真实需 MarriageComp + spouse 关系。
    """
    return 0


def query_spouse_title(world: Any, entity_id: int) -> str:
    """配偶称号（对照 xue.c L83 配偶分支消息）。

    桩：默认空串。真实需 MarriageComp。
    """
    return ""


def query_teach_skillsname(world: Any, entity_id: int) -> list[str]:
    """NPC 可教武功白名单（对照 tieyanling.c L84 teach_skillsname）。

    桩：默认空列表（对应 LPC 未设置白名单，迁移时走"没什么可以请教"分支）。
    真实：NpcBehavior 或 SkillData 中配置可教技能列表。
    """
    return []


# ===== 阶段一预建共享桩（ADR-0048 决策 2，消除阶段二并行写冲突）=====


def wizardp(world: Any, eid: int) -> bool:
    """巫师判定（对照 center.c:134 can_used / damage.c / emoted.c / s_combatd.c / bai.c）。

    桩：默认 False（新引擎无 wiz_level 组件，用 capability/permission 模型替代）。
    真实：WizLevel 枚举挂载到实体或 session token 解析。
    """
    return False


def start_more(msg: str) -> list[str]:
    """分页显示长文本（对照 center.c this_player()->start_more / bboard.c F_MORE）。

    全引擎无 pager（grep start_more/more/paging 零命中）。
    桩：返回 [msg]（命令返回值占位，测试检查子串）。
    真实：客户端层 pager 或 start_more 组件分块输出。
    """
    return [msg]


# LPC ansi.h 颜色码。新引擎砍颜色内核（收缩约束），常量回落空串。
NOR = HIW = HIY = HIR = HIG = HIC = HIB = HIM = ""
HBBLU = HBRED = HBYEL = HBGRE = HBCYN = HBMAG = ""
BLINK = BOLD = ""
ESC = ""
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s: str) -> str:
    """去 ANSI 转义码（对照 LPC 颜色码清理）。

    桩常量全空串，迁移代码注入的 HIW+...+NOR 无 ESC；本函数兼容测试
    注入带码串。
    """
    return _ANSI_RE.sub("", s)


def query_jiali(world: Any, eid: int) -> int:
    """加力值 query("jiali")（对照 songshan-jian.c / shizi.c）。

    桩：默认 0（dbase key "jiali" 未映射，玩家自由设置项无组件承接）。
    """
    return 0


def query_str(world: Any, eid: int) -> int:
    """有效膂力 query_str() sefun（对照 songshan-jian.c / shizi.c）。

    桩：回落 Attributes.str_ 基础值（race.py:228 明确 greenfield 无
    query_str 派生加成）。真实：str + 装备/condition 派生加成。
    """
    attrs = world.get(eid, Attributes)
    return attrs.str_ if attrs else 0


# skill 读写 API（set_skill / delete_skill / map_skill / prepare_skill /
# query_skills / query_skill_map / query_skill_prepare）原为薄包装桩，已正式化
# 到 runtime.skill 并在文件顶部 re-export（B 类补全，对照 feature/skill.c）。


# reset_action 原为 no-op 桩，已正式化到 runtime.equipment 并在文件顶部 re-export
# （B 类补全，对照 feature/attack.c:143-171）。


def tell_object(world: Any, eid: int, msg: str) -> None:
    """向实体输出消息 tell_object(ob, msg)（对照 LPC efun）。

    桩：写 world.pending_messages（M3-1 最小缓冲，复用 death.py:_tell 模式）。
    真实：ConnectionSystem.push_event WS 推送（后置 M3）。
    """
    pending = getattr(world, "pending_messages", None)
    if pending is not None:
        pending.append(msg)


def tell_room(
    world: Any, room_id: str, msg: str, exclude: tuple[int, ...] = ()
) -> None:
    """房间广播 tell_room(room, msg, exclude)（对照 LPC efun）。

    桩：遍历 world.entities_in_room 逐个 tell_object（排除 exclude）。
    """
    for eid in world.entities_in_room(room_id):
        if eid not in exclude:
            tell_object(world, eid, msg)


def message_vision(world: Any, msg: str, me: int, *others: int) -> str:
    """格式化广播 message_vision(msg, me, ...)（对照 LPC efun）。

    桩：仅返回 msg（PronounService.render 的 $N/$n 替换 + 房间广播后置 M3）。
    迁移方按需自行替换代词后调 tell_room 分发返回值。
    """
    return msg
