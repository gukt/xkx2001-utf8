"""ECS SparseSet 存储（阶段 1 T1，ADR-0017）。

每个组件类型一个 SparseSet（dense + sparse），查询某类型所有组件 O(count)。
API 对齐阶段 -1 dict 版本（``new_entity``/``add``/``get``/``has``/``remove``/
``entities_with``/``entities_in_room``），调用方无感迁移。

阶段 -1 S1 用 dict 存储（``entity_id -> {comp_type: comp}``）；阶段 1 T1 升级
为 SparseSet，因 1000 实体 + 多 System 每 tick 查询下 dict 的 O(total) 遍历会
放大开销。Archetype 后置（T10 压测发现瓶颈才评估，
[ADR-0017](../../../docs/adr/ADR-0017-ecs-sparse-set-effect-component.md) §1）。

T2（ADR-0019）：``World`` 可选注入 ``SchemaRegistry``，``get``/``add``/``has``/
``remove``/``entities_with`` 调 ``resolve(comp_type)`` 校验类型已注册，未注册
raise ``SchemaError``（非静默 None），防 LPC dbase query 拼写错误静默传播。
``schema=None`` 时不校验（向后兼容测试与开发期临时组件）。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xkx.runtime.schema import SchemaRegistry


class _SparseSet:
    """单组件类型的稀疏集合存储。

    - ``dense``: 组件实例数组（紧凑，无空洞）
    - ``sparse``: ``entity_id -> dense index``（O(1) 查找）
    - ``entities``: ``dense index -> entity_id``（swap-remove 反向查找）

    swap-remove：删除时把末尾元素移到被删位置，O(1) 但不保序。阶段 1 查询不依赖
    attach 顺序（ConditionHandler.on_tick 按 ``next_tick`` 排序，非 attach 顺序）。
    """

    __slots__ = ("dense", "sparse", "entities")

    def __init__(self) -> None:
        self.dense: list[Any] = []
        self.sparse: dict[int, int] = {}
        self.entities: list[int] = []

    def insert(self, eid: int, comp: Any) -> None:
        idx = self.sparse.get(eid)
        if idx is not None:
            self.dense[idx] = comp  # 覆盖同名组件
        else:
            self.sparse[eid] = len(self.dense)
            self.dense.append(comp)
            self.entities.append(eid)

    def get(self, eid: int) -> Any | None:
        idx = self.sparse.get(eid)
        return self.dense[idx] if idx is not None else None

    def has(self, eid: int) -> bool:
        return eid in self.sparse

    def remove(self, eid: int) -> None:
        idx = self.sparse.pop(eid, None)
        if idx is None:
            return
        last = len(self.dense) - 1
        if idx != last:
            # swap-remove：末尾元素移到被删位置
            self.dense[idx] = self.dense[last]
            self.entities[idx] = self.entities[last]
            self.sparse[self.entities[idx]] = idx
        self.dense.pop()
        self.entities.pop()

    def __iter__(self) -> Iterator[tuple[int, Any]]:
        return zip(self.entities, self.dense, strict=True)

    def __len__(self) -> int:
        return len(self.dense)


class World:
    """ECS 世界：entity_id 空间 + 按组件类型的 SparseSet 存储。"""

    def __init__(self, schema: SchemaRegistry | None = None) -> None:
        self._stores: dict[type, _SparseSet] = {}
        self._next_id: int = 1
        self._schema = schema

    def new_entity(self) -> int:
        eid = self._next_id
        self._next_id += 1
        return eid

    def _resolve(self, comp_type: type) -> type:
        """有 schema 时校验 comp_type 已注册（ADR-0019，未注册 raise SchemaError）。"""
        if self._schema is not None:
            self._schema.resolve(comp_type)
        return comp_type

    def _store(self, comp_type: type) -> _SparseSet:
        s = self._stores.get(comp_type)
        if s is None:
            s = _SparseSet()
            self._stores[comp_type] = s
        return s

    def add(self, eid: int, comp: Any) -> None:
        """挂载组件到实体（同类型覆盖）。"""
        ct = self._resolve(type(comp))
        self._store(ct).insert(eid, comp)

    def get(self, eid: int, comp_type: type) -> Any | None:
        """读取实体的某类型组件（无则 None）。"""
        self._resolve(comp_type)
        s = self._stores.get(comp_type)
        return s.get(eid) if s else None

    def has(self, eid: int, comp_type: type) -> bool:
        self._resolve(comp_type)
        s = self._stores.get(comp_type)
        return s.has(eid) if s else False

    def remove(self, eid: int, comp_type: type) -> None:
        """移除实体的某类型组件（无则 no-op）。"""
        self._resolve(comp_type)
        s = self._stores.get(comp_type)
        if s is not None:
            s.remove(eid)

    def entities_with(self, *comp_types: type) -> Iterator[int]:
        """返回同时拥有所有指定组件类型的实体 id。"""
        if not comp_types:
            return
        for ct in comp_types:
            self._resolve(ct)
        stores: list[_SparseSet] = []
        for ct in comp_types:
            s = self._stores.get(ct)
            if s is None:
                return  # 某组件类型无存储，无实体匹配
            stores.append(s)
        if len(stores) == 1:
            yield from (eid for eid, _ in stores[0])
            return
        # 选最小的 SparseSet 遍历，检查其他是否也有该实体
        stores.sort(key=len)
        smallest = stores[0]
        others = stores[1:]
        for eid, _ in smallest:
            if all(s.has(eid) for s in others):
                yield eid

    def entities_in_room(self, room_id: str) -> Iterator[int]:
        from xkx.runtime.components import Position

        for eid in self.entities_with(Position):
            pos = self.get(eid, Position)
            if pos and pos.room_id == room_id:
                yield eid
