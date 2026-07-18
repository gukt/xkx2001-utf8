"""命令调度：以"动词字符串 -> 处理函数"注册表组织。

调度流程保留"识别动词 -> 查找命令 -> 执行"最小主干；权限校验阶段留作未来
占位，M1 单机单玩家不需要它，本票不落地一个空阶段，避免过度设计。

处理函数只响应玩家一次性输入触发的状态变更，不承担随时间推进的世界演化
职责--那是未来心跳驱动系统（05 号票起）的范围。

02 号票把"一行文本怎么变成处理函数调用"拆成解析（文本->意图，见 parsing.py）
与执行（意图->效果，本模块的 ``execute``）两阶段；处理函数签名因此改为接收
``Intent`` 而非原始参数列表，不再感知"文本怎么切出来的"。命令别名在注册时
声明式声明（``register("look", aliases=("l",))``），不在调度框架里为每个命令
各写特例分支。03 号票新增 take/drop/inventory 三个物品命令，复用同一管线：
物品名匹配在解析层用 ``match_target`` 完成（``Intent.target`` = 物品规范名），
本模块只按规范名在容器里找到 entity 引用并转移，不直接碰别名匹配。
"""

from __future__ import annotations

from collections.abc import Callable

from mud_engine.components import Container, Description, Exits, Identity, Position
from mud_engine.intent import Intent
from mud_engine.world import EntityId, World

CommandHandler = Callable[[World, EntityId, Intent], list[str]]

# 规范动词 -> 处理函数
_REGISTRY: dict[str, CommandHandler] = {}
# 命令别名 -> 规范动词（供解析器查；新增命令"顺带"就有别名支持）
_ALIASES: dict[str, str] = {}


def register(
    verb: str, aliases: tuple[str, ...] = ()
) -> Callable[[CommandHandler], CommandHandler]:
    """把处理函数注册为某个动词的命令，顺带声明它的命令别名。

    新增命令只需要这一步；别名随注册声明，不另起一套特例机制（02 号票）。
    命令别名与已有规范动词或已声明的别名冲突时直接报错--这是"别名冲突不是
    未定义行为"的明确处理（spec 用户故事 24、02 号票 acceptance 第 7 条）：
    冲突是配置/程序错误，应在注册期 fail-fast，而非静默覆盖让后注册者赢。
    """

    def decorator(handler: CommandHandler) -> CommandHandler:
        _REGISTRY[verb] = handler
        for alias in aliases:
            if alias in _REGISTRY:
                raise ValueError(f"命令别名 {alias!r} 与已注册命令冲突")
            existing = _ALIASES.get(alias)
            if existing is not None and existing != verb:
                raise ValueError(f"命令别名 {alias!r} 已被命令 {existing!r} 占用")
            _ALIASES[alias] = verb
        return handler

    return decorator


def resolve_verb(token: str) -> str | None:
    """把一个 token 解析成规范动词：直接命中或经命令别名表命中，否则 None。"""
    if token in _REGISTRY:
        return token
    return _ALIASES.get(token)


def canonical_verbs() -> list[str]:
    """列出全部规范动词（不含别名），供 help 命令展示。"""
    return sorted(_REGISTRY)


def aliases_for(verb: str) -> list[str]:
    """列出某个规范动词声明的全部命令别名（供 help 展示）。"""
    return sorted(alias for alias, target in _ALIASES.items() if target == verb)


