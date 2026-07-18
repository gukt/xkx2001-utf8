"""CLI 前端：真实命令行终端进程的最小交互循环。

职责仅限于"输入行 -> 委托 execute_line 解析与调度 -> 打印输出"，不写游戏
逻辑（游戏逻辑归 mud_engine.commands 里的处理函数）。默认对接真实的
sys.stdin/sys.stdout；测试用内存文本流替换，不需要真实子进程。
"""

from __future__ import annotations

import sys
from typing import TextIO

from mud_engine.parsing import execute_line
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World

PROMPT = "> "


def run_repl(
    world: World,
    player_id: EntityId,
    *,
    tick_loop: TickLoop | None = None,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> None:
    """读一行输入 -> 解析并调度 -> 打印返回消息 -> 继续读下一行，直到退出。

    退出条件二选一：命令处理函数把 ``world.should_quit`` 置为真（如 ``quit``），
    或输入流到达 EOF（如管道关闭、Ctrl+D）--EOF 不算异常退出，只是安静结束循环。

    05 号票：传入 ``tick_loop`` 后，每条命令推进一个 tick（到间隔触发周期存档，
    验收 #1），循环退出前再 force_save 一次（``quit`` 无论是否到周期都立即存档，
    验收 #2）。不传则不触发存档，保持 01~04 号票测试的旧行为。
    """
    _print_messages(execute_line(world, player_id, "look"), output_stream)

    while not world.should_quit:
        output_stream.write(PROMPT)
        line = input_stream.readline()
        if line == "":  # EOF：真实终端里对应 Ctrl+D / 输入流关闭
            break
        messages = execute_line(world, player_id, line)
        _print_messages(messages, output_stream)
        if tick_loop is not None:
            tick_loop.advance()

    if tick_loop is not None:
        tick_loop.force_save()


def _print_messages(messages: list[str], output_stream: TextIO) -> None:
    """把消息列表逐行写到输出流；空列表什么都不打印。"""
    for message in messages:
        output_stream.write(message + "\n")
