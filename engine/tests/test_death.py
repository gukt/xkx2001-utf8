"""死亡轮回测试（阶段 2.2，对照 LPC feature/damage.c + combatd.c + chard.c）。

验证 die/unconcious/revive/reincarnate/death_penalty/killer_reward/make_corpse/
check_death + die vs unconcious 触发条件 + death_penalty 确定性。
"""

from __future__ import annotations

from xkx.runtime.components import (
    Attributes,
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.conditions import apply_condition, query_condition
from xkx.runtime.death import (
    DEATH_ROOM,
    GHOST_FLAG,
    UNCONSCIOUS_FLAG,
    check_death,
    death_penalty,
    die,
    killer_reward,
    make_corpse,
    reincarnate,
    revive,
    unconcious,
)
from xkx.runtime.ecs import World


def _make_player(
    world: World,
    *,
    qi: int = 100,
    max_qi: int = 100,
    eff_qi: int = 100,
    jing: int = 100,
    max_jing: int = 100,
    eff_jing: int = 100,
    jingli: int = 100,
    max_jingli: int = 100,
    combat_exp: int = 5000,
    potential: int = 100,
    room_id: str = "city/room1",
    con: int = 20,
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="player", is_player=True))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Attributes(con_=con))
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
            max_neili=100,
        ),
    )
    world.add(eid, Progression(combat_exp=combat_exp, potential=potential))
    return eid


def _make_npc(
    world: World, *, qi: int = 100, max_qi: int = 100, room_id: str = "city/room1"
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="npc", is_player=False))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Attributes(con_=20))
    world.add(eid, Vitals(qi=qi, max_qi=max_qi, eff_qi=max_qi, max_neili=100))
    return eid


def _make_room(world: World, *, room_id: str = "city/room1", no_death: bool = False) -> int:
    eid = world.new_entity()
    world.add(eid, RoomComp(room_id=room_id, short="room", long="room", no_death=no_death))
    return eid


# ---- check_death 触发条件 ----


def test_check_death_eff_qi_negative_dies() -> None:
    """eff_qi<0 直接触发 die（致命伤）。"""
    w = World()
    _make_room(w)
    p = _make_player(w, eff_qi=-1)
    assert check_death(w, p, tick=0) is True
    assert GHOST_FLAG in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == DEATH_ROOM


def test_check_death_qi_negative_unconcious() -> None:
    """qi<0 且 living 触发 unconcious（首次昏迷）。"""
    w = World()
    _make_room(w)
    p = _make_player(w, qi=-1)
    assert check_death(w, p, tick=0) is True
    assert UNCONSCIOUS_FLAG in w.get(p, Marks).flags
    v = w.get(p, Vitals)
    assert v.qi == 0
    assert v.jing == 0


def test_check_death_qi_negative_already_unconscious_dies() -> None:
    """qi<0 且已昏迷（!living）触发 die（昏迷中再受创->死）。"""
    w = World()
    _make_room(w)
    p = _make_player(w, qi=-1)
    w.add(p, Marks(flags={UNCONSCIOUS_FLAG}))
    assert check_death(w, p, tick=0) is True
    assert GHOST_FLAG in w.get(p, Marks).flags


def test_check_death_no_trigger_when_healthy() -> None:
    """健康状态不触发死亡/昏迷。"""
    w = World()
    _make_room(w)
    p = _make_player(w, qi=100)
    assert check_death(w, p, tick=0) is False


# ---- die 主流程 ----


def test_die_player_ghost_and_move_death_room() -> None:
    """玩家 die 后 ghost=1 + move DEATH_ROOM + 血量清 1。"""
    w = World()
    _make_room(w)
    p = _make_player(w)
    die(w, p)
    v = w.get(p, Vitals)
    assert v.qi == 1
    assert v.eff_qi == 1
    assert GHOST_FLAG in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == DEATH_ROOM


def test_die_npc_removes_position() -> None:
    """NPC die 后移除 Position（从房间消失）。"""
    w = World()
    _make_room(w)
    npc = _make_npc(w)
    die(w, npc)
    assert w.get(npc, Position) is None


def test_die_no_death_room_player_unconcious() -> None:
    """no_death 房玩家 die 转 unconcious（不真死，不进鬼魂）。"""
    w = World()
    _make_room(w, room_id="safe", no_death=True)
    p = _make_player(w, room_id="safe")
    die(w, p)
    assert UNCONSCIOUS_FLAG in w.get(p, Marks).flags
    assert GHOST_FLAG not in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == "safe"


