"""RANK_D 7 函数称谓求值（阶段 2.5，ADR-0028 决策 1）。

对照 LPC [adm/daemons/rankd.c](../../../adm/daemons/rankd.c) 7 函数，提取为无状态
纯函数。前 5 函数单实体属性（签名 ``(world, target)``），后 2 函数观察者相对的
二元关系（签名 ``(world, viewer, target)``，依赖 viewer 年龄判定辈分）。

**主题中立**（ADR-0028 开放问题 2 裁决）：核心引擎不硬编码武侠门派职业称谓
（武侠门派职业字面量）。class 分支表数据从题材包注入（``CLASS_TITLE_TABLE`` /
``WIZHOOD_TITLES``，默认空 dict），rank_service 按 ``char_class`` 查表，查不到
走 default 分支（shen 阈值分级，通用中文称谓，核心引擎硬编码）。test_theme_
neutrality 硬门禁：本模块不含武侠门派职业/武器字面量。

**不变量**（ADR-0028 决策 1）：

- ``rank_info`` 覆盖优先（行 327/411/468/520）：TitleComp.rank_info_* 非 None
  直接返回，跳过 gender/class 求值。
- ``is_ghost`` 最先（query_rank 行 19）：TitleComp.is_ghost True 返回鬼魂称谓。
- ``wizhood`` 优先于 class/shen（query_rank 行 60-78/170-188）：巫师等级返回
  对应仙界称谓，跳过 class/shen 分支。
- PKS>100 且 PKS>MKS -> 土匪/土匪婆（行 80-82/190-192）。
- ``age`` 修正（行 330/414/471/523）：``age = Attributes.age - reduce_age``。
  ``reduce_age`` 接 0（beauty 真实公式后置 2.3 Attribute/Skill，ADR-0028 简化
  台账第 1 项）。
- ``query_close`` 辈分判定（行 574-612）：viewer age vs target age，年长->
  target 是弟弟/妹妹，年幼-> 哥哥/姐姐。无性分支 ``random(5)==1`` 返回异性
  称谓（系统 RNG，非 DeterministicRNG，称谓系统非 combat，ADR-0028 开放问题 3）。
- ``query_self_close`` gender 取自 viewer（行 630/635）：自称性别跟随说话者。

[ADR-0028](../../../docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 1/2/4
[adm/daemons/rankd.c](../../../adm/daemons/rankd.c)
"""

from __future__ import annotations

import random as _random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xkx.runtime.components import Attributes, TitleComp
    from xkx.runtime.ecs import World


# ──────────────────────── 题材包注入点（主题中立） ────────────────────────
#
# 核心引擎不硬编码武侠门派职业称谓（武侠门派职业/武器字面量）。
# 以下表默认空 dict，由题材包（wuxia module pack）在启动期注入填充。测试用注入
# 的非武侠占位表验证查表框架（如 scholar/officer 或占位 class）。rank_service
# 按 char_class 查表，查不到走 default 分支（shen 阈值分级，通用中文称谓，
# 核心引擎硬编码，非武侠烙印）。ADR-0028 开放问题 2 裁决。

# query_rank 的 class 分支表：gender -> char_class -> 称谓串。
# 对齐 rankd.c 行 85-318 的 class 分支（武侠门派职业，题材数据）。
# 题材包注入完整表（含 skill 等级分层等题材数据）；默认空，查不到走 default。
CLASS_RANK_TABLE: dict[str, dict[str, str]] = {}

# query_respect 的 class 分支表：gender -> char_class -> 称谓串。
# 对齐 rankd.c 行 331-403 的 class 分支（宗教/门派称谓，题材数据）。
CLASS_RESPECT_TABLE: dict[str, dict[str, str]] = {}

# query_rude 的 class 分支表：gender -> char_class -> 称谓串。
# 对齐 rankd.c 行 415-460（宗教/门派粗鄙称谓，题材数据）。
CLASS_RUDE_TABLE: dict[str, dict[str, str]] = {}

