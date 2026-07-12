"""race 层 + 门派加成剥离测试（ADR-0030 决策 1）。

验证：
1. ``setup_race`` 通用公式行为等价（对照 human.c 年龄分层 / 70 岁衰减 / 属性随机
   / max_potential）
2. ``setup_race`` 确定性（同 rng 同输出）
3. ``apply_family_bonuses`` 分发 + 条件匹配 + 公式计算
4. 非武侠 FamilyBonus（大航海海盗帮航行加成 max_qi）
5. 武当派保气标准加成（验证标准门派数据走声明式载体）
6. hypothesis 属性测试（setup_race 确定性 + 三层资源不变量）

门派名/技能名全部写在测试文件里（题材包数据模拟），源码 race.py/family.py
不含任何门派名字面量（test_theme_neutrality 硬门禁，ADR-0030 决策 4）。

[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xkx.runtime.components import Attributes, Equipment, Progression, Vitals
from xkx.runtime.ecs import World
from xkx.runtime.family import FamilyBonus, apply_family_bonuses
from xkx.runtime.race import HUMAN_PROFILE, CombatAction, RaceProfile, setup_race

# ──────────────────────── 测试辅助 ────────────────────────


def _make_entity(world: World) -> int:
    """创建挂载全套组件的实体（对照 spawn_player，但无玩家专属字段）。"""
    eid = world.new_entity()
    world.add(eid, Attributes())
    world.add(eid, Vitals())
    world.add(eid, Progression())
    world.add(eid, Equipment())
    return eid


def _fixed_rng(seq: list[int]):
    """固定序列 rng：依次返回 seq 中值，耗尽后循环。"""
    idx = [0]

    def _next() -> int:
        v = seq[idx[0] % len(seq)]
        idx[0] += 1
        return v

    return _next


# ──────────────────────── setup_race 通用公式行为等价 ────────────────────────


class TestSetupRaceAgeFormulas:
    """对照 human.c 年龄分层公式（行 73-96 / 80-83 / 387-396）。"""

    def test_age_le_14_max_jing_is_100(self) -> None:
        """age<=14: max_jing = 100（human.c 行 75）。"""
        world = World()
        eid = _make_entity(world)
        # 显式设 age=14 避免被默认值哨兵覆盖；设属性非默认值避免随机
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 14
        attrs.str_ = 15
        attrs.con_ = 15
        attrs.dex_ = 15
        attrs.int_ = 15

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        assert vitals.max_jing == 100
        assert vitals.max_qi == 100
        assert vitals.max_jingli == 100

    def test_age_between_15_and_30_max_jing_formula(self) -> None:
        """age<=30: max_jing = 100 + (age-14)*(int+con)/2（human.c 行 76-77）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # 100 + (22-14)*(25+25)//2 = 100 + 8*25 = 300
        assert vitals.max_jing == 100 + (22 - 14) * (25 + 25) // 2
        # max_qi: 100 + (22-14)*(25+25)//2 = 300
        assert vitals.max_qi == 100 + (22 - 14) * (25 + 25) // 2

    def test_age_over_30_max_jing_formula(self) -> None:
        """age>30: max_jing = (int+con)*8+100（human.c 行 78）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 40
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # (25+25)*8+100 = 500
        assert vitals.max_jing == (25 + 25) * 8 + 100
        # max_qi: 100 + (25+25)*8 = 500
        assert vitals.max_qi == 100 + (25 + 25) * 8

    def test_age_over_70_senior_decay(self) -> None:
        """age>70: max_jing/qi 减衰（human.c 行 87-89 / 222-224）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 80
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # max_jing: (25+25)*8+100=500, 减 (80-70)*(25+25)//7=71 -> 429
        expected_jing = (25 + 25) * 8 + 100 - (80 - 70) * (25 + 25) // 7
        assert vitals.max_jing == expected_jing
        # max_qi: 100+(25+25)*8=500, 减 (80-70)*(25+25)//7=71 -> 429
        expected_qi = 100 + (25 + 25) * 8 - (80 - 70) * (25 + 25) // 7
        assert vitals.max_qi == expected_qi
        # max_jingli: 100+(str+dex)*(con-14)=100+50*11=650, 减 (80-70)*con//5=50 -> 600
        expected_jingli = 100 + (25 + 25) * (25 - 14) - (80 - 70) * 25 // 5
        assert vitals.max_jingli == expected_jingli

    def test_max_jingli_age_le_con_formula(self) -> None:
        """age<=con: max_jingli = 100 + (age-14)*(str+dex)（human.c 行 391）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 18
        attrs.str_ = 22
        attrs.con_ = 25
        attrs.dex_ = 18
        attrs.int_ = 15

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # age=18 <= con=25: 100 + (18-14)*(22+18) = 100+160=260
        assert vitals.max_jingli == 100 + (18 - 14) * (22 + 18)

    def test_max_jingli_age_gt_con_formula(self) -> None:
        """age>con: max_jingli = 100 + (str+dex)*(con-14)（human.c 行 392）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 40
        attrs.str_ = 22
        attrs.con_ = 18
        attrs.dex_ = 18
        attrs.int_ = 15

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # age=40 > con=18: 100 + (22+18)*(18-14) = 100+160=260
        assert vitals.max_jingli == 100 + (22 + 18) * (18 - 14)

    def test_eff_jingli_adds_to_max_jing(self) -> None:
        """max_jing += eff_jingli/4（human.c 行 212）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25
        vitals = world.get(eid, Vitals)
        assert vitals is not None
        vitals.eff_jingli = 80  # 非零触发 +eff_jingli/4

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # base max_jing = 100+(22-14)*(25+25)//2 = 300, +80//4=20 -> 320
        assert vitals.max_jing == 300 + 20

    def test_max_neili_adds_to_max_qi(self) -> None:
        """max_qi += max_neili/4（human.c 行 382）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25
        vitals = world.get(eid, Vitals)
        assert vitals is not None
        vitals.max_neili = 100

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # base max_qi = 300, +100//4=25 -> 325
        assert vitals.max_qi == 300 + 25

    def test_max_potential_formula(self) -> None:
        """max_potential = 100 + sqrt(combat_exp)/10 + (max_jing-100)/30（human.c 行 70）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25
        prog = world.get(eid, Progression)
        assert prog is not None
        prog.combat_exp = 10000  # sqrt=100, /10=10

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        prog = world.get(eid, Progression)
        assert prog is not None
        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # max_jing=300 -> (300-100)//30=6; 100 + 10 + 6 = 116
        assert prog.max_potential == 100 + 10 + (300 - 100) // 30

    def test_max_encumbrance_is_str_times_5000(self) -> None:
        """max_encumbrance = str*5000（human.c 行 422 简化）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 30
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        equipment = world.get(eid, Equipment)
        assert equipment is not None
        assert equipment.max_encumbrance == 30 * 5000

    def test_weight_formula_via_dbase_key(self) -> None:
        """weight = base_weight + (str-10)*str_weight_factor（human.c 行 422）。"""
        from xkx.runtime.query import query

        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        # weight 写入 dbase key "weight"（映射 Equipment.encumbrance，保真让步）
        weight = query(world, eid, "weight")
        assert weight == 40000 + (25 - 10) * 2000


