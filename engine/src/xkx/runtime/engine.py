"""统一 tick 循环 + System 注册（阶段 1 Wave 4 T10 整合遗留）。

Wave 2/3 各 System 分散实现（CombatSystem / StorageSystem / ConditionSystem /
ConnectionSystem / GovernanceSystem），T10 前收纳为统一 tick 循环，用
TickProfiler 测量 per-System compute（kill criteria 3 完整判定基础设施，
[12](../../../docs/xkx-arch/12-阶段1-核心循环实施计划.md) T10）。

整合遗留（PROGRESS.md Wave 2/3 整合遗留）：
- **CombatSystem**（combat/system.py）独立实现 -> ``CombatBridge`` 适配器接入
- **StorageSystem** 通过 ``world.storage_system`` 动态属性 -> 纳入 ``Engine.systems``
- **ConnectionSystem** 鸭子类型（``update(world, tick)``） -> 纳入 ``Engine.systems``
- **ConditionSystem** 已继承 ``System`` -> 纳入 ``Engine.systems``
- **GovernanceSystem**（governance.py）已继承 ``System`` -> 纳入 ``Engine.systems``
  （2.6 ADR-0029，death_stage 治理剧情 EffectComp tick 驱动）

非均匀 tick（CLAUDE.md 不变量）：tick=1s + compute<100ms。``Engine.tick`` 遍历
systems 调 ``update``，用 ``TickProfiler.measure_system`` 包裹计时。

[ADR-0023](../../../docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md) 决策 2
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xkx.combat.replay import CombatSnapshot, InputEntry
from xkx.combat.replay import replay as replay_fn
from xkx.combat.system import CombatSystem
from xkx.runtime.profiler import TickProfiler
from xkx.runtime.systems import System

if TYPE_CHECKING:
    from xkx.combat.result import CombatRoundResult
    from xkx.runtime.ecs import World


@runtime_checkable
class SystemLike(Protocol):
    """System 协议（鸭子类型）。

    CombatSystem / ConnectionSystem 不继承 ``runtime.systems.System``（避免循环依赖
    / 会话表非 ECS 组件），但只要满足 ``name`` + ``update(world, tick)`` 即可接入
    ``Engine.systems``。
    """

    name: str

    def update(self, world: World, tick: int) -> None: ...


class Engine:
    """统一 tick 循环引擎（T10 整合遗留）。

    维护 System 列表，每 tick 遍历调 ``update``，用 ``TickProfiler`` 测量 per-System
    compute。非均匀 tick：tick=1s 基准，compute<100ms 预算（CLAUDE.md 不变量）。

    用法（同步压测）::

        engine = Engine(world, profiler=TickProfiler(enabled=True))
        engine.add_system(ConditionSystem())
        engine.add_system(GovernanceSystem())  # 2.6 ADR-0029 治理剧情
        engine.add_system(CombatBridge())
        engine.add_system(world.storage_system)  # StorageSystem
        for _ in range(300):
            engine.tick()
        print(engine.profiler.report().to_table())
    """

    def __init__(
        self,
        world: World,
        *,
        profiler: TickProfiler | None = None,
        tick_interval: float = 1.0,
    ) -> None:
        self._world = world
        self._systems: list[SystemLike] = []
        self._profiler = profiler or TickProfiler(enabled=True)
        self._tick_interval = tick_interval
        self._tick_no = 0

    @property
    def world(self) -> World:
        return self._world

    @property
    def profiler(self) -> TickProfiler:
        return self._profiler

    @property
    def tick_no(self) -> int:
        return self._tick_no

    @property
    def tick_interval(self) -> float:
        return self._tick_interval

    @property
    def systems(self) -> list[SystemLike]:
        return list(self._systems)

    def add_system(self, system: SystemLike) -> None:
        """注册 System（按加入顺序 tick）。

        StorageSystem 接入时自动挂 ``world.storage_system``（供 CombatBridge /
        ConditionSystem 等 System 通过 ``getattr(world, "storage_system")`` 调
        ``mark_dirty``，ADR-0022 §4 mutation 路径标记）。build_world 已挂载时幂等。
        """
        self._systems.append(system)
        if system.name == "StorageSystem":
            self._world.storage_system = system  # type: ignore[attr-defined]

    def remove_system(self, name: str) -> SystemLike | None:
        """按 name 移除 System。"""
        for i, s in enumerate(self._systems):
            if s.name == name:
                return self._systems.pop(i)
        return None

    def get_system(self, name: str) -> SystemLike | None:
        """按 name 查找 System。"""
        for s in self._systems:
            if s.name == name:
                return s
        return None

    def tick(self) -> None:
        """推进一个 tick：遍历 System 调 update，用 profiler 计时。

        非均匀 tick（CLAUDE.md 不变量）：tick=1s 基准，compute<100ms 预算。
        调用方负责 tick 间隔（asyncio.sleep(tick_interval) 或压测中直接连续调）。
        """
        self._tick_no += 1
        self._profiler.next_tick()
        # M3-1 ADR-0032 决策 3：暴露当前 tick 给命令层（time-gate 冷却判定时间源）
        self._world.current_tick = self._tick_no  # type: ignore[attr-defined]
        for system in self._systems:
            with self._profiler.measure_system(system.name):
                system.update(self._world, self._tick_no)


class CombatBridge(System):
    """CombatSystem 适配器（T10 整合遗留）。

    ``CombatSystem``（combat/system.py）的 ``tick`` 接口接收 ``CombatSnapshot`` + seed
    （combat-only 确定性接口，ADR-0023 决策 2），与 ``System.update(world, tick)`` 签名
    不同。本适配器在 runtime 层桥接：从 world 构建快照 -> 按 enemy_ids 构建 input_log
    -> 调确定性重放 -> apply_effects 写回。

    combat 包保持自包含（不依赖 runtime），适配在 runtime 层（ADR-0023 决策 2 留口）。

    按 ``CombatState.enemy_ids`` 构建攻击对（O(活跃敌对对)），非 ``CombatSystem.tick``
    的 O(n²) 全 combatant 两两遍历--后者在 100 活跃战斗者下 9900 次攻击/tick 会超
    100ms 预算。真实场景 is_fighting 实体少且各有 1-2 敌人，input_log 规模可控。
    """

    name = "CombatSystem"

    def __init__(self, *, seed_base: int = 0) -> None:
        self._seed_base = seed_base

    def update(self, world: World, tick: int) -> None:
        from xkx.runtime.components import CombatState
        from xkx.runtime.world import apply_effects, to_snapshot

        # 收集活跃战斗者（is_fighting=True），构建 CombatantSnapshot 快照
        combatants: dict[int, object] = {}
        for eid in world.entities_with(CombatState):
            cs = world.get(eid, CombatState)
            if cs is None or not cs.is_fighting:
                continue
            combatants[eid] = to_snapshot(world, eid)

        if not combatants:
            return

        # 按 enemy_ids 构建 input_log（真实敌对对，非全两两遍历）
        input_log: list[InputEntry] = []
        seq = 0
        for attacker_id in combatants:
            cs = world.get(attacker_id, CombatState)
            if cs is None:
                continue
            for victim_id in cs.enemy_ids:
                if victim_id not in combatants:
                    continue
                input_log.append(
                    InputEntry(
                        attacker_id=attacker_id,
                        victim_id=victim_id,
                        attack_type=0,
                        seq=seq,
                    )
                )
                seq += 1

        if not input_log:
            return

        seed = self._seed_base + tick
        snapshot = CombatSnapshot(combatants=combatants, seed=seed)  # type: ignore[arg-type]
        results: list[CombatRoundResult] = replay_fn(snapshot, seed, input_log)

        # apply effects 写回 world（按账本顺序，含 riposte 子回合展开）
        for result in results:
            effects = CombatSystem.flatten_effects(result)
            apply_effects(world, effects)

        # ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist
        # （整合遗留：System mutation 路径显式标记，不依赖 setattr 拦截）
        storage = getattr(world, "storage_system", None)
        if storage is not None:
            for eid in combatants:
                storage.mark_dirty(eid)
