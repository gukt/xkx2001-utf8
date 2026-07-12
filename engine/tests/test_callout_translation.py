"""call_out -> Effect 翻译测试（阶段 2.4，ADR-0027 §1）。

验证两类 call_out 翻译的行为等价 + 崩溃恢复 + 中断契约 + 主题无关性：

1. **revive call_out -> EffectComp**（ADR-0027 §1.2，2.2 已实现）：
   - ``unconcious`` 启动 revive EffectComp（duration 衰减）
   - 到期（duration<=1）清 unconscious 标记（自然苏醒）
   - 崩溃恢复：duration 不衰减 + 悬空 target_id 跳过
2. **remove_call_out("revive") -> clear_one_condition**（2.2 已实现）：
   - die 中 ``revive(quiet=True)`` 强制安静苏醒，EffectComp 被移除（中断契约）
3. **start_* 同步执行 + 防御检查**（ADR-0027 §1.2，2.4 新增 auto_fight.py）：
   - auto_fight：NPC vs NPC 跳过 + looking_for_trouble 防重入 + 同步调 start_fight
   - start_fight 5 防御检查各分支 + 通过则调 on_start_fight 回调
4. **主题无关性**（ADR-0027 §1.3 + ADR-0003）：auto_fight 源码无武侠字面量

[ADR-0027](../../../docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) §1 /
[ADR-0022](../../../docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) §6 /
[feature/damage.c](../../../feature/damage.c) revive call_out /
[adm/daemons/combatd.c](../../../adm/daemons/combatd.c) auto_fight + start_*
"""

from __future__ import annotations

import asyncio
import inspect

from xkx.runtime import auto_fight as auto_fight_mod
from xkx.runtime.auto_fight import (
    LOOKING_FOR_TROUBLE_FLAG,
    FightType,
    auto_fight,
    register_start_fight_handler,
    start_fight,
)
from xkx.runtime.components import (
    EffectComp,
    Identity,
    Marks,
    Position,
    Progression,
    RoomComp,
    Vitals,
)
from xkx.runtime.conditions import (
    ConditionSystem,
    apply_condition,
    clear_one_condition,
    query_condition,
)
from xkx.runtime.death import (
    DISABLED_FLAG,
    UNCONSCIOUS_FLAG,
    die,
    unconcious,
)
from xkx.runtime.ecs import World
from xkx.runtime.schema import SchemaRegistry
from xkx.runtime.storage import DEFAULT_CHECKPOINT_INTERVAL, JsonFileBackend, StorageSystem

# ──────────────────────── 辅助 ────────────────────────


def _make_world() -> World:
    """带 SchemaRegistry 的 World（生产路径对齐，崩溃恢复测试用）。"""
    return World(SchemaRegistry.with_builtins())


def _make_player(
    world: World,
    *,
    name: str = "player",
    room_id: str = "city/room1",
    qi: int = 100,
    con: int = 20,
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name=name, is_player=True))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Vitals(qi=qi, max_qi=100, eff_qi=100, max_neili=100))
    world.add(eid, Progression(combat_exp=5000, potential=100))
    return eid


def _make_npc(
    world: World,
    *,
    name: str = "npc",
    room_id: str = "city/room1",
    qi: int = 100,
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name=name, is_player=False))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Vitals(qi=qi, max_qi=100, eff_qi=100, max_neili=100))
    return eid


def _make_room(
    world: World,
    *,
    room_id: str = "city/room1",
    no_fight: bool = False,
    no_death: bool = False,
) -> int:
    eid = world.new_entity()
    world.add(
        eid,
        RoomComp(
            room_id=room_id,
            short="room",
            long="room",
            no_fight=no_fight,
            no_death=no_death,
        ),
    )
    return eid


def _make_storage(tmp_path: str) -> tuple[StorageSystem, JsonFileBackend]:
    backend = JsonFileBackend(str(tmp_path))
    schema = SchemaRegistry.with_builtins()
    storage = StorageSystem(
        backend,
        schema=schema,
        persist_interval=1,
        checkpoint_interval=DEFAULT_CHECKPOINT_INTERVAL,
    )
    return storage, backend


def _has_revive_effect(world: World, eid: int) -> bool:
    """实体是否有 revive EffectComp。"""
    for eff_eid in world.entities_with(EffectComp):
        eff = world.get(eff_eid, EffectComp)
        if eff is not None and eff.target_id == eid and eff.effect_id == "revive":
            return True
    return False


