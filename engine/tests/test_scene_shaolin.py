"""M2-24：少林寺（门槏 + join + learn）。

Seam：``load_mvp_scene`` + ``execute_line``。
"""

from __future__ import annotations

from mud_engine.components import Container, Faction, Identity, Position, SkillLevels
from mud_engine.factions import FACTIONS
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene
from mud_engine.skills import SKILLS
from mud_engine.world import EntityId, World


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _move_to(world: World, player_id: EntityId, key: str) -> None:
    world.require_component(player_id, Position).room = _room(world, key)


def _give_edged_blade(world: World, player_id: EntityId) -> None:
    """把场景里的钢刀模板实例放进玩家背包（门槏刃器否决用）。"""
    from mud_engine.scene_loader import instantiate_item

    blade = instantiate_item(world, "steel_blade")
    bag = world.get_component(player_id, Container)
    if bag is None:
        world.add_component(player_id, Container())
        bag = world.require_component(player_id, Container)
    bag.items.add(blade)


class TestShaolinTemple:
    def test_shaolin_room_keys(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        for key in (
            "shaolin_shanmen",
            "shaolin_guangchang",
            "shaolin_damoyuan",
            "shaolin_cangjingge",
            "shaolin_wuchang",
        ):
            assert key in world.room_ids

    def test_faction_and_skills_wired(self) -> None:
        load_mvp_scene()
        assert "shaolin" in FACTIONS
        assert "luohan_quan" in SKILLS
        assert "hunyuan_yiqi" in SKILLS
        assert FACTIONS["shaolin"].map_skill.get("martial") == "luohan_quan"
        assert FACTIONS["shaolin"].map_skill.get("force") == "hunyuan_yiqi"

    def test_entry_guard_denies_edged_weapon(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "road_shaolin")
        _give_edged_blade(world, player_id)
        lines = execute_line(world, player_id, "go east")
        assert any("刀" in line or "刃" in line or "兵器" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room(world, "road_shaolin")

    def test_entry_guard_denies_wrong_gender(self) -> None:
        world, player_id = load_mvp_scene()
        from mud_engine.components import Gender

        world.require_component(player_id, Gender).value = "female"
        _move_to(world, player_id, "road_shaolin")
        lines = execute_line(world, player_id, "go east")
        assert any("男" in line or "女" in line or "性别" in line for line in lines)

    def test_entry_guard_denies_other_faction(self) -> None:
        world, player_id = load_mvp_scene()
        if not world.has_component(player_id, Faction):
            world.add_component(player_id, Faction(faction_id="beggars"))
        else:
            world.require_component(player_id, Faction).faction_id = "beggars"
        _move_to(world, player_id, "road_shaolin")
        lines = execute_line(world, player_id, "go east")
        assert any("他派" in line or "门派" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room(world, "road_shaolin")

    def test_script_enter_join_learn(self) -> None:
        """不满足门槏拒绝 -> 满足后进入 -> join -> learn。"""
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "road_shaolin")
        _give_edged_blade(world, player_id)
        denied = execute_line(world, player_id, "go east")
        assert any("刀" in line or "刃" in line or "兵器" in line for line in denied)

        # 放下刃器后再进
        execute_line(world, player_id, "drop 钢刀")
        entered = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == _room(world, "shaolin_shanmen")
        assert not any("不得" in line for line in entered)

        execute_line(world, player_id, "go north")  # 广场
        join = execute_line(world, player_id, "join 少林")
        assert any("加入了少林" in line for line in join)
        assert world.require_component(player_id, Faction).faction_id == "shaolin"

        execute_line(world, player_id, "go east")  # 武场
        learn = execute_line(world, player_id, "learn martial")
        assert any("学会了" in line for line in learn)
        skills = world.require_component(player_id, SkillLevels)
        assert "luohan_quan" in skills.levels

    def test_display_npcs_in_story_rooms(self) -> None:
        world, _ = load_mvp_scene()
        names = {world.require_component(e, Identity).name for e in world.entities_with(Identity)}
        for name in ("知客僧", "武僧", "达摩院僧", "藏经阁僧"):
            assert name in names
