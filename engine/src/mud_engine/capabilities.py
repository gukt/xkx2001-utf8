"""实体能力组件注册机制（M1-31 物品 + M2-01 房间/NPC）。

新增一个能力组件原本要散落改三文件四点：components.py（组件类）+
scene_loader 已知字段集合 / 挂载逻辑（加载）+ save._ser_X / _des_X / _CODECS
（存档）。本模块把每个能力自描述为 ``CapabilitySpec``（YAML 解析、dict 序列化、
dict 反序列化、已知 YAML 字段），按实体类别注册到：

- ``CAPABILITIES``：物品级（M1-31）
- ``ROOM_CAPABILITIES``：房间级（M2-01；块 B~G 后续追加 Terrain 等）
- ``NPC_CAPABILITIES``：NPC 级（M2-01；块 B~G 后续追加 Vitals/Faction 等）

``CapabilitySpec`` 形状三类共用，后续票追加新能力时直接照抄物品写法。

不在本模块扫平范围内（M2-01 刻意收缩，避免过度设计）：

- ``_PLAYER_KNOWN_FIELDS``（``name``/``start_room``）：player 段字段少，后续如需
  给玩家挂 Currency/Faction 初始值，直接加进该 frozenset，不为个别字段建注册表。
- ``_TOP_LEVEL_KNOWN_SECTIONS``：新顶层段（``factions:``/``skills:``）是全局注册表
  模式，不是"实体能力"模式，由各自票（03/08）决定。

YAML 解析失败抛 ``mud_engine.errors.SceneLoadError``（叶子错误模块，避免本模块
与 scene_loader 为共享错误类型而循环依赖）。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from mud_engine.components import (
    DEFAULT_UNCONSCIOUS_RECOVERY_TICKS,
    AIController,
    BaseAttributes,
    Behaviors,
    BehaviorSpec,
    Consumable,
    Container,
    Currency,
    Dead,
    Description,
    Engaged,
    EntryGuard,
    Equippable,
    Faction,
    Ferry,
    Gender,
    Inquiry,
    ItemFlags,
    ItemTags,
    Mount,
    NoDeathZone,
    Riding,
    RoomDetails,
    ShopEntry,
    ShopInventory,
    SkillLevels,
    SkillProgress,
    Stackable,
    Terrain,
    Unconscious,
    Valuable,
    Vitals,
    Weight,
)
from mud_engine.errors import SceneLoadError
from mud_engine.semantic_color import validate_markup
from mud_engine.skills import SKILLS


@dataclass(frozen=True)
class CapabilitySpec:
    """单个实体能力组件的自描述规格（物品 / 房间 / NPC 三类注册表共用）。

    - ``component_type``: 组件类（如 ``Stackable`` / ``Inquiry``），用于 codec 键与已知字段聚合。
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
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}的容器上限字段非法：{exc}") from exc
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


def _parse_item_tags(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> ItemTags | None:
    """``tags: [weapon, edged]`` 或 ``item_tags: [...]``。"""
    raw = data.get("tags", data.get("item_tags"))
    if raw is None:
        return None
    if isinstance(raw, str):
        return ItemTags(tags=frozenset({raw}))
    if not isinstance(raw, (list, tuple, set, frozenset)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 tags 应是列表，实际是 {type(raw).__name__}"
        )
    return ItemTags(tags=frozenset(str(t) for t in raw))


def _ser_item_tags(c: ItemTags) -> dict:
    return {"tags": sorted(c.tags)}


def _des_item_tags(d: dict) -> ItemTags:
    return ItemTags(tags=frozenset(str(t) for t in d.get("tags", ())))


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
    CapabilitySpec(
        component_type=ItemTags,
        known_fields=frozenset({"tags", "item_tags"}),
        from_yaml=_parse_item_tags,
        to_dict=_ser_item_tags,
        from_dict=_des_item_tags,
    ),
]

CAPABILITY_COMPONENT_TYPES: frozenset[type] = frozenset(
    spec.component_type for spec in CAPABILITIES
)


# ── 房间级能力（M2-01）──────────────────────────────────────────────────
# Description 本身由 scene_loader._attach_identity_and_description 挂载（含
# outdoors）；本条只贡献 known_fields（outdoors）与存档 codec，from_yaml 恒
# 返回 None，避免重复挂载。Description codec 挂在本表而非 NPC_CAPABILITIES：
# 房间/物品/NPC 共用同一组件类型，save.py 按类型查 codec 一次即可（票 01
# code-review：组织不对称但功能等价，刻意不在 NPC 表重复登记）。
# NoDeathZone / Ferry 等按物品能力写法追加真正的 from_yaml。


