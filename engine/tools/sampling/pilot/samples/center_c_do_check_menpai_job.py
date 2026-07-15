"""pilot 样本 id=2：d/wizard/center.c:do_check_menpai_job 迁移代码。

对照 LPC d/wizard/center.c L199-628。该函数对 11 个门派（武当/星宿/华山/
桃花/丐帮/峨嵋/白驼/全真/雪山/大理/少林）做结构完全相同的重复处理：解析
门派开关参数 -> 加载 job_data 单例 -> 每个选中门派查 query_family_jobdata
（统计）+ choose_of_player(family,"good"/"bad")（贡献度 top/bottom 玩家）
-> start_more 分页显示。11 段同构逻辑去重为参数化循环。

B 类架构缺口（整体未迁移子系统）：
- 门派任务(job)子系统：job_data 数据对象的 query_family_jobdata /
  choose_of_player / restore 三方法全无对应实现（runtime/family.py 仅有
  FamilyBonus 门派战斗加成，无任务/贡献度模型）。本样本以模块级可替换引用
  承接，测试 monkeypatch 注入样本特有桩。
- LPC 路径寻址对象模型：find_object(JOB_DIR+"job_data") / new(...) 是按
  LPC 路径字符串找/实例化单例数据对象，新引擎实体系统用 entity_id 而非
  路径，无对应语义。回落为占位 JobData 实例。
- start_more 分页显示（全引擎无 pager）：用预建桩 start_more 返回 [msg]。
- can_used 巫师门控：依赖 this_player()->query("id") 白名单
  （server/poke/xuanyuan）+ wizardp。新引擎 "id" 在 POSTPONED_KEYS（query
  返回 None），改读 Identity.prototype_id 近似 id；wizardp 用预建桩。

本文件为一次性测量代码，不污染 src/xkx（ADR-0048 决策 8）。
"""

from __future__ import annotations

from typing import Any, Protocol

from tools.sampling.pilot.stubs import HBBLU, HIR, HIY, NOR, start_more, wizardp

from xkx.runtime.commands import Game
from xkx.runtime.components import Identity

# 门派开关参数 -> 门派中文名对照表（L215-225 switch 的 11 个 case）。
# 顺序对应 LPC 源码声明顺序，去重后参数化循环遍历。
_MENPAI_OPTIONS: list[tuple[str, str]] = [
    ("-wudang", "武当派"),
    ("-xingxiu", "星宿派"),
    ("-huashan", "华山派"),
    ("-taohua", "桃花岛"),
    ("-gaibang", "丐帮"),
    ("-emei", "峨嵋派"),
    ("-baituo", "白驼山"),
    ("-quanzhen", "全真教"),
    ("-xueshan", "雪山派"),
    ("-dali", "大理段家"),
    ("-shaolin", "少林派"),
]

# LPC center.c L12：版权头字符串（ANSI 颜色码已回落空串）。
_COPYRIGHT = HBBLU + HIY + "游戏主动性任务察看器1.0版     Server 2001年7月     \n" + NOR


class JobDataLike(Protocol):
    """job_data 数据对象最小契约（样本特有桩实现本接口）。

    对照 LPC /clone/obj/job/job_data 的三个方法：
    - restore() -> None：从存档恢复（新引擎无 job_data 单例存档语义，桩 no-op）
    - query_family_jobdata(family) -> str：门派任务完成统计文本
    - choose_of_player(family, kind) -> list[str]：贡献度 top/bottom 玩家名
    """

    def restore(self) -> None: ...

    def query_family_jobdata(self, family: str) -> str: ...

    def choose_of_player(self, family: str, kind: str) -> list[str]: ...


# job_data 单例获取器（可被测试 monkeypatch 替换）。
# 对照 LPC L232-233：find_object(JOB_DIR+"job_data") || new(JOB_DIR+"job_data")。
# 新引擎无路径寻址对象模型，回落 None；测试注入样本特有桩。
_job_data_provider: Any = None


def _get_job_data() -> JobDataLike | None:
    """获取 job_data 单例（对照 L232-234 find_object/new + objectp 检查）。

    新引擎无 LPC 路径寻址对象模型，_job_data_provider 为 None 时返回 None
    （对应 LPC find_object/new 均失败的 L234 return 0）。测试 monkeypatch
    注入 _job_data_provider 返回样本特有桩。
    """
    if _job_data_provider is None:
        return None
    return _job_data_provider()


def _actor_id(world: Any, eid: int) -> str:
    """取 actor 的 id（对照 can_used L129 this_player()->query("id")）。

    新引擎 "id" 在 POSTPONED_KEYS（query 返回 None），回落读
    Identity.prototype_id 近似 LPC id（玩家 def id）。无 Identity 返回空串。
    """
    ident = world.get(eid, Identity)
    return ident.prototype_id if ident else ""


