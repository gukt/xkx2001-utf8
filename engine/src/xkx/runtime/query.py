"""运行时 query/set 接口 + 索引层 + Identity/Position/Inventory 语义。

阶段 2 Wave 1（2.1），对照 LPC F_DBASE 8 函数（[spec/layer_b](_set_spec)）+
F_NAME/F_MOVE 规格。映射到 ECS 组件字段（复用 DBASE_KEY_MAP），拼写错误不
静默（三类区分：mapped/postponed/unknown）。

**greenfield 简化**（ADR-0025 §2 简化台账）：

- 不区分 dbase vs tmp_dbase（无 LPC tmp_dbase static 语义）。``query``/
  ``query_temp`` 行为一致，``set``/``set_temp`` 行为一致。调用方按 LPC 习惯
  使用（marks/ 用 temp 变体，skill/ 用常规），greenfield 映射统一到组件字段。
- 不实现 ``raw`` 参数 / ``evaluate()`` / ``default_ob`` 回退（LPC function 类型
  + master copy 机制，greenfield 无对应概念）。
- 只支持 ``skill/<id>`` / ``marks/<flag>`` 两类路径前缀（不实现完整 treemap）。

[ADR-0025](../../../docs/adr/ADR-0025-query-index-layer.md)
"""

from __future__ import annotations

import builtins
import dataclasses
import warnings
from collections.abc import Iterator
from typing import Any

from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Inventory,
    Marks,
    Position,
    Skills,
)
from xkx.runtime.dbase_map import (
    APPLY_PREFIX,
    APPLY_SUBPATH_MAP,
    SEMANTIC_KEY_MAP,
    DbaseKeyError,
    classify_key,
    resolve_dbase_key,
)
from xkx.runtime.ecs import World

# 模块定义了 ``set`` 函数（LPC F_DBASE 8 函数之一），覆盖内置 ``set`` 类型。
# 需要内置 set/frozenset 处用 ``builtins.set`` / ``builtins.frozenset``。

# LPC query 对未设 key 返回 0（[spec/layer_b](_query_spec) postcondition）；
# greenfield 简单 key 返回 None（组件不存在），路径前缀 dict 返回 0、set 返回 0
_UNSET_DEFAULT = 0


# ──────────────────────── LPC F_DBASE 8 函数 ────────────────────────


def query(world: World, eid: int, key: str) -> Any:
    """读组件字段（LPC ``query(prop, raw=1)`` 语义，ADR-0025 决策 1）。

    - 已映射 key：返回组件字段值（简单 key 标量；``skill/<id>`` dict 查找；
      ``marks/<flag>`` set 成员判断返回 1/0）
    - 后置 key：返回 None + ``warnings.warn``（对应子系统未实现，非 bug）
    - 未知 key（拼写错误）：raise ``DbaseKeyError``（非静默，dissent 2）

    组件不存在时返回 None（LPC dbase 未初始化返回 0；路径前缀返回 0）。
    """
    cls = classify_key(key)
    if cls == "postponed":
        warnings.warn(
            f"query 后置 key {key!r} 未实现（对应子系统后置）",
            stacklevel=2,
        )
        return None
    if cls == "unknown":
        raise DbaseKeyError(
            f"query 未知 key {key!r}（拼写错误或未映射）"
        )
    return _read_field(world, eid, key)


def query_temp(world: World, eid: int, key: str) -> Any:
    """读 temp 变体（LPC ``query_temp`` 语义，ADR-0025 决策 1）。

    greenfield 简化：与 ``query`` 行为一致（无 dbase vs tmp_dbase 分离）。
    调用方按 LPC 习惯用 ``query_temp`` 读 ``marks/``，语义等价。
    """
    return query(world, eid, key)