def _parse_room_description(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> None:
    """房间 Description 已由固有装配路径挂载；此处只占位以保持 CapabilitySpec 形状。"""
    return None


def _ser_description(c: Description) -> dict:
    return {"short": c.short, "long": c.long, "outdoors": c.outdoors}


def _des_description(d: dict) -> Description:
    # outdoors 缺省 False：兼容旧存档（15 号票前无此字段）。
    return Description(short=d["short"], long=d["long"], outdoors=bool(d.get("outdoors", False)))


def _parse_no_death_zone(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> NoDeathZone | None:
    """``no_death: true`` → 挂 NoDeathZone；缺省 / false 不挂。"""
    raw = data.get("no_death")
    if raw is None or raw is False:
        return None
    if raw is True:
        return NoDeathZone()
    raise SceneLoadError(
        f"场景文件 {scene_path} 的{label}的 'no_death' 应是 true/false，实际是 {raw!r}"
    )


def _ser_no_death_zone(_c: NoDeathZone) -> dict:
    return {}


def _des_no_death_zone(_d: dict) -> NoDeathZone:
    return NoDeathZone()


def _parse_terrain(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Terrain | None:
    """``cost: N`` 或 ``terrain: {cost: N}`` / ``terrain: N``；缺省不挂（等同 cost=1）。"""
    if "cost" in data:
        raw = data["cost"]
    elif "terrain" in data:
        raw = data["terrain"]
        if isinstance(raw, Mapping):
            raw = raw.get("cost", 1)
    else:
        return None
    try:
        cost = int(raw)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 terrain/cost 应是整数，实际是 {raw!r}"
        ) from exc
    if cost < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 terrain cost 应 >= 1，实际是 {cost}"
        )
    return Terrain(cost=cost)


def _ser_terrain(c: Terrain) -> dict:
    return {"cost": c.cost}


def _des_terrain(d: dict) -> Terrain:
    return Terrain(cost=int(d.get("cost", 1)))


def _parse_ferry(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Ferry | None:
    """``ferry: {far_bank, cross_interval, direction}``；far_bank 键稍后解析。"""
    raw = data.get("ferry")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'ferry' 应是映射，实际是 {type(raw).__name__}"
        )
    far_key = raw.get("far_bank")
    if not far_key:
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}的 ferry 缺少必需字段 'far_bank'")
    direction = raw.get("direction")
    if not direction:
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}的 ferry 缺少必需字段 'direction'")
    interval_raw = raw.get("cross_interval")
    if interval_raw is None:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 ferry 缺少必需字段 'cross_interval'"
        )
    try:
        interval = int(interval_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 ferry.cross_interval 应是正整数，"
            f"实际是 {interval_raw!r}"
        ) from exc
    if interval < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 ferry.cross_interval 应 >= 1，实际是 {interval}"
        )
    # far_bank 房间键在 scene_loader 建完全部房间后再解析为 EntityId。
    return Ferry(
        far_bank=0,
        cross_interval=interval,
        direction=str(direction),
        _far_bank_key=str(far_key),
    )


def _ser_ferry(c: Ferry) -> dict:
    return {
        "far_bank": c.far_bank,
        "cross_interval": c.cross_interval,
        "direction": c.direction,
    }


def _des_ferry(d: dict) -> Ferry:
    return Ferry(
        far_bank=int(d["far_bank"]),
        cross_interval=int(d["cross_interval"]),
        direction=str(d["direction"]),
    )


def _parse_entry_guard(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> EntryGuard | None:
    """``entry_guard: {condition: {...}, deny_message: "..."}``。"""
    raw = data.get("entry_guard")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'entry_guard' 应是映射，实际是 {type(raw).__name__}"
        )
    cond = raw.get("condition")
    if not isinstance(cond, Mapping):
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}的 entry_guard.condition 应是映射")
    msg = raw.get("deny_message") or raw.get("message") or "你不能进入此地。"
    return EntryGuard(condition=dict(cond), deny_message=str(msg))


def _ser_entry_guard(c: EntryGuard) -> dict:
    return {"condition": dict(c.condition), "deny_message": c.deny_message}