# query_self 的 class 分支表：gender -> char_class -> 称谓串。
# 对齐 rankd.c 行 472-512（宗教/门派自称，题材数据）。
CLASS_SELF_TABLE: dict[str, dict[str, str]] = {}

# query_self_rude 的 class 分支表：gender -> char_class -> 称谓串。
# 对齐 rankd.c 行 524-568（宗教/门派傲慢自称，题材数据）。
CLASS_SELF_RUDE_TABLE: dict[str, dict[str, str]] = {}

# 巫师等级称谓表：gender -> wizhood 字符串 -> 称谓串。
# 对齐 rankd.c 行 60-78/170-188 的 wizhood() 分支（admin->天帝/天后, arch->大神/
# 女神, ...）。wizhood 字符串对齐 LPC wizhood() 返回值（如 "(admin)"）。
# 核心引擎默认无巫师称谓来源（TitleComp 无 wizhood 字段，capability 需 token 不便
# 纯函数取），query_wizhood 返回 None 走 default 分支。题材包注入本表 + 提供
# wizhood 来源后启用巫师称谓路径。
WIZHOOD_TITLES: dict[str, dict[str, str]] = {}


def query_wizhood(world: World, target: int) -> str | None:
    """查 target 的巫师等级字符串（对齐 LPC ``wizhood(ob)``，ADR-0028 决策 1）。

    LPC ``wizhood(ob)`` 返回巫师等级字符串（如 ``"(admin)"``）。greenfield 无全局
    wizard 判定组件（TitleComp 无 wizhood 字段，capability token 需 secret 不便
    在纯函数取），默认返回 None（走 default class/shen 分支）。

    题材包若要启用巫师称谓路径，需：(1) 注入 ``WIZHOOD_TITLES`` 表；(2) 通过
    monkeypatch 本函数或扩展 TitleComp 提供 wizhood 来源。核心引擎保持主题中立
    与无 token 依赖。
    """
    _ = world  # 占位：核心引擎无 wizard 判定组件，预留题材包扩展钩子
    return None


def set_class_tables(
    *,
    rank: dict[str, dict[str, str]] | None = None,
    respect: dict[str, dict[str, str]] | None = None,
    rude: dict[str, dict[str, str]] | None = None,
    self_: dict[str, dict[str, str]] | None = None,
    self_rude: dict[str, dict[str, str]] | None = None,
    wizhood: dict[str, dict[str, str]] | None = None,
) -> None:
    """题材包启动期注入 class 分支表 + wizhood 称谓表（ADR-0028 开放问题 2）。

    题材包（wuxia module pack）在 ``build_world`` 前调用本函数注入武侠门派职业
    称谓表。核心引擎不硬编码这些字面量（test_theme_neutrality 硬门禁）。测试用
    注入的非武侠占位表验证查表框架。
    """
    if rank is not None:
        CLASS_RANK_TABLE.update(rank)
    if respect is not None:
        CLASS_RESPECT_TABLE.update(respect)
    if rude is not None:
        CLASS_RUDE_TABLE.update(rude)
    if self_ is not None:
        CLASS_SELF_TABLE.update(self_)
    if self_rude is not None:
        CLASS_SELF_RUDE_TABLE.update(self_rude)
    if wizhood is not None:
        WIZHOOD_TITLES.update(wizhood)


def reset_class_tables() -> None:
    """清空所有 class 分支表 + wizhood 表（测试隔离用）。"""
    CLASS_RANK_TABLE.clear()
    CLASS_RESPECT_TABLE.clear()
    CLASS_RUDE_TABLE.clear()
    CLASS_SELF_TABLE.clear()
    CLASS_SELF_RUDE_TABLE.clear()
    WIZHOOD_TITLES.clear()


# ──────────────────────── 内部辅助 ────────────────────────


_GHOST_TITLE = "【 鬼  魂 】"
"""鬼魂称谓（query_rank is_ghost 最先，行 19-20）。LPC HIB/NOR 颜色码砍掉。"""

