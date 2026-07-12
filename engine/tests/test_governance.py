"""WorldGovernanceSystem 测试（阶段 2.6 批次 2，ADR-0029）。

覆盖 ADR-0029 §验收标准 11 项 + §决策 3/4/5（阴间/剧情/法院细节）+ §简化台账：

- A. 平台级 fail-closed 边界（验收 2）：治理常量硬编码 + 无 UGC 配置接口。
- B. 阴间死亡轮回完整闭环（验收 3）：enter_underworld -> 5 段剧情 -> 还阳。
- C. gate.c 物品销毁副作用顺序（验收 4）：make_corpse 转移 -> ghost move -> 销毁。
- D. death_stage EffectComp 崩溃恢复（验收 5 + 决策 8）：序列化往返 + 冷重启。
- E. 黑无常 is_ghost 检测（决策 4）：活人闯入传送回 wumiao。
- F. 法院通缉 condition 框架（验收 6）：四区域 apply/query_wanted。
- G. 审判收监（验收 7）：PKS 分级 + 穿琵琶骨 + 经验转移 + city_jail。
- H. 受贿销案：amount >= combat_exp//10 清 killer。
- I. 监狱释放（验收衔接）：city_jail/dali_jail/bonze_jail 到期 move。
- J. 可序列化（验收 8）：WantedCondition + death_stage EffectComp 往返。
- K. hypothesis 属性测试（验收 10）：通缉衰减 + 量刑单调。
- L. test_theme_neutrality 硬门禁（验收 12）：治理逻辑无武侠武学字面量。

[ADR-0029](../../../docs/adr/ADR-0029-world-governance-system.md)
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xkx.runtime.components import (
    EffectComp,
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    RoomComp,
    TitleComp,
    Vitals,
)
from xkx.runtime.conditions import (
    ConditionSystem,
    apply_condition,
    query_condition,
)
from xkx.runtime.death import (
    DEATH_ROOM,
    GHOST_FLAG,
    die,
)
from xkx.runtime.ecs import World
from xkx.runtime.governance import (
    BGARGOYLE_LIVING_TELEPORT,
    BRIBE_EXP_DIVISOR,
    DEATH_STAGE_EFFECT_ID,
    DEATH_STAGE_FIRST_DELAY,
    DEATH_STAGE_INTERVAL,
    DEATH_STAGE_KIND,
    DEATH_STAGE_MSGS_BGARGOYLE,
    DEATH_STAGE_MSGS_WGARGOYLE,
    DEATH_STAGE_SEGMENTS,
    EMBEDDED_FLAG,
    HIDDEN_REVIVE_ROOM,
    JAIL_ROOMS,
    REVIVE_ROOM,
    SENTENCE_DURATION_HIGH,
    SENTENCE_DURATION_LOW,
    SENTENCE_DURATION_MID,
    SENTENCE_DURATION_RECIDIVIST,
    SENTENCE_EXP_TRANSFER_CAP,
    SENTENCE_PKS_HIGH,
    SENTENCE_PKS_LOW,
    SENTENCE_PKS_MID,
    STARTROOM_FLAG_PREFIX,
    WANTED_DURATION,
    WANTED_REGIONS,
    GovernanceSystem,
    apply_wanted,
    bribe_clear_wanted,
    death_stage_handler,
    enter_underworld,
    proceed_sentencing,
    query_wanted,
    reincarnate_at,
    release_from_jail,
)
from xkx.runtime.serialization import deserialize_component, serialize_component

# ──────────────────────── 测试辅助：世界 + 实体构造 ────────────────────────


def _make_room(world: World, room_id: str, *, no_death: bool = False) -> int:
    """构造房间实体（RoomComp，含 items 集合供 drop 测试）。"""
    eid = world.new_entity()
    world.add(eid, RoomComp(room_id=room_id, short="", long="", no_death=no_death))
    return eid


def _make_player(
    world: World,
    *,
    room_id: str = "city/room1",
    qi: int = 100,
    max_qi: int = 100,
    eff_qi: int = 100,
    jing: int = 100,
    max_jing: int = 100,
    eff_jing: int = 100,
    jingli: int = 100,
    max_jingli: int = 100,
    max_neili: int = 100,
    combat_exp: int = 5000,
    pks: int = 0,
    is_ghost: bool = False,
    items: set[str] | None = None,
) -> int:
    """构造带全套治理所需组件的玩家实体。"""
    eid = world.new_entity()
    world.add(eid, Identity(name="player", is_player=True))
    world.add(eid, Position(room_id=room_id))
    world.add(
        eid,
        Vitals(
            qi=qi,
            max_qi=max_qi,
            eff_qi=eff_qi,
            jing=jing,
            max_jing=max_jing,
            eff_jing=eff_jing,
            jingli=jingli,
            max_jingli=max_jingli,
            max_neili=max_neili,
        ),
    )
    world.add(eid, Progression(combat_exp=combat_exp))
    world.add(eid, TitleComp(pks=pks, is_ghost=is_ghost))
    if is_ghost:
        world.add(eid, Marks(flags={GHOST_FLAG}))
    else:
        world.add(eid, Marks())
    if items is not None:
        world.add(eid, Inventory(items=items))
    else:
        world.add(eid, Inventory())
    return eid


def _make_arrester(world: World, *, combat_exp: int = 0) -> int:
    """构造逮捕者实体（接收经验转移）。"""
    eid = world.new_entity()
    world.add(eid, Identity(name="arrester"))
    world.add(eid, Progression(combat_exp=combat_exp))
    return eid


def _find_room(world: World, room_id: str) -> RoomComp:
    """按 room_id 找 RoomComp（断言存在）。"""
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    raise AssertionError(f"room {room_id} not found")


def _death_stage_effs(world: World) -> list[EffectComp]:
    """收集所有 death_stage EffectComp。"""
    result: list[EffectComp] = []
    for eid in world.entities_with(EffectComp):
        eff = world.get(eid, EffectComp)
        if eff is not None and eff.effect_id == DEATH_STAGE_EFFECT_ID:
            result.append(eff)
    return result


# ═══════════════════ A. 平台级 fail-closed 边界（验收 2） ═══════════════════


def test_governance_constants_hardcoded_values() -> None:
    """治理常量值正确（ADR-0029 §决策 2 硬编码）。

    通缉时长 100 / PKS 阈值 99,74,49 / 刑期 500,300,200,600 /
    DEATH_STAGE_SEGMENTS=5 / 首延 30 / 间隔 5。
    """
    assert WANTED_DURATION == 100
    assert SENTENCE_PKS_HIGH == 99
    assert SENTENCE_PKS_MID == 74
    assert SENTENCE_PKS_LOW == 49
    assert SENTENCE_DURATION_HIGH == 500
    assert SENTENCE_DURATION_MID == 300
    assert SENTENCE_DURATION_LOW == 200
    assert SENTENCE_DURATION_RECIDIVIST == 600
    assert DEATH_STAGE_SEGMENTS == 5
    assert DEATH_STAGE_FIRST_DELAY == 30
    assert DEATH_STAGE_INTERVAL == 5
    assert SENTENCE_EXP_TRANSFER_CAP == 3000
    assert BRIBE_EXP_DIVISOR == 10


def test_wanted_duration_default_not_modified_by_caller() -> None:
    """apply_wanted 默认 duration=100（调用方不传则用 WANTED_DURATION）。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, "city")  # 不传 duration
    assert query_condition(w, p, "killer") == WANTED_DURATION