def _des_entry_guard(d: dict) -> EntryGuard:
    return EntryGuard(
        condition=dict(d.get("condition", {})),
        deny_message=str(d.get("deny_message", "你不能进入此地。")),
    )


def _parse_room_details(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> RoomDetails | None:
    """``details: {键: 描述文本}``；缺省不挂。"""
    raw = data.get("details")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'details' 应是映射，实际是 {type(raw).__name__}"
        )
    entries: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 details 键应是非空字符串，实际是 {key!r}"
            )
        if not isinstance(value, str):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 details[{key!r}] 应是字符串，"
                f"实际是 {type(value).__name__}"
            )
        validate_markup(
            value,
            location=f"场景文件 {scene_path} 的{label}.details[{key!r}]",
        )
        entries[key] = value
    if not entries:
        return None
    return RoomDetails(entries=entries)


def _ser_room_details(c: RoomDetails) -> dict:
    return {"entries": dict(c.entries)}


def _des_room_details(d: dict) -> RoomDetails:
    raw = d.get("entries", d)
    return RoomDetails(entries={str(k): str(v) for k, v in dict(raw).items()})


ROOM_CAPABILITIES: list[CapabilitySpec] = [
    CapabilitySpec(
        component_type=Description,
        known_fields=frozenset({"outdoors"}),
        from_yaml=_parse_room_description,
        to_dict=_ser_description,
        from_dict=_des_description,
    ),
    CapabilitySpec(
        component_type=NoDeathZone,
        known_fields=frozenset({"no_death"}),
        from_yaml=_parse_no_death_zone,
        to_dict=_ser_no_death_zone,
        from_dict=_des_no_death_zone,
    ),
    CapabilitySpec(
        component_type=Ferry,
        known_fields=frozenset({"ferry"}),
        from_yaml=_parse_ferry,
        to_dict=_ser_ferry,
        from_dict=_des_ferry,
    ),
    CapabilitySpec(
        component_type=EntryGuard,
        known_fields=frozenset({"entry_guard"}),
        from_yaml=_parse_entry_guard,
        to_dict=_ser_entry_guard,
        from_dict=_des_entry_guard,
    ),
    CapabilitySpec(
        component_type=Terrain,
        known_fields=frozenset({"cost", "terrain"}),
        from_yaml=_parse_terrain,
        to_dict=_ser_terrain,
        from_dict=_des_terrain,
    ),
    CapabilitySpec(
        component_type=RoomDetails,
        known_fields=frozenset({"details"}),
        from_yaml=_parse_room_details,
        to_dict=_ser_room_details,
        from_dict=_des_room_details,
    ),
]


# ── NPC 级能力（M2-01）──────────────────────────────────────────────────
# 顺序：Inquiry 独立；Behaviors 在 AIController 之前（AIController 仅在有
# behaviors 时挂载，与 M1 语义一致）。


def _parse_inquiry(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Inquiry | None:
    """``inquiry: { topic: 文案, default: 兜底, handler: 钩子名 }``；缺省 None。"""
    raw = data.get("inquiry")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'inquiry' 应是映射，实际是 {type(raw).__name__}"
        )
    topics: dict[str, str] = {}
    default: str | None = None
    handler: str | None = None
    for key, value in raw.items():
        key_s = str(key)
        if key_s == "default":
            default = str(value)
            continue
        if key_s == "handler":
            handler = None if value is None else str(value)
            continue
        topics[key_s] = str(value)
    return Inquiry(topics=topics, default=default, handler=handler)


def _parse_behaviors(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Behaviors | None:
    """``behaviors:`` 列表为 ``Behaviors``；缺省 / 空列表返回 None。"""
    raw = data.get("behaviors")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'behaviors' 应是列表，实际是 {type(raw).__name__}"
        )
    entries: list[BehaviorSpec] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 behaviors[{index}] "
                f"应是映射，实际是 {type(entry).__name__}"
            )
        kind = str(entry.get("kind", ""))
        if not kind:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 behaviors[{index}] 缺少 'kind'"
            )
        msgs_raw = entry.get("chat_msgs", ())
        if not isinstance(msgs_raw, (list, tuple)):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 behaviors[{index}] "
                f"的消息列表应是列表，实际是 {type(msgs_raw).__name__}"
            )
        chance_raw = entry.get("chat_chance", 0.0)
        try:
            chance = float(chance_raw)
        except (TypeError, ValueError):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 behaviors[{index}] "
                f"的概率应是数字，实际是 {chance_raw!r}"
            ) from None
        when = entry.get("when")
        if when is not None and not isinstance(when, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 behaviors[{index}] "
                f"的 'when' 应是映射，实际是 {type(when).__name__}"
            )
        entries.append(
            BehaviorSpec(
                kind=kind,
                chat_msgs=tuple(str(m) for m in msgs_raw),
                chat_chance=chance,
                when=dict(when) if when is not None else None,
            )
        )
    if not entries:
        return None
    return Behaviors(entries=entries)