# query_rank default 分支 shen 阈值分级（行 147-166/297-316）。
# 通用中文称谓（侠/魔/平民），非武侠烙印，核心引擎硬编码。
# 正阈值用 >=（降序匹配），负阈值用 <=（升序匹配，先查绝对值大的），default 平民。
# 对齐 rankd.c 的 if-else 链：正阈值 4 档 + 负阈值 5 档 + default。
_SHEN_RANK_POS_MALE: list[tuple[int, str]] = [
    (1000000, "【旷世大侠】"),
    (100000, "【 大  侠 】"),
    (10000, "【 侠  客 】"),
    (1000, "【 少  侠 】"),
]
_SHEN_RANK_NEG_MALE: list[tuple[int, str]] = [
    (-1000000, "【旷世魔王】"),
    (-100000, "【 魔  王 】"),
    (-10000, "【 大  魔 】"),
    (-1000, "【 魔  头 】"),
    (-100, "【 少  魔 】"),
]
_SHEN_RANK_DEFAULT_MALE = "【 平  民 】"
_SHEN_RANK_POS_FEMALE: list[tuple[int, str]] = [
    (1000000, "【旷世侠女】"),
    (100000, "【 大侠女 】"),
    (10000, "【 侠  女 】"),
    (1000, "【 小侠女 】"),
]
_SHEN_RANK_NEG_FEMALE: list[tuple[int, str]] = [
    (-1000000, "【旷世魔女】"),
    (-100000, "【 女魔王 】"),
    (-10000, "【 大魔女 】"),
    (-1000, "【 魔  女 】"),
    (-100, "【 小魔女 】"),
]
_SHEN_RANK_DEFAULT_FEMALE = "【 民  女 】"

# PKS 称号（行 80-82/190-192）：PKS>100 且 PKS>MKS。
_PKS_TITLE_MALE = "【 土  匪 】"
_PKS_TITLE_FEMALE = "【 土匪婆 】"

# query_close 亲近称谓（行 590-611）：通用亲属称谓，核心硬编码。
_CLOSE_FEMALE_ELDER = "妹妹"  # viewer 年长（a1>=a2），target 是妹妹
_CLOSE_FEMALE_YOUNGER = "姐姐"  # viewer 年幼，target 是姐姐
_CLOSE_DEFAULT_ELDER = "弟弟"
_CLOSE_DEFAULT_YOUNGER = "哥哥"
# 无性 eunach 分支 random(5)==1 返回异性称谓（行 597-605）
_CLOSE_EUNACH_ELDER_RARE = "妹妹"  # random==1 异性
_CLOSE_EUNACH_ELDER_COMMON = "弟弟"
_CLOSE_EUNACH_YOUNGER_RARE = "姐姐"
_CLOSE_EUNACH_YOUNGER_COMMON = "哥哥"

# query_self_close 自称（行 638-650）：通用亲属自称，核心硬编码。
_SELF_CLOSE_FEMALE_ELDER = "姐姐我"  # viewer 年长
_SELF_CLOSE_FEMALE_YOUNGER = "小妹我"
_SELF_CLOSE_DEFAULT_ELDER = "愚兄我"
_SELF_CLOSE_DEFAULT_YOUNGER = "小弟我"

# query_respect/rude/self/self_rude 的 default 分支（无 class 匹配时）。
# 通用中文称谓，核心硬编码。对齐 rankd.c 各函数 default 分支。
_RESPECT_DEFAULT_FEMALE: list[tuple[int, str]] = [
    # (age_upper_exclusive, title)：age < bound 用此称谓
    (18, "小姑娘"),
    (50, "姑娘"),
    (1 << 60, "婆婆"),
]
_RESPECT_DEFAULT_MALE: list[tuple[int, str]] = [
    (20, "小兄弟"),
    (50, "壮士"),
    (1 << 60, "老爷子"),
]
_RUDE_DEFAULT_FEMALE: list[tuple[int, str]] = [
    (18, "小贱人"),
    (50, "贱人"),
    (1 << 60, "死老太婆"),
]
_RUDE_DEFAULT_MALE: list[tuple[int, str]] = [
    (20, "小王八蛋"),
    (50, "臭贼"),
    (1 << 60, "老匹夫"),
]
_SELF_DEFAULT_FEMALE: list[tuple[int, str]] = [
    (30, "小女子"),
    (50, "妾身"),
    (1 << 60, "老身"),
]
_SELF_DEFAULT_MALE: list[tuple[int, str]] = [
    (50, "在下"),
    (1 << 60, "老头子"),
]
_SELF_RUDE_DEFAULT_FEMALE: list[tuple[int, str]] = [
    (30, "本姑娘"),
    (1 << 60, "老娘"),
]
_SELF_RUDE_DEFAULT_MALE: list[tuple[int, str]] = [
    (50, "大爷我"),
    (1 << 60, "老子"),
]