def test_die_clears_conditions() -> None:
    """die 清除所有 condition。"""
    w = World()
    _make_room(w)
    p = _make_player(w)
    apply_condition(w, p, "poisoned", 10)
    die(w, p)
    assert query_condition(w, p, "poisoned") == 0


# ---- die 阴间剧情衔接（2.6 ADR-0029 §决策 6 衔接协议）----


def test_die_player_starts_death_stage_effectcomp() -> None:
    """玩家 die 衔接 governance.enter_underworld：启动 death_stage EffectComp。

    ADR-0029 §决策 3/6：die 玩家分支 ghost=1 + move DEATH_ROOM 后调
    ``governance.enter_underworld``，启动黑白无常 5 段剧情 EffectComp（首延
    30 秒，next_tick=tick+30）。gate.c 物品销毁清空鬼魂 Inventory。
    """
    from xkx.runtime.components import EffectComp, Inventory
    from xkx.runtime.governance import DEATH_STAGE_EFFECT_ID, DEATH_STAGE_KIND

    w = World()
    _make_room(w)
    p = _make_player(w)
    w.add(p, Inventory(items={"sword", "potion"}))
    die(w, p, tick=100)
    # ghost=1 + move DEATH_ROOM 保留（2.2 核心行为不变）
    assert GHOST_FLAG in w.get(p, Marks).flags
    assert w.get(p, Position).room_id == DEATH_ROOM
    # gate.c 物品销毁（鬼魂 Inventory 清空）
    assert w.get(p, Inventory).items == set()
    # 启动 death_stage EffectComp（首延 30 秒，next_tick=100+30=130）
    death_effs = [
        w.get(e, EffectComp)
        for e in w.entities_with(EffectComp)
        if w.get(e, EffectComp) is not None
        and w.get(e, EffectComp).effect_id == DEATH_STAGE_EFFECT_ID
    ]
    assert len(death_effs) == 1
    eff = death_effs[0]
    assert eff.kind == DEATH_STAGE_KIND
    assert eff.target_id == p
    assert eff.detail == "wgargoyle"  # 主路径白无常入口
    assert eff.duration == 5  # 5 段剧情
    assert eff.next_tick == 130  # tick=100 + 首延 30


def test_die_player_default_tick_first_delay_30() -> None:
    """die 无 tick 参数（默认 0）时 death_stage 首延 next_tick=30（向后兼容）。"""
    from xkx.runtime.components import EffectComp
    from xkx.runtime.governance import DEATH_STAGE_EFFECT_ID

    w = World()
    _make_room(w)
    p = _make_player(w)
    die(w, p)  # tick 默认 0
    death_effs = [
        w.get(e, EffectComp)
        for e in w.entities_with(EffectComp)
        if w.get(e, EffectComp) is not None
        and w.get(e, EffectComp).effect_id == DEATH_STAGE_EFFECT_ID
    ]
    assert len(death_effs) == 1
    assert death_effs[0].next_tick == 30  # 0 + 首延 30


def test_die_npc_no_death_stage_effectcomp() -> None:
    """NPC die 不启动阴间剧情（仅玩家分支衔接 enter_underworld）。"""
    from xkx.runtime.components import EffectComp
    from xkx.runtime.governance import DEATH_STAGE_EFFECT_ID

    w = World()
    _make_room(w)
    npc = _make_npc(w)
    die(w, npc, tick=5)
    death_effs = [
        w.get(e, EffectComp)
        for e in w.entities_with(EffectComp)
        if w.get(e, EffectComp) is not None
        and w.get(e, EffectComp).effect_id == DEATH_STAGE_EFFECT_ID
    ]
    assert death_effs == []


def test_die_no_death_room_player_no_underworld() -> None:
    """no_death 房玩家 die 转 unconcious，不衔接阴间（早退分支）。"""
    from xkx.runtime.components import EffectComp
    from xkx.runtime.governance import DEATH_STAGE_EFFECT_ID

    w = World()
    _make_room(w, room_id="safe", no_death=True)
    p = _make_player(w, room_id="safe")
    die(w, p, tick=10)
    # no_death 房转 unconcious，不进鬼魂/阴间
    assert GHOST_FLAG not in w.get(p, Marks).flags
    death_effs = [
        w.get(e, EffectComp)
        for e in w.entities_with(EffectComp)
        if w.get(e, EffectComp) is not None
        and w.get(e, EffectComp).effect_id == DEATH_STAGE_EFFECT_ID
    ]
    assert death_effs == []


