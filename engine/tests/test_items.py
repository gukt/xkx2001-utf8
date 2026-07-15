"""ItemCatalog 过渡层测试（ADR-0058 方案 B 最小子集）。

覆盖：
- item_weight/item_query/item_move_to_room/item_set 函数族。
- weight 双重语义区分（物品台账 weight vs 角色 dbase key "weight" -> Equipment.encumbrance）。
- weapon_prop 返回 mapping（非 scalar，不复用 Equipment.weapon_props 槽位副本）。
- WeaponDef schema + 2 手填武器（songshan-jian / shizi）。
- 写副作用维持现状（item_set no-op，台账全局 item_id 定义不变）。
"""

from __future__ import annotations

from xkx.runtime.commands import Game
from xkx.runtime.components import Equipment, RoomComp
from xkx.runtime.ecs import World
from xkx.runtime.items import (
    SAMPLE_WEAPONS,
    WeaponDef,
    get_weapon_def,
    item_move_to_room,
    item_query,
    item_set,
    item_weight,
)
from xkx.runtime.query import query
from xkx.runtime.query import set as dbase_set


def _make_game() -> tuple[Game, str]:
    """构造最小 Game：1 房间 + item_registry（武器 songshan-jian + 消耗品 suyou_guan）。"""
    world = World()
    room_eid = world.new_entity()
    room_id = "test/room"
    world.add(room_eid, RoomComp(room_id=room_id, short="测试房间", long=""))
    room_entities = {room_id: room_eid}
    item_registry: dict[str, dict] = {
        "songshan-jian": {
            "id": "songshan-jian",
            "name": "嵩山剑",
            "aliases": ["songshan jian", "jian"],
            "drink_supply": 0,
            "food_supply": 0,
            "jing_recover": 0,
            "qi_recover": 0,
            "read_skill": "",
            "weight": 5000,
            "value": 50000,
            "rigidity": 50,
            "weapon_prop": {"damage": 80, "force": 20},
            "unit": "把",
            "long": "一把嵩山剑。",
            "material": "steel",
            "flag": 4,
            "skill_type": "sword",
        },
        "suyou_guan": {
            "id": "suyou_guan",
            "name": "酥油罐",
            "aliases": ["suyou guan"],
            "drink_supply": 10,
            "food_supply": 5,
            "jing_recover": 3,
            "qi_recover": 0,
            "read_skill": "",
            "weight": 200,
            "value": 100,
            "rigidity": 0,
            "weapon_prop": {},
            "unit": "罐",
            "long": "",
            "material": "",
            "flag": 0,
            "skill_type": "",
        },
    }
    game = Game(world, room_entities, rules=[], item_registry=item_registry)
    return game, room_id


# ──────────────────────── item_weight ────────────────────────


def test_item_weight_reads_catalog() -> None:
    """item_weight 读台账物品级 weight（ADR-0058 §3）。"""
    game, _ = _make_game()
    assert item_weight(game, "songshan-jian") == 5000
    assert item_weight(game, "suyou_guan") == 200


def test_item_weight_unregistered_returns_zero() -> None:
    """未注册 item_id 返回 0（LPC 未设 set_weight 默认 0）。"""
    game, _ = _make_game()
    assert item_weight(game, "nonexistent-item") == 0


# ──────────────────────── item_query ────────────────────────


def test_item_query_reads_known_fields() -> None:
    """item_query 读台账已知字段。"""
    game, _ = _make_game()
    assert item_query(game, "songshan-jian", "name") == "嵩山剑"
    assert item_query(game, "songshan-jian", "value") == 50000
    assert item_query(game, "songshan-jian", "rigidity") == 50
    assert item_query(game, "songshan-jian", "unit") == "把"
    assert item_query(game, "songshan-jian", "material") == "steel"
    assert item_query(game, "songshan-jian", "flag") == 4
    assert item_query(game, "songshan-jian", "skill_type") == "sword"


def test_item_query_weapon_prop_returns_mapping() -> None:
    """item_query('weapon_prop') 返回 dict mapping（ADR-0058 §4，非 scalar）。

    对照 LPC equip.c L60 ``mapp(weapon_prop = query("weapon_prop"))``，wield 遍历
    keys 注入 apply/<key>。不复用 Equipment.weapon_props（per-slot 副本）。
    """
    game, _ = _make_game()
    wp = item_query(game, "songshan-jian", "weapon_prop")
    assert isinstance(wp, dict)
    assert wp == {"damage": 80, "force": 20}
    # 消耗品 weapon_prop 空 mapping
    assert item_query(game, "suyou_guan", "weapon_prop") == {}


def test_item_query_unknown_key_returns_none() -> None:
    """unknown key 返回 None（非 raise，ADR-0058 §2：开放 dict 未设语义）。"""
    game, _ = _make_game()
    assert item_query(game, "songshan-jian", "nonexistent_field") is None