def test_no_ugc_config_interface_for_governance_rules() -> None:
    """UGC 无接口修改治理规则：governance 模块无 set_wanted_duration 等配置函数。

    治理常量是模块级（不可变），无 setter 暴露。断言模块不导出配置型函数。
    """
    import xkx.runtime.governance as gov

    # 不存在配置型 setter 接口（fail-closed：治理规则不可被 UGC 修改）
    forbidden = [
        "set_wanted_duration",
        "set_sentence_threshold",
        "set_death_stage_segments",
        "set_jail_rooms",
        "configure",
    ]
    for name in forbidden:
        assert not hasattr(gov, name), f"governance 不应暴露配置接口 {name}"


def test_wanted_regions_four_area_mapping() -> None:
    """四区域通缉映射（city->killer, xa->xakiller, dl->dlkiller, bj->bjkiller）。"""
    assert WANTED_REGIONS == {
        "city": "killer",
        "xa": "xakiller",
        "dl": "dlkiller",
        "bj": "bjkiller",
    }


def test_jail_rooms_three_types_mapping() -> None:
    """监狱释放房间映射（city/dali/bonze 三类）。"""
    assert JAIL_ROOMS == {
        "city_jail": "city/yamen",
        "dali_jail": "dali/taihejie5",
        "bonze_jail": "shaolin/guangchang1",
    }


def test_death_stage_msgs_five_segments() -> None:
    """黑白无常剧情各 5 段对话（对照 wgargoyle.c/bgargoyle.c death_msg[0..4]）。"""
    assert len(DEATH_STAGE_MSGS_WGARGOYLE) == DEATH_STAGE_SEGMENTS
    assert len(DEATH_STAGE_MSGS_BGARGOYLE) == DEATH_STAGE_SEGMENTS
    # 白无常第 1 段含"白无常"，黑无常第 1 段含"黑无常"（NPC 名差异）
    assert "白无常" in DEATH_STAGE_MSGS_WGARGOYLE[0]
    assert "黑无常" in DEATH_STAGE_MSGS_BGARGOYLE[0]


# ═══════════════════ B. 阴间死亡轮回完整闭环（验收 3） ═══════════════════


def test_enter_underworld_clears_inventory_and_starts_death_stage() -> None:
    """enter_underworld：gate.c 销毁鬼魂 Inventory + 启动 death_stage EffectComp。

    EffectComp 字段：effect_id=death_stage, kind=governance_dialog, detail=wgargoyle,
    duration=5, next_tick=tick+30, tick_interval=5, source_id=gargoyle_eid。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    p = _make_player(w, items={"sword", "potion"})
    gargoyle = w.new_entity()  # 无常 NPC

    enter_underworld(w, p, tick=100, gargoyle_eid=gargoyle)

    # gate.c 物品销毁：鬼魂 Inventory 清空
    assert w.get(p, Inventory).items == set()
    # 启动 death_stage EffectComp
    effs = _death_stage_effs(w)
    assert len(effs) == 1
    eff = effs[0]
    assert eff.effect_id == DEATH_STAGE_EFFECT_ID
    assert eff.kind == DEATH_STAGE_KIND
    assert eff.target_id == p
    assert eff.source_id == gargoyle
    assert eff.detail == "wgargoyle"  # 主路径白无常
    assert eff.duration == DEATH_STAGE_SEGMENTS
    assert eff.next_tick == 100 + DEATH_STAGE_FIRST_DELAY  # tick+30
    assert eff.tick_interval == DEATH_STAGE_INTERVAL


def test_enter_underworld_default_gargoyle_eid_zero() -> None:
    """enter_underworld 不传 gargoyle_eid 时 source_id=0（无常 NPC 可选）。"""
    w = World()
    p = _make_player(w)
    enter_underworld(w, p, tick=0)
    eff = _death_stage_effs(w)[0]
    assert eff.source_id == 0
    assert eff.next_tick == DEATH_STAGE_FIRST_DELAY  # 0+30


def test_governance_update_advances_death_stage_five_segments() -> None:
    """GovernanceSystem.update 推进 death_stage：tick+30/+35/+40/+45/+50 五段。

    每 tick 推进一段，duration 5->4->3->2->1，stage 0-4 对话。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    _make_room(w, REVIVE_ROOM)
    p = _make_player(w, items=set())  # 鬼魂无物品（gate.c 已销毁）
    enter_underworld(w, p, tick=100)

    gs = GovernanceSystem()
    # tick=100+30=130 触发第 1 段（stage 0, duration 5->4）
    gs.update(w, 130)
    effs = _death_stage_effs(w)
    assert len(effs) == 1
    assert effs[0].duration == 4
    assert effs[0].next_tick == 130 + DEATH_STAGE_INTERVAL  # 135

    # tick=135 第 2 段（duration 4->3）
    gs.update(w, 135)
    assert _death_stage_effs(w)[0].duration == 3
    # tick=140 第 3 段（duration 3->2）
    gs.update(w, 140)
    assert _death_stage_effs(w)[0].duration == 2
    # tick=145 第 4 段（duration 2->1）
    gs.update(w, 145)
    assert _death_stage_effs(w)[0].duration == 1
    # tick=150 第 5 段（duration 1->0 触发还阳，EffectComp 移除）
    gs.update(w, 150)
    assert _death_stage_effs(w) == []  # 还阳后 EffectComp 移除