def set(world: World, eid: int, key: str, val: Any) -> Any:
    """写组件字段（LPC ``set(prop, data)`` 语义，ADR-0025 决策 1）。返回 val。

    - 已映射 key：写组件字段（简单 key ``setattr``；``skill/<id>`` dict 赋值；
      ``marks/<flag>`` val 真值添加/假值移除 flag）
    - 后置 key：raise ``DbaseKeyError``（无组件承接，写无意义）
    - 未知 key：raise ``DbaseKeyError``（拼写错误不静默）

    ``marks/`` 前缀的 Marks 组件不存在时自动创建（对齐 LPC tmp_dbase 自动
    初始化为空 mapping，[spec/layer_b](_set_temp_spec) invariant）。
    """
    cls = classify_key(key)
    if cls == "postponed":
        raise DbaseKeyError(
            f"set 后置 key {key!r} 无组件承接（对应子系统未实现）"
        )
    if cls == "unknown":
        raise DbaseKeyError(
            f"set 未知 key {key!r}（拼写错误或未映射）"
        )
    _write_field(world, eid, key, val)
    return val


def set_temp(world: World, eid: int, key: str, val: Any) -> Any:
    """写 temp 变体（LPC ``set_temp`` 语义，ADR-0025 决策 1）。返回 val。

    greenfield 简化：与 ``set`` 行为一致（无 dbase vs tmp_dbase 分离）。
    """
    return set(world, eid, key, val)


def add(world: World, eid: int, key: str, val: Any) -> Any:
    """增量写（LPC ``add(prop, data)`` 语义：query 旧值 + set 新值）。

    [spec/layer_b](_add_spec) postcondition：无旧值时等同 ``set``；有旧值时
    ``old + data``。支持 int/string/dict 类型；类型不兼容 raise ``TypeError``。
    """
    old = query(world, eid, key)
    new = _add_values(old, val)
    return set(world, eid, key, new)


def add_temp(world: World, eid: int, key: str, val: Any) -> Any:
    """temp 增量写（LPC ``add_temp`` 语义）。greenfield 简化：与 ``add`` 一致。"""
    return add(world, eid, key, val)


def delete(world: World, eid: int, key: str) -> int:
    """删除组件字段（LPC ``delete(prop)`` 语义，ADR-0025 决策 1）。

    - 简单 key：恢复字段默认值（dataclass default），返回 1；组件不存在返回 0
    - ``skill/<id>``：从 dict 移除 key，返回 1/0
    - ``marks/<flag>``：从 set 移除 flag，返回 1/0
    - 后置/未知 key：raise ``DbaseKeyError``
    """
    cls = classify_key(key)
    if cls == "postponed":
        raise DbaseKeyError(
            f"delete 后置 key {key!r} 无组件承接"
        )
    if cls == "unknown":
        raise DbaseKeyError(
            f"delete 未知 key {key!r}"
        )
    mapping = resolve_dbase_key(key)
    assert mapping is not None  # cls == "mapped" 保证
    comp_type, field_name = mapping
    comp = world.get(eid, comp_type)
    if comp is None:
        return 0
    if "/" in key:
        sub_key = key.split("/", 1)[1]
        attr = getattr(comp, field_name)
        if isinstance(attr, dict):
            return 1 if attr.pop(sub_key, None) is not None else 0
        if isinstance(attr, (builtins.set, builtins.frozenset)):
            if sub_key in attr:
                attr.discard(sub_key)
                return 1
            return 0
        return 0
    # 简单 key：恢复 dataclass 字段默认值
    for f in dataclasses.fields(comp_type):
        if f.name == field_name:
            if f.default is not dataclasses.MISSING:
                setattr(comp, field_name, f.default)
            elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                setattr(comp, field_name, f.default_factory())  # type: ignore[misc]
            else:
                setattr(comp, field_name, None)
            return 1
    return 0


def delete_temp(world: World, eid: int, key: str) -> int:
    """删除 temp 变体（LPC ``delete_temp`` 语义）。greenfield 简化：与 ``delete`` 一致。"""
    return delete(world, eid, key)


# ──────────────────────── 内部：字段读写 ────────────────────────