def test_item_query_unregistered_item_returns_none() -> None:
    """未注册 item_id 返回 None。"""
    game, _ = _make_game()
    assert item_query(game, "nonexistent-item", "weight") is None


# ──────────────────────── item_move_to_room ────────────────────────


def test_item_move_to_room_adds_to_room_items() -> None:
    """item_move_to_room 把 item_id 加入 RoomComp.items（ADR-0058 §2）。"""
    game, room_id = _make_game()
    room_eid = game.room_entities[room_id]
    room = game.world.get(room_eid, RoomComp)
    assert room is not None
    assert room.items == set()
    item_move_to_room(game, "songshan-jian", room_id)
    assert "songshan-jian" in room.items


def test_item_move_to_room_nonexistent_room_noop() -> None:
    """房间不存在 no-op（不 raise，对齐 LPC move 失败静默）。"""
    game, _ = _make_game()
    item_move_to_room(game, "songshan-jian", "no/such/room")  # 不 raise


# ──────────────────────── weight 双重语义区分（关键不变量 §3） ────────────────────────


def test_weight_dual_semantics_character_vs_item() -> None:
    """weight 双重语义：物品台账 weight vs 角色 dbase key "weight"（ADR-0058 §3）。

    - 物品 weight 走 item_weight(game, item_id)（台账字段）。
    - 角色 weight 走 dbase key "weight" -> Equipment.encumbrance
      （query/set 经 dbase_map.py:83）。
    二者不可混：set(eid, "weight", N) 写角色 encumbrance，不影响 item_weight。
    """
    game, _ = _make_game()
    # 角色实体 + Equipment（角色负重标量）
    char_eid = game.world.new_entity()
    game.world.add(char_eid, Equipment(encumbrance=0, max_encumbrance=10000))

    # 物品 weight：走台账
    assert item_weight(game, "songshan-jian") == 5000
    # 角色 weight：走 dbase key "weight" -> Equipment.encumbrance（初始 0）
    assert query(game.world, char_eid, "weight") == 0

    # 写角色 weight -> Equipment.encumbrance（角色负重），不影响物品台账
    dbase_set(game.world, char_eid, "weight", 3000)
    assert query(game.world, char_eid, "weight") == 3000  # 角色 encumbrance 变 3000
    equip = game.world.get(char_eid, Equipment)
    assert equip is not None
    assert equip.encumbrance == 3000  # 确认走的是 Equipment.encumbrance

    # 物品 weight 不受角色 weight 写影响（两条路径分离）
    assert item_weight(game, "songshan-jian") == 5000
    # 反之，item_weight 不写 Equipment.encumbrance（读台账，无角色副作用）
    assert equip.encumbrance == 3000  # 仍是 3000，未被 item_weight 读动


def test_item_weight_does_not_use_dbase_key_weight() -> None:
    """物品 weight 绝不走 dbase key "weight"（ADR-0058 不变量 1）。

    一个无 Equipment 的角色实体，query(eid, "weight") 返回 None（无组件），
    而 item_weight(item_id) 照常读台账返回物品重量，二者互不干扰。
    """
    game, _ = _make_game()
    char_eid = game.world.new_entity()  # 无 Equipment 组件
    # 角色 weight 无组件 -> None（query 组件不存在返回 None）
    assert query(game.world, char_eid, "weight") is None
    # 物品 weight 走台账，与角色 dbase 无关
    assert item_weight(game, "songshan-jian") == 5000


# ──────────────────────── 写副作用维持现状（ADR-0058 §5） ────────────────────────


def test_item_set_is_noop_global_definition_unchanged() -> None:
    """item_set no-op：台账全局 item_id 定义不变（规避方案 B 滚雪球）。

    LPC set("name","断掉的"+name)/set("value",0)/set("weapon_prop",0) 是 per-instance
    写。方案 B 用 item_id->dict 台账，per-instance set 会污染全局定义（同名武器全变
    "断掉的"）。故 item_set no-op，per-instance 语义留方案 A M3。
    """
    game, _ = _make_game()
    # 原值
    assert item_query(game, "songshan-jian", "name") == "嵩山剑"
    assert item_query(game, "songshan-jian", "value") == 50000
    assert item_query(game, "songshan-jian", "weapon_prop") == {"damage": 80, "force": 20}

    # item_set 不产生副作用（no-op）
    item_set(game, "songshan-jian", "name", "断掉的嵩山剑")
    item_set(game, "songshan-jian", "value", 0)
    item_set(game, "songshan-jian", "weapon_prop", 0)

    # 台账全局定义不变
    assert item_query(game, "songshan-jian", "name") == "嵩山剑"
    assert item_query(game, "songshan-jian", "value") == 50000
    assert item_query(game, "songshan-jian", "weapon_prop") == {"damage": 80, "force": 20}


