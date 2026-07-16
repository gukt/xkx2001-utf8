"""job_data 命令层：do_check_menpai_job / do_check_player / do_cut_job /
do_check_do_job（ADR-0061 决策 2）。

对照 LPC ``d/wizard/center.c`` L199-628 / L796-823 / L685-717 / L830-864，
在引擎层 DaemonStore + JobData + cmp_wiz_level 基础上迁移，
与 pilot 样本 ``center_c_do_check_menpai_job.py`` 行为等价。

设计（参照 bboard_commands.py ADR-0059）：

- 函数族模式（类比 [items.py](items.py) / [bboard_commands.py](bboard_commands.py)），
  签名 ``(game, ctx, job_data) -> list[str]``。``job_data`` 由调用方从
  ``daemon_store.get("job_data")`` 取后传入（解耦来源解析）。
- arg 从 ``ctx.raw_args`` 取（对齐 commands.py 现有命令取参模式）。
- 失败语义：LPC ``notify_fail`` 改返回单元素消息列表。
- ``start_more`` 内联 ``return [msg]``（对齐 bboard do_list，真实 pager 后置 M3）。
- ``do_cut_job`` save 走 ``DaemonStore.save``（原子写，不走 dirty-flag）。
- ``can_used`` 门控：``cmp_wiz_level`` + id 白名单 server/poke/xuanyuan。
- ``do_check_menpai_job`` 基于 pilot 样本正式化（11 门派同构去重为参数化循环）。

[ADR-0061](../../../docs/adr/ADR-0061-job-data-binary-source-equivalence.md)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from xkx.runtime.action_context import ActionContext
from xkx.runtime.capability import CapabilityToken, cmp_wiz_level
from xkx.runtime.components import Identity
from xkx.runtime.daemons.job_data import (
    COPYRIGHT,
    MENPAI_OPTIONS,
    JobData,
)

if TYPE_CHECKING:
    from xkx.runtime.commands import Game
    from xkx.runtime.ecs import World

_logger = logging.getLogger(__name__)


# ──────────────────────── 内部辅助 ────────────────────────


def _take_arg(ctx: ActionContext) -> str:
    """从 ctx 取参数（对齐 bboard_commands _take_arg）。

    优先 raw_args.strip()，空则回退 parsed_args[0]。
    """
    arg = ctx.raw_args.strip()
    if not arg and ctx.parsed_args:
        arg = ctx.parsed_args[0]
    return arg


def _can_used(
    world: World, actor: int, token: CapabilityToken | None
) -> list[str] | None:
    """can_used 门控（对照 center.c L124-138）。

    返回 None=通过，list[str]=失败消息（对应 LPC notify_fail + return 0）。
    L129-131 id 白名单（server/poke/xuanyuan）+ L134 wizardp 双门控。
    wizardp 映射 ``cmp_wiz_level(token, "(immortal)") >= 0``
    （immortal 及以上视为 wizard）。
    """
    ident = world.get(actor, Identity)
    actor_id = ident.prototype_id if ident else ""
    if actor_id not in ("server", "poke", "xuanyuan"):
        return ["任务控制系统目前只能由高级巫师来控制。\n"]
    if cmp_wiz_level(token, "(immortal)") < 0:
        return ["你还没有获得神仙的法力，无法控制这里。\n"]
    return None


def _start_more(msg: str) -> list[str]:
    """start_more 内联桩（对照 bboard_commands _start_more）。

    全引擎无 pager，返回 ``[msg]`` 包装（真实客户端层 pager 后置 M3）。
    """
    return [msg]


def _get_mapping(
    key: str, field: str, array: list[dict[str, Any]]
) -> dict[str, Any]:
    """从 array 中找 field 匹配 key 的 mapping（对照 lpc_math.h get_mapping）。

    lpc_math.h 源码缺失，从 center.c 调用方反推：
    ``get_mapping(player_name, "job_player", job_data->query_job_data())``
    -> 找 ``job_player == player_name`` 的条目。未找到返回空 dict
    （对照 center.c L813 ``sizeof(job_map)==0`` 检查）。
    """
    for item in array:
        if item.get(field) == key:
            return item
    return {}


def _p_map(mapping: dict[str, Any]) -> str:
    """格式化 mapping 为可读字符串（对照 lpc_math.h p_map）。

    lpc_math.h 源码缺失，从 center.c 调用方反推：
    ``msg += (p_map(job_map))``。推断为每行 ``key: value`` 格式
    （ADR-0061 决策 1 算法级不可逐行验证）。
    """
    if not mapping:
        return ""
    lines = [f"{k}: {v}" for k, v in mapping.items()]
    return "\n".join(lines) + "\n"


def _is_online(world: World, name: str) -> bool:
    """检查玩家是否在线（对照 center.c L824-828 is_online/find_player）。

    遍历有 Identity 组件的实体，查找 name 匹配。
    """
    for eid in world.entities_with(Identity):
        ident = world.get(eid, Identity)
        if ident and ident.name == name:
            return True
    return False


def _filter_online(
    world: World, names: list[str]
) -> list[str]:
    """过滤在线玩家列表（对照 center.c filter_array(:is_online:)）。"""
    return [n for n in names if _is_online(world, n)]


def _format_menpai(
    job_data: JobData, family: str, good: list[str], bad: list[str]
) -> str:
    """单个门派的贡献度展示格式化（对照 center.c L237-269，11 段同构去重）。

    good/bad 分别为 choose_of_player(family,"good"/"bad") 返回的玩家名列表。
    注意 LPC good 段（L241-254）空列表消息无前导换行，bad 段（L256-269）
    多/单列表消息带前导换行 ``\\n``（L261/267）；good 多列表同样无前导换行。
    LPC 原文"完家"为"玩家"笔误，行为等价保留原文。
    """
    # L239：统计文本（推断实现，ADR-0061 决策 1 算法级）
    msg = job_data.query_family_jobdata(family)

    # L240-254：good（贡献度最高）
    if not good:
        # L242：HIR + "这个门派没有完成任务的完家。\\n" + NOR
        msg += "这个门派没有完成任务的完家。\n"
    elif len(good) != 1:
        msg += "这个门派有数个贡献度最高的玩家，他们分别是：\n"
        for name in good:
            msg += name + "\t"
    else:
        msg += "这个门派贡献度最高的玩家是：\n"
        msg += good[0] + "\n"

    # L255-269：bad（贡献度最低），多/单列表消息带前导换行
    if not bad:
        msg += "这个门派没有完成任务的完家。\n"
    elif len(bad) != 1:
        msg += "\n这个门派有数个贡献度最低的玩家，他们分别是：\n"
        for name in bad:
            msg += name + "\t"
    else:
        msg += "\n这个门派贡献度最低的玩家是：\n"
        msg += bad[0] + "\n"

    return msg


# ──────────────────────── do_check_menpai_job ────────────────────────


def do_check_menpai_job(
    game: Game, ctx: ActionContext, job_data: JobData
) -> list[str]:
    """察看门派任务完成情况（对照 center.c L199-628）。

    基于 pilot 样本正式化（11 门派同构去重为参数化循环）。
    返回 actor 可见消息列表（start_more 包装，失败分支返回单条提示）。
    """
    world = game.world
    actor = ctx.actor
    token = ctx.capability_token

    # L204-205：无参数 -> 格式提示
    arg = _take_arg(ctx)
    if not arg:
        return ["格式check_menpai_job -menpai_name。\n"]

    # L206-207：can_used 巫师门控
    fail = _can_used(world, actor, token)
    if fail is not None:
        return fail

    # L210-230：参数解析（explode 按空格拆分，逆序遍历 switch 设门派开关）
    # default 分支：任意非门派参数 -> "你要查什么门派?"
    selected: set[str] = set()
    for tok in arg.split(" "):
        matched = False
        for flag, _family in MENPAI_OPTIONS:
            if tok == flag:
                selected.add(flag)
                matched = True
                break
        if not matched:
            # L227-228 default 分支
            return ["你要查什么门派?\n"]

    # L232-234：加载 job_data（由调用方传入）
    # L235：restore 从存档恢复（DaemonStore 管理下为 no-op）
    job_data.restore()

    # L236：拼版权头
    msg = COPYRIGHT

    # L237-622：11 段门派同构处理去重为参数化循环
    for flag, family in MENPAI_OPTIONS:
        if flag not in selected:
            continue
        good = job_data.choose_of_player(family, "good")
        bad = job_data.choose_of_player(family, "bad")
        msg += _format_menpai(job_data, family, good, bad)

    # L626：return 1（命令成功，返回累积 msg）
    return _start_more(msg)


# ──────────────────────── do_check_player ────────────────────────


def do_check_player(
    game: Game, ctx: ActionContext, job_data: JobData
) -> list[str]:
    """查找玩家任务执行情况（对照 center.c L796-823）。

    只读查询，无门控（LPC do_check_player 无 can_used 调用）。
    arg=玩家名。
    """
    # L802-805：arg 空检查 + sscanf 解析
    arg = _take_arg(ctx)
    if not arg:
        return ["do_check_player player_name。\n"]

    # L807-810：加载 job_data + restore
    job_data.restore()

    # L811：get_mapping(player_name, "job_player", query_job_data())
    job_map = _get_mapping(arg, "job_player", job_data.query_job_data())

    # L801/812：msg 初始为空格 + 拼版权头
    msg = " " + COPYRIGHT

    # L813-818：job_map 为空 -> 提示无信息
    if not job_map:
        msg += "没有这个player的信息。\n"
        return [msg]

    # L819：p_map(job_map) 格式化
    msg += _p_map(job_map)
    return [msg]


# ──────────────────────── do_cut_job ────────────────────────


def do_cut_job(
    game: Game, ctx: ActionContext, job_data: JobData
) -> list[str]:
    """删除玩家任务（对照 center.c L685-717）+ DaemonStore save 闭环。

    arg=玩家名（"all" 时重置全部）。删除后调 DaemonStore.save 主动
    同步存档（原子写，不走 dirty-flag，ADR-0057 不变量 2）。
    """
    world = game.world
    actor = ctx.actor
    token = ctx.capability_token

    # L691-692：can_used 门控
    fail = _can_used(world, actor, token)
    if fail is not None:
        return fail

    # L693-696：arg 空检查 + sscanf 解析
    arg = _take_arg(ctx)
    if not arg:
        return ["job_cut player_name。\n"]

    # L698-702：加载 job_data + restore
    job_data.restore()

    # L703-704：player_name=="all" -> reset()
    if arg == "all":
        job_data.reset()
        msg = ""
    else:
        # L707-711：拼消息 + get_mapping + detract_job_data
        msg = COPYRIGHT
        msg += f"你现在删除{arg}所有的任务\n"
        job_map = _get_mapping(
            arg, "job_player", job_data.query_job_data()
        )
        msg += _p_map(job_map)
        job_data.detract_job_data(arg)

    # L714：save 闭环（ADR-0057 per-object save，不走 dirty-flag）
    store = getattr(world, "daemon_store", None)
    if store is not None:
        store.save("job_data")
    else:
        _logger.warning(
            "do_cut_job: daemon_store 未注入，跳过 save（player=%r）",
            arg,
        )

    # L713：write(msg) -> return [msg]
    return [msg]


# ──────────────────────── do_check_do_job ────────────────────────


def do_check_do_job(
    game: Game, ctx: ActionContext, job_data: JobData
) -> list[str]:
    """查找所有在线玩家任务执行情况（对照 center.c L830-864）。

    只读查询，无门控（LPC do_check_do_job 无 can_used 调用）。
    分三组列出：已得到任务 / 正在执行任务 / 已完成任务。
    """
    world = game.world

    # L837-839：加载 job_data + restore
    job_data.restore()

    # L840-848：query_list + filter_array(is_online)
    finish_job = job_data.query_list("finish_job")
    if finish_job:
        finish_job = _filter_online(world, finish_job)

    ask_job = job_data.query_list("ask_job")
    if ask_job:
        # center.c L842：ask_job 过滤在线玩家
        ask_job = _filter_online(world, ask_job)

    oppose_job = job_data.query_list("oppose_pker")
    if oppose_job:
        oppose_job = _filter_online(world, oppose_job)

    # L849：拼版权头
    msg = COPYRIGHT

    # L850-853：已得到任务
    msg += "现在已经得到任务的人有:\n"
    for name in ask_job:
        msg += name + "\n"

    # L854-857：正在执行任务
    msg += "现在正在执行任务的人有:\n"
    for name in oppose_job:
        msg += name + "\n"

    # L858-861：已完成任务
    msg += "现在已经完成任务的人有:\n"
    for name in finish_job:
        msg += name + "\n"

    return [msg]