def _equipped_items(equipment: Equipment) -> frozenset[str]:
    """当前装备物品 id 集合（weapon + secondary_weapon + armors 值，排除 None）。

    ``equipped`` 语义 key 的读派生值（ADR-0026 §3，非简单字段）。
    """
    items: builtins.set[str] = builtins.set()
    if equipment.weapon:
        items.add(equipment.weapon)
    if equipment.secondary_weapon:
        items.add(equipment.secondary_weapon)
    items.update(equipment.armors.values())
    return frozenset(items)


def _read_field(world: World, eid: int, key: str) -> Any:
    """读已映射 key 的组件字段（简单 key + 路径前缀 + 语义 key，ADR-0025/0026）。"""
    # 语义 key（equipped）：返回装备物品集合（is_equipped 派生，ADR-0026 §3）
    if key in SEMANTIC_KEY_MAP:
        comp = world.get(eid, SEMANTIC_KEY_MAP[key])
        if comp is None:
            return frozenset()
        if isinstance(comp, Equipment):
            return _equipped_items(comp)
        return None
    mapping = resolve_dbase_key(key)
    if mapping is None:
        # apply/ 已知前缀但未知子路径（通用 apply/{skill}，无存储）-> 返回 0
        if "/" in key and key.split("/", 1)[0] == APPLY_PREFIX:
            return _UNSET_DEFAULT
        return None
    comp_type, field_name = mapping
    comp = world.get(eid, comp_type)
    if comp is None:
        return None
    attr = getattr(comp, field_name)
    if "/" in key:
        sub_key = key.split("/", 1)[1]
        if isinstance(attr, dict):
            # LPC query("skill/axe") 未设返回 0（[spec/layer_b](_query_spec)）
            return attr.get(sub_key, _UNSET_DEFAULT)
        if isinstance(attr, (builtins.set, builtins.frozenset)):
            # marks/ 成员判断：存在 1 不存在 0（LPC query_temp 语义）
            return 1 if sub_key in attr else 0
    return attr


def _write_field(world: World, eid: int, key: str, val: Any) -> None:
    """写已映射 key 的组件字段（简单 key + 路径前缀，ADR-0025 决策 1）。"""
    # 语义 key（equipped）：不支持 set（装备走 wield/wear，ADR-0026 §3）
    if key in SEMANTIC_KEY_MAP:
        raise DbaseKeyError(
            f"set 语义 key {key!r} 不支持直接 set（装备走 wield/wear）"
        )
    mapping = resolve_dbase_key(key)
    if mapping is None:
        # apply/ 已知前缀但未知子路径（无存储）-> raise（通用 apply 修正后置 M3）
        if "/" in key and key.split("/", 1)[0] == APPLY_PREFIX:
            raise DbaseKeyError(
                f"set apply/ 未知子路径 {key!r} 无存储"
                "（通用 apply 修正后置 M3）"
            )
        return
    comp_type, field_name = mapping
    if "/" in key:
        sub_key = key.split("/", 1)[1]
        comp = world.get(eid, comp_type)
        if comp is None:
            # marks/ 自动创建 Marks 组件（LPC tmp_dbase 自动初始化）
            if comp_type is Marks:
                comp = Marks()
                world.add(eid, comp)
            else:
                raise DbaseKeyError(
                    f"实体 {eid} 无 {comp_type.__name__} 组件，"
                    f"无法 set {key!r}"
                )
        attr = getattr(comp, field_name)
        if isinstance(attr, dict):
            attr[sub_key] = val
        elif isinstance(attr, (builtins.set, builtins.frozenset)):
            # marks/ val 真值添加 flag，假值移除（LPC set_temp 语义）
            if val:
                attr.add(sub_key)
            else:
                attr.discard(sub_key)
        else:
            # apply/ 前缀分发到标量字段（apply/attack -> apply_attack）
            setattr(comp, field_name, val)
        return
    comp = world.get(eid, comp_type)
    if comp is None:
        raise DbaseKeyError(
            f"实体 {eid} 无 {comp_type.__name__} 组件，无法 set {key!r}"
        )
    setattr(comp, field_name, val)


