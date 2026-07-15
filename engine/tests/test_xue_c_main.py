"""pilot 样本 id=1：xue.c:main 迁移单元测试。

覆盖 8 项后置分支中的关键路径：3 处 RNG、spouse 婚次/经验门控、
linji-zhuang 招式名特例、prevent_learn、env/no_teach、教师/玩家精力不足、
combat_exp 门控（被门控时不扣潜能）。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.xue_c_main import xue_c_main

from xkx.combat.context import SkillData
from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    EffectComp,
    FamilyComp,
    Identity,
    Position,
    Progression,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World


def _game(
    *,
    player_family: str = "雪山派",
    teacher_family: str = "雪山派",
    player_skills: dict[str, int] | None = None,
    teacher_skills: dict[str, int] | None = None,
    player_potential: int = 100,
    player_jing: int = 500,
    teacher_jing: int = 500,
    player_exp: int = 50000,
    teacher_exp: int = 50000,
    player_gender: str = "男性",
    player_int: int = 20,
    is_player_teacher: bool = False,
    master_id: str = "xueshan/gongcang",
    master_name: str = "贡藏",
) -> tuple[Game, int, int]:
    """构造 1 房间 + 玩家 + 教师的最小场景。"""
    world = World()

    player = world.new_entity()
    world.add(player, Identity(
        name="玩家", aliases=["player"], is_player=True, prototype_id="player"
    ))
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(
        family=player_family, gender=player_gender, int_=player_int
    ))
    world.add(player, Vitals(jing=player_jing, max_jing=player_jing))
    world.add(player, Progression(
        potential=player_potential, combat_exp=player_exp
    ))
    world.add(player, Skills(levels=dict(player_skills if player_skills is not None else {})))
    world.add(player, FamilyComp(
        family_name=player_family, master_id=master_id, master_name=master_name
    ))

    teacher = world.new_entity()
    world.add(teacher, Identity(
        name=master_name,
        aliases=[master_id.split("/")[-1]],
        is_player=is_player_teacher,
        prototype_id=master_id,
    ))
    world.add(teacher, Position(room_id="room/test"))
    world.add(teacher, Attributes(family=teacher_family, gender="男性", int_=20))
    world.add(teacher, Vitals(jing=teacher_jing, max_jing=teacher_jing))
    world.add(teacher, Progression(combat_exp=teacher_exp))
    default_teacher_skills = {"xueshan-sword": 50}
    teacher_skills = teacher_skills if teacher_skills is not None else default_teacher_skills
    world.add(teacher, Skills(levels=dict(teacher_skills)))

    return Game(world, {}, rules=[]), player, teacher


def _vitals(world: World, eid: int) -> Vitals:
    v = world.get(eid, Vitals)
    assert v is not None
    return v


def _prog(world: World, eid: int) -> Progression:
    p = world.get(eid, Progression)
    assert p is not None
    return p


def _skills(world: World, eid: int) -> Skills:
    s = world.get(eid, Skills)
    assert s is not None
    return s


def test_busy_fails() -> None:
    """busy 状态阻止学习。"""
    game, player, _ = _game()
    busy = game.world.new_entity()
    game.world.add(busy, EffectComp(
        effect_id="exercise", kind="busy", target_id=player, duration=1
    ))
    assert xue_c_main(game, player, "贡藏", "xueshan-sword") == ["你现在正忙着呢。"]


def test_not_apprentice_and_not_recognized_rejected(monkeypatch: Any) -> None:
    """非弟子、未认可、非配偶 -> 随机拒绝消息。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main._is_apprentice_of",
        lambda *_args, **_kw: False,
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[0])
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert len(msgs) == 1
    assert "您太客气了" in msgs[0]


def test_master_skill_zero_fails() -> None:
    """教师不会该技能 -> 失败。"""
    game, player, _ = _game(teacher_skills={})
    assert xue_c_main(game, player, "贡藏", "xueshan-sword") == [
        "这项技能你恐怕必须找别人学了。"
    ]


def test_prevent_learn_fails(monkeypatch: Any) -> None:
    """prevent_learn 返回 True -> 拒绝教。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.prevent_learn",
        lambda *_args, **_kw: True,
    )
    assert xue_c_main(game, player, "贡藏", "xueshan-sword") == [
        "贡藏不愿意教你这项技能。"
    ]


def test_player_skill_ge_master_fails() -> None:
    """玩家技能 ≥ 教师 -> 失败。"""
    game, player, _ = _game(
        player_skills={"xueshan-sword": 60}, teacher_skills={"xueshan-sword": 50}
    )
    assert xue_c_main(game, player, "贡藏", "xueshan-sword") == [
        "这项技能你的程度已经不输你师父了。"
    ]


def test_env_no_teach_fails(monkeypatch: Any) -> None:
    """env/no_teach 打开 -> 主消息 + 拒绝。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.query_env_no_teach",
        lambda *_args, **_kw: True,
    )
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert msgs[0] == "你向贡藏请教有关「xueshan-sword」的疑问。"
    assert "并不准备回答你的问题" in msgs[1]