def _parse_ai_controller(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> AIController | None:
    """有 Behaviors 时才挂 AIController；``tick_interval`` 默认 1。"""
    if Behaviors not in attached:
        return None
    raw = data.get("tick_interval", 1)
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'tick_interval' 应是正整数，实际是 {raw!r}"
        ) from None
    if value < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'tick_interval' 应 >= 1，实际是 {value}"
        )
    return AIController(tick_interval=value)


def _ser_inquiry(c: Inquiry) -> dict:
    return {"topics": dict(c.topics), "default": c.default, "handler": c.handler}


def _des_inquiry(d: dict) -> Inquiry:
    return Inquiry(
        topics=dict(d.get("topics", {})),
        default=d.get("default"),
        handler=d.get("handler"),
    )


def _ser_behaviors(c: Behaviors) -> dict:
    return {
        "entries": [
            {
                "kind": e.kind,
                "chat_msgs": list(e.chat_msgs),
                "chat_chance": e.chat_chance,
                "when": e.when,
            }
            for e in c.entries
        ]
    }


def _des_behaviors(d: dict) -> Behaviors:
    entries: list[BehaviorSpec] = []
    for raw in d.get("entries", []):
        entries.append(
            BehaviorSpec(
                kind=str(raw["kind"]),
                chat_msgs=tuple(raw.get("chat_msgs", [])),
                chat_chance=float(raw.get("chat_chance", 0.0)),
                when=raw.get("when"),
            )
        )
    return Behaviors(entries=entries)


def _ser_ai_controller(c: AIController) -> dict:
    return {"tick_interval": c.tick_interval}


def _des_ai_controller(d: dict) -> AIController:
    return AIController(tick_interval=int(d.get("tick_interval", 1)))


# ── NPC/玩家成长与经济能力（M2-05/07/08）────────────────────────────────


def _parse_vitals(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Vitals | None:
    """``vitals:`` 映射；缺省不挂（调用方可给玩家合理默认）。"""
    raw = data.get("vitals")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'vitals' 应是映射，实际是 {type(raw).__name__}"
        )

    def _pair(prefix: str, default_max: int = 100) -> tuple[int, int]:
        cur_key, max_key = f"{prefix}_current", f"{prefix}_max"
        # 也接受简写 qi / qi_max。
        cur = raw.get(cur_key, raw.get(prefix, default_max))
        mx = raw.get(max_key, cur if cur_key in raw or prefix in raw else default_max)
        try:
            return int(cur), int(mx)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 vitals.{prefix} 应是整数：{exc}"
            ) from exc

    qi_c, qi_m = _pair("qi")
    neili_c, neili_m = _pair("neili")
    jingli_c, jingli_m = _pair("jingli")
    return Vitals(
        qi_current=qi_c,
        qi_max=qi_m,
        neili_current=neili_c,
        neili_max=neili_m,
        jingli_current=jingli_c,
        jingli_max=jingli_m,
    )


def _ser_vitals(c: Vitals) -> dict:
    return {
        "qi_current": c.qi_current,
        "qi_max": c.qi_max,
        "neili_current": c.neili_current,
        "neili_max": c.neili_max,
        "jingli_current": c.jingli_current,
        "jingli_max": c.jingli_max,
    }


def _des_vitals(d: dict) -> Vitals:
    return Vitals(
        qi_current=int(d["qi_current"]),
        qi_max=int(d["qi_max"]),
        neili_current=int(d["neili_current"]),
        neili_max=int(d["neili_max"]),
        jingli_current=int(d["jingli_current"]),
        jingli_max=int(d["jingli_max"]),
    )


