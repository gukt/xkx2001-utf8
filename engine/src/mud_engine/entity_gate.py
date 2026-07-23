"""实体门槏：EntityGateContext + EntryGuard on_before_enter_room（M2-11 / spec E2）。

``EntityGateContext`` 实现 ``ConditionContext``，与 ``NatureState`` 同构。
条件节点复用 ``condition_from_data`` / ``evaluate``（属性数值门槏可走
M2-14 增补的 ``Gte``，与 Equals/Predicate 同属受限 AST）。
``attach_entry_guards`` 注册内置订阅者（幂等）。
事件名字符串与 ``commands.ON_BEFORE_ENTER_ROOM`` 对齐，本模块不 import commands
（避免循环依赖）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mud_engine.ai import condition_from_data
from mud_engine.components import (
    BaseAttributes,
    Container,
    EntryGuard,
    Faction,
    Gender,
    ItemTags,
)
from mud_engine.conditions import evaluate
from mud_engine.events import Deny

if TYPE_CHECKING:
    from mud_engine.world import EntityId, World
else:
    from mud_engine.world import EntityId, World

ON_BEFORE_ENTER_ROOM = "on_before_enter_room"

# 持械判定标签：与少林山门等内容票约定 ``edged`` 表示刃器。
EDGED_TAG = "edged"


class EntityGateContext:
    """从实体现算的只读门槏快照（非活组件引用）。

    除协议字段外，另暴露 ``str_``/``con``/``dex``/``int_``/``has_faction``，
    供 learn 门槏（M2-14）用 ``Equals`` 查询，无需再扩协议。

    Nature 读数按 ``room_id``（缺省为实体当前房）合成房间贴纸（ADR-0013）。
    """

    def __init__(
        self,
        world: World,
        entity_id: EntityId,
        *,
        room_id: EntityId | None = None,
    ) -> None:
        from mud_engine.components import Position
        from mud_engine.nature import resolve_effective_nature

        if room_id is None:
            pos = world.get_component(entity_id, Position)
            room_id = pos.room if pos is not None else None
        eff = resolve_effective_nature(world, room_id)
        if eff is None:
            self.phase = "day"
            self.is_night = False
            self.is_day = True
            self.is_raining = False
        else:
            self.phase = eff.phase
            self.is_night = eff.is_night
            self.is_day = eff.is_day
            self.is_raining = eff.is_raining

        faction = world.get_component(entity_id, Faction)
        self.faction_id = faction.faction_id if faction else None
        self.has_faction = self.faction_id is not None

        gender = world.get_component(entity_id, Gender)
        self.gender = gender.value if gender else None

        self.is_wielding_edged_weapon = _is_wielding_edged(world, entity_id)

        attrs = world.get_component(entity_id, BaseAttributes)
        self.str_ = attrs.str_ if attrs else 0
        self.con = attrs.con if attrs else 0
        self.dex = attrs.dex if attrs else 0
        self.int_ = attrs.int_ if attrs else 0
        # 别名：YAML/条件里可用 str / int（避开 Python 关键字字段名）
        self.str = self.str_
        self.int = self.int_


def _is_wielding_edged(world: World, entity_id: EntityId) -> bool:
    bag = world.get_component(entity_id, Container)
    if bag is None:
        return False
    for item in bag.items:
        tags = world.get_component(item, ItemTags)
        if tags is not None and EDGED_TAG in tags.tags:
            return True
    return False


def attach_entry_guards(world: World) -> None:
    """注册 EntryGuard 的 on_before_enter_room 订阅者（幂等）。

    用 ``world._entry_guard_attached`` 哨兵：handler 是闭包，无法靠函数 identity 去重。
    """
    if getattr(world, "_entry_guard_attached", False):
        return

    def _handler(ctx: Any) -> Deny | None:
        guard = world.get_component(ctx.to_room, EntryGuard)
        if guard is None:
            return None
        condition = condition_from_data(guard.condition)
        if condition is None:
            # 配置损坏时 fail-closed，避免门禁失效静默放行。
            return Deny(guard.deny_message)
        # 门禁挂在目标房：用 to_room 贴纸合成昼夜/雨（ADR-0013）。
        gate = EntityGateContext(world, ctx.player_id, room_id=ctx.to_room)
        if not evaluate(condition, gate):
            return Deny(guard.deny_message)
        return None

    world.events.register(ON_BEFORE_ENTER_ROOM, _handler)
    world._entry_guard_attached = True  # noqa: SLF001


__all__ = [
    "EDGED_TAG",
    "EntityGateContext",
    "ON_BEFORE_ENTER_ROOM",
    "attach_entry_guards",
]
