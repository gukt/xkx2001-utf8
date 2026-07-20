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

08 号票给 ``execute`` 外包命令级 before/after 生命周期钩子
（``on_command_before``/``on_command_after``，可否决 / 替换意图 / 修饰消息）；
09 号票在移动 / 物品 / 门命令路径埋**领域语义级**事件点
（``on_before_enter_room``/``on_enter_room``/``on_leave_room``/``on_traverse_blocked``/
``on_take``/``on_drop``/``on_door_state_change``），全部空挂复用 07 号票的
``world.events`` 事件总线，M1 默认放行不改现有命令行为。两者层次不同：命令级
钩子看 ``intent``（粗粒度，任何命令）、领域级事件点看领域上下文（细粒度，特定
语义发生时--如"门被打开"由 open/close/unlock 三处收敛到 ``on_door_state_change``
一个事件名）。可否决的 before 事件点复用 08 的 ``Allow``/``Deny``（领域级无
``Replace`` 改写语义）。
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
    Inquiry,
    PlayerSession,
    Position,
    Stackable,
    Valuable,
    Weight,
)
from mud_engine.events import Deny, run_vetoable
from mud_engine.intent import Intent
from mud_engine.npc_query import is_askable_npc
from mud_engine.transfer import (
    ON_DROP,
    ON_TAKE,
    TransferContext,
    item_weight,
    transfer,
)
from mud_engine.world import EntityId, World

CommandHandler = Callable[[World, EntityId, Intent], list[str]]

# 32/33 号票：``Deny`` / ``run_vetoable`` 的规范定义在 ``events``，``ON_TAKE`` /
# ``ON_DROP`` / ``TransferContext`` 在 ``transfer``（转移域概念归转移模块，消除
# transfer -> commands 反向 import）。commands 重新导出它们以保持命令钩子 API 表面
# 不变（``from mud_engine.commands import Deny, ON_TAKE, TransferContext`` 等仍可用，
# 见 test_command_hooks / test_domain_events / test_items_extension 的契约测试）。

# 命令生命周期钩子事件名（08 号票）：挂在 07 号票的 ``world.events`` 上，复用同一
# 个 EventBus（``register`` 与 ``commands.register`` 同构）。on_command_before 在
# 处理函数前跑（可否决 / 替换意图），on_command_after 在返回后跑（修饰消息列表）。
ON_COMMAND_BEFORE = "on_command_before"
ON_COMMAND_AFTER = "on_command_after"


@dataclass(frozen=True)
class Allow:
    """前置钩子放行：按（被 ``Replace`` 改写后的）意图继续执行处理函数。无载荷。"""


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

# 领域事件点事件名（09 号票）：挂在 07 号票的 ``world.events`` 上，复用同一个
# EventBus。与 08 号票的命令级 ``on_command_before``/``on_command_after`` 不同，
# 这是**领域语义级**事件点--在"移动 / 拿取 / 丢 / 门状态变化"这些领域事实发生时
# 触发，handler 收到的是领域上下文（房间 / 物品 / 门状态），而非命令意图。两者
# 互补：08 是"任何命令执行前后"的粗粒度环绕（handler 要自己从 intent 反推语义），
# 09 是"特定语义发生时"的细粒度触发点（如"门被打开"这个事实由 open/close/unlock
# 三处都能产生，收敛到一个事件名 ``on_door_state_change``，而非在命令钩子里逐个
# 判断动词）。spec 块 A user story 3/4/5/12。
ON_BEFORE_ENTER_ROOM = "on_before_enter_room"
ON_ENTER_ROOM = "on_enter_room"
ON_LEAVE_ROOM = "on_leave_room"
ON_TRAVERSE_BLOCKED = "on_traverse_blocked"
ON_DOOR_STATE_CHANGE = "on_door_state_change"
# 房间广播事件（28 号票，D4）：``say`` / Chatter 经 ``room_say`` 触发，
# handler 收 ``HearSayContext``（speaker / room / text）。
ON_HEAR_SAY = "on_hear_say"