def _parse_attributes(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> BaseAttributes | None:
    """``attributes:`` 四维；缺省不挂。"""
    raw = data.get("attributes")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'attributes' 应是映射，实际是 {type(raw).__name__}"
        )

    def _int(key: str, alt: str, default: int) -> int:
        val = raw.get(key, raw.get(alt, default))
        try:
            return int(val)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 attributes.{key} 应是整数，实际是 {val!r}"
            ) from exc

    return BaseAttributes(
        str_=_int("str_", "str", 10),
        con=_int("con", "con", 10),
        dex=_int("dex", "dex", 10),
        int_=_int("int_", "int", 10),
    )


def _ser_attributes(c: BaseAttributes) -> dict:
    return {"str_": c.str_, "con": c.con, "dex": c.dex, "int_": c.int_}


def _des_attributes(d: dict) -> BaseAttributes:
    return BaseAttributes(
        str_=int(d.get("str_", d.get("str", 10))),
        con=int(d.get("con", 10)),
        dex=int(d.get("dex", 10)),
        int_=int(d.get("int_", d.get("int", 10))),
    )


def _parse_skill_levels(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> SkillLevels | None:
    """实体级 ``skills:``（与顶层 SkillData 注册表不同层级）。"""
    raw = data.get("skills")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'skills' 应是映射，实际是 {type(raw).__name__}"
        )
    levels: dict[str, SkillProgress] = {}
    for skill_id, entry in raw.items():
        key = str(skill_id)
        if isinstance(entry, Mapping):
            level = entry.get("level", 0)
            exp = entry.get("exp", 0)
        else:
            level, exp = entry, 0
        try:
            levels[key] = SkillProgress(level=int(level), exp=int(exp))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 skills.{key} 等级/经验非法：{exc}"
            ) from exc
        # 加载期引用校验：实体 skills 必须指向已声明的全局 SkillData（spec H1）。
        if key not in SKILLS:
            raise SceneLoadError(f"场景文件 {scene_path} 的{label}的 skills 引用未声明技能 '{key}'")
    return SkillLevels(levels=levels)


def _ser_skill_levels(c: SkillLevels) -> dict:
    return {"levels": {sid: {"level": p.level, "exp": p.exp} for sid, p in c.levels.items()}}


def _des_skill_levels(d: dict) -> SkillLevels:
    raw = d.get("levels", {})
    levels = {
        str(sid): SkillProgress(level=int(p["level"]), exp=int(p.get("exp", 0)))
        for sid, p in raw.items()
    }
    return SkillLevels(levels=levels)


def _parse_currency(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Currency | None:
    """``currency: N`` 或 ``currency: {amount: N}``。"""
    if "currency" not in data:
        return None
    raw = data["currency"]
    if isinstance(raw, Mapping):
        raw = raw.get("amount")
    if raw is None:
        return None
    try:
        amount = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 currency 应是整数，实际是 {raw!r}"
        ) from exc
    if amount < 0:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 currency 不能为负，实际是 {amount}"
        )
    return Currency(amount=amount)


def _ser_currency(c: Currency) -> dict:
    return {"amount": c.amount}


def _des_currency(d: dict) -> Currency:
    return Currency(amount=int(d.get("amount", 0)))


def _parse_shop(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> ShopInventory | None:
    """``shop:`` 列表；条目 ``{item, ...}`` / ``{mount, price}`` / 裸物品模板键。"""
    raw = data.get("shop")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'shop' 应是列表，实际是 {type(raw).__name__}"
        )
    entries: list[ShopEntry] = []
    for index, entry in enumerate(raw):
        if isinstance(entry, str):
            entries.append(ShopEntry(item_template_key=entry))
            continue
        if not isinstance(entry, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 shop[{index}] "
                f"应是映射或模板键字符串，实际是 {type(entry).__name__}"
            )
        mount_key = entry.get("mount") or entry.get("mount_template_key")
        item_key = entry.get("item") or entry.get("item_template_key")
        discount_raw = entry.get("resell_discount", 1.0)
        try:
            discount = float(discount_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 shop[{index}] "
                f"的 resell_discount 应是数字，实际是 {discount_raw!r}"
            ) from exc
        price = None
        if "price" in entry and entry["price"] is not None:
            try:
                price = int(entry["price"])  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的{label}的 shop[{index}] "
                    f"的 price 应是整数，实际是 {entry['price']!r}"
                ) from exc
        if mount_key:
            if price is None or price < 0:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的{label}的 shop[{index}] 出售坐骑时必须声明非负 price"
                )
            entries.append(
                ShopEntry(
                    mount_template_key=str(mount_key),
                    resell_discount=discount,
                    price=price,
                )
            )
            continue
        if not item_key:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 shop[{index}] 缺少 'item' 或 'mount'"
            )
        entries.append(
            ShopEntry(
                item_template_key=str(item_key),
                resell_discount=discount,
                price=price,
            )
        )
    return ShopInventory(entries=tuple(entries))