# ──────────────────────── 1. revive call_out -> EffectComp 翻译 ────────────────────────


def test_unconcious_starts_revive_effectcomp() -> None:
    """unconcious 启动 revive EffectComp（LPC call_out("revive",delay) 翻译）。

    验证 2.2 实现：unconcious 后 target 有 revive EffectComp，duration>0。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    unconcious(w, p)
    assert _has_revive_effect(w, p)
    assert query_condition(w, p, "revive") > 0


def test_revive_effectcomp_decays_per_tick() -> None:
    """revive EffectComp duration 每 tick 衰减（LPC call_out 延迟倒计时）。

    验证 ConditionSystem.update 推进 revive EffectComp duration 衰减。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    unconcious(w, p)
    initial = query_condition(w, p, "revive")
    assert initial > 1
    # 推进 1 tick：duration -1
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, p, "revive") == initial - 1


def test_revive_effectcomp_expires_clears_unconscious() -> None:
    """revive EffectComp 到期（duration<=1）清 unconscious 标记（自然苏醒）。

    验证 _revive_trigger 到期触发 KIND_CLEAR_MARK 清 unconscious。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    unconcious(w, p)
    assert UNCONSCIOUS_FLAG in w.get(p, Marks).flags
    # 覆盖为 1（到期触发）
    apply_condition(w, p, "revive", 1)
    ConditionSystem().update(w, tick=0)
    assert UNCONSCIOUS_FLAG not in w.get(p, Marks).flags
    # EffectComp 到期移除
    assert not _has_revive_effect(w, p)


# ──────────────────────── 2. remove_call_out("revive") 中断契约 ────────────────────────


def test_die_revive_quiet_clears_revive_effectcomp() -> None:
    """die 中 revive(quiet=True) 移除 revive EffectComp（LPC remove_call_out 翻译）。

    中断契约：昏迷中 die 时，revive(quiet=True) 强制安静苏醒 + clear_one_condition
    移除 revive EffectComp（避免死后 EffectComp 仍挂悬空 target 触发）。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    # 先昏迷（启动 revive EffectComp）
    unconcious(w, p)
    assert _has_revive_effect(w, p)
    assert UNCONSCIOUS_FLAG in w.get(p, Marks).flags
    # 昏迷中 die：revive(quiet=True) 清标记 + clear_condition 移除 EffectComp
    die(w, p, tick=0)
    # revive EffectComp 已被 clear_condition(world,eid) 全清（die 内）
    assert not _has_revive_effect(w, p)


def test_clear_one_condition_revive_interrupts() -> None:
    """clear_one_condition("revive") 中断 revive EffectComp（直接验证中断契约）。

    对齐 LPC remove_call_out("revive")：显式移除指定 condition 的 EffectComp。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    unconcious(w, p)
    assert _has_revive_effect(w, p)
    # 显式中断 revive EffectComp
    assert clear_one_condition(w, p, "revive") is True
    assert not _has_revive_effect(w, p)
    # 再次清返回 False（无此 condition）
    assert clear_one_condition(w, p, "revive") is False


def test_die_revive_quiet_no_revive_message() -> None:
    """die 中 revive(quiet=True) 不输出苏醒消息（安静苏醒）。

    验证 quiet 参数语义：die 处理昏迷中死亡场景，强制安静苏醒不播消息。
    （2.2 消息推送后置 M3，本测试验证 quiet 标记 + EffectComp 中断行为等价。）
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w, qi=-1)
    unconcious(w, p)
    # 昏迷中 die：revive(quiet=True) 应清 unconscious 但不触苏醒副作用
    die(w, p, tick=0)
    # unconscious 标记已被 revive(quiet=True) 清
    marks = w.get(p, Marks)
    assert UNCONSCIOUS_FLAG not in marks.flags
    # revive EffectComp 已移除（die 内 clear_condition 全清）
    assert not _has_revive_effect(w, p)


# ──────────────────────── 3. start_* 同步执行 + 防御检查 ────────────────────────