def test_check_death_passes_tick_to_die_underworld() -> None:
    """check_death 透传 tick 给 die -> enter_underworld（next_tick=tick+30）。"""
    from xkx.runtime.components import EffectComp
    from xkx.runtime.governance import DEATH_STAGE_EFFECT_ID

    w = World()
    _make_room(w)
    p = _make_player(w, eff_qi=-1)  # 致命伤触发 die
    assert check_death(w, p, tick=50) is True
    death_effs = [
        w.get(e, EffectComp)
        for e in w.entities_with(EffectComp)
        if w.get(e, EffectComp) is not None
        and w.get(e, EffectComp).effect_id == DEATH_STAGE_EFFECT_ID
    ]
    assert len(death_effs) == 1
    # check_death tick=50 透传 -> next_tick=50+30=80
    assert death_effs[0].next_tick == 80


# ---- unconcious / revive / reincarnate ----


def test_unconcious_clears_vitals_and_sets_flag() -> None:
    """unconcious 清零 qi/jing/jingli + 设 unconscious 标记 + revive 定时器。"""
    w = World()
    _make_room(w)
    p = _make_player(w, qi=50, jing=50, jingli=50)
    unconcious(w, p)
    v = w.get(p, Vitals)
    assert v.qi == 0
    assert v.jing == 0
    assert v.jingli == 0
    assert UNCONSCIOUS_FLAG in w.get(p, Marks).flags
    assert query_condition(w, p, "revive") > 0


def test_unconcious_skips_if_already_unconscious() -> None:
    """已昏迷不再触发 unconcious（LPC 前置条件）。"""
    w = World()
    _make_room(w)
    p = _make_player(w, qi=50)
    w.add(p, Marks(flags={UNCONSCIOUS_FLAG}))
    unconcious(w, p)
    assert w.get(p, Vitals).qi == 50  # 未清零


def test_revive_clears_flag() -> None:
    """revive 清 unconscious 标记 + 移除 revive 定时器。"""
    w = World()
    p = _make_player(w)
    w.add(p, Marks(flags={UNCONSCIOUS_FLAG}))
    apply_condition(w, p, "revive", 30)
    revive(w, p)
    assert UNCONSCIOUS_FLAG not in w.get(p, Marks).flags
    assert query_condition(w, p, "revive") == 0


def test_reincarnate_full_restore() -> None:
    """reincarnate 完整恢复 qi/jing/eff 到 max + 清 ghost。"""
    w = World()
    p = _make_player(w, qi=1, eff_qi=1, jing=1, eff_jing=1)
    w.add(p, Marks(flags={GHOST_FLAG}))
    reincarnate(w, p)
    v = w.get(p, Vitals)
    assert v.qi == v.max_qi
    assert v.eff_qi == v.max_qi
    assert v.jing == v.max_jing
    assert v.eff_jing == v.max_jing
    assert v.jingli == v.max_jingli
    assert GHOST_FLAG not in w.get(p, Marks).flags


# ---- death_penalty（确定性三段扣减）----


def test_death_penalty_high_exp() -> None:
    """combat_exp>5000 扣 amount=combat_exp/100 + potential 扣半。"""
    w = World()
    p = _make_player(w, combat_exp=10000, potential=100)
    death_penalty(w, p)
    prog = w.get(p, Progression)
    assert prog.combat_exp == 9900  # 10000 - 100
    assert prog.potential == 50  # 100 // 2


def test_death_penalty_mid_exp() -> None:
    """20 < combat_exp <= 5000 扣固定 20（potential 不扣）。"""
    w = World()
    p = _make_player(w, combat_exp=100, potential=100)
    death_penalty(w, p)
    prog = w.get(p, Progression)
    assert prog.combat_exp == 80  # 100 - 20
    assert prog.potential == 100


def test_death_penalty_low_exp_no_deduction() -> None:
    """combat_exp <= 20 不扣。"""
    w = World()
    p = _make_player(w, combat_exp=10, potential=100)
    death_penalty(w, p)
    prog = w.get(p, Progression)
    assert prog.combat_exp == 10
    assert prog.potential == 100


