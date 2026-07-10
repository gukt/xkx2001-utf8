"""最小 ECS（S1）：dict 存储。

``entity_id(int) -> {comp_type: comp}``。SparseSet + Archetype 后置（01 子系统3）。
S1 只提供 create/query/attach/detach/按组件/按房间查询。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class World:
    def __init__(self) -> None:
        self._entities: dict[int, dict[type, Any]] = {}
        self._next_id: int = 1

    def new_entity(self) -> int:
        eid = self._next_id
        self._next_id += 1
        self._entities[eid] = {}
        return eid

    def add(self, eid: int, comp: Any) -> None:
        self._entities.setdefault(eid, {})[type(comp)] = comp

    def get(self, eid: int, comp_type: type) -> Any | None:
        return self._entities.get(eid, {}).get(comp_type)

    def has(self, eid: int, comp_type: type) -> bool:
        return comp_type in self._entities.get(eid, {})

    def remove(self, eid: int, comp_type: type) -> None:
        self._entities.get(eid, {}).pop(comp_type, None)

    def entities_with(self, *comp_types: type) -> Iterator[int]:
        for eid, comps in self._entities.items():
            if all(ct in comps for ct in comp_types):
                yield eid

    def entities_in_room(self, room_id: str) -> Iterator[int]:
        from xkx.runtime.components import Position

        for eid in self.entities_with(Position):
            pos = self.get(eid, Position)
            if pos and pos.room_id == room_id:
                yield eid
