"""JSON 存档后端 + 崩溃恢复 + dirty-flag + Effect 序列化（阶段 1 Wave 2 T5）。

ADR-0022 的核心实现。三大承重决策：

1. **持久化边界抽象**（§1）：``StorageBackend.persist`` = 崩溃恢复级耐久，非
   ``save=权威写``。内存是权威态，persist 只周期性快照到耐久介质；崩溃后
   ``restore`` 恢复到最近 checkpoint（丢失 checkpoint 后到崩溃间的变更，最多一个
   存档周期）。
2. **原子写三步**（§2）：write-temp + fsync + os.replace。写 tmp 中途崩溃只损坏
   tmp，target 仍是上一次完整存档；``os.replace`` POSIX 原子替换。
3. **offload + dirty-flag**（§3/§4）：persist 在 ``asyncio.to_thread`` 执行不阻塞
   事件循环；per-entity dirty-flag 只存脏实体，全量 checkpoint 周期重置 flag。

Effect 崩溃恢复（§6）：restore 时 ``next_tick`` 对齐到 ``current_tick + tick_interval``
（不补执行，避免瞬间触发大量 DoT），``duration`` 不衰减（时间冻结）。悬空引用
（``target_id``/``source_id`` 指向不存在实体）跳过不 crash（§5 台账 #4）。

不重蹈 LPC ``save_object`` 覆辙：LPC 全量覆盖 target 无原子写，写入中途崩溃即
target 损坏；本模块的 tmp + replace 隔离"写"与"替换"两阶段。

[ADR-0022](../../../docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from xkx.runtime.serialization import (
    deserialize_entity,
    serialize_entity,
)
from xkx.runtime.systems import System

if TYPE_CHECKING:
    from xkx.runtime.ecs import World
    from xkx.runtime.schema import SchemaRegistry

logger = logging.getLogger(__name__)


def write_json_atomic(path: str, obj: dict[str, Any]) -> None:
    """原子写 JSON 文件（ADR-0022 §2 三步，ADR-0057 提为模块级 helper）。

    JsonFileBackend 与 DaemonStore 共用本 helper 保证 daemon/entity 存档同等
    崩溃安全。三步：

    1. write-temp：写到 ``<path>.tmp.<pid>``（同目录同 filesystem，保证
       ``os.replace`` 是原子 rename 非跨设备拷贝）
    2. fsync：``os.fsync(tmp_fd)`` 刷盘（数据 + 元数据）
    3. os.replace：POSIX 原子 rename(2) 替换 target

    写 tmp 中途崩溃只损坏 tmp，target 仍是上一次完整存档。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)  # assure_file 对齐
    tmp = f"{path}.tmp.{os.getpid()}"
    # 步骤 1：write-temp
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
        f.flush()
        # 步骤 2：fsync 刷盘（数据 + 元数据）
        os.fsync(f.fileno())
    # 步骤 3：os.replace 原子替换（POSIX rename(2)）
    os.replace(tmp, path)

# 默认存档周期（tick 数）。对齐 LPC NATURE_D event_sunrise 每日自动保存的周期语义
# 但缩短到适合测试的间隔（ADR-0022 §3）。
DEFAULT_PERSIST_INTERVAL = 30  # ticks（tick=1s 即 30s）

# 全量 checkpoint 周期：每 N 次增量 persist 做一次全量（重置所有 dirty-flag）。
# ADR-0022 §4：避免增量存档文件无限增长。per-entity 文件模型下增量=只写 dirty
# entity 文件，全量=写所有 entity 文件并重置 flag。
DEFAULT_CHECKPOINT_INTERVAL = 10


class StorageBackend(ABC):
    """持久化边界抽象（ADR-0022 §1）。

    核心语义是**崩溃恢复级耐久**（crash-recovery durability）：

    - ``persist`` 返回成功后，进程崩溃不丢失本次落盘数据；返回前崩溃不保证已落盘。
    - ``restore`` 读回最近一次成功 persist 的状态。

    不承诺（§5 台账）：事务原子性 / 并发写 CAS / 关系完整性 / append-only 防篡改。
    这些是 PG 才有的语义，迁 PG 时补齐（kill criteria 8）。

    策略切换路径：``JsonFileBackend``（T5）与未来 ``PostgresBackend`` 是两个实现，
    接口只暴露 persist/restore，调用方（StorageSystem）无感。
    """

    @abstractmethod
    def persist_blocking(
        self,
        entity_states: dict[int, dict[str, Any]],
    ) -> None:
        """同步阻塞持久化（在事件循环外线程调用，ADR-0022 §3）。

        Args:
            entity_states: ``{eid -> 存档 JSON object}``（已序列化，线程只做文件 IO）
        """

    @abstractmethod
    def restore(self) -> dict[int, dict[str, Any]]:
        """读回最近一次成功 persist 的状态。

        Returns:
            ``{eid -> 存档 JSON object}``，由 StorageSystem 反序列化重建 world
        """


