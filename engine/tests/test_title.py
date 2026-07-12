"""RANK_D 7 函数 + PronounContext + TitleComp 测试（阶段 2.5 批次 2，ADR-0028）。

覆盖 ADR-0028 验收标准 11 项：

1. RANK_D 7 函数行为等价（对照 rankd.c 典型 case，含 is_ghost/wizhood/PKS/
   class/shen/gender/age 全分支）
2. PronounContext 三元组求值（$C/$c 角色互换 viewer 翻转 + 10 占位符 + 可见性门控
   + System tick 回退）
3. TitleComp 序列化往返（ADR-0022）
4. short() TitleComp 集成（补 test_query.py 没覆盖的 title/nickname/鬼气组合）
5. PKS 称号
6. hypothesis 属性测试（rank_info 覆盖优先 + query_close 辈分 + is_ghost 短路）

[ADR-0028](../../../docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md)
[adm/daemons/rankd.c](../../../adm/daemons/rankd.c)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xkx.runtime.components import Attributes, Identity, Marks, TitleComp
from xkx.runtime.pronoun import (
    PronounContext,
    PronounService,
    gender_pronoun,
    gender_self,
    visible,
)
from xkx.runtime.serialization import deserialize_component, serialize_component
from xkx.runtime.title import (
    query_close,
    query_rank,
    query_respect,
    query_rude,
    query_self,
    query_self_close,
    query_self_rude,
    reset_class_tables,
    set_class_tables,
)
from xkx.runtime.world import build_world

# ---- 测试辅助 ----

# 最小 IR（build_world 需要至少一个房间）
_MIN_IR: dict = {
    "rooms": [
        {"id": "city/street", "short": "街道", "long": "一条热闹的街道。", "exits": {}},
    ],
    "npcs": [],
}


def _make_world() -> object:
    """构建空世界（无玩家实体，测试自行 new_entity + add）。"""
    world, _, _ = build_world(_MIN_IR)
    return world


def spawn_entity(
    world,
    *,
    name: str = "测试实体",
    aliases: list[str] | None = None,
    gender: str = "男性",
    age: int = 25,
    title_comp: TitleComp | None = None,
    marks: set[str] | None = None,
    add_title: bool = True,
) -> int:
    """构造带 Identity + Attributes + TitleComp（可选）+ Marks（可选）的实体。

    rankd 7 函数依赖 TitleComp 存在（无则返回空串），默认添加空 TitleComp
    （add_title=True）。测试无 TitleComp 场景传 add_title=False。参考
    test_query.py/test_modifier_stack.py 的实体构造模式。
    """
    eid = world.new_entity()
    world.add(
        eid,
        Identity(name=name, aliases=aliases if aliases is not None else ["test"]),
    )
    world.add(eid, Attributes(age=age, gender=gender))
    if title_comp is not None:
        world.add(eid, title_comp)
    elif add_title:
        world.add(eid, TitleComp())
    if marks is not None:
        world.add(eid, Marks(flags=marks))
    return eid


@pytest.fixture(autouse=True)
def _isolate_class_tables():
    """每个测试前后清空注入的 class 表（测试隔离，防跨测试污染）。"""
    reset_class_tables()
    yield
    reset_class_tables()


# ═══════════════════ 1. query_rank 行为等价 ═══════════════════


# ---- is_ghost 最先短路 ----


def test_query_rank_is_ghost_short_circuits() -> None:
    """is_ghost True 最先返回鬼魂称谓（行 19-20），跳过所有后续分支。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        title_comp=TitleComp(is_ghost=True, shen=1000000, pks=200, char_class="bonze"),
    )
    assert query_rank(world, eid) == "【 鬼  魂 】"


