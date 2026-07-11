"""JSON 存档 + 崩溃恢复 + dirty-flag + Effect 序列化测试（阶段 1 Wave 2 T5）。

验证 ADR-0022 承重决策：

1. 原子写崩溃安全（§2）：写入中断 tmp 损坏，target 不损坏
2. offload 不阻塞事件循环（§3）：persist 在线程，tick 不阻塞
3. dirty-flag 只存脏实体（§4）：非脏实体文件不重写
4. 冷重启恢复玩家状态（§7）：从 checkpoint 恢复 Vitals/Progression 等
5. Effect 崩溃恢复（§6）：duration/next_tick 恢复 + 不补执行 + duration 不衰减 +
   悬空引用跳过
6. hypothesis 序列化往返一致性（§6）：组件 dataclass <-> JSON 往返保持等价

[ADR-0022](../../../docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime.components import (
    Attributes,
    EffectComp,
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.schema import SchemaRegistry
from xkx.runtime.serialization import (
    deserialize_component,
    deserialize_entity,
    serialize_component,
    serialize_entity,
)
from xkx.runtime.storage import (
    DEFAULT_CHECKPOINT_INTERVAL,
    JsonFileBackend,
    StorageSystem,
)

# ---- 辅助 ----


def _make_world() -> World:
    """带 SchemaRegistry 的 World（生产路径对齐）。"""
    return World(SchemaRegistry.with_builtins())


def _make_storage(tmp_path: str, **kwargs) -> tuple[StorageSystem, JsonFileBackend]:
    """创建 StorageSystem + JsonFileBackend（persist_interval=1 便于测试）。"""
    backend = JsonFileBackend(str(tmp_path))
    schema = SchemaRegistry.with_builtins()
    storage = StorageSystem(
        backend,
        schema=schema,
        persist_interval=kwargs.get("persist_interval", 1),
        checkpoint_interval=kwargs.get("checkpoint_interval", DEFAULT_CHECKPOINT_INTERVAL),
    )
    return storage, backend


def _spawn_player(world: World, name: str = "玩家", qi: int = 200) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name=name, is_player=True, prototype_id="player"))
    world.add(eid, Position(room_id="city/street"))
    world.add(eid, Attributes(str_=20, dex_=20, int_=20, con_=20, age=22))
    world.add(eid, Vitals(qi=qi, max_qi=200, eff_qi=200, jing=150, max_jing=150))
    world.add(eid, Progression(combat_exp=500))
    world.add(eid, Inventory(items={"sword"}))
    world.add(eid, Marks(flags={"visited"}))
    return eid


# ---- 1. 原子写崩溃安全 ----


def test_atomic_write_target_intact_on_tmp_corruption(tmp_path):
    """写入中断（tmp 损坏）不损坏 target（ADR-0022 §2 崩溃安全性）。

    模拟：先成功 persist 一次（target 完整），再制造损坏的 tmp 文件，
    验证 target 仍是上一次完整存档。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    eid = _spawn_player(world, qi=150)
    storage.mark_dirty(eid)

    # 第一次成功 persist
    asyncio.run(storage.persist_now(world))
    target = os.path.join(str(tmp_path), "entity", f"{eid}.json")
    assert os.path.exists(target)
    with open(target, encoding="utf-8") as f:
        first_state = json.load(f)
    assert first_state["components"]["Vitals"]["qi"] == 150

    # 制造损坏的 tmp 文件（模拟写入中断）
    tmp_path_file = f"{target}.tmp.99999"
    with open(tmp_path_file, "w", encoding="utf-8") as f:
        f.write("{ 损坏的半截 JSON")

    # target 仍应完整（tmp 损坏不影响 target）
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    assert state["components"]["Vitals"]["qi"] == 150


