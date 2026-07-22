"""房间广播：``room_say`` 与 ``on_hear_say`` 事件契约。

从 ``commands`` 抽出，解开 ``ai`` ↔ ``commands`` 循环依赖：Chatter 可在模块
顶部直接 ``from mud_engine.messaging import room_say``，不必在函数体内延迟 import。
``say`` 命令与 NPC Chatter 共用本模块。
"""

from __future__ import annotations

from dataclasses import dataclass

from mud_engine.components import Identity, PlayerSession, Position
from mud_engine.world import EntityId, World

# 房间广播事件（28 号票，D4）：``say`` / Chatter 经 ``room_say`` 触发，
# handler 收 ``HearSayContext``（speaker / room / text）。
ON_HEAR_SAY = "on_hear_say"


@dataclass(frozen=True)
class HearSayContext:
    """``on_hear_say`` 上下文：房间内有人 ``say`` 时触发（28 号票）。

    ``speaker_id`` 是说话者（玩家或 NPC），``room`` 是所在房间，``text`` 是说
    出的内容。形状被契约测试锁定，供 NPC 反应 / 未来对话钩子消费。
    """

    speaker_id: EntityId
    room: EntityId
    text: str


def room_say(world: World, speaker_id: EntityId, text: str) -> list[str]:
    """向同房间广播一句话，并触发 ``on_hear_say``（28 号票）。

    说话者若是玩家，返回 ``你说：...``；同房间其他玩家经各自收件箱收到
    ``{名}说：...``。NPC 说话不返回给自己，只推给房间内玩家会话。
    Chatter（ai.py）与 ``say`` 命令共用本函数。
    """
    room = world.require_component(speaker_id, Position).room
    speaker_name = world.require_component(speaker_id, Identity).name
    world.events.dispatch(
        ON_HEAR_SAY,
        HearSayContext(speaker_id=speaker_id, room=room, text=text),
    )
    speaker_is_player = _is_player_entity(world, speaker_id)
    # 同房间其他玩家收广播（NPC 说话不返回给自己）。遍历走 entities_in_room（34 号票）。
    for entity in world.entities_in_room(room, exclude=speaker_id):
        if _is_player_entity(world, entity):
            world.push_message(entity, f"{speaker_name}说：{text}")
    if speaker_is_player:
        return [f"你说：{text}"]
    return []


def _is_player_entity(world: World, entity: EntityId) -> bool:
    """玩家判定：挂 ``PlayerSession``（US33；28 号票起取代 Container 启发式）。"""
    return world.has_component(entity, PlayerSession)


__all__ = [
    "HearSayContext",
    "ON_HEAR_SAY",
    "room_say",
]