def test_governance_update_non_due_tick_no_advance() -> None:
    """非均匀 tick：next_tick > tick 的 EffectComp 不触发（ADR-0018 §3）。"""
    w = World()
    _make_room(w, DEATH_ROOM)
    p = _make_player(w)
    enter_underworld(w, p, tick=100)  # next_tick=130

    gs = GovernanceSystem()
    gs.update(w, 129)  # < 130，不触发
    assert _death_stage_effs(w)[0].duration == 5  # 未衰减


def test_reincarnate_main_path_drops_items_and_moves() -> None:
    """还阳主路径：reincarnate_at(drop_items=True) 清 ghost + 恢复 vitals +
    丢弃 Inventory 物品到鬼魂当前房间地面 + move REVIVE_ROOM。

    被测代码行为：drop 发生在 move 之前（``_drop_all_inventory`` 在 ``move_to``
    前），物品掉在鬼魂当前位置（DEATH_ROOM），随后 move 到 REVIVE_ROOM。
    对照 wgargoyle.c:62-68 reincarnate + DROP + move 顺序。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    _make_room(w, REVIVE_ROOM)
    p = _make_player(
        w,
        room_id=DEATH_ROOM,
        qi=1,
        eff_qi=1,
        jing=1,
        eff_jing=1,
        jingli=1,
        is_ghost=True,
        items={"sword", "potion"},
    )

    reincarnate_at(w, p, REVIVE_ROOM, drop_items=True)

    # ghost 清除
    assert GHOST_FLAG not in w.get(p, Marks).flags
    # vitals 完整恢复到 max
    v = w.get(p, Vitals)
    assert v.qi == v.max_qi
    assert v.eff_qi == v.max_qi
    assert v.jing == v.max_jing
    assert v.eff_jing == v.max_jing
    assert v.jingli == v.max_jingli
    # 位置移动到还阳房间
    assert w.get(p, Position).room_id == REVIVE_ROOM
    # 物品丢弃到鬼魂当前位置（DEATH_ROOM，drop 在 move 之前）+ Inventory 清空
    assert w.get(p, Inventory).items == set()
    assert _find_room(w, DEATH_ROOM).items == {"sword", "potion"}
    # 还阳房间无物品（move 在 drop 之后，物品不会跟到 REVIVE_ROOM）
    assert _find_room(w, REVIVE_ROOM).items == set()


def test_reincarnate_hidden_path_no_drop() -> None:
    """还阳隐藏路径：reincarnate_at(drop_items=False) 不丢弃物品。"""
    w = World()
    _make_room(w, HIDDEN_REVIVE_ROOM)
    p = _make_player(
        w,
        room_id=DEATH_ROOM,
        is_ghost=True,
        items={"sword"},  # 隐藏路径鬼魂理论上无物品，测试保留
    )

    reincarnate_at(w, p, HIDDEN_REVIVE_ROOM, drop_items=False)

    # ghost 清除 + vitals 恢复
    assert GHOST_FLAG not in w.get(p, Marks).flags
    assert w.get(p, Vitals).qi == w.get(p, Vitals).max_qi
    # 位置移动
    assert w.get(p, Position).room_id == HIDDEN_REVIVE_ROOM
    # 物品保留（不丢弃）
    assert w.get(p, Inventory).items == {"sword"}
    # 房间地面无新物品
    assert _find_room(w, HIDDEN_REVIVE_ROOM).items == set()


def test_full_underworld_reincarnation_loop_via_die() -> None:
    """完整闭环：die(player) -> enter_underworld -> GovernanceSystem 推进 5 段 ->
    还阳主路径（tick=100,130,135,140,145,150）。"""
    w = World()
    _make_room(w, "city/room1")
    _make_room(w, DEATH_ROOM)
    _make_room(w, REVIVE_ROOM)
    p = _make_player(w, room_id="city/room1", items={"sword", "potion"})

    # die 触发阴间入口（ghost=1 + move DEATH_ROOM + gate.c 销毁 + death_stage）
    die(w, p, tick=100)
    assert GHOST_FLAG in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == DEATH_ROOM
    assert w.get(p, Inventory).items == set()  # gate.c 销毁

    # GovernanceSystem 推进 5 段剧情
    gs = GovernanceSystem()
    for t in (130, 135, 140, 145, 150):
        gs.update(w, t)

    # 还阳完成：ghost 清除 + vitals 恢复 + move REVIVE_ROOM
    assert GHOST_FLAG not in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == REVIVE_ROOM
    v = w.get(p, Vitals)
    assert v.qi == v.max_qi
    assert v.eff_qi == v.max_qi
    # death_stage EffectComp 已移除
    assert _death_stage_effs(w) == []


def test_death_stage_handler_returns_stage_messages() -> None:
    """death_stage_handler 纯函数：返回对应 stage 的对话 + new_duration 衰减。"""
    w = World()
    p = _make_player(w, is_ghost=True)
    # duration=5 -> stage=0
    eff = EffectComp(
        effect_id=DEATH_STAGE_EFFECT_ID,
        kind=DEATH_STAGE_KIND,
        target_id=p,
        detail="wgargoyle",
        duration=5,
        tick_interval=5,
        next_tick=30,
    )
    r = death_stage_handler(w, eff, tick=30)
    assert r.messages == [DEATH_STAGE_MSGS_WGARGOYLE[0]]
    assert r.new_duration == 4

    # duration=1 -> stage=4（最后一段）
    eff.duration = 1
    r = death_stage_handler(w, eff, tick=50)
    assert r.messages == [DEATH_STAGE_MSGS_WGARGOYLE[4]]
    assert r.new_duration == 0


# ═══════════════════ C. gate.c 物品销毁副作用顺序（验收 4） ═══════════════════


def test_die_make_corpse_transfers_items_before_ghost_move() -> None:
    """die -> make_corpse 转移物品到尸体（尸体留死亡房间）-> ghost move DEATH_ROOM。

    断言：死亡房间有尸体（尸体 Inventory 含被转移物品），鬼魂在 DEATH_ROOM 且
    Inventory 为空（gate.c 销毁）。
    """
    w = World()
    _make_room(w, "city/room1")
    _make_room(w, DEATH_ROOM)
    p = _make_player(w, room_id="city/room1", items={"sword", "potion"})

    die(w, p, tick=0)

    # 死亡房间有尸体（Identity name 含"尸体"）
    corpses = [
        e
        for e in w.entities_with(Inventory)
        if w.get(e, Identity) is not None and "尸体" in (w.get(e, Identity).name or "")
    ]
    assert len(corpses) == 1
    corpse = corpses[0]
    # 尸体 Inventory 含被转移物品
    assert w.get(corpse, Inventory).items == {"sword", "potion"}
    # 尸体留在死亡房间
    assert w.get(corpse, Position).room_id == "city/room1"
    # 鬼魂在 DEATH_ROOM 且 Inventory 为空（gate.c 销毁）
    assert w.get(p, Position).room_id == DEATH_ROOM
    assert w.get(p, Inventory).items == set()


def test_enter_underworld_defensive_destroy_remaining_items() -> None:
    """防御性销毁：鬼魂进入阴间时仍有物品（手动加），gate.c 销毁清空。

    正常路径 die.make_corpse 已转移物品，鬼魂本应无物品；本测试手动给鬼魂加
    物品后调 enter_underworld，验证 gate.c 防御性销毁仍清空。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    p = _make_player(w, room_id=DEATH_ROOM, is_ghost=True, items={"leftover"})

    enter_underworld(w, p, tick=0)

    assert w.get(p, Inventory).items == set()