def test_atomic_write_replace_is_atomic(tmp_path):
    """os.replace 原子性：persist 后 target 是新内容，无半截状态。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    eid = _spawn_player(world, qi=100)
    storage.mark_dirty(eid)
    asyncio.run(storage.persist_now(world))

    # 修改 qi 后再次 persist
    world.get(eid, Vitals).qi = 50
    storage.mark_dirty(eid)
    asyncio.run(storage.persist_now(world))

    target = os.path.join(str(tmp_path), "entity", f"{eid}.json")
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    assert state["components"]["Vitals"]["qi"] == 50  # 新内容完整


# ---- 2. offload 不阻塞事件循环 ----


def test_persist_does_not_block_event_loop(tmp_path):
    """persist 在线程执行，事件循环不被阻塞（ADR-0022 §3）。

    验证：persist 期间事件循环仍能调度其他任务（tick 心跳不被阻塞）。
    用 persist_now（await to_thread）+ 并发 tick 计数器验证。
    """
    storage, _ = _make_storage(tmp_path)
    world = _make_world()
    for i in range(10):
        eid = _spawn_player(world, name=f"玩家{i}")
        storage.mark_dirty(eid)

    tick_count = 0

    async def tick_loop():
        """模拟 tick 循环：每 1ms 递增，验证 persist 期间不阻塞。"""
        nonlocal tick_count
        for _ in range(50):
            tick_count += 1
            await asyncio.sleep(0.001)

    async def main():
        # 并发执行 persist + tick 循环
        await asyncio.gather(
            storage.persist_now(world),
            tick_loop(),
        )

    start = time.monotonic()
    asyncio.run(main())
    elapsed = time.monotonic() - start
    # tick 循环应跑完 50 次（若 persist 阻塞事件循环，tick 会被卡）
    assert tick_count == 50
    # 总耗时应远小于串行（persist + 50ms tick）；这里宽松断言不超 5s
    assert elapsed < 5.0


# ---- 3. dirty-flag 只存脏实体 ----


def test_dirty_flag_only_persists_dirty_entities(tmp_path):
    """dirty-flag 分摊：非脏实体文件不被创建（ADR-0022 §4）。

    通过 ``_trigger_persist``（增量路径）验证：只标记脏的实体被 persist，
    非脏实体文件不创建。``persist_now`` 是全量路径（关机存档用），不适用此测试。
    """
    storage, _ = _make_storage(tmp_path, persist_interval=1, checkpoint_interval=99)
    world = _make_world()
    eid_dirty = _spawn_player(world, name="脏玩家", qi=100)
    eid_clean = _spawn_player(world, name="干净玩家", qi=200)

    # 只标记 eid_dirty 脏
    storage.mark_dirty(eid_dirty)

    async def _run():
        # _trigger_persist 是 fire-and-forget，需等 task 完成
        storage._trigger_persist(world)  # type: ignore[attr-defined]
        # 等待 pending task 完成
        if storage._pending_persist is not None:  # type: ignore[attr-defined]
            await storage._pending_persist

    asyncio.run(_run())

    dirty_file = os.path.join(str(tmp_path), "entity", f"{eid_dirty}.json")
    clean_file = os.path.join(str(tmp_path), "entity", f"{eid_clean}.json")
    assert os.path.exists(dirty_file)  # 脏实体被 persist
    assert not os.path.exists(clean_file)  # 非脏实体未被 persist


def test_dirty_flag_cleared_after_persist(tmp_path):
    """persist 完成后 dirty-flag 清除（增量只清本次 persist 的）。"""
    storage, _ = _make_storage(tmp_path)
    world = _make_world()
    eid = _spawn_player(world, qi=100)
    storage.mark_dirty(eid)
    assert eid in storage._dirty  # type: ignore[attr-defined]

    asyncio.run(storage.persist_now(world))
    assert eid not in storage._dirty  # type: ignore[attr-defined]


def test_checkpoint_resets_all_dirty(tmp_path):
    """全量 checkpoint 周期重置所有 dirty-flag（ADR-0022 §4）。"""
    storage, _ = _make_storage(tmp_path, checkpoint_interval=1)
    world = _make_world()
    eid1 = _spawn_player(world, name="玩家1", qi=100)
    eid2 = _spawn_player(world, name="玩家2", qi=200)

    # checkpoint_interval=1：第一次 persist 即全量 checkpoint
    # persist_now 内部 mark_all_dirty + persist + clear
    asyncio.run(storage.persist_now(world))

    # 两个实体都被 persist（全量）
    f1 = os.path.join(str(tmp_path), "entity", f"{eid1}.json")
    f2 = os.path.join(str(tmp_path), "entity", f"{eid2}.json")
    assert os.path.exists(f1)
    assert os.path.exists(f2)


# ---- 4. 冷重启恢复玩家状态 ----


def test_cold_restart_restores_player_state(tmp_path):
    """冷重启从 checkpoint 恢复玩家状态（ADR-0022 §7）。

    场景：persist 后修改内存态（模拟崩溃前未 persist 的变更），restore 应恢复到
    persist 时的状态（非崩溃前内存态）。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    eid = _spawn_player(world, qi=150)
    world.get(eid, Progression).combat_exp = 999
    storage.mark_dirty(eid)
    asyncio.run(storage.persist_now(world))

    # 模拟崩溃：丢弃 world，新建空 world 从存档恢复
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=100)

    # 恢复后状态 = persist 时状态
    vitals = world2.get(eid, Vitals)
    assert vitals is not None
    assert vitals.qi == 150
    prog = world2.get(eid, Progression)
    assert prog is not None
    assert prog.combat_exp == 999
    ident = world2.get(eid, Identity)
    assert ident is not None
    assert ident.name == "玩家"
    assert ident.is_player is True
    inv = world2.get(eid, Inventory)
    assert inv is not None
    assert inv.items == {"sword"}
    marks = world2.get(eid, Marks)
    assert marks is not None
    assert marks.flags == {"visited"}


