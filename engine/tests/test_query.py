"""Query/索引层测试（阶段 2 Wave 1 / 2.1，ADR-0025）。

覆盖：
- LPC F_DBASE 8 函数（query/set/add/delete + temp 变体）：简单 key + 路径前缀
- 未映射 key 三类处理（mapped/postponed/unknown，dissent 2 拼写错误不静默）
- 索引层：entities_with_family / entities_by_prototype / find_in_room / find_item
- Identity/Position/Inventory 语义：id_match / short / move_to / environment /
  present_item / all_inventory
- hypothesis 属性测试：路径前缀往返 + key 三类分类 + add 增量 + marks/ 往返
- marks/ 自动创建 Marks 组件（对齐 LPC tmp_dbase 自动初始化）

[ADR-0025](../../../docs/adr/ADR-0025-query-index-layer.md)
[spec/layer_b](_set_spec)/[_query_spec]/[_delete_spec]/[_add_spec) + temp 变体
"""

from __future__ import annotations

import builtins
import warnings

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xkx.runtime.components import (
    Attributes,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    Skills,
    Vitals,
)
from xkx.runtime.dbase_map import (
    DBASE_KEY_MAP,
    POSTPONED_KEYS,
    DbaseKeyError,
    classify_key,
    is_postponed,
)
from xkx.runtime.ecs import World
from xkx.runtime.query import (
    add,
    add_temp,
    all_inventory,
    delete,
    delete_temp,
    entities_by_prototype,
    entities_with_family,
    environment,
    find_in_room,
    find_item,
    id_match,
    move_to,
    present_item,
    query,
    query_temp,
    set,
    set_temp,
    short,
)
from xkx.runtime.world import build_world

# ---- 测试辅助 ----

# 最小 IR（build_world 需要至少一个房间），player 在此房间内
_MIN_IR: dict = {
    "rooms": [
        {"id": "city/street", "short": "街道", "long": "一条热闹的街道。", "exits": {}},
        {"id": "city/square", "short": "广场", "long": "宽敞的广场。", "exits": {}},
    ],
    "npcs": [],
}


def _make_world_with_player() -> tuple[World, int]:
    """构建带完整组件的玩家实体（spawn_player 等价，本文件自包含）。"""
    world, _, _ = build_world(_MIN_IR)
    eid = world.new_entity()
    world.add(eid, Identity(name="测试玩家", aliases=["player", "ceshi"], is_player=True))
    world.add(eid, Position(room_id="city/street"))
    world.add(eid, Attributes(str_=20, dex_=20, int_=20, con_=20, age=22, family="丐帮"))
    world.add(
        eid,
        Vitals(
            qi=200,
            max_qi=200,
            eff_qi=200,
            jing=150,
            max_jing=150,
            jingli=200,
            max_jingli=200,
        ),
    )
    world.add(eid, Progression(combat_exp=500))
    world.add(eid, Skills(levels={"unarmed": 30, "dodge": 20}))
    world.add(eid, Inventory(items={"sword", "pill"}))
    world.add(eid, Marks(flags={"已拜师"}))
    return world, eid


def _make_world_with_npc(
    *,
    name: str = "葛伦布",
    aliases: list[str] | None = None,
    family: str = "",
    prototype_id: str = "city/npc/ge",
    room_id: str = "city/street",
) -> tuple[World, int]:
    """构建带 Identity/Position/Attributes 的 NPC 实体。"""
    world, _, _ = build_world(_MIN_IR)
    eid = world.new_entity()
    world.add(
        eid,
        Identity(
            name=name,
            aliases=aliases if aliases is not None else ["ge lunbu"],
            prototype_id=prototype_id,
        ),
    )
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Attributes(family=family))
    return world, eid


# ═══════════════════ 1. LPC F_DBASE 8 函数 ═══════════════════


# ---- query ----


def test_query_simple_key_qi() -> None:
    """query("qi") -> Vitals.qi（简单 key 标量）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "qi") == 200


def test_query_simple_key_combat_exp() -> None:
    """query("combat_exp") -> Progression.combat_exp。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "combat_exp") == 500


