"""最小可玩 CLI REPL（S5a）：交互式命令行前端。

加载 xueshan_micro 场景，解析玩家输入 -> 调用命令函数 -> 打印消息。
支持命令：go/get/kill/ask/give/quest/look/inventory/hp/help/quit + 方向简写。

运行：``python -m xkx.cli``（需在 engine/ 目录下，venv 激活）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from xkx.dsl.cpk_loader import load_cpk
from xkx.runtime.commands import (
    Game,
    ask,
    give,
    go,
    hp,
    inventory,
    kill,
    look,
    quest,
    take,
)
from xkx.runtime.world import build_world, spawn_player

SCENES_DIR = Path(__file__).resolve().parent.parent.parent / "scenes"

# 方向简写映射（对齐 LPC go.c default_dirs + 常见缩写）
DIR_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    "u": "up", "d": "down",
    "nu": "northup", "su": "southup", "eu": "eastup", "wu": "westup",
    "nd": "northdown", "sd": "southdown", "ed": "eastdown", "wd": "westdown",
}
ALL_DIRS = set(DIR_ALIASES.keys()) | set(DIR_ALIASES.values())

HELP_TEXT = """\
可用命令：
  go <方向>               向指定方向移动（如 go north），移动后自动查看房间
  <方向>                  直接输入方向即可移动，支持简写：n s e w ne nw se sw
                          u d nu su eu wu nd sd ed wd（如 n = go north）
  look                    查看当前房间（简写 l）
  get <物品>              捡起地上的物品（也支持 take）
  kill <NPC>              攻击 NPC（多回合战斗，至一方倒下）
  ask <NPC> about <话题>  向 NPC 打听/对话
  give <NPC> <物品>       把物品给 NPC
  quest                   查看任务列表
  inventory               查看物品栏（简写 i）
  hp                      查看自己的气/精力/经验（简写 score）
  help                    显示本帮助（简写 h）
  quit                    退出游戏
"""


def load_game(scene: str = "xueshan_micro") -> tuple[Game, int]:
    """加载场景 CPK + 创建玩家，返回 (game, player_id)。

    M3-2 ADR-0031：通过 ThemeRegistry + ``load_cpk`` 加载 CPK。``theme_config`` 从
    ``registry[manifest.theme].theme_config`` 读取（cli.py 不硬编码
    ``ThemeConfig.wuxia()``，题材配置由 ThemeRegistry 注入）。起始房间从
    ``world.theme_config.start_room`` 读取。

    Args:
        scene: CPK 目录名（``scenes/`` 下，默认 ``xueshan_micro`` 武侠旗舰）。
    """
    from xkx.themes import default_registry

    registry = default_registry()
    manifest, ir, rules = load_cpk(SCENES_DIR / scene, registry=registry)
    descriptor = registry.require(manifest.theme)
    world, room_idx, quest_idx = build_world(
        ir, theme_config=descriptor.theme_config
    )
    item_registry = {i["id"]: i["name"] for i in ir.get("items", [])}
    start_room = world.theme_config.start_room  # type: ignore[attr-defined]
    pid = spawn_player(world, "行者", start_room)
    game = Game(
        world,
        room_idx,
        rules,
        quests=quest_idx,
        spawn_room=start_room,
        item_registry=item_registry,
    )
    return game, pid


def _print(messages: list[str]) -> None:
    for m in messages:
        print(m)


def _print_combat(messages: list[str]) -> None:
    """战斗消息逐条打印，每条间短暂停顿（模拟 LPC heart_beat 节奏）。"""
    for m in messages:
        print(m)
        sys.stdout.flush()
        time.sleep(0.25)


def parse_and_run(game: Game, pid: int, line: str) -> bool:
    """解析并执行一行输入，返回 False 表示退出。"""
    parts = line.strip().split()
    if not parts:
        return True
    cmd, args = parts[0], parts[1:]

    # 方向简写：直接输入方向即移动（LPC 习惯）
    if cmd in ALL_DIRS:
        _print(go(game, pid, DIR_ALIASES.get(cmd, cmd)))
        return True
    if cmd in ("quit", "exit"):
        return False
    if cmd in ("help", "h", "?"):
        print(HELP_TEXT)
        return True
    if cmd in ("look", "l"):
        _print(look(game, pid))
        return True
    if cmd in ("inventory", "i"):
        _print(inventory(game, pid))
        return True
    if cmd in ("hp", "score"):
        _print(hp(game, pid))
        return True
    if cmd == "go":
        if not args:
            print("要去哪？如：go north 或直接 n")
            return True
        _print(go(game, pid, args[0]))
        return True
    if cmd in ("get", "take"):
        if not args:
            print("要捡起什么？如：get suyou_guan")
            return True
        _print(take(game, pid, args[0]))
        return True
    if cmd == "kill":
        if not args:
            print("要攻击谁？如：kill 葛伦布")
            return True
        _print_combat(kill(game, pid, " ".join(args)))
        return True
    if cmd == "ask":
        if "about" in args:
            idx = args.index("about")
            npc = " ".join(args[:idx])
            topic = " ".join(args[idx + 1 :])
        elif len(args) >= 2:
            npc, topic = args[0], " ".join(args[1:])
        else:
            print("如：ask 葛伦布 about 还愿")
            return True
        _print(ask(game, pid, npc, topic))
        return True
    if cmd == "give":
        if len(args) < 2:
            print("如：give 葛伦布 suyou_guan")
            return True
        npc = " ".join(args[:-1])
        item = args[-1]
        _print(give(game, pid, npc, item))
        return True
    if cmd == "quest":
        _print(quest(game, pid, " ".join(args)))
        return True

    print(f"未知命令「{cmd}」，输入 help 查看帮助。")
    return True


def main() -> None:
    game, pid = load_game()
    print("=== 侠客行 MUD 垂直切片试玩 ===")
    print("输入 help 查看命令，quit 退出。")
    print()
    _print(look(game, pid))
    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not parse_and_run(game, pid, line):
            print("再见！")
            break


if __name__ == "__main__":
    main()