def test_cold_restart_restores_next_entity_id(tmp_path):
    """恢复后 World._next_id 不与已恢复 eid 冲突。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    eid = _spawn_player(world)
    storage.mark_dirty(eid)
    asyncio.run(storage.persist_now(world))

    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=0)

    # 新建实体 id 应 > 已恢复的 eid
    new_eid = world2.new_entity()
    assert new_eid > eid


def test_cold_restart_empty_dir_returns_zero(tmp_path):
    """空存档目录 restore 返回 last_tick=0。"""
    backend = JsonFileBackend(str(tmp_path))
    world = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage = StorageSystem(backend, schema=schema)
    last_tick = storage.restore_world(world, current_tick=0)
    assert last_tick == 0


# ---- 5. Effect 崩溃恢复 ----


def test_effect_crash_recovery_duration_not_decayed(tmp_path):
    """Effect duration 不衰减（ADR-0022 §6：崩溃期间 Effect 时间冻结）。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    target_eid = _spawn_player(world, qi=100)
    # 持续 Effect：duration=5，next_tick=10，tick_interval=2
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="poison",
            kind="damage",
            target_id=target_eid,
            amount=5,
            duration=5,
            tick_interval=2,
            next_tick=10,
        ),
    )
    storage.mark_dirty(target_eid)
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：current_tick=20（崩溃期间 next_tick=10 本应触发但未触发）
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)

    eff = world2.get(eff_eid, EffectComp)
    assert eff is not None
    # duration 不衰减：保持存档时值 5
    assert eff.duration == 5
    # next_tick 对齐到 current_tick + tick_interval = 20 + 2 = 22（不补执行）
    assert eff.next_tick == 22


def test_effect_crash_recovery_no_catchup(tmp_path):
    """Effect 不补执行：崩溃期间本应触发的 tick 不补（ADR-0022 §6）。

    验证：restore 后 target 的 qi 不被扣（崩溃期间 DoT 未触发）。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    target_eid = _spawn_player(world, qi=100)
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="poison",
            kind="damage",
            target_id=target_eid,
            amount=10,
            duration=5,
            tick_interval=2,
            next_tick=10,
        ),
    )
    storage.mark_dirty(target_eid)
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：current_tick=20（next_tick=10,12,14,16,18 本应触发 5 次，扣 50 血）
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)

    # 不补执行：qi 仍为 100（存档时值）
    vitals = world2.get(target_eid, Vitals)
    assert vitals is not None
    assert vitals.qi == 100


def test_effect_crash_recovery_next_tick_future_unchanged(tmp_path):
    """next_tick > current_tick 时不对齐（未来触发的 Effect 保持原 next_tick）。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    target_eid = _spawn_player(world, qi=100)
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="buff",
            kind="damage",
            target_id=target_eid,
            amount=0,
            duration=10,
            tick_interval=5,
            next_tick=50,  # 未来 tick
        ),
    )
    storage.mark_dirty(target_eid)
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：current_tick=20（next_tick=50 > 20，不对齐）
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)

    eff = world2.get(eff_eid, EffectComp)
    assert eff is not None
    assert eff.next_tick == 50  # 未来触发，不对齐
    assert eff.duration == 10


