"""单例数据对象 per-object save（ADR-0057）。

承接 LPC F_SAVE 单例语义：bboard / job_data / job_server / mapdb 等全局单例
数据对象按自定义路径主动 save/restore，独立于 ``StorageSystem``（ECS 实体周期
persist + dirty-flag）。

核心边界（ADR-0057 决策 3/4）：

- daemon save 复用 ADR-0022 §2 原子写三步 + §3 offload，**不走 §4 dirty-flag**
  （dirty-flag 是周期 persist 的分摊优化，daemon 是业务变更点主动同步 save，
  无延迟语义，套 dirty-flag 是无意义层）。
- daemon 数据非 ECS 组件，直接 ``to_dict``/``from_dict`` JSON，不套
  ``serialize_entity``。
- daemon save 不在事件循环线程直接文件 IO，用 ``asyncio.to_thread`` offload
  避免阻塞 tick<100ms 预算；无事件循环时直接阻塞写。

[ADR-0057](../../../docs/adr/ADR-0057-daemon-store-per-object-save.md)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Protocol, runtime_checkable

from xkx.runtime.storage import write_json_atomic

logger = logging.getLogger(__name__)


@runtime_checkable
class DaemonSerializable(Protocol):
    """daemon 可序列化协议（ADR-0057 决策 1）。

    daemon 数据对象实现 ``to_dict``/``from_dict``，由 ``DaemonStore`` 直接
    ``json.dump`` dict 落盘（非 ECS 组件，不套 ``serialize_entity``）。

    ``from_dict`` 为类方法：``SomeDaemon.from_dict(d) -> SomeDaemon``。
    ``DaemonStore.register`` 时记录 daemon 的 ``type``，``restore_all`` 用
    ``type.from_dict`` 反序列化 re-register。
    """

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DaemonSerializable: ...


class DaemonStore:
    """单例数据对象 per-object save（ADR-0057 决策 1）。

    独立于 ``StorageSystem``，只共用 ``write_json_atomic`` helper。存档路径
    ``<root>/daemon/<name>.json``，name 由业务自定义（如 ``bboard_<board_id>``）。

    与 ``StorageSystem`` 的差异：daemon 是业务变更点主动 ``save(name)``（同步
    blocking，事件循环内 offload），不参与 tick 周期 persist / dirty-flag。
    """

    def __init__(self, root: str) -> None:
        self._root = os.path.abspath(root)
        self._daemons: dict[str, DaemonSerializable] = {}
        # name -> daemon type（restore_all 反序列化用 from_dict）
        self._types: dict[str, type[DaemonSerializable]] = {}

    @property
    def root(self) -> str:
        return self._root

    def _daemon_path(self, name: str) -> str:
        """daemon 存档路径：``<root>/daemon/<name>.json``（同 filesystem 保证 replace 原子）。"""
        return os.path.join(self._root, "daemon", f"{name}.json")

    def register(self, name: str, daemon: DaemonSerializable) -> None:
        """注册 daemon 实例（记录 type 供 restore_all 反序列化）。"""
        self._daemons[name] = daemon
        self._types[name] = type(daemon)

    def get(self, name: str) -> DaemonSerializable | None:
        """取已注册 daemon，未注册返回 None。"""
        return self._daemons.get(name)

    def save(self, name: str) -> None:
        """主动同步 save 单个 daemon（ADR-0057 决策 1/3，不走 dirty-flag）。

        sync blocking：直接阻塞写。daemon save 频率低（bboard 发帖 / job_data
        统计更新），单次 fsync 在 ms 级，可接受。事件循环内若需 offload 避免阻塞
        tick，调用方应改用 ``save_async``（``await store.save_async(name)``）。

        未注册 daemon 记 warning 跳过（对齐 LPC save 无对象时 no-op）。
        """
        daemon = self._daemons.get(name)
        if daemon is None:
            logger.warning("DaemonStore.save: 未注册 daemon %s，跳过", name)
            return
        path = self._daemon_path(name)
        state = self._serialize(daemon, name)
        write_json_atomic(path, state)

    async def save_async(self, name: str) -> None:
        """异步 save（事件循环内调用方 await，ADR-0022 §3 offload 不阻塞 tick）。"""
        daemon = self._daemons.get(name)
        if daemon is None:
            logger.warning("DaemonStore.save_async: 未注册 daemon %s，跳过", name)
            return
        path = self._daemon_path(name)
        state = self._serialize(daemon, name)
        await asyncio.to_thread(write_json_atomic, path, state)

    @staticmethod
    def _serialize(daemon: DaemonSerializable, name: str) -> dict[str, Any]:
        """序列化 daemon + 内部元字段（type 全限定名 + name，restore_all 用）。"""
        state = daemon.to_dict()
        state["__daemon_type__"] = (
            f"{type(daemon).__module__}:{type(daemon).__qualname__}"
        )
        state["__daemon_name__"] = name
        return state

    def restore_all(self) -> None:
        """扫描 ``<root>/daemon/*.json`` 反序列化 re-register（ADR-0057 决策 1）。

        损坏文件（json 解析失败 / type 不可定位 / from_dict 抛错）记 warning 跳过，
        不 crash（对齐 ``JsonFileBackend.restore`` 鲁棒性）。
        """
        daemon_dir = os.path.join(self._root, "daemon")
        if not os.path.isdir(daemon_dir):
            return
        for fname in os.listdir(daemon_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(daemon_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("daemon 存档损坏，跳过: %s (%s)", path, e)
                continue
            name = state.get("__daemon_name__") or fname[:-5]
            type_qname = state.get("__daemon_type__")
            daemon_type = self._resolve_type(type_qname)
            if daemon_type is None:
                logger.warning(
                    "daemon 存档 type 不可定位，跳过: %s (%s)", path, type_qname
                )
                continue
            try:
                # 剥离内部元字段后 from_dict
                payload = {k: v for k, v in state.items() if not k.startswith("__")}
                daemon = daemon_type.from_dict(payload)  # type: ignore[attr-defined]
            except Exception as e:  # noqa: BLE001
                logger.warning("daemon 反序列化失败，跳过 %s: %s", name, e)
                continue
            self.register(name, daemon)

    def _resolve_type(
        self, type_qname: str | None
    ) -> type[DaemonSerializable] | None:
        """按 ``module:QualName`` 定位 daemon type（restore_all 反序列化用）。

        优先从已注册 type 表查 qualname 匹配（避免任意 import 安全风险）；
        未命中再 importlib 定位（daemon type 必须在已注册集合内，否则跳过）。
        """
        if type_qname is None:
            return None
        for t in self._types.values():
            if f"{t.__module__}:{t.__qualname__}" == type_qname:
                return t
        # 未注册过该 type：不允许任意 import（安全），跳过
        return None