def test_death_penalty_deterministic() -> None:
    """death_penalty 无 random（同输入同输出）。"""
    w1 = World()
    p1 = _make_player(w1, combat_exp=10000, potential=100)
    w2 = World()
    p2 = _make_player(w2, combat_exp=10000, potential=100)
    death_penalty(w1, p1)
    death_penalty(w2, p2)
    assert w1.get(p1, Progression).combat_exp == w2.get(p2, Progression).combat_exp


def test_death_penalty_skill_stub() -> None:
    """skill_death_penalty stub：所有技能 -1（LPC < 0 才删除，0 级保留）。"""
    w = World()
    p = _make_player(w)
    w.add(p, Skills(levels={"unarmed": 5, "dodge": 0}))
    death_penalty(w, p)
    skills = w.get(p, Skills)
    assert skills.levels["unarmed"] == 4
    assert "dodge" not in skills.levels  # 0-1=-1 < 0 删除


# ---- killer_reward ----


def test_killer_reward_city_killer_condition() -> None:
    """killer 玩家在 /d/city/ 城区杀人施加 killer condition 100 tick。"""
    w = World()
    _make_room(w, room_id="city/room1")
    killer = _make_player(w, room_id="city/room1")
    victim = _make_player(w, room_id="city/room1")
    killer_reward(w, killer, victim)
    assert query_condition(w, killer, "killer") == 100


def test_killer_reward_non_city_no_killer_condition() -> None:
    """非城区杀人不施加 killer condition。"""
    w = World()
    _make_room(w, room_id="forest/room1")
    killer = _make_player(w, room_id="forest/room1")
    victim = _make_player(w, room_id="forest/room1")
    killer_reward(w, killer, victim)
    assert query_condition(w, killer, "killer") == 0


def test_killer_reward_pvp_pker_accumulate() -> None:
    """双玩家 PvP 施加 pker +120（叠加）。"""
    w = World()
    _make_room(w, room_id="city/room1")
    killer = _make_player(w, room_id="city/room1")
    victim = _make_player(w, room_id="city/room1")
    killer_reward(w, killer, victim)
    assert query_condition(w, killer, "pker") == 120
    killer_reward(w, killer, victim)
    assert query_condition(w, killer, "pker") == 240


def test_killer_reward_npc_victim_no_pker() -> None:
    """victim 是 NPC 不施加 pker（仅 PvP）。"""
    w = World()
    _make_room(w, room_id="city/room1")
    killer = _make_player(w, room_id="city/room1")
    victim = _make_npc(w, room_id="city/room1")
    killer_reward(w, killer, victim)
    assert query_condition(w, killer, "pker") == 0


# ---- make_corpse ----


def test_make_corpse_transfers_inventory() -> None:
    """make_corpse 生成尸体 + 物品转移到尸体。"""
    w = World()
    _make_room(w, room_id="city/room1")
    npc = _make_npc(w, room_id="city/room1")
    w.add(npc, Inventory(items={"sword", "potion"}))
    corpse_eid = make_corpse(w, npc)
    assert corpse_eid is not None
    assert w.get(corpse_eid, Inventory).items == {"sword", "potion"}
    assert w.get(npc, Inventory).items == set()


def test_make_corpse_ghost_no_corpse() -> None:
    """ghost 死者不生成尸体，物品掉环境。"""
    w = World()
    _make_room(w, room_id="city/room1")
    p = _make_player(w, room_id="city/room1")
    w.add(p, Marks(flags={GHOST_FLAG}))
    w.add(p, Inventory(items={"sword"}))
    corpse_eid = make_corpse(w, p)
    assert corpse_eid is None
    room = _find_room(w, "city/room1")
    assert "sword" in room.items


def test_make_corpse_has_identity() -> None:
    """尸体有 Identity（名字=死者名+的尸体）。"""
    w = World()
    _make_room(w, room_id="city/room1")
    npc = _make_npc(w, room_id="city/room1")
    w.add(npc, Inventory(items=set()))
    corpse_eid = make_corpse(w, npc)
    ident = w.get(corpse_eid, Identity)
    assert ident.name == "npc的尸体"
    assert "corpse" in ident.aliases


def _find_room(world: World, room_id: str) -> RoomComp:
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    raise AssertionError(f"room {room_id} not found")