# ──────────────────────── WeaponDef schema + 2 手填武器（ADR-0058 §6） ────────────────────────


def test_weapon_def_schema_construction() -> None:
    """WeaponDef schema 可构造（对照 LPC init_blade(damage, flag) + set 习惯）。"""
    w = WeaponDef(
        item_id="test-blade",
        name="测试刀",
        damage=20,
        rigidity=30,
        flag=4,  # EDGED
        skill_type="blade",
        weight=7000,
        value=1000,
        material="steel",
    )
    assert w.item_id == "test-blade"
    assert w.damage == 20
    assert w.rigidity == 30
    assert w.flag == 4
    assert w.skill_type == "blade"
    assert w.weight == 7000
    assert w.value == 1000
    assert w.material == "steel"


def test_weapon_def_defaults() -> None:
    """WeaponDef 默认值（仅 item_id/name 必填，其余 0/空）。"""
    w = WeaponDef(item_id="x", name="x")
    assert w.damage == 0
    assert w.rigidity == 0
    assert w.flag == 0
    assert w.skill_type == ""
    assert w.weight == 0
    assert w.value == 0
    assert w.material == ""


def test_sample_weapon_songshan_jian() -> None:
    """id=5 场景武器 songshan-jian 手填数据（对照 LPC sword.c init_sword）。"""
    w = get_weapon_def("songshan-jian")
    assert w is not None
    assert w.name == "嵩山剑"
    assert w.damage == 80
    assert w.rigidity == 50
    assert w.flag == 4  # EDGED（sword.c init_sword 设 flag | EDGED）
    assert w.skill_type == "sword"
    assert w.weight == 5000
    assert w.value == 50000
    assert w.material == "steel"


def test_sample_weapon_shizi() -> None:
    """id=8 场景武器 shizi 小石子手填数据（对照 shizi.c create()）。"""
    w = get_weapon_def("shizi")
    assert w is not None
    assert w.name == "小石子"
    assert w.damage == 5  # 对照 shizi.c init_throwing(5)
    assert w.rigidity == 0
    assert w.flag == 0  # 投掷物无握持标记
    assert w.skill_type == "throwing"
    assert w.weight == 100
    assert w.value == 0  # shizi.c set("value", 0)
    assert w.material == "stone"


def test_sample_weapons_count() -> None:
    """SAMPLE_WEAPONS 含 2 个手填样例（songshan-jian / shizi）。"""
    assert set(SAMPLE_WEAPONS.keys()) == {"songshan-jian", "shizi"}


def test_get_weapon_def_unregistered_returns_none() -> None:
    """未注册武器返回 None。"""
    assert get_weapon_def("nonexistent-weapon") is None


# ──────────────────────── ItemDef 扩展字段编译进 item_registry（ADR-0058 §1） ────


def test_item_def_extended_fields_compile_to_registry() -> None:
    """ItemDef 扩展字段经 compile_item 编译进 item_registry dict（单台账收敛）。

    确认 ADR-0058 §1：ItemDef 扩展字段 + compile_item 编译进 dict，item_registry
    自然带这些键，drink/take/give 等读 item_registry 的命令语义不变（新字段带默认值）。
    """
    from xkx.dsl.ir import compile_item
    from xkx.dsl.layer0 import ItemDef

    item = ItemDef(
        id="test-weapon",
        name="测试剑",
        weight=3000,
        value=20000,
        rigidity=40,
        weapon_prop={"damage": 60},
        unit="把",
        material="iron",
        flag=4,
        skill_type="sword",
    )
    ir = compile_item(item)
    assert ir["kind"] == "item"
    # 扩展字段编译进 dict
    assert ir["weight"] == 3000
    assert ir["value"] == 20000
    assert ir["rigidity"] == 40
    assert ir["weapon_prop"] == {"damage": 60}
    assert ir["unit"] == "把"
    assert ir["material"] == "iron"
    assert ir["flag"] == 4
    assert ir["skill_type"] == "sword"
    # 原 8 字段不破坏
    assert ir["id"] == "test-weapon"
    assert ir["name"] == "测试剑"
    assert ir["drink_supply"] == 0  # 默认值


def test_item_def_extended_fields_defaults_backward_compatible() -> None:
    """ItemDef 扩展字段默认值向后兼容（仅 id+name 必填，不破坏旧 YAML）。"""
    from xkx.dsl.layer0 import ItemDef

    item = ItemDef(id="x", name="x")
    assert item.weight == 0
    assert item.value == 0
    assert item.rigidity == 0
    assert item.weapon_prop == {}
    assert item.unit == ""
    assert item.long == ""
    assert item.material == ""
    assert item.flag == 0
    assert item.skill_type == ""
