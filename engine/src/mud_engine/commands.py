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
``on_get``/``on_drop``/``on_door_state_change``），全部空挂复用 07 号票的
``world.events`` 事件总线，M1 默认放行不改现有命令行为。两者层次不同：命令级
钩子看 ``intent``（粗粒度，任何命令）、领域级事件点看领域上下文（细粒度，特定
语义发生时--如"门被打开"由 open/close/unlock 三处收敛到 ``on_door_state_change``
一个事件名）。可否决的 before 事件点复用 08 的 ``Allow``/``Deny``（领域级无
``Replace`` 改写语义）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mud_engine import lookup
from mud_engine.components import (
    DRINK_RESTORE_JINGLI,
    EAT_RESTORE_JINGLI,
    EAT_RESTORE_QI,
    HOTEL_RENT_COST,
    MOUNT_JINGLI_PER_TERRAIN_COST,
    WALK_JINGLI_PER_TERRAIN_COST,
    BaseAttributes,
    BlockExits,
    Consumable,
    Container,
    Currency,
    Description,
    Door,
    Doors,
    DoorState,
    Engaged,
    Exit,
    Exits,
    Faction,
    Ferry,
    HiddenExits,
    HotelRoom,
    Identity,
    Inquiry,
    LibraryRoom,
    LiquidContainer,
    Mount,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    ReadingSession,
    RentPaid,
    Riding,
    RoomDetails,
    RoomFlags,
    RoomHookBinding,
    RoomResources,
    ShopInventory,
    SkillLevels,
    SkillProgress,
    Stackable,
    Terrain,
    Unconscious,
    Valuable,
    Vitals,
    Weight,
)
from mud_engine.death_flow import UNCONSCIOUS_BLOCKED_VERBS
from mud_engine.events import Deny, run_vetoable
from mud_engine.intent import Intent
from mud_engine.library import (
    continue_more,
    find_book,
    format_toc,
    set_reading,
    start_more,
)
from mud_engine.messaging import publish_channel, room_say
from mud_engine.npc_query import is_askable_npc
from mud_engine.quest import accept_quest, try_complete_quest_on_give
from mud_engine.room_details import resolve_detail
from mud_engine.transfer import item_weight, transfer
from mud_engine.world import EntityId, World

CommandHandler = Callable[[World, EntityId, Intent], list[str]]

# 32/33 号票：``Deny`` / ``run_vetoable`` 规范在 ``events``；``ON_GET`` / ``ON_DROP`` /
# ``TransferContext`` 规范在 ``transfer``（消除 transfer -> commands 反向 import）。
# ``Deny`` 仍由本模块再导出：它与 ``Allow`` / ``Replace`` 同属命令钩子三态 API。
# 转移域符号请从 ``mud_engine.transfer`` 导入，不再经本模块空壳转发。

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
ON_BEFORE_LEAVE_ROOM = "on_before_leave_room"
ON_ENTER_ROOM = "on_enter_room"
ON_LEAVE_ROOM = "on_leave_room"
ON_TRAVERSE_BLOCKED = "on_traverse_blocked"
ON_DOOR_STATE_CHANGE = "on_door_state_change"