def test_teacher_tired_fails() -> None:
    """教师精力不足 -> 主消息 + 太累拒绝。"""
    game, player, teacher = _game(teacher_jing=1)
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert msgs[0].startswith("你向贡藏请教")
    assert "太累了" in msgs[1]
    assert _vitals(game.world, teacher).jing == 1


def test_player_tired_no_improve() -> None:
    """玩家精力不足 -> 不扣潜能、不提升、精力清零。"""
    game, player, _ = _game(player_jing=1)
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "今天太累了" in msgs[1]
    assert _vitals(game.world, player).jing == 0
    assert _prog(game.world, player).potential == 100
    assert "xueshan-sword" not in _skills(game.world, player).levels


def test_blocked_by_exp_deducts_jing_not_potential(monkeypatch: Any) -> None:
    """martial 技能被 combat_exp 门控时：扣精力、不扣潜能、不提升。"""
    game, player, _ = _game(
        player_exp=10,
        player_skills={"xueshan-sword": 10},
        teacher_skills={"xueshan-sword": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.get_skill_data",
        lambda _skill_id: SkillData(skill_type="martial", valid_learn=True),
    )
    before_jing = _vitals(game.world, player).jing
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "缺乏实战经验" in msgs[1]
    assert _prog(game.world, player).potential == 100
    assert _vitals(game.world, player).jing < before_jing
    assert _skills(game.world, player).levels["xueshan-sword"] == 10


def test_success_improves_skill(monkeypatch: Any) -> None:
    """正常学习：扣潜能、扣精力、提升技能。"""
    game, player, _ = _game(player_skills={"xueshan-sword": 1})
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    before_jing = _vitals(game.world, player).jing
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "似乎有些心得" in msgs[1]
    assert _prog(game.world, player).potential == 99
    assert _vitals(game.world, player).jing < before_jing
    assert _skills(game.world, player).levels["xueshan-sword"] > 1


def test_emei_slow_factor_halves_gain(monkeypatch: Any) -> None:
    """峨嵋派男徒且 int < 20+random(25) -> slow_factor=2，消息带"想了良久"。"""
    game, player, _ = _game(
        player_family="峨嵋派",
        teacher_family="峨嵋派",
        player_gender="男性",
        player_int=20,
        player_skills={"xueshan-sword": 10},
    )
    # random(25) 返回 1，使 20 < 20+1 成立；gain random(int) 固定 10
    monkeypatch.setattr("random.randint", lambda a, b: 1 if b == 24 else 10)
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "想了良久" in msgs[1]


def test_spouse_married_times_penalty(monkeypatch: Any) -> None:
    """配偶且 skill ≥ master - 20*(married_times-1) -> 拒绝。"""
    game, player, _ = _game(
        player_skills={"xueshan-sword": 40},
        teacher_skills={"xueshan-sword": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.is_spouse_of",
        lambda *_args, **_kw: True,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.query_married_times",
        lambda *_args, **_kw: 2,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.query_spouse_title",
        lambda *_args, **_kw: "前妻",
    )
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "有点不大愿意教你" in msgs[0]


def test_spouse_low_combat_exp_martial_fails(monkeypatch: Any) -> None:
    """配偶互教 martial 且任一方 exp < 10000 -> 拒绝。"""
    game, player, _ = _game(
        player_exp=5000,
        teacher_exp=5000,
        player_skills={"xueshan-sword": 10},
        teacher_skills={"xueshan-sword": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.is_spouse_of",
        lambda *_args, **_kw: True,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.get_skill_data",
        lambda _skill_id: SkillData(skill_type="martial", valid_learn=True),
    )
    assert xue_c_main(game, player, "贡藏", "xueshan-sword") == [
        "你们夫妇实战经验还不足，不能互相传授武艺！"
    ]


def test_spouse_success_non_martial(monkeypatch: Any) -> None:
    """配偶互教非 martial（知识类）-> 不受经验门控，正常学习。"""
    game, player, _ = _game(
        player_exp=5000,
        teacher_exp=5000,
        player_skills={"literate": 10},
        teacher_skills={"literate": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.is_spouse_of",
        lambda *_args, **_kw: True,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    msgs = xue_c_main(game, player, "贡藏", "literate")
    assert "似乎有些心得" in msgs[1]
    assert _prog(game.world, player).potential == 99


def test_linji_zhuang_message(monkeypatch: Any) -> None:
    """linji-zhuang 且 query_skill_name 返回名称 -> 特殊修养消息。"""
    game, player, _ = _game(
        player_skills={"linji-zhuang": 1},
        teacher_skills={"linji-zhuang": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.xue_c_main.query_skill_name",
        lambda _skill, _level: "坐忘",
    )
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    msgs = xue_c_main(game, player, "贡藏", "linji-zhuang")
    assert "对「坐忘」的修养似乎有所提高" in msgs[1]


def test_query_skill_name_none_fallback(monkeypatch: Any) -> None:
    """query_skill_name 返回 None -> 走兜底消息。"""
    game, player, _ = _game(player_skills={"xueshan-sword": 10})
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    msgs = xue_c_main(game, player, "贡藏", "xueshan-sword")
    assert "似乎有些心得" in msgs[1]
    assert "这一招" not in msgs[1]
