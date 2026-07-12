"""通用种族基础数据 + setup_race 纯函数（ADR-0030 决策 1）。

把 LPC ``adm/daemons/race/human.c`` 的 ``setup_human`` 拆为"通用种族基础（引擎层）"
+"门派加成（题材包 CPK 资产，见 family.py）"两层。本模块只承载主题无关的通用
人类种族逻辑：属性随机、年龄分层 max_jing/max_qi/max_jingli 公式、70 岁衰减、
max_potential/max_encumbrance/weight 公式。

**主题无关性硬门禁**（ADR-0030 决策 4）：本模块源码不得含任何门派名 / 武侠技能名
字面量；公式参数全部从 RaceProfile 读取，由题材包注入。

[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from xkx.runtime.components import Attributes, Equipment, Progression, Vitals
from xkx.runtime.ecs import World
from xkx.runtime.query import set as dbase_set

if TYPE_CHECKING:
    from collections.abc import Callable


# ──────────────────────── 声明式载体 ────────────────────────


@dataclass(frozen=True)
class CombatAction:
    """徒手招式（对照 human.c ``combat_action`` 数组每条 mapping）。

    - ``action``：招式文本（含 ``$N``/``$n``/``$l`` 占位符，由战斗管线替换）
    - ``damage_type``：伤害类型（如"瘀伤"/"内伤"，对照 LPC ``"damage_type"`` 键）
    """

    action: str
    damage_type: str


@dataclass(frozen=True)
class RaceProfile:
    """通用人类种族基础数据声明（题材包注入接口，ADR-0030 决策 1）。

    对照 LPC ``human.c`` 的 ``create()`` + ``setup_human`` 通用部分（不含门派
    加成）。所有公式参数化，引擎层不硬编码任何题材数据。

    可序列化（ADR-0022）：字段全基本类型 + list 容器，serialization.py 按
    dataclasses.fields 自动提取。CombatAction 同为 frozen dataclass 全基本类型。

    对照 LPC human.c：

    | 字段 | 类型 | 对照 human.c |
    |---|---|---|
    | ``limbs`` | ``list[str]`` | ``set("limbs", ...)`` 21 部位 |
    | ``combat_actions`` | ``list[CombatAction]`` | ``combat_action`` 数组 5 条 |
    | ``dead_message`` 等 | ``str`` | ``set("dead_message", ...)`` 等 |
    | ``base_weight`` | ``int`` | ``BASE_WEIGHT=40000`` |
    | ``str_weight_factor`` | ``int`` | ``(str-10)*2000`` 的系数 |
    | ``attr_min``/``attr_max`` | ``int`` | ``10 + random(21)``（min=10, max=30）|
    """

    limbs: list[str]
    combat_actions: list[CombatAction]
    dead_message: str
    unconcious_message: str
    revive_message: str
    base_weight: int = 40000
    str_weight_factor: int = 2000
    attr_min: int = 10
    attr_max: int = 30


# 对照 human.c create() + combat_action 数组默认值。门派名/技能名零硬编码。
HUMAN_PROFILE: RaceProfile = RaceProfile(
    limbs=[
        "头顶", "颈部", "胸口", "后心", "左肩", "右肩", "左臂",
        "右臂", "左手", "右手", "两肋", "左脸", "腰间", "小腹",
        "左腿", "右腿", "右脸", "左脚", "右脚", "左耳", "右耳",
    ],
    combat_actions=[
        CombatAction(action="$N挥拳攻击$n的$l", damage_type="瘀伤"),
        CombatAction(action="$N往$n的$l一抓", damage_type="擦伤"),
        CombatAction(action="$N往$n的$l狠狠地踢了一脚", damage_type="瘀伤"),
        CombatAction(action="$N提起拳头往$n的$l捶去", damage_type="内伤"),
        CombatAction(action="$N对准$n的$l用力挥出一拳", damage_type="瘀伤"),
    ],
    dead_message="\n$N倒在地上，挣扎了几下就死了。\n\n",
    unconcious_message="\n$N脚下一个不稳，跌在地上昏了过去。\n\n",
    revive_message="\n$N慢慢睁开眼睛，清醒了过来。\n\n",
)


# ──────────────────────── setup_race 纯函数 ────────────────────────


def setup_race(
    world: World,
    eid: int,
    profile: RaceProfile,
    *,
    rng: Callable[[], int] | None = None,
) -> None:
    """通用种族基础初始化（对照 human.c ``setup_human`` **通用部分**）。

    不含任何门派加成（门派加成由 ``family.apply_family_bonuses`` 分发，题材包
    CPK 资产）。对照 human.c 行 51-423 的通用逻辑：

    - 属性随机（str/con/dex/int/per/kar 未定义时 = attr_min + random(attr_max-attr_min)）
    - age 默认 14（未定义时）
    - ``max_potential = 100 + int(sqrt(combat_exp))/10 + (max_jing-100)/30``
    - ``max_jing`` 年龄分层公式（age<=14:100 / age<=30:100+(age-14)*(int+con)/2 /
      age>30:(int+con)*8+100 / age>70 减衰）
    - ``max_qi`` 年龄分层公式（同理，用 con+str）
    - ``max_jingli`` 年龄分层公式（age<=14:100 / age<=con:100+(age-14)*(str+dex) /
      age>con:100+(str+dex)*(con-14) / age>70 减衰）
    - ``max_jing += eff_jingli/4``；``max_qi += max_neili/4``
    - ``max_encumbrance = str*5000``（简化：忽略 query_str-str 的 1000 系数项）
    - ``weight = base_weight + (str-10)*str_weight_factor``

    ``rng`` 可选随机数生成器（返回非负整数，取模 ``attr_max-attr_min`` 得偏移，
    对照 LPC ``random(n)``）；默认用 ``random.randrange``。确定性测试传固定
    rng（如 ``lambda: 5``），同 rng 同输出。

    要求实体已挂载 ``Attributes`` / ``Vitals`` / ``Progression`` / ``Equipment``
    组件（由 ``build_world``/``spawn_player`` 完成）。本函数原地修改组件字段。
    """
    attrs = world.get(eid, Attributes)
    vitals = world.get(eid, Vitals)
    prog = world.get(eid, Progression)
    equipment = world.get(eid, Equipment)
    assert attrs is not None, "setup_race 要求实体已挂载 Attributes"
    assert vitals is not None, "setup_race 要求实体已挂载 Vitals"
    assert prog is not None, "setup_race 要求实体已挂载 Progression"
    assert equipment is not None, "setup_race 要求实体已挂载 Equipment"

    # 随机数生成器：对照 LPC ``random(n)`` 返回 [0, n) 整数
    def _rand(n: int) -> int:
        if n <= 0:
            return 0
        if rng is not None:
            return rng() % n
        return random.randrange(n)

    attr_span = profile.attr_max - profile.attr_min

    # age 默认 14（human.c 行 61：undefinedp(my["age"]) 时兜底 14）
    # greenfield dataclass 无 undefinedp 哨兵，用 Attributes 默认值 20 作为"未
    # 定义"标记（spawn_player 传 age=22 非默认值不受影响；build_world NPC 默认
    # 20 会被覆盖成 14，对齐 LPC "未 set age 的 NPC 用 14" 行为）
    _DEFAULT_AGE = 20
    _DEFAULT_ATTR = 20
    if attrs.age == _DEFAULT_AGE:
        attrs.age = 14

    # 属性随机（human.c 行 62-67：undefinedp 时 = attr_min + random(attr_span)）
    # 同样用默认值 20 作为"未定义"哨兵。per/kar 在 greenfield 组件无对应字段
    # （S1 简化，后置 M3），跳过。调用方若显式设非 20 值则不随机。
    if attrs.str_ == _DEFAULT_ATTR:
        attrs.str_ = profile.attr_min + _rand(attr_span)
    if attrs.con_ == _DEFAULT_ATTR:
        attrs.con_ = profile.attr_min + _rand(attr_span)
    if attrs.dex_ == _DEFAULT_ATTR:
        attrs.dex_ = profile.attr_min + _rand(attr_span)
    if attrs.int_ == _DEFAULT_ATTR:
        attrs.int_ = profile.attr_min + _rand(attr_span)

    age = attrs.age
    int_ = attrs.int_
    con_ = attrs.con_
    str_ = attrs.str_
    dex_ = attrs.dex_

    # max_jing 年龄分层（human.c 行 73-83）
    if age <= 14:
        vitals.max_jing = 100
    elif age <= 30:
        vitals.max_jing = 100 + (age - 14) * (int_ + con_) // 2
    else:
        vitals.max_jing = (int_ + con_) * 8 + 100

    # max_qi 年龄分层（human.c 行 80-83）
    if age <= 14:
        vitals.max_qi = 100
    elif age <= 30:
        vitals.max_qi = 100 + (age - 14) * (con_ + str_) // 2
    else:
        vitals.max_qi = 100 + (con_ + str_) * 8

    # 70 岁衰减（human.c 行 87-89 / 222-224，通用部分不含道家/佛家保精保气）
    if age > 70:
        vitals.max_jing -= (age - 70) * (int_ + con_) // 7
        vitals.max_qi -= (age - 70) * (con_ + str_) // 7

    # max_jing += eff_jingli/4（human.c 行 212）；max_qi += max_neili/4（行 382）
    if vitals.eff_jingli > 0:
        vitals.max_jing += vitals.eff_jingli // 4
    if vitals.max_neili > 0:
        vitals.max_qi += vitals.max_neili // 4

    # max_jingli 年龄分层（human.c 行 387-396）
    if age <= 14:
        vitals.max_jingli = 100
    elif age <= con_:
        vitals.max_jingli = 100 + (age - 14) * (str_ + dex_)
    else:
        vitals.max_jingli = 100 + (str_ + dex_) * (con_ - 14)

    # jingli 70 岁衰减（human.c 行 395-396）
    if age > 70:
        vitals.max_jingli -= (age - 70) * con_ // 5

    # max_jingli 下限保护（human.c 无 clamp，但 con<14 时 (con-14) 为负致
    # max_jingli 为负不合理；对照 human.c 行 417 setup_char 兜底 max_jingli=1）
    if vitals.max_jingli < 1:
        vitals.max_jingli = 1

    # max_potential（human.c 行 69-70）
    prog.max_potential = (
        100
        + int(math.sqrt(max(prog.combat_exp, 0))) // 10
        + (vitals.max_jing - 100) // 30
    )

    # max_encumbrance（human.c 行 422 简化：str*5000，忽略 query_str-str 的 1000
    # 系数项，greenfield 无 query_str 派生）
    equipment.max_encumbrance = str_ * 5000

    # weight（human.c 行 422：BASE_WEIGHT + (str-10)*2000）
    # greenfield 无独立 weight 字段（F_MOVE 后置 2.3 衔接），通过 dbase key "weight"
    # 写入（dbase_map 映射到 Equipment.encumbrance，保真让步：LPC set_weight 语义）
    weight = profile.base_weight + (str_ - 10) * profile.str_weight_factor
    dbase_set(world, eid, "weight", weight)


__all__ = [
    "HUMAN_PROFILE",
    "CombatAction",
    "RaceProfile",
    "setup_race",
]
