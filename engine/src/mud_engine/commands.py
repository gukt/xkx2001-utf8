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

04 号票新增 open/close/knock/unlock 四个门命令，同样复用解析层的方向别名匹配
（``Intent.target`` = 方向规范名，与 ``go`` 同一套候选）。门状态是独立于
``Exits`` 的 ``Doors`` 组件，本模块只按方向读写它，不改 ``Exits``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mud_engine.components import (
    Container,
    Description,
    Door,
    Doors,
    DoorState,
    Exits,
    Identity,
    Position,
)
from mud_engine.intent import Intent
from mud_engine.world import EntityId, World

CommandHandler = Callable[[World, EntityId, Intent], list[str]]

# 命令生命周期钩子事件名（08 号票）：挂在 07 号票的 ``world.events`` 上，复用同一
# 个 EventBus（``register`` 与 ``commands.register`` 同构）。on_command_before 在
# 处理函数前跑（可否决 / 替换意图），on_command_after 在返回后跑（修饰消息列表）。
ON_COMMAND_BEFORE = "on_command_before"
ON_COMMAND_AFTER = "on_command_after"


@dataclass(frozen=True)
class Allow:
    """前置钩子放行：按（被 ``Replace`` 改写后的）意图继续执行处理函数。无载荷。"""


@dataclass(frozen=True)
class Deny:
    """前置钩子否决：不执行处理函数，把 ``message`` 作为拒绝提示返回给玩家。"""

    message: str


@dataclass(frozen=True)
class Replace:
    """前置钩子替换：用 ``intent`` 取代本次执行的意图，后续 before 钩子与执行都用它。"""

    intent: Intent


# 前置钩子返回值三态（Allow 放行 / Deny 否决 / Replace 替换）。形状被契约测试锁定
# （test_command_hooks 的 TestCommandLifecycleContract），防 M2 引入真实规则时改接口。
CommandBeforeResult = Allow | Deny | Replace

# 钩子签名（契约测试锁定形状）：before 收 (world, player, intent) 返回三态之一
# （返回 None 容错视为 Allow）；after 收 (world, player, 生效意图, 当前消息) 返回
# 消息列表，按注册顺序折叠（前一个的输出是后一个的输入）。
CommandBeforeHook = Callable[[World, EntityId, Intent], CommandBeforeResult | None]
CommandAfterHook = Callable[[World, EntityId, Intent, list[str]], list[str]]

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
    """执行一个已解析的意图：经 before/after 生命周期钩子环绕调处理函数。

    执行阶段完全不关心某个意图是被哪个解析器解析出来的（spec 用户故事 25）。
    未知动词本不该走到这里（解析阶段已拦截成 ParseFailure），但手工构造的
    Intent 若带了未注册动词，这里仍给一句提示而非抛 KeyError。

    08 号票：``execute`` 外包一层命令生命周期钩子（Inform 7 四段式的"前置校验
    -> 执行 -> 后置通知"精炼，是"夜里 NPC 不卖酒""诅咒物品拿不起"等前置否决
    规则的挂载点--不补则 M2 引入时要改 ``execute`` 签名）。``on_command_before``
    在处理函数前跑：``Deny`` 否决并返回拒绝消息（跳过处理函数与 after）、
    ``Replace`` 改写本次意图（后续 before 钩子与执行都用新意图，故 ``Replace``
    改写动词后按生效意图重新解析处理函数）、``Allow`` 放行；M1 默认无 handler 即
    放行，现有 11 个命令行为零回归。``on_command_after`` 在处理函数返回后跑，
    按注册顺序折叠消息列表。原动词未知时无处理函数，before/after 不挂（否决一个
    不存在的命令无意义）；``Replace`` 改写到未知动词时按生效意图给未知命令提示。
    钩子复用 07 号票的 ``world.events`` 注册表；before 的否决短路 / after 的消息
    折叠都不是 fire-and-forget，故走 ``handlers_for`` 自取 handler 列表自行聚合
    （07 已为此预留空间）。
    """
    if intent.verb not in _REGISTRY:
        # 未知动词无处理函数：before/after 不挂（否决一个不存在的命令无意义）。
        return _unknown_verb_message(intent.verb)

    denial, effective_intent = _run_before_hooks(world, player_id, intent)
    if denial is not None:
        # 否决：不执行处理函数，after 也不挂（处理函数没跑就没有"后置"可通知）。
        return [denial]

    # Replace 可能改写动词：按生效意图重新解析处理函数（改写到未知动词给提示）。
    handler = _REGISTRY.get(effective_intent.verb)
    if handler is None:
        return _unknown_verb_message(effective_intent.verb)

    messages = handler(world, player_id, effective_intent)
    return _run_after_hooks(world, player_id, effective_intent, messages)