def test_query_simple_key_name() -> None:
    """query("name") -> Identity.name。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "name") == "测试玩家"


def test_query_skill_path_set() -> None:
    """query("skill/unarmed") -> Skills.levels["unarmed"]（路径前缀，已设值）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "skill/unarmed") == 30


def test_query_skill_path_unset_returns_zero() -> None:
    """query("skill/axe") 未设返回 0（LPC query postcondition：未设 key 返回 0）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "skill/axe") == 0


def test_query_marks_present_returns_one() -> None:
    """query("marks/已拜师") flag 存在返回 1（LPC query_temp marks 语义）。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "marks/已拜师") == 1


def test_query_marks_absent_returns_zero() -> None:
    """query("marks/不存在") flag 不存在返回 0。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "marks/不存在") == 0


def test_query_component_absent_returns_none() -> None:
    """组件不存在时简单 key 返回 None（greenfield，LPC 返回 0）。"""
    world, _ = _make_world_with_player()
    # 实体无 Vitals 组件
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸实体"))
    assert query(world, bare_eid, "qi") is None


# ---- query_temp（与 query 一致）----


def test_query_temp_equals_query() -> None:
    """greenfield 不区分 dbase/tmp_dbase，query_temp 与 query 行为一致。"""
    world, eid = _make_world_with_player()
    assert query_temp(world, eid, "qi") == query(world, eid, "qi") == 200
    assert query_temp(world, eid, "skill/unarmed") == 30
    assert query_temp(world, eid, "marks/已拜师") == 1
    assert query_temp(world, eid, "marks/不存在") == 0


# ---- set ----


def test_set_simple_key_returns_val_and_writes() -> None:
    """set("qi", 50) 写 Vitals.qi + 返回 val。"""
    world, eid = _make_world_with_player()
    assert set(world, eid, "qi", 50) == 50
    assert query(world, eid, "qi") == 50
    assert world.get(eid, Vitals).qi == 50


def test_set_skill_path_writes_dict() -> None:
    """set("skill/axe", 40) 写 Skills.levels["axe"]。"""
    world, eid = _make_world_with_player()
    assert set(world, eid, "skill/axe", 40) == 40
    assert query(world, eid, "skill/axe") == 40
    assert world.get(eid, Skills).levels["axe"] == 40


def test_set_marks_truthy_adds_flag() -> None:
    """set("marks/X", 1) 真值添加 flag。"""
    world, eid = _make_world_with_player()
    assert set(world, eid, "marks/新标记", 1) == 1
    assert "新标记" in world.get(eid, Marks).flags
    assert query(world, eid, "marks/新标记") == 1


def test_set_marks_falsy_removes_flag() -> None:
    """set("marks/X", 0) 假值移除 flag。"""
    world, eid = _make_world_with_player()
    assert set(world, eid, "marks/已拜师", 0) == 0
    assert "已拜师" not in world.get(eid, Marks).flags
    assert query(world, eid, "marks/已拜师") == 0


# ---- set_temp（与 set 一致）----


def test_set_temp_equals_set() -> None:
    """greenfield 不区分 set/set_temp，行为一致。"""
    world, eid = _make_world_with_player()
    assert set_temp(world, eid, "qi", 88) == 88
    assert query(world, eid, "qi") == 88
    assert set_temp(world, eid, "marks/temp标记", 1) == 1
    assert "temp标记" in world.get(eid, Marks).flags


# ---- add ----


def test_add_int_increment() -> None:
    """add("qi", 10) 等价 query 旧值 + set 新值。"""
    world, eid = _make_world_with_player()
    assert query(world, eid, "qi") == 200
    assert add(world, eid, "qi", 10) == 210
    assert query(world, eid, "qi") == 210


def test_add_int_negative() -> None:
    """add 支持负增量（qi -50）。"""
    world, eid = _make_world_with_player()
    assert add(world, eid, "qi", -50) == 150
    assert query(world, eid, "qi") == 150


def test_add_string_concat() -> None:
    """add string 拼接（LPC add 字符串语义）。"""
    world, eid = _make_world_with_player()
    set(world, eid, "name", "前缀")
    assert add(world, eid, "name", "后缀") == "前缀后缀"
    assert query(world, eid, "name") == "前缀后缀"


def test_add_dict_merge() -> None:
    """add dict 合并（LPC add mapping 语义，inquiry 是 NpcBehavior.inquiry dict）。"""
    world, eid = _make_world_with_player()
    world.add(eid, NpcBehavior(inquiry={"a": "1"}))
    # add("inquiry", {"b": "2"}) 合并两个 dict
    result = add(world, eid, "inquiry", {"b": "2"})
    assert result == {"a": "1", "b": "2"}
    assert query(world, eid, "inquiry") == {"a": "1", "b": "2"}


def test_add_none_old_equals_set() -> None:
    """旧值 None 时 add 等同 set（LPC add postcondition）。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    # 无 Vitals，query("qi") 返回 None
    assert query(world, bare_eid, "qi") is None
    # add 时 None 旧值 -> set 语义，但 _write_field 需要组件存在
    # 无 Vitals 组件时 set("qi") raise DbaseKeyError（无组件承接）
    with pytest.raises(DbaseKeyError):
        add(world, bare_eid, "qi", 10)