@dataclass(frozen=True)
class EnterRoomContext:
    """移动事件点上下文：``on_before_enter_room`` / ``on_before_leave_room`` /
    ``on_enter_room`` / ``on_leave_room`` 共用同一形状。

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


# 规范动词 -> 处理函数
_REGISTRY: dict[str, CommandHandler] = {}
# 命令别名 -> 规范动词（供解析器查；新增命令"顺带"就有别名支持）
_ALIASES: dict[str, str] = {}
# 房间动作动词（dig/jump/climb 等）在无关房间的统一拒绝文案（Pre-M4 钩子命令面）。
_ROOM_ACTION_REFUSED = "这里不能这么做。"


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

    # 昏迷态行为限制（M2-17 / to-tickets 决策 4）：至少禁止 attack/flee/go 等行动。
    if (
        world.has_component(player_id, Unconscious)
        and intent.verb in UNCONSCIOUS_BLOCKED_VERBS
    ):
        return ["你昏迷不醒，无法行动。"]

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
    """容器内物品展示名，按名排序（look 地面 / inventory / look 容器内容共用）。

    挂 ``Stackable`` 且 ``amount != 1`` 时附带 ``×数量``（如 ``铜钱×8``），
    便于 ``i`` 直接看到堆叠数，不必再 ``look <物>``。
    """
    labels: list[str] = []
    for item in container.items:
        name = world.require_component(item, Identity).name
        stackable = world.get_component(item, Stackable)
        if stackable is not None and stackable.amount != 1:
            labels.append(f"{name}×{stackable.amount}")
        else:
            labels.append(name)
    return sorted(labels)


def _sorted_npc_names_in_room(world: World, room: EntityId, player_id: EntityId) -> list[str]:
    """同房间内静态展示型 NPC 的规范名，按名排序（look 在场展示用）。

    NPC 用 ``Position`` 表达"在房间里"，不进房间的 ``Container``（否则会被
    take）；玩家也持有 Position，故排除玩家本人。物品无 Position，不会被收进。
    房间内实体遍历走 ``world.entities_in_room``（34 号票去重）。
    """
    names: list[str] = []
    for entity in world.entities_in_room(room, exclude=player_id):
        identity = world.get_component(entity, Identity)
        if identity is not None:
            names.append(identity.name)
    return sorted(names)


@register("look", aliases=("l",))
def _cmd_look(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """无目标：展示当前房间；有目标：实体（物品/NPC）或房间风景 details（Pre-M4-01）。

    房间 look：简述、详细描述、户外时辰/天气（15/17）、地面物品、在场 NPC、出口。
    有目标：解析层已按物品 → NPC 优先；此处再查 details，最后失败提示。
    """
    if intent.target is not None:
        return _look_target(world, player_id, intent)

    room = _player_room(world, player_id)
    description = world.require_component(room, Description)
    exits = world.require_component(room, Exits)

    lines = [description.short, description.long]
    # 户外房间追加当前时辰 × 天气描述（15/17 号票；ADR-0013 按本房贴纸合成）。
    if description.outdoors:
        from mud_engine.nature import outdoor_desc_for_room

        nature_line = outdoor_desc_for_room(world, room)
        if nature_line is not None:
            lines.append(nature_line)
    # 渡口状态现算（M2-09）：不塞进 Description。
    from mud_engine.ferry import ferry_status_line

    ferry_line = ferry_status_line(world, room)
    if ferry_line is not None:
        lines.append(ferry_line)
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

    # NPC 挡向（剧情门）：在查出口之前也可挡已有出口。
    block = world.get_component(room, BlockExits)
    if block is not None:
        entry = block.by_direction.get(direction) if direction else None
        if entry is not None:
            blocker = _find_npc_template_in_room(world, room, entry.npc_template)
            if blocker is not None:
                if entry.deny_message:
                    return [entry.deny_message]
                name = world.require_component(blocker, Identity).name
                return [f"{name}挡住了{direction}方向的去路。"]

    passage = exits.by_direction.get(direction)
    if passage is None:
        # 渡口：船不在此岸时对应方向出口被撤掉；给专用提示（M2-09/25），
        # 避免玩家只看到笼统的「没有出口」。
        ferry = world.get_component(room, Ferry)
        if ferry is not None and direction == ferry.direction:
            return ["渡船不在此岸，过不了河。"]
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

    # 骑乘地形校验（M2-15）：在移动前；不通过则不消耗坐骑精力。
    # 步行精力校验（Polishing-05）：仅非骑乘且挂 Vitals 时；不足则拒走，不引入昏迷。
    riding = world.get_component(player_id, Riding)
    terrain = world.get_component(passage.target, Terrain)
    cost = 1 if terrain is None else terrain.cost
    walk_drain = 0
    if riding is not None:
        mount = world.get_component(riding.mount_id, Mount)
        if mount is not None and cost > mount.ability:
            return ["这地方骑不过去。"]
    else:
        vitals = world.get_component(player_id, Vitals)
        if vitals is not None:
            walk_drain = cost * WALK_JINGLI_PER_TERRAIN_COST
            if vitals.jingli_current < walk_drain:
                return ["你精力不足，走不动了。"]

    # before：先离房否决（迷途等），再进房否决。任一否决则不移动、不触发 enter/leave。
    move_ctx = EnterRoomContext(player_id=player_id, from_room=room, to_room=passage.target)
    leave_denial = run_vetoable(world, ON_BEFORE_LEAVE_ROOM, move_ctx)
    if leave_denial is not None:
        return [leave_denial]
    denial = run_vetoable(world, ON_BEFORE_ENTER_ROOM, move_ctx)
    if denial is not None:
        return [denial]

    # 移动发生。
    position = world.require_component(player_id, Position)
    position.room = passage.target
    riding_line: str | None = None
    fall_line: str | None = None
    riding = world.get_component(player_id, Riding)
    if riding is not None:
        mount_id = riding.mount_id
        mount_pos = world.get_component(mount_id, Position)
        if mount_pos is not None:
            mount_pos.room = passage.target
        mount = world.get_component(mount_id, Mount)
        mount_name = "坐骑"
        mid = world.get_component(mount_id, Identity)
        if mid is not None:
            mount_name = mid.name
        if mount is not None:
            terrain = world.get_component(passage.target, Terrain)
            cost = 1 if terrain is None else terrain.cost
            drain = cost * MOUNT_JINGLI_PER_TERRAIN_COST
            mount.jingli_current = max(0, mount.jingli_current - drain)
            if mount.jingli_current == 0:
                # 人马已到目标房；马倒 → 挂 Unconscious、解除骑乘（摔在目标房）。
                if not world.has_component(mount_id, Unconscious):
                    world.add_component(mount_id, Unconscious())
                mount.ridden_by = None
                world.remove_component(player_id, Riding)
                fall_line = f"{mount_name}精力耗尽，你摔了下来。"
            else:
                riding_line = f"你骑着{mount_name}前行。"
        else:
            riding_line = f"你骑着{mount_name}前行。"
    elif walk_drain > 0:
        vitals = world.require_component(player_id, Vitals)
        vitals.jingli_current -= walk_drain
    # after：先离开旧房间、再进入新房间（对应 LPC move 先 leave 旧环境再 enter 新）。
    # 两者共用 EnterRoomContext 形状，事件名区分语义。fire-and-forget 不短路。
    enter_ctx = EnterRoomContext(player_id=player_id, from_room=room, to_room=passage.target)
    world.events.dispatch(ON_LEAVE_ROOM, enter_ctx)
    world.events.dispatch(ON_ENTER_ROOM, enter_ctx)
    look_lines = _cmd_look(world, player_id, Intent(verb="look", target=None))
    prefix: list[str] = []
    if riding_line is not None:
        prefix.append(riding_line)
    if fall_line is not None:
        prefix.append(fall_line)
    if prefix:
        return [*prefix, *look_lines]
    return look_lines


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
    """解锁当前房间某方向出口上的门（04 号票 + Pre-M4-06 剧情门）。

    锁定门绑定钥匙（``key_item_id``）时，玩家物品栏需持有该钥匙物品才能解锁；
    标准门解锁后门变为关（``CLOSED``），需再 ``open`` 才能通行。
    ``consume_key`` 为真时解锁成功销毁钥匙。``hidden_until_unlocked`` 出口解锁后
    迁入 ``Exits`` 且门直接打开，便于「解锁后可走」。
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
    key_id = door.key_item_id
    if key_id is not None:
        player_container = world.get_component(player_id, Container)
        if player_container is None or key_id not in player_container.items:
            return ["你需要一把匹配的钥匙才能 unlock 那扇门。"]

    hidden = world.get_component(room, HiddenExits)
    is_hidden = hidden is not None and direction in hidden.by_direction
    if is_hidden:
        pending = hidden.by_direction.pop(direction)
        exits = world.require_component(room, Exits)
        exits.by_direction[direction] = Exit(target=pending.target, aliases=pending.aliases)
        _set_door_state(world, player_id, room, direction, door, DoorState.OPEN)
    else:
        _set_door_state(world, player_id, room, direction, door, DoorState.CLOSED)

    if door.consume_key and key_id is not None:
        bag = world.require_component(player_id, Container)
        bag.items.discard(key_id)
        world.destroy_entity(key_id)

    return [f"你解锁了{direction}方向的门。"]