def _add_values(old: Any, val: Any) -> Any:
    """LPC add 语义的值合并（[spec/layer_b](_add_spec) postcondition）。"""
    if old is None:
        return val
    if isinstance(old, bool) or isinstance(val, bool):
        # bool 是 int 子类但 add 语义不适用布尔（LPC 不做布尔加法）
        raise TypeError(
            f"add 不支持 bool 类型: {type(old).__name__} + {type(val).__name__}"
        )
    if isinstance(old, int) and isinstance(val, int):
        return old + val
    if isinstance(old, str) and isinstance(val, str):
        return old + val
    if isinstance(old, dict) and isinstance(val, dict):
        return {**old, **val}
    raise TypeError(
        f"add 类型不兼容: {type(old).__name__} + {type(val).__name__}"
    )


# ──────────────────────── 索引层（ADR-0025 决策 3） ────────────────────────


def entities_with_family(world: World, family: str) -> Iterator[int]:
    """按门派查实体（Attributes.family，LPC shanmen.c 守卫判断）。

    线性扫描 O(n)（ADR-0025 决策 3：1000 实体规模足够，预建索引后置）。
    """
    for eid in world.entities_with(Attributes):
        attrs = world.get(eid, Attributes)
        if attrs and attrs.family == family:
            yield eid


def entities_by_prototype(world: World, prototype_id: str) -> Iterator[int]:
    """按 NPC def id 查实体（Identity.prototype_id，LPC clone 追踪）。

    线性扫描 O(n)；prototype_id 空字符串不匹配（避免误命中无 prototype 的实体）。
    """
    if not prototype_id:
        return
    for eid in world.entities_with(Identity):
        ident = world.get(eid, Identity)
        if ident and ident.prototype_id == prototype_id:
            yield eid


def find_in_room(world: World, room_id: str, keyword: str) -> int | None:
    """房间内按 name/alias/id 查实体（LPC ``present(str, room_ob)`` 语义）。

    匹配优先级：name 精确 > aliases 含 keyword（对齐 LPC ``id(str)``）。
    """
    for eid in world.entities_in_room(room_id):
        ident = world.get(eid, Identity)
        if ident and id_match(ident, keyword):
            return eid
    return None


def find_item(world: World, eid: int, keyword: str) -> str | None:
    """玩家物品栏按 id 查物品（LPC ``present(str, me)`` 语义）。

    当前 Inventory.items 是 id 集合（无 ItemDef alias），只支持 id 精确匹配。
    物品 alias 匹配后置（物品系统，阶段 2.3+）。
    """
    inv = world.get(eid, Inventory)
    if inv is None:
        return None
    if keyword in inv.items:
        return keyword
    return None


# ──────────────────────── Identity/Position/Inventory 语义 ────────────────────────


def id_match(identity: Identity, keyword: str) -> bool:
    """keyword 匹配 name 或 aliases（LPC ``id(str)`` 语义，[spec/layer_b](_id_spec)）。

    apply/id 掩码后置（greenfield 无 apply 机制）；可见性检查后置 2.5 visible 三级。
    """
    return keyword == identity.name or keyword in identity.aliases


def short(identity: Identity) -> str:
    """基础 short 格式：name(id)（LPC ``short(raw=1)`` 语义，[spec/layer_b](_short_spec)）。

    状态修饰（打坐/鬼气/断线/昏迷）后置 2.5 TitleSystem。id 取 aliases[0]
    （LPC set_name 的 id[0] 主 ID）；无 aliases 回退 prototype_id。
    """
    id_str = identity.aliases[0] if identity.aliases else identity.prototype_id
    return f"{identity.name}({id_str})"