def _unknown_verb_message(verb: str) -> list[str]:
    """未知动词给玩家的提示（原动词未知 / ``Replace`` 改写到未知动词共用）。"""
    return [f"未知命令：{verb}。输入 help 查看当前支持的命令列表。"]


def _run_before_hooks(
    world: World, player_id: EntityId, intent: Intent
) -> tuple[str | None, Intent]:
    """跑 ``on_command_before`` 全部钩子，返回 (否决消息或 None, 生效意图)。

    聚合：按注册顺序遍历，``Replace`` 改写"生效意图"（后续钩子看到改写后的）、
    首个 ``Deny`` 即否决并短路（其后的钩子不再跑）。``Allow`` 与 ``None``（容错
    忘写 return）都视为放行。M1 默认无钩子注册时直接返回 (None, 原意图)。
    """
    effective = intent
    for hook in world.events.handlers_for(ON_COMMAND_BEFORE):
        result = hook(world, player_id, effective)
        if isinstance(result, Deny):
            return result.message, effective
        if isinstance(result, Replace):
            effective = result.intent
        # Allow / None：放行，继续下一个
    return None, effective


def _run_after_hooks(
    world: World, player_id: EntityId, intent: Intent, messages: list[str]
) -> list[str]:
    """跑 ``on_command_after`` 全部钩子，按注册顺序折叠消息列表。

    每个 after 钩子收 (world, player, 生效意图, 当前消息) 返回新消息列表，前一
    个的输出是后一个的输入。M1 默认无钩子注册时原样返回（零回归）。
    """
    for hook in world.events.handlers_for(ON_COMMAND_AFTER):
        messages = hook(world, player_id, intent, messages)
    return messages


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
    """展示玩家当前房间的简述、详细描述、地面物品、在场 NPC 与出口列表。

    出口列表标注门状态（关/锁）--门状态来自独立于 ``Exits`` 的 ``Doors`` 组件，
    look 综合两者展示（04 号票）。
    """
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
        labels = [_exit_label(world, room, direction) for direction in sorted(exits.by_direction)]
        lines.append("出口：" + "、".join(labels))
    else:
        lines.append("出口：无")
    return lines


