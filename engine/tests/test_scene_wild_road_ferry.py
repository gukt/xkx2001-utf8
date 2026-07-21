"""M2-25：野外 / 官道 / 渡口（aggro、地形骑乘、Ferry）。

Seam：``load_mvp_scene`` + ``execute_line`` + ``TickLoop``。
"""

from __future__ import annotations

from mud_engine.components import (
    Currency,
    Engaged,
    Exits,
    Ferry,
    Identity,
    Position,
    Riding,
    SkillLevels,
    Terrain,
    Vitals,
)
from mud_engine.parsing import execute_line
from mud_engine.scenes import load_mvp_scene
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _move_to(world: World, player_id: EntityId, key: str) -> None:
    world.require_component(player_id, Position).room = _room(world, key)


def _npc_named(world: World, name: str, *, exclude: EntityId) -> EntityId:
    for entity in world.entities_with(Identity):
        if entity == exclude:
            continue
        if world.require_component(entity, Identity).name == name:
            return entity
    raise AssertionError(f"{name!r} not found")


class TestWildRoadAndFerry:
    def test_zone_keys_and_yangzhou_shaolin_link(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        for key in (
            "road_yz_east",
            "wild_edge",
            "wild_forest",
            "wild_thicket",
            "ferry_west",
            "ferry_east",
            "road_shaolin",
        ):
            assert key in world.room_ids
        # 扬州东门 -> … -> 少林山门连通链上的关键边
        dongmen = world.require_component(_room(world, "yangzhou_dongmen"), Exits)
        assert dongmen.by_direction["east"].target == _room(world, "road_yz_east")
        shanmen = world.require_component(_room(world, "shaolin_shanmen"), Exits)
        assert shanmen.by_direction["west"].target == _room(world, "road_shaolin")

    def test_high_terrain_blocks_weak_mount(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "road_yz_east")
        edge = _room(world, "wild_edge")
        assert world.require_component(edge, Terrain).cost >= 8
        # 场景内矮种马 ability 低
        execute_line(world, player_id, "ride 矮种马")
        assert world.has_component(player_id, Riding)
        lines = execute_line(world, player_id, "go east")
        assert any("骑不过去" in line for line in lines)
        assert world.require_component(player_id, Position).room == _room(world, "road_yz_east")

    def test_ferry_look_and_cross(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "ferry_west")
        assert world.has_component(_room(world, "ferry_west"), Ferry)
        look = execute_line(world, player_id, "look")
        assert any("渡船" in line for line in look)
        # 初始船在西岸时可直接过
        west_exits = world.require_component(_room(world, "ferry_west"), Exits)
        if "across" not in west_exits.by_direction:
            for _ in range(6):
                TickLoop(lambda: None, world=world).advance()
                west_exits = world.require_component(_room(world, "ferry_west"), Exits)
                if "across" in west_exits.by_direction:
                    break
        lines = execute_line(world, player_id, "go across")
        assert world.require_component(player_id, Position).room == _room(world, "ferry_east")
        assert any("东岸" in line or "渡" in line or "岸" in line for line in lines)

    def test_ferry_absent_denies_crossing(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "ferry_west")
        # 等船离开西岸
        for _ in range(6):
            TickLoop(lambda: None, world=world).advance()
            if "across" not in world.require_component(
                _room(world, "ferry_west"), Exits
            ).by_direction:
                break
        assert "across" not in world.require_component(
            _room(world, "ferry_west"), Exits
        ).by_direction
        look = execute_line(world, player_id, "look")
        assert any("渡船" in line and ("到达" in line or "东岸" in line) for line in look)
        denied = execute_line(world, player_id, "go across")
        assert any("渡船不在" in line for line in denied)
        assert world.require_component(player_id, Position).room == _room(world, "ferry_west")

    def test_script_wild_combat_loot_road_ferry(self) -> None:
        """野外遭遇 -> 战胜获战利品 -> 弱马拒行后步行 -> 渡口过河。"""
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "wild_forest")
        bandit = _npc_named(world, "山贼", exclude=player_id)
        # aggro 应在 tick 后交战
        TickLoop(lambda: None, world=world).advance()
        assert world.has_component(player_id, Engaged) or world.has_component(bandit, Engaged)
        if not world.has_component(player_id, Engaged):
            execute_line(world, player_id, "attack 山贼")

        # 打到气血归零
        world.require_component(player_id, Vitals).qi_current = 200
        world.require_component(player_id, Vitals).qi_max = 200
        money_before = world.require_component(player_id, Currency).amount
        for _ in range(40):
            if not world.has_component(bandit, Vitals):
                break
            if world.require_component(bandit, Vitals).qi_current <= 0:
                break
            TickLoop(lambda: None, world=world).advance()
        # 击杀后应有金钱或经验播报/数值变化
        money_after = world.require_component(player_id, Currency).amount
        skills = world.get_component(player_id, SkillLevels)
        assert money_after > money_before or (
            skills is not None and any(p.exp > 0 for p in skills.levels.values())
        ) or any("打倒" in m or "银" in m for m in world.pending_messages)

        # 弱马拒行后 unride 步行进入高地形
        _move_to(world, player_id, "road_yz_east")
        if world.has_component(player_id, Engaged):
            from mud_engine.combat_system import clear_engagement

            clear_engagement(world, player_id, reason="test")
        execute_line(world, player_id, "ride 矮种马")
        denied = execute_line(world, player_id, "go east")
        assert any("骑不过去" in line for line in denied)
        execute_line(world, player_id, "unride")
        walked = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == _room(world, "wild_edge")
        assert any("野外" in line or "官道" in line or "林" in line for line in walked)

        # 走到渡口并过河
        _move_to(world, player_id, "ferry_west")
        west_exits = world.require_component(_room(world, "ferry_west"), Exits)
        if "across" not in west_exits.by_direction:
            for _ in range(6):
                TickLoop(lambda: None, world=world).advance()
        execute_line(world, player_id, "go across")
        assert world.require_component(player_id, Position).room == _room(world, "ferry_east")