def test_add_incompatible_types_raise_typeerror() -> None:
    """类型不兼容 raise TypeError（int + str）。"""
    world, eid = _make_world_with_player()
    with pytest.raises(TypeError):
        add(world, eid, "qi", "字符串")  # int + str


def test_add_bool_rejected() -> None:
    """bool 是 int 子类但 add 不做布尔加法，raise TypeError。"""
    world, eid = _make_world_with_player()
    with pytest.raises(TypeError):
        add(world, eid, "qi", True)


# ---- add_temp（与 add 一致）----


def test_add_temp_equals_add() -> None:
    """greenfield 不区分 add/add_temp，行为一致。"""
    world, eid = _make_world_with_player()
    assert add_temp(world, eid, "qi", 5) == 205
    assert query(world, eid, "qi") == 205


# ---- delete ----


def test_delete_simple_key_restores_default() -> None:
    """delete("qi") 恢复 dataclass 默认值（Vitals.qi default=100）。"""
    world, eid = _make_world_with_player()
    set(world, eid, "qi", 50)
    assert delete(world, eid, "qi") == 1
    # Vitals.qi 默认值 100（dataclass field default）
    assert query(world, eid, "qi") == 100


def test_delete_skill_path_removes_key() -> None:
    """delete("skill/unarmed") 从 Skills.levels 移除 key，返回 1。"""
    world, eid = _make_world_with_player()
    assert "unarmed" in world.get(eid, Skills).levels
    assert delete(world, eid, "skill/unarmed") == 1
    assert "unarmed" not in world.get(eid, Skills).levels
    # 移除后 query 返回 0（未设默认）
    assert query(world, eid, "skill/unarmed") == 0


def test_delete_skill_path_absent_returns_zero() -> None:
    """delete 未设的 skill key 返回 0。"""
    world, eid = _make_world_with_player()
    assert delete(world, eid, "skill/axe") == 0


def test_delete_marks_removes_flag() -> None:
    """delete("marks/已拜师") 从 Marks.flags 移除 flag，返回 1。"""
    world, eid = _make_world_with_player()
    assert "已拜师" in world.get(eid, Marks).flags
    assert delete(world, eid, "marks/已拜师") == 1
    assert "已拜师" not in world.get(eid, Marks).flags


def test_delete_marks_absent_returns_zero() -> None:
    """delete 未设的 marks flag 返回 0。"""
    world, eid = _make_world_with_player()
    assert delete(world, eid, "marks/不存在") == 0


