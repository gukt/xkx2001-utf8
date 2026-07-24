"""客店房钱状态：离开 HotelRoom 时清除 RentPaid。

复用既有 ``on_leave_room`` 事件点，不新增 hook 协议方法（Polishing-06）。
"""

from __future__ import annotations

from typing import Any

from openmud.components import HotelRoom, RentPaid
from openmud.room_hooks import ON_LEAVE_ROOM
from openmud.world import World


def attach_hotel_rent(world: World) -> None:
    """订阅 ``on_leave_room``：离开客店房时清除玩家 ``RentPaid``（幂等可重复挂）。"""

    def _on_leave(ctx: Any) -> None:
        if world.get_component(ctx.from_room, HotelRoom) is None:
            return
        if world.has_component(ctx.player_id, RentPaid):
            world.remove_component(ctx.player_id, RentPaid)

    world.events.register(ON_LEAVE_ROOM, _on_leave)


__all__ = ["attach_hotel_rent"]
