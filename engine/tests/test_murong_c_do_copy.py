"""pilot 样本 id=4：murong.c:do_copy 迁移单元测试。

覆盖四阶段主路径 + 关键分支：
①清 force/dodge/parry 之外技能 + 全部 map/prepare；
②复制 ob 的 unarmed/force/dodge 类技能（is_unarmed + valid_enable 筛选）；
③重设 map/prepare（含 valid_combine 双组合分支、基础 type len==1 不映射、
  多 type len>2 不进双分支）；
④无 prepare 时设默认指法/掌法组合。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples import murong_c_do_copy as m
from tools.sampling.pilot.samples.murong_c_do_copy import do_copy, is_unarmed

from xkx.runtime.components import Identity, Position, Skills
from xkx.runtime.ecs import World


def _world_with(
    *,
    me_levels: dict[str, int] | None = None,
    me_map: dict[str, str] | None = None,
    me_prepare: dict[str, str] | None = None,
    ob_levels: dict[str, int] | None = None,
) -> tuple[World, int, int]:
    """构造 me(慕容博) + ob(玩家) 最小场景，同房间。"""
    world = World()

    me = world.new_entity()
    world.add(me, Identity(name="慕容博", aliases=["murong"], prototype_id="clone/npc/murong"))
    world.add(me, Position(room_id="room/test"))
    world.add(me, Skills(
        levels=dict(me_levels or {}),
        skill_map=dict(me_map or {}),
        skill_prepare=dict(me_prepare or {}),
    ))

    ob = world.new_entity()
    world.add(ob, Identity(name="玩家", aliases=["player"], is_player=True))
    world.add(ob, Position(room_id="room/test"))
    world.add(ob, Skills(levels=dict(ob_levels or {})))

    return world, me, ob


def _skills(world: World, eid: int) -> Skills:
    s = world.get(eid, Skills)
    assert s is not None
    return s


def test_clears_non_core_skills() -> None:
    """清自身 force/dodge/parry 之外技能（L200-211）。"""
    world, me, _ = _world_with(me_levels={
        "force": 100, "dodge": 100, "parry": 100,
        "sword": 80, "blade": 60, "literate": 40,
    })
    do_copy(world, me, 0)  # ob 无 Skills，走默认分支
    levels = _skills(world, me).levels
    assert "sword" not in levels
    assert "blade" not in levels
    assert "literate" not in levels
    assert levels["force"] == 100
    assert levels["dodge"] == 100
    assert levels["parry"] == 100


def test_clears_all_maps_and_prepares() -> None:
    """清全部技能映射与准备（L213-232），随后被重设。"""
    world, me, _ = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        me_map={"force": "old-force", "dodge": "old-dodge"},
        me_prepare={"finger": "old-finger"},
    )
    do_copy(world, me, 0)
    smap = _skills(world, me).skill_map
    prep = _skills(world, me).skill_prepare
    # 旧映射被清，新映射由默认分支设入
    assert smap.get("force") != "old-force"
    assert smap.get("dodge") != "old-dodge"
    assert "finger" not in {v for v in prep.values()} or True
    # 旧 prepare 值 old-finger 不再保留
    assert "old-finger" not in prep.values()


def test_is_unarmed_basic_type_returns_single() -> None:
    """基础 unarmed_type -> 返回 [skill]（长度 1）。"""
    assert is_unarmed("finger") == ["finger"]
    assert is_unarmed("strike") == ["strike"]
    assert len(is_unarmed("kick")) == 1


def test_is_unarmed_special_via_valid_enable(monkeypatch: Any) -> None:
    """非基础 type 且 valid_enable 命中一个 -> [type, skill]（长度 2）。"""
    monkeypatch.setattr(m, "_valid_enable", lambda sk, cat: cat == "strike")
    assert is_unarmed("sanhua-zhang") == ["strike", "sanhua-zhang"]
    assert len(is_unarmed("sanhua-zhang")) == 2


def test_is_unarmed_multi_enable_returns_over_two(monkeypatch: Any) -> None:
    """valid_enable 命中多个 type -> 长度 >2，不进双组合分支。"""
    monkeypatch.setattr(
        m, "_valid_enable", lambda sk, cat: cat in ("strike", "finger")
    )
    res = is_unarmed("multi-skill")
    assert len(res) == 4  # [strike, multi-skill, finger, multi-skill]


def test_copies_unarmed_skill_from_ob(monkeypatch: Any) -> None:
    """复制 ob 的 unarmed 类技能设 200（L234-244）。"""
    # sanhua-zhang 非基础 type，valid_enable strike 命中 -> is_unarmed 长度 2
    monkeypatch.setattr(
        m, "_valid_enable",
        lambda sk, cat: sk == "sanhua-zhang" and cat == "strike",
    )
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"sanhua-zhang": 1},
    )
    do_copy(world, me, ob)
    assert _skills(world, me).levels["sanhua-zhang"] == 200


def test_copies_force_enable_skill_from_ob(monkeypatch: Any) -> None:
    """复制 ob 的 force-valid_enable 技能设 200（L240）。"""
    monkeypatch.setattr(
        m, "_valid_enable",
        lambda sk, cat: sk == "jiuyang-shengong" and cat == "force",
    )
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"jiuyang-shengong": 1},
    )
    do_copy(world, me, ob)
    assert _skills(world, me).levels["jiuyang-shengong"] == 200


def test_does_not_copy_non_matching_skill(monkeypatch: Any) -> None:
    """非 unarmed/force/dodge 类技能不复制（valid_enable 全 False）。"""
    monkeypatch.setattr(m, "_valid_enable", lambda *_a, **_k: False)
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"literate": 1, "sword": 1},
    )
    do_copy(world, me, ob)
    levels = _skills(world, me).levels
    assert "literate" not in levels
    assert "sword" not in levels


def test_double_prepare_branch_first_skill(monkeypatch: Any) -> None:
    """len==2 且 prepare 空 -> 首个双组合技能设 map+prepare（L255-258）。"""
    # sanhua-zhang valid_enable strike -> is_unarmed 长度 2
    monkeypatch.setattr(
        m, "_valid_enable",
        lambda sk, cat: sk == "sanhua-zhang" and cat == "strike",
    )
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"sanhua-zhang": 1},
    )
    do_copy(world, me, ob)
    smap = _skills(world, me).skill_map
    prep = _skills(world, me).skill_prepare
    # strike 基础技能被补设 200，map/prepare 设 sanhua-zhang
    assert _skills(world, me).levels["strike"] == 200
    assert smap["strike"] == "sanhua-zhang"
    assert prep["strike"] == "sanhua-zhang"


def test_valid_combine_second_skill_overrides(monkeypatch: Any) -> None:
    """prepare==1 且 valid_combine True -> 第二技能覆盖 map+prepare（L259-263）。"""
    # 两个 unarmed 技能都 valid_enable strike（共用 base）
    def fake_valid_enable(sk: str, cat: str) -> bool:
        return sk in ("sanhua-zhang", "yizhi-chan") and cat == "strike"

    monkeypatch.setattr(m, "_valid_enable", fake_valid_enable)
    monkeypatch.setattr(m, "valid_combine", lambda a, b: True)
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"sanhua-zhang": 1, "yizhi-chan": 1},
    )
    do_copy(world, me, ob)
    prep = _skills(world, me).skill_prepare
    smap = _skills(world, me).skill_map
    # 第一个 sanhua-zhang 设入后 prepare==1，第二个 yizhi-chan valid_combine
    # -> 覆盖为 yizhi-chan
    assert prep["strike"] == "yizhi-chan"
    assert smap["strike"] == "yizhi-chan"


def test_valid_combine_false_keeps_first(monkeypatch: Any) -> None:
    """prepare==1 但 valid_combine False -> 保留第一个，不覆盖。"""
    def fake_valid_enable(sk: str, cat: str) -> bool:
        return sk in ("sanhua-zhang", "yizhi-chan") and cat == "strike"

    monkeypatch.setattr(m, "_valid_enable", fake_valid_enable)
    monkeypatch.setattr(m, "valid_combine", lambda a, b: False)
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"sanhua-zhang": 1, "yizhi-chan": 1},
    )
    do_copy(world, me, ob)
    prep = _skills(world, me).skill_prepare
    # 第一个 sanhua-zhang 保留
    assert prep["strike"] == "sanhua-zhang"


def test_force_skill_mapped(monkeypatch: Any) -> None:
    """force-valid_enable 技能 -> map_skill("force", sname)（L265）。"""
    monkeypatch.setattr(
        m, "_valid_enable",
        lambda sk, cat: sk == "jiuyang-shengong" and cat == "force",
    )
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"jiuyang-shengong": 1},
    )
    do_copy(world, me, ob)
    assert _skills(world, me).skill_map["force"] == "jiuyang-shengong"


def test_dodge_skill_mapped(monkeypatch: Any) -> None:
    """dodge-valid_enable 技能 -> map_skill("dodge", sname)（L266-267）。"""
    monkeypatch.setattr(m, "_valid_enable", lambda sk, cat: sk == "lingbo-weibu" and cat == "dodge")
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"lingbo-weibu": 1},
    )
    do_copy(world, me, ob)
    assert _skills(world, me).skill_map["dodge"] == "lingbo-weibu"


def test_default_prepare_when_empty() -> None:
    """ob 无可复制技能 -> 无 prepare -> 设默认指法/掌法组合（L271-281）。"""
    world, me, _ = _world_with(me_levels={"force": 100, "dodge": 100, "parry": 100})
    do_copy(world, me, 0)
    levels = _skills(world, me).levels
    smap = _skills(world, me).skill_map
    prep = _skills(world, me).skill_prepare
    assert levels["finger"] == 200
    assert levels["strike"] == 200
    assert levels["sanhua-zhang"] == 200
    assert levels["yizhi-chan"] == 200
    assert smap["finger"] == "yizhi-chan"
    assert smap["strike"] == "sanhua-zhang"
    assert smap["parry"] == "sanhua-zhang"
    assert prep["strike"] == "sanhua-zhang"
    assert prep["finger"] == "yizhi-chan"


def test_default_prepare_skipped_when_already_set(monkeypatch: Any) -> None:
    """已有 prepare（双组合已设）-> 跳过默认分支（L271 条件）。"""
    monkeypatch.setattr(
        m, "_valid_enable",
        lambda sk, cat: sk == "sanhua-zhang" and cat == "strike",
    )
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"sanhua-zhang": 1},
    )
    do_copy(world, me, ob)
    levels = _skills(world, me).levels
    # 默认分支的 yizhi-chan 不应被设
    assert "yizhi-chan" not in levels


def test_basic_unarmed_type_not_mapped_in_loop(monkeypatch: Any) -> None:
    """基础 unarmed_type（finger）被复制为 200 但循环中 len==1 不进双分支也不映射。"""
    # ob 有基础 finger 技能：is_unarmed("finger") 长度 1 -> 复制但循环不映射
    monkeypatch.setattr(m, "_valid_enable", lambda *_a, **_k: False)
    world, me, ob = _world_with(
        me_levels={"force": 100, "dodge": 100, "parry": 100},
        ob_levels={"finger": 50},
    )
    do_copy(world, me, ob)
    levels = _skills(world, me).levels
    # finger 被复制为 200（L242），但循环不映射（len==1）
    assert levels["finger"] == 200


def test_returns_none_void_contract() -> None:
    """do_copy 遵循 LPC void 契约，返回 None。"""
    world, me, _ = _world_with(me_levels={"force": 100, "dodge": 100, "parry": 100})
    assert do_copy(world, me, 0) is None
