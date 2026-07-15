"""pilot 样本 id=11：inherit/char/char.c:setup 迁移代码。

对照 LPC inherit/char/char.c L49-58（setup 函数体）+ adm/daemons/chard.c
L22-114（CHAR_D->setup_char 编排）。本文件为一次性测量代码，不污染 src/xkx
（ADR-0048 决策 8）。

char.c:setup 是角色 create() 之后配置"create 期未知属性"（living_name 等）
的入口，5 行编排：seteuid(getuid(this_object())) / set_heart_beat(1) /
tick = 5 + random(10) / enable_player() / CHAR_D->setup_char(this_object())。

CHAR_D->setup_char（chard.c L22-114）是 daemon 编排：8 种族 dispatch
（简化只 human，其余后置）+ dbase 兜底初始化（jing=max_jing / qi=max_qi /
jingli=max_jingli）+ eff 钳位 + 玩家 neili/jingli 超限钳位 + shen 公式 +
behavior_exp/quest_exp 兜底 + reset_action。

B 类架构缺口（简化测关键分支，effort.notes 记待迁移面）：
- set_living_name / find_living：living-name 注册全缺（enable_player 依赖项）
- CHAR_D 8 种族 daemon dispatch：只 human，其余 7 种族后置
- set_heart_beat per-object 开关 / per-object 非均匀 tick 计数器：新引擎全局
  tick 始终驱动，无 per-object 关闭/省 CPU；本样本用模块级表达开启+计数器
- reset_action 完整重算：用 stubs.reset_action no-op（equipment.py:103 仅 wield
  时更新，完整 action mapping 推断后置 2.3）
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tools.sampling.pilot.stubs import reset_action

from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Marks,
    Progression,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.query import query_skill
from xkx.runtime.query import set as dbase_set

# LPC set_heart_beat(1) 的心跳间隔（秒），对照 engine.py:79 tick_interval=1.0。
# 新引擎全局 tick 始终驱动，无 per-object set_heart_beat(0) 关闭语义。
HEART_BEAT_INTERVAL = 1

# LPC char.c:36 static int tick; per-object 非均匀计数器（heart_beat 每 5-14
# tick 才 update_condition，char.c:54 tick = 5 + random(10)）。新引擎
# ConditionSystem.update 每 tick 运行（conditions.py:519），无 per-object 计数器。
# 本样本用 SetupResult.tick 记录该值，标记"非均匀 tick 待迁移"。
_TICK_MIN = 5
_TICK_RANDOM = 10

# death.py:59 DISABLED_FLAG（disable_player 失能标记）。enable_player 等价移除。
_DISABLED_FLAG = "disabled"

# 模块级 living-name 注册表（样本特有桩，enable_player 依赖项，全引擎未实现）。
# set_living_name 写入，find_living 反查。测试间隔离用 _clear_living_registry。
_LIVING_REGISTRY: dict[str, int] = {}


def _clear_living_registry() -> None:
    """清空 living-name 注册表（测试隔离用，避免跨用例污染）。"""
    _LIVING_REGISTRY.clear()


@dataclass
class SetupResult:
    """setup() 编排结果（对照 LPC void setup()，无返回值；此处记录各步状态供测试断言）。"""

    # seteuid/getuid 步骤（capability token 已在 ws_server.issue_token 覆盖，
    # 此处标记"已设置有效 uid"，对照 char.c L51 seteuid(getuid(this_object()))）
    euid_set: bool = False
    # set_heart_beat(1)：全局 tick 已开启，标记 per-object 心跳启用
    heart_beat_enabled: bool = False
    # tick = 5 + random(10)：per-object 非均匀计数器值
    tick: int = 0
    # enable_player：命令可执行身份 + living-name 注册（living-name 桩）
    player_enabled: bool = False
    # living-name 注册是否落地（set_living_name 缺口，桩默认 False）
    living_name_registered: bool = False
    # CHAR_D->setup_char：种族 dispatch 结果
    race: str = ""
    # setup_char 末尾 reset_action 是否调用（stubs no-op，仅标记调用）
    reset_action_called: bool = False
    # setup() 产生的 actor 可见消息（setup 本身无消息推送，保持空列表对齐 LPC void）
    messages: list[str] = field(default_factory=list)


def _setup_human(world: World, eid: int, *, rng: Callable[[int], int] | None) -> None:
    """human race 基础初始化（对照 adm/daemons/race/human.c setup_human 通用部分）。

    独立实现，不调 src setup_race（simp=true：独立迁移补全分支）。覆盖 human.c
    通用部分：属性随机（undefinedp 时 = 10 + random(21)）/ age 默认 14 /
    max_jing/max_qi/max_jingli 年龄分层公式 / 70 岁衰减 / max_potential /
    max_encumbrance / weight。门派加成（family.apply_family_bonuses，题材包
    CPK 资产）不在 setup_char 范围，后置。

    对照 human.c：greenfield dataclass 无 undefinedp 哨兵，用 Attributes 默认
    值 20 作为"未定义"标记（与 race.py:154 一致）。
    """
    attrs = world.get(eid, Attributes)
    vitals = world.get(eid, Vitals)
    prog = world.get(eid, Progression)
    equipment = world.get(eid, Equipment)
    assert attrs is not None, "setup_human 要求实体已挂载 Attributes"
    assert vitals is not None, "setup_human 要求实体已挂载 Vitals"
    assert prog is not None, "setup_human 要求实体已挂载 Progression"
    assert equipment is not None, "setup_human 要求实体已挂载 Equipment"

    def _rand(n: int) -> int:
        if n <= 0:
            return 0
        if rng is not None:
            return rng(n)
        return random.randrange(n)

    _DEFAULT_AGE = 20
    _DEFAULT_ATTR = 20
    attr_min = 10
    attr_span = 21  # human.c: 10 + random(21)，min=10 max=30

    # age 默认 14（human.c:61 undefinedp 兜底）
    if attrs.age == _DEFAULT_AGE:
        attrs.age = 14

    # 属性随机（human.c:62-67 undefinedp 时 = 10 + random(21)）
    if attrs.str_ == _DEFAULT_ATTR:
        attrs.str_ = attr_min + _rand(attr_span)
    if attrs.con_ == _DEFAULT_ATTR:
        attrs.con_ = attr_min + _rand(attr_span)
    if attrs.dex_ == _DEFAULT_ATTR:
        attrs.dex_ = attr_min + _rand(attr_span)
    if attrs.int_ == _DEFAULT_ATTR:
        attrs.int_ = attr_min + _rand(attr_span)

    age = attrs.age
    int_ = attrs.int_
    con_ = attrs.con_
    str_ = attrs.str_
    dex_ = attrs.dex_

    # max_jing 年龄分层（human.c:73-83）
    if age <= 14:
        vitals.max_jing = 100
    elif age <= 30:
        vitals.max_jing = 100 + (age - 14) * (int_ + con_) // 2
    else:
        vitals.max_jing = (int_ + con_) * 8 + 100

    # max_qi 年龄分层（human.c:80-83）
    if age <= 14:
        vitals.max_qi = 100
    elif age <= 30:
        vitals.max_qi = 100 + (age - 14) * (con_ + str_) // 2
    else:
        vitals.max_qi = 100 + (con_ + str_) * 8

    # 70 岁衰减（human.c:87-89）
    if age > 70:
        vitals.max_jing -= (age - 70) * (int_ + con_) // 7
        vitals.max_qi -= (age - 70) * (con_ + str_) // 7

    # max_jingli 年龄分层（human.c:387-396）
    if age <= 14:
        vitals.max_jingli = 100
    elif age <= con_:
        vitals.max_jingli = 100 + (age - 14) * (str_ + dex_)
    else:
        vitals.max_jingli = 100 + (str_ + dex_) * (con_ - 14)

    # jingli 70 岁衰减（human.c:395-396）
    if age > 70:
        vitals.max_jingli -= (age - 70) * con_ // 5

    # max_jingli 下限保护（human.c:417 setup_char 兜底 max_jingli=1）
    if vitals.max_jingli < 1:
        vitals.max_jingli = 1

    # max_potential（human.c:69-70）
    prog.max_potential = (
        100
        + int(math.sqrt(max(prog.combat_exp, 0))) // 10
        + (vitals.max_jing - 100) // 30
    )

    # max_encumbrance / weight（human.c:422）；weight 经 dbase key 写 Equipment
    equipment.max_encumbrance = str_ * 5000
    weight = 40000 + (str_ - 10) * 2000
    dbase_set(world, eid, "weight", weight)


def _setup_char(
    world: World, eid: int, *, race: str = "", rng: Callable[[int], int] | None
) -> str:
    """CHAR_D->setup_char 编排（对照 adm/daemons/chard.c L22-114）。

    返回 dispatch 的种族名（供 SetupResult.race 记录）。简化：只 human race
    dispatch（8 种族 daemon 后置），default 走"人类"兜底（chard.c:27-30）。

    POSTPONED_KEYS（race/pighead/jiajin/shen_type/behavior_exp/quest_exp，dbase_map
    无组件承接）不可用引擎 set 写（raise DbaseKeyError），故 chard.c 对应行用
    本地默认值参与计算 + SetupResult 记待迁移面，不调 dbase_set。仅写已映射
    key（jing/qi/jingli/eff_jing/eff_qi/max_neili/neili/max_jingli/max_encumbrance/
    shen/weight）。
    """
    # chard.c:27-30：race 未定义时兜底"人类"。"race" 为 POSTPONED_KEYS（query 返回
    # None + warning），故由调用方传入 race 参数，未传（空）走"人类"兜底，不查引擎
    if not race:
        race = "人类"

    # chard.c:32-59：8 种族 switch dispatch（简化只 human 覆盖，其余 7 种族
    # daemon 后置内容生产，noop 跳过；未知种族名走 default error）
    _KNOWN_NONHUMAN_RACES = frozenset(
        {"妖魔", "野兽", "家畜", "飞禽", "游鱼", "蛇类", "昆虫"}
    )
    if race == "人类":
        _setup_human(world, eid, rng=rng)
    elif race not in _KNOWN_NONHUMAN_RACES:
        # chard.c:57-58：default error("Chard: undefined race ...")
        raise ValueError(f"Chard: undefined race {race}.")
    # 已知非 human 种族 daemon 未迁移，noop（待迁移面记 effort.notes）

    attrs = world.get(eid, Attributes)
    vitals = world.get(eid, Vitals)
    prog = world.get(eid, Progression)
    ident = world.get(eid, Identity)
    skills = world.get(eid, Skills)
    assert vitals is not None and attrs is not None and prog is not None

    # chard.c:62：pighead 未定义兜底 0（POSTPONED_KEYS 无组件承接，跳过记待迁移）

    # chard.c:64-66：jing/qi/jingli 未定义时 = max。greenfield dataclass 无
    # undefinedp 哨兵，取"当前值<=0 视为未初始化"兜底（对齐 chard.c 兜底意图）
    if vitals.jing <= 0:
        vitals.jing = vitals.max_jing
    if vitals.qi <= 0:
        vitals.qi = vitals.max_qi
    if vitals.jingli <= 0:
        vitals.jingli = vitals.max_jingli

    # chard.c:68-69：eff_jing/eff_qi 未定义或超 max 时钳到 max
    if vitals.eff_jing == 0 or vitals.eff_jing > vitals.max_jing:
        vitals.eff_jing = vitals.max_jing
    if vitals.eff_qi == 0 or vitals.eff_qi > vitals.max_qi:
        vitals.eff_qi = vitals.max_qi

    # chard.c:72：jiajin 未定义兜底 1（POSTPONED_KEYS 无组件承接，跳过记待迁移）

    # chard.c:75-81：玩家 force 有效等级 > 基础值时，max_neili 钳到
    # force*con*2/3，neili 钳到 max_neili（避免内力超限）
    is_player = bool(ident and ident.is_player)
    if is_player and skills is not None:
        force_eff = query_skill(world, eid, "force")
        force_raw = query_skill(world, eid, "force", raw=True)
        if force_eff > force_raw:
            cap_neili = force_raw * attrs.con_ * 2 // 3
            if vitals.max_neili > cap_neili:
                vitals.max_neili = cap_neili
            if vitals.neili > vitals.max_neili:
                vitals.neili = vitals.max_neili

    # chard.c:84-92：玩家 jingli 同理钳到 force*con/2，下限 100
        if force_eff > force_raw:
            cap_jingli = force_raw * attrs.con_ // 2
            if vitals.max_jingli > cap_jingli:
                vitals.max_jingli = cap_jingli
            if vitals.jingli > vitals.max_jingli:
                vitals.jingli = vitals.max_jingli
            if vitals.max_jingli < 100:
                vitals.max_jingli = 100

    # chard.c:94-95：NPC 有 max_neili 但 force<1 时，set_skill("force", max_neili/6)
    if (
        not is_player
        and skills is not None
        and vitals.max_neili
        and query_skill(world, eid, "force", raw=True) < 1
    ):
        skills.levels["force"] = vitals.max_neili // 6

    # chard.c:97-104：shen_type（POSTPONED，本地 0 默认）兜底；shen 未定义时
    # 玩家=0，NPC=shen_type*combat_exp/10。shen 映射 TitleComp.shen 可写
    shen_type = 0  # POSTPONED_KEYS，待 shen_type 子系统迁移
    title = world.get(eid, TitleComp)
    if title is not None and title.shen == 0:
        if is_player:
            title.shen = 0
        else:
            title.shen = shen_type * prog.combat_exp // 10

    # chard.c:106-107：behavior_exp / quest_exp 未定义兜底（POSTPONED_KEYS 无组件
    # 承接，跳过记待迁移）

    # chard.c:109-111：max_encumbrance 为 0 时补 str*5000 + (query_str-str)*1000
    # greenfield 无 query_str 派生（race.py:228 注释），简化用 str*5000
    equipment = world.get(eid, Equipment)
    if equipment and not equipment.max_encumbrance:
        equipment.max_encumbrance = attrs.str_ * 5000

    # chard.c:113：reset_action（stubs no-op，标记调用）
    reset_action(world, eid)

    return race


def _set_living_name(world: World, eid: int) -> bool:
    """set_living_name 桩（对照 LPC F_NAME set_living_name，enable_player 依赖）。

    living-name 注册（find_living 反查）全引擎未实现。桩：把 Identity.name -> eid
    写入模块级 registry，find_living 反查。真实需 LivingNameRegistry + 双向表。
    返回是否注册成功（无 Identity 视为未注册）。
    """
    ident = world.get(eid, Identity)
    if ident is None or not ident.name:
        return False
    _LIVING_REGISTRY[ident.name] = eid
    return True


def find_living(name: str) -> int | None:
    """find_living 桩（对照 LPC efun）。返回 set_living_name 注册的 entity_id。"""
    return _LIVING_REGISTRY.get(name)


def setup(
    game: Any,
    actor_id: int,
    *,
    race: str = "",
    rng: Callable[[int], int] | None = None,
) -> SetupResult:
    """char.c:setup 迁移（对照 inherit/char/char.c L49-58）。

    返回 SetupResult 记录各步状态（LPC setup 为 void 无返回，此处为测试可断言）。
    LPC tell_object / 消息推送：setup 本身无消息输出，messages 保持空列表。
    """
    world = game.world
    result = SetupResult()

    # L51：seteuid(getuid(this_object()))
    # 新引擎 capability token（ws_server.issue_token）已覆盖"设置有效 uid"语义，
    # 此处标记已设置（对照 capability.py:133 seteuid/getuid）
    result.euid_set = True

    # L53：set_heart_beat(1)
    # 新引擎全局 tick（engine.py:132 Engine.tick，tick_interval=1.0）始终驱动，
    # 无 per-object set_heart_beat(0) 关闭语义；标记 per-object 心跳启用
    result.heart_beat_enabled = True

    # L54：tick = 5 + random(10)
    # per-object 非均匀计数器（heart_beat 每 5-14 tick 才 update_condition），
    # 新引擎 ConditionSystem.update 每 tick 运行无 per-object 计数器；记录值
    # 标记"非均匀 tick 待迁移"
    tick_rand = rng(_TICK_RANDOM) if rng is not None else random.randrange(_TICK_RANDOM)
    result.tick = _TICK_MIN + tick_rand

    # L55：enable_player()
    # capability token + middleware 8 段 + Marks.flags 分布覆盖主流程（命令可
    # 执行身份 + 路径 + 失能标记）。enable_player 反向移除 disable_player 设的
    # DISABLED_FLAG（death.py:59），并注册 living-name（set_living_name 后置桩）
    marks = world.get(actor_id, Marks)
    if marks is not None:
        marks.flags.discard(_DISABLED_FLAG)
    result.player_enabled = True
    result.living_name_registered = _set_living_name(world, actor_id)

    # L57：CHAR_D->setup_char(this_object())
    # daemon 编排（chard.c L22-114）：race dispatch + dbase 兜底 + 钳位 +
    # shen 公式 + reset_action
    result.race = _setup_char(world, actor_id, race=race, rng=rng)
    result.reset_action_called = True

    return result