def test_query_rank_is_ghost_overrides_pks() -> None:
    """is_ghost 优先于 PKS 称号（行 19 在行 80 之前）。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        gender="女性",
        title_comp=TitleComp(is_ghost=True, pks=200, mks=0),
    )
    assert query_rank(world, eid) == "【 鬼  魂 】"


# ---- PKS 称号（行 80-82/190-192）----


def test_query_rank_pks_male_bandit() -> None:
    """PKS>100 且 PKS>MKS -> 土匪（男）。"""
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(pks=200, mks=100))
    assert query_rank(world, eid) == "【 土  匪 】"


def test_query_rank_pks_female_bandit_wife() -> None:
    """PKS>100 且 PKS>MKS -> 土匪婆（女）。"""
    world = _make_world()
    eid = spawn_entity(
        world, gender="女性", title_comp=TitleComp(pks=200, mks=100)
    )
    assert query_rank(world, eid) == "【 土匪婆 】"


def test_query_rank_pks_equal_100_not_triggered() -> None:
    """PKS=100 不触发（LPC ``> 100`` 严格大于），走 class/shen 分支。"""
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(pks=100, mks=0))
    # 不触发 PKS -> shen=0 default 平民
    assert query_rank(world, eid) == "【 平  民 】"


def test_query_rank_pks_le_mks_not_triggered() -> None:
    """PKS>100 但 PKS<=MKS 不触发，走 shen 分支。"""
    world = _make_world()
    eid = spawn_entity(
        world, title_comp=TitleComp(pks=200, mks=300, shen=10000)
    )
    # PKS>MKS 不成立 -> shen=10000 -> 侠客
    assert query_rank(world, eid) == "【 侠  客 】"


# ---- shen 阈值分级（default 分支，行 147-166/297-316）----


@pytest.mark.parametrize(
    ("shen", "expected"),
    [
        (1000000, "【旷世大侠】"),
        (100000, "【 大  侠 】"),
        (10000, "【 侠  客 】"),
        (1000, "【 少  侠 】"),
        (500, "【 平  民 】"),
        (0, "【 平  民 】"),
        (-100, "【 少  魔 】"),
        (-1000, "【 魔  头 】"),
        (-10000, "【 大  魔 】"),
        (-100000, "【 魔  王 】"),
        (-1000000, "【旷世魔王】"),
    ],
    ids=lambda x: f"shen={x}" if not isinstance(x, str) else x,
)
def test_query_rank_shen_thresholds_male(shen: int, expected: str) -> None:
    """shen 阈值分级（男，default 分支，行 297-316）。"""
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(shen=shen))
    assert query_rank(world, eid) == expected


@pytest.mark.parametrize(
    ("shen", "expected"),
    [
        (1000000, "【旷世侠女】"),
        (100000, "【 大侠女 】"),
        (10000, "【 侠  女 】"),
        (1000, "【 小侠女 】"),
        (0, "【 民  女 】"),
        (-100, "【 小魔女 】"),
        (-1000, "【 魔  女 】"),
        (-10000, "【 大魔女 】"),
        (-100000, "【 女魔王 】"),
        (-1000000, "【旷世魔女】"),
    ],
)
def test_query_rank_shen_thresholds_female(shen: int, expected: str) -> None:
    """shen 阈值分级（女，default 分支，行 147-166）。"""
    world = _make_world()
    eid = spawn_entity(
        world, gender="女性", title_comp=TitleComp(shen=shen)
    )
    assert query_rank(world, eid) == expected


def test_query_rank_shen_boundary_exclusive() -> None:
    """shen 边界值：1000000 命中旷世大侠（>=），999999 命中大侠。"""
    world = _make_world()
    eid_high = spawn_entity(world, title_comp=TitleComp(shen=1000000))
    assert query_rank(world, eid_high) == "【旷世大侠】"
    eid_low = spawn_entity(world, title_comp=TitleComp(shen=999999))
    assert query_rank(world, eid_low) == "【 大  侠 】"


# ---- class 注入表查表（查表框架，非武侠占位）----


def test_query_rank_class_table_lookup() -> None:
    """注入 class 表后按 gender+char_class 查表（查表框架验证，非武侠占位）。"""
    set_class_tables(
        rank={
            "男性": {"scholar": "【 书  生 】"},
            "女性": {"scholar": "【 才  女 】"},
        }
    )
    world = _make_world()
    eid_m = spawn_entity(world, title_comp=TitleComp(char_class="scholar"))
    assert query_rank(world, eid_m) == "【 书  生 】"
    eid_f = spawn_entity(
        world, gender="女性", title_comp=TitleComp(char_class="scholar")
    )
    assert query_rank(world, eid_f) == "【 才  女 】"


def test_query_rank_class_table_miss_falls_back_to_shen() -> None:
    """class 表查不到走 default shen 分支。"""
    set_class_tables(rank={"男性": {"scholar": "【 书  生 】"}})
    world = _make_world()
    # char_class="officer" 不在注入表 -> 走 shen 分支
    eid = spawn_entity(
        world, title_comp=TitleComp(char_class="officer", shen=10000)
    )
    assert query_rank(world, eid) == "【 侠  客 】"


def test_query_rank_empty_class_table_default_branch() -> None:
    """默认空 class 表（reset 后）走 default shen 分支（主题中立，无注入）。"""
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(shen=0))
    assert query_rank(world, eid) == "【 平  民 】"


# ---- wizhood 注入路径 ----


def test_query_rank_wizhood_priority_over_class_shen() -> None:
    """wizhood 优先于 class/shen（行 60-78/170-188）。

    核心引擎 query_wizhood 默认返回 None（无 wizard 判定组件），需注入
    WIZHOOD_TITLES 表 + monkeypatch query_wizhood 才能启用。本测试验证注入后
    wizhood 优先于 class/shen 分支。
    """
    import xkx.runtime.title as title_mod

    set_class_tables(
        rank={"男性": {"scholar": "【 书  生 】"}},
        wizhood={"男性": {"(admin)": "【 天  帝 】"}},
    )
    # monkeypatch query_wizhood 返回巫师等级
    original = title_mod.query_wizhood
    title_mod.query_wizhood = lambda world, target: "(admin)"  # type: ignore[assignment]
    try:
        world = _make_world()
        eid = spawn_entity(
            world,
            title_comp=TitleComp(char_class="scholar", shen=1000000),
        )
        assert query_rank(world, eid) == "【 天  帝 】"
    finally:
        title_mod.query_wizhood = original  # type: ignore[assignment]


def test_query_rank_wizhood_none_falls_through() -> None:
    """query_wizhood 默认返回 None，走 class/shen 分支（核心引擎无 wizard 组件）。"""
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(shen=10000))
    # wizhood=None -> 走 shen 分支
    assert query_rank(world, eid) == "【 侠  客 】"


# ---- 无 TitleComp ----


def test_query_rank_no_title_comp_returns_empty() -> None:
    """实体无 TitleComp 返回空串（spawn 应保证有）。"""
    world = _make_world()
    eid = spawn_entity(world, add_title=False)  # 显式不加 TitleComp
    assert query_rank(world, eid) == ""


def test_query_rank_no_attributes_defaults_male() -> None:
    """无 Attributes 组件 gender 默认男性（对齐 rankd.c default 分支）。"""
    world = _make_world()
    eid = world.new_entity()
    world.add(eid, Identity(name="裸", aliases=["x"]))
    world.add(eid, TitleComp(shen=0))
    assert query_rank(world, eid) == "【 平  民 】"


# ═══════════════════ 2. query_respect/rude/self/self_rude 行为等价 ═══════════════════


# ---- rank_info 覆盖优先（行 327/411/468/520）----


def test_query_respect_rank_info_override() -> None:
    """rank_info/respect 覆盖优先，跳过 gender/class/age 求值。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        gender="女性",
        age=30,
        title_comp=TitleComp(rank_info_respect="尊夫人", char_class="bonze"),
    )
    assert query_respect(world, eid) == "尊夫人"


