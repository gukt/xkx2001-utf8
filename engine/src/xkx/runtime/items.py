"""ItemCatalog 过渡层（ADR-0058 方案 B 最小子集）。

greenfield 物品是 ``str item_id``（无 ECS 实体 / 无 ``ItemComp``），LPC 武器物品对象
的 ``weight()``/``name()``/``query("rigidity")``/``unequip()``/``move()``/``set(...)``
等对象方法无直接等价目标（pilot 样本 id=5/8 暴露的缺口）。本模块提供方案 B 过渡：

- 复用扩展 ``Game.item_registry``（[commands.py](commands.py) L77，``dict[str, dict]``）
  作台账后端（单台账，``ItemDef`` 扩展字段 + ``compile_item`` 编译进 dict）。
- 函数族 ``item_weight``/``item_query``/``item_move_to_room``/``item_set``：读属性 +
  move 掉落，写副作用维持现状（per-instance set no-op，规避滚雪球）。
- ``WeaponDef`` schema（机制层，数据后置，对照 LPC ``init_blade(damage, flag)``）。

方案 A 物品实体化（``ItemComp`` + 物品 ``Position`` 组件）留 M3。str item_id 模型不变。

[ADR-0058](../../../docs/adr/ADR-0058-item-catalog-transition-layer.md)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from xkx.runtime.components import RoomComp

if TYPE_CHECKING:
    from xkx.runtime.commands import Game
    from xkx.runtime.ecs import World

_logger = logging.getLogger(__name__)


# ──────────────────────── ItemCatalog 函数族（读属性 + move 掉落） ────────────────────────


def _spec(game: Game, item_id: str) -> dict[str, Any] | None:
    """取 item_registry 台账条目（dict 或 None）。

    向后兼容旧 ``{id: name}`` str 结构（返回 None 走默认值路径）。ADR-0058 §1：复用
    扩展 Game.item_registry 单台账。
    """
    spec = game.item_registry.get(item_id)
    return spec if isinstance(spec, dict) else None


def item_weight(game: Game, item_id: str) -> int:
    """读台账物品级 weight（ADR-0058 §3，LPC ``weapon->weight()`` 等价读）。

    **关键不变量**：物品 weight 是台账字段，**绝不走 dbase key "weight"**（那是角色级
    ``Equipment.encumbrance``，[dbase_map.py](dbase_map.py) L83）。未注册返回 0
    （LPC 未设 set_weight 默认 0）。
    """
    spec = _spec(game, item_id)
    if spec is None:
        return 0
    return int(spec.get("weight", 0))


def item_query(game: Game, item_id: str, key: str) -> Any:
    """读台账物品属性（ADR-0058 §2，LPC ``weapon->query(key)`` 等价读）。

    - ``weapon_prop`` 返回 ``dict[str, int]`` mapping（LPC dbase mapping，wield 遍历
      注入 ``apply/<key>``；ADR-0058 §4：不复用 ``Equipment.weapon_props`` 槽位副本）。
    - 已知字段（weight/value/rigidity/unit/long/material/flag/skill_type/name/aliases
      等）返回台账值。
    - unknown key（不在台账 dict 里）返回 ``None``（非 raise：物品台账是开放 dict，
      "未设属性"与"拼写错误"难区分，返回 None 对齐 LPC ``query`` 未设语义；区别于
      dbase key 的 unknown-raise，因物品属性不走 dbase_map 分类体系）。
    - 未注册 item_id 返回 ``None``。
    """
    spec = _spec(game, item_id)
    if spec is None:
        return None
    return spec.get(key)


def item_move_to_room(game: Game, item_id: str, room_id: str) -> None:
    """把 item_id 加入目标房间地面（ADR-0058 §2，LPC ``ob->move(environment(victim))`` 等价）。

    对照 [commands.py](commands.py) take/drop 的 ``RoomComp.items``（``set[str]``）用法。
    room_id 由调用方传（对齐样本桩 ``move_to_room(item_id, room_id)`` 签名）。房间不存在
    则 no-op（记日志，对齐 LPC move 失败静默）。

    方案 B 限制：物品无 ``Position`` 组件，"掉落"仅体现为 item_id 进入 Room.items
    集合（take 命令可拾取）。物品自身位置态（per-instance）留方案 A M3。
    """
    world: World = game.world
    room_eid = game.room_entities.get(room_id)
    if room_eid is None:
        _logger.debug("item_move_to_room: 房间 %r 不存在，item_id=%r 掉落 no-op", room_id, item_id)
        return
    room = world.get(room_eid, RoomComp)
    if room is None:
        _logger.debug(
            "item_move_to_room: 房间 %r 无 RoomComp，item_id=%r 掉落 no-op",
            room_id,
            item_id,
        )
        return
    room.items.add(item_id)


def item_set(game: Game, item_id: str, key: str, val: Any) -> None:
    """写台账物品属性（ADR-0058 §5，LPC ``ob->set(key, val)`` per-instance 写）。

    **方案 B 维持现状**：no-op + 记日志。LPC ``set("name","断掉的"+name)`` /
    ``set("value",0)`` / ``set("weapon_prop",0)`` 是 per-instance 写（击碎武器改名 +
    贬值 + 清 prop）。方案 B 用 ``item_id`` -> dict 台账，per-instance set 会污染该
    item_id 的全局定义（同名武器全变"断掉的"），滚雪球。故引擎层 item_set 不实现
    per-instance 修改，留方案 A（M3 物品实体化，per-instance 状态由 ItemComp 承接）。

    样本 id=5/8 的 set_name/set_value/set_weapon_prop 在样本桩里是 per-instance dict
    改（仅影响测试注入副本），不进 src/xkx。
    """
    _logger.debug(
        "item_set: 方案 B 维持现状 no-op（item_id=%r key=%r val=%r）；"
        "per-instance 写留方案 A M3",
        item_id,
        key,
        val,
    )


# ──────────────────────── WeaponDef schema（机制层，数据后置） ────────────────────────
# DEPRECATED（ADR-0060 决策 1）：全量武器数据改由 ItemDef YAML 台账承载
# （scenes/wuxia_common/ + scenes/wuxia_<sect>/ 数据层 CPK，items.yaml -> load_items
# -> compile_item 链，ADR-0062 接线进 game.item_registry）。本 schema
# 标量 damage 丢 weapon_prop 子键（speed/dodge，法轮实证），是错误建模。wield 命令批
# 定夺去留：若需强类型武器视图从 ItemDef 台账投影重构，否则彻底删除；SAMPLE_WEAPONS
# 2 样例届时迁为 ItemDef YAML 条目。本批不删代码（避免破坏现有引用）。


class WeaponDef(BaseModel):
    """武器定义 schema（ADR-0058 §6，机制层，数据后置）。

    对照 LPC 武器 ``create()`` + ``init_blade(damage, flag)`` / ``init_sword(damage, flag)``
    （[blade.c](../../../inherit/weapon/blade.c) / [sword.c](../../../inherit/weapon/sword.c)）
    + ``set("rigidity")`` / ``set("skill_type")`` / ``set("value")`` / ``set("material")``
    / ``set_weight(N)`` 习惯。全量武器数据提取（逐文件 ``init_*(N)``）是内容生产工作，
    留后续门派迁移批；本 schema 先落地机制层 + 2 个手填样例（id=5/8 场景武器）。

    字段与 ``ItemDef`` 武器属性字段对齐（damage 走 weapon_prop/damage，rigidity/flag/
    skill_type/weight/value/material 独立字段），WeaponDef 是武器专用的结构化视图
    （从 ItemDef 台账或独立数据源构造）。
    """

    item_id: str  # 对应 ItemDef.id / item_registry key
    name: str  # LPC set_name 第 1 参
    damage: int = 0  # LPC init_blade(damage) / weapon_prop/damage
    rigidity: int = 0  # LPC set("rigidity", N)，击碎判定用
    flag: int = 0  # LPC set("flag", EDGED)，weapon.h 位掩码（TWO_HANDED/SECONDARY/EDGED/...）
    skill_type: str = ""  # LPC set("skill_type", "sword"/"blade")，init_* 设
    weight: int = 0  # LPC set_weight(N)，物品级重量（非角色 encumbrance）
    value: int = 0  # LPC set("value", N)
    material: str = ""  # LPC set("material", "steel")


# ADR-0058 §6：id=5/8 两武器手填样例（验证 schema 可用）。
# - songshan-jian 场景的剑（id=5 样本 next_sword 的 weapon 参数，对照 LPC 剑 set 习惯：
#   sword.c init_sword(damage, flag=EDGED)，skill_type=sword）。
# - shizi 小石子（id=8 样本 bash_weapon 的 ob，对照 [shizi.c](../../../d/taohua/obj/shizi.c)
#   create()：set_name("小石子")/set("value",0)/投掷物；weapon_prop/damage 由 init_throwing
#   设，此处按样本测试注入取 damage=5）。
SAMPLE_WEAPONS: dict[str, WeaponDef] = {
    "songshan-jian": WeaponDef(
        item_id="songshan-jian",
        name="嵩山剑",
        damage=80,
        rigidity=50,
        flag=4,  # EDGED（sword.c init_sword 设 flag | EDGED）
        skill_type="sword",
        weight=5000,
        value=50000,
        material="steel",
    ),
    "shizi": WeaponDef(
        item_id="shizi",
        name="小石子",
        damage=5,  # 对照 shizi.c init_throwing(5) 注释
        rigidity=0,
        flag=0,  # 投掷物无握持标记
        skill_type="throwing",
        weight=100,
        value=0,  # shizi.c set("value", 0)
        material="stone",
    ),
}


def get_weapon_def(item_id: str) -> WeaponDef | None:
    """取手填武器 schema（SAMPLE_WEAPONS）。未注册返回 None。

    生产环境应由全量武器数据台账提供（门派迁移批），此处仅 2 个样例验证 schema。
    """
    return SAMPLE_WEAPONS.get(item_id)