# ═══════════════════ D. death_stage EffectComp 崩溃恢复（验收 5 + 决策 8） ═══════════════════


def test_death_stage_effectcomp_serialization_roundtrip() -> None:
    """death_stage EffectComp 序列化往返：duration/next_tick/tick_interval 恢复。"""
    eff = EffectComp(
        effect_id=DEATH_STAGE_EFFECT_ID,
        kind=DEATH_STAGE_KIND,
        target_id=42,
        source_id=7,
        detail="wgargoyle",
        duration=3,
        tick_interval=DEATH_STAGE_INTERVAL,
        next_tick=135,
    )
    data = serialize_component(eff)
    restored = deserialize_component(EffectComp, data)
    assert restored == eff
    assert restored.duration == 3
    assert restored.next_tick == 135
    assert restored.tick_interval == DEATH_STAGE_INTERVAL
    assert restored.detail == "wgargoyle"


def test_death_stage_progress_survives_cold_restart() -> None:
    """冷重启：death_stage 进度跨 world 重建继续（序列化 -> 反序列化到新 world）。

    鬼魂玩家 + death_stage EffectComp 序列化 -> 反序列化到新 world ->
    鬼魂仍在阴间 + death_stage 进度继续（duration 不衰减，崩溃期间剧情暂停）。
    """
    w1 = World()
    _make_room(w1, DEATH_ROOM)
    p = _make_player(w1, room_id=DEATH_ROOM, is_ghost=True)
    enter_underworld(w1, p, tick=100)
    # 推进 1 段（duration 5->4，next_tick=135）
    GovernanceSystem().update(w1, 130)
    eff1 = _death_stage_effs(w1)[0]
    assert eff1.duration == 4

    # 序列化鬼魂 + death_stage EffectComp
    ghost_data = {
        "Marks": serialize_component(w1.get(p, Marks)),
        "Position": serialize_component(w1.get(p, Position)),
    }
    eff_data = serialize_component(eff1)

    # 冷重启：反序列化到新 world（崩溃期间无 tick 推进，duration 不衰减）
    w2 = World()
    _make_room(w2, DEATH_ROOM)
    new_p = w2.new_entity()
    w2.add(new_p, deserialize_component(Marks, ghost_data["Marks"]))
    w2.add(new_p, deserialize_component(Position, ghost_data["Position"]))
    eff_eid = w2.new_entity()
    w2.add(eff_eid, deserialize_component(EffectComp, eff_data))

    # 鬼魂仍在阴间
    assert GHOST_FLAG in w2.get(new_p, Marks).flags
    assert w2.get(new_p, Position).room_id == DEATH_ROOM
    # death_stage 进度继续（duration=4，未因崩溃衰减）
    eff2 = _death_stage_effs(w2)[0]
    assert eff2.duration == 4
    # 冷重启 next_tick 对齐（ADR-0022 §6）：next_tick < current_tick 时顺延一周期
    # 此处 next_tick=135，若 current_tick=200（>135），update 触发但只推进一段
    # （不补执行崩溃期间的段，符合"顺延不补执行"）


def test_death_stage_no_decay_during_pause() -> None:
    """崩溃期间剧情暂停：tick 不推进时 duration 不衰减。

    模拟：启动 death_stage 后不调 update（引擎停摆），duration 保持 5。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    p = _make_player(w, is_ghost=True)
    enter_underworld(w, p, tick=100)

    # 不调 update（"崩溃期间"），duration 保持 5
    assert _death_stage_effs(w)[0].duration == 5


# ═══════════════════ E. 黑无常 is_ghost 检测（决策 4） ═══════════════════


def test_bgargoyle_living_teleport_to_wumiao() -> None:
    """黑无常 detail="bgargoyle" + 活人（!is_ghost）-> 传送回 city/wumiao。

    对照 bgargoyle.c:60-66 ob->move("/d/city/wumiao")。
    death_stage_handler 返回 new_duration=0，update 移除 EffectComp。
    """
    w = World()
    _make_room(w, "death/gate")
    _make_room(w, BGARGOYLE_LIVING_TELEPORT)
    living = _make_player(w, room_id="death/gate", is_ghost=False)  # 活人

    # 手动构造 bgargoyle death_stage EffectComp（黑无常剧情）
    eff_eid = w.new_entity()
    w.add(
        eff_eid,
        EffectComp(
            effect_id=DEATH_STAGE_EFFECT_ID,
            kind=DEATH_STAGE_KIND,
            target_id=living,
            source_id=0,
            detail="bgargoyle",
            duration=5,
            tick_interval=DEATH_STAGE_INTERVAL,
            next_tick=30,
        ),
    )

    GovernanceSystem().update(w, 30)

    # 活人被传送回 wumiao
    assert w.get(living, Position).room_id == BGARGOYLE_LIVING_TELEPORT
    # death_stage EffectComp 被移除（new_duration=0 触发移除 + reincarnate_at）
    assert _death_stage_effs(w) == []


def test_bgargoyle_handler_living_returns_zero_duration() -> None:
    """death_stage_handler 黑无常活人分支返回 new_duration=0 + 传送消息。"""
    w = World()
    _make_room(w, BGARGOYLE_LIVING_TELEPORT)
    living = _make_player(w, is_ghost=False)
    eff = EffectComp(
        effect_id=DEATH_STAGE_EFFECT_ID,
        kind=DEATH_STAGE_KIND,
        target_id=living,
        detail="bgargoyle",
        duration=5,
        tick_interval=5,
        next_tick=30,
    )
    r = death_stage_handler(w, eff, tick=30)
    assert r.new_duration == 0
    assert len(r.messages) == 1
    # 活人被传送（handler 内 move_to）
    assert w.get(living, Position).room_id == BGARGOYLE_LIVING_TELEPORT


def test_wgargoyle_does_not_check_is_ghost() -> None:
    """白无常 detail="wgargoyle" 不检测 is_ghost：鬼魂正常推进剧情。

    白无常是鬼门关入口，只对 ghost 启动；活人不会进入白无常剧情（无活人分支）。
    """
    w = World()
    _make_room(w, DEATH_ROOM)
    ghost = _make_player(w, room_id=DEATH_ROOM, is_ghost=True)
    eff = EffectComp(
        effect_id=DEATH_STAGE_EFFECT_ID,
        kind=DEATH_STAGE_KIND,
        target_id=ghost,
        detail="wgargoyle",
        duration=5,
        tick_interval=5,
        next_tick=30,
    )
    r = death_stage_handler(w, eff, tick=30)
    # 鬼魂正常推进（不传送）
    assert r.new_duration == 4
    assert w.get(ghost, Position).room_id == DEATH_ROOM  # 未被传送


# ═══════════════════ F. 法院通缉 condition 框架（验收 6） ═══════════════════


@pytest.mark.parametrize(
    ("region", "effect_id"),
    [
        ("city", "killer"),
        ("xa", "xakiller"),
        ("dl", "dlkiller"),
        ("bj", "bjkiller"),
    ],
)
def test_apply_wanted_four_regions(region: str, effect_id: str) -> None:
    """apply_wanted 四区域：city/xa/dl/bj -> killer/xakiller/dlkiller/bjkiller。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, region)
    assert query_condition(w, p, effect_id) == WANTED_DURATION