@register("get", aliases=("take",))
def _cmd_get(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """从房间地面或容器取出物品到玩家物品栏（03/19/20/22 号票 + verify 补齐）。

    规范动词 ``get``（对齐 LPC ``cmds/std/get.c``）；``take`` 为别名。

    - ``get <物品>`` / ``get <物品> <数量>``：从当前房间地面拿（可拆堆）。
    - ``get <物品> from <容器>``：从可达容器取出（intent.args 含 ``from`` + 容器名）。
    - ``get all``：地面可拿物品逐件转移（``no_get`` 等失败跳过）。
    全部走 ``transfer``：``on_get`` 否决、no_get、堆叠合并/拆分在原语内处理。
    """
    name = intent.target
    if name is None:
        return ["拿什么？用法：get <物品> [数量] [from <容器>]；或 get all"]
    if name == "all":
        return _cmd_get_all(world, player_id)

    room = _player_room(world, player_id)
    from_container_name, amount = _parse_get_args(intent.args)
    if from_container_name is not None:
        holder = lookup.find_reachable_container(world, player_id, from_container_name)
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

    result = transfer(world, item, src, player_id, player_id=player_id, amount=amount)
    if not result.success:
        return [result.message or "拿不起来。"]
    if amount is not None:
        return [f"你拿起 {amount} 个 {name}。"]
    return [f"你拿起 {name}。"]


def _cmd_get_all(world: World, player_id: EntityId) -> list[str]:
    """``get all``：当前房间地面逐件拿起；失败（no_get 等）跳过，不中断整批。"""
    room = _player_room(world, player_id)
    floor = world.require_component(room, Container)
    items = list(floor.items)
    if not items:
        return ["这里没有任何东西。"]
    got = 0
    for item in items:
        # 转移可能已从 floor 移除；若仍在则再试。
        if item not in floor.items:
            continue
        result = transfer(world, item, room, player_id, player_id=player_id)
        if result.success:
            got += 1
    if got == 0:
        return ["这里没什么可捡的。"]
    return ["捡好了。"]


@register("drop")
def _cmd_drop(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把玩家物品栏里匹配的物品放到当前房间地面（03/19 号票 + verify 补齐）。

    - ``drop <物品>`` / ``drop <物品> <数量>``：可拆堆丢下。
    - ``drop all``：物品栏逐件放下（``no_drop`` 等失败跳过）。
    走 ``transfer``：``on_drop`` 否决、``no_drop``（含自定义提示）在原语内处理。
    """
    name = intent.target
    if name is None:
        return ["放下什么？用法：drop <物品> [数量]；或 drop all"]
    if name == "all":
        return _cmd_drop_all(world, player_id)

    room = _player_room(world, player_id)
    player_container = world.require_component(player_id, Container)
    item = _find_item_in_container(world, player_container, name)
    if item is None:
        return [f"你没有 {name}。"]
    amount: int | None = None
    if intent.args and intent.args[0].isdigit():
        amount = int(intent.args[0])
    result = transfer(world, item, player_id, room, player_id=player_id, amount=amount)
    if not result.success:
        return [result.message or "放不下。"]
    if amount is not None:
        return [f"你放下 {amount} 个 {name}。"]
    return [f"你放下 {name}。"]


def _cmd_drop_all(world: World, player_id: EntityId) -> list[str]:
    """``drop all``：物品栏逐件放下；失败（no_drop 等）跳过，不中断整批。"""
    room = _player_room(world, player_id)
    inv = world.require_component(player_id, Container)
    items = list(inv.items)
    if not items:
        return ["你什么都没带。"]
    dropped = 0
    for item in items:
        if item not in inv.items:
            continue
        result = transfer(world, item, player_id, room, player_id=player_id)
        if result.success:
            dropped += 1
    if dropped == 0:
        return ["没什么可丢的。"]
    return ["放下了。"]


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
    holder = lookup.find_reachable_container(world, player_id, container_name)
    if holder is None:
        return [f"这里没有容器 {container_name}。"]
    if holder == item:
        return ["不能把东西放进它自己。"]
    result = transfer(world, item, player_id, holder, player_id=player_id)
    if not result.success:
        return [result.message or "放不进去。"]
    return [f"你把 {name} 放进了 {container_name}。"]


@register("give")
def _cmd_give(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把背包物品交给同房间 NPC：``give <物品> to <NPC>``。

    玩家互 give 本波不做。目标须带 ``Container``；转移复用 ``transfer``
    （``no_drop`` / 容量 / 重量等既有拒绝语义原样生效）。
    """
    item_name = intent.target
    if item_name is None or not intent.args:
        return ["给什么？用法：give <物品> to <人物>"]
    npc_name = intent.args[0]
    player_container = world.require_component(player_id, Container)
    item = _find_item_in_container(world, player_container, item_name)
    if item is None:
        return [f"你没有 {item_name}。"]
    npc = intent.target_id
    if npc is None or not world.has_component(npc, Identity):
        npc = _find_npc_in_room(world, player_id, npc_name)
    if npc is None:
        return [f"这里没有 {npc_name}。"]
    if world.has_component(npc, PlayerSession):
        return ["不能把东西交给其他玩家。"]
    if not world.has_component(npc, Container):
        return [f"{npc_name}接不过来。"]
    result = transfer(world, item, player_id, npc, player_id=player_id)
    if not result.success:
        return [result.message or "交不出去。"]
    messages = [f"你把 {item_name} 交给了 {npc_name}。"]
    messages.extend(try_complete_quest_on_give(world, player_id, item, npc))
    return messages


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

    解析层已把 NPC 规范名放进 ``intent.target``、topic 放进 ``intent.args[0]``；
    ``target_id`` 有值时优先用实体引用（M2-20 同名消歧）。
    """
    npc_name = intent.target
    if npc_name is None or not intent.args:
        return ["问谁什么？用法：ask <人物> about <话题>"]
    topic = intent.args[0]
    npc = intent.target_id
    if npc is None or not world.has_component(npc, Identity):
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


@register("chat")
def _cmd_chat(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """向 ``chat`` 频道发言（pre-m4-05）：跨房间投给订阅者。空内容拒绝。"""
    text = intent.args[0] if intent.args else ""
    if not text.strip():
        return ["聊什么？用法：chat <内容>"]
    return publish_channel(world, "chat", player_id, text)


@register("quest")
def _cmd_quest(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """任务命令：本波仅 ``quest accept <id>``（pre-m4-06）。"""
    if not intent.args:
        return ["用法：quest accept <任务id>"]
    sub = intent.args[0].lower()
    if sub != "accept":
        return ["用法：quest accept <任务id>"]
    if len(intent.args) < 2:
        return ["接取哪个任务？用法：quest accept <任务id>"]
    return accept_quest(world, player_id, intent.args[1])


@register("status")
def _cmd_status(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """展示气血/内力/精力与四维基础属性（M2-05）。"""
    vitals = world.get_component(player_id, Vitals)
    attrs = world.get_component(player_id, BaseAttributes)
    if vitals is None and attrs is None:
        return ["你还没有角色属性（缺少 Vitals / BaseAttributes 组件）。"]
    lines: list[str] = []
    if vitals is not None:
        lines.append(
            f"气血：{vitals.qi_current}/{vitals.qi_max}　"
            f"内力：{vitals.neili_current}/{vitals.neili_max}　"
            f"精力：{vitals.jingli_current}/{vitals.jingli_max}"
        )
    else:
        lines.append("（未配置气血/内力/精力）")
    if attrs is not None:
        lines.append(
            f"力量：{attrs.str_}　根骨：{attrs.con}　敏捷：{attrs.dex}　智力：{attrs.int_}"
        )
    else:
        lines.append("（未配置基础属性）")
    return lines


@register("skills")
def _cmd_skills(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """展示已学技能等级/经验（M2-05）。"""
    skill_levels = world.get_component(player_id, SkillLevels)
    if skill_levels is None or not skill_levels.levels:
        return ["你还没有学会任何技能。"]
    lines = ["你已学会的技能："]
    for skill_id in sorted(skill_levels.levels):
        progress = skill_levels.levels[skill_id]
        lines.append(f"  {skill_id}：等级 {progress.level}，经验 {progress.exp}")
    return lines


# 商店清单未包含该物品类型时的默认回购折扣（明确策略，非未定义行为）：
# 按 Valuable.value × 0.5 收购。清单内条目用各自 resell_discount。
_DEFAULT_RESELL_DISCOUNT = 0.5


@register("buy")
def _cmd_buy(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """从同房间商店 NPC 购买物品或坐骑（M2-07 / M2-10）。

    坐骑购买机制（M2-10 Comments）：扩展本命令——``ShopEntry.mount_template_key``
    指向 ``world.spawners`` 中带 ``Mount`` 的 NPC 蓝图；扣 ``Currency`` 后
    ``spawn_from_blueprint`` 到玩家当前房间（不进物品栏，立即可 ``ride``）。
    """
    item_name = intent.target or (intent.args[0] if intent.args else None)
    if not item_name:
        return ["买什么？用法：buy <物品|坐骑>"]
    shop_npc = _find_shop_npc(world, player_id)
    if shop_npc is None:
        return ["这里没有商店。"]
    shop = world.require_component(shop_npc, ShopInventory)
    entry = _shop_entry_by_name(world, shop, item_name)
    if entry is None:
        return [f"店里没有「{item_name}」出售。"]

    if entry.mount_template_key:
        return _buy_mount(world, player_id, entry, item_name)

    template = world.item_templates.get(entry.item_template_key or "")
    if template is None:
        return [f"店里没有「{item_name}」出售。"]
    from mud_engine.scene_loader import instantiate_item

    price = (
        entry.price
        if entry.price is not None
        else _template_price(world, entry.item_template_key or "")
    )
    if price is None:
        return [f"「{item_name}」无法计价。"]
    currency = world.get_component(player_id, Currency)
    if currency is None:
        return ["你身上没有钱袋。"]
    if currency.amount < price:
        return [f"银两不足（需要 {price}，你有 {currency.amount}）。"]
    item = instantiate_item(world, entry.item_template_key or "")
    if not world.has_component(shop_npc, Container):
        world.add_component(shop_npc, Container())
    world.require_component(shop_npc, Container).items.add(item)
    result = transfer(world, item, shop_npc, player_id, player_id=player_id)
    if not result.success:
        world.require_component(shop_npc, Container).items.discard(item)
        world.destroy_entity(item)
        return [result.message]
    currency.amount -= price
    return [f"你花了 {price} 两银子买下了{item_name}。"]


def _buy_mount(world: World, player_id: EntityId, entry, item_name: str) -> list[str]:
    from mud_engine.ai import spawn_from_blueprint

    key = entry.mount_template_key
    assert key is not None
    blueprint = world.spawners.get(key)
    if blueprint is None:
        return [f"店里没有「{item_name}」出售。"]
    price = entry.price
    if price is None:
        return [f"「{item_name}」无法计价。"]
    currency = world.get_component(player_id, Currency)
    if currency is None:
        return ["你身上没有钱袋。"]
    if currency.amount < price:
        return [f"银两不足（需要 {price}，你有 {currency.amount}）。"]
    room = _player_room(world, player_id)
    mount = spawn_from_blueprint(world, blueprint, room=room)
    # 新实例尚未被骑乘。
    mount_comp = world.get_component(mount, Mount)
    if mount_comp is not None:
        mount_comp.ridden_by = None
    currency.amount -= price
    name = world.require_component(mount, Identity).name
    return [f"你花了 {price} 两银子买下了{name}。它就在你身边，可以 ride。"]


@register("ride")
def _cmd_ride(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """骑上同房间未被骑乘的坐骑（M2-10）。"""
    mount_name = intent.target or (intent.args[0] if intent.args else None)
    if not mount_name:
        return ["骑什么？用法：ride <坐骑>"]
    if world.has_component(player_id, Riding):
        return ["你已经在骑乘中了。"]
    mount = _find_mount_in_room(world, player_id, mount_name)
    if mount is None:
        return [f"这里没有可骑乘的「{mount_name}」。"]
    mount_comp = world.require_component(mount, Mount)
    if mount_comp.ridden_by is not None:
        return [f"「{mount_name}」已经被骑着了。"]
    mount_comp.ridden_by = player_id
    world.add_component(player_id, Riding(mount_id=mount))
    name = world.require_component(mount, Identity).name
    return [f"你骑上了{name}。"]


@register("unride")
def _cmd_unride(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """下马：清除双向 Riding/Mount.ridden_by，坐骑留在当前房间。"""
    riding = world.get_component(player_id, Riding)
    if riding is None:
        return ["你现在没有在骑马。"]
    mount = riding.mount_id
    world.remove_component(player_id, Riding)
    mount_comp = world.get_component(mount, Mount)
    if mount_comp is not None and mount_comp.ridden_by == player_id:
        mount_comp.ridden_by = None
    name = (
        world.require_component(mount, Identity).name
        if world.get_component(mount, Identity)
        else "坐骑"
    )
    return [f"你从{name}上下来了。"]


@register("sleep")
def _cmd_sleep(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """在房间睡觉恢复气血/精力（Polishing-06）。

    ``RoomFlags.no_sleep_room`` 拒绝；``HotelRoom`` 须先有 ``RentPaid``。
    成功时将 ``qi_current`` / ``jingli_current`` 拉满（内力不变）。
    """
    room = _player_room(world, player_id)
    flags = world.get_component(room, RoomFlags)
    if flags is not None and flags.no_sleep_room:
        return ["这里不适合睡觉。"]
    if world.get_component(room, HotelRoom) is not None:
        if not world.has_component(player_id, RentPaid):
            return ["你还没付房钱，不能在客店睡。先 pay <店小二>。"]
    vitals = world.get_component(player_id, Vitals)
    if vitals is not None:
        vitals.qi_current = vitals.qi_max
        vitals.jingli_current = vitals.jingli_max
    return ["你舒服地睡了一觉，精神好多了。"]


@register("pay")
def _cmd_pay(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """向同房 NPC 付客店房钱：``pay <npc>``（Polishing-06）。

    房间须挂 ``HotelRoom``；扣 ``HOTEL_RENT_COST`` 银两后置 ``RentPaid``。
    已付过则提示无需再付（不重复扣款）。
    """
    npc_name = intent.target
    if npc_name is None:
        return ["付给谁？用法：pay <人物>"]
    room = _player_room(world, player_id)
    if world.get_component(room, HotelRoom) is None:
        return ["这里不是客店，没什么好付的。"]
    npc = intent.target_id
    if npc is None or not world.has_component(npc, Identity):
        npc = _find_npc_in_room(world, player_id, npc_name)
    if npc is None:
        return [f"这里没有 {npc_name}。"]
    if world.has_component(player_id, RentPaid):
        return ["你已经付过房钱了。"]
    currency = world.get_component(player_id, Currency)
    if currency is None or currency.amount < HOTEL_RENT_COST:
        return [f"你的银两不够（房钱 {HOTEL_RENT_COST} 两）。"]
    currency.amount -= HOTEL_RENT_COST
    world.add_component(player_id, RentPaid())
    return [f"你付给{npc_name} {HOTEL_RENT_COST} 两银子作房钱。"]


@register("fill")
def _cmd_fill(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """在有 ``resource.water`` 的房间给液体容器灌水：``fill <容器>``（Polishing-08）。"""
    name = intent.target
    if not name:
        return ["灌什么？用法：fill <容器>"]
    item, err = _inventory_item_or_error(world, player_id, name)
    if err is not None:
        return err
    assert item is not None
    liquid = world.get_component(item, LiquidContainer)
    if liquid is None:
        return [f"「{name}」不能装水。"]
    room = _player_room(world, player_id)
    resources = world.get_component(room, RoomResources)
    if resources is None or not resources.water:
        return ["这里没有水源，没法打水。"]
    if liquid.filled_liquid is not None:
        return [f"「{name}」已经装满了。"]
    liquid.filled_liquid = "water"
    return [f"你把{name}灌满了清水。"]


@register("drink")
def _cmd_drink(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """饮用已灌装容器：一次性恢复精力并清空灌装（Polishing-08；不接 Effect 生命周期）。"""
    name = intent.target
    if not name:
        return ["喝什么？用法：drink <容器>"]
    item, err = _inventory_item_or_error(world, player_id, name)
    if err is not None:
        return err
    assert item is not None
    liquid = world.get_component(item, LiquidContainer)
    if liquid is None:
        return [f"「{name}」不是容器。"]
    if liquid.filled_liquid is None:
        return [f"「{name}」是空的，没什么可喝。"]
    if liquid.filled_liquid != "water":
        return [f"「{name}」里装的不是水，你不想喝。"]
    liquid.filled_liquid = None
    vitals = world.get_component(player_id, Vitals)
    if vitals is not None:
        vitals.jingli_current = min(
            vitals.jingli_max, vitals.jingli_current + DRINK_RESTORE_JINGLI
        )
    return [f"你喝了{name}里的水，精神好些了。"]


@register("eat")
def _cmd_eat(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """进食可消耗物：一次性恢复气血/精力，并按 ``Consumable.uses`` 递减/销毁。"""
    name = intent.target
    if not name:
        return ["吃什么？用法：eat <食物>"]
    item, err = _inventory_item_or_error(world, player_id, name)
    if err is not None:
        return err
    assert item is not None
    consumable = world.get_component(item, Consumable)
    if consumable is None:
        return [f"「{name}」不能吃。"]
    vitals = world.get_component(player_id, Vitals)
    if vitals is not None:
        vitals.qi_current = min(vitals.qi_max, vitals.qi_current + EAT_RESTORE_QI)
        vitals.jingli_current = min(
            vitals.jingli_max, vitals.jingli_current + EAT_RESTORE_JINGLI
        )
    _consume_uses(world, player_id, item)
    return [f"你吃了{name}，觉得好多了。"]


def _inventory_item_or_error(
    world: World, player_id: EntityId, name: str
) -> tuple[EntityId | None, list[str] | None]:
    """在玩家背包按规范名找物品；缺失时返回 ``(None, 错误文案)``。"""
    bag = world.get_component(player_id, Container)
    if bag is None:
        return None, [f"你身上没有「{name}」。"]
    item = _find_item_in_container(world, bag, name)
    if item is None:
        return None, [f"你身上没有「{name}」。"]
    return item, None


def _consume_uses(world: World, holder_id: EntityId, item: EntityId) -> None:
    """递减 ``Consumable.uses``；耗尽则从持有者容器移除并 ``destroy_entity``。

    eat 等命令共用本路径，不另建平行销毁逻辑。
    """
    consumable = world.require_component(item, Consumable)
    consumable.uses -= 1
    if consumable.uses > 0:
        return
    bag = world.get_component(holder_id, Container)
    if bag is not None:
        bag.items.discard(item)
    world.destroy_entity(item)


@register("practice")
def _cmd_practice(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """练习已学会的技能（M2-13）。消耗/经验门槏来自 SkillData。"""
    from mud_engine.skills import SKILLS

    room = _player_room(world, player_id)
    if world.get_component(room, LibraryRoom) is not None:
        return ["这里是读书的地方，还是别练功了。"]
    if world.get_component(room, HotelRoom) is not None:
        return ["这里是客店，还是别练功了。"]

    skill_token = intent.target or (intent.args[0] if intent.args else None)
    if not skill_token:
        return ["练习什么？用法：practice <技能>"]
    skill_levels = world.get_component(player_id, SkillLevels)
    if skill_levels is None or skill_token not in skill_levels.levels:
        return ["你还没学会这个技能。"]
    data = SKILLS.get(skill_token)
    if data is None:
        return [f"技能「{skill_token}」数据缺失。"]
    vitals = world.get_component(player_id, Vitals)
    if vitals is None:
        return ["你现在练不动。"]
    if (
        vitals.neili_current < data.practice_neili_cost
        or vitals.jingli_current < data.practice_jingli_cost
    ):
        return ["你现在练不动（内力或精力不足）。"]
    vitals.neili_current -= data.practice_neili_cost
    vitals.jingli_current -= data.practice_jingli_cost
    progress = skill_levels.levels[skill_token]
    new_exp = progress.exp + data.practice_exp_gain
    new_level = progress.level
    leveled = False
    # 升级：exp 达到当前等级门槏后 level+1，结转剩余 exp（可连升）。
    while data.exp_thresholds:
        idx = min(new_level, len(data.exp_thresholds) - 1)
        need = data.exp_thresholds[idx]
        if need <= 0 or new_exp < need:
            break
        new_exp -= need
        new_level += 1
        leveled = True
    skill_levels.levels[skill_token] = SkillProgress(level=new_level, exp=new_exp)
    lines = [f"你练习了{skill_token}，经验 +{data.practice_exp_gain}。"]
    if leveled:
        lines.append(f"你的{skill_token}升到了 {new_level} 级！")
    return lines


@register("read")
def _cmd_read(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """藏书：``read <缩写|书名|id>`` 选书；``read <章号>`` 付费读章（Pre-M4-04）。"""
    token = intent.target or (intent.args[0] if intent.args else None)
    if not token:
        return ["读什么？用法：read <缩写或书名> 选书；read <章号> 阅读。"]

    room = _player_room(world, player_id)
    lib = world.get_component(room, LibraryRoom)
    if lib is None or not lib.books:
        return ["这里没有可借阅的藏书。"]

    if token.isdigit():
        return _read_chapter(world, player_id, lib, room, int(token))

    book = find_book(lib, token)
    if book is None:
        return [f"书架上没有「{token}」这本书。"]
    set_reading(world, player_id, book_id=book.book_id, room=room)
    n = len(book.chapters)
    return [
        f"你选了《{book.title}》，共 {n} 章，每章 {book.chapter_cost} 两银子。"
        f"输入 read <章号> 阅读。"
    ]


def _read_chapter(
    world: World,
    player_id: EntityId,
    lib: LibraryRoom,
    room: EntityId,
    chapter_no: int,
) -> list[str]:
    session = world.get_component(player_id, ReadingSession)
    if session is None or session.room != room:
        return ["请先用 read <缩写或书名> 选一本书。"]
    book = next((b for b in lib.books if b.book_id == session.book_id), None)
    if book is None:
        return ["你选的书已不在此架上。"]
    if chapter_no < 1 or chapter_no > len(book.chapters):
        return [f"《{book.title}》没有第 {chapter_no} 章（共 {len(book.chapters)} 章）。"]

    currency = world.get_component(player_id, Currency)
    if currency is None:
        return ["你身上没有钱袋。"]
    cost = book.chapter_cost
    if currency.amount < cost:
        return [f"银两不足（需要 {cost}，你有 {currency.amount}）。"]
    currency.amount -= cost

    body = book.chapters[chapter_no - 1]
    body_lines = body.splitlines() or [body]
    header = [f"《{book.title}》第 {chapter_no} 章（付 {cost} 两）："]
    return header + start_more(world, player_id, body_lines)


@register("more")
def _cmd_more(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """继续分页展示（TOC / 章节正文）。"""
    _ = intent
    return continue_more(world, player_id)


@register("learn")
def _cmd_learn(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """向门派技能池学习技能类型（M2-14）：map_skill → skill_pool → learn_condition。"""
    from mud_engine.ai import condition_from_data
    from mud_engine.conditions import evaluate
    from mud_engine.entity_gate import EntityGateContext
    from mud_engine.factions import FACTIONS
    from mud_engine.skills import SKILLS

    skill_type = intent.target or (intent.args[0] if intent.args else None)
    if not skill_type:
        return ["学习什么？用法：learn <技能类型>"]
    faction = world.get_component(player_id, Faction)
    if faction is None or faction.faction_id is None:
        return ["你还没有门派。"]
    definition = FACTIONS.get(faction.faction_id)
    if definition is None:
        return ["你还没有门派。"]
    skill_id = definition.map_skill.get(skill_type)
    if skill_id is None:
        return ["你的门派不会这个。"]
    if skill_id not in definition.skill_pool:
        return [f"「{skill_id}」不在本门技能池内。"]
    data = SKILLS.get(skill_id)
    if data is None:
        return [f"技能「{skill_id}」尚未载入。"]
    skill_levels = world.get_component(player_id, SkillLevels)
    if skill_levels is not None and skill_id in skill_levels.levels:
        return [f"你已经学会了{skill_id}。"]
    # level_req：技能声明的最低等级门槛。MVP 无独立角色等级时，用已学技能
    # 的最高等级代理（皆无则为 0）；具体属性门槏走 learn_condition。
    current_level = 0
    if skill_levels is not None and skill_levels.levels:
        current_level = max(p.level for p in skill_levels.levels.values())
    if current_level < data.level_req:
        return [f"你的等级不够（需要 {data.level_req}，当前 {current_level}）。"]
    gate = EntityGateContext(world, player_id)
    if data.learn_condition is not None:
        cond = condition_from_data(data.learn_condition)
        if cond is not None and not evaluate(cond, gate):
            reason = _learn_deny_reason(cond, gate)
            return [reason]
    if skill_levels is None:
        world.add_component(player_id, SkillLevels(levels={}))
        skill_levels = world.require_component(player_id, SkillLevels)
    skill_levels.levels[skill_id] = SkillProgress(level=1, exp=0)
    return [f"你学会了{skill_id}。"]


def _learn_deny_reason(condition: object, ctx) -> str:
    from mud_engine.conditions import And, Equals, Gte, Or, Predicate

    if isinstance(condition, And):
        for part in condition.parts:
            from mud_engine.conditions import evaluate

            if not evaluate(part, ctx):
                return _learn_deny_reason(part, ctx)
        return "不满足学习条件。"
    if isinstance(condition, Or):
        return "不满足学习条件。"
    if isinstance(condition, Gte):
        actual = getattr(ctx, condition.field, None)
        labels = {
            "con": "根骨",
            "str": "力量",
            "str_": "力量",
            "dex": "敏捷",
            "int": "智力",
            "int_": "智力",
        }
        label = labels.get(condition.field, condition.field)
        return f"你的{label}不够（需要 >= {condition.value!r}，当前 {actual!r}）。"
    if isinstance(condition, Equals):
        actual = getattr(ctx, condition.field, None)
        field = condition.field
        labels = {
            "con": "根骨",
            "str": "力量",
            "str_": "力量",
            "dex": "敏捷",
            "int": "智力",
            "int_": "智力",
        }
        label = labels.get(field, field)
        return f"你的{label}不够（需要 {condition.value!r}，当前 {actual!r}）。"
    if isinstance(condition, Predicate):
        return f"需要满足 {condition.name}"
    return "不满足学习条件。"


@register("sell")
def _cmd_sell(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """把物品卖给同房间商店 NPC（M2-07）。"""
    item_name = intent.target or (intent.args[0] if intent.args else None)
    if not item_name:
        return ["卖什么？用法：sell <物品>"]
    shop_npc = _find_shop_npc(world, player_id)
    if shop_npc is None:
        return ["这里没有商店。"]
    player_bag = world.require_component(player_id, Container)
    item = _find_item_in_container(world, player_bag, item_name)
    if item is None:
        return [f"你身上没有「{item_name}」。"]
    valuable = world.get_component(item, Valuable)
    if valuable is None:
        return [f"「{item_name}」无法出售（没有标价）。"]
    shop = world.require_component(shop_npc, ShopInventory)
    discount = _resell_discount_for_item(world, shop, item)
    payout = int(valuable.value * discount)
    currency = world.get_component(player_id, Currency)
    if currency is None:
        world.add_component(player_id, Currency(amount=0))
        currency = world.require_component(player_id, Currency)
    if not world.has_component(shop_npc, Container):
        world.add_component(shop_npc, Container())
    result = transfer(world, item, player_id, shop_npc, player_id=player_id)
    if not result.success:
        return [result.message]
    currency.amount += payout
    return [f"你卖掉了{item_name}，得到 {payout} 两银子。"]


@register("join")
def _cmd_join(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """加入门派（M2-08）。

    MVP 策略：已有门派归属时允许直接覆盖为新门派（不做"先退出"流程），
    降低早期内容复杂度；换门派的叙事/惩罚留给后续题材包。
    """
    from mud_engine.conditions import evaluate
    from mud_engine.factions import FACTIONS

    faction_token = intent.target or (intent.args[0] if intent.args else None)
    if not faction_token:
        return ["加入哪个门派？用法：join <门派>"]
    # 支持按 id 或 display_name 匹配。
    definition = FACTIONS.get(faction_token)
    if definition is None:
        for entry in FACTIONS.values():
            if entry.display_name == faction_token or entry.faction_id == faction_token:
                definition = entry
                break
    if definition is None:
        return [f"没有叫做「{faction_token}」的门派。"]
    if definition.join_condition is not None:
        ctx = _JoinContext(world, player_id)
        if not evaluate(definition.join_condition, ctx):
            reason = _join_deny_reason(definition.join_condition, ctx)
            return [f"无法加入{definition.display_name}：{reason}"]
    faction = world.get_component(player_id, Faction)
    if faction is None:
        world.add_component(player_id, Faction(faction_id=definition.faction_id))
    else:
        faction.faction_id = definition.faction_id
    return [f"你加入了{definition.display_name}。"]


@register("attack", aliases=("kill",))
def _cmd_attack(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """对同房间目标建立交战（M2-12）。不直接结算伤害；伤害由 on_tick 系统推进。"""
    from mud_engine.combat_system import try_engage

    room = _player_room(world, player_id)
    flags = world.get_component(room, RoomFlags)
    if flags is not None and flags.no_fight:
        return ["这里不能动手打架。"]

    target_name = intent.target or (intent.args[0] if intent.args else None)
    if not target_name and intent.target_id is None:
        return ["攻击谁？用法：attack <目标>"]
    target = intent.target_id
    if target is None or not world.has_component(target, Identity):
        if not target_name:
            return ["攻击谁？用法：attack <目标>"]
        target = _find_combat_target_in_room(world, player_id, target_name)
    if target is None:
        return [f"这里没有「{target_name}」。"]
    err = try_engage(world, player_id, target)
    if err is not None:
        return [err]
    name = world.require_component(target, Identity).name
    return [f"你开始与{name}交战！"]


@register("flee")
def _cmd_flee(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """尝试脱离交战（M2-12）。失败时挨对手一次额外攻击。

    成功概率由 ``world.combat.flee_success_chance`` 控制（可注入 RNG，确定性可测）。
    """
    from mud_engine.combat_system import attach_combat_system, clear_engagement, resolve_one_strike

    engaged = world.get_component(player_id, Engaged)
    if engaged is None:
        return ["你现在没有在交战。"]
    # 命令期防御性兜底：仅当 world.combat 意外为 None 时补挂交战系统。
    # 不走 wire_runtime——那会重挂 nature/AI/渡口/门禁，过重且可能改 RNG；
    # 这不是与 load/restore 并列的第三份接线清单。
    if world.combat is None:
        attach_combat_system(world)
    combat = world.combat
    assert combat is not None
    opponent = engaged.opponent
    if combat.rng.random() < combat.flee_success_chance:
        clear_engagement(world, player_id, reason="flee")
        return ["你成功脱离了交战！"]
    # 失败：对手立即打一记。
    resolve_one_strike(world, opponent, player_id, rng=combat.rng)
    opp_name = (
        world.require_component(opponent, Identity).name
        if world.get_component(opponent, Identity)
        else "对手"
    )
    lines = [f"你试图逃走，但没能甩开{opp_name}！"]
    # 把本回合 pending 战斗播报一并返回给命令调用方。
    if world.pending_messages:
        lines.extend(world.pending_messages)
        world.pending_messages.clear()
    return lines


def _invoke_room_hook_action(
    world: World, player_id: EntityId, method_name: str
) -> list[str]:
    """房间动作动词公共路径：当前房绑定钩子且实现 ``method_name`` 时调用。

    无关房间 / 未实现方法 → 统一「这里不能这么做。」（不是「未知命令」）。
    """
    from mud_engine.room_hooks import RoomHookContext, get_room_hook

    room = _player_room(world, player_id)
    binding = world.get_component(room, RoomHookBinding)
    if binding is None:
        return [_ROOM_ACTION_REFUSED]
    hook = get_room_hook(binding.hook_id)
    if hook is None or not hasattr(hook, method_name):
        return [_ROOM_ACTION_REFUSED]
    method = getattr(hook, method_name)
    ctx = RoomHookContext(
        world,
        room,
        actor_id=player_id,
        params=binding.params,
        tick=world.tick,
    )
    return list(method(ctx))


@register("dig")
def _cmd_dig(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """挖洞：仅在挂了实现 ``on_dig`` 的房间钩子的房间生效（Pre-M4-02）。"""
    return _invoke_room_hook_action(world, player_id, "on_dig")


@register("scrape", aliases=("刮锈",))
def _cmd_scrape(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """刮锈：多步机关第一步（Pre-M4-03）。"""
    return _invoke_room_hook_action(world, player_id, "on_scrape")


@register("pull", aliases=("拔斧",))
def _cmd_pull(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """拔斧：多步机关第二步（Pre-M4-03）。"""
    return _invoke_room_hook_action(world, player_id, "on_pull")


@register("push", aliases=("推门",))
def _cmd_push(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """推门：多步机关第三步，完成后开出口（Pre-M4-03）。"""
    return _invoke_room_hook_action(world, player_id, "on_push")


@register("jump", aliases=("跳",))
def _cmd_jump(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """跳跃：技能门槛机关（Pre-M4-05）。"""
    return _invoke_room_hook_action(world, player_id, "on_jump")


@register("climb", aliases=("爬",))
def _cmd_climb(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """攀爬：技能门槛机关（Pre-M4-05）。"""
    return _invoke_room_hook_action(world, player_id, "on_climb")


def _find_combat_target_in_room(world: World, player_id: EntityId, name: str) -> EntityId | None:
    """同房间按规范名/别名找可交战目标（挂 Identity，通常还挂 Vitals）。"""
    room = _player_room(world, player_id)
    for entity in world.entities_in_room(room, exclude=player_id):
        identity = world.get_component(entity, Identity)
        if identity is None:
            continue
        if identity.name == name or name in identity.aliases:
            return entity
    return None


class _JoinContext:
    """join 命令专用最小 ConditionContext（M2-08；通用 EntityGateContext 见 11 号票）。"""

    def __init__(self, world: World, player_id: EntityId) -> None:
        from mud_engine.nature import nature_snapshot_for_room

        self._world = world
        self._player_id = player_id
        room = world.get_component(player_id, Position)
        room_id = room.room if room is not None else None
        eff = nature_snapshot_for_room(world, room_id)
        self.phase = eff.phase
        self.is_night = eff.is_night
        self.is_day = eff.is_day
        self.is_raining = eff.is_raining
        faction = world.get_component(player_id, Faction)
        self.faction_id = faction.faction_id if faction else None
        self.has_faction = self.faction_id is not None

    def __getattr__(self, name: str) -> object:
        # 允许 join_condition 用 equals 查任意暴露属性；未知属性返回 None。
        return None


def _join_deny_reason(condition: object, ctx: _JoinContext) -> str:
    """尽量给出具体缺什么，而不是笼统"不满足条件"。"""
    from mud_engine.conditions import Equals, Predicate

    if isinstance(condition, Equals):
        actual = getattr(ctx, condition.field, None)
        return f"需要 {condition.field}={condition.value!r}（当前为 {actual!r}）"
    if isinstance(condition, Predicate):
        return f"需要满足 {condition.name}"
    return "不满足加入条件"


def _find_shop_npc(world: World, player_id: EntityId) -> EntityId | None:
    room = _player_room(world, player_id)
    for entity in world.entities_in_room(room, exclude=player_id):
        if world.has_component(entity, ShopInventory):
            return entity
    return None


def _shop_entry_by_name(world: World, shop: ShopInventory, item_name: str):
    """按物品模板名或坐骑蓝图名匹配商店条目。"""
    for entry in shop.entries:
        if entry.mount_template_key:
            blueprint = world.spawners.get(entry.mount_template_key)
            if blueprint is None:
                continue
            if blueprint.name == item_name or item_name in blueprint.aliases:
                return entry
            continue
        if not entry.item_template_key:
            continue
        template = world.item_templates.get(entry.item_template_key)
        if template is None:
            continue
        if str(template.get("name", "")) == item_name:
            return entry
        aliases = template.get("aliases") or ()
        if item_name in {str(a) for a in aliases}:
            return entry
    return None


def _shop_entry_by_item_name(world: World, shop: ShopInventory, item_name: str):
    """兼容旧名。"""
    return _shop_entry_by_name(world, shop, item_name)


def _find_mount_in_room(world: World, player_id: EntityId, name: str) -> EntityId | None:
    room = _player_room(world, player_id)
    for entity in world.entities_in_room(room, exclude=player_id):
        if not world.has_component(entity, Mount):
            continue
        identity = world.get_component(entity, Identity)
        if identity is None:
            continue
        if identity.name == name or name in identity.aliases:
            return entity
    return None


def _template_price(world: World, template_key: str) -> int | None:
    raw = world.item_templates.get(template_key)
    if raw is None:
        return None
    if "valuable" in raw:
        v = raw["valuable"]
        if isinstance(v, dict):
            v = v.get("value")
        try:
            return int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    if "value" in raw:
        try:
            return int(raw["value"])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    return None


def _resell_discount_for_item(world: World, shop: ShopInventory, item: EntityId) -> float:
    """清单内用条目折扣；清单外用 ``_DEFAULT_RESELL_DISCOUNT``（见模块常量注释）。"""
    identity = world.require_component(item, Identity)
    for entry in shop.entries:
        if not entry.item_template_key:
            continue
        template = world.item_templates.get(entry.item_template_key)
        if template is None:
            continue
        if str(template.get("name", "")) == identity.name:
            return entry.resell_discount
    return _DEFAULT_RESELL_DISCOUNT


def _find_npc_in_room(world: World, player_id: EntityId, name: str) -> EntityId | None:
    """在玩家当前房间找规范名等于 name 的可 ask NPC（见 ``npc_query.is_askable_npc``）。

    房间内实体遍历走 ``world.entities_in_room``（34 号票去重）。
    """
    room = _player_room(world, player_id)
    for entity in world.entities_in_room(room, exclude=player_id):
        if not is_askable_npc(world, entity):
            continue
        identity = world.get_component(entity, Identity)
        if identity is not None and identity.name == name:
            return entity
    return None


def _find_npc_template_in_room(
    world: World, room: EntityId, template_key: str
) -> EntityId | None:
    """在房间内找 ``NpcSpawnMeta.template_key`` 匹配的 NPC。"""
    for entity in world.entities_in_room(room):
        meta = world.get_component(entity, NpcSpawnMeta)
        if meta is not None and meta.template_key == template_key:
            return entity
    return None


def _look_target(world: World, player_id: EntityId, intent: Intent) -> list[str]:
    """有目标 look：物品 / NPC（解析层已优先）→ 藏书架 TOC → 房间 details → 失败提示。"""
    name = intent.target
    assert name is not None
    if intent.target_id is not None:
        return _look_entity(world, intent.target_id, name)
    item_lines = _look_item(world, player_id, name)
    if item_lines is not None:
        return item_lines
    room = _player_room(world, player_id)
    lib = world.get_component(room, LibraryRoom)
    if lib is not None and name == lib.shelf_key and lib.books:
        return start_more(world, player_id, format_toc(lib))
    details = world.get_component(room, RoomDetails)
    if details is not None:
        entry = resolve_detail(details, name)
        if entry is not None:
            return [entry.text]
    return [f"这里没有 {name}。"]


def _look_entity(world: World, entity_id: EntityId, name: str) -> list[str]:
    """``look <NPC/实体>``：展示 Description（short/long）。"""
    description = world.get_component(entity_id, Description)
    if description is not None and description.long:
        return [description.long]
    if description is not None and description.short:
        return [description.short]
    identity = world.get_component(entity_id, Identity)
    return [identity.name if identity is not None else name]


def _look_item(world: World, player_id: EntityId, name: str) -> list[str] | None:
    """``look <物品>``：long + 容器内容 + 堆叠/价值/重量；未找到返回 None。"""
    item = _find_lookable_item(world, player_id, name)
    if item is None:
        return None
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
    """在房间地面、玩家物品栏及其直接嵌套容器中按规范名找物品。

    遍历结构走共享的 ``lookup.iter_lookable_containers``（30 号票与 parsing 去重），
    在此基础上做"首个规范名匹配"。``iter_lookable_containers`` 的 holder 分组顺序
    保证结果与原内联遍历一致（直接容器先于其嵌套）。
    """
    for container in lookup.iter_lookable_containers(world, player_id):
        found = _find_item_in_container(world, container, name)
        if found is not None:
            return found
    return None


def _parse_get_args(args: tuple[str, ...]) -> tuple[str | None, int | None]:
    """解析 get 的 args：可选数量 + 可选 ``from <容器>``。

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
    """look 出口列表的单项：中英并列方向名 + 门状态标注（关/锁）。

    十向展示如 ``东(east)``（与 ``directions`` 内置表同源）；非十向键仍显示原键。
    门状态后缀保留在英文键之后：``东(east)（关）``。
    """
    from mud_engine.directions import exit_display_label

    base = exit_display_label(direction)
    door = _door_in_direction(world, room, direction)
    if door is not None and door.state is not DoorState.OPEN:
        suffix = "（锁）" if door.state is DoorState.LOCKED else "（关）"
        return base + suffix
    return base


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
    "ON_BEFORE_ENTER_ROOM",
    "ON_BEFORE_LEAVE_ROOM",
    "ON_COMMAND_AFTER",
    "ON_COMMAND_BEFORE",
    "ON_DOOR_STATE_CHANGE",
    "ON_ENTER_ROOM",
    "ON_LEAVE_ROOM",
    "ON_TRAVERSE_BLOCKED",
    "Replace",
    "TraverseBlockedContext",
    "canonical_verbs",
    "execute",
    "register",
    "resolve_verb",
]
