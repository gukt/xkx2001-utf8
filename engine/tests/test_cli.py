"""CLI 主循环：输入行 -> 委托 execute_line -> 打印输出，直到 should_quit。

测试驱动 `run_repl` 这个函数入口本身（用内存文本流替代真实 stdin/stdout），
不 spawn 真实子进程——这是 M1 spec 已确认的测试 seam。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

import io

from mud_engine.cli import run_repl
from mud_engine.scenes import build_world


class TestRunRepl:
    def test_shows_the_starting_rooms_look_output_before_reading_any_input(self) -> None:
        # 与"玩家输入了什么"无关——不管接下来输入什么，循环启动时都先看一次
        # 当前房间，所以不归在任何 When 分支下。
        world, player_id = build_world()
        output_stream = io.StringIO()
        run_repl(world, player_id, input_stream=io.StringIO("quit\n"), output_stream=output_stream)
        assert "起始庭院" in output_stream.getvalue()

    class WhenPlayerTypesQuit:
        def test_prints_the_quit_message(self) -> None:
            world, player_id = build_world()
            output_stream = io.StringIO()
            run_repl(
                world, player_id, input_stream=io.StringIO("quit\n"), output_stream=output_stream
            )
            assert "再见" in output_stream.getvalue()

        def test_sets_should_quit_on_the_world(self) -> None:
            world, player_id = build_world()
            run_repl(
                world, player_id, input_stream=io.StringIO("quit\n"), output_stream=io.StringIO()
            )
            assert world.should_quit is True

    class WhenInputStreamReachesEofWithoutQuit:
        def test_stops_the_loop_without_raising(self) -> None:
            world, player_id = build_world()
            output_stream = io.StringIO()
            run_repl(
                world, player_id, input_stream=io.StringIO("look\n"), output_stream=output_stream
            )
            assert "起始庭院" in output_stream.getvalue()

    class WhenPlayerTypesAnUnknownCommand:
        def test_reports_it_and_keeps_the_loop_going(self) -> None:
            world, player_id = build_world()
            output_stream = io.StringIO()
            run_repl(
                world,
                player_id,
                input_stream=io.StringIO("fly\nquit\n"),
                output_stream=output_stream,
            )
            assert "未知命令" in output_stream.getvalue()
            assert world.should_quit is True
