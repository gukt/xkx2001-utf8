"""命令调度测试：直接驱动 execute_line 这个 CLI 函数入口（已确认的测试 seam），
断言返回的消息内容与之后可查询的世界状态，不断言内部实现细节。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

import pytest

from openmud.components import Container, Identity, Position
from openmud.parsing import execute_line
from openmud.scenes import build_world
from openmud.world import EntityId, World


def _player_room_name(world: World, player_id: EntityId) -> str:
    """玩家当前所在房间的展示名，跨 world 比较时用名字而非裸 id。"""
    room = world.require_component(player_id, Position).room
    return world.require_component(room, Identity).name


class TestLook:
    def test_shows_room_short_and_long_description(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "look")
        assert "起始庭院" in messages[0]
        assert any("骨架" in m for m in messages)

    def test_lists_available_exits(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "look")
        assert any("north" in m for m in messages)

    def test_verb_matching_is_case_insensitive(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "LOOK")
        assert "起始庭院" in messages[0]


class TestGo:
    class WhenDirectionHasExit:
        def test_moves_player_to_the_target_room(self) -> None:
            world, player_id = build_world()
            start_room = world.require_component(player_id, Position).room
            execute_line(world, player_id, "go north")
            new_room = world.require_component(player_id, Position).room
            assert new_room != start_room
            assert world.has_component(new_room, Identity)

        def test_output_includes_the_new_rooms_description(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "go north")
            assert any("长廊" in m for m in messages)

    class WhenDirectionHasNoExit:
        def test_player_does_not_move(self) -> None:
            world, player_id = build_world()
            before = world.require_component(player_id, Position).room
            execute_line(world, player_id, "go east")
            after = world.require_component(player_id, Position).room
            assert before == after

        def test_warning_message_mentions_the_attempted_direction(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "go east")
            assert any("east" in m for m in messages)

    class WhenDirectionArgumentIsMissing:
        def test_returns_a_usage_hint(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "go")
            assert messages
            assert "go" in messages[0].lower() or "方向" in messages[0]

    class WhenDirectionIsGivenByAlias:
        def test_moves_player_through_the_aliased_exit(self) -> None:
            # corridor 房间 aliases 含「北道」，经目标房回退可 go 北道。
            world, player_id = build_world()
            start = world.require_component(player_id, Position).room
            messages = execute_line(world, player_id, "go 北道")
            new_room = world.require_component(player_id, Position).room
            assert new_room != start
            assert any("长廊" in m for m in messages)

        def test_alias_reaches_the_same_room_as_canonical_name(self) -> None:
            world_a, player_a = build_world()
            execute_line(world_a, player_a, "go 北道")
            world_b, player_b = build_world()
            execute_line(world_b, player_b, "go north")
            assert _player_room_name(world_a, player_a) == _player_room_name(world_b, player_b)


class TestDirectionShortcuts:
    def test_n_alone_moves_player_north(self) -> None:
        world, player_id = build_world()
        start = world.require_component(player_id, Position).room
        messages = execute_line(world, player_id, "n")
        assert world.require_component(player_id, Position).room != start
        assert any("长廊" in m for m in messages)

    def test_n_reaches_the_same_room_as_go_north(self) -> None:
        for cmd in ("n", "go north"):
            world, player_id = build_world()
            execute_line(world, player_id, cmd)
            assert _player_room_name(world, player_id) == "长廊"


class TestTake:
    class WhenTheItemIsOnTheFloor:
        def test_moves_the_item_to_the_players_inventory(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            inventory = world.require_component(player_id, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in inventory.items)

        def test_removes_the_item_from_the_rooms_floor(self) -> None:
            world, player_id = build_world()
            room = world.require_component(player_id, Position).room
            execute_line(world, player_id, "get 石头")
            floor = world.require_component(room, Container)
            assert not any(world.require_component(i, Identity).name == "石头" for i in floor.items)

        def test_look_reflects_the_taken_item_is_gone(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            combined = " ".join(execute_line(world, player_id, "look"))
            assert "石头" not in combined

        def test_inventory_lists_the_taken_item(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            combined = " ".join(execute_line(world, player_id, "inventory"))
            assert "石头" in combined

        def test_reports_picking_it_up(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "get 石头")
            assert any("拿" in m and "石头" in m for m in messages)

    class WhenMatchingByAlias:
        def test_alias_reaches_the_same_item_as_canonical_name(self) -> None:
            # 石头的别名是"石"（见 scenes.py）；别名匹配走 02 号票的 match_target。
            world, player_id = build_world()
            execute_line(world, player_id, "get 石")
            inventory = world.require_component(player_id, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in inventory.items)

    class WhenTheItemIsNotHere:
        def test_returns_a_hint_and_changes_nothing(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "get 剑")
            assert any("这里没有" in m for m in messages)
            assert not world.require_component(player_id, Container).items

        def test_does_not_raise(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 剑")  # 不应抛异常

    class WhenNoItemGiven:
        def test_returns_a_usage_hint(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "get")
            assert messages
            assert "get" in messages[0] or "什么" in messages[0]

    class WhenUsingTakeAlias:
        def test_take_alias_picks_up_like_get(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "take 石头")
            assert any("拿" in m and "石头" in m for m in messages)
            inventory = world.require_component(player_id, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in inventory.items)


class TestDrop:
    class WhenThePlayerHasTheItem:
        def test_moves_it_to_the_rooms_floor(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            execute_line(world, player_id, "drop 石头")
            room = world.require_component(player_id, Position).room
            floor = world.require_component(room, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in floor.items)
            assert not world.require_component(player_id, Container).items

        def test_look_reflects_the_dropped_item(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            execute_line(world, player_id, "drop 石头")
            combined = " ".join(execute_line(world, player_id, "look"))
            assert "石头" in combined

        def test_reports_dropping_it(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            messages = execute_line(world, player_id, "drop 石头")
            assert any("放下" in m for m in messages)

        def test_inventory_reflects_the_drop(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            execute_line(world, player_id, "drop 石头")
            combined = " ".join(execute_line(world, player_id, "inventory"))
            assert "没" in combined  # 物品栏空 -> "你什么都没带。"

    class WhenThePlayerDoesNotHaveIt:
        def test_returns_a_hint_and_changes_nothing(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "drop 石头")
            assert any("你没有" in m for m in messages)
            room = world.require_component(player_id, Position).room
            floor = world.require_component(room, Container)
            # start_yard 地面仍有石头（drop 失败不改地面）
            assert any(world.require_component(i, Identity).name == "石头" for i in floor.items)


class TestInventory:
    def test_lists_nothing_when_empty(self) -> None:
        world, player_id = build_world()
        combined = " ".join(execute_line(world, player_id, "inventory"))
        assert "没" in combined  # "你什么都没带。"

    def test_lists_items_after_taking(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "get 石头")
        combined = " ".join(execute_line(world, player_id, "inventory"))
        assert "石头" in combined

    def test_i_is_an_alias_for_inventory(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "get 石头")
        assert execute_line(world, player_id, "i") == execute_line(world, player_id, "inventory")


class TestHelp:
    def test_lists_all_registered_commands(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "help")
        combined = " ".join(messages)
        for verb in ("go", "look", "help", "quit"):
            assert verb in combined

    def test_h_is_an_alias_for_help(self) -> None:
        world, player_id = build_world()
        assert execute_line(world, player_id, "h") == execute_line(world, player_id, "help")

    def test_help_entry_is_annotated_with_its_h_alias(self) -> None:
        # 02 号票起别名声式声明：h 不再作为第二个独立动词出现，而是在 help
        # 条目旁标注。锁定这个展示格式（01 号票的旧断言已随声明式别名调整）。
        world, player_id = build_world()
        combined = " ".join(execute_line(world, player_id, "help"))
        assert "help（h）" in combined

    def test_help_points_out_direction_shortcuts(self) -> None:
        world, player_id = build_world()
        combined = " ".join(execute_line(world, player_id, "help"))
        assert "n/s/e/w" in combined


class TestQuit:
    def test_sets_the_should_quit_flag_on_the_world(self) -> None:
        world, player_id = build_world()
        assert world.should_quit is False
        execute_line(world, player_id, "quit")
        assert world.should_quit is True


class TestExecuteLineDispatch:
    class WhenVerbIsNotRegistered:
        def test_returns_an_unknown_command_hint(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "fly")
            assert any("未知命令" in m for m in messages)

        def test_hint_points_the_player_to_help(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "fly")
            assert any("help" in m for m in messages)

        def test_does_not_raise(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "fly")  # 不应抛异常

    class WhenLineIsBlank:
        def test_produces_no_messages(self) -> None:
            world, player_id = build_world()
            assert execute_line(world, player_id, "   ") == []


class TestCommandAliasConflicts:
    """命令别名冲突在注册期 fail-fast（spec 用户故事 24、02 号票 acceptance
    第 7 条：别名与规范名/别名冲突"不是未定义行为"）。注册的临时命令在
    finally 里清理，避免污染全局注册表影响其他测试。"""

    def test_alias_colliding_with_a_canonical_verb_raises(self) -> None:
        from openmud import commands

        with pytest.raises(ValueError):

            @commands.register("__conflict_canonical__", aliases=("look",))
            def _a(world, player_id, intent): ...

        commands._REGISTRY.pop("__conflict_canonical__", None)

    def test_alias_already_claimed_by_another_command_raises(self) -> None:
        from openmud import commands

        @commands.register("__temp_owner__", aliases=("__dup__",))
        def _a(world, player_id, intent): ...

        try:
            with pytest.raises(ValueError):

                @commands.register("__temp_claimer__", aliases=("__dup__",))
                def _b(world, player_id, intent): ...
        finally:
            commands._REGISTRY.pop("__temp_owner__", None)
            commands._REGISTRY.pop("__temp_claimer__", None)
            commands._ALIASES.pop("__dup__", None)
