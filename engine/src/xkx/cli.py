"""最小可玩 CLI REPL（M3-1 子任务 5 整合）：交互式命令行前端。

加载 xueshan_micro CPK，接入 Engine tick 推进（练功 busy + 死亡轮回自动完成），
解析玩家输入 -> 调用命令函数 -> 打印消息 + 推进 tick。

支持命令：go/get/take/kill/fight/ask/give/quest/look/inventory/hp/help/quit +
方向简写 + 拜师 bai/kneel/betrayer + 练功 learn/practice/dazuo/tuna/enable。

运行：``python -m xkx.cli``（需在 engine/ 目录下）。
"""

from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from xkx.dsl.cpk_loader import load_cpk
from xkx.runtime.commands import (
    Game,
    ask,
    bai,
    betrayer,
    dazuo,
    drink,
    drop,
    du,
    enable,
    fight,
    flee,
    give,
    go,
    hp,
    inventory,
    kill,
    kneel,
    learn,
    look,
    practice,
    quest,
    take,
    tuna,
    unwield,
    wield,
)
from xkx.runtime.world import build_world, spawn_player

if TYPE_CHECKING:
    from xkx.runtime.theme_registry import ThemeRegistry

SCENES_DIR = Path(__file__).resolve().parent.parent.parent / "scenes"

# 自动推进 tick 上限（阴间 death_stage 首延 30 + 5 段每段 5 = 55，余量 200）
_AUTO_ADVANCE_MAX_TICKS = 200
# 需自动推进到完成的 EffectComp（练功 busy + 阴间轮回）
_AUTO_ADVANCE_EFFECTS = frozenset({"exercise", "respirate", "death_stage"})

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
  look [target]          查看房间或 NPC 详情（简写 l；邪派 NPC 会瞪眼）
  get <物品>              捡起地上的物品（也支持 take）
  drink <物品>            喝/服用（酥油茶恢复精，雪莲丹恢复气）
  kill <NPC>              攻击 NPC（多回合战斗，至一方倒下）
  fight <NPC>             切磋武艺（点到为止，不致死）
  ask <NPC> about <话题>  向 NPC 打听/对话
  give <NPC> <物品>       把物品给 NPC
  quest                   查看任务列表
  inventory               查看物品栏（简写 i）
  hp                      查看自己的气/精力/经验（简写 score）
  bai <师傅>              拜师（须满足入门条件）
  kneel                   跪下受戒剃度（须先获师傅许可）
  learn <师傅> <技能> [次数]  向师傅请教技能（消耗潜能+精）
  practice <技能种类> [次数] 练习已启用的特殊技能（种类如 force/sword/unarmed）
  dazuo <气量>            打坐练内力（须先 enable 内功）
  tuna <精量>             吐纳练精力
  enable [种类] [技能]    启用特殊技能映射（种类如 force；无参查看当前）
  du <经书>               研读经书提升武功（须先 kneel 剃度入佛门）
  betrayer                叛出师门
  help                    显示本帮助（简写 h）
  quit                    退出游戏