def test_apply_wanted_unknown_region_no_op() -> None:
    """未知 region 不施加（fail-closed，不静默 fallback 到通用 killer）。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, "unknown_region")
    assert query_condition(w, p, "killer") == 0
    assert query_wanted(w, p) is None


def test_apply_wanted_custom_duration() -> None:
    """apply_wanted 自定义 duration（调用方可指定非默认时长）。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, "city", duration=50)
    assert query_condition(w, p, "killer") == 50


@pytest.mark.parametrize(
    ("region",),
    [("city",), ("xa",), ("dl",), ("bj",)],
)
def test_query_wanted_returns_region(region: str) -> None:
    """query_wanted 返回 region（"city" 等）或 None（无通缉）。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, region)
    assert query_wanted(w, p) == region


def test_query_wanted_none_when_no_wanted() -> None:
    """无通缉 condition 时 query_wanted 返回 None。"""
    w = World()
    p = _make_player(w)
    assert query_wanted(w, p) is None


def test_bjkiller_supported_without_lpc_condition_file() -> None:
    """bjkiller 无 LPC condition 文件也支持（apply_condition 直接施加，走 _default
    衰减容错）。bjkiller 无注册 handler，ConditionSystem.update 走 _default_trigger
    衰减。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, "bj")
    assert query_condition(w, p, "bjkiller") == WANTED_DURATION
    # bjkiller 无 handler，_default_trigger 衰减（duration-1）
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, p, "bjkiller") == WANTED_DURATION - 1


def test_query_wanted_first_match_deterministic() -> None:
    """多 condition 同时存在时返回首个匹配（WANTED_REGIONS 迭代顺序，无 random）。"""
    w = World()
    p = _make_player(w)
    # 同时施加 city 和 xa 通缉
    apply_wanted(w, p, "city")
    apply_wanted(w, p, "xa")
    # WANTED_REGIONS 迭代顺序：city 在 xa 前 -> 返回 "city"
    result = query_wanted(w, p)
    assert result == "city"


# ═══════════════════ G. 审判收监（验收 7） ═══════════════════


@pytest.mark.parametrize(
    ("pks", "expected_sentence"),
    [
        (100, SENTENCE_DURATION_HIGH),  # PKS>99 => 500
        (75, SENTENCE_DURATION_MID),  # PKS>74 => 300
        (50, SENTENCE_DURATION_LOW),  # PKS>49 => 200
        (99, SENTENCE_DURATION_MID),  # PKS=99 不>99，走 MID（>74）
        (74, SENTENCE_DURATION_LOW),  # PKS=74 不>74，走 LOW（>49）
        (49, 0),  # PKS=49 不>49，不量刑
        (0, 0),  # PKS=0 不量刑
    ],
)
def test_proceed_sentencing_pks_grading(pks: int, expected_sentence: int) -> None:
    """proceed_sentencing PKS 分级量刑（>99=>500 / >74=>300 / >49=>200 / <=49=>0）。"""
    w = World()
    p = _make_player(w, pks=pks, combat_exp=0)  # combat_exp=0 避免经验转移干扰
    arrester = _make_arrester(w)
    sentence = proceed_sentencing(w, p, arrester)
    assert sentence == expected_sentence
    if expected_sentence > 0:
        assert query_condition(w, p, "city_jail") == expected_sentence
    else:
        assert query_condition(w, p, "city_jail") == 0


def test_proceed_sentencing_embedded_flag() -> None:
    """穿琵琶骨：Marks.flags 含 EMBEDDED_FLAG（对照 set("embedded", 1)）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=0)
    arrester = _make_arrester(w)
    proceed_sentencing(w, p, arrester)
    assert EMBEDDED_FLAG in w.get(p, Marks).flags


def test_proceed_sentencing_clears_inventory() -> None:
    """审判清空被审 eid 的 Inventory（destruct 所有物品）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=0, items={"sword", "armor"})
    arrester = _make_arrester(w)
    proceed_sentencing(w, p, arrester)
    assert w.get(p, Inventory).items == set()