def test_delete_component_absent_returns_zero() -> None:
    """组件不存在时 delete 返回 0（LPC delete 无 key 返回 0）。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert delete(world, bare_eid, "qi") == 0


# ---- delete_temp（与 delete 一致）----


def test_delete_temp_equals_delete() -> None:
    """greenfield 不区分 delete/delete_temp，行为一致。"""
    world, eid = _make_world_with_player()
    assert delete_temp(world, eid, "marks/已拜师") == 1
    assert query(world, eid, "marks/已拜师") == 0


# ═══════════════════ 2. 未映射 key 三类处理（dissent 2） ═══════════════════


def test_classify_key_mapped() -> None:
    """已映射 key（简单 + 路径前缀）分类为 mapped。"""
    assert classify_key("qi") == "mapped"
    assert classify_key("combat_exp") == "mapped"
    assert classify_key("name") == "mapped"
    assert classify_key("skill/axe") == "mapped"
    assert classify_key("marks/酥") == "mapped"


def test_classify_key_postponed() -> None:
    """后置 key 分类为 postponed。"""
    assert classify_key("title") == "postponed"
    assert classify_key("equipped") == "postponed"
    assert classify_key("shen") == "postponed"


def test_classify_key_unknown() -> None:
    """未知 key（拼写错误）分类为 unknown。"""
    assert classify_key("cobmat_exp") == "unknown"  # combat_exp 拼写错误
    assert classify_key("nosuchkey") == "unknown"
    assert classify_key("env/immortal") == "unknown"  # 路径但前缀未映射


def test_is_postponed_true_false() -> None:
    """is_postponed 判断正确。"""
    assert is_postponed("title") is True
    assert is_postponed("equipped") is True
    assert is_postponed("qi") is False
    assert is_postponed("cobmat_exp") is False  # 未知非后置
    assert is_postponed("skill/axe") is False


def test_postponed_key_query_warns_returns_none() -> None:
    """后置 key query 返回 None + warnings.warn（用 pytest.warns 捕获）。"""
    world, eid = _make_world_with_player()
    with pytest.warns(UserWarning, match="后置 key"):
        result = query(world, eid, "title")
    assert result is None


def test_postponed_key_set_raises_dbasekeyerror() -> None:
    """后置 key set raise DbaseKeyError（无组件承接，写无意义）。"""
    world, eid = _make_world_with_player()
    with pytest.raises(DbaseKeyError, match="后置 key"):
        set(world, eid, "equipped", "sword")


def test_unknown_key_query_raises_dbasekeyerror() -> None:
    """未知 key（拼写错误）query raise DbaseKeyError（非静默，dissent 2）。"""
    world, eid = _make_world_with_player()
    with pytest.raises(DbaseKeyError, match="未知 key"):
        query(world, eid, "cobmat_exp")


def test_unknown_key_set_raises_dbasekeyerror() -> None:
    """未知 key set raise DbaseKeyError。"""
    world, eid = _make_world_with_player()
    with pytest.raises(DbaseKeyError, match="未知 key"):
        set(world, eid, "cobmat_exp", 100)


def test_mapped_key_query_no_warn_no_raise() -> None:
    """已映射 key query/set 不 raise 不 warn（正常路径）。"""
    world, eid = _make_world_with_player()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # 任何 warning 转 error
        assert query(world, eid, "qi") == 200
        set(world, eid, "qi", 180)
        assert query(world, eid, "qi") == 180


# ═══════════════════ 3. 索引层 ═══════════════════


def test_entities_with_family() -> None:
    """按 Attributes.family 查实体。"""
    world, _ = _make_world_with_player()
    # 玩家 family="丐帮"
    pids = list(entities_with_family(world, "丐帮"))
    assert len(pids) == 1
    # 另一个不同门派实体
    eid2 = world.new_entity()
    world.add(eid2, Identity(name="NPC"))
    world.add(eid2, Attributes(family="武当"))
    assert len(list(entities_with_family(world, "丐帮"))) == 1
    assert len(list(entities_with_family(world, "武当"))) == 1
    assert len(list(entities_with_family(world, "少林"))) == 0


def test_entities_by_prototype() -> None:
    """按 Identity.prototype_id 查实体。"""
    world, ge_eid = _make_world_with_npc(prototype_id="city/npc/ge")
    found = list(entities_by_prototype(world, "city/npc/ge"))
    assert found == [ge_eid]


def test_entities_by_prototype_empty_string_no_match() -> None:
    """prototype_id 空字符串不匹配（避免误命中无 prototype 的实体）。"""
    world, _ = _make_world_with_npc(prototype_id="")  # 空原型
    # 玩家 prototype_id 默认空（_make_world_with_npc 的 NPC 也空）
    assert list(entities_by_prototype(world, "")) == []


def test_find_in_room_by_name() -> None:
    """房间内按 name 精确查实体。"""
    world, ge_eid = _make_world_with_npc(name="葛伦布", room_id="city/street")
    assert find_in_room(world, "city/street", "葛伦布") == ge_eid


def test_find_in_room_by_alias() -> None:
    """房间内按 aliases 含 keyword 查实体。"""
    world, ge_eid = _make_world_with_npc(
        name="葛伦布", aliases=["ge lunbu"], room_id="city/street"
    )
    assert find_in_room(world, "city/street", "ge lunbu") == ge_eid


def test_find_in_room_not_found_returns_none() -> None:
    """房间内未找到返回 None。"""
    world, _ = _make_world_with_npc(room_id="city/street")
    assert find_in_room(world, "city/street", "不存在") is None
    assert find_in_room(world, "city/noroom", "葛伦布") is None


def test_find_item_by_id() -> None:
    """物品栏按 id 精确查（Inventory.items 集合）。"""
    world, eid = _make_world_with_player()
    assert find_item(world, eid, "sword") == "sword"
    assert find_item(world, eid, "不存在") is None


def test_find_item_no_inventory_returns_none() -> None:
    """无 Inventory 组件返回 None。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert find_item(world, bare_eid, "sword") is None


