"""Engine 统一 tick 循环 + CombatBridge 适配器测试（阶段 1 Wave 4 T10 整合遗留）。

验证：
- Engine 注册/移除 System + tick 推进 + profiler 测量
- CombatState 扩展字段（guarding/is_fighting/fight_dodge）默认值 + to_snapshot 传递
- CombatBridge 从 world 构建快照 -> 按 enemy_ids -> replay -> apply_effects
- CombatBridge 无活跃战斗者 / 无敌对对时 no-op
- Engine + ConditionSystem + CombatBridge + StorageSystem 联合 tick
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from xkx.runtime.components import (
    Attributes,
    CombatState,
    EffectComp,
    Identity,
    Position,
    Progression,
    Skills,
    Vitals,
)
from xkx.runtime.conditions import ConditionSystem
from xkx.runtime.ecs import World
from xkx.runtime.engine import CombatBridge, Engine
from xkx.runtime.profiler import TickProfiler
from xkx.runtime.schema import SchemaRegistry
from xkx.runtime.storage import JsonFileBackend, StorageSystem
from xkx.runtime.systems import System
from xkx.runtime.world import to_snapshot


class _DummySystem(System):
    """计数 System（测试 Engine tick 循环用）。"""

    name = "DummySystem"

    def __init__(self) -> None:
        self.update_count = 0
        self.last_tick = 0

    def update(self, world: World, tick: int) -> None:
        self.update_count += 1
        self.last_tick = tick


def _make_world() -> World:
    return World(SchemaRegistry.with_builtins())


def _make_combatant(
    world: World,
    *,
    name: str,
    str_: int = 50,
    dex_: int = 50,
    con_: int = 20,
    combat_exp: int = 99999,
    skills: dict[str, int] | None = None,
    max_qi: int = 600,
    is_fighting: bool = False,
    enemy_ids: list[int] | None = None,
) -> int:
    """创建有全组件的战斗实体（to_snapshot 需 6 组件齐全）。"""
    eid = world.new_entity()
    world.add(eid, Identity(name=name))
    world.add(eid, Position(room_id="room1"))
    world.add(eid, Attributes(str_=str_, dex_=dex_, con_=con_))
    world.add(
        eid,
        Vitals(qi=max_qi, max_qi=max_qi, eff_qi=max_qi, max_jingli=300, jingli=300),
    )
    world.add(eid, Progression(combat_exp=combat_exp))
    world.add(eid, Skills(levels=skills if skills is not None else {"unarmed": 80}))
    world.add(
        eid,
        CombatState(is_fighting=is_fighting, enemy_ids=enemy_ids or []),
    )
    return eid


# ---- Engine 基础 ----


def test_engine_add_remove_get_system() -> None:
    """Engine 注册/移除/查找 System。"""
    world = _make_world()
    engine = Engine(world, profiler=TickProfiler(enabled=False))
    dummy = _DummySystem()
    engine.add_system(dummy)
    assert engine.get_system("DummySystem") is dummy
    assert engine.systems == [dummy]

    removed = engine.remove_system("DummySystem")
    assert removed is dummy
    assert engine.systems == []
    assert engine.get_system("DummySystem") is None
    assert engine.remove_system("NoSuch") is None


def test_engine_tick_advances_tick_no_and_calls_update() -> None:
    """tick 推进 tick_no + 调用各 System.update。"""
    world = _make_world()
    dummy = _DummySystem()
    engine = Engine(world, profiler=TickProfiler(enabled=False))
    engine.add_system(dummy)

    assert engine.tick_no == 0
    engine.tick()
    engine.tick()
    engine.tick()
    assert engine.tick_no == 3
    assert dummy.update_count == 3
    assert dummy.last_tick == 3


def test_engine_profiler_measures_per_system() -> None:
    """profiler 按 System name 分组采样。"""
    world = _make_world()
    profiler = TickProfiler(enabled=True)
    engine = Engine(world, profiler=profiler)
    engine.add_system(_DummySystem())
    for _ in range(5):
        engine.tick()
    assert profiler.sample_count == 5
    summary = profiler.report().system_summary()
    assert len(summary) == 1
    assert summary[0].system_name == "DummySystem"
    assert summary[0].ticks == 5


# ---- CombatState 扩展字段 ----


def test_combat_state_extension_defaults() -> None:
    """CombatState 扩展字段默认值（不 break 现有代码）。"""
    cs = CombatState()
    assert cs.guarding == 0
    assert cs.is_fighting is False
    assert cs.fight_dodge == 0


def test_to_snapshot_passes_extension_fields() -> None:
    """to_snapshot 传递 guarding/is_fighting/fight_dodge 到 CombatantSnapshot。"""
    world = _make_world()
    eid = _make_combatant(world, name="甲", is_fighting=True)
    cs = world.get(eid, CombatState)
    assert cs is not None
    cs.guarding = 1
    cs.fight_dodge = 50
    snap = to_snapshot(world, eid)
    assert snap.guarding == 1
    assert snap.is_fighting is True
    assert snap.fight_dodge == 50


# ---- CombatBridge ----


def test_combat_bridge_no_fighters_noop() -> None:
    """无 is_fighting 实体时 CombatBridge no-op（profiler 无 sample 执行体）。"""
    world = _make_world()
    _make_combatant(world, name="甲", is_fighting=False)
    _make_combatant(world, name="乙", is_fighting=False)
    bridge = CombatBridge(seed_base=42)
    # 不应 raise（无活跃战斗者直接返回）
    bridge.update(world, tick=1)


def test_combat_bridge_no_enemy_ids_noop() -> None:
    """is_fighting=True 但 enemy_ids 为空时 no-op（无攻击对）。"""
    world = _make_world()
    _make_combatant(world, name="甲", is_fighting=True, enemy_ids=[])
    bridge = CombatBridge(seed_base=42)
    bridge.update(world, tick=1)


def test_combat_bridge_deals_damage() -> None:
    """CombatBridge 对活跃敌对对 apply 战斗伤害（victim qi 下降）。

    强 attacker（unarmed=80/str=50）vs 弱 victim（dodge=0/combat_exp=0）：
    dp=max(1,0)=1, ap≈170865, 闪避概率≈0.000006，几乎必中。
    """
    world = _make_world()
    attacker = _make_combatant(
        world,
        name="甲",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"unarmed": 80},
        max_qi=600,
        is_fighting=True,
    )
    victim = _make_combatant(
        world,
        name="乙",
        str_=10,
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=100,
        is_fighting=True,
    )
    # 互设敌对
    a_cs = world.get(attacker, CombatState)
    v_cs = world.get(victim, CombatState)
    assert a_cs is not None and v_cs is not None
    a_cs.enemy_ids = [victim]
    v_cs.enemy_ids = [attacker]

    bridge = CombatBridge(seed_base=0)
    bridge.update(world, tick=1)

    v_vitals = world.get(victim, Vitals)
    assert v_vitals is not None
    # 几乎必中 -> victim qi 下降
    assert v_vitals.qi < v_vitals.max_qi, f"victim qi 未下降 ({v_vitals.qi}/{v_vitals.max_qi})"


def test_combat_bridge_respects_enemy_ids() -> None:
    """CombatBridge 只攻击 enemy_ids 中的实体（非全两两遍历）。

    A 敌视 B，但 B 不敌视 A -> 只有 A->B 一条攻击（非 A<->B 两条）。
    """
    world = _make_world()
    a = _make_combatant(world, name="甲", is_fighting=True)
    b = _make_combatant(world, name="乙", is_fighting=True)
    # 只有 A 敌视 B
    a_cs = world.get(a, CombatState)
    assert a_cs is not None
    a_cs.enemy_ids = [b]

    bridge = CombatBridge(seed_base=0)
    bridge.update(world, tick=1)

    # B 的 qi 可能下降（被 A 攻击），A 的 qi 不变（B 未攻击 A）
    a_vitals = world.get(a, Vitals)
    assert a_vitals is not None
    assert a_vitals.qi == a_vitals.max_qi  # A 未受伤


def test_combat_bridge_engine_integration() -> None:
    """CombatBridge 作为 System 接入 Engine，profiler 记录 CombatSystem 采样。"""
    world = _make_world()
    attacker = _make_combatant(world, name="甲", is_fighting=True)
    victim = _make_combatant(world, name="乙", is_fighting=True)
    a_cs = world.get(attacker, CombatState)
    assert a_cs is not None
    a_cs.enemy_ids = [victim]

    profiler = TickProfiler(enabled=True)
    engine = Engine(world, profiler=profiler)
    engine.add_system(CombatBridge(seed_base=0))

    engine.tick()
    summary = profiler.report().system_summary()
    names = [s.system_name for s in summary]
    assert "CombatSystem" in names


# ---- 完整整合：Engine + 多 System 联合 tick ----


def test_engine_full_integration_with_storage_and_conditions() -> None:
    """Engine + ConditionSystem + CombatBridge + StorageSystem 联合 tick。

    验证：
    - 各 System 都被 tick 调用（profiler 有 3 个 System 采样）
    - ConditionSystem 处理 EffectComp（衰减 duration）
    - StorageSystem 周期 persist（tick%interval==0 时触发）
    - CombatBridge 处理活跃战斗者
    """
    with tempfile.TemporaryDirectory() as tmp:
        world = _make_world()
        backend = JsonFileBackend(tmp)
        storage = StorageSystem(backend, schema=world._schema)  # type: ignore[arg-type]
        # 设 persist_interval=2 方便测试
        storage._persist_interval = 2  # type: ignore[attr-defined]

        # 创建一个有 EffectComp 的实体（ConditionSystem 处理）
        effect_eid = world.new_entity()
        world.add(
            effect_eid,
            EffectComp(
                effect_id="poison1",
                kind="poison",
                target_id=effect_eid,
                amount=5,
                duration=10,
                tick_interval=1,
                next_tick=1,
            ),
        )
        # 给 effect target 加 Vitals（apply_effects 需要）
        world.add(effect_eid, Vitals(qi=100, max_qi=100, eff_qi=100))

        # 创建战斗对
        attacker = _make_combatant(world, name="甲", is_fighting=True)
        victim = _make_combatant(world, name="乙", is_fighting=True)
        a_cs = world.get(attacker, CombatState)
        assert a_cs is not None
        a_cs.enemy_ids = [victim]

        profiler = TickProfiler(enabled=True)
        engine = Engine(world, profiler=profiler)
        engine.add_system(ConditionSystem())
        engine.add_system(CombatBridge(seed_base=0))
        engine.add_system(storage)

        # 跑 4 tick（persist_interval=2 -> tick 2/4 触发 persist）
        for _ in range(4):
            engine.tick()

        summary = profiler.report().system_summary()
        names = {s.system_name for s in summary}
        assert "ConditionSystem" in names
        assert "CombatSystem" in names
        assert "StorageSystem" in names

        # 存档文件已落盘（tick 2 和 4 触发 persist）
        entity_files = list(Path(tmp).rglob("*.json"))
        assert len(entity_files) > 0, "存档未落盘"

        # ConditionSystem 衰减了 duration（4 tick -> duration 10->6）
        eff = world.get(effect_eid, EffectComp)
        assert eff is not None
        assert eff.duration == 6, f"duration 未正确衰减: {eff.duration}"


def test_combat_bridge_seed_determinism() -> None:
    """同 seed_base + tick -> 同伤害（CombatBridge 确定性）。"""
    world1 = _make_world()
    world2 = _make_world()

    for w in (world1, world2):
        a = _make_combatant(w, name="甲", is_fighting=True)
        v = _make_combatant(
            w, name="乙", str_=10, dex_=1, con_=1, combat_exp=0, skills={"dodge": 0}
        )
        a_cs = w.get(a, CombatState)
        assert a_cs is not None
        a_cs.enemy_ids = [v]

    CombatBridge(seed_base=0).update(world1, tick=1)
    CombatBridge(seed_base=0).update(world2, tick=1)

    v1 = world1.get(2, Vitals)  # victim 是第 2 个实体
    v2 = world2.get(2, Vitals)
    assert v1 is not None and v2 is not None
    assert v1.qi == v2.qi, f"伤害不一致: {v1.qi} vs {v2.qi}"


# ---- CombatBridge select_opponent（B-2 ADR-0045 后置收尾，多对手）----


def test_combat_bridge_selects_one_opponent() -> None:
    """多对手 select_opponent：每 attacker 每 tick 只打 1 个敌人（对齐 LPC attack.c，
    修正原"每 tick 打所有敌人"语义偏差）。A 敌视 B+C -> 只 B 或 C 之一受伤。"""
    world = _make_world()
    a = _make_combatant(
        world, name="甲", str_=50, dex_=50, combat_exp=99999,
        skills={"unarmed": 80}, max_qi=600, is_fighting=True,
    )
    b = _make_combatant(
        world, name="乙", str_=10, dex_=1, con_=1, combat_exp=0,
        skills={"dodge": 0}, max_qi=100, is_fighting=True,
    )
    c = _make_combatant(
        world, name="丙", str_=10, dex_=1, con_=1, combat_exp=0,
        skills={"dodge": 0}, max_qi=100, is_fighting=True,
    )
    a_cs = world.get(a, CombatState)
    assert a_cs is not None
    a_cs.enemy_ids = [b, c]  # A 敌视 B+C；B/C 不敌视 A（只测 A 的 select）

    CombatBridge(seed_base=0).update(world, tick=1)

    b_vitals = world.get(b, Vitals)
    c_vitals = world.get(c, Vitals)
    assert b_vitals is not None and c_vitals is not None
    # select 只打 1 个：B 或 C 至少一个满血（未被打）
    assert b_vitals.qi == b_vitals.max_qi or c_vitals.qi == c_vitals.max_qi
    selects = getattr(world, "combat_selects", {})
    assert selects.get(a) in (b, c)  # A 选中 B 或 C


def test_combat_bridge_multi_opponent_determinism() -> None:
    """多对手同 seed 同 select：两个 world 同 tick -> A 选中同对手 + 同伤害。"""
    world1 = _make_world()
    world2 = _make_world()
    for w in (world1, world2):
        a = _make_combatant(
            w, name="甲", str_=50, dex_=50, combat_exp=99999,
            skills={"unarmed": 80}, is_fighting=True,
        )
        b = _make_combatant(
            w, name="乙", str_=10, dex_=1, con_=1, combat_exp=0,
            skills={"dodge": 0}, is_fighting=True,
        )
        c = _make_combatant(
            w, name="丙", str_=10, dex_=1, con_=1, combat_exp=0,
            skills={"dodge": 0}, is_fighting=True,
        )
        a_cs = w.get(a, CombatState)
        assert a_cs is not None
        a_cs.enemy_ids = [b, c]

    CombatBridge(seed_base=0).update(world1, tick=1)
    CombatBridge(seed_base=0).update(world2, tick=1)

    # A 的选中对手一致（两 world 同构 A=1/B=2/C=3）
    s1 = getattr(world1, "combat_selects", {})
    s2 = getattr(world2, "combat_selects", {})
    assert s1.get(1) == s2.get(1)
    selected = s1.get(1)
    v1 = world1.get(selected, Vitals)
    v2 = world2.get(selected, Vitals)
    assert v1 is not None and v2 is not None
    assert v1.qi == v2.qi


def test_combat_bridge_single_enemy_select_fallback() -> None:
    """单敌人 select_opponent 确定性 fallback enemy[0]（which >= len 时 fallback，
    单敌人行为不变，对齐 LPC sizeof(enemy)=1 永远打 enemy[0]）。"""
    world = _make_world()
    a = _make_combatant(world, name="甲", is_fighting=True)
    b = _make_combatant(world, name="乙", is_fighting=True)
    a_cs = world.get(a, CombatState)
    assert a_cs is not None
    a_cs.enemy_ids = [b]  # 单敌人

    CombatBridge(seed_base=0).update(world, tick=1)

    selects = getattr(world, "combat_selects", {})
    assert selects.get(a) == b  # 单敌人必选 b（fallback enemy[0]）