def test_proceed_sentencing_exp_transfer_high_pks() -> None:
    """经验转移：PKS>99 时 arrester.combat_exp += bonus（combat_exp//10，上限 3000）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=10000)
    arrester = _make_arrester(w, combat_exp=0)
    proceed_sentencing(w, p, arrester)
    # bonus = min(10000//10, 3000) = 1000，PKS>99 全额转移
    assert w.get(arrester, Progression).combat_exp == 1000
    # 被审方扣减
    assert w.get(p, Progression).combat_exp == 10000 - 1000


def test_proceed_sentencing_exp_transfer_cap_3000() -> None:
    """经验转移上限 3000（combat_exp//10 > 3000 时截断）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=100000)  # 100000//10=10000 > 3000
    arrester = _make_arrester(w, combat_exp=0)
    proceed_sentencing(w, p, arrester)
    assert w.get(arrester, Progression).combat_exp == SENTENCE_EXP_TRANSFER_CAP


def test_proceed_sentencing_exp_transfer_mid_pks_two_thirds() -> None:
    """PKS>74（MID）经验转移 = bonus * 2 // 3。"""
    w = World()
    p = _make_player(w, pks=75, combat_exp=9000)  # bonus=900
    arrester = _make_arrester(w, combat_exp=0)
    proceed_sentencing(w, p, arrester)
    # bonus * 2 // 3 = 900 * 2 // 3 = 600
    assert w.get(arrester, Progression).combat_exp == 600


def test_proceed_sentencing_exp_transfer_low_pks_half() -> None:
    """PKS>49（LOW）经验转移 = bonus // 2。"""
    w = World()
    p = _make_player(w, pks=50, combat_exp=8000)  # bonus=800
    arrester = _make_arrester(w, combat_exp=0)
    proceed_sentencing(w, p, arrester)
    # bonus // 2 = 400
    assert w.get(arrester, Progression).combat_exp == 400


def test_proceed_sentencing_clears_existing_conditions() -> None:
    """proceed_sentencing 先 clear_condition（清所有 condition，对照 kexiu.c:192）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=0)
    apply_condition(w, p, "killer", 100)
    apply_condition(w, p, "poisoned", 10)
    arrester = _make_arrester(w)
    proceed_sentencing(w, p, arrester)
    # killer/poisoned 被清（city_jail 是 proceed 后新施加的）
    assert query_condition(w, p, "killer") == 0
    assert query_condition(w, p, "poisoned") == 0


def test_proceed_sentencing_returns_sentence_int() -> None:
    """proceed_sentencing 返回刑期 int（对照 apply_condition("city_jail", N) 的 N）。"""
    w = World()
    p = _make_player(w, pks=100, combat_exp=0)
    arrester = _make_arrester(w)
    sentence = proceed_sentencing(w, p, arrester)
    assert isinstance(sentence, int)
    assert sentence == SENTENCE_DURATION_HIGH


def test_proceed_sentencing_recidivist_aggravation() -> None:
    """累犯加重（city_jail>4 => 600）覆盖分级量刑（ADR-0029 §5）。

    被审实体已有 city_jail>4（累犯在押）+ PKS>99（HIGH 500）时，累犯加重
    覆盖为 600（SENTENCE_DURATION_RECIDIVIST）。对照 LPC kexiu.c:229-230：
    累犯检测在 clear_condition 之前查 city_jail（修复前 clear 在前导致死代码，
    修复后累犯加重生效）。
    """
    w = World()
    p = _make_player(w, pks=100, combat_exp=0)
    arrester = _make_arrester(w)
    # 先施加 city_jail duration=10（模拟累犯在押）
    apply_condition(w, p, "city_jail", 10)
    assert query_condition(w, p, "city_jail") == 10

    sentence = proceed_sentencing(w, p, arrester)
    # 累犯加重覆盖 HIGH 500 -> 600（RECIDIVIST）
    assert sentence == SENTENCE_DURATION_RECIDIVIST
    # clear 后重新施加 city_jail 刑期 600
    assert query_condition(w, p, "city_jail") == SENTENCE_DURATION_RECIDIVIST


def test_proceed_sentencing_low_pks_no_jail_no_exp_transfer() -> None:
    """PKS<=49 不量刑：sentence=0 + 不施加 city_jail + 不转移经验。"""
    w = World()
    p = _make_player(w, pks=10, combat_exp=10000)
    arrester = _make_arrester(w, combat_exp=0)
    sentence = proceed_sentencing(w, p, arrester)
    assert sentence == 0
    assert query_condition(w, p, "city_jail") == 0
    # 低 PKS 不转移经验
    assert w.get(arrester, Progression).combat_exp == 0
    assert w.get(p, Progression).combat_exp == 10000


# ═══════════════════ H. 受贿销案 ═══════════════════


def test_bribe_clear_wanted_sufficient_amount() -> None:
    """受贿销案：amount >= combat_exp//10 -> 清 killer 返回 True。"""
    w = World()
    p = _make_player(w, combat_exp=10000)  # 阈值 = 1000
    apply_condition(w, p, "killer", 100)
    # amount=1000 >= 1000 -> 销案
    assert bribe_clear_wanted(w, p, 1000) is True
    assert query_condition(w, p, "killer") == 0


def test_bribe_clear_wanted_more_than_threshold() -> None:
    """受贿销案：amount > 阈值也销案（>= 含等号，超也成立）。"""
    w = World()
    p = _make_player(w, combat_exp=10000)  # 阈值 1000
    apply_condition(w, p, "killer", 100)
    assert bribe_clear_wanted(w, p, 5000) is True
    assert query_condition(w, p, "killer") == 0


def test_bribe_clear_wanted_insufficient_amount() -> None:
    """受贿销案：amount < 阈值 -> 返回 False（不清除）。"""
    w = World()
    p = _make_player(w, combat_exp=10000)  # 阈值 1000
    apply_condition(w, p, "killer", 100)
    # amount=999 < 1000 -> 不足
    assert bribe_clear_wanted(w, p, 999) is False
    assert query_condition(w, p, "killer") == 100  # 未清


def test_bribe_clear_wanted_no_killer_returns_false() -> None:
    """受贿销案：无 killer condition 时 clear_one_condition 返回 False。"""
    w = World()
    p = _make_player(w, combat_exp=1000)  # 阈值 100
    # amount 足够但无 killer condition
    assert bribe_clear_wanted(w, p, 200) is False


def test_bribe_threshold_zero_combat_exp() -> None:
    """combat_exp=0 时阈值=0，任意正金额销案（amount >= 0）。"""
    w = World()
    p = _make_player(w, combat_exp=0)  # 阈值 0
    apply_condition(w, p, "killer", 100)
    assert bribe_clear_wanted(w, p, 0) is True  # 0 >= 0