@dataclass(frozen=True)
class EnterRoomContext:
    """移动事件点上下文：``on_before_enter_room`` / ``on_enter_room`` /
    ``on_leave_room`` 共用同一形状。

    before 在移动前触发（玩家仍在 ``from_room``）、可否决；enter/leave 在移动后
    触发（玩家已在 ``to_room``）、fire-and-forget。``from_room`` 是离开的旧房间、
    ``to_room`` 是进入的新房间。形状被契约测试锁定（test_domain_events），未来加
    字段不破坏 ``handler(ctx)`` 签名（同 ``TickContext`` 思路，spec 块 A user story 6）。
    """

    player_id: EntityId
    from_room: EntityId
    to_room: EntityId


@dataclass(frozen=True)
class TraverseBlockedContext:
    """``on_traverse_blocked`` 上下文：出口存在但被门挡住时触发（go 走不通）。

    ``door_state`` 区分是关还是锁挡住了通行，handler 据此给不同反馈（如"锁住"
    触发 NPC 提示钥匙线索）。出口本身不存在（无门无出口）不触发此事件--那是输入
    无效，不是领域阻塞。
    """

    player_id: EntityId
    from_room: EntityId
    direction: str
    door_state: DoorState


@dataclass(frozen=True)
class DoorStateChangeContext:
    """``on_door_state_change`` 上下文：门状态实际变化时触发
    （open/close/unlock 改 ``door.state`` 处）。

    ``old_state``/``new_state`` 用 ``DoorState`` 枚举，handler 据此判断"开->关"
    还是"锁->关"等。knock 不改状态不触发；open 已开 / close 已关 / unlock 未锁
    等无变化路径不触发（"门被打开触发机关""门状态联动出口增删"等规则的挂载点，
    spec 块 A user story 5）。
    """

    player_id: EntityId
    room: EntityId
    direction: str
    old_state: DoorState
    new_state: DoorState


@dataclass(frozen=True)
class HearSayContext:
    """``on_hear_say`` 上下文：房间内有人 ``say`` 时触发（28 号票）。

    ``speaker_id`` 是说话者（玩家或 NPC），``room`` 是所在房间，``text`` 是说
    出的内容。形状被契约测试锁定，供 NPC 反应 / 未来对话钩子消费。
    """

    speaker_id: EntityId
    room: EntityId
    text: str


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
    """无目标：展示当前房间；有目标：展示物品详情（23 号票）。

    房间 look：简述、详细描述、户外时辰/天气（15/17）、地面物品、在场 NPC、出口。
    物品 look：long + 容器内容 + 堆叠/价值/重量数值。
    """
    if intent.target is not None:
        return _look_item(world, player_id, intent.target)

    room = _player_room(world, player_id)
    description = world.require_component(room, Description)
    exits = world.require_component(room, Exits)

    lines = [description.short, description.long]
    # 户外房间追加当前时辰 × 天气描述（15/17 号票）；室内不追加。
    if description.outdoors and world.nature is not None:
        lines.append(world.nature.outdoor_desc())
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

    出口上若有门且非开（关/锁），拒绝移动并提示门状态（04 号票），并分发
    ``on_traverse_blocked``（09 号票：出口存在但被门挡住的领域阻塞事件）。移动前
    分发可否决的 ``on_before_enter_room``，否决则不移动；移动后分发 ``on_leave_room``
    （离开旧房间）与 ``on_enter_room``（进入新房间）。
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
    if door is not None and door.state is not DoorState.OPEN:
        # 出口存在但被门挡住：分发 on_traverse_blocked（door_state 区分锁/关）。
        world.events.dispatch(
            ON_TRAVERSE_BLOCKED,
            TraverseBlockedContext(
                player_id=player_id,
                from_room=room,
                direction=direction,
                door_state=door.state,
            ),
        )
        if door.state is DoorState.LOCKED:
            return ["那个方向的门锁着，过不去。"]
        return ["那个方向的门关着，过不去。"]

    # before：可否决（"封城不能进""进房触发 NPC 反应前先校验"等规则挂载点）。
    # 否决则不移动、不触发 enter/leave。
    denial = run_vetoable(
        world,
        ON_BEFORE_ENTER_ROOM,
        EnterRoomContext(player_id=player_id, from_room=room, to_room=passage.target),
    )
    if denial is not None:
        return [denial]

    # 移动发生。
    position = world.require_component(player_id, Position)
    position.room = passage.target
    # after：先离开旧房间、再进入新房间（对应 LPC move 先 leave 旧环境再 enter 新）。
    # 两者共用 EnterRoomContext 形状，事件名区分语义。fire-and-forget 不短路。
    enter_ctx = EnterRoomContext(player_id=player_id, from_room=room, to_room=passage.target)
    world.events.dispatch(ON_LEAVE_ROOM, enter_ctx)
    world.events.dispatch(ON_ENTER_ROOM, enter_ctx)
    return _cmd_look(world, player_id, Intent(verb="look", target=None))