def _get_title(world: World, target: int) -> TitleComp | None:
    """取 target 的 TitleComp（rankd 求值主输入）。"""
    from xkx.runtime.components import TitleComp

    return world.get(target, TitleComp)


def _get_attrs(world: World, target: int) -> Attributes | None:
    """取 target 的 Attributes（gender/age）。"""
    from xkx.runtime.components import Attributes

    return world.get(target, Attributes)


def _effective_age(world: World, target: int) -> int:
    """age 修正（行 330/414/471/523）：age = Attributes.age - reduce_age。

    ``reduce_age`` = ``SKILL_D("beauty")->reduce_age(ob)``。beauty 真实公式后置
    2.3 Attribute/Skill（ADR-0028 简化台账第 1 项），2.5 接 0（不减龄）。
    无 Attributes 返回 0（对齐 LPC query("age") 未设返回 0）。
    """
    attrs = _get_attrs(world, target)
    if attrs is None:
        return 0
    return attrs.age  # reduce_age 接 0（beauty 公式后置）


def _lookup_class(
    table: dict[str, dict[str, str]], gender: str, char_class: str
) -> str | None:
    """class 分支查表（gender -> char_class -> 称谓）。查不到返回 None（走 default）。"""
    by_class = table.get(gender)
    if by_class is None:
        # gender 无匹配表时回退 "男性" default（对齐 rankd.c case "女性" + default 两分支）
        by_class = table.get("男性")
    if by_class is None:
        return None
    return by_class.get(char_class)


def _age_band(bands: list[tuple[int, str]], age: int) -> str:
    """按 age 段查称谓（bands 按 age 上界升序，第一个 age < bound 命中）。"""
    for upper, title in bands:
        if age < upper:
            return title
    return bands[-1][1]  # 兜底返回最后一档


# ──────────────────────── RANK_D 7 函数 ────────────────────────


def query_rank(world: World, target: int) -> str:
    """求 target 的等级称谓（对齐 rankd.c query_rank，行 8-320）。

    求值顺序（不变量，ADR-0028 决策 1）：

    1. ``is_ghost`` 最先（行 19）：TitleComp.is_ghost True 返回鬼魂称谓。
    2. ``wizhood`` 优先（行 60-78/170-188）：query_wizhood 返回巫师等级，
       查 WIZHOOD_TITLES 得称谓。
    3. PKS 称号（行 80-82/190-192）：PKS>100 且 PKS>MKS -> 土匪/土匪婆。
    4. class 分支（行 85-318）：CLASS_RANK_TABLE 查表，查不到走 default。
    5. shen 阈值分级（行 147-166/297-316）：default 分支按 shen 降序匹配。
    """
    title = _get_title(world, target)
    if title is None:
        return ""  # 无 TitleComp 无法求值（spawn 应保证有，见 world.py 衔接）

    # 1. is_ghost 最先（行 19-20）
    if title.is_ghost:
        return _GHOST_TITLE

    # 取 gender（无 Attributes 默认男性，对齐 rankd.c default 分支）
    attrs = _get_attrs(world, target)
    gender = attrs.gender if attrs else "男性"
    is_female = gender == "女性"

    # 2. wizhood 优先于 class/shen（行 60-78/170-188）
    wiz = query_wizhood(world, target)
    if wiz is not None:
        wiz_table = WIZHOOD_TITLES.get(gender) or WIZHOOD_TITLES.get("男性")
        if wiz_table:
            wiz_title = wiz_table.get(wiz)
            if wiz_title is not None:
                return wiz_title

    # 3. PKS 称号（行 80-82/190-192）：PKS>100 且 PKS>MKS
    if title.pks > 100 and title.pks > title.mks:
        return _PKS_TITLE_FEMALE if is_female else _PKS_TITLE_MALE

    # 4. class 分支（行 85-318）：查注入表，查不到走 default shen 分支
    class_title = _lookup_class(CLASS_RANK_TABLE, gender, title.char_class)
    if class_title is not None:
        return class_title

    # 5. shen 阈值分级（default 分支，行 147-166/297-316）
    # 正阈值用 >=（降序），负阈值用 <=（升序，先查绝对值大的），default 平民
    shen = title.shen
    if is_female:
        pos_bands, neg_bands, default_title = (
            _SHEN_RANK_POS_FEMALE,
            _SHEN_RANK_NEG_FEMALE,
            _SHEN_RANK_DEFAULT_FEMALE,
        )
    else:
        pos_bands, neg_bands, default_title = (
            _SHEN_RANK_POS_MALE,
            _SHEN_RANK_NEG_MALE,
            _SHEN_RANK_DEFAULT_MALE,
        )
    for lower_bound, rank_title in pos_bands:
        if shen >= lower_bound:
            return rank_title
    for lower_bound, rank_title in neg_bands:
        if shen <= lower_bound:
            return rank_title
    return default_title