# ═══════════════════ 4. Identity/Position/Inventory 语义 ═══════════════════


def test_id_match_name_exact() -> None:
    """id_match: name 精确匹配。"""
    ident = Identity(name="葛伦布", aliases=["ge lunbu"])
    assert id_match(ident, "葛伦布") is True


def test_id_match_alias() -> None:
    """id_match: aliases 含 keyword。"""
    ident = Identity(name="葛伦布", aliases=["ge lunbu", "ge"])
    assert id_match(ident, "ge lunbu") is True
    assert id_match(ident, "ge") is True


def test_id_match_no_match() -> None:
    """id_match: 不匹配返回 False。"""
    ident = Identity(name="葛伦布", aliases=["ge lunbu"])
    assert id_match(ident, "不存在") is False


def test_short_with_aliases() -> None:
    """short: name(id) 格式，id 取 aliases[0]。"""
    ident = Identity(name="葛伦布", aliases=["ge lunbu"])
    assert short(ident) == "葛伦布(ge lunbu)"


def test_short_without_aliases_fallback_prototype() -> None:
    """short: 无 aliases 回退 prototype_id。"""
    ident = Identity(name="神秘人", aliases=[], prototype_id="npc/mystery")
    assert short(ident) == "神秘人(npc/mystery)"


def test_move_to_switches_room() -> None:
    """move_to: 切换 Position.room_id。"""
    world, eid = _make_world_with_player()
    assert environment(world, eid) == "city/street"
    move_to(world, eid, "city/square")
    assert environment(world, eid) == "city/square"


def test_move_to_creates_position_if_absent() -> None:
    """move_to: Position 不存在时自动创建。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert environment(world, bare_eid) is None
    move_to(world, bare_eid, "city/square")
    assert environment(world, bare_eid) == "city/square"


def test_environment_no_position_returns_none() -> None:
    """environment: 无 Position 返回 None。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert environment(world, bare_eid) is None


def test_present_item_delegates_find_item() -> None:
    """present_item 委托 find_item。"""
    world, eid = _make_world_with_player()
    assert present_item(world, eid, "sword") == "sword"
    assert present_item(world, eid, "不存在") is None


def test_present_item_no_inventory_returns_none() -> None:
    """present_item: 无 Inventory 返回 None。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert present_item(world, bare_eid, "sword") is None


def test_all_inventory_returns_copy() -> None:
    """all_inventory 返回副本，修改副本不影响原组件。"""
    world, eid = _make_world_with_player()
    inv = all_inventory(world, eid)
    assert inv == {"sword", "pill"}
    inv.add("新物品")
    inv.discard("sword")
    # 原组件不变
    assert world.get(eid, Inventory).items == {"sword", "pill"}


def test_all_inventory_no_inventory_returns_empty() -> None:
    """all_inventory: 无 Inventory 返回空集合。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="裸"))
    assert all_inventory(world, bare_eid) == builtins.set()