# ═══════════════════ I. 监狱释放（衔接 conditions jail handler） ═══════════════════


@pytest.mark.parametrize(
    ("jail_type", "release_room"),
    [
        ("city_jail", "city/yamen"),
        ("dali_jail", "dali/taihejie5"),
        ("bonze_jail", "shaolin/guangchang1"),
    ],
)
def test_release_from_jail_moves_and_sets_startroom(jail_type: str, release_room: str) -> None:
    """release_from_jail：move 到 JAIL_ROOMS[jail_type] + 设 startroom 标记。"""
    w = World()
    _make_room(w, release_room)
    p = _make_player(w, room_id="jail/cell")
    release_from_jail(w, p, jail_type)
    assert w.get(p, Position).room_id == release_room
    # startroom 标记（Marks.flags 含 "startroom:{room}"）
    assert f"{STARTROOM_FLAG_PREFIX}:{release_room}" in w.get(p, Marks).flags


def test_release_from_jail_unknown_type_no_op() -> None:
    """未知 jail_type 不释放（fail-closed）。"""
    w = World()
    p = _make_player(w, room_id="jail/cell")
    release_from_jail(w, p, "unknown_jail")
    assert w.get(p, Position).room_id == "jail/cell"  # 未移动


def test_jail_condition_expire_triggers_release_via_condition_system() -> None:
    """city_jail condition 到期（ConditionSystem.update 推进 duration 到 0）->
    衔接 release_from_jail move 到 city/yamen + 设 startroom。

    ADR-0029 §决策 5 + 开放问题 2：jail 到期 move 由 ConditionSystem 触发，
    调 governance.release_from_jail。
    """
    w = World()
    _make_room(w, "city/yamen")
    p = _make_player(w, room_id="jail/cell")
    # 施加 city_jail duration=1（下 tick 到期）
    apply_condition(w, p, "city_jail", 1)

    ConditionSystem().update(w, tick=0)

    # 到期 -> release_from_jail move + startroom
    assert w.get(p, Position).room_id == "city/yamen"
    assert "startroom:city/yamen" in w.get(p, Marks).flags
    # city_jail EffectComp 被移除
    assert query_condition(w, p, "city_jail") == 0


def test_jail_condition_not_expired_no_release() -> None:
    """city_jail 未到期不释放（duration>1 时纯衰减）。"""
    w = World()
    _make_room(w, "city/yamen")
    p = _make_player(w, room_id="jail/cell")
    apply_condition(w, p, "city_jail", 5)  # duration=5，未到期

    ConditionSystem().update(w, tick=0)

    # 未到期 -> 不释放，仍在监狱
    assert w.get(p, Position).room_id == "jail/cell"
    assert query_condition(w, p, "city_jail") == 4  # 衰减到 4


def test_dali_jail_expire_release_room() -> None:
    """dali_jail 到期 -> move 到 dali/taihejie5。"""
    w = World()
    _make_room(w, "dali/taihejie5")
    p = _make_player(w, room_id="jail/cell")
    apply_condition(w, p, "dali_jail", 1)

    ConditionSystem().update(w, tick=0)

    assert w.get(p, Position).room_id == "dali/taihejie5"
    assert "startroom:dali/taihejie5" in w.get(p, Marks).flags


def test_bonze_jail_expire_release_room() -> None:
    """bonze_jail 到期 -> move 到 shaolin/guangchang1。"""
    w = World()
    _make_room(w, "shaolin/guangchang1")
    p = _make_player(w, room_id="jail/cell")
    apply_condition(w, p, "bonze_jail", 1)

    ConditionSystem().update(w, tick=0)

    assert w.get(p, Position).room_id == "shaolin/guangchang1"
    assert "startroom:shaolin/guangchang1" in w.get(p, Marks).flags


# ═══════════════════ J. 可序列化（验收 8） ═══════════════════


@pytest.mark.parametrize(
    ("region", "effect_id"),
    [
        ("city", "killer"),
        ("xa", "xakiller"),
        ("dl", "dlkiller"),
        ("bj", "bjkiller"),
    ],
)
def test_wanted_condition_serialization_roundtrip(region: str, effect_id: str) -> None:
    """WantedCondition（EffectComp effect_id=killer 等）序列化往返一致性。"""
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, region, duration=77)
    # 找到施加的 EffectComp
    eff = None
    for e in w.entities_with(EffectComp):
        ec = w.get(e, EffectComp)
        if ec is not None and ec.target_id == p and ec.effect_id == effect_id:
            eff = ec
            break
    assert eff is not None

    data = serialize_component(eff)
    restored = deserialize_component(EffectComp, data)
    assert restored == eff
    assert restored.effect_id == effect_id
    assert restored.duration == 77
    assert restored.target_id == p


def test_death_stage_effectcomp_full_fields_roundtrip() -> None:
    """death_stage EffectComp 序列化往返（duration/next_tick/tick_interval 完整恢复）。"""
    eff = EffectComp(
        effect_id=DEATH_STAGE_EFFECT_ID,
        kind=DEATH_STAGE_KIND,
        target_id=99,
        source_id=5,
        detail="bgargoyle",
        duration=2,
        tick_interval=DEATH_STAGE_INTERVAL,
        next_tick=140,
    )
    data = serialize_component(eff)
    restored = deserialize_component(EffectComp, data)
    assert restored == eff
    # 关键崩溃恢复字段
    assert restored.duration == 2
    assert restored.next_tick == 140
    assert restored.tick_interval == DEATH_STAGE_INTERVAL