"""


def _load_theme_data_items(theme: str, registry: ThemeRegistry) -> list[dict]:
    """加载题材数据层 CPK 的物品（ADR-0062 接线）。

    glob ``scenes/<theme>_*/`` 目录，预读 manifest：``entry_points`` 为空的是数据层
    CPK（纯物品台账，无 rooms/入口），``load_cpk`` 合并其 ``ir["items"]``。有
    ``entry_points`` 的场景 CPK（如 ``wuxia_micro``）跳过。非武侠题材（``default``）
    无匹配目录返回空。

    ADR-0062 决策 2 落地：武器数据按公共/门派拆分为 17 个数据层 CPK
    （``wuxia_common`` + 16 门派），本函数按题材前缀发现并合并进 ``item_registry``，
    供 wield 命令批消费。
    """
    import yaml

    from xkx.dsl.cpk import CpkManifest

    items: list[dict] = []
    for cpk_dir in sorted(SCENES_DIR.glob(f"{theme}_*/")):
        mpath = cpk_dir / "manifest.yaml"
        if not mpath.exists():
            continue
        manifest = CpkManifest.model_validate(
            yaml.safe_load(mpath.read_text(encoding="utf-8"))
        )
        if manifest.entry_points:  # 场景 CPK（有入口房间）跳过
            continue
        _, ir, _, _ = load_cpk(cpk_dir, registry=registry)
        items += ir.get("items", [])
    return items


def load_game(scene: str = "xueshan_micro") -> tuple[Game, int]:
    """加载场景 CPK + 创建玩家 + 接入 Engine，返回 (game, player_id)。

    M3-2 ADR-0031：通过 ThemeRegistry + ``load_cpk`` 加载 CPK。``theme_config`` 从
    ``registry[manifest.theme].theme_config`` 读取。起始房间从
    ``world.theme_config.start_room`` 读取。

    M3-1 子任务 5：接入 Engine（HealSystem + ConditionSystem + GovernanceSystem），
    挂 ``game.engine``。``parse_and_run`` 每命令后推进 tick（练功 busy + 死亡轮回
    自动完成），玩家无需手动 wait。

    Args:
        scene: CPK 目录名（``scenes/`` 下，默认武侠旗舰微场景）。
    """
    from xkx.runtime.conditions import ConditionSystem
    from xkx.runtime.doors import DoorSystem
    from xkx.runtime.engine import CombatBridge, Engine
    from xkx.runtime.governance import GovernanceSystem
    from xkx.runtime.heal import HealSystem
    from xkx.runtime.skill import register_skill_defs
    from xkx.themes import default_registry

    registry = default_registry()
    manifest, ir, rules, skills = load_cpk(SCENES_DIR / scene, registry=registry)
    descriptor = registry.require(manifest.theme)
    world, room_idx, quest_idx = build_world(
        ir, theme_config=descriptor.theme_config
    )
    register_skill_defs(skills)
    # C4 ADR-0043：item_registry 存完整 item dict（name/aliases/consumable）
    # ADR-0062 接线：合并题材数据层 CPK 物品（wuxia_common + 16 门派武器 = 149）
    data_items = _load_theme_data_items(manifest.theme, registry)
    item_registry = {i["id"]: i for i in ir.get("items", []) + data_items}
    start_room = world.theme_config.start_room  # type: ignore[attr-defined]
    pid = spawn_player(world, "行者", start_room)
    # demo 试玩便利：给玩家初始潜能 + 基础 force，便于测通
    # learn -> enable -> dazuo -> practice 链路。LPC 新角色 potential=0 靠战斗积累、
    # force 基础靠练功获得；demo 直接给以方便试玩（不影响 spawn_player 规范语义）。
    from xkx.runtime.components import Progression, Skills

    prog = world.get(pid, Progression)
    if prog is not None:
        prog.potential = 100
        # B3：combat_exp 便利值（同 potential 便利逻辑），让 longxiang-banruo 能学到
        # ~36（拜萨木门槛 30）；spawn_player 默认 500 会卡在 ~17（my_skill³/10>500）。
        prog.combat_exp = 5000
    skills = world.get(pid, Skills)
    if skills is not None:
        skills.levels["force"] = 30
    game = Game(
        world,
        room_idx,
        rules,
        quests=quest_idx,
        spawn_room=start_room,
        item_registry=item_registry,
    )
    # M3-1 子任务 5：接入 Engine tick 推进（练功 busy + 阴间还阳 + 自然恢复）
    # ADR-0039：CombatBridge 驱动战斗 tick（kill/fight 建立 CombatState 后由其推进）
    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    engine.add_system(DoorSystem())  # C5 ADR-0042 门定时关门
    # B-2 ADR-0039 决策 4 + ADR-0045：注册 auto_fight handler（NPC 主动攻击接入运行时）
    from xkx.runtime.auto_fight import (
        FightType,
        aggressive_start_fight_handler,
        hatred_start_fight_handler,
        register_start_fight_handler,
        vendetta_start_fight_handler,
    )

    register_start_fight_handler(FightType.AGGRESSIVE, aggressive_start_fight_handler)
    register_start_fight_handler(FightType.HATRED, hatred_start_fight_handler)
    register_start_fight_handler(FightType.VENDETTA, vendetta_start_fight_handler)
    game.engine = engine  # type: ignore[attr-defined]
    return game, pid


def _print(messages: list[str]) -> None:
    for m in messages:
        print(m)


def _print_paced(messages: list[str]) -> None:
    """逐条打印消息，每条间短暂停顿（模拟 LPC heart_beat 1 秒节奏的可读化）。

    用于战斗回合消息 + 阴间 death_stage 剧情消息：这两类在 CLI 同步模式下会被
    一次性收集（combat 由 ``_run_combat`` 压缩到同步推进，death_stage 由
    ``_auto_advance`` 连续 tick 推进），逐条停顿让玩家看清时序，而非一古脑刷屏。
    空列表不打印也不停顿（``_auto_advance`` 多数 tick 无消息）。
    """
    for m in messages:
        print(m)
        sys.stdout.flush()
        time.sleep(0.25)


def _drain_pending(game: Game) -> list[str]:
    """读取并清空 ``world.pending_messages``（System/_tell 产生的消息）。"""
    world = game.world
    msgs = list(getattr(world, "pending_messages", []))
    if msgs:
        world.pending_messages = []  # type: ignore[attr-defined]
    return msgs


def _advance_heartbeat(game: Game) -> None:
    """命令后推进 1 tick（heartbeat：自然恢复 + condition 衰减）+ 打印消息。"""
    engine = getattr(game, "engine", None)
    if engine is None:
        return
    engine.tick()
    _print(_drain_pending(game))


def _auto_advance(game: Game, pid: int) -> None:
    """命令后自动推进 tick：练功 busy + 阴间还阳。

    M3-1 子任务 5：检测玩家身上的 exercise/respirate/death_stage EffectComp，循环
    tick 直到移除（练功完成 / 还阳）。ADR-0039：战斗由 kill/fight 命令内的
    ``_run_combat`` 推进完（CombatBridge 驱动），本函数只处理战斗后的死亡轮回
    （玩家死 die() 启动 death_stage -> 自动推进到还阳）+ 练功 busy。
    """
    from xkx.runtime.components import EffectComp

    engine = getattr(game, "engine", None)
    if engine is None:
        return
    world = game.world
    for _ in range(_AUTO_ADVANCE_MAX_TICKS):
        active = False
        for effect_eid in world.entities_with(EffectComp):
            eff = world.get(effect_eid, EffectComp)
            if (
                eff is not None
                and eff.target_id == pid
                and eff.effect_id in _AUTO_ADVANCE_EFFECTS
            ):
                active = True
                break
        if not active:
            break
        engine.tick()
        _print_paced(_drain_pending(game))


def parse_and_run(game: Game, pid: int, line: str) -> bool:
    """解析并执行一行输入，返回 False 表示退出。

    引号感知分词（C1）：``kill "小 喇嘛"`` -> ``["kill", "小 喇嘛"]``，支持含空格的
    NPC/物品名。无引号时等价空格分词；引号不匹配时 fallback 到简单 split。
    """
    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.strip().split()
    if not parts:
        return True
    cmd, args = parts[0], parts[1:]

    # 方向简写：直接输入方向即移动（LPC 习惯）
    if cmd in ALL_DIRS:
        _print(go(game, pid, DIR_ALIASES.get(cmd, cmd)))
        _advance_heartbeat(game)
        return True
    if cmd in ("quit", "exit"):
        return False
    if cmd in ("help", "h", "?"):
        print(HELP_TEXT)
        return True
    if cmd in ("look", "l"):
        _print(look(game, pid, " ".join(args)))
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
        _advance_heartbeat(game)
        return True
    if cmd in ("get", "take"):
        if not args:
            print("要捡起什么？如：get suyou_guan")
            return True
        _print(take(game, pid, " ".join(args)))
        return True
    if cmd == "drop":
        if not args:
            print("要丢弃什么？如：drop suyou_guan")
            return True
        _print(drop(game, pid, " ".join(args)))
        _advance_heartbeat(game)
        return True
    if cmd in ("drink", "he"):
        if not args:
            print("要喝什么？如：drink 酥油茶")
            return True
        _print(drink(game, pid, " ".join(args)))
        _advance_heartbeat(game)
        return True
    if cmd == "wield":
        if not args:
            print("要装备什么武器？如：wield 长剑 或 wield all")
            return True
        _print(wield(game, pid, " ".join(args)))
        return True
    if cmd == "unwield":
        if not args:
            print("要脱掉什么武器？如：unwield 长剑")
            return True
        _print(unwield(game, pid, " ".join(args)))
        return True
    if cmd == "kill":
        if not args:
            print("要攻击谁？如：kill 葛伦布")
            return True
        _print_paced(kill(game, pid, " ".join(args)))
        # ADR-0039：战斗 + 死亡轮回由 _auto_advance 推进（CombatBridge tick 驱动）
        _auto_advance(game, pid)
        return True
    if cmd == "fight":
        if not args:
            print("要和谁切磋？如：fight 达尔巴")
            return True
        _print_paced(fight(game, pid, " ".join(args)))
        _auto_advance(game, pid)
        return True
    if cmd == "flee":
        _print(flee(game, pid))
        _advance_heartbeat(game)
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
        _advance_heartbeat(game)
        return True
    if cmd == "give":
        if len(args) < 2:
            print("如：give 葛伦布 suyou_guan")
            return True
        npc = " ".join(args[:-1])
        item = args[-1]
        _print(give(game, pid, npc, item))
        _advance_heartbeat(game)
        return True
    if cmd == "quest":
        _print(quest(game, pid, " ".join(args)))
        return True
    if cmd == "bai":
        if not args:
            print("要拜谁为师？如：bai 昌齐大喇嘛")
            return True
        _print(bai(game, pid, " ".join(args)))
        _advance_heartbeat(game)
        return True
    if cmd == "kneel":
        _print(kneel(game, pid))
        _advance_heartbeat(game)
        return True
    if cmd == "betrayer":
        _print(betrayer(game, pid))
        _advance_heartbeat(game)
        return True
    if cmd in ("learn", "xue"):
        if len(args) < 2:
            print("指令格式：learn <师傅> <技能> [次数]，如：learn 昌齐大喇嘛 longxiang-banruo")
            return True
        times = 1
        if len(args) >= 3:
            try:
                times = int(args[2])
            except ValueError:
                print("请教次数必须是数字。")
                return True
        _print(learn(game, pid, args[0], args[1], times))
        _advance_heartbeat(game)
        return True
    if cmd in ("practice", "lian"):
        if not args:
            print("你要练什么技能种类？如：practice force")
            return True
        times = 1
        if len(args) >= 2:
            try:
                times = int(args[1])
            except ValueError:
                print("练习次数必须是数字。")
                return True
        _print(practice(game, pid, args[0], times))
        _advance_heartbeat(game)
        return True
    if cmd in ("dazuo", "exercise"):
        if not args:
            print("你要花多少气练功？（如：dazuo 100）")
            return True
        try:
            cost = int(args[0])
        except ValueError:
            print("你要花多少气练功？")
            return True
        _print(dazuo(game, pid, cost))
        # exercise EffectComp 启动 -> 自动推进到完成（max_neili 提升/瓶颈）
        _auto_advance(game, pid)
        return True
    if cmd in ("tuna", "respirate"):
        if not args:
            print("你要花多少精练功？（如：tuna 100）")
            return True
        try:
            cost = int(args[0])
        except ValueError:
            print("你要花多少精练功？")
            return True
        _print(tuna(game, pid, cost))
        # respirate EffectComp 启动 -> 自动推进到完成（max_jingli 提升/瓶颈）
        _auto_advance(game, pid)
        return True
    if cmd in ("enable", "jifa"):
        skill_type = args[0] if args else ""
        map_to = args[1] if len(args) >= 2 else ""
        _print(enable(game, pid, skill_type, map_to))
        return True
    if cmd in ("du", "study"):
        if not args:
            print("你要研读什么？如：du 龙象般若经")
            return True
        _print(du(game, pid, " ".join(args)))
        _advance_heartbeat(game)
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
