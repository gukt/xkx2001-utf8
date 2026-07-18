"""命令调度测试：直接驱动 execute_line 这个 CLI 函数入口（已确认的测试 seam），
断言返回的消息内容与之后可查询的世界状态，不断言内部实现细节。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

from mud_engine.commands import execute_line
from mud_engine.components import Identity, Position
from mud_engine.scenes import build_world


class TestLook:
    def test_shows_room_short_and_long_description(self) -> None:
        world, player = build_world()
        messages = execute_line(world, player, "look")
        assert "起始庭院" in messages[0]
        assert any("骨架" in m for m in messages)

    def test_lists_available_exits(self) -> None:
        world, player = build_world()
        messages = execute_line(world, player, "look")
        assert any("north" in m for m in messages)

    def test_verb_matching_is_case_insensitive(self) -> None:
        world, player = build_world()
        messages = execute_line(world, player, "LOOK")
        assert "起始庭院" in messages[0]


class TestGo:
    class WhenDirectionHasExit:
        def test_moves_player_to_the_target_room(self) -> None:
            world, player = build_world()
            start_room = world.require_component(player, Position).room
            execute_line(world, player, "go north")
            new_room = world.require_component(player, Position).room
            assert new_room != start_room
            assert world.has_component(new_room, Identity)

        def test_output_includes_the_new_rooms_description(self) -> None:
            world, player = build_world()
            messages = execute_line(world, player, "go north")
            assert any("长廊" in m for m in messages)

    class WhenDirectionHasNoExit:
        def test_player_does_not_move(self) -> None:
            world, player = build_world()
            before = world.require_component(player, Position).room
            execute_line(world, player, "go east")
            after = world.require_component(player, Position).room
            assert before == after

        def test_warning_message_mentions_the_attempted_direction(self) -> None:
            world, player = build_world()
            messages = execute_line(world, player, "go east")
            assert any("east" in m for m in messages)

    class WhenDirectionArgumentIsMissing:
        def test_returns_a_usage_hint(self) -> None:
            world, player = build_world()
            messages = execute_line(world, player, "go")
            assert messages
            assert "go" in messages[0].lower() or "方向" in messages[0]


class TestHelp:
    def test_lists_all_registered_commands(self) -> None:
        world, player = build_world()
        messages = execute_line(world, player, "help")
        combined = " ".join(messages)
        for verb in ("go", "look", "help", "quit"):
            assert verb in combined

    def test_h_is_an_alias_for_help(self) -> None:
        world, player = build_world()
        assert execute_line(world, player, "h") == execute_line(world, player, "help")

    def test_listing_includes_the_h_alias_alongside_help(self) -> None:
        # 当前实现直接把 `h` 注册成第二个动词（见 commands.py 里的说明），所以
        # 它会和 `help` 一起出现在命令列表里；这是本票范围内接受的取舍，本条
        # 测试把这个行为锁定下来，防止以后改动时悄悄变成未定义行为。02 号票
        # 引入声明式别名机制后，这条测试的断言可能需要一起调整。
        world, player = build_world()
        combined = " ".join(execute_line(world, player, "help"))
        assert "h" in combined.split("：")[1].split("、")


class TestQuit:
    def test_sets_the_should_quit_flag_on_the_world(self) -> None:
        world, player = build_world()
        assert world.should_quit is False
        execute_line(world, player, "quit")
        assert world.should_quit is True


class TestExecuteLineDispatch:
    class WhenVerbIsNotRegistered:
        def test_returns_an_unknown_command_hint(self) -> None:
            world, player = build_world()
            messages = execute_line(world, player, "fly")
            assert any("未知命令" in m for m in messages)

        def test_hint_points_the_player_to_help(self) -> None:
            world, player = build_world()
            messages = execute_line(world, player, "fly")
            assert any("help" in m for m in messages)

        def test_does_not_raise(self) -> None:
            world, player = build_world()
            execute_line(world, player, "fly")  # 不应抛异常

    class WhenLineIsBlank:
        def test_produces_no_messages(self) -> None:
            world, player = build_world()
            assert execute_line(world, player, "   ") == []
