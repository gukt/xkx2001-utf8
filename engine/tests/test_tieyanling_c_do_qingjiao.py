"""pilot 样本 id=3：tieyanling.c:do_qingjiao 迁移单元测试。

覆盖明教门派门控、teach_skillsname 白名单、literate 拒绝、prevent_learn
静默成功、教师/玩家精力不足、combat_exp 门控等关键分支。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.tieyanling_c_do_qingjiao import (
    tieyanling_c_do_qingjiao,
)

from xkx.combat.context import SkillData
from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    EffectComp,
    Identity,
    Position,
    Progression,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World


def _game(
    *,
    player_family: str = "明教",
    teacher_family: str = "明教",
    player_skills: dict[str, int] | None = None,
    teacher_skills: dict[str, int] | None = None,
    player_potential: int = 100,
    player_jing: int = 500,
    teacher_jing: int = 500,
    player_exp: int = 50000,
    player_int: int = 20,
    teacher_name: str = "张无忌",
    teacher_id: str = "mingjiao/zhangwuji",
) -> tuple[Game, int, int]:
    """构造 1 房间 + 明教玩家 + 教师的最小场景。"""
    world = World()

    player = world.new_entity()
    world.add(player, Identity(
        name="玩家", aliases=["player"], is_player=True, prototype_id="player"
    ))
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(
        family=player_family, gender="男性", int_=player_int
    ))
    world.add(player, Vitals(jing=player_jing, max_jing=player_jing))
    world.add(player, Progression(
        potential=player_potential, combat_exp=player_exp
    ))
    world.add(player, Skills(levels=dict(
        player_skills if player_skills is not None else {}
    )))

    teacher = world.new_entity()
    world.add(teacher, Identity(
        name=teacher_name,
        aliases=[teacher_id.split("/")[-1]],
        is_player=False,
        prototype_id=teacher_id,
    ))
    world.add(teacher, Position(room_id="room/test"))
    world.add(teacher, Attributes(family=teacher_family, gender="男性", int_=20))
    world.add(teacher, Vitals(jing=teacher_jing, max_jing=teacher_jing))
    world.add(teacher, Progression(combat_exp=50000))
    default_teacher_skills = {"jiuyang-shengong": 50}
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
    """busy 状态阻止请教。"""
    game, player, _ = _game()
    busy = game.world.new_entity()
    game.world.add(busy, EffectComp(
        effect_id="exercise", kind="busy", target_id=player, duration=1
    ))
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "你现在正忙着呢。"
    ]


def test_teacher_not_mingjiao_fails() -> None:
    """教师非明教 -> 拒绝。"""
    game, player, _ = _game(teacher_family="雪山派")
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "你只能向明教中的兄弟请教武功。"
    ]


def test_player_not_mingjiao_fails() -> None:
    """玩家非明教 -> 拒绝。"""
    game, player, _ = _game(player_family="雪山派")
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "你非我明教兄弟，如何搞得这铁焰令，居然还来向我讨教功夫？"
    ]


def test_self_teach_fails(monkeypatch: Any) -> None:
    """自己向自己请教 -> 拒绝。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao._find_npc_in_room",
        lambda *_args, **_kw: player,
    )
    assert tieyanling_c_do_qingjiao(game, player, "玩家", "jiuyang-shengong") == [
        "自己向自己请教？"
    ]


def test_empty_teach_list_fails() -> None:
    """教师 teach_skillsname 为空 -> 拒绝。"""
    game, player, _ = _game()
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "张无忌没什么可以请教的武功。"
    ]


def test_literate_refused(monkeypatch: Any) -> None:
    """teach_skillsname 含 literate 时仍然拒绝。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["literate", "jiuyang-shengong"],
    )
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "literate") == [
        "张无忌说道：读书写字只能靠你平时自己在书院学习，我不能传授你。"
    ]


def test_skill_not_in_whitelist_fails(monkeypatch: Any) -> None:
    """技能不在 teach_skillsname 中 -> 拒绝。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["other-skill"],
    )
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "张无忌不能传授你这项武功。"
    ]