@register("go")
def _cmd_go(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把玩家移动到当前房间某个方向的出口指向的房间，并自动展示新房间。

    出口上若有门且非开（关/锁），拒绝移动并提示门状态（04 号票）。
    """
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

    door = _door_in_direction(world, room, direction)
    if door is not None:
        if door.state is DoorState.LOCKED:
            return ["那个方向的门锁着，过不去。"]
        if door.state is DoorState.CLOSED:
            return ["那个方向的门关着，过不去。"]

    position = world.require_component(player_id, Position)
    position.room = passage.target
    return _cmd_look(world, player_id, Intent(verb="look", target=None))


@register("open")
def _cmd_open(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """打开当前房间某方向出口上的门（04 号票）。锁着的门需先 unlock。"""
    direction = intent.target
    if direction is None:
        return ["开什么？用法：open <方向>"]
    door = _door_at_player(world, player_id, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is DoorState.LOCKED:
        return ["那扇门锁着，先用钥匙 unlock。"]
    if door.state is DoorState.OPEN:
        return ["那扇门已经开着。"]
    door.state = DoorState.OPEN
    return [f"你打开了{direction}方向的门。"]


@register("close")
def _cmd_close(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """关上当前房间某方向出口上的门（04 号票）。锁着的门视为已关，不另处理。"""
    direction = intent.target
    if direction is None:
        return ["关什么？用法：close <方向>"]
    door = _door_at_player(world, player_id, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is DoorState.LOCKED:
        return ["那扇门锁着，关不了。"]
    if door.state is DoorState.CLOSED:
        return ["那扇门已经关着。"]
    door.state = DoorState.CLOSED
    return [f"你关上了{direction}方向的门。"]


@register("knock")
def _cmd_knock(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """敲当前房间某方向出口上的门，按门状态给不同反馈（04 号票，纯展示）。"""
    direction = intent.target
    if direction is None:
        return ["敲什么？用法：knock <方向>"]
    door = _door_at_player(world, player_id, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is DoorState.LOCKED:
        return [f"你敲了敲{direction}方向的门，门锁着，没人应。"]
    if door.state is DoorState.CLOSED:
        return [f"你敲了敲{direction}方向的门，咚咚作响。"]
    return [f"{direction}方向的门开着，敲什么。"]


@register("unlock")
def _cmd_unlock(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """解锁当前房间某方向出口上的门（04 号票）。

    锁定门绑定钥匙（``key_item_id``）时，玩家物品栏需持有该钥匙物品才能解锁；
    解锁后门变为关（``CLOSED``），需再 ``open`` 才能通行（行为在实现中明确锁定）。
    """
    direction = intent.target
    if direction is None:
        return ["解锁什么？用法：unlock <方向>"]
    door = _door_at_player(world, player_id, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is not DoorState.LOCKED:
        return ["那扇门没上锁。"]
    if door.key_item_id is not None:
        player_container = world.get_component(player_id, Container)
        if player_container is None or door.key_item_id not in player_container.items:
            return ["你需要一把匹配的钥匙才能 unlock 那扇门。"]
    door.state = DoorState.CLOSED
    return [f"你解锁了{direction}方向的门。"]


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


def _door_in_direction(world: World, room: EntityId, direction: str) -> Door | None:
    """读取某房间某方向的门状态；房间无 Doors 组件或该方向无门时返回 None。

    门状态读自独立于 ``Exits`` 的 ``Doors`` 组件（04 号票）。不抛异常：玩家
    引用一个没门的方向属于"可输入但无效"，应给提示而非崩溃。
    """
    doors = world.get_component(room, Doors)
    if doors is None:
        return None
    return doors.by_direction.get(direction)


def _door_at_player(world: World, player_id: EntityId, direction: str) -> Door | None:
    """门命令共用：取玩家当前房间某方向的门（不存在返回 None 让命令给提示）。"""
    room = _player_room(world, player_id)
    return _door_in_direction(world, room, direction)


def _exit_label(world: World, room: EntityId, direction: str) -> str:
    """look 出口列表的单项：方向名 + 门状态标注（关/锁），无门或开着不加标注。"""
    door = _door_in_direction(world, room, direction)
    if door is not None and door.state is not DoorState.OPEN:
        suffix = "（锁）" if door.state is DoorState.LOCKED else "（关）"
        return direction + suffix
    return direction


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


__all__ = [
    "ON_COMMAND_AFTER",
    "ON_COMMAND_BEFORE",
    "Allow",
    "CommandAfterHook",
    "CommandBeforeHook",
    "CommandBeforeResult",
    "Deny",
    "Replace",
    "canonical_verbs",
    "execute",
    "register",
    "resolve_verb",
]
