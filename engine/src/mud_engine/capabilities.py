"""物品能力组件注册机制（31 号票 Shotgun Surgery 去重）。

新增一个 item 能力组件原本要散落改三文件四点：components.py（组件类）+
scene_loader._attach_item_capabilities / _ITEM_KNOWN_FIELDS（加载）+
save._ser_X / _des_X / _CODECS（存档）。本模块把每个能力自描述为
``CapabilitySpec``（YAML 解析、dict 序列化、dict 反序列化、已知 YAML 字段），
统一注册到 ``CAPABILITIES`` 列表；scene_loader 与 save 都消费该列表。

新增能力时只需：1) 在 components.py 定义组件类；2) 在本模块追加一条
``CapabilitySpec``（3 个 callable + 1 字段集合）。不再散落三文件。

YAML 解析失败抛 ``mud_engine.errors.SceneLoadError``（叶子错误模块，避免本模块
与 scene_loader 为共享错误类型而循环依赖）。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from mud_engine.components import (
    Consumable,
    Container,
    Equippable,
    ItemFlags,
    Stackable,
    Valuable,
    Weight,
)
from mud_engine.errors import SceneLoadError


@dataclass(frozen=True)
class CapabilitySpec:
    """单个物品能力组件的自描述规格。

    - ``component_type``: 组件类（如 ``Stackable``），用于 codec 键与已知字段聚合。
    - ``known_fields``: 该能力在 YAML 中消费的字段名集合，用于未识别段透传过滤。
    - ``from_yaml``: 把 YAML 字段映射成组件实例；无可挂载内容时返回 ``None``。
    - ``to_dict`` / ``from_dict``: 存档序列化 / 反序列化（JSON 级 dict）。
    """

    component_type: type
    known_fields: frozenset[str]
    from_yaml: Callable[[Mapping, str, Path, dict[type, object]], object | None]
    to_dict: Callable[[object], dict]
    from_dict: Callable[[dict], object]


# ── YAML 解析（从 scene_loader 移来）─────────────────────────────────────
# 每条解析函数在 ``from_yaml(data, label, scene_path, attached)`` 签名下保持原语义，
# 失败抛 ``SceneLoadError`` 并带定位信息。``attached`` 是当前物品已挂载组件映射，
# Weight 用它判断是否需要跳过（Stackable 物品用 unit_weight*amount，不挂 Weight）。

def _parse_stackable(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Stackable | None:
    """``stackable: true|{amount, unit_weight}`` 或顶层 ``amount`` / ``unit_weight``。"""
    raw = data.get("stackable")
    amount = data.get("amount")
    unit_weight = data.get("unit_weight")
    if raw is None and amount is None and unit_weight is None:
        return None
    if isinstance(raw, Mapping):
        amount = raw.get("amount", amount)
        unit_weight = raw.get("unit_weight", unit_weight)
    elif raw is False:
        return None
    if amount is None:
        amount = 1
    try:
        amt = int(amount)
        uw = 1.0 if unit_weight is None else float(unit_weight)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 stackable 字段非法：{exc}"
        ) from exc
    if amt < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 stackable.amount 应 >= 1，实际是 {amt}"
        )
    return Stackable(amount=amt, unit_weight=uw)


def _parse_valuable(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Valuable | None:
    """``valuable: <int>`` / ``valuable: {value: N}`` / 顶层 ``value: N``。"""
    if "valuable" not in data and "value" not in data:
        return None
    raw = data.get("valuable", data.get("value"))
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    if raw is None or raw is False:
        return None
    try:
        return Valuable(value=int(raw))
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 valuable/value 应是整数，实际是 {raw!r}"
        ) from exc


def _parse_equippable(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Equippable | None:
    """``equippable: true|{slot, apply_hook}`` 占位。"""
    raw = data.get("equippable")
    if raw is None or raw is False:
        return None
    if raw is True:
        return Equippable()
    if isinstance(raw, Mapping):
        slot = str(raw.get("slot", "") or "")
        apply_hook = raw.get("apply_hook")
        hook = None if apply_hook is None else str(apply_hook)
        return Equippable(slot=slot, apply_hook=hook)
    raise SceneLoadError(
        f"场景文件 {scene_path} 的{label}的 'equippable' 应是 true 或映射，"
        f"实际是 {type(raw).__name__}"
    )


def _parse_consumable(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Consumable | None:
    """``consumable: true|{uses}`` 占位。"""
    raw = data.get("consumable")
    if raw is None or raw is False:
        return None
    if raw is True:
        return Consumable()
    if isinstance(raw, Mapping):
        uses = raw.get("uses", 1)
        try:
            return Consumable(uses=int(uses))
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 consumable.uses 应是整数，实际是 {uses!r}"
            ) from exc
    raise SceneLoadError(
        f"场景文件 {scene_path} 的{label}的 'consumable' 应是 true 或映射，"
        f"实际是 {type(raw).__name__}"
    )


def _parse_item_flags(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> ItemFlags | None:
    """``no_get`` / ``no_drop`` / ``no_drop_message``；全缺省则不挂组件。"""
    if not any(k in data for k in ("no_get", "no_drop", "no_drop_message")):
        return None
    no_get = bool(data.get("no_get", False))
    no_drop = bool(data.get("no_drop", False))
    msg = data.get("no_drop_message")
    if msg is not None:
        msg = str(msg)
    if not no_get and not no_drop and msg is None:
        return None
    return ItemFlags(no_get=no_get, no_drop=no_drop, no_drop_message=msg)


def _parse_item_container(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Container | None:
    """``container: true|{max_capacity, max_weight}`` 或顶层 max_* 且 container 真。"""
    raw = data.get("container")
    max_capacity = data.get("max_capacity")
    max_weight = data.get("max_weight")
    if raw is None and max_capacity is None and max_weight is None:
        return None
    if raw is False:
        return None
    if isinstance(raw, Mapping):
        max_capacity = raw.get("max_capacity", max_capacity)
        max_weight = raw.get("max_weight", max_weight)
    elif raw is None and (max_capacity is not None or max_weight is not None):
        # 仅顶层上限、未写 container: 不自动变容器（避免误挂）。
        return None
    if raw is None:
        return None
    try:
        cap = None if max_capacity is None else int(max_capacity)
        w = None if max_weight is None else float(max_weight)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的容器上限字段非法：{exc}"
        ) from exc
    return Container(max_capacity=cap, max_weight=w)


def _parse_weight(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Weight | None:
    """``weight: <number>``；Stackable 物品已用 unit_weight*amount，不挂 Weight。"""
    if "weight" not in data:
        return None
    # Stackable 物品用 unit_weight*amount，Weight 与之互斥；Stackable 必须在 Weight 之前处理。
    if Stackable in attached:
        return None
    try:
        return Weight(value=float(data["weight"]))
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'weight' 应是数字，实际是 {data['weight']!r}"
        ) from exc


# ── 序列化 / 反序列化（从 save.py 移来）──────────────────────────────────
# 把原 _ser_X / _des_X 移入 specs，保持原 JSON dict 形状不变。

def _ser_stackable(c: Stackable) -> dict:
    return {"amount": c.amount, "unit_weight": c.unit_weight}


def _des_stackable(d: dict) -> Stackable:
    return Stackable(amount=int(d["amount"]), unit_weight=float(d.get("unit_weight", 1.0)))


def _ser_valuable(c: Valuable) -> dict:
    return {"value": c.value}


def _des_valuable(d: dict) -> Valuable:
    return Valuable(value=int(d["value"]))


def _ser_equippable(c: Equippable) -> dict:
    return {"slot": c.slot, "apply_hook": c.apply_hook}


def _des_equippable(d: dict) -> Equippable:
    return Equippable(slot=str(d.get("slot", "")), apply_hook=d.get("apply_hook"))


def _ser_consumable(c: Consumable) -> dict:
    return {"uses": c.uses}


def _des_consumable(d: dict) -> Consumable:
    return Consumable(uses=int(d.get("uses", 1)))


def _ser_item_flags(c: ItemFlags) -> dict:
    return {
        "no_get": c.no_get,
        "no_drop": c.no_drop,
        "no_drop_message": c.no_drop_message,
    }


def _des_item_flags(d: dict) -> ItemFlags:
    return ItemFlags(
        no_get=bool(d.get("no_get", False)),
        no_drop=bool(d.get("no_drop", False)),
        no_drop_message=d.get("no_drop_message"),
    )


def _ser_weight(c: Weight) -> dict:
    return {"value": c.value}


def _des_weight(d: dict) -> Weight:
    return Weight(value=float(d.get("value", 0.0)))


def _ser_container(c: Container) -> dict:
    payload: dict = {"items": sorted(c.items)}
    if c.max_capacity is not None:
        payload["max_capacity"] = c.max_capacity
    if c.max_weight is not None:
        payload["max_weight"] = c.max_weight
    return payload


def _des_container(d: dict) -> Container:
    return Container(
        items=set(d.get("items", [])),
        max_capacity=d.get("max_capacity"),
        max_weight=d.get("max_weight"),
    )


# ── 注册表 ──────────────────────────────────────────────────────────────
# 顺序重要：Stackable 必须在 Weight 之前处理，Weight.from_yaml 需要 attached 中已有
# Stackable 来判断是否跳过。其他能力之间无依赖。

CAPABILITIES: list[CapabilitySpec] = [
    CapabilitySpec(
        component_type=Stackable,
        known_fields=frozenset({"stackable", "amount", "unit_weight"}),
        from_yaml=_parse_stackable,
        to_dict=_ser_stackable,
        from_dict=_des_stackable,
    ),
    CapabilitySpec(
        component_type=Valuable,
        known_fields=frozenset({"valuable", "value"}),
        from_yaml=_parse_valuable,
        to_dict=_ser_valuable,
        from_dict=_des_valuable,
    ),
    CapabilitySpec(
        component_type=Equippable,
        known_fields=frozenset({"equippable"}),
        from_yaml=_parse_equippable,
        to_dict=_ser_equippable,
        from_dict=_des_equippable,
    ),
    CapabilitySpec(
        component_type=Consumable,
        known_fields=frozenset({"consumable"}),
        from_yaml=_parse_consumable,
        to_dict=_ser_consumable,
        from_dict=_des_consumable,
    ),
    CapabilitySpec(
        component_type=ItemFlags,
        known_fields=frozenset({"no_get", "no_drop", "no_drop_message"}),
        from_yaml=_parse_item_flags,
        to_dict=_ser_item_flags,
        from_dict=_des_item_flags,
    ),
    CapabilitySpec(
        component_type=Container,
        known_fields=frozenset({"container", "max_capacity", "max_weight"}),
        from_yaml=_parse_item_container,
        to_dict=_ser_container,
        from_dict=_des_container,
    ),
    CapabilitySpec(
        component_type=Weight,
        known_fields=frozenset({"weight"}),
        from_yaml=_parse_weight,
        to_dict=_ser_weight,
        from_dict=_des_weight,
    ),
]

CAPABILITY_COMPONENT_TYPES: frozenset[type] = frozenset(
    spec.component_type for spec in CAPABILITIES
)

__all__ = [
    "CAPABILITIES",
    "CAPABILITY_COMPONENT_TYPES",
    "CapabilitySpec",
]