def test_query_rude_rank_info_override() -> None:
    """rank_info/rude 覆盖优先。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        age=30,
        title_comp=TitleComp(rank_info_rude="老贼", char_class="bonze"),
    )
    assert query_rude(world, eid) == "老贼"


def test_query_self_rank_info_override() -> None:
    """rank_info/self 覆盖优先。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        gender="女性",
        age=30,
        title_comp=TitleComp(rank_info_self="本宫", char_class="bonze"),
    )
    assert query_self(world, eid) == "本宫"


def test_query_self_rude_rank_info_override() -> None:
    """rank_info/self_rude 覆盖优先。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        age=30,
        title_comp=TitleComp(rank_info_self_rude="本座", char_class="bonze"),
    )
    assert query_self_rude(world, eid) == "本座"


def test_rank_info_none_not_override() -> None:
    """rank_info_* 为 None 时不覆盖，走 class/age 分支。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        age=30,
        title_comp=TitleComp(
            rank_info_respect=None,
            rank_info_rude=None,
            rank_info_self=None,
            rank_info_self_rude=None,
        ),
    )
    # 全 None -> default 分支，男 age=30 -> 壮士/臭贼/在下/大爷我
    assert query_respect(world, eid) == "壮士"
    assert query_rude(world, eid) == "臭贼"
    assert query_self(world, eid) == "在下"
    assert query_self_rude(world, eid) == "大爷我"


# ---- default 分支 age 段（通用中文称谓）----


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (17, "小兄弟"),
        (19, "小兄弟"),
        (20, "壮士"),
        (49, "壮士"),
        (50, "老爷子"),
        (80, "老爷子"),
    ],
)
def test_query_respect_male_age_bands(age: int, expected: str) -> None:
    """query_respect 男 default age 段（<20 小兄弟 / <50 壮士 / >=50 老爷子）。"""
    world = _make_world()
    eid = spawn_entity(world, age=age)
    assert query_respect(world, eid) == expected


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (17, "小姑娘"),
        (18, "姑娘"),
        (49, "姑娘"),
        (50, "婆婆"),
        (80, "婆婆"),
    ],
)
def test_query_respect_female_age_bands(age: int, expected: str) -> None:
    """query_respect 女 default age 段（<18 小姑娘 / <50 姑娘 / >=50 婆婆）。"""
    world = _make_world()
    eid = spawn_entity(world, gender="女性", age=age)
    assert query_respect(world, eid) == expected


def test_query_rude_age_bands() -> None:
    """query_rude default age 段。"""
    world = _make_world()
    eid_young = spawn_entity(world, age=19)
    assert query_rude(world, eid_young) == "小王八蛋"
    eid_mid = spawn_entity(world, age=30)
    assert query_rude(world, eid_mid) == "臭贼"
    eid_old = spawn_entity(world, age=60)
    assert query_rude(world, eid_old) == "老匹夫"


def test_query_self_age_bands() -> None:
    """query_self default age 段（男 <50 在下 / >=50 老头子）。"""
    world = _make_world()
    eid_young = spawn_entity(world, age=30)
    assert query_self(world, eid_young) == "在下"
    eid_old = spawn_entity(world, age=60)
    assert query_self(world, eid_old) == "老头子"


def test_query_self_rude_age_bands() -> None:
    """query_self_rude default age 段（男 <50 大爷我 / >=50 老子）。"""
    world = _make_world()
    eid_young = spawn_entity(world, age=30)
    assert query_self_rude(world, eid_young) == "大爷我"
    eid_old = spawn_entity(world, age=60)
    assert query_self_rude(world, eid_old) == "老子"


# ---- class 注入表查表 ----


def test_query_respect_class_table_lookup() -> None:
    """注入 respect 表后按 gender+char_class 查表。"""
    set_class_tables(
        respect={
            "男性": {"bonze": "大师"},
            "女性": {"bonze": "师太"},
        }
    )
    world = _make_world()
    eid_m = spawn_entity(world, title_comp=TitleComp(char_class="bonze"))
    assert query_respect(world, eid_m) == "大师"
    eid_f = spawn_entity(
        world, gender="女性", title_comp=TitleComp(char_class="bonze")
    )
    assert query_respect(world, eid_f) == "师太"


def test_query_rude_class_table_lookup() -> None:
    """注入 rude 表后查表。"""
    set_class_tables(rude={"男性": {"taoist": "死牛鼻子"}})
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(char_class="taoist"))
    assert query_rude(world, eid) == "死牛鼻子"


def test_query_self_class_table_lookup() -> None:
    """注入 self 表后查表。"""
    set_class_tables(self_={"男性": {"taoist": "贫道"}})
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(char_class="taoist"))
    assert query_self(world, eid) == "贫道"


