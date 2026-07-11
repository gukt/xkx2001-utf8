"""组件 dataclass <-> JSON 序列化/反序列化（阶段 1 Wave 2 T5，ADR-0022 §6）。

衔接 [SchemaRegistry](schema.py) 的字段名集：序列化时按 ``dataclasses.fields``
提取字段；反序列化时按组件类型名从 SchemaRegistry 解析回类型，用字段集校验。

设计要点（ADR-0022 §6 + §7）：

- 组件字段全为基本类型（int/str/bool）+ ``set``/``dict`` 容器，dataclasses 友好。
- ``set`` 字段序列化为 JSON ``list``（JSON 无 set），反序列化时还原 ``set``。
- ``Optional`` 字段（如 ``Skills.weapon: str | None``）原样存取，``None`` -> ``null``。
- EffectComp 随实体序列化，含 ``duration``/``next_tick``/``tick_interval``，崩溃
  恢复时由 StorageSystem/restore 对齐 ``next_tick``（本模块只做忠实序列化，不做
  对齐--对齐需要 current_tick，属 restore 协议职责，见 storage.py）。

存档文件 schema（ADR-0022 §4）：

```
{
  "version": 1,
  "entity_id": <int>,
  "last_tick": <int>,          # 存档时的 tick 编号（冷重启 tick 对齐用）
  "components": {
    "<CompTypeName>": { "<field>": <value>, ... },
    ...
  }
}
```

EffectComp 与其他组件一视同仁（进 ``components``）。T5 按 ADR-0017 的"独立 effect
实体"模型：持续 Effect 是独立实体，EffectComp 随该实体存档，``target_id``/``source_id``
是 entity_id 引用。restore 时引用校验在 storage.py（ADR-0022 §5 台账 #4 + §7 步骤 3）。

不持久化（ADR-0022 §6 边界）：

- ``ConditionTickResult``（on_tick 返回值，apply 后丢弃）。
- combat 即时 ``Effect``（``CombatRoundResult.effects``，apply 后丢弃）。
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xkx.runtime.schema import SchemaRegistry


# 存档 schema 版本（ADR-0022 §7 不做热迁移，version 字段预留）
SAVE_VERSION = 1


def _set_field_names(comp_type: type) -> frozenset[str]:
    """组件中类型为 ``set`` 的字段名集（用于反序列化时 list -> set 还原）。

    ``from __future__ import annotations`` 下 ``Field.type`` 是字符串，需用
    ``typing.get_type_hints`` 解析为真实类型。缓存到 ``__xkx_set_fields__`` 避免重复
    解析（组件类型稳定，一次解析多次复用）。
    """
    cached = comp_type.__dict__.get("__xkx_set_fields__")
    if cached is not None:
        return cached
    import typing

    hints = typing.get_type_hints(comp_type)
    names = frozenset(
        name for name, hint in hints.items() if typing.get_origin(hint) is set
    )
    # 缓存到类型属性（dataclass 类型可设类属性，不冲突）
    comp_type.__xkx_set_fields__ = names  # type: ignore[attr-defined]
    return names


def serialize_component(comp: Any) -> dict[str, Any]:
    """单个组件 -> JSON object（set 字段转 list）。

    用 ``dataclasses.fields`` 提取字段集，与 SchemaRegistry 注册的字段集一致
    （SchemaRegistry 用同一 API 提取，ADR-0019）。set 字段按值类型判断（运行时
    ``isinstance``），序列化为 sorted list 保证往返可复现（hypothesis 友好）。
    """
    obj: dict[str, Any] = {}
    for f in dataclasses.fields(comp):
        val = getattr(comp, f.name)
        if isinstance(val, set):
            obj[f.name] = sorted(val)  # 排序保证往返稳定性
        else:
            obj[f.name] = val
    return obj


def deserialize_component(comp_type: type, data: dict[str, Any]) -> Any:
    """JSON object -> 组件实例（list 字段还原 set）。

    用 ``_set_field_names`` 判定哪些字段是 set，把 JSON list 还原为 set。其余字段
    按 dataclass 构造传入。

    多余/缺失字段容忍（ADR-0022 §7 version 兼容）：多余字段忽略（向前兼容新字段），
    缺失字段用 dataclass 默认值（向后兼容旧存档缺字段）。
    """
    set_names = _set_field_names(comp_type)
    field_map = {f.name: f for f in dataclasses.fields(comp_type)}
    kwargs: dict[str, Any] = {}
    for name, val in data.items():
        if name not in field_map:
            continue  # 多余字段忽略（schema 演进容忍）
        if name in set_names and isinstance(val, list):
            kwargs[name] = set(val)
        else:
            kwargs[name] = val
    return comp_type(**kwargs)


def serialize_entity(
    eid: int,
    components: list[Any],
    *,
    last_tick: int = 0,
) -> dict[str, Any]:
    """实体 -> 存档 JSON object（ADR-0022 §4 文件格式）。

    Args:
        eid: 实体 id
        components: 该实体的所有组件实例（含 EffectComp）
        last_tick: 存档时的 tick 编号（冷重启 tick 对齐用，ADR-0022 §7 步骤 4）
    """
    comps: dict[str, Any] = {}
    for comp in components:
        type_name = type(comp).__name__
        comps[type_name] = serialize_component(comp)
    return {
        "version": SAVE_VERSION,
        "entity_id": eid,
        "last_tick": last_tick,
        "components": comps,
    }


def deserialize_entity(
    data: dict[str, Any],
    schema: SchemaRegistry,
) -> tuple[int, list[Any]]:
    """存档 JSON object -> (entity_id, 组件实例列表)。

    用 SchemaRegistry 按组件类型名解析回类型（``resolve_name``），ADR-0019 拼写
    校验。未知类型名 raise ``SchemaError``（不静默丢弃，存档损坏明确失败）。

    ``last_tick`` 不在此返回（restore 协议在 storage.py 读，用于 tick 对齐）。
    """
    eid = int(data["entity_id"])
    comps_raw = data.get("components", {})
    components: list[Any] = []
    for type_name, comp_data in comps_raw.items():
        comp_type = schema.resolve_name(type_name)
        components.append(deserialize_component(comp_type, comp_data))
    return eid, components


def serialize_world_snapshot(
    entities: dict[int, list[Any]],
    *,
    last_tick: int = 0,
) -> dict[int, dict[str, Any]]:
    """批量序列化：``{eid -> 组件列表}`` -> ``{eid -> 存档 object}``。

    供 StorageSystem.persist 在深拷贝快照上调用（ADR-0022 §3 并发安全：persist
    线程只读快照）。
    """
    return {
        eid: serialize_entity(eid, comps, last_tick=last_tick)
        for eid, comps in entities.items()
    }