def can_used(world: Any, actor_id: int) -> list[str] | None:
    """can_used 迁移（对照 center.c L124-138）。

    返回 None 表示通过；返回 list[str] 表示失败消息（对应 LPC notify_fail +
    return 0）。L129-133 id 白名单（server/poke/xuanyuan）+ L134 wizardp
    双门控。wizardp 用预建桩（回落 False）。
    """
    actor_id_val = _actor_id(world, actor_id)
    if actor_id_val not in ("server", "poke", "xuanyuan"):
        return ["任务控制系统目前只能由高级巫师来控制。\n"]
    if not wizardp(world, actor_id):
        return ["你还没有获得神仙的法力，无法控制这里。\n"]
    return None


def _format_menpai(
    job_data: JobDataLike, family: str, good: list[str], bad: list[str]
) -> str:
    """单个门派的贡献度展示格式化（对照 L237-269 武当段，11 段同构去重）。

    good/bad 分别为 choose_of_player(family,"good"/"bad") 返回的玩家名列表。
    注意 LPC good 段（L241-254）空列表消息无前导换行，bad 段（L256-269）
    多/单列表消息带前导换行 "\n"（L261/267）；good 多列表同样无前导换行。
    """
    # L239：统计文本
    msg = job_data.query_family_jobdata(family)

    # L240-254：good（贡献度最高）
    if not good:
        # L242：HIR + "这个门派没有完成任务的完家。\n" + NOR
        # （LPC 原文"完家"为"玩家"笔误，行为等价保留原文）
        msg += HIR + "这个门派没有完成任务的完家。\n" + NOR
    elif len(good) != 1:
        msg += "这个门派有数个贡献度最高的玩家，他们分别是：\n"
        for name in good:
            msg += name + "\t"
    else:
        msg += "这个门派贡献度最高的玩家是：\n"
        msg += good[0] + "\n"

    # L255-269：bad（贡献度最低），多/单列表消息带前导换行
    if not bad:
        msg += HIR + "这个门派没有完成任务的完家。\n" + NOR
    elif len(bad) != 1:
        msg += "\n这个门派有数个贡献度最低的玩家，他们分别是：\n"
        for name in bad:
            msg += name + "\t"
    else:
        msg += "\n这个门派贡献度最低的玩家是：\n"
        msg += bad[0] + "\n"

    return msg


def do_check_menpai_job(game: Game, actor_id: int, arg: str | None) -> list[str]:
    """center.c:do_check_menpai_job 迁移（对照 L199-628）。

    返回 actor 可见消息列表。LPC this_player()->start_more(msg) 分页显示的
    副作用用预建桩 start_more(msg) 承接（返回 [msg]，命令返回值占位）。
    """
    world = game.world

    # L204-205：无参数 -> 格式提示
    if not arg:
        return ["格式check_menpai_job -menpai_name。\n"]

    # L206-207：can_used 巫师门控（返回失败消息则直接返回）
    fail = can_used(world, actor_id)
    if fail is not None:
        return fail

    # L210-230：参数解析（explode 按空格拆分，逆序遍历 switch 设门派开关）
    # default 分支：任意非门派参数 -> "你要查什么门派?"
    option = arg.split(" ")
    # LPC 逆序 while(i--) 遍历，顺序不影响开关集合，用集合判定
    selected: set[str] = set()
    for tok in option:
        matched = False
        for flag, _family in _MENPAI_OPTIONS:
            if tok == flag:
                selected.add(flag)
                matched = True
                break
        if not matched:
            # L227-228 default 分支
            return ["你要查什么门派?\n"]

    # L232-234：加载 job_data 单例（find_object/new + objectp 检查）
    job_data = _get_job_data()
    if job_data is None:
        # 对应 LPC objectp(job_data) 为假 return 0（命令返回空）
        return []

    # L235：restore 从存档恢复（样本特有桩 no-op）
    job_data.restore()

    # L236：拼版权头
    msg = _COPYRIGHT

    # L237-622：11 段门派同构处理去重为参数化循环
    # 每段：query_family_jobdata(统计) + choose_of_player good/bad +
    # 格式化 + start_more(msg) 分页。LPC 每段末尾各调一次 start_more，
    # 多门派选中时 start_more 被多次调用（每次带累积 msg）。
    for flag, family in _MENPAI_OPTIONS:
        if flag not in selected:
            continue
        good = job_data.choose_of_player(family, "good")
        bad = job_data.choose_of_player(family, "bad")
        msg += _format_menpai(job_data, family, good, bad)
        # L270/306/...：this_player()->start_more(msg)
        # 引擎消息推送后置 M3，用预建桩承接（返回 [msg] 占位）
        start_more(msg)

    # L626：return 1（命令成功，返回累积 msg）
    return [msg]
