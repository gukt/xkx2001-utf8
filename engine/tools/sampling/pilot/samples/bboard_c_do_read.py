"""pilot 样本 id=9：inherit/misc/bboard.c:do_read 迁移代码。

对照 LPC inherit/misc/bboard.c L167-230，在 engine 现有 dbase/权限基础上
迁移读帖主路径 + 关键门控到行为等价。本文件为一次性测量代码，不污染
src/xkx（ADR-0048 决策 8）。

B 类架构缺口（board/留言板子系统整体未迁移）按简化建议处理：
- bboard 物品 dbase(board_id/notes/wizard_only/poster_family 无 ItemComp)
  -> 样本特有 BoardItem 数据结构（测试构造注入）
- per-object save/restore(F_SAVE) -> 简化为读帖主路径不依赖存档，跳过
- board_last_read 玩家读帖记录 -> 样本特有 BoardLastRead 组件（存 world）
- tune/open channels -> 跳过（频道系统后置 channeld，do_read 主流程不依赖）
- cmp_wiz_level -> 样本特有桩，默认用 WizLevel 枚举序比较（测试可 monkeypatch）
- sscanf/sprintf/ctime/pointerp/stringp/mapp/undefinedp/sizeof -> Python trivial
- start_more -> 预建桩（stubs.py）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from tools.sampling.pilot.stubs import start_more

from xkx.runtime.capability import WizLevel
from xkx.runtime.commands import Game
from xkx.runtime.query import query


@dataclass
class Note:
    """单条留言（对照 LPC notes[i] mapping：title/author/time/msg）。"""

    title: str = ""
    author: str = ""
    time: int = 0
    msg: str = ""


@dataclass
class BoardItem:
    """bboard 物品自身 dbase 承载（对照 bboard.c query 结果）。

    greenfield 无 ItemComp，本结构为样本特有桩，承载 board_id/notes/
    wizard_only/poster_family 四个 LPC 物品 dbase key。
    """

    board_id: str = ""
    notes: list[Note] = field(default_factory=list)
    wizard_only: bool = False
    poster_family: str | None = None


@dataclass
class BoardLastRead:
    """玩家读帖记录（对照 LPC me->query(\"board_last_read\") mapping）。

    greenfield 无该 dbase key 映射（unknown 会 raise DbaseKeyError），
    本组件为样本特有桩，存 board_id -> 最后阅读时间戳。
    """

    records: dict[str, int] = field(default_factory=dict)


def cmp_wiz_level(world: Any, eid: int, level_str: str) -> int:
    """SECURITY_D->cmp_wiz_level 桩（对照 bboard.c L184/196）。

    LPC 返回玩家等级与 level_str 的比较结果 -1/0/1（<0 表示玩家等级低于
    level_str）。greenfield 有 WizLevel 枚举层次（capability.py:39）但无
    cmp_wiz_level 函数；本桩从实体 capability token 或默认 PLAYER 取等级，
    用枚举声明序比较。测试可 monkeypatch 覆盖以构造巫师/凡人场景。

    真实：需从 session CapabilityToken.status 取玩家 wiz 等级，再做序比较。
    """
    player_level = _entity_wiz_level(world, eid)
    try:
        target = WizLevel(level_str)
    except ValueError:
        # LPC 未知等级字符串默认按最低处理（cmp_wiz_level 对非法 level 返回 >=0）
        target = WizLevel.PLAYER
    return _compare_wiz_level(player_level, target)


def _entity_wiz_level(world: Any, eid: int) -> WizLevel:
    """取实体巫师等级（样本桩：默认 PLAYER，测试 monkeypatch 覆盖）。"""
    return WizLevel.PLAYER


def _compare_wiz_level(a: WizLevel, b: WizLevel) -> int:
    """两 WizLevel 枚举序比较，返回 -1/0/1（对齐 LPC cmp_wiz_level 返回契约）。"""
    order = list(WizLevel)
    ia, ib = order.index(a), order.index(b)
    if ia < ib:
        return -1
    if ia > ib:
        return 1
    return 0


def _player_family(world: Any, eid: int) -> str:
    """取玩家门派 family_name（对照 bboard.c L191 me->query(\"family\")）。

    LPC query(\"family\") 返回 mapping 再取 fam[\"family_name\"]；greenfield
    已映射 Attributes.family 为 str（family_name 同义，dbase_map.py:54），
    直接返回 str。
    """
    fam = query(world, eid, "family")
    if isinstance(fam, str):
        return fam
    return ""


def _get_last_read(world: Any, eid: int) -> dict[str, int]:
    """取玩家 board_last_read 记录（对照 bboard.c L178）。

    桩：从 BoardLastRead 组件取，无则视为空 mapping（LPC undefinedp 分支）。
    """
    rec = world.get(eid, BoardLastRead)
    return dict(rec.records) if rec is not None else {}


def _set_last_read(world: Any, eid: int, records: dict[str, int]) -> None:
    """写玩家 board_last_read 记录（对照 bboard.c L224-227）。"""
    rec = world.get(eid, BoardLastRead)
    if rec is None:
        rec = BoardLastRead()
        world.add(eid, rec)
    rec.records = dict(records)


def _format_note_header(num: int, note: Note) -> str:
    """组装留言显示头（对照 bboard.c L216-218 sprintf）。

    LPC: \"[%d] %-40s %s(%s)\\n---...\\n\" + msg，
    ctime(time)[0..9] 取日期段（\"Day Mon DD\"）。
    """
    date_seg = time.ctime(note.time)[0:10]
    header = (
        f"[{num}] {note.title:<40} {note.author}({date_seg})\n"
        "----------------------------------------------------------------------\n"
    )
    return header + note.msg


def bboard_c_do_read(
    game: Game, actor_id: int, board: BoardItem, arg: str | None
) -> list[str]:
    """bboard.c:do_read 迁移（对照 inherit/misc/bboard.c L167-230）。

    返回 actor 可见消息列表（start_more 桩返回 [msg]，失败分支返回单条提示）。
    LPC notify_fail 失败语义改为返回单元素消息列表（命令框架吸收）。
    tune_channels/open_channels 频道副作用跳过（后置 channeld）。
    """
    world = game.world

    # L176：this_player()
    the_player = actor_id

    # L178：last_read_time = the_player->query("board_last_read")
    last_read_time = _get_last_read(world, the_player)
    # L179-180：myid / notes（board 物品自身 dbase）
    myid = board.board_id
    notes = board.notes

    # L182-185：wizard_only 门控
    # LPC arc = query("wizard_only")；非空且玩家等级低于 (immortal) -> 拒绝
    if board.wizard_only and cmp_wiz_level(world, the_player, "(immortal)") < 0:
        return ["内部通讯不得窥视。\n"]

    # L187-188：notes 空检查（pointerp(notes) && sizeof(notes)）
    if not isinstance(notes, list) or len(notes) == 0:
        return ["留言板上目前没有任何留言。\n"]

    # L190-198：poster_family 门控
    family = board.poster_family
    fam = _player_family(world, the_player)
    # LPC: stringp(family) && cmp_wiz_level(player,"(immortal)")<0
    #       && (!mapp(fam) || fam["family_name"] != family)
    # greenfield fam 为 str（family_name），mapp(fam) 恒 False 会反转行为，
    # 故按 LPC 语义改写：玩家非 immortal 且门派不匹配 -> 拒绝
    if (
        isinstance(family, str)
        and cmp_wiz_level(world, the_player, "(immortal)") < 0
        and fam != family
    ):
        return ["非本派弟子不得窥视本派内部通讯。\n"]

    # L200：arg 空检查
    if not arg:
        return ["指令格式：read <留言编号>|new|next\n"]

    num: int
    # L201-207：new/next 分支，定位第一张未读留言
    # LPC for(num=1; num<=sizeof(notes); num++) if(notes[num-1]["time"]
    # > last_read_time[myid]) break; -- 找到则 num=该帖号，否则循环退出时
    # num=sizeof(notes)+1（越界，后续报"没有这张留言"，即所有帖都已读）
    if arg == "new" or arg == "next":
        if not isinstance(last_read_time, dict) or myid not in last_read_time:
            num = 1
        else:
            num = len(notes) + 1  # 默认越界：全读时无未读
            for i in range(1, len(notes) + 1):
                if notes[i - 1].time > last_read_time[myid]:
                    num = i
                    break
    # L209-210：sscanf(arg, "%d", num) 失败分支
    else:
        try:
            num = int(arg)
        except (ValueError, TypeError):
            return ["你要读第几张留言？\n"]

    # L212-213：num 越界检查
    if num < 1 or num > len(notes):
        return ["没有这张留言。\n"]

    # L214：转为 0 基下标
    num -= 1

    # L215：tune_channels()（频道副作用，后置 channeld，跳过）

    # L216-219：start_more 显示留言正文
    msg = _format_note_header(num + 1, notes[num])
    result = start_more(msg)

    # L220：open_channels()（频道副作用，后置 channeld，跳过）

    # L222-227：更新 board_last_read
    note_time = notes[num].time
    if not isinstance(last_read_time, dict):
        # L223-224：last_read_time 非 mapping -> 整体重置
        _set_last_read(world, the_player, {myid: note_time})
    else:
        # L226-227：myid 缺失或当前 time 更大 -> 更新该 board 记录
        if myid not in last_read_time or note_time > last_read_time[myid]:
            last_read_time[myid] = note_time
            _set_last_read(world, the_player, last_read_time)

    return result