def move_to(world: World, eid: int, room_id: str) -> None:
    """切换 Position.room_id（LPC ``move(dest)`` 核心效果，[spec/layer_b](_move_spec)）。

    负重级联 + 自动 look 后置 2.3 Attribute/Skill/Equipment（F_MOVE weight/
    encumbrance）。Position 组件不存在时自动创建（LPC move 到新环境）。
    """
    pos = world.get(eid, Position)
    if pos is None:
        world.add(eid, Position(room_id=room_id))
    else:
        pos.room_id = room_id


def environment(world: World, eid: int) -> str | None:
    """返回 Position.room_id（LPC ``environment()`` 语义）。无 Position 返回 None。"""
    pos = world.get(eid, Position)
    return pos.room_id if pos else None


def present_item(world: World, eid: int, keyword: str) -> str | None:
    """物品栏按 id 查物品（LPC ``present(str, me)`` 语义）。委托 ``find_item``。"""
    return find_item(world, eid, keyword)


def all_inventory(world: World, eid: int) -> set[str]:
    """返回 Inventory.items 副本（LPC ``all_inventory()`` 语义）。

    返回副本（防外部修改组件内部状态）；无 Inventory 返回空集合。
    """
    inv = world.get(eid, Inventory)
    return builtins.set(inv.items) if inv else builtins.set()


# ──────────────────────── ModifierStack 求值（ADR-0026） ────────────────────────


def query_skill(world: World, eid: int, skill_id: str, raw: bool = False) -> int:
    """技能有效等级（对照 LPC feature/skill.c:94-109 query_skill，ADR-0026 §2）。

    三层叠加（非 raw 模式）：
    1. ``apply/{skill}`` 修正：已知 6 个标量（attack/dodge/parry/damage/armor/
       speed）读 Skills.apply_*；其他 skill 无对应标量，apply 修正=0
    2. 永久基础值：``levels[skill] // 2``（半值计入有效等级）
    3. 映射技能全值：``levels[skill_map[skill]]``（skill_map 映射）

    raw 模式返回 ``levels[skill]`` 原值。无 Skills 组件返回 0。通用
    ``apply/{skill}`` 开放存储后置 M3（greenfield 只 6 个标量，简化台账）。
    """
    skills = world.get(eid, Skills)
    if skills is None:
        return 0
    if raw:
        return skills.levels.get(skill_id, 0)
    # 1. apply/{skill} 修正（已知 6 个标量；其他 skill 无对应标量 -> 0）
    apply_field = APPLY_SUBPATH_MAP.get(skill_id)
    apply_val = getattr(skills, apply_field) if apply_field else 0
    # 2. 永久基础值（半值）+ 3. 映射技能全值（skill_map）
    base = skills.levels.get(skill_id, 0) // 2
    mapped = skills.levels.get(skills.skill_map.get(skill_id, ""), 0)
    return apply_val + base + mapped


def effective_apply(world: World, eid: int, apply_key: str) -> int:
    """apply_* 有效值（装备加成 + condition 修正叠加，ADR-0026 §1）。

    apply_key 为已知 6 个（attack/dodge/parry/damage/armor/speed）之一，返回
    对应 Skills.apply_* 标量（equip 已注入装备加成，condition 由 EffectComp 驱动
    修正）。未知 apply_key 返回 0（无对应标量）。
    """
    skills = world.get(eid, Skills)
    if skills is None:
        return 0
    field = APPLY_SUBPATH_MAP.get(apply_key)
    return getattr(skills, field) if field else 0


def effective_skill_level(
    world: World, eid: int, skill_id: str, raw: bool = False
) -> int:
    """技能有效等级（ModifierStack 求值入口，ADR-0026 §4）。

    委托 ``query_skill``。combat 走 CombatantSnapshot 标量（ADR-0023 第 4 项
    定稿，resolve_attack 不调本函数）；本函数供运行时非 combat 路径查询
    （NPC AI / 命令 / 调试）。
    """
    return query_skill(world, eid, skill_id, raw=raw)
