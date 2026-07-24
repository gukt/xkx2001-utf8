"""声明式 Quest：接取 / 交物完成 / 旗标完成（pre-m4-06）。

场景 YAML ``quests.<id>`` 加载为 ``QuestDef`` 挂在 ``world.quests``（纯内存、
不进存档）。玩家进度在 ``QuestProgress`` 组件，进存档。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from openmud.components import (
    Container,
    Currency,
    ItemSpawnMeta,
    ItemTemplateKey,
    NpcSpawnMeta,
    Position,
    QuestProgress,
)

if TYPE_CHECKING:
    from openmud.world import EntityId, World
else:
    from openmud.world import EntityId, World

QUEST_ACTIVE = "active"
QUEST_COMPLETED = "completed"


@dataclass(frozen=True)
class QuestDef:
    """单条声明式任务（场景加载后只读）。"""

    quest_id: str
    name: str
    require_npc: str | None = None
    give_item: str | None = None
    to_npc: str | None = None
    required_flags: frozenset[tuple[str, bool]] = frozenset()
    reward_currency: int = 0
    accept_message: str | None = None
    complete_message: str | None = None


def ensure_quest_progress(world: World, player_id: EntityId) -> QuestProgress:
    """取或创建玩家 ``QuestProgress``。"""
    progress = world.get_component(player_id, QuestProgress)
    if progress is None:
        progress = QuestProgress()
        world.add_component(player_id, progress)
    return progress


def accept_quest(world: World, player_id: EntityId, quest_id: str) -> list[str]:
    """接取任务：校验同房 NPC 等条件；失败不改状态。"""
    quest = world.quests.get(quest_id)
    if quest is None:
        return [f"没有名为 {quest_id} 的任务。"]
    progress = ensure_quest_progress(world, player_id)
    status = progress.quests.get(quest_id)
    if status == QUEST_ACTIVE:
        return [f"任务「{quest.name}」已在进行中。"]
    if status == QUEST_COMPLETED:
        return [f"任务「{quest.name}」已经完成过了。"]
    if quest.require_npc is not None:
        if not _same_room_npc_template(world, player_id, quest.require_npc):
            return [f"无法接取「{quest.name}」：需要与相关人物同处一室。"]
    progress.quests[quest_id] = QUEST_ACTIVE
    if quest.accept_message:
        return [quest.accept_message]
    return [f"你接取了任务「{quest.name}」。"]


def try_complete_quest_on_give(
    world: World,
    player_id: EntityId,
    item_id: EntityId,
    npc_id: EntityId,
) -> list[str]:
    """give 成功后的结算钩子：命中交物完成条件则完成任务、发奖、销毁物品。"""
    item_key = _item_template_key(world, item_id)
    npc_meta = world.get_component(npc_id, NpcSpawnMeta)
    if item_key is None or npc_meta is None:
        return []
    progress = world.get_component(player_id, QuestProgress)
    if progress is None:
        return []
    for quest_id, status in list(progress.quests.items()):
        if status != QUEST_ACTIVE:
            continue
        quest = world.quests.get(quest_id)
        if quest is None or quest.give_item is None or quest.to_npc is None:
            continue
        if item_key != quest.give_item:
            continue
        if npc_meta.template_key != quest.to_npc:
            continue
        return _complete_quest(world, player_id, quest, consume_item=(item_id, npc_id))
    return []


def _item_template_key(world: World, item_id: EntityId) -> str | None:
    """按模板键识别物品：优先 ``ItemTemplateKey``，回退 ``ItemSpawnMeta``。"""
    ref = world.get_component(item_id, ItemTemplateKey)
    if ref is not None:
        return ref.key
    meta = world.get_component(item_id, ItemSpawnMeta)
    return meta.template_key if meta is not None else None


def set_quest_flag(
    world: World, player_id: EntityId, flag: str, value: bool = True
) -> list[str]:
    """设置玩家旗标，并尝试完成依赖该旗标的进行中任务。"""
    progress = ensure_quest_progress(world, player_id)
    progress.flags[flag] = value
    messages: list[str] = []
    for quest_id, status in list(progress.quests.items()):
        if status != QUEST_ACTIVE:
            continue
        quest = world.quests.get(quest_id)
        if quest is None or not quest.required_flags:
            continue
        if quest.give_item is not None:
            # 交物任务不以旗标单独结算（本波：旗标完成类型与交物互斥优先交物钩子）。
            continue
        if _flags_satisfied(progress, quest):
            messages.extend(_complete_quest(world, player_id, quest))
    return messages


def _flags_satisfied(progress: QuestProgress, quest: QuestDef) -> bool:
    for key, expected in quest.required_flags:
        if progress.flags.get(key) != expected:
            return False
    return bool(quest.required_flags)


def _complete_quest(
    world: World,
    player_id: EntityId,
    quest: QuestDef,
    *,
    consume_item: tuple[EntityId, EntityId] | None = None,
) -> list[str]:
    progress = ensure_quest_progress(world, player_id)
    progress.quests[quest.quest_id] = QUEST_COMPLETED
    if consume_item is not None:
        item_id, holder_id = consume_item
        holder = world.get_component(holder_id, Container)
        if holder is not None:
            holder.items.discard(item_id)
        world.destroy_entity(item_id)
    if quest.reward_currency:
        currency = world.get_component(player_id, Currency)
        if currency is None:
            currency = Currency(amount=0)
            world.add_component(player_id, currency)
        currency.amount += quest.reward_currency
    if quest.complete_message:
        return [quest.complete_message]
    if quest.reward_currency:
        return [f"你完成了任务「{quest.name}」，获得 {quest.reward_currency} 两银子。"]
    return [f"你完成了任务「{quest.name}」。"]


def _same_room_npc_template(world: World, player_id: EntityId, template_key: str) -> bool:
    room = world.require_component(player_id, Position).room
    for entity in world.entities_in_room(room, exclude=player_id):
        meta = world.get_component(entity, NpcSpawnMeta)
        if meta is not None and meta.template_key == template_key:
            return True
    return False


__all__ = [
    "QUEST_ACTIVE",
    "QUEST_COMPLETED",
    "QuestDef",
    "accept_quest",
    "ensure_quest_progress",
    "set_quest_flag",
    "try_complete_quest_on_give",
]
