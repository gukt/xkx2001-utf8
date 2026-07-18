"""命令调度：以"动词字符串 -> 处理函数"注册表组织。

调度流程保留"识别动词 -> 查找命令 -> 执行"最小主干；权限校验阶段留作未来
占位，M1 单机单玩家不需要它，因此本票不落地一个空阶段，避免过度设计。

处理函数只响应玩家一次性输入触发的状态变更，不承担随时间推进的世界演化
职责——那是未来心跳驱动系统（05 号票起）的范围。

本票的解析是最直接的"按空白切词，第一个词是动词"，**不做**"文本 -> 意图 ->
执行"两阶段解耦——那是 02 号票的范围。但处理函数签名（world、玩家实体 id、
参数列表）不与"怎么从一行文本切出参数"这件事耦合，为 02 号票的重构留自然
切入点。
"""

from __future__ import annotations

from collections.abc import Callable

from mud_engine.components import Description, Exits, Position
from mud_engine.world import EntityId, World

CommandHandler = Callable[[World, EntityId, list[str]], list[str]]

_REGISTRY: dict[str, CommandHandler] = {}


def register(verb: str) -> Callable[[CommandHandler], CommandHandler]:
    """把一个处理函数注册为某个动词的命令。新增命令只需要这一步。"""

    def decorator(handler: CommandHandler) -> CommandHandler:
        _REGISTRY[verb] = handler
        return handler

    return decorator


def execute_line(world: World, player: EntityId, line: str) -> list[str]:
    """给定一行原始输入文本，识别动词、查找命令、执行，返回展示给玩家的消息。

    未知动词、缺失参数、目标不存在均返回明确提示，不抛出未捕获异常。
    """
    stripped = line.strip()
    if not stripped:
        return []

    verb, *args = stripped.split()
    handler = _REGISTRY.get(verb.lower())
    if handler is None:
        return [f"未知命令：{verb}。输入 help 查看当前支持的命令列表。"]
    return handler(world, player, args)


@register("look")
def _cmd_look(world: World, player: EntityId, args: list[str]) -> list[str]:
    """展示玩家当前房间的简述、详细描述与出口列表。"""
    room = _player_room(world, player)
    description = world.require_component(room, Description)
    exits = world.require_component(room, Exits)

    lines = [description.short, description.long]
    if exits.by_direction:
        lines.append("出口：" + "、".join(sorted(exits.by_direction)))
    else:
        lines.append("出口：无")
    return lines


@register("go")
def _cmd_go(world: World, player: EntityId, args: list[str]) -> list[str]:
    """把玩家移动到当前房间某个方向的出口指向的房间，并自动展示新房间。"""
    if not args:
        return ["去哪个方向？用法：go <方向>"]

    direction = args[0].lower()
    room = _player_room(world, player)
    exits = world.require_component(room, Exits)

    target = exits.by_direction.get(direction)
    if target is None:
        return [f"那个方向（{direction}）没有出口。"]

    position = world.require_component(player, Position)
    position.room = target
    return _cmd_look(world, player, [])


@register("help")
def _cmd_help(world: World, player: EntityId, args: list[str]) -> list[str]:
    """列出当前注册表里全部可用的动词（含别名，如 `h`）。"""
    verbs = "、".join(sorted(_REGISTRY))
    return [f"当前支持的命令：{verbs}"]


# `h` 是 `help` 唯一在本票范围内就需要的别名（spec 用户故事 10）。通用的、
# 声明式的"注册命令时随手带别名列表"机制是 02 号票的范围；本票不为这一个
# 特例先建整套机制，直接把同一个处理函数注册两次即可。
_REGISTRY["h"] = _cmd_help


@register("quit")
def _cmd_quit(world: World, player: EntityId, args: list[str]) -> list[str]:
    """请求 CLI 主循环结束（本票不含存档，见 05 号票）。"""
    world.should_quit = True
    return ["再见。"]


def _player_room(world: World, player: EntityId) -> EntityId:
    """读取玩家当前所在房间 id，封装掉组件读取的样板代码。"""
    return world.require_component(player, Position).room


__all__ = ["execute_line", "register"]