def query_respect(world: World, target: int) -> str:
    """求 target 的尊敬称谓（对齐 rankd.c query_respect，行 322-404）。

    - rank_info/respect 覆盖优先（行 327）：TitleComp.rank_info_respect 非 None 直接返回。
    - age 修正（行 330）：age = Attributes.age - reduce_age（接 0）。
    - gender/class 分支（行 331-403）：CLASS_RESPECT_TABLE 查表，查不到走 default。
    """
    title = _get_title(world, target)
    if title is None:
        return ""

    # rank_info 覆盖优先（行 327）
    if title.rank_info_respect is not None:
        return title.rank_info_respect

    attrs = _get_attrs(world, target)
    gender = attrs.gender if attrs else "男性"
    is_female = gender == "女性"
    age = _effective_age(world, target)

    # class 分支查表（行 331-403）
    class_title = _lookup_class(CLASS_RESPECT_TABLE, gender, title.char_class)
    if class_title is not None:
        return class_title

    # default 分支（通用中文称谓）
    bands = _RESPECT_DEFAULT_FEMALE if is_female else _RESPECT_DEFAULT_MALE
    return _age_band(bands, age)


def query_rude(world: World, target: int) -> str:
    """求 target 的粗鄙称谓（对齐 rankd.c query_rude，行 406-461）。

    - rank_info/rude 覆盖优先（行 411）。
    - age 修正 + gender/class 分支（行 415-460）。
    """
    title = _get_title(world, target)
    if title is None:
        return ""

    if title.rank_info_rude is not None:
        return title.rank_info_rude

    attrs = _get_attrs(world, target)
    gender = attrs.gender if attrs else "男性"
    is_female = gender == "女性"
    age = _effective_age(world, target)

    class_title = _lookup_class(CLASS_RUDE_TABLE, gender, title.char_class)
    if class_title is not None:
        return class_title

    bands = _RUDE_DEFAULT_FEMALE if is_female else _RUDE_DEFAULT_MALE
    return _age_band(bands, age)


def query_self(world: World, target: int) -> str:
    """求 target 的自称（对齐 rankd.c query_self，行 463-513）。

    - rank_info/self 覆盖优先（行 468）。
    - age 修正 + gender/class 分支（行 472-512）。
    """
    title = _get_title(world, target)
    if title is None:
        return ""

    if title.rank_info_self is not None:
        return title.rank_info_self

    attrs = _get_attrs(world, target)
    gender = attrs.gender if attrs else "男性"
    is_female = gender == "女性"
    age = _effective_age(world, target)

    class_title = _lookup_class(CLASS_SELF_TABLE, gender, title.char_class)
    if class_title is not None:
        return class_title

    bands = _SELF_DEFAULT_FEMALE if is_female else _SELF_DEFAULT_MALE
    return _age_band(bands, age)