# ═══════════════════ 5. hypothesis 属性测试 ═══════════════════


# 路径前缀 key 的合法子 id（字母/数字/下划线/中文，避免 "/" 避免歧义）
_SKILL_ID_STRATEGY = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Lo"),  # 字母+数字+中文
        min_codepoint=0x41,
    ),
    min_size=1,
    max_size=10,
)


@given(skill_id=_SKILL_ID_STRATEGY, val=st.integers(min_value=0, max_value=1000))
@settings(max_examples=40)
def test_prop_skill_path_roundtrip(skill_id: str, val: int) -> None:
    """路径前缀往返：set("skill/<id>", val) 后 query == val（hypothesis 随机 id+int）。"""
    world, eid = _make_world_with_player()
    key = f"skill/{skill_id}"
    set(world, eid, key, val)
    assert query(world, eid, key) == val


@given(s=st.text(min_size=1, max_size=8))
@settings(max_examples=50)
def test_prop_classify_key_returns_valid_class(s: str) -> None:
    """classify_key 任意字符串返回值在三类集合中。"""
    assert classify_key(s) in {"mapped", "postponed", "unknown"}


@given(key=st.sampled_from(sorted(DBASE_KEY_MAP.keys())))
@settings(max_examples=40)
def test_prop_mapped_key_classifies_as_mapped(key: str) -> None:
    """已知 mapped key（DBASE_KEY_MAP）分类为 mapped。"""
    assert classify_key(key) == "mapped"


@given(key=st.sampled_from(sorted(POSTPONED_KEYS)))
@settings(max_examples=40)
def test_prop_postponed_key_classifies_as_postponed(key: str) -> None:
    """已知 postponed key（POSTPONED_KEYS）分类为 postponed。"""
    assert classify_key(key) == "postponed"


@given(delta=st.integers(min_value=-100, max_value=100))
@settings(max_examples=40)
def test_prop_add_int_equals_query_set_query(delta: int) -> None:
    """int add 等价 query+set+query。"""
    world, eid = _make_world_with_player()
    old = query(world, eid, "qi")
    expected = old + delta
    result = add(world, eid, "qi", delta)
    assert result == expected
    assert query(world, eid, "qi") == expected


@given(flag=st.text(min_size=1, max_size=8))
@settings(max_examples=30)
def test_prop_marks_set_query_roundtrip(flag: str) -> None:
    """marks/ set_temp+query_temp 往返：set 1 后 query==1，set 0 后 query==0。"""
    world, eid = _make_world_with_player()
    key = f"marks/{flag}"
    set_temp(world, eid, key, 1)
    assert query_temp(world, eid, key) == 1
    set_temp(world, eid, key, 0)
    assert query_temp(world, eid, key) == 0


# ═══════════════════ 6. marks/ 自动创建 Marks 组件 ═══════════════════


def test_set_temp_marks_autocreates_marks_component() -> None:
    """set_temp("marks/新标记", 1) 对无 Marks 组件的实体：自动创建 + 添加 flag + query 返回 1。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="无标记实体"))
    # 确认无 Marks
    assert world.get(bare_eid, Marks) is None
    set_temp(world, bare_eid, "marks/新标记", 1)
    marks = world.get(bare_eid, Marks)
    assert marks is not None
    assert "新标记" in marks.flags
    assert query_temp(world, bare_eid, "marks/新标记") == 1


def test_set_marks_autocreates_marks_component() -> None:
    """set("marks/新标记", 1) 同样自动创建（greenfield 不区分 set/set_temp）。"""
    world, _ = _make_world_with_player()
    bare_eid = world.new_entity()
    world.add(bare_eid, Identity(name="无标记实体"))
    assert world.get(bare_eid, Marks) is None
    set(world, bare_eid, "marks/新标记", 1)
    marks = world.get(bare_eid, Marks)
    assert marks is not None
    assert "新标记" in marks.flags
    assert query(world, bare_eid, "marks/新标记") == 1