def test_prevent_learn_silent_success(monkeypatch: Any) -> None:
    """prevent_learn 返回 True -> 静默成功（空消息）。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.prevent_learn",
        lambda *_args, **_kw: True,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == []


def test_player_skill_ge_master_fails(monkeypatch: Any) -> None:
    """玩家技能 ≥ 教师 -> 拒绝。"""
    game, player, _ = _game(
        player_skills={"jiuyang-shengong": 60},
        teacher_skills={"jiuyang-shengong": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    assert tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong") == [
        "张无忌呵呵一笑：这项技能你已经不输与我，我那里还敢教阁下什么？"
    ]


def test_env_no_teach_fails(monkeypatch: Any) -> None:
    """env/no_teach 打开 -> 主消息 + 拒绝。"""
    game, player, _ = _game()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_env_no_teach",
        lambda *_args, **_kw: True,
    )
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert msgs[0] == "你向张无忌请教有关「jiuyang-shengong」的疑问。"
    assert "并不准备回答你什么" in msgs[1]


def test_teacher_tired_fails(monkeypatch: Any) -> None:
    """教师精力不足 -> 主消息 + 太累拒绝。"""
    game, player, teacher = _game(teacher_jing=1)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert msgs[0].startswith("你向张无忌请教")
    assert "太累了" in msgs[1]
    assert _vitals(game.world, teacher).jing == 1


def test_player_tired_no_improve(monkeypatch: Any) -> None:
    """玩家精力不足 -> 不扣潜能、不提升、返回特殊消息。"""
    game, player, _ = _game(player_jing=1)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert "你现在精神不够" in msgs[1]
    assert _vitals(game.world, player).jing == 1
    assert _prog(game.world, player).potential == 100


def test_blocked_by_exp_deducts_jing_not_potential(monkeypatch: Any) -> None:
    """martial 技能被 combat_exp 门控时：扣精力、不扣潜能、不提升。"""
    game, player, _ = _game(
        player_exp=10,
        player_skills={"jiuyang-shengong": 10},
        teacher_skills={"jiuyang-shengong": 50},
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.get_skill_data",
        lambda _skill_id: SkillData(skill_type="martial", valid_learn=True),
    )
    before_jing = _vitals(game.world, player).jing
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert "缺乏实战经验" in msgs[1]
    assert _prog(game.world, player).potential == 100
    assert _vitals(game.world, player).jing < before_jing
    assert _skills(game.world, player).levels["jiuyang-shengong"] == 10


def test_success_improves_skill(monkeypatch: Any) -> None:
    """正常请教：扣潜能、扣精力、提升技能。"""
    game, player, _ = _game(player_skills={"jiuyang-shengong": 1})
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    before_jing = _vitals(game.world, player).jing
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert "似乎有些心得" in msgs[1]
    assert _prog(game.world, player).potential == 99
    assert _vitals(game.world, player).jing < before_jing
    assert _skills(game.world, player).levels["jiuyang-shengong"] > 1


def test_query_skill_name_message(monkeypatch: Any) -> None:
    """query_skill_name 返回名称 -> 招式名消息。"""
    game, player, _ = _game(player_skills={"jiuyang-shengong": 1})
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_teach_skillsname",
        lambda *_args, **_kw: ["jiuyang-shengong"],
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.tieyanling_c_do_qingjiao.query_skill_name",
        lambda _skill, _level: "九阳初现",
    )
    monkeypatch.setattr("random.randint", lambda a, b: 5 if b == 19 else 0)
    msgs = tieyanling_c_do_qingjiao(game, player, "张无忌", "jiuyang-shengong")
    assert "对「九阳初现」这一招似乎有些心得" in msgs[1]