def execute(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """执行一个已解析的意图：查注册表调对应处理函数并产出消息。

    执行阶段完全不关心某个意图是被哪个解析器解析出来的（spec 用户故事 25）。
    未知动词本不该走到这里（解析阶段已拦截成 ParseFailure），但手工构造的
    Intent 若带了未注册动词，这里仍给一句提示而非抛 KeyError。
    """
    handler = _REGISTRY.get(intent.verb)
    if handler is None:
        return [f"未知命令：{intent.verb}。输入 help 查看当前支持的命令列表。"]
    return handler(world, player_id, intent)


def _sorted_item_names(world: World, container: Container) -> list[str]:
    """容器内物品的规范名，按名排序（look 地面展示与 inventory 共用）。"""
    return sorted(world.require_component(item, Identity).name for item in container.items)


def _sorted_npc_names_in_room(world: World, room: EntityId, player_id: EntityId) -> list[str]:
    """同房间内静态展示型 NPC 的规范名，按名排序（look 在场展示用）。

    NPC 用 ``Position`` 表达"在房间里"，不进房间的 ``Container``（否则会被
    take）；玩家也持有 Position，故排除玩家本人。物品无 Position，不会被收进。
    """
    names: list[str] = []
    for entity in world.entities_with(Position):
        if entity == player_id:
            continue
        if world.require_component(entity, Position).room != room:
            continue
        identity = world.get_component(entity, Identity)
        if identity is not None:
            names.append(identity.name)
    return sorted(names)


@register("look", aliases=("l",))
def _cmd_look(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """展示玩家当前房间的简述、详细描述、地面物品、在场 NPC 与出口列表。"""
    room = _player_room(world, player_id)
    description = world.require_component(room, Description)
    exits = world.require_component(room, Exits)

    lines = [description.short, description.long]
    container = world.get_component(room, Container)
    if container and container.items:
        names = _sorted_item_names(world, container)
        lines.append("这里有：" + "、".join(names))
    npc_names = _sorted_npc_names_in_room(world, room, player_id)
    if npc_names:
        lines.append("你看到：" + "、".join(npc_names))
    if exits.by_direction:
        lines.append("出口：" + "、".join(sorted(exits.by_direction)))
    else:
        lines.append("出口：无")
    return lines


@register("go")
def _cmd_go(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把玩家移动到当前房间某个方向的出口指向的房间，并自动展示新房间。"""
    direction = intent.target
    if direction is None:
        return ["去哪个方向？用法：go <方向>"]

    room = _player_room(world, player_id)
    exits = world.require_component(room, Exits)

    passage = exits.by_direction.get(direction)
    if passage is None:
        # 解析阶段正常会把"当前房间没有的方向"拦成 NO_TARGET_MATCH；这里保留
        # 兜底，防御手工构造的 Intent 带了不规范方向。
        return [f"那个方向（{direction}）没有出口。"]

    position = world.require_component(player_id, Position)
    position.room = passage.target
    return _cmd_look(world, player_id, Intent(verb="look", target=None))


@register("take")
def _cmd_take(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把当前房间地面容器里匹配的物品移到玩家物品栏（03 号票）。"""
    name = intent.target
    if name is None:
        return ["拿什么？用法：take <物品>"]

    room = _player_room(world, player_id)
    room_container = world.require_component(room, Container)
    player_container = world.require_component(player_id, Container)
    item = _find_item_in_container(world, room_container, name)
    if item is None:
        # 解析阶段已 match，正常不会走到；保留兜底防御手工构造的 Intent。
        return [f"这里没有 {name}。"]
    room_container.items.discard(item)
    player_container.items.add(item)
    return [f"你拿起 {name}。"]


@register("drop")
def _cmd_drop(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把玩家物品栏里匹配的物品放到当前房间地面容器（03 号票）。"""
    name = intent.target
    if name is None:
        return ["放下什么？用法：drop <物品>"]

    room = _player_room(world, player_id)
    player_container = world.require_component(player_id, Container)
    room_container = world.require_component(room, Container)
    item = _find_item_in_container(world, player_container, name)
    if item is None:
        return [f"你没有 {name}。"]
    player_container.items.discard(item)
    room_container.items.add(item)
    return [f"你放下 {name}。"]


@register("inventory", aliases=("i",))
def _cmd_inventory(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """列出玩家物品栏当前持有的全部物品（03 号票）。"""
    container = world.require_component(player_id, Container)
    if not container.items:
        return ["你什么都没带。"]
    return ["你带着：" + "、".join(_sorted_item_names(world, container))]


@register("help", aliases=("h",))
def _cmd_help(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """列出当前注册表里全部可用的规范命令及其命令别名。"""
    entries: list[str] = []
    for verb in canonical_verbs():
        aliases = aliases_for(verb)
        entry = verb if not aliases else f"{verb}（{'、'.join(aliases)}）"
        entries.append(entry)
    lines = ["当前支持的命令：" + "、".join(entries)]
    lines.append("方向简写 n/s/e/w 可代替 go <方向>。")
    return lines


@register("quit")
def _cmd_quit(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """请求 CLI 主循环结束（本票不含存档，见 05 号票）。"""
    world.should_quit = True
    return ["再见。"]


def _find_item_in_container(world: World, container: Container, name: str) -> EntityId | None:
    """在容器里找规范名等于 name 的物品 entity id；不存在返回 None。

    解析阶段已确认 name 在候选里且唯一（同名物品会先被 match_target 判歧义
    拦下），这里按规范名匹配拿到 entity 引用。M1 假设容器内物品规范名唯一。
    """
    for item in container.items:
        if world.require_component(item, Identity).name == name:
            return item
    return None


def _player_room(world: World, player_id: EntityId) -> EntityId:
    """读取玩家当前所在房间 id，封装掉组件读取的样板代码。"""
    return world.require_component(player_id, Position).room


__all__ = ["canonical_verbs", "execute", "register", "resolve_verb"]
