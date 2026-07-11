"""Entity Inspector 测试（ADR-0013 PRD 1）。"""

from __future__ import annotations

from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.inspector import (
    COMPONENT_NAMES,
    LPC_KEY_MAP,
    EntityInspector,
    _component_to_dict,
    main,
)


def _world_with_entities() -> World:
    w = World()
    # 官兵 NPC
    e1 = w.new_entity()
    w.add(e1, Identity(name="官兵", aliases=["bing"], prototype_id="city/npc/bing"))
    w.add(e1, Position(room_id="xkx/chaguan"))
    w.add(e1, Vitals(qi=85, max_qi=100, eff_qi=100))
    w.add(e1, Skills(levels={"unarmed": 50}))
    w.add(e1, Attributes(str_=20))
    w.add(e1, Progression(combat_exp=500))
    w.add(e1, Marks(flags={"quest_done"}))
    w.add(e1, Inventory(items={"sword"}))
    # 玩家
    e2 = w.new_entity()
    w.add(e2, Identity(name="玩家甲", aliases=["player"], is_player=True))
    w.add(e2, Position(room_id="xkx/chaguan"))
    w.add(e2, Vitals(qi=100, max_qi=100))
    return w


# ---------------------------------------------------------------------------
# 快照与查询
# ---------------------------------------------------------------------------


def test_snapshot_returns_all_components() -> None:
    """snapshot 返回实体全部组件。"""
    w = _world_with_entities()
    insp = EntityInspector(w)
    snap = insp.snapshot(1)
    assert snap["entity_id"] == 1
    assert "identity" in snap["components"]
    assert "vitals" in snap["components"]
    assert snap["components"]["identity"]["name"] == "官兵"
    assert snap["components"]["vitals"]["qi"] == 85


def test_snapshot_missing_entity_returns_empty() -> None:
    """不存在实体的 snapshot 返回空组件。"""
    insp = EntityInspector(_world_with_entities())
    snap = insp.snapshot(999)
    assert snap["components"] == {}


def test_component_snapshot() -> None:
    """component_snapshot 返回单组件 dict。"""
    insp = EntityInspector(_world_with_entities())
    vitals = insp.component_snapshot(1, Vitals)
    assert vitals is not None
    assert vitals["qi"] == 85
    assert insp.component_snapshot(999, Vitals) is None


def test_query_by_component() -> None:
    """query_by_component 返回同时拥有指定组件的实体。"""
    insp = EntityInspector(_world_with_entities())
    both = insp.query_by_component(Identity, Position)
    assert set(both) == {1, 2}
    vitals_only = insp.query_by_component(Vitals)
    assert set(vitals_only) == {1, 2}


def test_query_by_room() -> None:
    """query_by_room 返回指定房间内实体。"""
    insp = EntityInspector(_world_with_entities())
    assert set(insp.query_by_room("xkx/chaguan")) == {1, 2}
    assert insp.query_by_room("other") == []


def test_query_by_name() -> None:
    """query_by_name 模糊匹配 Identity.name。"""
    insp = EntityInspector(_world_with_entities())
    assert insp.query_by_name("官兵") == [1]
    assert insp.query_by_name("玩家") == [2]
    assert insp.query_by_name("甲") == [2]
    assert insp.query_by_name("不存在") == []


# ---------------------------------------------------------------------------
# 序列化（set -> sorted list）
# ---------------------------------------------------------------------------


def test_component_to_dict_serializes_set_to_sorted_list() -> None:
    """set 字段序列化为 sorted list（确定性输出）。"""
    insp = EntityInspector(_world_with_entities())
    marks = insp.component_snapshot(1, Marks)
    assert marks["flags"] == ["quest_done"]  # set -> sorted list
    inv = insp.component_snapshot(1, Inventory)
    assert inv["items"] == ["sword"]


def test_component_to_dict_non_dataclass_returns_empty() -> None:
    """非 dataclass 返回空 dict。"""
    assert _component_to_dict("not a dataclass") == {}
    assert _component_to_dict(42) == {}


