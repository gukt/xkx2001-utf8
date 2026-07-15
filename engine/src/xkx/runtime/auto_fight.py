"""自动战斗触发机制（阶段 2.4，对照 LPC adm/daemons/combatd.c auto_fight + start_*）。

翻译 LPC ``call_out("start_"+type, 0, me, obj)`` 延迟 0 秒启动语义为 greenfield
单线程 tick 内同步执行 + 防御检查（ADR-0027 §1.2 决策：倾向同步执行，避免
duration=0 EffectComp 的语义复杂度）。

**LPC 源码对照**（combatd.c:852-962）：

- ``auto_fight(me, obj, type)``：NPC vs NPC 跳过（``!userp(me) && !userp(obj)``）+
  ``looking_for_trouble`` 标记防重入 + ``call_out("start_"+type, 0, me, obj)``
- ``start_berserk/hatred/vendetta/aggressive(me, obj)``：开头 4 防御检查
  （``!me||!obj`` / ``is_fighting`` / ``!living`` / ``environment!=environment`` /
  ``no_fight``），通过后执行各自 fight 逻辑（message + kill_ob/fight_ob）

**greenfield 翻译**：

- ``auto_fight``：NPC vs NPC 跳过（用 ``Identity.is_player`` 判定，对齐 LPC
  ``userp``）+ ``looking_for_trouble`` 标记防重入（Marks.flags）+ 同步调
  ``start_fight``（对齐 LPC ``call_out(...,0)`` 延迟 0 秒，greenfield 无异步
  语义，同步执行行为等价）
- ``start_fight``：4 防御检查（me/obj 有效性 / is_fighting / living / 同房间 /
  no_fight），通过后调 ``on_start_fight`` 回调钩子（题材数据/NPC AI 声明，
  后置 M3 填充；2.4 默认 no-op）

**主题无关性**（ADR-0027 §1.3 + ADR-0003）：本模块只承载通用战斗触发语义
（FightType 枚举 + 防御检查 + 回调分发），不含题材特有字面量。具体战斗触发逻辑
（message + kill_ob/fight_ob 等价）由题材数据通过 ``register_start_fight_handler``
注册的回调声明，内核只做分发。

**revive 中断契约**（ADR-0027 §1.2，文档化）：2.2 已实现 revive call_out ->
EffectComp 翻译（``death.unconcious`` 调 ``apply_condition(world,eid,"revive",delay)``
启动 EffectComp，``_revive_trigger`` 到期清 unconscious 标记）。die 中的
``remove_call_out("revive")`` -> ``death.revive(quiet=True)`` -> ``clear_one_condition``
中断 EffectComp（强制安静苏醒，处理昏迷中死亡场景）。中断契约文档化 + 测试见
``tests/test_callout_translation.py``。

[ADR-0027](../../../docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) §1.2 /
[ADR-0003](../../../docs/adr/ADR-0003-combatkernel-theme-neutrality.md) /
[adm/daemons/combatd.c](../../../adm/daemons/combatd.c) auto_fight + start_* /
[feature/damage.c](../../../feature/damage.c) revive call_out
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from xkx.runtime.components import Identity, Marks, Position, RoomComp
from xkx.runtime.ecs import World

# looking_for_trouble 标记（Marks.flags，对照 LPC set_temp("looking_for_trouble")）
LOOKING_FOR_TROUBLE_FLAG = "looking_for_trouble"

# 昏迷/失能标记（对照 death.py，living() 判定用）
UNCONSCIOUS_FLAG = "unconscious"
DISABLED_FLAG = "disabled"


class FightType(Enum):
    """战斗触发类型（通用战斗语义，对照 LPC auto_fight 的 type 参数）。

    非题材特有：berserk（狂暴）/ hatred（仇恨）/ vendetta（宿怨）/ aggressive
    （主动攻击）是通用 RPG 战斗触发分类，题材数据可复用。
    """

    BERSERK = "berserk"
    HATRED = "hatred"
    VENDETTA = "vendetta"
    AGGRESSIVE = "aggressive"


# on_start_fight 回调签名：(world, me_id, obj_id, fight_type) -> None
# 题材数据/NPC AI 声明具体战斗触发逻辑（message + kill_ob/fight_ob 等价），
# 内核只做分发，2.4 默认 no-op（后置 M3 填充）。
StartFightHandler = Callable[[World, int, int, FightType], None]

# FightType -> handler 注册表（2.4）。未注册的 FightType 用默认 no-op handler。
_START_FIGHT_HANDLERS: dict[FightType, StartFightHandler] = {}


def register_start_fight_handler(
    fight_type: FightType, handler: StartFightHandler
) -> None:
    """注册 start_fight 回调（题材数据/NPC AI 声明，2.4）。

    类似 ``conditions.register_condition``：模块加载时由题材数据注册具体 FightType
    的战斗触发逻辑（message + kill_ob/fight_ob 等价）。内核只做分发，不解释
    题材内容（主题无关，ADR-0027 §1.3）。
    """
    _START_FIGHT_HANDLERS[fight_type] = handler


def _default_start_fight_handler(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """默认 no-op handler（2.4 占位，后置 M3 由题材数据填充）。

    greenfield 2.4 不实现具体战斗触发逻辑（kill_ob/fight_ob 等价由 CombatSystem
    承接，后置 M3）。默认 no-op 保证 auto_fight 管线可测试 + 防御检查行为等价
    验证可独立进行。
    """
    return None


def initiate_combat(
    world: World, attacker_id: int, target_id: int, *, to_death: bool, win_threshold: int = 0
) -> None:
    """建立双向敌对关系（B-2 ADR-0039 决策 4，对齐 LPC kill_ob/fight_ob + set_heart_beat(1)）。

    供 ``on_start_fight`` handler（NPC 主动攻击）+ commands ``_start_combat``（玩家发起）
    共用，逻辑下移到本模块避免循环依赖（auto_fight 不导入 commands）。双方
    ``CombatState.enemy_ids`` 互加 + ``is_fighting=True``。``to_death`` 区分 kill/fight，
    ``win_threshold`` 是 fight 模式 qi% 判赢阈值。
    """
    from xkx.runtime.components import CombatState

    for a, b in ((attacker_id, target_id), (target_id, attacker_id)):
        cs = world.get(a, CombatState)
        if cs is None:
            cs = CombatState()
            world.add(a, cs)
        if b not in cs.enemy_ids:
            cs.enemy_ids.append(b)
        cs.is_fighting = True
        cs.to_death = to_death
        cs.win_threshold = win_threshold
        # B-2 ADR-0045：to_death（kill_ob）双向写 killer_ids（对齐 LPC killer 数组）；
        # fight 模式（fight_ob）不写（killer 只记致死目标）。init() 查 is_killing 重触 hatred。
        if to_death and b not in cs.killer_ids:
            cs.killer_ids.append(b)


def aggressive_start_fight_handler(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """AGGRESSIVE 触发的战斗 handler（B-2 ADR-0039 决策 4，对齐 LPC kill_ob）。

    NPC ``attitude=aggressive`` 主动攻击玩家：建立敌对关系（to_death），后续攻击由
    CombatBridge tick 驱动（对齐 LPC heart_beat）。由 ``register_start_fight_handler``
    在 engine/game 初始化时注册。
    """
    initiate_combat(world, me_id, obj_id, to_death=True)


def hatred_start_fight_handler(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """HATRED 触发的战斗 handler（B-2 ADR-0045，对齐 LPC start_hatred kill_ob）。

    NPC 记住要杀的玩家（killer_ids），玩家重入房间时 init() 查 is_killing 重触
    hatred。建立敌对关系（to_death）。与 aggressive handler 实质相同（都 to_death），
    区分仅为 FightType 语义标签（对齐 LPC 三触发 hatred > vendetta > aggressive）。
    """
    initiate_combat(world, me_id, obj_id, to_death=True)


def vendetta_start_fight_handler(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """VENDETTA 触发的战斗 handler（B-2 ADR-0045，对齐 LPC start_vendetta kill_ob）。

    标记式追杀：玩家杀有 vendetta_mark 的 NPC 获 ``vendetta:<mark>`` flag，遇同类
    vendetta_mark NPC 触发。建立敌对关系（to_death）。与 hatred/aggressive handler
    实质相同，区分仅为 FightType 语义标签。
    """
    initiate_combat(world, me_id, obj_id, to_death=True)


# ──────────────────────── auto_fight（战斗触发入口） ────────────────────────


def auto_fight(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """自动战斗触发入口（对照 LPC combatd.c:852 auto_fight）。

    LPC ``auto_fight(me, obj, type)`` 三步：
    1. NPC vs NPC 跳过（``!userp(me) && !userp(obj)``）
    2. ``looking_for_trouble`` 标记防重入（已有标记则跳过）
    3. ``call_out("start_"+type, 0, me, obj)`` 延迟 0 秒启动

    greenfield 翻译（ADR-0027 §1.2 倾向同步执行）：
    1. NPC vs NPC 跳过（``Identity.is_player`` 判定，对齐 ``userp``）
    2. ``looking_for_trouble`` 标记防重入（Marks.flags）
    3. 同步调 ``start_fight``（对齐 ``call_out(...,0)`` 延迟 0 秒，greenfield
       单线程 tick 内同步执行 + 防御检查行为等价）
    """
    # 1. NPC vs NPC 跳过（对齐 LPC !userp(me) && !userp(obj)）
    if not _is_player(world, me_id) and not _is_player(world, obj_id):
        return
    # 2. looking_for_trouble 标记防重入（对齐 LPC query_temp("looking_for_trouble")）
    if _has_flag(world, me_id, LOOKING_FOR_TROUBLE_FLAG):
        return
    _set_flag(world, me_id, LOOKING_FOR_TROUBLE_FLAG)
    # 3. 同步调 start_fight（对齐 LPC call_out("start_"+type, 0, me, obj)）
    start_fight(world, me_id, obj_id, fight_type)


def start_fight(
    world: World, me_id: int, obj_id: int, fight_type: FightType
) -> None:
    """战斗触发执行（对照 LPC combatd.c:869-962 start_berserk/hatred/vendetta/aggressive）。

    LPC ``start_*`` 开头 4 防御检查（任一命中则 return）：
    1. ``!me || !obj``：实体是否仍存在（未变尸体）
    2. ``is_fighting(obj)``：是否已在战斗（CombatState.enemies 含 obj）
    3. ``!living(me)``：me 是否可操作（Marks.flags 不含 unconscious/disabled）
    4. ``environment(me) != environment(obj)``：是否同房间
    5. ``environment(me)->query("no_fight")``：是否和平房

    greenfield 翻译：5 防御检查（LPC 原文 4 条 + no_fight 是同一 if 的第 5 条件，
    本实现拆为独立检查以便分支测试）。通过后清 ``looking_for_trouble`` 标记
    （对齐 LPC ``set_temp("looking_for_trouble", 0)``）+ 调 on_start_fight 回调。
    """
    # 清 looking_for_trouble 标记（对齐 LPC start_* 开头 set_temp("...",0)）
    # 放在防御检查前：LPC start_* 第一行就清标记，无论后续检查是否通过
    _clear_flag(world, me_id, LOOKING_FOR_TROUBLE_FLAG)

    # 1. me/obj 有效性（对齐 LPC !me || !obj）
    if not _entity_exists(world, me_id) or not _entity_exists(world, obj_id):
        return
    # 2. is_fighting（对齐 LPC is_fighting(obj)，CombatState.enemy_ids 含 obj）
    if _is_fighting(world, me_id, obj_id):
        return
    # 3. living（对齐 LPC !living(me)，Marks.flags 不含 unconscious/disabled）
    if not _is_living(world, me_id):
        return
    # 4. 同房间（对齐 LPC environment(me) != environment(obj)）
    if not _same_room(world, me_id, obj_id):
        return
    # 5. no_fight（对齐 LPC environment(me)->query("no_fight")）
    if _is_no_fight_room(world, me_id):
        return
    # 通过防御检查 -> 调 on_start_fight 回调（题材数据声明，2.4 默认 no-op）
    handler = _START_FIGHT_HANDLERS.get(fight_type, _default_start_fight_handler)
    handler(world, me_id, obj_id, fight_type)


# ──────────────────────── 内部辅助 ────────────────────────


def _is_player(world: World, eid: int) -> bool:
    """是否玩家（对齐 LPC userp()）。greenfield 用 Identity.is_player 判定。"""
    identity = world.get(eid, Identity)
    return identity is not None and identity.is_player


def _entity_exists(world: World, eid: int) -> bool:
    """实体是否有效存在（对齐 LPC !me / !obj 判定，对象是否仍存在未变尸体）。

    greenfield：实体有 Identity 组件视为有效（战斗参与者必有 Identity）。
    """
    return world.get(eid, Identity) is not None


def _is_fighting(world: World, me_id: int, obj_id: int) -> bool:
    """是否已在战斗 obj（对齐 LPC is_fighting(obj)）。

    greenfield：CombatState.enemy_ids 含 obj_id 视为已在战斗。
    """
    from xkx.runtime.components import CombatState

    cs = world.get(me_id, CombatState)
    if cs is None:
        return False
    return obj_id in cs.enemy_ids


def _is_living(world: World, eid: int) -> bool:
    """对象是否可操作（对齐 LPC living()，!disable_player）。

    复用 death.py 的 _is_living 模式：Marks.flags 不含 unconscious/disabled。
    """
    marks = world.get(eid, Marks)
    if marks is None:
        return True
    return UNCONSCIOUS_FLAG not in marks.flags and DISABLED_FLAG not in marks.flags


def _same_room(world: World, me_id: int, obj_id: int) -> bool:
    """是否同房间（对齐 LPC environment(me) != environment(obj)）。"""
    me_pos = world.get(me_id, Position)
    obj_pos = world.get(obj_id, Position)
    if me_pos is None or obj_pos is None:
        return False
    return me_pos.room_id == obj_pos.room_id


def _is_no_fight_room(world: World, me_id: int) -> bool:
    """me 所在房间是否禁止战斗（对齐 LPC environment(me)->query("no_fight")）。

    复用 death.py 的 _get_room 模式：按 room_id 线性扫描 RoomComp。
    """
    pos = world.get(me_id, Position)
    if pos is None:
        return False
    room = _get_room(world, pos.room_id)
    return room is not None and room.no_fight


def _get_room(world: World, room_id: str) -> RoomComp | None:
    """按 room_id 找 RoomComp（线性扫描，房间数有限，复用 death.py 模式）。"""
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    return None


def _has_flag(world: World, eid: int, flag: str) -> bool:
    """是否含 Marks 标记（对照 LPC query_temp）。"""
    marks = world.get(eid, Marks)
    return marks is not None and flag in marks.flags


def _set_flag(world: World, eid: int, flag: str) -> None:
    """设 Marks 标记（对照 LPC set_temp）。"""
    marks = world.get(eid, Marks)
    if marks is None:
        marks = Marks()
        world.add(eid, marks)
    marks.flags.add(flag)


def _clear_flag(world: World, eid: int, flag: str) -> None:
    """清 Marks 标记（对照 LPC set_temp("...",0)）。"""
    marks = world.get(eid, Marks)
    if marks is not None:
        marks.flags.discard(flag)
