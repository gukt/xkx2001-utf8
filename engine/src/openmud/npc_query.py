"""NPC 查询谓词：ask 候选等共用（消 parsing / commands 重复）。"""

from __future__ import annotations

from openmud.components import Inquiry, NpcSpawnMeta
from openmud.world import EntityId, World


def is_askable_npc(world: World, entity: EntityId) -> bool:
    """可被 ``ask`` 的 NPC：挂 ``Inquiry`` 或 ``NpcSpawnMeta``（排除裸 Position）。

    父 spec D3 原写「同房间 Position」；re-pass 收窄为显式 NPC 标记，避免把
    任意同房 Position 实体（路人甲 decoy）当成可对话对象。见 spec-extension
    「范围修订记录」2026-07-20 条。
    """
    return world.has_component(entity, Inquiry) or world.has_component(entity, NpcSpawnMeta)


__all__ = ["is_askable_npc"]