def test_ghost_player_with_death_stage_survives_cold_restart() -> None:
    """冷重启场景：ghost 玩家 + death_stage EffectComp 序列化 -> 反序列化到新 world
    -> 鬼魂仍在阴间 + death_stage 进度继续。"""
    w1 = World()
    _make_room(w1, DEATH_ROOM)
    p = _make_player(w1, room_id=DEATH_ROOM, is_ghost=True)
    enter_underworld(w1, p, tick=100)
    # 推进到 duration=3（next_tick=140）
    gs = GovernanceSystem()
    gs.update(w1, 130)  # 5->4
    gs.update(w1, 135)  # 4->3
    eff1 = _death_stage_effs(w1)[0]
    assert eff1.duration == 3
    assert eff1.next_tick == 140

    # 序列化鬼魂状态 + death_stage EffectComp
    marks_data = serialize_component(w1.get(p, Marks))
    pos_data = serialize_component(w1.get(p, Position))
    eff_data = serialize_component(eff1)

    # 冷重启到新 world
    w2 = World()
    _make_room(w2, DEATH_ROOM)
    new_p = w2.new_entity()
    w2.add(new_p, deserialize_component(Marks, marks_data))
    w2.add(new_p, deserialize_component(Position, pos_data))
    eff_eid = w2.new_entity()
    w2.add(eff_eid, deserialize_component(EffectComp, eff_data))

    # 鬼魂仍在阴间
    assert GHOST_FLAG in w2.get(new_p, Marks).flags
    assert w2.get(new_p, Position).room_id == DEATH_ROOM
    # death_stage 进度继续（duration=3，未因崩溃衰减）
    eff2 = _death_stage_effs(w2)[0]
    assert eff2.duration == 3
    assert eff2.next_tick == 140
    # 推进可继续（tick=140 触发下一段）
    gs.update(w2, 140)
    assert _death_stage_effs(w2)[0].duration == 2


# ═══════════════════ K. hypothesis 属性测试（验收 10） ═══════════════════


@given(
    duration=st.integers(min_value=1, max_value=200),
    n_ticks=st.integers(min_value=0, max_value=250),
)
@settings(max_examples=50, deadline=None)
def test_prop_wanted_duration_decays_linearly(duration: int, n_ticks: int) -> None:
    """通缉时长衰减属性：apply_wanted(duration=d) -> N tick 后 query_condition =
    max(0, d-N)（线性衰减，每 tick -1）。

    ADR-0029 §验收 10 + §决策 5：通缉 condition 走 ConditionSystem 通用衰减。
    ConditionSystem 非均匀 tick：next_tick<=tick 才触发，故每次 update 递增 tick。
    """
    w = World()
    p = _make_player(w)
    apply_wanted(w, p, "city", duration=duration)

    cs = ConditionSystem()
    # 递增 tick（apply_condition 设 next_tick=0，tick_interval=1）
    for t in range(n_ticks):
        cs.update(w, tick=t)

    expected = max(0, duration - n_ticks)
    assert query_condition(w, p, "killer") == expected


@given(
    pks1=st.integers(min_value=0, max_value=10000),
    pks2=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100, deadline=None)
def test_prop_sentencing_monotonic_in_pks(pks1: int, pks2: int) -> None:
    """量刑分级单调性：PKS 越高刑期越长（pks1<pks2 => sentence(pks1) <= sentence(pks2)）。

    同档相等（99/100 同档 500，74/75 同档 300，49/50 同档 200，0-49 同档 0）。
    ADR-0029 §验收 10 + §决策 5：PKS 分级 if-else 确定性无 random。
    """
    if pks1 > pks2:
        pks1, pks2 = pks2, pks1  # 保证 pks1 <= pks2

    w1 = World()
    p1 = _make_player(w1, pks=pks1, combat_exp=0)
    a1 = _make_arrester(w1)
    s1 = proceed_sentencing(w1, p1, a1)

    w2 = World()
    p2 = _make_player(w2, pks=pks2, combat_exp=0)
    a2 = _make_arrester(w2)
    s2 = proceed_sentencing(w2, p2, a2)

    # 单调：pks1 <= pks2 => s1 <= s2
    assert s1 <= s2, f"pks1={pks1} s1={s1} > pks2={pks2} s2={s2}"


@given(
    pks=st.integers(min_value=100, max_value=10000),
)
@settings(max_examples=30, deadline=None)
def test_prop_sentencing_high_pks_always_500(pks: int) -> None:
    """PKS>99 恒判 500（HIGH 档上限，不随 PKS 增长）。

    验证分级阈值 99 的严格性（>99 触发 HIGH）。
    """
    w = World()
    p = _make_player(w, pks=pks, combat_exp=0)
    a = _make_arrester(w)
    assert proceed_sentencing(w, p, a) == SENTENCE_DURATION_HIGH


# ═══════════════════ L. test_theme_neutrality 硬门禁（验收 12） ═══════════════════


def test_governance_source_no_wuxia_weapon_literals() -> None:
    """治理逻辑常量区无武侠武学/门派语义字面量（grep sword/blade 在治理逻辑区无命中）。

    ADR-0029 §关键约束 4：本模块源码无武侠门派/武学字面量。通缉/阴间/监狱/黑白
    无常是通用治理概念（阴间神话非武侠烙印）。

    注意：JAIL_ROOMS 中的 "shaolin/guangchang1" / "bonze_jail" 是 ADR-0029 §5
    监狱表硬性规格（监狱位置题材绑定，LPC 原文 room_id 保真），是 room_id 常量
    非武学字面量，必须保留。本测试 grep 治理逻辑常量区不含武学词。
    """
    import xkx.runtime.governance as gov

    src = inspect.getsource(gov)
    # 治理逻辑不含武学武器字面量（sword/blade/saber 等）
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src
    assert '"saber"' not in src and "'saber'" not in src
    # 不含门派武学招式名（dodge/parry 是 condition handler 语义非武学）
    # 阴间/通缉/监狱/无常是通用治理概念，非武侠烙印


def test_governance_imports_cleanly() -> None:
    """governance 模块可正常 import（test_theme_neutrality 现有门禁持续通过）。

    governance.py 含 shaolin/guangchang1 / bonze_jail 等 room_id 常量，是
    ADR-0029 §5 监狱表硬性规格（监狱位置题材绑定），现有 test_theme_neutrality
    只 grep resolve_attack 模块，governance 自动通过。本测试确认 import 无异常。
    """
    import xkx.runtime.governance as gov

    # 关键治理接口存在（平台级 fail-closed System + 阴间 + 法院 API）
    assert hasattr(gov, "GovernanceSystem")
    assert hasattr(gov, "enter_underworld")
    assert hasattr(gov, "reincarnate_at")
    assert hasattr(gov, "apply_wanted")
    assert hasattr(gov, "query_wanted")
    assert hasattr(gov, "proceed_sentencing")
    assert hasattr(gov, "bribe_clear_wanted")
    assert hasattr(gov, "release_from_jail")


def test_governance_system_is_system_subclass() -> None:
    """GovernanceSystem 是 System 子类（平台级 fail-closed Python System）。"""
    from xkx.runtime.systems import System

    assert issubclass(GovernanceSystem, System)
    assert GovernanceSystem.name == "GovernanceSystem"