def _ser_shop(c: ShopInventory) -> dict:
    return {
        "entries": [
            {
                "item_template_key": e.item_template_key,
                "mount_template_key": e.mount_template_key,
                "resell_discount": e.resell_discount,
                "price": e.price,
            }
            for e in c.entries
        ]
    }


def _des_shop(d: dict) -> ShopInventory:
    entries = tuple(
        ShopEntry(
            item_template_key=(
                None if e.get("item_template_key") in (None, "") else str(e["item_template_key"])
            ),
            mount_template_key=(
                None if e.get("mount_template_key") in (None, "") else str(e["mount_template_key"])
            ),
            resell_discount=float(e.get("resell_discount", 1.0)),
            price=None if e.get("price") is None else int(e["price"]),
        )
        for e in d.get("entries", [])
    )
    return ShopInventory(entries=entries)


def _parse_faction(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Faction | None:
    """``faction: <id>`` 或 ``faction: {id: ...}``；缺省不挂（无门派）。

    引用未声明门派的校验在 scene_loader（FACTIONS 加载后）补做。
    """
    if "faction" not in data:
        return None
    raw = data["faction"]
    if raw is None:
        return Faction(faction_id=None)
    if isinstance(raw, Mapping):
        raw = raw.get("id", raw.get("faction_id"))
    return Faction(faction_id=str(raw) if raw is not None else None)


def _ser_faction(c: Faction) -> dict:
    return {"faction_id": c.faction_id}


def _des_faction(d: dict) -> Faction:
    raw = d.get("faction_id")
    return Faction(faction_id=None if raw is None else str(raw))


def _parse_runtime_marker(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> None:
    """Unconscious/Dead 仅运行时挂载，无 YAML；本条只贡献存档 codec。"""
    return None


def _ser_unconscious(c: Unconscious) -> dict:
    return {"ticks_remaining": int(c.ticks_remaining)}


def _des_unconscious(d: dict) -> Unconscious:
    # 老存档缺字段 → 回退默认，不新增迁移框架。
    return Unconscious(
        ticks_remaining=int(
            d.get("ticks_remaining", DEFAULT_UNCONSCIOUS_RECOVERY_TICKS)
        )
    )


def _ser_dead(_c: Dead) -> dict:
    return {}


def _des_dead(_d: dict) -> Dead:
    return Dead()


def _ser_engaged(c: Engaged) -> dict:
    return {"opponent": int(c.opponent)}


def _des_engaged(d: dict) -> Engaged:
    return Engaged(opponent=int(d["opponent"]))


def _parse_mount(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Mount | None:
    """``mount: {ability, jingli/jingli_current, jingli_max}``。"""
    raw = data.get("mount")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 'mount' 应是映射，实际是 {type(raw).__name__}"
        )
    try:
        ability = int(raw.get("ability", 1))
        jingli_max = int(raw.get("jingli_max", raw.get("jingli", 100)))
        jingli_current = int(raw.get("jingli_current", jingli_max))
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}的 mount 字段应是整数") from exc
    return Mount(
        ability=ability,
        jingli_current=jingli_current,
        jingli_max=jingli_max,
        ridden_by=None,
    )


def _ser_mount(c: Mount) -> dict:
    return {
        "ability": c.ability,
        "jingli_current": c.jingli_current,
        "jingli_max": c.jingli_max,
        "ridden_by": c.ridden_by,
    }


def _des_mount(d: dict) -> Mount:
    ridden = d.get("ridden_by")
    return Mount(
        ability=int(d.get("ability", 1)),
        jingli_current=int(d.get("jingli_current", 0)),
        jingli_max=int(d.get("jingli_max", 0)),
        ridden_by=None if ridden is None else int(ridden),
    )


def _ser_riding(c: Riding) -> dict:
    return {"mount_id": int(c.mount_id)}


def _des_riding(d: dict) -> Riding:
    return Riding(mount_id=int(d["mount_id"]))


def _parse_gender(
    data: Mapping, label: str, scene_path: Path, attached: dict[type, object]
) -> Gender | None:
    """``gender: male`` 或 ``gender: {value: ...}``。"""
    if "gender" not in data:
        return None
    raw = data["gender"]
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        raw = raw.get("value", raw.get("gender"))
    return Gender(value=str(raw))


def _ser_gender(c: Gender) -> dict:
    return {"value": c.value}


def _des_gender(d: dict) -> Gender:
    return Gender(value=str(d.get("value", "")))


NPC_CAPABILITIES: list[CapabilitySpec] = [
    CapabilitySpec(
        component_type=Inquiry,
        known_fields=frozenset({"inquiry"}),
        from_yaml=_parse_inquiry,
        to_dict=_ser_inquiry,
        from_dict=_des_inquiry,
    ),
    CapabilitySpec(
        component_type=Behaviors,
        known_fields=frozenset({"behaviors"}),
        from_yaml=_parse_behaviors,
        to_dict=_ser_behaviors,
        from_dict=_des_behaviors,
    ),
    CapabilitySpec(
        component_type=AIController,
        known_fields=frozenset({"tick_interval"}),
        from_yaml=_parse_ai_controller,
        to_dict=_ser_ai_controller,
        from_dict=_des_ai_controller,
    ),
    CapabilitySpec(
        component_type=Vitals,
        known_fields=frozenset({"vitals"}),
        from_yaml=_parse_vitals,
        to_dict=_ser_vitals,
        from_dict=_des_vitals,
    ),
    CapabilitySpec(
        component_type=BaseAttributes,
        known_fields=frozenset({"attributes"}),
        from_yaml=_parse_attributes,
        to_dict=_ser_attributes,
        from_dict=_des_attributes,
    ),
    CapabilitySpec(
        component_type=SkillLevels,
        known_fields=frozenset({"skills"}),
        from_yaml=_parse_skill_levels,
        to_dict=_ser_skill_levels,
        from_dict=_des_skill_levels,
    ),
    CapabilitySpec(
        component_type=Currency,
        known_fields=frozenset({"currency"}),
        from_yaml=_parse_currency,
        to_dict=_ser_currency,
        from_dict=_des_currency,
    ),
    CapabilitySpec(
        component_type=ShopInventory,
        known_fields=frozenset({"shop"}),
        from_yaml=_parse_shop,
        to_dict=_ser_shop,
        from_dict=_des_shop,
    ),
    CapabilitySpec(
        component_type=Faction,
        known_fields=frozenset({"faction"}),
        from_yaml=_parse_faction,
        to_dict=_ser_faction,
        from_dict=_des_faction,
    ),
    # 运行时 marker：无 YAML 字段；from_yaml 恒 None，只贡献存档 codec（票 06）。
    CapabilitySpec(
        component_type=Unconscious,
        known_fields=frozenset(),
        from_yaml=_parse_runtime_marker,
        to_dict=_ser_unconscious,
        from_dict=_des_unconscious,
    ),
    CapabilitySpec(
        component_type=Dead,
        known_fields=frozenset(),
        from_yaml=_parse_runtime_marker,
        to_dict=_ser_dead,
        from_dict=_des_dead,
    ),
    CapabilitySpec(
        component_type=Engaged,
        known_fields=frozenset(),
        from_yaml=_parse_runtime_marker,
        to_dict=_ser_engaged,
        from_dict=_des_engaged,
    ),
    CapabilitySpec(
        component_type=Mount,
        known_fields=frozenset({"mount"}),
        from_yaml=_parse_mount,
        to_dict=_ser_mount,
        from_dict=_des_mount,
    ),
    CapabilitySpec(
        component_type=Riding,
        known_fields=frozenset(),
        from_yaml=_parse_runtime_marker,
        to_dict=_ser_riding,
        from_dict=_des_riding,
    ),
    CapabilitySpec(
        component_type=Gender,
        known_fields=frozenset({"gender"}),
        from_yaml=_parse_gender,
        to_dict=_ser_gender,
        from_dict=_des_gender,
    ),
]


__all__ = [
    "CAPABILITIES",
    "CAPABILITY_COMPONENT_TYPES",
    "CapabilitySpec",
    "NPC_CAPABILITIES",
    "ROOM_CAPABILITIES",
]
