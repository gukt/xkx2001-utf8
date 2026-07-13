"""SchemaRegistry 组件类型注册表（阶段 1 T2，ADR-0019）。

LPC dbase ``query`` 拼写错误静默返回 0（[spec/layer_b](_query_spec) postcondition）；
greenfield ``world.get(eid, comp_type)`` 传未注册类型也静默返回 None。SchemaRegistry
让这类错误启动期/调用期明确失败（``SchemaError``），非静默传播。

只做类型注册 + 字段名存在性校验（拼写检查），不做语义校验（dissent 3 护栏）。
语义校验留给 DSL SchemaValidator（ADR-0008，创作期）+ System 不变量（运行期）。

[ADR-0019](../../../docs/adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator


class SchemaError(TypeError):
    """组件类型未注册或字段不存在的拼写错误（ADR-0019）。"""


class SchemaRegistry:
    """组件类型注册表 + 字段名存在性校验（ADR-0019）。

    启动时注册所有内置组件类型，从 ``dataclasses.fields`` 自动提取字段集。
    ``World.get``/``add``/``has``/``remove`` 调 ``resolve(comp_type)`` 校验，未注册
    类型 raise ``SchemaError``（非静默 None）。

    只做拼写检查，不做语义校验（dissent 3 护栏：名字存在性 ≠ 值合法性）。
    """

    def __init__(self) -> None:
        self._types: dict[str, type] = {}  # 类型名 -> 类型
        self._fields: dict[type, frozenset[str]] = {}  # 类型 -> 合法字段名集

    def register(self, comp_type: type) -> None:
        """注册组件类型（启动期调用，从 dataclass fields 提取字段集）。

        重复注册同一类型 no-op；类型名冲突（不同类型同名）raise ``SchemaError``。
        """
        name = comp_type.__name__
        existing = self._types.get(name)
        if existing is not None and existing is not comp_type:
            raise SchemaError(
                f"组件类型名冲突: {name!r} 已注册为 {existing!r}，"
                f"重复注册为 {comp_type!r}"
            )
        if existing is comp_type:
            return  # 幂等
        if not dataclasses.is_dataclass(comp_type):
            raise SchemaError(
                f"组件类型 {comp_type!r} 不是 dataclass，"
                "阶段 1 组件须为 dataclass（ADR-0017）"
            )
        self._types[name] = comp_type
        self._fields[comp_type] = frozenset(
            f.name for f in dataclasses.fields(comp_type)
        )

    def resolve(self, comp_type: type) -> type:
        """校验 comp_type 已注册（未注册 raise SchemaError，非静默 None）。"""
        if comp_type not in self._fields:
            raise SchemaError(
                f"未注册的组件类型 {comp_type!r}，拼写错误或未 register()？"
                f" 已注册: {sorted(self._types)}"
            )
        return comp_type

    def resolve_name(self, name: str) -> type:
        """按类型名解析（T3 dbase key 兼容层用）。"""
        t = self._types.get(name)
        if t is None:
            raise SchemaError(
                f"未知组件类型名: {name!r}，已注册: {sorted(self._types)}"
            )
        return t

    def has_field(self, comp_type: type, field_name: str) -> bool:
        """字段名存在性查询（T3 DBASE_KEY_MAP 校验映射目标用）。"""
        return field_name in self._fields.get(comp_type, frozenset())

    def field_names(self, comp_type: type) -> frozenset[str]:
        """组件的合法字段名集（T3 映射表构建用）。"""
        self.resolve(comp_type)
        return self._fields[comp_type]

    def registered_types(self) -> Iterator[type]:
        """已注册的所有组件类型（调试/自检用）。"""
        return iter(self._types.values())

    @classmethod
    def with_builtins(cls) -> SchemaRegistry:
        """注册全部内置组件（build_world 生产路径用）。"""
        from xkx.runtime.components import (
            Attributes,
            CombatState,
            EffectComp,
            Equipment,
            FamilyComp,
            Identity,
            Inventory,
            Marks,
            NpcBehavior,
            Position,
            Progression,
            QuestLog,
            RoomComp,
            Skills,
            TitleComp,
            Vitals,
        )

        reg = cls()
        for t in (
            Identity,
            Position,
            Attributes,
            Vitals,
            Progression,
            Skills,
            Equipment,
            CombatState,
            NpcBehavior,
            Inventory,
            Marks,
            QuestLog,
            EffectComp,
            RoomComp,
            TitleComp,
            FamilyComp,
        ):
            reg.register(t)
        return reg