def test_query_self_rude_class_table_lookup() -> None:
    """注入 self_rude 表后查表。"""
    set_class_tables(self_rude={"男性": {"taoist": "本山人"}})
    world = _make_world()
    eid = spawn_entity(world, title_comp=TitleComp(char_class="taoist"))
    assert query_self_rude(world, eid) == "本山人"


def test_class_table_gender_fallback_male() -> None:
    """gender 无匹配表时回退男性表（对齐 rankd.c case 女性 + default 两分支）。"""
    set_class_tables(respect={"男性": {"scholar": "先生"}})
    world = _make_world()
    # gender="无性" 无表 -> 回退男性表
    eid = spawn_entity(
        world, gender="无性", title_comp=TitleComp(char_class="scholar")
    )
    assert query_respect(world, eid) == "先生"


# ═══════════════════ 3. query_close 行为等价 ═══════════════════


def test_query_close_viewer_older_male_younger_brother() -> None:
    """viewer 年长（a1>=a2）-> 弟弟（男 target，default 分支）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30, name="年长者")
    target = spawn_entity(world, age=20, name="年幼者")
    assert query_close(world, viewer, target) == "弟弟"


def test_query_close_viewer_younger_male_elder_brother() -> None:
    """viewer 年幼（a1<a2）-> 哥哥（男 target）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=20)
    target = spawn_entity(world, age=30)
    assert query_close(world, viewer, target) == "哥哥"


def test_query_close_age_equal_returns_elder_form() -> None:
    """age 相等（a1>=a2 命中）-> 弟弟（边界，>= 含等号）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=25)
    target = spawn_entity(world, age=25)
    assert query_close(world, viewer, target) == "弟弟"


def test_query_close_female_target() -> None:
    """女 target：viewer 年长 -> 妹妹，viewer 年幼 -> 姐姐。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target_young = spawn_entity(world, gender="女性", age=20)
    assert query_close(world, viewer, target_young) == "妹妹"
    target_old = spawn_entity(world, gender="女性", age=40)
    assert query_close(world, viewer, target_old) == "姐姐"


def test_query_close_eunach_random_in_valid_set() -> None:
    """无性 eunach 分支 random(5)：返回值在 {弟弟,哥哥,妹妹,姐姐} 集合（非确定性）。

    rankd.c 行 597-605：class=="eunach" 时 random(5)==1 返回异性称谓，否则同性。
    系统_rng（非 DeterministicRNG，称谓系统非 combat，ADR-0028 开放问题 3）。
    测返回值集合，不测确定性。
    """
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target = spawn_entity(
        world,
        gender="无性",
        age=20,
        title_comp=TitleComp(char_class="eunach"),
    )
    valid = {"弟弟", "哥哥", "妹妹", "姐姐"}
    # 多次调用覆盖 random 可能值
    results = {query_close(world, viewer, target) for _ in range(60)}
    assert results.issubset(valid)
    # 至少命中一个（不应恒空）
    assert len(results) >= 1


def test_query_close_eunach_viewer_younger_set() -> None:
    """无性 eunach viewer 年幼：返回值在 {弟弟,哥哥} 异性 {姐姐} 集合内。

    viewer 年幼 -> 同性哥哥 / 异性姐姐（行 603-604）。
    """
    world = _make_world()
    viewer = spawn_entity(world, age=20)
    target = spawn_entity(
        world,
        gender="无性",
        age=30,
        title_comp=TitleComp(char_class="eunach"),
    )
    valid = {"哥哥", "姐姐"}
    results = {query_close(world, viewer, target) for _ in range(60)}
    assert results.issubset(valid)


def test_query_close_gender_from_target_not_viewer() -> None:
    """query_close gender 取自 target（非 viewer），viewer 性别不影响结果。"""
    world = _make_world()
    # viewer 女 年长，target 男 年幼 -> 弟弟（取 target 男性别）
    viewer = spawn_entity(world, gender="女性", age=30)
    target = spawn_entity(world, gender="男性", age=20)
    assert query_close(world, viewer, target) == "弟弟"


def test_query_close_default_for_non_eunach_neuter() -> None:
    """无性但非 eunach class -> default 分支（弟弟/哥哥，行 606-610）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target = spawn_entity(
        world,
        gender="无性",
        age=20,
        title_comp=TitleComp(char_class="scholar"),
    )
    assert query_close(world, viewer, target) == "弟弟"


# ═══════════════════ 4. query_self_close 行为等价 ═══════════════════


def test_query_self_close_gender_from_viewer() -> None:
    """query_self_close gender 取自 viewer（行 630/635），自称性别跟随说话者。"""
    world = _make_world()
    # viewer 女 年长 target -> 姐姐我；target 性别无关
    viewer = spawn_entity(world, gender="女性", age=30)
    target = spawn_entity(world, gender="男性", age=20)
    assert query_self_close(world, viewer, target) == "姐姐我"


def test_query_self_close_viewer_younger_female() -> None:
    """女 viewer 年幼 -> 小妹我。"""
    world = _make_world()
    viewer = spawn_entity(world, gender="女性", age=20)
    target = spawn_entity(world, age=30)
    assert query_self_close(world, viewer, target) == "小妹我"


def test_query_self_close_male_elder() -> None:
    """男 viewer 年长 -> 愚兄我。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target = spawn_entity(world, age=20)
    assert query_self_close(world, viewer, target) == "愚兄我"