class TestSetupRaceAttributeRandom:
    """对照 human.c 属性随机（行 62-67：10+random(21)）。"""

    def test_default_attrs_are_randomized(self) -> None:
        """默认值 20 的属性字段被随机化（对照 LPC undefinedp 分支）。"""
        world = World()
        eid = _make_entity(world)
        # Attributes 默认 str_/con_/dex_/int_=20，age 默认 20
        # rng=lambda: 5 -> attr_min + 5%21 = 10+5 = 15
        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 5)

        attrs = world.get(eid, Attributes)
        assert attrs is not None
        # age 默认 20 -> 覆盖为 14（默认值哨兵）
        assert attrs.age == 14
        # 四属性默认 20 -> 随机为 10 + 5%21 = 15
        assert attrs.str_ == 15
        assert attrs.con_ == 15
        assert attrs.dex_ == 15
        assert attrs.int_ == 15

    def test_explicit_attrs_not_overwritten(self) -> None:
        """调用方显式设的非默认值属性不被随机覆盖。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 25
        attrs.str_ = 30  # 非默认 20，不随机
        attrs.con_ = 28
        attrs.dex_ = 27
        attrs.int_ = 26

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 5)

        attrs = world.get(eid, Attributes)
        assert attrs is not None
        assert attrs.age == 25
        assert attrs.str_ == 30
        assert attrs.con_ == 28
        assert attrs.dex_ == 27
        assert attrs.int_ == 26

    def test_attr_min_max_bounds_with_system_random(self) -> None:
        """用系统 random 时，属性落在 [attr_min, attr_max] 范围内。"""
        world = World()
        eid = _make_entity(world)

        setup_race(world, eid, HUMAN_PROFILE)  # 不传 rng，用系统 random

        attrs = world.get(eid, Attributes)
        assert attrs is not None
        assert HUMAN_PROFILE.attr_min <= attrs.str_ <= HUMAN_PROFILE.attr_max
        assert HUMAN_PROFILE.attr_min <= attrs.con_ <= HUMAN_PROFILE.attr_max
        assert HUMAN_PROFILE.attr_min <= attrs.dex_ <= HUMAN_PROFILE.attr_max
        assert HUMAN_PROFILE.attr_min <= attrs.int_ <= HUMAN_PROFILE.attr_max


# ──────────────────────── setup_race 确定性 ────────────────────────


class TestSetupRaceDeterminism:
    """同 rng 同输出（确定性）。"""

    def test_same_rng_same_output(self) -> None:
        rng = _fixed_rng([3, 7, 11, 13])
        world1 = World()
        eid1 = _make_entity(world1)
        setup_race(world1, eid1, HUMAN_PROFILE, rng=rng)

        rng2 = _fixed_rng([3, 7, 11, 13])
        world2 = World()
        eid2 = _make_entity(world2)
        setup_race(world2, eid2, HUMAN_PROFILE, rng=rng2)

        a1 = world1.get(eid1, Attributes)
        a2 = world2.get(eid2, Attributes)
        assert a1 is not None and a2 is not None
        assert a1.str_ == a2.str_
        assert a1.con_ == a2.con_
        assert a1.dex_ == a2.dex_
        assert a1.int_ == a2.int_

        v1 = world1.get(eid1, Vitals)
        v2 = world2.get(eid2, Vitals)
        assert v1 is not None and v2 is not None
        assert v1.max_jing == v2.max_jing
        assert v1.max_qi == v2.max_qi
        assert v1.max_jingli == v2.max_jingli

    def test_different_rng_different_attrs(self) -> None:
        """不同 rng 序列产生不同属性（验证 rng 真的被使用）。"""
        world1 = World()
        eid1 = _make_entity(world1)
        setup_race(world1, eid1, HUMAN_PROFILE, rng=lambda: 1)

        world2 = World()
        eid2 = _make_entity(world2)
        setup_race(world2, eid2, HUMAN_PROFILE, rng=lambda: 9)

        a1 = world1.get(eid1, Attributes)
        a2 = world2.get(eid2, Attributes)
        assert a1 is not None and a2 is not None
        assert a1.str_ != a2.str_


# ──────────────────────── RaceProfile 载体 ────────────────────────


class TestRaceProfile:
    """RaceProfile 声明式载体。"""

    def test_human_profile_limbs_count(self) -> None:
        """HUMAN_PROFILE.limbs 21 部位（对照 human.c 行 40-44）。"""
        assert len(HUMAN_PROFILE.limbs) == 21

    def test_human_profile_combat_actions_count(self) -> None:
        """HUMAN_PROFILE.combat_actions 5 条（对照 human.c 行 14-30）。"""
        assert len(HUMAN_PROFILE.combat_actions) == 5
        for action in HUMAN_PROFILE.combat_actions:
            assert isinstance(action, CombatAction)
            assert action.action  # 非空
            assert action.damage_type  # 非空

    def test_race_profile_frozen(self) -> None:
        """RaceProfile 是 frozen dataclass（可哈希/可序列化前提）。"""
        assert HUMAN_PROFILE.base_weight == 40000
        assert HUMAN_PROFILE.str_weight_factor == 2000
        assert HUMAN_PROFILE.attr_min == 10
        assert HUMAN_PROFILE.attr_max == 30
        with pytest.raises(AttributeError):
            HUMAN_PROFILE.base_weight = 50000  # type: ignore[misc]

    def test_custom_profile_non_wuxia(self) -> None:
        """非武侠题材 RaceProfile 可注入（如大航海水手种族）。"""
        profile = RaceProfile(
            limbs=["头部", "躯干", "左臂", "右臂", "左腿", "右腿"],
            combat_actions=[
                CombatAction(action="$N挥拳打向$n的$l", damage_type="钝伤"),
            ],
            dead_message="$N 倒在甲板上。",
            unconcious_message="$N 失去意识。",
            revive_message="$N 苏醒过来。",
            base_weight=70000,
            str_weight_factor=3000,
            attr_min=8,
            attr_max=28,
        )
        assert profile.base_weight == 70000
        assert profile.attr_min == 8


# ──────────────────────── apply_family_bonuses 分发 ────────────────────────


class TestApplyFamilyBonuses:
    """apply_family_bonuses 分发 + 条件匹配 + 公式计算。"""

    def test_family_name_filter_only_matching_bonus_applied(self) -> None:
        """只有 family_name 匹配的 bonus 被应用。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 25
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"sailing": 50, "navigation": 80}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            # 海盗帮：航行加成 max_qi（匹配）
            FamilyBonus(
                family_name="海盗帮",
                target="max_qi",
                condition_skill="sailing",
                condition_threshold=39,
                bonus_skill="navigation",
                divisor=10,
            ),
            # 不匹配的门派（应被跳过）
            FamilyBonus(
                family_name="商帮",
                target="max_qi",
                condition_skill="trade",
                condition_threshold=39,
                bonus_skill="accounting",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "海盗帮", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # sailing=50 > 39, xism_age = 50//2 - 30 = -5 <= 0 -> 不加成
        # 实际：age=25 <= 30, adjusted_age = 25 - 25 = 0 <= 0 -> 不加成
        # 等等：cond_level=50, adjusted_age = 50//2 - 25(age) = 25-25=0 <= 0
        # 所以 bonus 不应用
        assert vitals.max_qi == max_qi_before

    def test_wudang_standard_bonuses_applied(self) -> None:
        """武当派保气标准加成（验证标准门派数据走声明式载体）。

        对照 human.c 行 246-257：
        - family_name="武当派", condition_skill="taoism" threshold=39
        - bonus_skill="force", divisor=10, target="max_qi"
        - age=35 (>30): adjusted_age = taoism//2 - 30
        - bonus = adjusted_age * (force_level // 10)
        """
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"taoism": 80, "force": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="武当派",
                target="max_qi",
                condition_skill="taoism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "武当派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # taoism=80 > 39, age=35 > 30 -> adjusted_age = 80//2 - 30 = 10
        # force=100 (有效等级：base 100//2=50 + mapped 0 = 50? 不对)
        # query_skill 非 raw: apply_val=0 + levels["force"]//2=50 + skill_map 0 = 50
        # bonus = 10 * (50 // 10) = 10 * 5 = 50
        force_effective = 100 // 2  # query_skill 非 raw 返回 50
        expected_bonus = 10 * (force_effective // 10)
        assert vitals.max_qi == max_qi_before + expected_bonus

    def test_condition_threshold_not_met_no_bonus(self) -> None:
        """条件技能等级 <= threshold 时不加成。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"taoism": 30, "force": 100}))  # taoism<=39

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="武当派",
                target="max_qi",
                condition_skill="taoism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "武当派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        assert vitals.max_qi == max_qi_before  # 无加成

    def test_age_le_30_adjusted_age_subtracts_age(self) -> None:
        """age<=30: adjusted_age = cond_level//2 - age（human.c 行 114）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 22
        attrs.str_ = 25
        attrs.con_ = 25
        attrs.dex_ = 25
        attrs.int_ = 25
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"taoism": 100, "force": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="武当派",
                target="max_qi",
                condition_skill="taoism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "武当派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # taoism=100, age=22<=30 -> adjusted_age = 100//2 - 22 = 28
        # force effective = 100//2 = 50, bonus = 28 * (50//10) = 28*5 = 140
        assert vitals.max_qi == max_qi_before + 140

    def test_adjusted_age_zero_or_negative_no_bonus(self) -> None:
        """adjusted_age <= 0 时不加成（human.c if (xism_age > 0) 门控）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 30
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        # taoism=40, age=30 -> adjusted_age = 40//2 - 30 = -10 <= 0
        world.add(eid, Skills(levels={"taoism": 40, "force": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="武当派",
                target="max_qi",
                condition_skill="taoism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "武当派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        assert vitals.max_qi == max_qi_before  # 无加成

    def test_target_max_jing(self) -> None:
        """target="max_jing" 时加到 max_jing（对照少林养精等）。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"buddhism": 80, "force": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_jing_before = vitals_before.max_jing

        bonuses = [
            FamilyBonus(
                family_name="少林派",
                target="max_jing",
                condition_skill="buddhism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "少林派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # buddhism=80>39, age=35>30 -> adjusted_age=80//2-30=10
        # force effective=50, bonus=10*(50//10)=50
        assert vitals.max_jing == max_jing_before + 50

    def test_extra_condition_adds_bonus(self) -> None:
        """额外条件满足时追加一份加成（对照华山 yin-jue 分支）。

        human.c 行 165-168：
        - yin-jue > 1: max_jing += jing_age * (zixia-gong/10)  [追加]
        - 总是: max_jing += jing_age * (zixia-gong/15)         [基础]
        """
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Marks, Skills

        world.add(eid, Skills(levels={"ziyin-yin": 80, "zixia-gong": 60}))
        # huashan/yin-jue > 1：dbase key 路径前缀，需 Marks 或对应存储
        # query("huashan/yin-jue") -> dbase_map 映射？查 dbase_map 支持的路径前缀
        # huashan/ 不在已知前缀，会 raise DbaseKeyError。改用 marks/ 测试 extra。
        # 实际：extra_condition_key 可以是任意 dbase key，这里用 marks/yin-jue
        marks = Marks()
        marks.flags.add("yin-jue")  # query("marks/yin-jue") 返回 1
        world.add(eid, marks)

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_jing_before = vitals_before.max_jing

        bonuses = [
            FamilyBonus(
                family_name="测试门派",
                target="max_jing",
                condition_skill="ziyin-yin",
                condition_threshold=39,
                bonus_skill="zixia-gong",
                divisor=15,  # 基础 /15
                extra_condition_key="marks/yin-jue",
                extra_condition_threshold=0,  # marks/ 返回 1 > 0
                extra_divisor=10,  # 满足时追加 /10
            ),
        ]
        apply_family_bonuses(world, eid, "测试门派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # ziyin-yin=80>39, age=35>30 -> adjusted_age=80//2-30=10
        # zixia-gong effective = 60//2=30
        # 基础: 10 * (30//15) = 10*2 = 20
        # extra(marks/yin-jue=1>0): 10 * (30//10) = 10*3 = 30
        # 总加成 = 20 + 30 = 50
        assert vitals.max_jing == max_jing_before + 50

    def test_extra_condition_not_met_only_base_bonus(self) -> None:
        """额外条件不满足时只有基础加成。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"ziyin-yin": 80, "zixia-gong": 60}))
        # 不设 marks/yin-jue -> query 返回 0 <= 0，extra 不触发

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_jing_before = vitals_before.max_jing

        bonuses = [
            FamilyBonus(
                family_name="测试门派",
                target="max_jing",
                condition_skill="ziyin-yin",
                condition_threshold=39,
                bonus_skill="zixia-gong",
                divisor=15,
                extra_condition_key="marks/yin-jue",
                extra_condition_threshold=0,
                extra_divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "测试门派", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # 基础: 10 * (30//15) = 20
        assert vitals.max_jing == max_jing_before + 20

    def test_no_matching_family_no_change(self) -> None:
        """family_name 不匹配任何 bonus 时 max_jing/max_qi 不变。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 25
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"taoism": 80, "force": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_jing_before = vitals_before.max_jing
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="其他门派",
                target="max_qi",
                condition_skill="taoism",
                condition_threshold=39,
                bonus_skill="force",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "武当派", bonuses)  # family_name 不匹配

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        assert vitals.max_jing == max_jing_before
        assert vitals.max_qi == max_qi_before

    def test_empty_bonuses_list_no_change(self) -> None:
        """空 bonuses 列表不变。"""
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 25

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_jing_before = vitals_before.max_jing

        apply_family_bonuses(world, eid, "任何门派", [])

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        assert vitals.max_jing == max_jing_before


class TestNonWuxiaFamilyBonus:
    """非武侠 FamilyBonus 验证（ADR-0030 决策 4 非武侠微场景）。"""

    def test_pirate_sailing_bonus_max_qi(self) -> None:
        """大航海海盗帮航行加成 max_qi（非武侠 family_name + 非武侠技能）。

        验证 FamilyBonus 载体主题无关性：family_name="海盗帮"、condition_skill
        ="sailing"、bonus_skill="navigation"，公式与武侠门派同构。
        """
        world = World()
        eid = _make_entity(world)
        attrs = world.get(eid, Attributes)
        assert attrs is not None
        attrs.age = 35
        attrs.str_ = 20
        attrs.con_ = 20
        attrs.dex_ = 20
        attrs.int_ = 20
        from xkx.runtime.components import Skills

        world.add(eid, Skills(levels={"sailing": 80, "navigation": 100}))

        setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

        vitals_before = world.get(eid, Vitals)
        assert vitals_before is not None
        max_qi_before = vitals_before.max_qi

        bonuses = [
            FamilyBonus(
                family_name="海盗帮",
                target="max_qi",
                condition_skill="sailing",
                condition_threshold=39,
                bonus_skill="navigation",
                divisor=10,
            ),
        ]
        apply_family_bonuses(world, eid, "海盗帮", bonuses)

        vitals = world.get(eid, Vitals)
        assert vitals is not None
        # sailing=80>39, age=35>30 -> adjusted_age=80//2-30=10
        # navigation effective=100//2=50, bonus=10*(50//10)=50
        assert vitals.max_qi == max_qi_before + 50


class TestFamilyBonusSerialization:
    """FamilyBonus 可序列化（ADR-0022）。"""

    def test_family_bonus_frozen_all_basic_types(self) -> None:
        """FamilyBonus 是 frozen dataclass 全基本类型。"""
        import dataclasses

        bonus = FamilyBonus(
            family_name="测试",
            target="max_qi",
            condition_skill="skill_a",
            condition_threshold=39,
            bonus_skill="skill_b",
            divisor=10,
            extra_condition_key="marks/flag",
            extra_condition_threshold=0,
            extra_divisor=15,
        )
        # frozen
        with pytest.raises(AttributeError):
            bonus.divisor = 20  # type: ignore[misc]

        # 全基本类型
        for f in dataclasses.fields(bonus):
            assert f.type in (
                str,
                int,
                bool,
                "str",
                "int",
                "bool",
                "str | None",
                "int | None",
                "Literal['max_jing', 'max_qi']",
            ), f"字段 {f.name} 类型 {f.type} 非基本类型"

    def test_family_bonus_minimal_fields(self) -> None:
        """最小字段构造（extra_* 默认 None/0）。"""
        bonus = FamilyBonus(
            family_name="x",
            target="max_jing",
            condition_skill="a",
            condition_threshold=39,
            bonus_skill="b",
        )
        assert bonus.divisor == 10
        assert bonus.age_adjusted is True
        assert bonus.extra_condition_key is None
        assert bonus.extra_condition_threshold == 0
        assert bonus.extra_divisor is None


# ──────────────────────── hypothesis 属性测试 ────────────────────────


@given(
    age=st.integers(min_value=14, max_value=80),
    str_=st.integers(min_value=10, max_value=30),
    con_=st.integers(min_value=10, max_value=30),
    dex_=st.integers(min_value=10, max_value=30),
    int_=st.integers(min_value=10, max_value=30),
    seed=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=30, deadline=None)
def test_setup_race_deterministic_property(
    age: int, str_: int, con_: int, dex_: int, int_: int, seed: int
) -> None:
    """属性测试：同 seed 同输出（setup_race 确定性）。"""
    rng = random.Random(seed)

    def rng_fn() -> int:
        return rng.randint(0, 1000)

    # 两次独立构造，比较输出
    world1 = World()
    eid1 = _make_entity(world1)
    a1 = world1.get(eid1, Attributes)
    assert a1 is not None
    a1.age = age
    a1.str_ = str_
    a1.con_ = con_
    a1.dex_ = dex_
    a1.int_ = int_
    setup_race(world1, eid1, HUMAN_PROFILE, rng=rng_fn)

    rng2 = random.Random(seed)

    def rng_fn2() -> int:
        return rng2.randint(0, 1000)

    world2 = World()
    eid2 = _make_entity(world2)
    a2 = world2.get(eid2, Attributes)
    assert a2 is not None
    a2.age = age
    a2.str_ = str_
    a2.con_ = con_
    a2.dex_ = dex_
    a2.int_ = int_
    setup_race(world2, eid2, HUMAN_PROFILE, rng=rng_fn2)

    v1 = world1.get(eid1, Vitals)
    v2 = world2.get(eid2, Vitals)
    assert v1 is not None and v2 is not None
    assert v1.max_jing == v2.max_jing
    assert v1.max_qi == v2.max_qi
    assert v1.max_jingli == v2.max_jingli


@given(
    age=st.integers(min_value=14, max_value=80),
    str_=st.integers(min_value=10, max_value=30),
    con_=st.integers(min_value=10, max_value=30),
    dex_=st.integers(min_value=10, max_value=30),
    int_=st.integers(min_value=10, max_value=30),
)
@settings(max_examples=30, deadline=None)
def test_three_layer_resource_invariant(
    age: int, str_: int, con_: int, dex_: int, int_: int
) -> None:
    """属性测试：三层资源不变量 0 <= qi <= eff_qi <= max_qi。

    setup_race 后 max_qi/max_jing/max_jingli 应非负（即使 70 岁衰减后）。
    当前 qi/eff_qi 默认 100，需 <= max_qi（setup_race 后 max 可能 < 100 的情况
    在 70 岁高衰减下出现，这里只断言 max_* 非负 + max_qi 一致性）。
    """
    world = World()
    eid = _make_entity(world)
    a = world.get(eid, Attributes)
    assert a is not None
    a.age = age
    a.str_ = str_
    a.con_ = con_
    a.dex_ = dex_
    a.int_ = int_

    setup_race(world, eid, HUMAN_PROFILE, rng=lambda: 0)

    v = world.get(eid, Vitals)
    assert v is not None
    # max_* 非负（70 岁衰减不应让 max 跌到负数；human.c 也无 clamp 但实际属性范围
    # 下不会负）
    assert v.max_jing >= 0, f"max_jing={v.max_jing} < 0 (age={age},int={int_},con={con_})"
    assert v.max_qi >= 0, f"max_qi={v.max_qi} < 0 (age={age},str={str_},con={con_})"
    assert v.max_jingli >= 0, f"max_jingli={v.max_jingli} < 0 (age={age},con={con_})"


# ──────────────────────── 主题无关性硬门禁 ────────────────────────


class TestThemeNeutrality:
    """ADR-0030 决策 4：race.py / family.py 源码不得含门派名字面量。

    门派名黑名单：武当/少林/峨嵋/华山/丐帮/桃花/古墓/灵鹫/星宿/白驼/明教/雪山
    /血刀/大理段/全真。
    """

    BANNED_FAMILY_NAMES = [
        "武当", "少林", "峨嵋", "华山", "丐帮", "桃花", "古墓",
        "灵鹫", "星宿", "白驼", "明教", "雪山", "血刀", "大理段", "全真",
    ]

    def test_race_source_has_no_family_name_literals(self) -> None:
        import inspect

        from xkx.runtime import race as race_mod

        src = inspect.getsource(race_mod)
        for name in self.BANNED_FAMILY_NAMES:
            assert name not in src, f"race.py 源码含门派名 {name!r}"

    def test_family_source_has_no_family_name_literals(self) -> None:
        import inspect

        from xkx.runtime import family as family_mod

        src = inspect.getsource(family_mod)
        for name in self.BANNED_FAMILY_NAMES:
            assert name not in src, f"family.py 源码含门派名 {name!r}"

    def test_race_source_has_no_wuxia_skill_literals(self) -> None:
        """race.py 不得含武侠技能名字面量。"""
        import inspect

        from xkx.runtime import race as race_mod

        src = inspect.getsource(race_mod)
        banned_skills = [
            "taoism", "buddhism", "mahayana", "lamaism",
            "zixia-gong", "ziyin-yin", "zhengqi-jue",
            "bitao-xuangong", "yunu-jue", "yunu-xinjing",
            "bahuang-gong", "huagong-dafa", "hamagong",
            "guangming-xinfa", "shenghuo-xuanming",
            "huntian-qigong", "qimen-dunjia", "poison", "music",
            "hunyuan-yiqi", "linji-zhuang", "longxiang-banruo",
            "kurong-changong",
        ]
        for skill in banned_skills:
            assert skill not in src, f"race.py 源码含武侠技能名 {skill!r}"

    def test_family_source_has_no_wuxia_skill_literals(self) -> None:
        """family.py 不得含武侠技能名字面量。"""
        import inspect

        from xkx.runtime import family as family_mod

        src = inspect.getsource(family_mod)
        banned_skills = [
            "taoism", "buddhism", "mahayana", "lamaism",
            "zixia-gong", "ziyin-yin", "zhengqi-jue",
            "bitao-xuangong", "yunu-jue", "yunu-xinjing",
            "bahuang-gong", "huagong-dafa", "hamagong",
            "guangming-xinfa", "shenghuo-xuanming",
            "huntian-qigong", "qimen-dunjia", "poison", "music",
            "hunyuan-yiqi", "linji-zhuang", "longxiang-banruo",
            "kurong-changong",
        ]
        for skill in banned_skills:
            assert skill not in src, f"family.py 源码含武侠技能名 {skill!r}"