def test_auto_fight_npc_vs_npc_skipped() -> None:
    """NPC vs NPC 跳过（对齐 LPC !userp(me) && !userp(obj)）。"""
    w = _make_world()
    _make_room(w)
    npc1 = _make_npc(w, name="npc1")
    npc2 = _make_npc(w, name="npc2")
    called: list[tuple[int, int, FightType]] = []

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        called.append((me_id, obj_id, ft))

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        auto_fight(w, npc1, npc2, FightType.AGGRESSIVE)
        # NPC vs NPC 跳过：handler 不调用 + 不设 looking_for_trouble 标记
        assert called == []
        marks = w.get(npc1, Marks)
        assert marks is None or LOOKING_FOR_TROUBLE_FLAG not in marks.flags
    finally:
        # 清理注册（避免影响其他测试）
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_auto_fight_player_vs_npc_proceeds() -> None:
    """玩家 vs NPC 通过 auto_fight + start_fight 防御检查调 on_start_fight。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w, name="player")
    npc = _make_npc(w, name="npc")
    called: list[tuple[int, int, FightType]] = []

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        called.append((me_id, obj_id, ft))

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        auto_fight(w, p, npc, FightType.AGGRESSIVE)
        assert called == [(p, npc, FightType.AGGRESSIVE)]
        # start_fight 通过后清 looking_for_trouble 标记
        assert LOOKING_FOR_TROUBLE_FLAG not in w.get(p, Marks).flags
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_auto_fight_looking_for_trouble_prevents_reentry() -> None:
    """looking_for_trouble 标记防重入（对齐 LPC query_temp 防重入）。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w)
    call_count = 0

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal call_count
        call_count += 1

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        # 预设 looking_for_trouble 标记（模拟上一次 auto_fight 未完成）
        marks = w.get(p, Marks)
        if marks is None:
            marks = Marks()
            w.add(p, marks)
        marks.flags.add(LOOKING_FOR_TROUBLE_FLAG)
        auto_fight(w, p, npc, FightType.AGGRESSIVE)
        # 已有标记 -> 跳过，handler 不调用
        assert call_count == 0
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_invalid_me_skipped() -> None:
    """start_fight：me 无效（不存在）跳过（对齐 LPC !me）。"""
    w = _make_world()
    _make_room(w)
    npc = _make_npc(w)
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        # me_id=99999 不存在（无 Identity）
        start_fight(w, 99999, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_invalid_obj_skipped() -> None:
    """start_fight：obj 无效（不存在）跳过（对齐 LPC !obj）。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, 99999, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_already_fighting_skipped() -> None:
    """start_fight：is_fighting（enemy_ids 含 obj）跳过（对齐 LPC is_fighting）。"""
    from xkx.runtime.components import CombatState

    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w)
    # p 已在与 npc 战斗
    w.add(p, CombatState(enemy_ids=[npc]))
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_not_living_unconscious_skipped() -> None:
    """start_fight：!living（unconscious）跳过（对齐 LPC !living）。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w)
    # p 昏迷
    marks = w.get(p, Marks)
    if marks is None:
        marks = Marks()
        w.add(p, marks)
    marks.flags.add(UNCONSCIOUS_FLAG)
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_disabled_skipped() -> None:
    """start_fight：!living（disabled 标记）跳过（对齐 LPC !living）。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w)
    marks = w.get(p, Marks)
    if marks is None:
        marks = Marks()
        w.add(p, marks)
    marks.flags.add(DISABLED_FLAG)
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_different_room_skipped() -> None:
    """start_fight：不同房间跳过（对齐 LPC environment!=environment）。"""
    w = _make_world()
    _make_room(w, room_id="city/room1")
    _make_room(w, room_id="city/room2")
    p = _make_player(w, room_id="city/room1")
    npc = _make_npc(w, room_id="city/room2")
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_no_fight_room_skipped() -> None:
    """start_fight：no_fight 房跳过（对齐 LPC query("no_fight")）。"""
    w = _make_world()
    _make_room(w, room_id="city/safe", no_fight=True)
    p = _make_player(w, room_id="city/safe")
    npc = _make_npc(w, room_id="city/safe")
    called = False

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        nonlocal called
        called = True

    register_start_fight_handler(FightType.AGGRESSIVE, handler)
    try:
        start_fight(w, p, npc, FightType.AGGRESSIVE)
        assert not called
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_start_fight_all_checks_pass_calls_handler() -> None:
    """start_fight：全部防御检查通过调 on_start_fight 回调。"""
    w = _make_world()
    _make_room(w, room_id="city/wild", no_fight=False)
    p = _make_player(w, room_id="city/wild")
    npc = _make_npc(w, room_id="city/wild")
    called: list[tuple[int, int, FightType]] = []

    def handler(world: World, me_id: int, obj_id: int, ft: FightType) -> None:
        called.append((me_id, obj_id, ft))

    register_start_fight_handler(FightType.HATRED, handler)
    try:
        start_fight(w, p, npc, FightType.HATRED)
        assert called == [(p, npc, FightType.HATRED)]
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.HATRED, None)


def test_start_fight_clears_looking_for_trouble_even_if_check_fails() -> None:
    """start_fight 开头清 looking_for_trouble 标记（即使防御检查未通过）。

    对齐 LPC start_* 第一行 set_temp("looking_for_trouble",0) 无论后续检查结果。
    """
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w, room_id="city/other")  # 不同房间 -> 检查失败
    marks = w.get(p, Marks)
    if marks is None:
        marks = Marks()
        w.add(p, marks)
    marks.flags.add(LOOKING_FOR_TROUBLE_FLAG)
    start_fight(w, p, npc, FightType.AGGRESSIVE)
    # 检查失败但标记已清
    assert LOOKING_FOR_TROUBLE_FLAG not in w.get(p, Marks).flags


def test_start_fight_default_noop_when_unregistered() -> None:
    """未注册 handler 的 FightType 用默认 no-op（2.4 占位，不 crash）。"""
    w = _make_world()
    _make_room(w)
    p = _make_player(w)
    npc = _make_npc(w)
    # VENDETTA 未注册 handler -> 默认 no-op，不 crash
    start_fight(w, p, npc, FightType.VENDETTA)
    # 无异常即通过


# ──────────────────────── 4. 崩溃恢复（revive EffectComp） ────────────────────────


def test_revive_effectcomp_crash_recovery_duration_not_decayed(tmp_path) -> None:
    """revive EffectComp duration 崩溃期间不衰减（ADR-0022 §6 时间冻结）。

    验证 revive call_out -> EffectComp 翻译的崩溃安全：存档时 duration=N，
    冷重启后 duration 仍为 N（不补执行不衰减）。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    _make_room(world)
    p = _make_player(world, qi=-1)
    unconcious(world, p)
    initial_duration = query_condition(world, p, "revive")
    storage.mark_dirty(p)
    for eff_eid in world.entities_with(EffectComp):
        storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：current_tick=100（崩溃期间 revive 本应到期）
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=100)

    # duration 不衰减：保持存档时值
    assert query_condition(world2, p, "revive") == initial_duration