def test_query_self_close_male_younger() -> None:
    """男 viewer 年幼 -> 小弟我。"""
    world = _make_world()
    viewer = spawn_entity(world, age=20)
    target = spawn_entity(world, age=30)
    assert query_self_close(world, viewer, target) == "小弟我"


def test_query_self_close_age_equal_elder_form() -> None:
    """age 相等 -> 年长形式（愚兄我，>= 含等号）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=25)
    target = spawn_entity(world, age=25)
    assert query_self_close(world, viewer, target) == "愚兄我"


# ═══════════════════ 5. PronounContext 10 变量求值 ═══════════════════


def test_build_context_all_10_fields_filled() -> None:
    """build_context 10 字段全填充（非空）。"""
    world = _make_world()
    speaker = spawn_entity(world, name="张三", aliases=["zhang san"], age=30)
    target = spawn_entity(world, name="李四", aliases=["li si"], age=20)
    ctx = PronounService.build_context(world, speaker, target)
    # 10 字段全非 None（frozen dataclass）
    assert ctx.name_me == "张三"
    assert ctx.name_you == "李四"
    assert ctx.pronoun_me == "你"
    assert ctx.pronoun_you == "他"
    assert ctx.close  # 非空
    assert ctx.close_rev  # 非空
    assert ctx.respect  # 非空
    assert ctx.respect_rev  # 非空
    assert ctx.self  # 非空
    assert ctx.self_rude  # 非空


def test_build_context_close_vs_close_rev_viewer_flip() -> None:
    """$C/$c 角色互换 viewer 翻转（决策 2 核心）。

    speaker 年长 target：$C（speaker 看 target，viewer=speaker）= 弟弟；
    $c（target 看 speaker，viewer=target）= 哥哥。$C != $c 证明 viewer 是求值参数。
    """
    world = _make_world()
    speaker = spawn_entity(world, name="长辈", age=30)
    target = spawn_entity(world, name="晚辈", age=20)
    ctx = PronounService.build_context(world, speaker, target)
    # $C：speaker 看 target（viewer=speaker 年长）-> 弟弟
    assert ctx.close == "弟弟"
    # $c：target 看 speaker（viewer=target 年幼）-> 哥哥
    assert ctx.close_rev == "哥哥"
    # 核心不变量：$C != $c（viewer 翻转产出不同结果）
    assert ctx.close != ctx.close_rev


def test_build_context_respect_vs_respect_rev() -> None:
    """$R/$r 角色互换：$R = query_respect(target)，$r = query_respect(speaker)。"""
    world = _make_world()
    # speaker 年长（age 60 -> 老爷子），target 年幼（age 20 -> 壮士）
    speaker = spawn_entity(world, age=60)
    target = spawn_entity(world, age=20)
    ctx = PronounService.build_context(world, speaker, target)
    assert ctx.respect == query_respect(world, target)  # 壮士
    assert ctx.respect_rev == query_respect(world, speaker)  # 老爷子
    assert ctx.respect != ctx.respect_rev


def test_build_context_self_and_self_rude_from_speaker() -> None:
    """$S/$s 取自 speaker（query_self/query_self_rude）。"""
    world = _make_world()
    speaker = spawn_entity(world, age=30)
    target = spawn_entity(world, age=20)
    ctx = PronounService.build_context(world, speaker, target)
    assert ctx.self == query_self(world, speaker)  # 在下
    assert ctx.self_rude == query_self_rude(world, speaker)  # 大爷我


def test_build_context_pronoun_me_always_you() -> None:
    """$P 恒为"你"（gender_self 不分性别，对齐 LPC gender.c）。"""
    world = _make_world()
    speaker_f = spawn_entity(world, gender="女性", age=30)
    target = spawn_entity(world, age=20)
    ctx = PronounService.build_context(world, speaker_f, target)
    assert ctx.pronoun_me == "你"


def test_build_context_pronoun_you_by_gender() -> None:
    """$p 按 target 性别（他/她/它，对齐 gender.c gender_pronoun）。"""
    world = _make_world()
    speaker = spawn_entity(world, age=30)
    target_m = spawn_entity(world, gender="男性", age=20)
    ctx_m = PronounService.build_context(world, speaker, target_m)
    assert ctx_m.pronoun_you == "他"

    target_f = spawn_entity(world, gender="女性", age=20)
    ctx_f = PronounService.build_context(world, speaker, target_f)
    assert ctx_f.pronoun_you == "她"


# ---- render 10 占位符 ----


def test_render_all_placeholders() -> None:
    """render 全 10 占位符替换。"""
    ctx = PronounContext(
        name_me="张三",
        name_you="李四",
        pronoun_me="你",
        pronoun_you="他",
        close="弟弟",
        close_rev="哥哥",
        respect="壮士",
        respect_rev="老爷子",
        self="在下",
        self_rude="大爷我",
    )
    template = "$N对$n说：$P$S在此，敢问$R大名？$r可曾听闻？$C$c亲如一家，$s狂妄之极。"
    result = PronounService.render(template, ctx)
    assert result == (
        "张三对李四说：你在下在此，敢问壮士大名？老爷子可曾听闻？弟弟哥哥亲如一家，"
        "大爷我狂妄之极。"
    )


def test_render_partial_placeholders() -> None:
    """render 部分占位符替换（无占位符文本保留）。"""
    ctx = PronounContext(
        name_me="甲",
        name_you="乙",
        pronoun_me="你",
        pronoun_you="他",
        close="弟弟",
        close_rev="哥哥",
        respect="壮士",
        respect_rev="老爷子",
        self="在下",
        self_rude="大爷我",
    )
    assert PronounService.render("$N攻击$n", ctx) == "甲攻击乙"
    assert PronounService.render("无占位符文本", ctx) == "无占位符文本"


def test_render_case_sensitive() -> None:
    """render 大小写区分（$N vs $n，$C vs $c）。"""
    ctx = PronounContext(
        name_me="大写",
        name_you="小写",
        pronoun_me="P大",
        pronoun_you="p小",
        close="C大",
        close_rev="c小",
        respect="R大",
        respect_rev="r小",
        self="S大",
        self_rude="s小",
    )
    result = PronounService.render("$N$n$P$p$C$c$R$r$S$s", ctx)
    assert result == "大写小写P大p小C大c小R大r小S大s小"


def test_render_empty_values_replaced() -> None:
    """render 空字符串值也替换（占位符消失）。"""
    ctx = PronounContext(
        name_me="甲",
        name_you="",
        pronoun_me="你",
        pronoun_you="他",
        close="",
        close_rev="",
        respect="",
        respect_rev="",
        self="",
        self_rude="",
    )
    assert PronounService.render("$N[$n]", ctx) == "甲[]"


# ---- 可见性门控（target 不可见退化）----


def test_build_context_target_invisible_degrades() -> None:
    """target 不可见（is_ghost）时 $n/$p/$C/$c/$R/$r 退化为基础代词。

    避免泄露隐身目标信息（ADR-0028 决策 2 可见性不变量）。
    """
    world = _make_world()
    speaker = spawn_entity(world, name="说话者", age=30)
    # target is_ghost -> visible 返回 False
    target = spawn_entity(
        world,
        name="鬼魂目标",
        age=20,
        title_comp=TitleComp(is_ghost=True),
    )
    ctx = PronounService.build_context(world, speaker, target)
    # $n/$p 退化
    assert ctx.name_you == "某人"
    assert ctx.pronoun_you == "它"
    # $C/$c/$R/$r 退化（空串）
    assert ctx.close == ""
    assert ctx.close_rev == ""
    assert ctx.respect == ""
    assert ctx.respect_rev == ""


def test_build_context_target_invisible_speaker_fields_unaffected() -> None:
    """target 不可见时 $N/$P/$S/$s 不受影响（speaker 侧正常求值）。"""
    world = _make_world()
    speaker = spawn_entity(world, name="说话者", age=30)
    target = spawn_entity(
        world,
        name="鬼魂",
        age=20,
        title_comp=TitleComp(is_ghost=True),
    )
    ctx = PronounService.build_context(world, speaker, target)
    assert ctx.name_me == "说话者"
    assert ctx.pronoun_me == "你"
    assert ctx.self == query_self(world, speaker)  # 在下
    assert ctx.self_rude == query_self_rude(world, speaker)  # 大爷我


def test_visible_ghost_target_returns_false() -> None:
    """visible: target is_ghost True -> False（鬼魂默认不可见）。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target = spawn_entity(
        world, age=20, title_comp=TitleComp(is_ghost=True)
    )
    assert visible(viewer, target, world) is False