# ---------------------------------------------------------------------------
# LPC F_DBASE 语义映射
# ---------------------------------------------------------------------------


def test_lpc_key_mapping_exact_match() -> None:
    """精确匹配 LPC key。"""
    insp = EntityInspector(_world_with_entities())
    m = insp.lpc_key_mapping("qi")
    assert m.mapped is True
    assert m.component is Vitals
    assert m.field_path == "qi"
    assert m.lpc_scope == "dbase"


def test_lpc_key_mapping_unmapped() -> None:
    """未映射的 key 返回 mapped=False。"""
    insp = EntityInspector(_world_with_entities())
    m = insp.lpc_key_mapping("equipped")
    assert m.mapped is False
    assert m.component is None
    assert "后置" in m.note


def test_lpc_key_mapping_skill_path() -> None:
    """skill/<id> 路径访问映射到 Skills.levels。"""
    insp = EntityInspector(_world_with_entities())
    m = insp.lpc_key_mapping("skill/axe")
    assert m.mapped is True
    assert m.component is Skills
    assert "levels" in m.field_path
    assert m.lpc_scope == "dbase"


def test_lpc_key_mapping_marks_path() -> None:
    """marks/<flag> 路径访问映射到 Marks.flags。"""
    insp = EntityInspector(_world_with_entities())
    m = insp.lpc_key_mapping("marks/酥")
    assert m.mapped is True
    assert m.component is Marks
    assert m.lpc_scope == "temp"


def test_lpc_key_mapping_unknown_key() -> None:
    """未知 key 返回 mapped=False。"""
    insp = EntityInspector(_world_with_entities())
    m = insp.lpc_key_mapping("unknown_key")
    assert m.mapped is False
    assert m.component is None


def test_lpc_key_map_covers_core_components() -> None:
    """LPC_KEY_MAP 覆盖核心组件字段（PRD §二.3）。"""
    # 精确匹配的 key 应映射到对应组件
    assert LPC_KEY_MAP["name"].component is Identity
    assert LPC_KEY_MAP["qi"].component is Vitals
    assert LPC_KEY_MAP["combat_exp"].component is Progression
    assert LPC_KEY_MAP["str"].component is Attributes
    assert LPC_KEY_MAP["short"].component is RoomComp
    assert LPC_KEY_MAP["inquiry"].component is NpcBehavior


def test_component_names_covers_all_components() -> None:
    """COMPONENT_NAMES 覆盖全部内置组件。"""
    assert COMPONENT_NAMES["combat"] is CombatState
    assert COMPONENT_NAMES["npc"] is NpcBehavior
    assert COMPONENT_NAMES["quest"] is QuestLog
    assert COMPONENT_NAMES["room"] is RoomComp


# ---------------------------------------------------------------------------
# 只读不变量
# ---------------------------------------------------------------------------


def test_inspector_does_not_modify_world() -> None:
    """Inspector 只读，不修改 world 状态。"""
    w = _world_with_entities()
    insp = EntityInspector(w)
    insp.snapshot(1)
    insp.query_by_component(Identity)
    insp.query_by_room("xkx/chaguan")
    insp.component_snapshot(1, Vitals)
    # 状态不变
    assert w.get(1, Identity).name == "官兵"
    assert w.get(1, Vitals).qi == 85


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_map(capsys: object) -> None:
    """inspect --map <key> 查询 LPC 映射。"""
    ret = main(["--map", "qi"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Vitals" in out
    assert "qi" in out


def test_main_map_skill_path(capsys: object) -> None:
    """inspect --map skill/axe 路径映射。"""
    ret = main(["--map", "skill/axe"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Skills" in out


def test_main_map_unmapped(capsys: object) -> None:
    """inspect --map <unmapped> 显示 unmapped。"""
    ret = main(["--map", "equipped"])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "unmapped" in out.lower() or "False" in out


def test_main_no_args(capsys: object) -> None:
    """inspect 无参数显示用法。"""
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "用法" in out