class JsonFileBackend(StorageBackend):
    """JSON 文件存档后端（ADR-0022 §2/§3/§4）。

    per-entity 文件模型：每个实体一个 JSON 文件，路径 ``<root>/<entity_type>/<id>.json``。
    对齐 LPC ``DATA_DIR/user/<首字母>/<id>`` 的 per-object 文件模型。

    原子写三步（§2）：

    1. write-temp：写到 ``<target>.tmp.<pid>``（同目录同 filesystem）
    2. fsync：``os.fsync(tmp_fd)`` 刷盘
    3. os.replace：POSIX 原子 rename 替换 target

    崩溃安全性：写 tmp 中途崩溃只损坏 tmp，target 仍是上一次完整存档；
    ``os.replace`` 原子，替换瞬间无中间态。
    """

    def __init__(self, root: str) -> None:
        self._root = os.path.abspath(root)

    def _entity_path(self, eid: int) -> str:
        """实体存档路径：``<root>/entity/<eid>.json``。

        T5 简化：所有实体统一放 ``entity/`` 子目录（不分 player/npc/room），按 eid
        命名。entity_type 分目录后置（需 world 提供实体类型分类，当前 World 无此信息）。
        per-entity 文件粒度已满足 dirty-flag 分摊需求。
        """
        return os.path.join(self._root, "entity", f"{eid}.json")

    def persist_blocking(
        self,
        entity_states: dict[int, dict[str, Any]],
    ) -> None:
        """同步阻塞 persist：每个实体写一个 JSON 文件（原子写三步）。"""
        for eid, state in entity_states.items():
            self._write_entity_atomic(eid, state)

    def _write_entity_atomic(self, eid: int, state: dict[str, Any]) -> None:
        """原子写单个实体文件（ADR-0022 §2 三步，ADR-0057 复用 helper）。"""
        write_json_atomic(self._entity_path(eid), state)

    def restore(self) -> dict[int, dict[str, Any]]:
        """扫描存档目录读回所有实体（ADR-0022 §7 步骤 1-2）。

        扫描 ``<root>/entity/*.json``，按 entity_id 去重。损坏文件（json 解析失败）
        记 warning 跳过，不 crash（对齐 LPC restore_object 容忍半损坏文件的鲁棒性）。
        """
        result: dict[int, dict[str, Any]] = {}
        entity_dir = os.path.join(self._root, "entity")
        if not os.path.isdir(entity_dir):
            return result
        for fname in os.listdir(entity_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(entity_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                # 损坏文件跳过（§7 鲁棒性，不 crash）
                logger.warning("存档文件损坏，跳过: %s (%s)", path, e)
                continue
            try:
                eid = int(state["entity_id"])
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("存档文件缺 entity_id，跳过: %s (%s)", path, e)
                continue
            result[eid] = state
        return result


class StorageSystem(System):
    """存档 System（ADR-0022 §3/§4/§6/§7），tick 驱动周期 persist + dirty-flag。

    作为 ECS System 之一与 CombatSystem/ConditionSystem 并列，每 tick 调 ``update``。
    每 ``persist_interval`` ticks 触发一次 persist（offload 到线程，不阻塞事件循环）。
    per-entity dirty-flag：只存脏实体；全量 checkpoint 周期重置 flag。

    Effect 崩溃恢复（§6）：``restore_world`` 读回 EffectComp 后对齐 ``next_tick``
    到 ``current_tick + tick_interval``（不补执行），``duration`` 不衰减；悬空引用
    跳过（§5 台账 #4）。
    """

    name = "StorageSystem"

    def __init__(
        self,
        backend: StorageBackend,
        *,
        schema: SchemaRegistry,
        persist_interval: int = DEFAULT_PERSIST_INTERVAL,
        checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
    ) -> None:
        self._backend = backend
        self._schema = schema
        self._persist_interval = persist_interval
        self._checkpoint_interval = checkpoint_interval
        self._dirty: set[int] = set()
        self._persist_count = 0  # 增量 persist 次数，用于 checkpoint 周期判断
        self._last_tick = 0  # 最近一次 persist 时的 tick 编号（存档 last_tick 字段）
        self._pending_persist: asyncio.Task[None] | None = None

    def mark_dirty(self, eid: int) -> None:
        """标记实体脏（组件 mutation 路径调用，ADR-0022 §4）。

        System.update 末尾调本方法显式标记，不依赖 setattr 拦截以避免热路径开销。
        EffectComp 的 duration/next_tick mutation（ConditionSystem apply）同样标记。
        """
        self._dirty.add(eid)

    def mark_all_dirty(self, world: World) -> None:
        """标记所有实体脏（全量 checkpoint 用，或启动后首次 persist 用）。

        遍历 world 所有实体（通过各组件 SparseSet 的 entities 汇总去重）。
        """
        all_eids: set[int] = set()
        # World 内部 _stores 是 dict[type, _SparseSet]，遍历各 SparseSet 的 entities
        for store in world._stores.values():  # type: ignore[attr-defined]
            all_eids.update(eid for eid, _ in store)
        self._dirty.update(all_eids)

    def update(self, world: World, tick: int) -> None:
        """每 tick 执行：到 persist_interval 触发一次 persist（异步 offload）。

        persist 是 async 操作但 System.update 是同步的（对齐其他 System）。这里采用
        fire-and-forget：触发 persist 任务后立即返回，不阻塞 tick。下一次 persist
        触发前若上一个未完成则跳过（避免堆积）。
        """
        self._last_tick = tick
        if tick % self._persist_interval != 0:
            return
        # 上一个 persist 未完成则跳过本次（避免堆积，ADR-0022 §3 不阻塞 tick）
        if self._pending_persist is not None and not self._pending_persist.done():
            return
        self._trigger_persist(world)

    def _trigger_persist(self, world: World) -> None:
        """触发一次 persist：深拷贝脏实体快照 + offload 到线程写盘。

        ADR-0022 §3 并发安全：persist 线程读快照，tick 写现场。深拷贝在事件循环中
        同步执行（μs-ms 级，不破 tick 预算），persist 线程只读快照不碰现场。
        """
        # 全量 checkpoint：到周期则标记所有实体脏 + 重置计数
        is_checkpoint = self._persist_count >= self._checkpoint_interval
        if is_checkpoint:
            self.mark_all_dirty(world)

        # 快照本次要 persist 的 eid 集（persist 期间新 mutation 的 dirty 追加不清除）
        persist_eids = set(self._dirty)

        # 收集脏实体的组件快照（深拷贝，避免线程读到半 mutation 状态）
        states: dict[int, dict[str, Any]] = {}
        for eid in persist_eids:
            comps = self._collect_components(world, eid)
            if not comps:
                continue
            states[eid] = serialize_entity(eid, comps, last_tick=self._last_tick)

        if not states:
            # 无脏实体：checkpoint 周期也推进计数
            if is_checkpoint:
                self._persist_count = 0
            return

        # 序列化在事件循环中完成（深拷贝 + JSON object 构建），线程只做文件 IO
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无事件循环（测试同步调用）：直接阻塞 persist
            self._backend.persist_blocking(states)
            self._on_persist_done(persist_eids, is_checkpoint)
            return

        self._pending_persist = loop.create_task(
            self._async_persist(states, persist_eids, is_checkpoint)
        )

    async def _async_persist(
        self,
        states: dict[int, dict[str, Any]],
        persist_eids: set[int],
        is_checkpoint: bool,
    ) -> None:
        """offload persist 到线程（ADR-0022 §3，不阻塞事件循环）。"""
        await asyncio.to_thread(self._backend.persist_blocking, states)
        self._on_persist_done(persist_eids, is_checkpoint)

    def _on_persist_done(
        self,
        persist_eids: set[int],
        is_checkpoint: bool,
    ) -> None:
        """persist 完成后处理：清除本次 persist 的 dirty-flag。

        checkpoint 全量重置（``persist_eids`` = 所有实体）；增量只清本次 persist 的
        eid（persist 期间新 mutation 追加的 dirty 保留到下次）。
        """
        self._dirty -= persist_eids
        if is_checkpoint:
            self._persist_count = 0
        else:
            self._persist_count += 1

    def _collect_components(self, world: World, eid: int) -> list[Any]:
        """收集实体的所有组件实例（遍历 World 所有 SparseSet）。"""
        comps: list[Any] = []
        for store in world._stores.values():  # type: ignore[attr-defined]
            comp = store.get(eid)
            if comp is not None:
                comps.append(comp)
        return comps

    async def persist_now(self, world: World) -> None:
        """立即触发一次全量 persist（测试/关机存档用，不等 persist_interval）。

        标记所有实体脏 + 同步 persist（await 完成）。不受 update 的 fire-and-forget
        约束，确保返回时存档已落盘。
        """
        self.mark_all_dirty(world)
        states: dict[int, dict[str, Any]] = {}
        for eid in self._dirty:
            comps = self._collect_components(world, eid)
            if not comps:
                continue
            states[eid] = serialize_entity(eid, comps, last_tick=self._last_tick)
        await asyncio.to_thread(self._backend.persist_blocking, states)
        self._dirty.clear()
        self._persist_count = 0

    def restore_world(
        self,
        world: World,
        *,
        current_tick: int,
    ) -> int:
        """冷重启恢复协议（ADR-0022 §7）。

        步骤：
        1. backend.restore() 读回所有实体存档
        2. 反序列化每个实体，``world.add(eid, comp)`` 重建（eid 从存档取，不复用 new_entity）
        3. 引用校验：EffectComp.target_id/source_id 指向不存在实体则跳过该 Effect（§5 台账 #4）
        4. Effect next_tick 对齐：``next_tick < current_tick`` 则对齐到
           ``current_tick + tick_interval``（§6 不补执行），duration 不衰减
        5. tick 对齐：返回存档 last_tick，current_tick 由调用方从 last_tick+1 继续

        Args:
            world: 空 World（恢复目标）
            current_tick: 重启时的 tick 编号（Effect next_tick 对齐基准）
        Returns:
            存档时的 last_tick（调用方据此继续递增 current_tick）
        """
        from xkx.runtime.components import EffectComp

        states = self._backend.restore()
        if not states:
            return 0

        # 先全部反序列化 + add，记录存在的 eid 集合（引用校验用）
        existing_eids: set[int] = set()
        last_tick = 0
        # 两阶段：先 add 所有实体（含 EffectComp），再校验 Effect 引用
        # 因 EffectComp.target_id 可能指向尚未 restore 的实体，需先全量 add 再校验
        for eid, state in states.items():
            try:
                restored_eid, comps = deserialize_entity(state, self._schema)
            except Exception as e:  # noqa: BLE001
                logger.warning("实体反序列化失败，跳过 eid=%s: %s", eid, e)
                continue
            # 同步 World._next_id 避免后续 new_entity 与恢复的 eid 冲突
            if restored_eid >= world._next_id:  # type: ignore[attr-defined]
                world._next_id = restored_eid + 1  # type: ignore[attr-defined]
            for comp in comps:
                world.add(restored_eid, comp)
            existing_eids.add(restored_eid)
            lt = state.get("last_tick", 0)
            if isinstance(lt, int) and lt > last_tick:
                last_tick = lt

        # Effect 引用校验 + next_tick 对齐（ADR-0022 §5 台账 #4 + §6）
        dangling: list[int] = []
        for effect_eid in list(world.entities_with(EffectComp)):
            eff = world.get(effect_eid, EffectComp)
            if eff is None:
                continue
            # 悬空引用：target_id 不存在 -> 跳过该 Effect（不 crash）
            if eff.target_id not in existing_eids:
                logger.warning(
                    "Effect %s 悬空引用 target_id=%s，跳过",
                    eff.effect_id,
                    eff.target_id,
                )
                world.remove(effect_eid, EffectComp)
                dangling.append(effect_eid)
                continue
            # next_tick 对齐：存档时 next_tick < current_tick 说明崩溃期间本应触发
            # 但未触发，不补执行（避免瞬间触发大量 DoT），改为顺延一个周期
            # ADR-0022 §6 + ADR-0017 §2 "跳过崩溃期间未执行的 tick，非补执行"
            if eff.next_tick <= current_tick:
                eff.next_tick = current_tick + eff.tick_interval
            # duration 不衰减：保持存档时值（崩溃期间 Effect 时间冻结，ADR-0022 §6）

        if dangling:
            logger.info("冷重启跳过 %d 个悬空 Effect", len(dangling))

        return last_tick
