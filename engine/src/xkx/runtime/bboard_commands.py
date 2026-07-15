"""bboard 命令层：do_read / do_list / do_discard（ADR-0059 务实合一）。

对照 LPC ``inherit/misc/bboard.c`` 的 do_read(L167-230) / do_list(L73-93) /
do_discard(L233-253)，在引擎层 DaemonStore + BboardData + BoardLastRead +
cmp_wiz_level 基础上迁移，与 pilot 样本 ``bboard_c_do_read.py`` 行为等价。

本模块是权威实现（ADR-0059 合一）：后续迁移用引擎层，不各自 monkeypatch。
pilot 样本保留作历史记录（ADR-0056 决策 2）。

设计（D4/D5）：

- 函数族模式（类比 [items.py](items.py)），签名 ``(game, ctx, board) -> list[str]``。
  ``board`` 由调用方从 ``daemon_store`` 取后传入（解耦 board 来源解析）。
- arg 从 ``ctx.raw_args`` 取（对齐 commands.py 现有命令取参模式）。
- ``cmp_wiz_level(ctx.capability_token, level_str)`` 做权限门控（fail-closed，
  token=None 返回 -1 视为最低等级）。
- ``BoardLastRead`` 组件（per-player）存取读帖记录；``BboardData`` 是 daemon
  单例（per-board），二者不混（不变量 3）。
- 失败语义：LPC ``notify_fail`` 改返回单元素消息列表（对齐 pilot 已验证模式）。
- ``tune_channels`` / ``open_channels`` 频道副作用跳过（channeld 后置）。
- ``start_more``：引擎层内联 ``return [msg]``（对齐 LPC ``start_more``，真实
  pager 后置 M3）。
- ``do_discard`` save 走 ``DaemonStore.save``（原子写，不走 dirty-flag，不变量 2）。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from xkx.runtime.action_context import ActionContext
from xkx.runtime.capability import cmp_wiz_level
from xkx.runtime.components import Attributes, BoardLastRead, Identity
from xkx.runtime.daemons.bboard import BboardData, Note

if TYPE_CHECKING:
    from xkx.runtime.commands import Game
    from xkx.runtime.ecs import World

_logger = logging.getLogger(__name__)


# ──────────────────────── 内部辅助 ────────────────────────


def _format_note_header(num: int, note: Note) -> str:
    """组装留言显示头（对照 bboard.c L216-218 sprintf）。

    LPC: ``[%d] %-40s %s(%s)\\n---...\\n`` + msg，
    ``ctime(time)[0..9]`` 取日期段（``Day Mon DD``）。
    """
    date_seg = time.ctime(note.time)[0:10]
    header = (
        f"[{num}] {note.title:<40} {note.author}({date_seg})\n"
        "----------------------------------------------------------------------\n"
    )
    return header + note.msg


def _start_more(msg: str) -> list[str]:
    """start_more 内联桩（对照 LPC ``this_player()->start_more``）。

    全引擎无 pager，返回 ``[msg]`` 包装（真实客户端层 pager 后置 M3）。
    对齐 pilot ``stubs.start_more`` 行为。
    """
    return [msg]


def _player_family(world: World, eid: int) -> str:
    """取玩家门派 family_name（对照 bboard.c L191 ``me->query("family")``）。

    greenfield 已映射 ``Attributes.family`` 为 str（family_name 同义）。
    """
    attrs = world.get(eid, Attributes)
    return attrs.family if attrs else ""


def _get_last_read(world: World, eid: int) -> dict[str, int]:
    """取玩家 board_last_read 记录（对照 bboard.c L178）。

    无 BoardLastRead 组件时返回空 dict（LPC ``undefinedp`` 分支）。
    返回副本，调用方修改不影响原组件（写回用 ``_set_last_read``）。
    """
    rec = world.get(eid, BoardLastRead)
    return dict(rec.records) if rec is not None else {}


def _set_last_read(world: World, eid: int, records: dict[str, int]) -> None:
    """写玩家 board_last_read 记录（对照 bboard.c L224-227）。"""
    rec = world.get(eid, BoardLastRead)
    if rec is None:
        rec = BoardLastRead()
        world.add(eid, rec)
    rec.records = dict(records)


def _author_signature(world: World, eid: int) -> str:
    """构造作者签名 ``name(id)``（对照 bboard.c L244 ``this_player(1)->name()
    +"("+query("id")+")"``）。

    greenfield 用 Identity.name + Identity.prototype_id（LPC query("id") 等价）。
    无 Identity 组件返回空串（不匹配任何 author）。
    """
    ident = world.get(eid, Identity)
    if ident is None:
        return ""
    return f"{ident.name}({ident.prototype_id})"


def _take_arg(ctx: ActionContext) -> str:
    """从 ctx 取参数（对齐 commands.py go/look 取参模式）。

    优先 raw_args.strip()，空则回退 parsed_args[0]。
    """
    arg = ctx.raw_args.strip()
    if not arg and ctx.parsed_args:
        arg = ctx.parsed_args[0]
    return arg


# ──────────────────────── do_read ────────────────────────


def do_read(game: Game, ctx: ActionContext, board: BboardData) -> list[str]:
    """读帖（对照 bboard.c L167-230，从 pilot 样本迁移，行为等价）。

    返回 actor 可见消息列表（start_more 包装，失败分支返回单条提示）。
    ``tune_channels`` / ``open_channels`` 频道副作用跳过（后置 channeld）。
    """
    world = game.world
    actor = ctx.actor
    token = ctx.capability_token

    # L178-180：last_read_time / myid / notes
    last_read_time = _get_last_read(world, actor)
    myid = board.board_id
    notes = board.notes

    # L182-185：wizard_only 门控
    if board.wizard_only and cmp_wiz_level(token, "(immortal)") < 0:
        return ["内部通讯不得窥视。\n"]

    # L187-188：notes 空检查（pointerp(notes) && sizeof(notes)）
    if not isinstance(notes, list) or len(notes) == 0:
        return ["留言板上目前没有任何留言。\n"]

    # L190-198：poster_family 门控
    family = board.poster_family
    fam = _player_family(world, actor)
    # LPC: stringp(family) && cmp_wiz_level(player,"(immortal)")<0
    #       && (!mapp(fam) || fam["family_name"] != family)
    # greenfield fam 为 str，玩家非 immortal 且门派不匹配 -> 拒绝
    if (
        isinstance(family, str)
        and cmp_wiz_level(token, "(immortal)") < 0
        and fam != family
    ):
        return ["非本派弟子不得窥视本派内部通讯。\n"]

    # L200：arg 空检查
    arg = _take_arg(ctx)
    if not arg:
        return ["指令格式：read <留言编号>|new|next\n"]

    num: int
    # L201-207：new/next 分支，定位第一张未读留言
    if arg == "new" or arg == "next":
        if not isinstance(last_read_time, dict) or myid not in last_read_time:
            num = 1
        else:
            # 默认越界：全读时无未读（循环退出 num=sizeof(notes)+1）
            num = len(notes) + 1
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
    result = _start_more(msg)

    # L220：open_channels()（频道副作用，后置 channeld，跳过）

    # L222-227：更新 board_last_read
    note_time = notes[num].time
    if not isinstance(last_read_time, dict):
        # L223-224：last_read_time 非 mapping -> 整体重置
        _set_last_read(world, actor, {myid: note_time})
    else:
        # L226-227：myid 缺失或当前 time 更大 -> 更新该 board 记录
        if myid not in last_read_time or note_time > last_read_time[myid]:
            last_read_time[myid] = note_time
            _set_last_read(world, actor, last_read_time)

    return result


# ──────────────────────── do_list ────────────────────────


def do_list(game: Game, ctx: ActionContext, board: BboardData) -> list[str]:
    """列帖（对照 bboard.c L73-93，无门控行为等价）。

    无参。列出所有 notes 的编号/标题/作者/日期，未读帖高亮（引擎层用 ``*``
    标记，LPC 用 HIY 颜色码，收缩约束砍颜色内核）。空板提示。

    行为等价：LPC do_list（L73-93）无 wizard_only/poster_family 门控--标题
    列表对所有人可见（``short``/``long``/``do_list`` 均无门控，读正文
    ``do_read`` 才检查权限）。引擎层严格对齐 LPC，不擅自补门控（行为等价是
    greenfield 硬约束；若需安全增强应独立 ADR 关联 dissent，非迁移职责）。
    """
    world = game.world
    actor = ctx.actor

    notes = board.notes

    # L82-83：notes 空检查（LPC do_list 无权限门控，标题列表公开）
    if not isinstance(notes, list) or len(notes) == 0:
        return ["留言板上目前没有任何留言。\n"]

    # L84：列表头（LPC 用 query("long")+query("name")，引擎层用 board_id 占位）
    msg = f"{board.board_id}上现有下列留言：\n------------------------\n"

    # L85-89：遍历 notes 列出，未读高亮
    last_read_time = _get_last_read(world, actor)
    last = last_read_time.get(board.board_id, 0)
    for i, note in enumerate(notes):
        unread = note.time > last
        # LPC: sprintf("%s[%2d]" NOR "  %-40s %12s (%s)\n", HIY|"", ...)
        # 引擎层 HIY/NOR 为空串，用 * 标记未读
        prefix = "*" if unread else " "
        date_seg = time.ctime(note.time)[0:16]
        msg += (
            f"{prefix}[{i + 1:2d}]  {note.title:<40} "
            f"{note.author:>12} ({date_seg})\n"
        )

    # L90：start_more 分页输出
    return _start_more(msg)


# ──────────────────────── do_discard ────────────────────────


def do_discard(game: Game, ctx: ActionContext, board: BboardData) -> list[str]:
    """删帖（对照 bboard.c L233-253）+ DaemonStore save 闭环（ADR-0057）。

    arg=编号。sscanf 解析数字，越界检查。权限检查：作者本人（``author ==
    name(id)`` 格式）或 caretaker+ 等级。删除后调 ``DaemonStore.save`` 主动
    同步存档（原子写，不走 dirty-flag，不变量 2）。
    """
    world = game.world
    actor = ctx.actor
    token = ctx.capability_token

    # L238：arg 空检查 + sscanf 解析
    arg = _take_arg(ctx)
    if not arg:
        return ["指令格式：discard <留言编号>\n"]

    try:
        num = int(arg)
    except (ValueError, TypeError):
        return ["指令格式：discard <留言编号>\n"]

    # L240-242：notes 检查 + num 越界检查
    notes = board.notes
    if not isinstance(notes, list) or num < 1 or num > len(notes):
        return ["没有这张留言。\n"]
    # L243：转为 0 基下标
    num -= 1

    # L244-246：权限检查（作者本人 或 caretaker+）
    author_sig = _author_signature(world, actor)
    if notes[num].author != author_sig and cmp_wiz_level(token, "(caretaker)") < 0:
        return ["这个留言不是你写的。\n"]

    # L248：删除 note（重组 notes 数组）
    board.notes = notes[:num] + notes[num + 1:]

    # L250：save 闭环（ADR-0057 per-object save，不走 dirty-flag）
    # daemon_store 是 world 动态属性，可能为 None（demo 未接）。
    # None 则跳过 save + 记 warning（对齐 LPC 无存档时 no-op）。
    store = getattr(world, "daemon_store", None)
    if store is not None:
        store.save(f"bboard_{board.board_id}")
    else:
        _logger.warning(
            "do_discard: daemon_store 未注入，跳过 save（board_id=%r）",
            board.board_id,
        )

    # L251：删除成功提示（num+1 恢复 1 基显示）
    return [f"删除第 {num + 1} 号留言....Ok。\n"]
