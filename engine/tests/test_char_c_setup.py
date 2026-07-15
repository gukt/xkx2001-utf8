"""pilot 样本 id=11：char.c:setup 迁移单元测试。

覆盖 5 步初始化序列的关键分支：seteuid 标记 / heart_beat / tick RNG 范围 /
enable_player 移除 DISABLED flag + living-name 注册 / CHAR_D->setup_char 编排
（human dispatch、属性随机、max_jing 年龄分层、jing/eff 钳位、玩家 force
max_neili 钳位、NPC shen 公式、NPC force 自动 set、reset_action 调用）。
"""

from __future__ import annotations

from tools.sampling.pilot.samples.char_c_setup import (
    _clear_living_registry,
    find_living,
    setup,
)

from xkx.runtime.commands import Game
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

_DISABLED_FLAG = "disabled"


def _game(
    *,
    is_player: bool = True,
    name: str = "测试侠客",
    age: int | None = None,
    str_: int | None = None,
    con_: int | None = None,
    int_: int | None = None,
    dex_: int | None = None,
    combat_exp: int = 1000,
    max_neili: int = 0,
    force_level: int = 0,
    force_map: str | None = None,
    mapped_skill: tuple[str, int] | None = None,
    disabled: bool = False,
) -> tuple[Game, int]:
    """构造 1 实体最小场景（setup 不依赖房间，无需 Position）。"""
    _clear_living_registry()
    world = World()

    eid = world.new_entity()
    world.add(eid, Identity(name=name, is_player=is_player, prototype_id="player"))

    attrs = Attributes()
    if age is not None:
        attrs.age = age
    if str_ is not None:
        attrs.str_ = str_
    if con_ is not None:
        attrs.con_ = con_
    if int_ is not None:
        attrs.int_ = int_
    if dex_ is not None:
        attrs.dex_ = dex_
    world.add(eid, attrs)

    vitals = Vitals(max_neili=max_neili, neili=max_neili)
    world.add(eid, vitals)

    world.add(eid, Progression(combat_exp=combat_exp))
    world.add(eid, Equipment())

    skills = Skills()
    if force_level:
        skills.levels["force"] = force_level
    if force_map:
        skills.skill_map["force"] = force_map
    if mapped_skill:
        skills.levels[mapped_skill[0]] = mapped_skill[1]
    world.add(eid, skills)

    marks = Marks()
    if disabled:
        marks.flags.add(_DISABLED_FLAG)
    world.add(eid, marks)

    world.add(eid, TitleComp())

    return Game(world, {}, rules=[]), eid


def _vitals(world: World, eid: int) -> Vitals:
    v = world.get(eid, Vitals)
    assert v is not None
    return v


def _attrs(world: World, eid: int) -> Attributes:
    a = world.get(eid, Attributes)
    assert a is not None
    return a


def test_setup_runs_all_five_steps() -> None:
    """主路径：5 步全执行，SetupResult 各标记置位，无消息推送。"""
    game, eid = _game()
    res = setup(game, eid, rng=lambda n: 3)
    assert res.euid_set is True
    assert res.heart_beat_enabled is True
    assert res.player_enabled is True
    assert res.living_name_registered is True
    assert res.race == "人类"
    assert res.reset_action_called is True
    assert res.messages == []


def test_non_human_race_raises() -> None:
    """未知种族名走 chard.c:57-58 default error 分支 raise。"""
    game, eid = _game()
    try:
        setup(game, eid, race="外星人", rng=lambda n: 0)
    except ValueError as ex:
        assert "Chard: undefined race" in str(ex)
    else:
        raise AssertionError("未知种族应 raise ValueError")


def test_known_nonhuman_race_noop_no_raise() -> None:
    """已知非 human 种族（妖魔）daemon 未迁移，noop 不 raise（chard.c 有 case）。"""
    game, eid = _game()
    res = setup(game, eid, race="妖魔", rng=lambda n: 0)
    assert res.race == "妖魔"


def test_tick_rng_range() -> None:
    """tick = 5 + random(10)，范围 [5, 14]，对照 char.c L54。"""
    game, eid = _game()
    res = setup(game, eid, rng=lambda n: 0)
    assert res.tick == 5
    game2, eid2 = _game()
    res2 = setup(game2, eid2, rng=lambda n: 9)
    assert res2.tick == 14


def test_enable_player_removes_disabled_flag() -> None:
    """enable_player 移除 disable_player 设的 DISABLED_FLAG（death.py:59）。"""
    game, eid = _game(disabled=True)
    marks = game.world.get(eid, Marks)
    assert marks is not None
    assert _DISABLED_FLAG in marks.flags
    setup(game, eid, rng=lambda n: 0)
    assert _DISABLED_FLAG not in marks.flags


def test_living_name_registered_and_findable() -> None:
    """set_living_name 桩注册 Identity.name，find_living 反查到 entity_id。"""
    game, eid = _game(name="令狐冲")
    setup(game, eid, rng=lambda n: 0)
    assert find_living("令狐冲") == eid


def test_living_name_not_registered_without_identity() -> None:
    """无 Identity 时 living_name_registered=False（桩回落）。"""
    _clear_living_registry()
    world = World()
    eid = world.new_entity()
    world.add(eid, Attributes())
    world.add(eid, Vitals())
    world.add(eid, Progression())
    world.add(eid, Equipment())
    world.add(eid, Skills())
    world.add(eid, Marks())
    world.add(eid, TitleComp())
    game = Game(world, {}, rules=[])
    res = setup(game, eid, rng=lambda n: 0)
    assert res.living_name_registered is False