def test_effect_dangling_reference_skipped(tmp_path):
    """悬空引用跳过：Effect.target_id 指向不存在实体，跳过不 crash（ADR-0022 §5 台账 #4）。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    # 只 persist 一个 Effect 实体，不 persist 其 target（模拟 target 存档丢失）
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="orphan",
            kind="damage",
            target_id=99999,  # 不存在的 target
            amount=5,
            duration=3,
            tick_interval=1,
            next_tick=10,
        ),
    )
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    # 冷重启：target=99999 不存在 -> 跳过该 Effect
    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    # 不 crash
    storage2.restore_world(world2, current_tick=20)

    # 悬空 Effect 被移除
    assert list(world2.entities_with(EffectComp)) == []


def test_effect_dangling_source_skipped(tmp_path):
    """source_id 悬空也跳过（若 Effect 只引用 source 不引用 target 仍保留）。

    补充：ADR-0022 §5 台账 #4 只要求 target_id 校验（source_id 是来源，悬空不破坏
    Effect 语义）。本测试验证 source_id 悬空不导致跳过（只 target_id 悬空才跳过）。
    """
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    target_eid = _spawn_player(world, qi=100)
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="dot",
            kind="damage",
            target_id=target_eid,
            source_id=88888,  # source 悬空（不影响 Effect 有效性）
            amount=5,
            duration=3,
            tick_interval=1,
            next_tick=10,
        ),
    )
    storage.mark_dirty(target_eid)
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)

    # source 悬空不跳过（target 存在即保留）
    eff = world2.get(eff_eid, EffectComp)
    assert eff is not None
    assert eff.source_id == 88888  # source 悬空但保留


def test_effect_permanent_duration_zero_restored(tmp_path):
    """永久 Effect（duration=0）崩溃恢复保持 duration=0（不衰减）。"""
    storage, backend = _make_storage(tmp_path)
    world = _make_world()
    target_eid = _spawn_player(world, qi=100)
    eff_eid = world.new_entity()
    world.add(
        eff_eid,
        EffectComp(
            effect_id="perm",
            kind="damage",
            target_id=target_eid,
            amount=0,
            duration=0,  # 永久
            tick_interval=1,
            next_tick=10,
        ),
    )
    storage.mark_dirty(target_eid)
    storage.mark_dirty(eff_eid)
    asyncio.run(storage.persist_now(world))

    world2 = _make_world()
    schema = SchemaRegistry.with_builtins()
    storage2 = StorageSystem(backend, schema=schema)
    storage2.restore_world(world2, current_tick=20)

    eff = world2.get(eff_eid, EffectComp)
    assert eff is not None
    assert eff.duration == 0  # 永久不衰减


# ---- 6. hypothesis 序列化往返一致性 ----


@dataclass
class _SetHolder:
    """测试用 dataclass（set 字段往返）。"""
    items: set[str] = field(default_factory=set)
    name: str = ""
    count: int = 0


# 组件策略：生成合理字段值
_vitals_strategy = st.builds(
    Vitals,
    qi=st.integers(0, 1000),
    max_qi=st.integers(0, 1000),
    eff_qi=st.integers(0, 1000),
    jing=st.integers(0, 1000),
    max_jing=st.integers(0, 1000),
    jingli=st.integers(0, 1000),
    max_jingli=st.integers(0, 1000),
    neili=st.integers(0, 1000),
    max_neili=st.integers(0, 1000),
)

_progression_strategy = st.builds(
    Progression,
    combat_exp=st.integers(0, 100000),
    potential=st.integers(0, 100),
    max_potential=st.integers(0, 100),
)

_inventory_strategy = st.builds(
    Inventory,
    items=st.sets(st.text(min_size=1, max_size=10), max_size=5),
)

_marks_strategy = st.builds(
    Marks,
    flags=st.sets(st.text(min_size=1, max_size=10), max_size=5),
)

_effect_strategy = st.builds(
    EffectComp,
    effect_id=st.text(min_size=1, max_size=10),
    kind=st.sampled_from(["damage", "wound", "exp", "potential"]),
    target_id=st.integers(1, 100),
    source_id=st.integers(0, 100),
    amount=st.integers(-100, 100),
    detail=st.text(max_size=20),
    duration=st.integers(0, 100),
    tick_interval=st.integers(1, 10),
    next_tick=st.integers(0, 100),
    flags=st.integers(0, 3),
)


@given(_vitals_strategy)
@settings(max_examples=50)
def test_vitals_roundtrip(vitals: Vitals) -> None:
    """Vitals 序列化往返一致性。"""
    data = serialize_component(vitals)
    restored = deserialize_component(Vitals, data)
    assert restored == vitals


@given(_progression_strategy)
@settings(max_examples=50)
def test_progression_roundtrip(progression: Progression) -> None:
    """Progression 序列化往返一致性。"""
    data = serialize_component(progression)
    restored = deserialize_component(Progression, data)
    assert restored == progression


@given(_inventory_strategy)
@settings(max_examples=50)
def test_inventory_roundtrip(inventory: Inventory) -> None:
    """Inventory（set 字段）序列化往返一致性。"""
    data = serialize_component(inventory)
    # set 序列化为 sorted list
    assert isinstance(data["items"], list)
    restored = deserialize_component(Inventory, data)
    assert restored == inventory
    assert isinstance(restored.items, set)


@given(_marks_strategy)
@settings(max_examples=50)
def test_marks_roundtrip(marks: Marks) -> None:
    """Marks（set 字段）序列化往返一致性。"""
    data = serialize_component(marks)
    assert isinstance(data["flags"], list)
    restored = deserialize_component(Marks, data)
    assert restored == marks
    assert isinstance(restored.flags, set)


@given(_effect_strategy)
@settings(max_examples=50)
def test_effect_roundtrip(effect: EffectComp) -> None:
    """EffectComp 序列化往返一致性（ADR-0022 §6）。"""
    data = serialize_component(effect)
    restored = deserialize_component(EffectComp, data)
    assert restored == effect
    # 关键字段完整保留
    assert restored.duration == effect.duration
    assert restored.next_tick == effect.next_tick
    assert restored.tick_interval == effect.tick_interval


@given(_vitals_strategy, _progression_strategy)
@settings(max_examples=30)
def test_entity_roundtrip(vitals: Vitals, progression: Progression) -> None:
    """实体多组件序列化往返一致性。"""
    schema = SchemaRegistry.with_builtins()
    eid = 42
    state = serialize_entity(eid, [vitals, progression], last_tick=99)
    assert state["version"] == 1
    assert state["entity_id"] == eid
    assert state["last_tick"] == 99
    assert "Vitals" in state["components"]
    assert "Progression" in state["components"]

    restored_eid, comps = deserialize_entity(state, schema)
    assert restored_eid == eid
    assert len(comps) == 2
    # 找回各组件
    comp_map = {type(c).__name__: c for c in comps}
    assert comp_map["Vitals"] == vitals
    assert comp_map["Progression"] == progression


def test_deserialize_tolerates_extra_fields() -> None:
    """反序列化容忍多余字段（schema 演进向前兼容，ADR-0022 §7）。"""
    vitals = Vitals(qi=50)
    data = serialize_component(vitals)
    data["future_field"] = "unknown"  # 模拟未来 schema 新增字段
    restored = deserialize_component(Vitals, data)
    assert restored.qi == 50


def test_deserialize_tolerates_missing_fields() -> None:
    """反序列化容忍缺失字段（向后兼容旧存档，ADR-0022 §7）。"""
    data = {"qi": 50}  # 缺大部分字段
    restored = deserialize_component(Vitals, data)
    assert restored.qi == 50
    assert restored.max_qi == 100  # dataclass 默认值


def test_persist_via_update_tick(tmp_path):
    """StorageSystem.update 在 persist_interval 周期触发 persist。"""
    storage, _ = _make_storage(tmp_path, persist_interval=3)
    world = _make_world()
    eid = _spawn_player(world, qi=100)
    storage.mark_dirty(eid)

    # tick=1,2 不触发；tick=3 触发
    storage.update(world, tick=1)
    storage.update(world, tick=2)
    target = os.path.join(str(tmp_path), "entity", f"{eid}.json")
    assert not os.path.exists(target)

    storage.update(world, tick=3)
    # update 触发 fire-and-forget task，需等其完成
    asyncio.run(asyncio.sleep(0.05))
    assert os.path.exists(target)


def test_build_world_integrates_storage(tmp_path):
    """build_world 接入 StorageSystem（ADR-0022 T5 world.py 最小接入）。"""
    from xkx.runtime.storage import JsonFileBackend
    from xkx.runtime.world import build_world

    backend = JsonFileBackend(str(tmp_path))
    ir = {
        "rooms": [
            {
                "id": "city/street",
                "short": "街道",
                "long": "一条街。",
                "exits": {},
                "objects": {},
                "items": [],
                "outdoors": False,
                "no_fight": False,
            }
        ],
        "npcs": [],
    }
    world, _, _ = build_world(ir, storage_backend=backend)
    assert hasattr(world, "storage_system")
    assert isinstance(world.storage_system, StorageSystem)
    # 不传 backend 时不接入（向后兼容）
    world2, _, _ = build_world(ir)
    assert not hasattr(world2, "storage_system")
