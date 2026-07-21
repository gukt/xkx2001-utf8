"""物品转移统一原语（19–24 号票）。

take / drop / put / take-from 全部收敛到 ``transfer(world, item, src, dst)``：
校验标志位、容量/重量、分发 ``on_get`` / ``on_drop`` 否决钩子、堆叠合并与拆分。
命令层只负责解析目标与把 ``TransferResult`` 翻译成玩家提示。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum

from mud_engine.components import (
    Container,
    Identity,
    ItemFlags,
    Stackable,
    Weight,
)
from mud_engine.events import run_vetoable
from mud_engine.world import EntityId, World


class TransferFailReason(StrEnum):
    """转移失败原因枚举（契约测试锁定；命令层按 reason 选默认文案）。

    ``StrEnum`` 成员既是枚举又是字符串值，``reason == "no_get"`` 与
    ``reason == TransferFailReason.NO_GET`` 等价（``TransferResult.reason``
    类型仍为 ``str | None``，比较/存档无回归）。
    """

    NO_GET = "no_get"
    NO_DROP = "no_drop"
    OVER_CAPACITY = "over_capacity"
    OVER_WEIGHT = "over_weight"
    NOT_FOUND = "not_found"
    DENIED = "denied"
    INVALID_AMOUNT = "invalid_amount"
    SAME_CONTAINER = "same_container"


@dataclass(frozen=True)
class TransferResult:
    """转移结果：成功或失败原因 + 可选玩家提示。

    ``reason`` / ``message`` 在成功时为 ``None``；失败时 ``reason`` 为
    ``TransferFailReason`` 常量之一，``message`` 为可直接展示的提示（含
    ``no_drop`` 自定义文案）。形状被契约测试锁定。
    """

    success: bool
    reason: str | None = None
    message: str | None = None


# 转移事件点事件名（09 号票）：挂在 ``world.events`` 上。``on_get`` / ``on_drop``
# 在物品进入 / 离开玩家持有时触发，handler 收 ``TransferContext``、返回 ``Deny``
# 可否决（``events.run_vetoable`` 聚合）。32 号票从 commands 移至 transfer：这些是
# 转移域事件，由 ``transfer()`` 触发，归 transfer 模块（原住 commands 导致 transfer
# 反向 import commands 成循环依赖）。
ON_GET = "on_get"
ON_DROP = "on_drop"


@dataclass(frozen=True)
class TransferContext:
    """``on_get`` / ``on_drop`` 上下文：物品转移前触发，可否决。

    ``src``/``dst`` 是持有容器的 entity id（take: src=房间, dst=玩家；drop:
    src=玩家, dst=房间；未来 put/give 的 src/dst 是箱子 / 其他 NPC）。全 EntityId
    无 mutable 引用，形状直接喂给 ``transfer()``（spec 块 A user story 23）。
    """

    player_id: EntityId
    item: EntityId
    src: EntityId
    dst: EntityId


def item_weight(world: World, item: EntityId) -> float:
    """物品当前重量：Stackable 用 ``unit_weight * amount``，否则用 ``Weight.value``，皆无则 0。"""
    stackable = world.get_component(item, Stackable)
    if stackable is not None:
        return float(stackable.unit_weight) * int(stackable.amount)
    weight = world.get_component(item, Weight)
    if weight is not None:
        return float(weight.value)
    return 0.0


def container_total_weight(world: World, container: Container) -> float:
    """容器内全部物品的重量之和。"""
    return sum(item_weight(world, item) for item in container.items)


def transfer(
    world: World,
    item: EntityId,
    src: EntityId,
    dst: EntityId,
    *,
    player_id: EntityId | None = None,
    amount: int | None = None,
) -> TransferResult:
    """把物品（或其堆叠的一部分）从 ``src`` 容器转移到 ``dst`` 容器。

    - ``amount`` 为 ``None`` 或等于全部时整件转移；小于堆叠数时拆分新实体再转移。
    - 目标已有同名 ``Stackable`` 时合并 amount（不占新槽位）。
    - src=涉及玩家离开 / dst=进入玩家时分别触发 ``on_drop`` / ``on_get`` 否决钩子。
    - ``no_get`` / ``no_drop`` / 容量 / 重量在钩子之前校验。
    """
    if src == dst:
        return TransferResult(
            success=False,
            reason=TransferFailReason.SAME_CONTAINER,
            message="已经在那里了。",
        )
    # 防嵌套循环：dst 在 item 的容器链里时（如 put A in B 而 B 已在 A 内）拒绝，
    # 否则 A 与 B 互含成不可达循环，物品永久丢失且 container_total_weight 递归爆栈。
    if _is_descendant(world, item, dst):
        return TransferResult(
            success=False,
            reason=TransferFailReason.SAME_CONTAINER,
            message="不能把东西放进它自己或它的内容物里。",
        )

    src_container = world.get_component(src, Container)
    dst_container = world.get_component(dst, Container)
    if src_container is None or item not in src_container.items:
        return TransferResult(
            success=False,
            reason=TransferFailReason.NOT_FOUND,
            message="找不到那件物品。",
        )
    if dst_container is None:
        return TransferResult(
            success=False,
            reason=TransferFailReason.NOT_FOUND,
            message="那里装不下东西。",
        )

    stackable = world.get_component(item, Stackable)
    move_amount = _resolve_move_amount(stackable, amount)
    if isinstance(move_amount, TransferResult):
        return move_amount

    flags = world.get_component(item, ItemFlags)
    # 进入玩家持有 → no_get；离开玩家持有 → no_drop（put 也算离开玩家）。
    entering_player = player_id is not None and dst == player_id
    leaving_player = player_id is not None and src == player_id
    if entering_player and flags is not None and flags.no_get:
        return TransferResult(
            success=False,
            reason=TransferFailReason.NO_GET,
            message="那东西拿不起来。",
        )
    if leaving_player and flags is not None and flags.no_drop:
        msg = flags.no_drop_message or "那东西不能丢下。"
        return TransferResult(
            success=False,
            reason=TransferFailReason.NO_DROP,
            message=msg,
        )

    # 拆分时实际进入目标的是新实体；合并时不增加槽位数。先算"将放入目标的实体"
    # 与"将增加的重量"，再做容量/重量校验。
    will_merge = _find_merge_target(world, dst_container, item) is not None
    split = stackable is not None and move_amount is not None and move_amount < stackable.amount
    # 整堆转移且合并 → 不占新槽；拆分后合并 → 不占新槽；否则占 1 槽（除非目标已有该实体，不会）。
    needs_new_slot = not will_merge
    added_weight = _transfer_weight(world, item, move_amount)

    capacity_fail = _check_capacity(dst_container, needs_new_slot=needs_new_slot)
    if capacity_fail is not None:
        return capacity_fail
    weight_fail = _check_weight(world, dst_container, added_weight)
    if weight_fail is not None:
        return weight_fail

    # 否决钩子：进入玩家 → on_get；离开玩家 → on_drop（与 take/drop 基线一致）。
    # ON_GET/ON_DROP/TransferContext 本模块定义（32 号票从 commands 移出，消除
    # transfer -> commands 反向 import）；run_vetoable 来自 events（33 号票与
    # commands._run_vetoable 共用的单一聚合实现，原 transfer._run_transfer_veto 删除）。
    if player_id is not None:
        if entering_player:
            denial = run_vetoable(
                world,
                ON_GET,
                TransferContext(player_id=player_id, item=item, src=src, dst=dst),
            )
            if denial is not None:
                return TransferResult(
                    success=False, reason=TransferFailReason.DENIED, message=denial
                )
        if leaving_player:
            denial = run_vetoable(
                world,
                ON_DROP,
                TransferContext(player_id=player_id, item=item, src=src, dst=dst),
            )
            if denial is not None:
                return TransferResult(
                    success=False, reason=TransferFailReason.DENIED, message=denial
                )

    # 执行转移（拆分 / 合并 / 整件）。
    moving = item
    if split:
        assert stackable is not None and move_amount is not None
        moving = _split_stack(world, item, move_amount)
        # 拆出的新实体尚不在任何容器；源堆已减量仍留在 src。
    else:
        src_container.items.discard(item)

    merge_into = _find_merge_target(world, dst_container, moving)
    if merge_into is not None:
        dest_stack = world.require_component(merge_into, Stackable)
        src_stack = world.require_component(moving, Stackable)
        dest_stack.amount += src_stack.amount
        # 被合并的实体不再被任何容器引用，组件保留无害（M1 不回收 entity）。
        if moving in src_container.items:
            src_container.items.discard(moving)
    else:
        dst_container.items.add(moving)

    return TransferResult(success=True)


def _resolve_move_amount(
    stackable: Stackable | None, amount: int | None
) -> int | None | TransferResult:
    """校验并规范化拆分数量；返回 None 表示整件移动，int 表示移动数量，或失败结果。"""
    if amount is None:
        return None
    if amount <= 0:
        return TransferResult(
            success=False,
            reason=TransferFailReason.INVALID_AMOUNT,
            message="数量无效。",
        )
    if stackable is None:
        if amount != 1:
            return TransferResult(
                success=False,
                reason=TransferFailReason.INVALID_AMOUNT,
                message="那东西不能按数量拆分。",
            )
        return None
    if amount > stackable.amount:
        return TransferResult(
            success=False,
            reason=TransferFailReason.INVALID_AMOUNT,
            message=f"这里没有那么多（只有 {stackable.amount}）。",
        )
    if amount == stackable.amount:
        return None  # 整堆
    return amount


def _transfer_weight(world: World, item: EntityId, move_amount: int | None) -> float:
    """本次转移将带入目标的重量。"""
    stackable = world.get_component(item, Stackable)
    if stackable is not None and move_amount is not None:
        return float(stackable.unit_weight) * int(move_amount)
    return item_weight(world, item)


def _check_capacity(container: Container, *, needs_new_slot: bool) -> TransferResult | None:
    if not needs_new_slot or container.max_capacity is None:
        return None
    if len(container.items) + 1 > container.max_capacity:
        return TransferResult(
            success=False,
            reason=TransferFailReason.OVER_CAPACITY,
            message="那里已经装不下更多东西了。",
        )
    return None


def _check_weight(world: World, container: Container, added_weight: float) -> TransferResult | None:
    if container.max_weight is None:
        return None
    total = container_total_weight(world, container) + added_weight
    if total > container.max_weight + 1e-9:
        return TransferResult(
            success=False,
            reason=TransferFailReason.OVER_WEIGHT,
            message="太重了，放不进去。",
        )
    return None


def _find_merge_target(world: World, container: Container, item: EntityId) -> EntityId | None:
    """目标容器里可与 ``item`` 合并的同名 Stackable（不含 item 自身）。"""
    if world.get_component(item, Stackable) is None:
        return None
    name = world.require_component(item, Identity).name
    for other in container.items:
        if other == item:
            continue
        if world.get_component(other, Stackable) is None:
            continue
        if world.require_component(other, Identity).name == name:
            return other
    return None


def _is_descendant(world: World, ancestor: EntityId, candidate: EntityId) -> bool:
    """``candidate`` 是否在 ``ancestor`` 的容器链里（含多层嵌套）。

    防 ``put A in B`` 而 ``B`` 已在 ``A`` 内时成互含循环：物品永久丢失且
    ``container_total_weight`` 递归会爆栈。M1 嵌套浅，递归深度可控。
    """
    container = world.get_component(ancestor, Container)
    if container is None:
        return False
    for child in container.items:
        if child == candidate:
            return True
        if _is_descendant(world, child, candidate):
            return True
    return False


def _split_stack(world: World, item: EntityId, amount: int) -> EntityId:
    """从堆叠物品拆出 ``amount`` 件为新实体；源堆 amount 递减。新实体尚未入任何容器。"""
    source_stack = world.require_component(item, Stackable)
    source_stack.amount -= amount
    new_item = world.create_entity()
    for _component_type, component in world.components_of(item):
        world.add_component(new_item, _clone_component(component))
    new_stack = world.require_component(new_item, Stackable)
    new_stack.amount = amount
    return new_item


def _clone_component(component: object) -> object:
    """浅拷贝 dataclass 组件；可变字段（如 set）深拷一份，避免与源实体共享。"""
    if is_dataclass(component) and not isinstance(component, type):
        kwargs = {}
        for f in fields(component):
            value = getattr(component, f.name)
            if isinstance(value, set):
                kwargs[f.name] = set(value)
            elif isinstance(value, (list, dict)):
                kwargs[f.name] = copy.copy(value)
            else:
                kwargs[f.name] = value
        return type(component)(**kwargs)
    return copy.copy(component)


__all__ = [
    "ON_DROP",
    "ON_GET",
    "TransferContext",
    "TransferFailReason",
    "TransferResult",
    "container_total_weight",
    "item_weight",
    "transfer",
]