def test_attribute_randomization_when_undefined() -> None:
    """属性默认值 20（哨兵）时随机成 10 + random(21)。rng 固定 5 -> str=15。"""
    game, eid = _game()
    setup(game, eid, rng=lambda n: 5)
    attrs = _attrs(game.world, eid)
    assert attrs.str_ == 15
    assert attrs.con_ == 15
    assert attrs.age == 14  # 默认 20 哨兵兜底成 14


def test_attribute_preserved_when_set() -> None:
    """显式设置的属性不被随机覆盖（age=22, str=25 保留）。"""
    game, eid = _game(age=22, str_=25, con_=18, int_=16, dex_=14)
    setup(game, eid, rng=lambda n: 5)
    attrs = _attrs(game.world, eid)
    assert attrs.age == 22
    assert attrs.str_ == 25
    assert attrs.con_ == 18
    assert attrs.int_ == 16
    assert attrs.dex_ == 14


def test_max_jing_age_layered_formula() -> None:
    """max_jing 年龄分层：age=22, int=24, con=24 -> 100+(22-14)*(48)//2=292。

    int/con 不取默认 20（_setup_human 用 20 作"未定义"哨兵会随机覆盖）。
    """
    game, eid = _game(age=22, int_=24, con_=24, str_=25, dex_=22)
    setup(game, eid, rng=lambda n: 0)
    v = _vitals(game.world, eid)
    assert v.max_jing == 292
    # max_qi = 100+(age-14)*(con+str)//2 = 100+8*(24+25)//2 = 100+196 = 296
    assert v.max_qi == 296


def test_jing_qi_jingli_default_to_max_when_zero() -> None:
    """jing/qi/jingli <=0 视为未初始化，兜底到 max（chard.c L64-66）。"""
    game, eid = _game(age=22, int_=24, con_=24, str_=25, dex_=22)
    v = _vitals(game.world, eid)
    v.jing = 0
    v.qi = 0
    v.jingli = 0
    setup(game, eid, rng=lambda n: 0)
    assert v.jing == v.max_jing
    assert v.qi == v.max_qi
    assert v.jingli == v.max_jingli


def test_eff_clamped_to_max() -> None:
    """eff_jing/eff_qi 超 max 时钳到 max（chard.c L68-69）。"""
    game, eid = _game(age=22, int_=20, con_=20)
    v = _vitals(game.world, eid)
    v.eff_jing = 9999
    v.eff_qi = 9999
    setup(game, eid, rng=lambda n: 0)
    assert v.eff_jing == v.max_jing
    assert v.eff_qi == v.max_qi


def test_player_force_clamps_max_neili() -> None:
    """玩家 force 有效 > 基础时，max_neili 钳到 force*con*2/3（chard.c L75-81）。

    force 基础 0，映射到 neigong 100 -> eff = 0//2 + 100 = 100 > 0。
    con=30 -> cap = 0*30*2//3 = 0，max_neili 被钳到 0。
    """
    game, eid = _game(
        is_player=True, con_=30, max_neili=500,
        force_map="neigong", mapped_skill=("neigong", 100),
    )
    v = _vitals(game.world, eid)
    assert v.max_neili == 500
    setup(game, eid, rng=lambda n: 0)
    assert v.max_neili == 0
    assert v.neili == 0


def test_npc_shen_formula() -> None:
    """NPC shen = shen_type(0) * combat_exp / 10（chard.c L99-104，shen_type 后置为 0）。"""
    game, eid = _game(is_player=False, combat_exp=5000)
    title = game.world.get(eid, TitleComp)
    assert title is not None
    assert title.shen == 0
    setup(game, eid, rng=lambda n: 0)
    # shen_type=0（POSTPONED），故 NPC shen = 0 * 5000 // 10 = 0
    assert title.shen == 0


def test_npc_force_auto_set_from_max_neili() -> None:
    """NPC 有 max_neili 但 force<1 时，set force=max_neili/6（chard.c L94-95）。"""
    game, eid = _game(is_player=False, max_neili=600)
    skills = game.world.get(eid, Skills)
    assert skills is not None
    assert skills.levels.get("force", 0) == 0
    setup(game, eid, rng=lambda n: 0)
    assert skills.levels["force"] == 100  # 600 // 6


def test_npc_force_not_set_when_already_has_force() -> None:
    """NPC 已有 force 技能时不覆盖（chard.c L94 force<1 门控）。"""
    game, eid = _game(is_player=False, max_neili=600, force_level=50)
    skills = game.world.get(eid, Skills)
    assert skills is not None
    setup(game, eid, rng=lambda n: 0)
    assert skills.levels["force"] == 50


def test_max_encumbrance_from_str() -> None:
    """max_encumbrance = str*5000（chard.c L109-111，无 query_str 派生简化）。

    str 取 25（非默认 20 哨兵，避免被随机覆盖）。
    """
    game, eid = _game(str_=25)
    setup(game, eid, rng=lambda n: 0)
    equip = game.world.get(eid, Equipment)
    assert equip is not None
    assert equip.max_encumbrance == 125000


def test_weight_written_to_equipment() -> None:
    """weight = 40000 + (str-10)*2000 经 dbase key 写 Equipment.encumbrance。"""
    game, eid = _game(str_=25)
    setup(game, eid, rng=lambda n: 0)
    equip = game.world.get(eid, Equipment)
    assert equip is not None
    # weight = 40000 + (25-10)*2000 = 70000
    assert equip.encumbrance == 70000
