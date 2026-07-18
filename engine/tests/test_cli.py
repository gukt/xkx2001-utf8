"""CLI 主循环：输入行 -> 委托 execute_line -> 打印输出，直到 should_quit。

测试驱动 `run_repl` 这个函数入口本身（用内存文本流替代真实 stdin/stdout），
不 spawn 真实子进程——这是 M1 spec 已确认的测试 seam。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

import io

from mud_engine.cli import run_repl
from mud_engine.save import has_save, restore_world, save_world
from mud_engine.scenes import build_world
from mud_engine.tick import TickLoop


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


class TestTickLoopIntegration:
    """05 号票：CLI 接入 TickLoop -- 周期存档（验收 #1）与 quit 立即存档（验收 #2）。"""

    def test_quit_triggers_an_immediate_save(self, tmp_path) -> None:
        # 验收 #2：quit 无论当前 tick 是否到周期，退出前都立即存档。
        # interval=100 确保周期不会触发，只有 quit 的 force_save 存档。
        world, player_id = build_world()
        tick_loop = TickLoop(lambda: save_world(world, player_id, tmp_path), interval=100)
        run_repl(
            world,
            player_id,
            tick_loop=tick_loop,
            input_stream=io.StringIO("quit\n"),
            output_stream=io.StringIO(),
        )
        assert has_save(tmp_path) is True
        assert restore_world(tmp_path) is not None

    def test_periodic_save_fires_when_interval_reached(self, tmp_path) -> None:
        # 验收 #1 端到端：达到 tick 间隔后触发一次存档（在 quit 之前已发生）。
        # interval=2 + "look\nlook\nquit\n"：tick 2（第 2 条 look 后）周期存档，
        # 之后 quit -> force_save；save_count>=2 说明周期与 force 各触发一次。
        world, player_id = build_world()
        tick_loop = TickLoop(lambda: save_world(world, player_id, tmp_path), interval=2)
        run_repl(
            world,
            player_id,
            tick_loop=tick_loop,
            input_stream=io.StringIO("look\nlook\nquit\n"),
            output_stream=io.StringIO(),
        )
        assert tick_loop.save_count >= 2
        assert has_save(tmp_path) is True

    def test_no_tick_loop_means_no_save(self, tmp_path) -> None:
        # 不传 tick_loop 保持 01~04 号票旧行为：不触发存档。
        world, player_id = build_world()
        run_repl(
            world,
            player_id,
            input_stream=io.StringIO("quit\n"),
            output_stream=io.StringIO(),
        )
        assert has_save(tmp_path) is False