def test_visible_normal_target_returns_true() -> None:
    """visible: 正常 target（非鬼魂）-> True。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    target = spawn_entity(world, age=20)
    assert visible(viewer, target, world) is True


def test_visible_no_identity_returns_false() -> None:
    """visible: target 无 Identity -> False。"""
    world = _make_world()
    viewer = spawn_entity(world, age=30)
    bare = world.new_entity()
    assert visible(viewer, bare, world) is False


# ---- build_context_for_system（System tick 回退，决策 4）----


def test_build_context_for_system_viewer_equals_speaker() -> None:
    """System tick 路径 viewer 回退 speaker 自身（决策 4）。

    build_context_for_system 与 build_context 行为一致（viewer=speaker 已是
    build_context 默认），但 $C/$c 内部仍翻转 viewer 不退化。
    """
    world = _make_world()
    speaker = spawn_entity(world, name="行动者", age=30)
    target = spawn_entity(world, name="目标", age=20)
    ctx_sys = PronounService.build_context_for_system(world, speaker, target)
    ctx_cmd = PronounService.build_context(world, speaker, target)
    # System 路径与 Command 路径（viewer=speaker）结果一致
    assert ctx_sys == ctx_cmd
    # $C/$c 内部仍翻转（不退化）
    assert ctx_sys.close == "弟弟"  # speaker 年长 target
    assert ctx_sys.close_rev == "哥哥"  # target 年幼 speaker


# ---- gender_self / gender_pronoun 单元（对齐 gender.c）----


def test_gender_self_always_you() -> None:
    """gender_self 恒返回"你"（不分性别）。"""
    for g in ("男性", "女性", "无性", "中性神", "雄性"):
        assert gender_self(g) == "你"


def test_gender_pronoun_branches() -> None:
    """gender_pronoun: 男性/中性神/无性->他，女性->她，其他->它。"""
    assert gender_pronoun("男性") == "他"
    assert gender_pronoun("中性神") == "他"
    assert gender_pronoun("无性") == "他"
    assert gender_pronoun("女性") == "她"
    assert gender_pronoun("雄性") == "它"
    assert gender_pronoun("雌性") == "它"
    assert gender_pronoun("未知") == "它"


# ═══════════════════ 6. TitleComp 序列化往返（ADR-0022） ═══════════════════


def test_titlecomp_roundtrip_default() -> None:
    """全默认实例往返等价。"""
    comp = TitleComp()
    data = serialize_component(comp)
    restored = deserialize_component(TitleComp, data)
    assert restored == comp


def test_titlecomp_roundtrip_full_values() -> None:
    """非默认值实例往返等价。"""
    comp = TitleComp(
        title="华山派弟子",
        nickname="老顽童",
        shen=50000,
        rank_info_respect="尊夫人",
        rank_info_rude="老贼",
        rank_info_self="本宫",
        rank_info_self_rude="本座",
        pks=200,
        mks=50,
        char_class="bonze",
        dali_rank=5,
        family_rank=9,
        is_ghost=True,
    )
    data = serialize_component(comp)
    restored = deserialize_component(TitleComp, data)
    assert restored == comp


def test_titlecomp_roundtrip_none_fields() -> None:
    """含 None 字段（rank_info_*）往返保持 None。"""
    comp = TitleComp(
        rank_info_respect=None,
        rank_info_rude=None,
        rank_info_self=None,
        rank_info_self_rude=None,
    )
    data = serialize_component(comp)
    # None 序列化为 null
    assert data["rank_info_respect"] is None
    assert data["rank_info_self_rude"] is None
    restored = deserialize_component(TitleComp, data)
    assert restored.rank_info_respect is None
    assert restored.rank_info_self_rude is None


def test_titlecomp_roundtrip_bool_field() -> None:
    """bool 字段（is_ghost）往返保持 True。"""
    comp = TitleComp(is_ghost=True)
    data = serialize_component(comp)
    assert data["is_ghost"] is True
    restored = deserialize_component(TitleComp, data)
    assert restored.is_ghost is True


def test_titlecomp_extra_fields_ignored() -> None:
    """多余字段忽略（向前兼容新字段，ADR-0022 §7）。"""
    comp = TitleComp(title="大侠")
    data = serialize_component(comp)
    data["future_field"] = "ignore me"
    data["another_extra"] = 123
    restored = deserialize_component(TitleComp, data)
    assert restored.title == "大侠"
    assert not hasattr(restored, "future_field")


def test_titlecomp_missing_fields_use_defaults() -> None:
    """缺失字段用 dataclass 默认值（向后兼容旧存档，ADR-0022 §7）。"""
    # 仅提供部分字段
    data = {"title": "大侠", "shen": 1000}
    restored = deserialize_component(TitleComp, data)
    assert restored.title == "大侠"
    assert restored.shen == 1000
    # 缺失字段用默认值
    assert restored.nickname == ""
    assert restored.pks == 0
    assert restored.is_ghost is False
    assert restored.rank_info_respect is None


def test_titlecomp_serialized_field_count() -> None:
    """序列化含全部 13 字段（dataclass fields 全提取）。"""
    comp = TitleComp()
    data = serialize_component(comp)
    expected_fields = {
        "title",
        "nickname",
        "shen",
        "rank_info_respect",
        "rank_info_rude",
        "rank_info_self",
        "rank_info_self_rude",
        "pks",
        "mks",
        "char_class",
        "dali_rank",
        "family_rank",
        "is_ghost",
    }
    assert set(data.keys()) == expected_fields


# ═══════════════════ 7. short() TitleComp 集成 ═══════════════════


def test_short_title_and_nickname_combined() -> None:
    """title + nickname 组合：大侠「老顽童」name(id)（name.c 行 132-133）。"""
    from xkx.runtime.query import short

    world = _make_world()
    eid = spawn_entity(
        world,
        name="周伯通",
        aliases=["zhou botong"],
        title_comp=TitleComp(title="大侠", nickname="老顽童"),
    )
    assert short(world, eid) == "大侠「老顽童」周伯通(zhou botong)"


def test_short_title_only_with_space() -> None:
    """仅 title 无 nick：title 后加空格（name.c 行 132-133）。"""
    from xkx.runtime.query import short

    world = _make_world()
    eid = spawn_entity(
        world,
        name="王五",
        aliases=["wang wu"],
        title_comp=TitleComp(title="普通百姓"),
    )
    assert short(world, eid) == "普通百姓 王五(wang wu)"


def test_short_nickname_only_brackets() -> None:
    """仅 nickname 无 title：「{nick}」name(id)（name.c 行 129-130）。"""
    from xkx.runtime.query import short

    world = _make_world()
    eid = spawn_entity(
        world,
        name="周伯通",
        aliases=["zhou botong"],
        title_comp=TitleComp(nickname="老顽童"),
    )
    assert short(world, eid) == "「老顽童」周伯通(zhou botong)"


def test_short_ghost_prefix_with_title_and_nick() -> None:
    """is_ghost 前缀 (鬼气) 与 title/nickname 叠加（顺序：title/nick -> 鬼气）。

    name.c 行 137：(鬼气) 在 title/nick 前缀之后。
    """
    from xkx.runtime.query import short

    world = _make_world()
    eid = spawn_entity(
        world,
        name="鬼魂",
        aliases=["ghost"],
        title_comp=TitleComp(title="大侠", nickname="老顽童", is_ghost=True),
    )
    assert short(world, eid) == "(鬼气) 大侠「老顽童」鬼魂(ghost)"


def test_short_ghost_prefix_only() -> None:
    """仅 is_ghost 无 title/nick：(鬼气) name(id)。"""
    from xkx.runtime.query import short

    world = _make_world()
    eid = spawn_entity(
        world,
        name="孤魂",
        aliases=["gu hun"],
        title_comp=TitleComp(is_ghost=True),
    )
    assert short(world, eid) == "(鬼气) 孤魂(gu hun)"


# ═══════════════════ 8. hypothesis 属性测试 ═══════════════════


# 合法 gender / char_class 策略
_GENDER_STRATEGY = st.sampled_from(["男性", "女性", "无性"])
_CHAR_CLASS_STRATEGY = st.sampled_from(["", "scholar", "officer", "bonze", "taoist"])
_SHEN_STRATEGY = st.integers(min_value=-2000000, max_value=2000000)
_AGE_STRATEGY = st.integers(min_value=0, max_value=120)


@given(
    gender=_GENDER_STRATEGY,
    char_class=_CHAR_CLASS_STRATEGY,
    shen=_SHEN_STRATEGY,
    age=_AGE_STRATEGY,
)
@settings(max_examples=50)
def test_prop_rank_info_respect_overrides_all(
    gender: str, char_class: str, shen: int, age: int
) -> None:
    """rank_info_respect 非 None 时 query_respect 返回该值（忽略 gender/class/shen/age）。

    ADR-0028 决策 1 不变量：rank_info 覆盖优先（行 327）。
    """
    world = _make_world()
    eid = spawn_entity(
        world,
        gender=gender,
        age=age,
        title_comp=TitleComp(
            shen=shen,
            char_class=char_class,
            rank_info_respect="固定尊称",
        ),
    )
    assert query_respect(world, eid) == "固定尊称"


@given(
    gender=_GENDER_STRATEGY,
    char_class=_CHAR_CLASS_STRATEGY,
    shen=_SHEN_STRATEGY,
    age=_AGE_STRATEGY,
)
@settings(max_examples=50)
def test_prop_rank_info_all_keys_override(
    gender: str, char_class: str, shen: int, age: int
) -> None:
    """rank_info 四键全设时，四函数均返回覆盖值（不变量：行 327/411/468/520）。"""
    world = _make_world()
    eid = spawn_entity(
        world,
        gender=gender,
        age=age,
        title_comp=TitleComp(
            shen=shen,
            char_class=char_class,
            rank_info_respect="R",
            rank_info_rude="U",
            rank_info_self="S",
            rank_info_self_rude="X",
        ),
    )
    assert query_respect(world, eid) == "R"
    assert query_rude(world, eid) == "U"
    assert query_self(world, eid) == "S"
    assert query_self_rude(world, eid) == "X"


@given(
    viewer_age=_AGE_STRATEGY,
    target_age=_AGE_STRATEGY,
    target_gender=st.sampled_from(["男性", "女性"]),
)
@settings(max_examples=50)
def test_prop_query_close_seniority(
    viewer_age: int, target_age: int, target_gender: str
) -> None:
    """query_close 辈分判定不变量：viewer_age>=target_age -> 弟弟/妹妹（同性 target）。

    男性 target：年长->弟弟，年幼->哥哥。
    女性 target：年长->妹妹，年幼->姐姐。
    ADR-0028 决策 1 不变量（行 574-612）。
    """
    world = _make_world()
    viewer = spawn_entity(world, age=viewer_age)
    target = spawn_entity(world, gender=target_gender, age=target_age)
    result = query_close(world, viewer, target)
    if viewer_age >= target_age:
        expected = "妹妹" if target_gender == "女性" else "弟弟"
    else:
        expected = "姐姐" if target_gender == "女性" else "哥哥"
    assert result == expected


@given(
    gender=_GENDER_STRATEGY,
    char_class=_CHAR_CLASS_STRATEGY,
    shen=_SHEN_STRATEGY,
    age=_AGE_STRATEGY,
    pks=st.integers(min_value=0, max_value=10000),
    mks=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=50)
def test_prop_is_ghost_short_circuits_query_rank(
    gender: str,
    char_class: str,
    shen: int,
    age: int,
    pks: int,
    mks: int,
) -> None:
    """is_ghost=True 时 query_rank 恒返回鬼魂称谓（忽略所有其他字段）。

    ADR-0028 决策 1 不变量：is_ghost 最先（行 19-20）。
    """
    world = _make_world()
    eid = spawn_entity(
        world,
        gender=gender,
        age=age,
        title_comp=TitleComp(
            shen=shen,
            char_class=char_class,
            pks=pks,
            mks=mks,
            is_ghost=True,
        ),
    )
    assert query_rank(world, eid) == "【 鬼  魂 】"


@given(
    shen=st.integers(min_value=1000, max_value=1000000),
    gender=st.sampled_from(["男性", "女性"]),
)
@settings(max_examples=40)
def test_prop_shen_positive_male_returns_xia(shen: int, gender: str) -> None:
    """shen>=1000 正阈值分级不变量：返回对应侠称谓（不返回平民/魔）。"""
    world = _make_world()
    eid = spawn_entity(
        world, gender=gender, title_comp=TitleComp(shen=shen)
    )
    result = query_rank(world, eid)
    if gender == "男性":
        valid = {"【旷世大侠】", "【 大  侠 】", "【 侠  客 】", "【 少  侠 】"}
    else:
        valid = {"【旷世侠女】", "【 大侠女 】", "【 侠  女 】", "【 小侠女 】"}
    assert result in valid