def test_revive_effectcomp_dangling_target_skipped(tmp_path) -> None:
    """悬空 target_id 的 EffectComp 崩溃恢复跳过（ADR-0022 §5 台账 #4）。

    验证 revive EffectComp 的 target 存档丢失时，冷重启不 crash + 悬空 Effect 移除。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    # 只 persist revive EffectComp 实体，不 persist target（模拟 target 存档丢失）
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="revive",
            kind="",
            target_id=99999,  # 不存在的 target
            duration=3,
            tick_interval=1,
            next_tick=10,
        ),
    )
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：target=99999 不存在 -> 跳过该 Effect（不 crash）
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)
    # 悬空 Effect 被移除
    assert list(world2.entities_with(EffectComp)) == []


# ──────────────────────── 5. 主题无关性（ADR-0027 §1.3 + ADR-0003） ────────────────────────


def test_auto_fight_source_theme_neutral() -> None:
    """auto_fight.py 源码无武侠字面量（ADR-0027 §1.3 主题无关性硬门禁）。

    武侠特有字面量黑名单：门派名/武学名/阵法名等不得出现在通用战斗触发模块
    源码中。FightType 枚举值（berserk/hatred/vendetta/aggressive）是通用 RPG
    战斗语义，不在黑名单。
    """
    source = inspect.getsource(auto_fight_mod)
    # 武侠题材字面量黑名单（门派/武学/阵法/武侠特有名词）
    banned = [
        "武侠",
        "侠客行",
        "华山",
        "少林",
        "武当",
        "丐帮",
        "峨眉",
        "全真",
        "桃花",
        "慕容",
        "阵法",
        "合击",
        "破阵",
        "布阵",
        "anubis",
        "kungfu",
        "perform",
        "exert",
        "pozhen",
        "buzhen",
        "heji",
    ]
    for word in banned:
        assert word not in source, f"auto_fight.py 源码含武侠字面量: {word}"


def test_fighttype_values_are_generic() -> None:
    """FightType 枚举值是通用战斗语义（非武侠特有）。"""
    values = {ft.value for ft in FightType}
    assert values == {"berserk", "hatred", "vendetta", "aggressive"}