@register("open")
def _cmd_open(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """打开当前房间某方向出口上的门（04 号票）。锁着的门需先 unlock。

    门状态实际变化时（CLOSED->OPEN）分发 ``on_door_state_change``（09 号票）。
    """
    direction = intent.target
    if direction is None:
        return ["开什么？用法：open <方向>"]
    room = _player_room(world, player_id)
    door = _door_in_direction(world, room, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is DoorState.LOCKED:
        return ["那扇门锁着，先用钥匙 unlock。"]
    if door.state is DoorState.OPEN:
        return ["那扇门已经开着。"]
    _set_door_state(world, player_id, room, direction, door, DoorState.OPEN)
    return [f"你打开了{direction}方向的门。"]


@register("close")
def _cmd_close(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """关上当前房间某方向出口上的门（04 号票）。锁着的门视为已关，不另处理。

    门状态实际变化时（OPEN->CLOSED）分发 ``on_door_state_change``（09 号票）。
    """
    direction = intent.target
    if direction is None:
        return ["关什么？用法：close <方向>"]
    room = _player_room(world, player_id)
    door = _door_in_direction(world, room, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is DoorState.LOCKED:
        return ["那扇门锁着，关不了。"]
    if door.state is DoorState.CLOSED:
        return ["那扇门已经关着。"]
    _set_door_state(world, player_id, room, direction, door, DoorState.CLOSED)
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
    门状态实际变化时（LOCKED->CLOSED）分发 ``on_door_state_change``（09 号票）。
    """
    direction = intent.target
    if direction is None:
        return ["解锁什么？用法：unlock <方向>"]
    room = _player_room(world, player_id)
    door = _door_in_direction(world, room, direction)
    if door is None:
        return [f"那个方向（{direction}）没有门。"]
    if door.state is not DoorState.LOCKED:
        return ["那扇门没上锁。"]
    if door.key_item_id is not None:
        player_container = world.get_component(player_id, Container)
        if player_container is None or door.key_item_id not in player_container.items:
            return ["你需要一把匹配的钥匙才能 unlock 那扇门。"]
    _set_door_state(world, player_id, room, direction, door, DoorState.CLOSED)
    return [f"你解锁了{direction}方向的门。"]


@register("take")
def _cmd_take(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """从房间地面或容器取出物品到玩家物品栏（03/19/20/22 号票）。

    - ``take <物品>`` / ``take <物品> <数量>``：从当前房间地面拿（可拆堆）。
    - ``take <物品> from <容器>``：从可达容器取出（intent.args 含 ``from`` + 容器名）。
    全部走 ``transfer``：``on_take`` 否决、no_take、堆叠合并/拆分在原语内处理。
    """
    name = intent.target
    if name is None:
        return ["拿什么？用法：take <物品> [数量] [from <容器>]"]

    room = _player_room(world, player_id)
    from_container_name, amount = _parse_take_args(intent.args)
    if from_container_name is not None:
        holder = _find_reachable_container(world, player_id, from_container_name)
        if holder is None:
            return [f"这里没有容器 {from_container_name}。"]
        src = holder
        src_container = world.require_component(src, Container)
        missing = f"{from_container_name} 里没有 {name}。"
    else:
        src = room
        src_container = world.require_component(room, Container)
        missing = f"这里没有 {name}。"

    # spec C3：地面多堆同名 Stackable 自动合并拿走（无数量全拿，有数量从一堆拆）。
    if amount is None:
        stackables = [
            it
            for it in src_container.items
            if world.get_component(it, Stackable) is not None
            and world.require_component(it, Identity).name == name
        ]
        if stackables:
            for it in stackables:
                r = transfer(world, it, src, player_id, player_id=player_id)
                if not r.success:
                    return [r.message or "拿不起来。"]
            return [f"你拿起 {name}。"]

    item = _find_item_in_container(world, src_container, name)
    if item is None:
        return [missing]

    result = transfer(
        world, item, src, player_id, player_id=player_id, amount=amount
    )
    if not result.success:
        return [result.message or "拿不起来。"]
    if amount is not None:
        return [f"你拿起 {amount} 个 {name}。"]
    return [f"你拿起 {name}。"]


@register("drop")
def _cmd_drop(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把玩家物品栏里匹配的物品放到当前房间地面（03/19 号票）。

    走 ``transfer``：``on_drop`` 否决、``no_drop``（含自定义提示）在原语内处理。
    """
    name = intent.target
    if name is None:
        return ["放下什么？用法：drop <物品>"]

    room = _player_room(world, player_id)
    player_container = world.require_component(player_id, Container)
    item = _find_item_in_container(world, player_container, name)
    if item is None:
        return [f"你没有 {name}。"]
    result = transfer(world, item, player_id, room, player_id=player_id)
    if not result.success:
        return [result.message or "放不下。"]
    return [f"你放下 {name}。"]


@register("put")
def _cmd_put(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把物品栏物品放入可达容器：``put <物品> in <容器>``（22/24 号票）。

    容器须在同房间地面或玩家物品栏内。走 ``transfer``（离开玩家触发 on_drop /
    no_drop；容量与重量上限在原语内拒绝）。
    """
    name = intent.target
    if name is None or not intent.args:
        return ["放什么？用法：put <物品> in <容器>"]
    container_name = intent.args[0]
    player_container = world.require_component(player_id, Container)
    item = _find_item_in_container(world, player_container, name)
    if item is None:
        return [f"你没有 {name}。"]
    holder = _find_reachable_container(world, player_id, container_name)
    if holder is None:
        return [f"这里没有容器 {container_name}。"]
    if holder == item:
        return ["不能把东西放进它自己。"]
    result = transfer(world, item, player_id, holder, player_id=player_id)
    if not result.success:
        return [result.message or "放不进去。"]
    return [f"你把 {name} 放进了 {container_name}。"]


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


@register("ask")
def _cmd_ask(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """向同房间 NPC 提问：``ask <npc> about <topic>``（27 号票，D3）。

    解析层已把 NPC 规范名放进 ``intent.target``、topic 放进 ``intent.args[0]``。
    响应走 ``Inquiry`` 组件的声明式映射；未知 topic 用 ``default`` 或内置提示。
    """
    npc_name = intent.target
    if npc_name is None or not intent.args:
        return ["问谁什么？用法：ask <人物> about <话题>"]
    topic = intent.args[0]
    npc = _find_npc_in_room(world, player_id, npc_name)
    if npc is None:
        return [f"这里没有 {npc_name}。"]
    inquiry = world.get_component(npc, Inquiry)
    if inquiry is None:
        return [f"{npc_name}似乎不想和你说话。"]
    if topic in inquiry.topics:
        return [f"{npc_name}说：{inquiry.topics[topic]}"]
    if inquiry.default is not None:
        return [f"{npc_name}说：{inquiry.default}"]
    return [f"{npc_name}摇摇头，似乎不知道。"]


@register("say")
def _cmd_say(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """向同房间广播一句话（28 号票，D4）。空内容拒绝。"""
    text = intent.args[0] if intent.args else ""
    if not text.strip():
        return ["说什么？用法：say <内容>"]
    return room_say(world, player_id, text)


def room_say(world: World, speaker_id: EntityId, text: str) -> list[str]:
    """向同房间广播一句话，并触发 ``on_hear_say``（28 号票）。

    说话者若是玩家，返回 ``你说：...``；同房间其他玩家经 ``pending_messages``
    收到 ``{名}说：...``（M1 单玩家时主要服务 NPC Chatter）。NPC 说话不返回
    给自己，只推给房间内玩家。Chatter（ai.py）与 ``say`` 命令共用本函数。
    """
    room = world.require_component(speaker_id, Position).room
    speaker_name = world.require_component(speaker_id, Identity).name
    world.events.dispatch(
        ON_HEAR_SAY,
        HearSayContext(speaker_id=speaker_id, room=room, text=text),
    )
    speaker_is_player = _is_player_entity(world, speaker_id)
    for entity in world.entities_with(Position):
        if entity == speaker_id:
            continue
        if world.require_component(entity, Position).room != room:
            continue
        if _is_player_entity(world, entity):
            world.pending_messages.append(f"{speaker_name}说：{text}")
    if speaker_is_player:
        return [f"你说：{text}"]
    return []


def _is_player_entity(world: World, entity: EntityId) -> bool:
    """玩家判定：挂 ``PlayerSession``（US33；28 号票起取代 Container 启发式）。"""
    return world.has_component(entity, PlayerSession)


def _find_npc_in_room(world: World, player_id: EntityId, name: str) -> EntityId | None:
    """在玩家当前房间找规范名等于 name 的可 ask NPC（见 ``npc_query.is_askable_npc``）。"""
    room = _player_room(world, player_id)
    for entity in world.entities_with(Position):
        if entity == player_id:
            continue
        if world.require_component(entity, Position).room != room:
            continue
        if not is_askable_npc(world, entity):
            continue
        identity = world.get_component(entity, Identity)
        if identity is not None and identity.name == name:
            return entity
    return None


def _look_item(world: World, player_id: EntityId, name: str) -> list[str]:
    """``look <物品>``：long + 容器内容 + 堆叠/价值/重量（23 号票）。"""
    item = _find_lookable_item(world, player_id, name)
    if item is None:
        return [f"这里没有 {name}。"]
    description = world.get_component(item, Description)
    lines: list[str] = []
    if description is not None and description.long:
        lines.append(description.long)
    elif description is not None and description.short:
        lines.append(description.short)
    else:
        lines.append(name)

    stackable = world.get_component(item, Stackable)
    if stackable is not None:
        lines.append(f"数量：{stackable.amount}")
    valuable = world.get_component(item, Valuable)
    if valuable is not None:
        lines.append(f"价值：{valuable.value}")
    # 有 Stackable / Valuable / Weight 之一时展示重量（纯描述物品不硬塞重量行）。
    if (
        stackable is not None
        or valuable is not None
        or world.get_component(item, Weight) is not None
    ):
        lines.append(f"重量：{item_weight(world, item):g}")

    nested = world.get_component(item, Container)
    if nested is not None:
        if nested.items:
            lines.append("里面有：" + "、".join(_sorted_item_names(world, nested)))
        else:
            lines.append("里面是空的。")
    return lines


def _find_lookable_item(world: World, player_id: EntityId, name: str) -> EntityId | None:
    """在房间地面、玩家物品栏及其直接嵌套容器中按规范名找物品。"""
    room = _player_room(world, player_id)
    for holder in (room, player_id):
        container = world.get_component(holder, Container)
        if container is None:
            continue
        found = _find_item_in_container(world, container, name)
        if found is not None:
            return found
        for nested_id in container.items:
            nested = world.get_component(nested_id, Container)
            if nested is None:
                continue
            found = _find_item_in_container(world, nested, name)
            if found is not None:
                return found
    return None


def _parse_take_args(args: tuple[str, ...]) -> tuple[str | None, int | None]:
    """解析 take 的 args：可选数量 + 可选 ``from <容器>``。

    返回 ``(容器规范名或 None, 数量或 None)``。解析层已把容器名解析为规范名；
    数量为十进制正整数字符串。
    """
    if not args:
        return None, None
    tokens = list(args)
    amount: int | None = None
    # 形如 ("3",) / ("3", "from", "箱子") / ("from", "箱子")
    if tokens[0].isdigit():
        amount = int(tokens[0])
        tokens = tokens[1:]
    container_name: str | None = None
    if len(tokens) >= 2 and tokens[0] == "from":
        container_name = tokens[1]
    elif len(tokens) == 1 and tokens[0] != "from":
        # 兼容仅数量：已在上面处理；孤立非 from token 忽略（防御）。
        pass
    return container_name, amount


def _find_reachable_container(
    world: World, player_id: EntityId, name: str
) -> EntityId | None:
    """按规范名找可达容器物品：当前房间地面或玩家物品栏内挂 Container 的物品。"""
    room = _player_room(world, player_id)
    for holder in (room, player_id):
        container = world.get_component(holder, Container)
        if container is None:
            continue
        for item in container.items:
            if world.require_component(item, Identity).name != name:
                continue
            if world.get_component(item, Container) is not None:
                return item
    return None


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


def _set_door_state(
    world: World,
    player_id: EntityId,
    room: EntityId,
    direction: str,
    door: Door,
    new_state: DoorState,
) -> None:
    """改门状态并分发 ``on_door_state_change``（open/close/unlock 共用，09 号票）。

    记录 ``old_state``、改 ``door.state``、dispatch 事件。调用方已在分支里确认
    状态会实际变化（open 前是 CLOSED、close 前是 OPEN、unlock 前是 LOCKED），故
    old/new 必不同。集中在此使 ``on_door_state_change`` 的触发只有一处，避免三处
    命令各自 dispatch 漏挂（"门被打开触发机关""门状态联动出口增删"等规则的挂载点）。
    """
    old_state = door.state
    door.state = new_state
    world.events.dispatch(
        ON_DOOR_STATE_CHANGE,
        DoorStateChangeContext(
            player_id=player_id,
            room=room,
            direction=direction,
            old_state=old_state,
            new_state=new_state,
        ),
    )


def _exit_label(world: World, room: EntityId, direction: str) -> str:
    """look 出口列表的单项：方向名 + 门状态标注（关/锁），无门或开着不加标注。"""
    door = _door_in_direction(world, room, direction)
    if door is not None and door.state is not DoorState.OPEN:
        suffix = "（锁）" if door.state is DoorState.LOCKED else "（关）"
        return direction + suffix
    return direction


def _find_item_in_container(world: World, container: Container, name: str) -> EntityId | None:
    """在容器里找规范名等于 name 的物品 entity id；不存在返回 None。

    返回第一个匹配项。同名 Stackable 已在解析阶段去重为一堆（spec C3 自动
    合并），此处可能命中其中任一实体；take 无数量走多堆合并路径不调本函数，
    take <数量> 从这一堆拆。同名非 Stackable 仍会被 match_target 判 Ambiguous
    拦下，不会到此。
    """
    for item in container.items:
        if world.require_component(item, Identity).name == name:
            return item
    return None


def _player_room(world: World, player_id: EntityId) -> EntityId:
    """读取玩家当前所在房间 id，封装掉组件读取的样板代码。"""
    return world.require_component(player_id, Position).room


__all__ = [
    "Allow",
    "CommandAfterHook",
    "CommandBeforeHook",
    "CommandBeforeResult",
    "Deny",
    "DoorStateChangeContext",
    "EnterRoomContext",
    "HearSayContext",
    "ON_BEFORE_ENTER_ROOM",
    "ON_COMMAND_AFTER",
    "ON_COMMAND_BEFORE",
    "ON_DOOR_STATE_CHANGE",
    "ON_DROP",
    "ON_ENTER_ROOM",
    "ON_HEAR_SAY",
    "ON_LEAVE_ROOM",
    "ON_TAKE",
    "ON_TRAVERSE_BLOCKED",
    "Replace",
    "TransferContext",
    "TraverseBlockedContext",
    "canonical_verbs",
    "execute",
    "register",
    "resolve_verb",
    "room_say",
]
