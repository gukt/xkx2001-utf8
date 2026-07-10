"""最小可玩 CLI REPL（S5a）：交互式命令行前端。

加载 xueshan_micro 场景，解析玩家输入 -> 调用命令函数 -> 打印消息。
支持命令：go/kill/ask/give/quest/look/take/inventory/help/quit。

运行：``python -m xkx.cli``（需在 engine/ 目录下，venv 激活）。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import (
    Game,
    ask,
    give,
    go,
    inventory,
    kill,
    look,
    quest,
    take,
)
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent.parent / "scenes" / "xueshan_micro"
START_ROOM = "xueshan/shanmen"

HELP_TEXT = """\
可用命令：
  go <方向>               向指定方向移动（如 go north）
  look                    查看当前房间（简写 l）
  take <物品>             拾取地上的物品
  kill <NPC>              攻击 NPC（多回合战斗，至一方倒下）
  ask <NPC> about <话题>  向 NPC 打听/对话
  give <NPC> <物品>       把物品给 NPC
  quest                   查看任务列表
  inventory               查看物品栏（简写 i）
  help                    显示本帮助（简写 h）
  quit                    退出游戏
"""


def load_game() -> tuple[Game, int]:
    """加载 xueshan_micro 场景 + 创建玩家，返回 (game, player_id)。"""
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs, quests)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "行者", START_ROOM)
    game = Game(world, room_idx, rules, quests=quest_idx, spawn_room=START_ROOM)
    return game, pid


def _print(messages: list[str]) -> None:
    for m in messages:
        print(m)


def parse_and_run(game: Game, pid: int, line: str) -> bool:
    """解析并执行一行输入，返回 False 表示退出。"""
    parts = line.strip().split()
    if not parts:
        return True
    cmd, args = parts[0], parts[1:]

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
    if cmd == "go":
        if not args:
            print("要去哪？如：go north")
            return True
        _print(go(game, pid, args[0]))
        return True
    if cmd == "take":
        if not args:
            print("要拿什么？如：take suyou_guan")
            return True
        _print(take(game, pid, args[0]))
        return True
    if cmd == "kill":
        if not args:
            print("要攻击谁？如：kill 葛伦布")
            return True
        _print(kill(game, pid, " ".join(args)))
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