def query_self_rude(world: World, target: int) -> str:
    """求 target 的傲慢自称（对齐 rankd.c query_self_rude，行 515-569）。

    - rank_info/self_rude 覆盖优先（行 520）。
    - age 修正 + gender/class 分支（行 524-568）。
    """
    title = _get_title(world, target)
    if title is None:
        return ""

    if title.rank_info_self_rude is not None:
        return title.rank_info_self_rude

    attrs = _get_attrs(world, target)
    gender = attrs.gender if attrs else "男性"
    is_female = gender == "女性"
    age = _effective_age(world, target)

    class_title = _lookup_class(CLASS_SELF_RUDE_TABLE, gender, title.char_class)
    if class_title is not None:
        return class_title

    bands = _SELF_RUDE_DEFAULT_FEMALE if is_female else _SELF_RUDE_DEFAULT_MALE
    return _age_band(bands, age)


def query_close(world: World, viewer: int, target: int) -> str:
    """求 viewer 看 target 的亲近称谓（对齐 rankd.c query_close，行 570-613）。

    **观察者相对的二元关系函数**（专家 3 承重论断 2）：依赖 viewer 年龄与 target
    年龄比较决定辈分。``a1 = viewer.mud_age || viewer.age``，``a2 = target.mud_age
    || target.age``；``a1 >= a2`` -> viewer 年长（target 是弟弟/妹妹），否则 viewer
    年幼（target 是哥哥/姐姐）。mud_age 后置 M3，2.5 用 Attributes.age。

    无性分支（行 597-605）：``class == "eunach"`` 时 ``random(5)==1`` 返回异性
    称谓，否则同性。系统 RNG（非 DeterministicRNG，称谓系统非 combat，ADR-0028
    开放问题 3）。
    """
    attrs_t = _get_attrs(world, target)
    gender = attrs_t.gender if attrs_t else "男性"

    a1 = _effective_age(world, viewer)  # viewer age
    a2 = _effective_age(world, target)  # target age
    viewer_older = a1 >= a2

    title = _get_title(world, target)
    is_eunach = title is not None and title.char_class == "eunach"

    if gender == "女性":
        return _CLOSE_FEMALE_ELDER if viewer_older else _CLOSE_FEMALE_YOUNGER
    if gender == "无性" and is_eunach:
        # random(5)==1 返回异性称谓（行 597-605），系统 RNG（非 combat）
        rare = _random.randint(1, 5) == 1
        if viewer_older:
            return _CLOSE_EUNACH_ELDER_RARE if rare else _CLOSE_EUNACH_ELDER_COMMON
        return _CLOSE_EUNACH_YOUNGER_RARE if rare else _CLOSE_EUNACH_YOUNGER_COMMON
    # default（含男性/无性非 eunach）
    return _CLOSE_DEFAULT_ELDER if viewer_older else _CLOSE_DEFAULT_YOUNGER


def query_self_close(world: World, viewer: int, target: int) -> str:
    """求 viewer 对 target 的亲近自称（对齐 rankd.c query_self_close，行 615-651）。

    **gender 取自 viewer**（行 630/635）：自称性别跟随说话者（viewer），非 target。
    辈分判定同 query_close（viewer age vs target age）。
    """
    attrs_v = _get_attrs(world, viewer)
    gender = attrs_v.gender if attrs_v else "男性"
    is_female = gender == "女性"

    a1 = _effective_age(world, viewer)
    a2 = _effective_age(world, target)
    viewer_older = a1 >= a2

    if is_female:
        return _SELF_CLOSE_FEMALE_ELDER if viewer_older else _SELF_CLOSE_FEMALE_YOUNGER
    return _SELF_CLOSE_DEFAULT_ELDER if viewer_older else _SELF_CLOSE_DEFAULT_YOUNGER
