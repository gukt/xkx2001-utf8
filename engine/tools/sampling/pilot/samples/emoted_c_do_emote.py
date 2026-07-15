"""pilot 样本 id=7：adm/daemons/emoted.c:do_emote 迁移代码。

对照 LPC adm/daemons/emoted.c L79-175，迁移本地 emote（channel_emote==0）
主路径 + 关键分支到行为等价。本文件为一次性测量代码，不污染 src/xkx
（ADR-0048 决策 8）。

do_emote 是 daemon 函数（非命令函数），LPC 返回契约：
- 本地非频道（channel_emote==0）：成功 return 1，失败 return 0（notify_fail）
- 频道（channel_emote!=0）：成功 return normal_color(others 消息)，失败 return 0

B 类缺口简化（任务说明 + triage_13.json triages[6]）：
- find_player(arg)：全局查在线玩家，无 API -> 测试 monkeypatch 局部桩
- relay_emote(me, verb)：NPC 感知回调，无 API -> 测试 monkeypatch 局部桩
- message facade：用预建 tell_object/tell_room 收集副作用消息
- ANSI CYN/NOR/normal_color：预建空串 + strip_ansi
- wizardp：预建桩（默认 False）
- env/invisibility：未建模 -> 测试 monkeypatch query_env_invisibility 局部桩
- INTERMUD_MUD_NAME（channel_emote==3）：跨 Mud 单机排除，跳过 intermud 分支
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.stubs import (
    strip_ansi,
    tell_object,
    tell_room,
    wizardp,
)

from xkx.runtime.components import Identity
from xkx.runtime.pronoun import (
    gender_pronoun,
    gender_self,
    visible,
)
from xkx.runtime.query import environment, find_in_room
from xkx.runtime.title import (
    query_close,
    query_respect,
    query_rude,
    query_self,
    query_self_close,
    query_self_rude,
)

# emote 定义表：pattern -> 各段消息模板（对照 emoted.c emote mapping）。
# myself/target/others 三段，每段可带 _self/_target 后缀（对照 L124/140/154）。
# 真实由 F_SAVE 从 DATA_DIR/emoted 存档加载；此处用测试注入的最小表。
EmoteTable = dict[str, dict[str, str]]


def _entity_name(world: Any, eid: int) -> str:
    """取实体裸名（对照 LPC me->name()，emote 用裸名非 short）。"""
    ident = world.get(eid, Identity)
    return ident.name if ident else ""


def _is_character(world: Any, eid: int) -> bool:
    """是否角色（对照 LPC target->is_character()，greenfield 用 Identity 存在判定）。"""
    return world.get(eid, Identity) is not None


def _replace_pronouns(
    s: str,
    *,
    myname: str,
    my_gender: str,
    targetname: str | None,
    target_gender: str | None,
    world: Any,
    me_eid: int,
    target_eid: int | None,
    self_pronoun_is_self: bool,
) -> str:
    """对消息模板做 $X 代词替换（对照 L125-136 / L141-150 / L155-166）。

    myself 段：$P=gender_self(my_gender)（emoter 看自己=你），$p=gender_pronoun
    target 段：$P=gender_pronoun(my_gender)（target 看 emoter），$p=gender_self
    others 段：$P=gender_pronoun(my_gender)，$p=gender_pronoun(target_gender)

    self_pronoun_is_self=True 表示 $P 用 gender_self（myself 段），
    False 表示 $P 用 gender_pronoun（target/others 段）。
    target 段的 $p 用 gender_self(target_gender)，其余段 $p 用 gender_pronoun。
    """
    s = s.replace("$N", myname)
    if self_pronoun_is_self:
        s = s.replace("$P", gender_self(my_gender))
    else:
        s = s.replace("$P", gender_pronoun(my_gender))
    s = s.replace("$S", query_self(world, me_eid))
    s = s.replace("$s", query_self_rude(world, me_eid))
    if target_eid is not None and targetname is not None:
        s = s.replace("$C", query_self_close(world, me_eid, target_eid))
        s = s.replace("$c", query_close(world, me_eid, target_eid))
        s = s.replace("$R", query_respect(world, target_eid))
        s = s.replace("$r", query_rude(world, target_eid))
        s = s.replace("$n", targetname)
        # $p：target 段用 gender_self(target_gender)，myself/others 段用
        # gender_pronoun(target_gender)。caller 通过 self_pronoun_is_self
        # 复用同一标志不成立，故 target 段单独传 use_self_p_for_target。
        s = s.replace("$p", gender_pronoun(target_gender or "男性"))
    return s


def _replace_target_section(
    s: str,
    *,
    myname: str,
    my_gender: str,
    targetname: str,
    target_gender: str,
    world: Any,
    me_eid: int,
    target_eid: int,
) -> str:
    """target 段替换（对照 L141-150）：$P=gender_pronoun(my_gender)，
    $p=gender_self(target_gender)。
    """
    s = s.replace("$N", myname)
    s = s.replace("$P", gender_pronoun(my_gender))
    s = s.replace("$S", query_self(world, me_eid))
    s = s.replace("$s", query_self_rude(world, me_eid))
    s = s.replace("$C", query_self_close(world, me_eid, target_eid))
    s = s.replace("$c", query_close(world, me_eid, target_eid))
    s = s.replace("$R", query_respect(world, target_eid))
    s = s.replace("$r", query_rude(world, target_eid))
    s = s.replace("$n", targetname)
    s = s.replace("$p", gender_self(target_gender))
    return s


def do_emote(
    world: Any,
    emote: EmoteTable,
    me_eid: int,
    verb: str,
    arg: str | None = None,
    channel_emote: int = 0,
    *,
    find_player: Any = None,
    relay_emote: Any = None,
    query_env_invisibility: Any = None,
) -> int | str:
    """emoted.c:do_emote 迁移（对照 L79-175）。

    参数：
    - world：ECS 世界
    - emote：emote 定义表（pattern -> 段模板），测试注入
    - me_eid：emoter 实体 id
    - verb：emote 动词（如 "smile"）
    - arg：目标参数（如 "someone"），无目标传 None/空串
    - channel_emote：0=本地 / 2=rumor / 3=intermud（1=chat）
    - find_player/relay_emote/query_env_invisibility：B 类缺口桩，测试注入

    返回：本地成功 1 / 失败 0；频道成功 others 消息串 / 失败 0。

    副作用消息（本地非频道）通过预建 tell_object/tell_room 收集到
    world.pending_messages（facade 写全局缓冲，测试可 monkeypatch 精确路由）。
    """
    # L84：!environment(me) return 0
    room_id = environment(world, me_eid)
    if room_id is None:
        return 0

    # L86：emote 表无此 verb return 0
    if not isinstance(emote, dict) or verb not in emote:
        return 0

    # L88-93：myname 三路
    # channel_emote==2 或（非频道且 wizard 且 env/invisibility）-> "某人"
    # channel_emote==3 intermud -> name(id@mud)（单机排除，跳过）
    # else -> name()
    invis = False
    if not channel_emote and query_env_invisibility is not None:
        invis = wizardp(world, me_eid) and bool(query_env_invisibility(world, me_eid))
    if channel_emote == 2 or invis:
        myname = "某人"
    elif channel_emote == 3:
        # intermud 跨 Mud 单机排除（收缩约束 1），本地不依赖，跳过格式化
        # 仍取裸名占位（单机无 INTERMUD_MUD_NAME）
        myname = _entity_name(world, me_eid)
    else:
        myname = _entity_name(world, me_eid)

    # L96-114：目标解析
    target_eid: int | None = None
    target_gender: str | None = None
    msg_postfix = ""

    if arg is not None and arg != "":
        # L97：present(arg, environment(me))
        target_eid = find_in_room(world, room_id, arg)
        if target_eid is None:
            # L100-101：非频道仅在环境内找，找不到 return 0
            if not channel_emote:
                return 0
            # L102-103：频道 find_player(arg)
            if find_player is not None:
                target_eid = find_player(world, arg)
            if target_eid is None:
                return 0

        # L106-107：!is_character || !visible -> notify_fail
        if not _is_character(world, target_eid) or not visible(me_eid, target_eid, world):
            # notify_fail("你要对谁做这个动作？\\n") -> 本地 return 0
            return 0

        target_gender = _query_gender(world, target_eid)
        # L110-113：target==me -> _self（target 清零）；else _target
        if target_eid == me_eid:
            msg_postfix = "_self"
            target_eid = None
        else:
            msg_postfix = "_target"
    else:
        msg_postfix = ""

    # L116：my_gender
    my_gender = _query_gender(world, me_eid)

    # L117-122：targetname（intermud 三路单机简化为裸名）
    targetname: str | None = None
    if target_eid is not None:
        targetname = _entity_name(world, target_eid)

    # 三段消息渲染 + 输出
    # L124-138：myself 段（emoter 自己看）
    myself_tmpl = emote[verb].get("myself" + msg_postfix)
    if isinstance(myself_tmpl, str):
        str_myself = _replace_pronouns(
            myself_tmpl,
            myname=myname,
            my_gender=my_gender,
            targetname=targetname,
            target_gender=target_gender,
            world=world,
            me_eid=me_eid,
            target_eid=target_eid,
            self_pronoun_is_self=True,
        )
        if not channel_emote:
            # L137：message("emote", CYN+normal_color(str)+NOR, me)
            # 颜色码 CYN/NOR 预建空串（stubs 无 CYN，颜色内核砍掉），
            # normal_color=strip_ansi；输出即 strip_ansi(str)
            tell_object(world, me_eid, strip_ansi(str_myself))

    # L140-152：target 段（被 emote 的目标看）
    if target_eid is not None:
        target_tmpl = emote[verb].get("target")
        if isinstance(target_tmpl, str):
            str_target = _replace_target_section(
                target_tmpl,
                myname=myname,
                my_gender=my_gender,
                targetname=targetname or "",
                target_gender=target_gender or "男性",
                world=world,
                me_eid=me_eid,
                target_eid=target_eid,
            )
            if not channel_emote:
                # L151：message("emote", CYN+normal_color(str)+NOR, target)
                tell_object(world, target_eid, strip_ansi(str_target))

    # L154-169：others 段（房间其他人看 / 频道返回）
    others_tmpl = emote[verb].get("others" + msg_postfix)
    if isinstance(others_tmpl, str):
        str_others = _replace_pronouns(
            others_tmpl,
            myname=myname,
            my_gender=my_gender,
            targetname=targetname,
            target_gender=target_gender,
            world=world,
            me_eid=me_eid,
            target_eid=target_eid,
            self_pronoun_is_self=False,
        )
        if not channel_emote:
            # L167：message("emote", ..., environment(me), ({me, target}))
            exclude = (me_eid,) + ((target_eid,) if target_eid is not None else ())
            tell_room(world, room_id, strip_ansi(str_others), exclude)
        else:
            # L168：频道 return normal_color(str)
            return strip_ansi(str_others)

    # L172：target->relay_emote(me, verb)（NPC 感知回调）
    if target_eid is not None and relay_emote is not None:
        relay_emote(world, target_eid, me_eid, verb)

    # L174：本地成功 return 1
    return 1


def _query_gender(world: Any, eid: int) -> str:
    """取实体性别（对照 me->query("gender")）。"""
    from xkx.runtime.components import Attributes

    attrs = world.get(eid, Attributes)
    return attrs.gender if attrs else "男性"
