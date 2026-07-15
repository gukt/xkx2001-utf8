"""DaemonStore 单测（ADR-0057）。

覆盖：原子写（写后读回一致 + tmp 清理）+ register/get/save/restore_all +
to_dict/from_dict 往返 + 事件循环内/外 save 不阻塞崩 + BboardData 往返 +
损坏文件鲁棒性 + job_data Protocol 占位可 register/save。
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from xkx.runtime.daemon_store import DaemonSerializable, DaemonStore
from xkx.runtime.daemons.bboard import BboardData, Note

# ──────────────────────── 原子写 ────────────────────────


def test_save_writes_valid_json_and_cleans_tmp(tmp_path: Any) -> None:
    """save 后 target 是合法 JSON + tmp 文件清理（write_json_atomic 三步）。"""
    store = DaemonStore(str(tmp_path))
    daemon = BboardData(board_id="b1", notes=[Note(title="t", author="a", time=1, msg="m")])
    store.register("bboard_b1", daemon)

    store.save("bboard_b1")

    target = tmp_path / "daemon" / "bboard_b1.json"
    assert target.exists()
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    assert state["board_id"] == "b1"
    assert state["notes"][0]["title"] == "t"
    # tmp 文件已 replace 清理（无残留 .tmp 文件）
    tmp_files = [p for p in (tmp_path / "daemon").iterdir() if ".tmp." in p.name]
    assert tmp_files == []


def test_save_unregistered_warns_not_raises(tmp_path: Any) -> None:
    """save 未注册 daemon 记 warning 跳过，不 raise。"""
    store = DaemonStore(str(tmp_path))
    store.save("nope")  # 不应 raise
    assert not (tmp_path / "daemon").exists() or not list(
        (tmp_path / "daemon").iterdir()
    )


# ──────────────────────── register / get ────────────────────────


def test_register_and_get(tmp_path: Any) -> None:
    store = DaemonStore(str(tmp_path))
    daemon = BboardData(board_id="b1")
    store.register("bboard_b1", daemon)
    assert store.get("bboard_b1") is daemon
    assert store.get("missing") is None


# ──────────────────────── to_dict / from_dict 往返 ────────────────────────


def test_bboard_data_roundtrip(tmp_path: Any) -> None:
    """BboardData save -> restore_all -> get 往返一致。"""
    store = DaemonStore(str(tmp_path))
    original = BboardData(
        board_id="city_board",
        notes=[
            Note(title="公告", author="巫师", time=1000, msg="内容"),
            Note(title="第二帖", author="玩家", time=2000, msg="回复"),
        ],
        wizard_only=True,
        poster_family="华山派",
    )
    store.register("bboard_city_board", original)
    store.save("bboard_city_board")

    # 新 store 模拟冷重启：restore_all 反序列化 re-register
    store2 = DaemonStore(str(tmp_path))
    # restore_all 需要已知 type 才能定位 from_dict；预注册一个同 type 实例建立 type 表
    store2.register("bboard_city_board", BboardData(board_id="city_board"))
    store2.restore_all()

    restored = store2.get("bboard_city_board")
    assert restored is not None
    assert isinstance(restored, BboardData)
    assert restored.board_id == "city_board"  # type: ignore[attr-defined]
    assert restored.wizard_only is True  # type: ignore[attr-defined]
    assert restored.poster_family == "华山派"  # type: ignore[attr-defined]
    notes = restored.notes  # type: ignore[attr-defined]
    assert len(notes) == 2
    assert notes[0].title == "公告"
    assert notes[1].msg == "回复"


def test_bboard_data_from_dict_roundtrip() -> None:
    """BboardData.to_dict -> from_dict 纯往返。"""
    original = BboardData(
        board_id="b",
        notes=[Note(title="t", author="a", time=5, msg="m")],
        wizard_only=False,
        poster_family=None,
    )
    d = original.to_dict()
    restored = BboardData.from_dict(d)
    assert restored.board_id == "b"
    assert restored.wizard_only is False
    assert restored.poster_family is None
    assert len(restored.notes) == 1
    assert restored.notes[0].author == "a"


# ──────────────────────── restore_all 鲁棒性 ────────────────────────


def test_restore_all_corrupt_file_skipped(tmp_path: Any) -> None:
    """损坏 JSON 文件记 warning 跳过，不 crash。"""
    store = DaemonStore(str(tmp_path))
    good = BboardData(board_id="good")
    store.register("bboard_good", good)
    store.save("bboard_good")

    # 写一个损坏文件
    daemon_dir = tmp_path / "daemon"
    (daemon_dir / "corrupt.json").write_text("{ not valid json", encoding="utf-8")

    store2 = DaemonStore(str(tmp_path))
    store2.register("bboard_good", BboardData(board_id="good"))
    store2.restore_all()  # 不应 raise

    restored = store2.get("bboard_good")
    assert restored is not None
    assert store2.get("corrupt") is None


def test_restore_all_unknown_type_skipped(tmp_path: Any) -> None:
    """type 不可定位（未注册）的存档跳过（安全，不任意 import）。"""
    store = DaemonStore(str(tmp_path))
    store.register("bboard_b1", BboardData(board_id="b1"))
    store.save("bboard_b1")

    # 改写存档的 __daemon_type__ 为未注册 type
    target = tmp_path / "daemon" / "bboard_b1.json"
    state = json.loads(target.read_text(encoding="utf-8"))
    state["__daemon_type__"] = "nonexistent.module:Nope"
    target.write_text(json.dumps(state), encoding="utf-8")

    store2 = DaemonStore(str(tmp_path))
    # 不预注册任何 BboardData，type 表为空 -> 跳过
    store2.restore_all()  # 不应 raise
    assert store2.get("bboard_b1") is None


def test_restore_all_empty_dir(tmp_path: Any) -> None:
    """无 daemon 目录时 restore_all 不 raise（返回空）。"""
    store = DaemonStore(str(tmp_path))
    store.restore_all()  # 不应 raise


# ──────────────────────── 事件循环内/外 save ────────────────────────


def test_save_outside_event_loop(tmp_path: Any) -> None:
    """无事件循环时 save 直接阻塞写（不报错）。"""
    store = DaemonStore(str(tmp_path))
    store.register("bboard_b1", BboardData(board_id="b1"))
    store.save("bboard_b1")
    assert (tmp_path / "daemon" / "bboard_b1.json").exists()


def test_save_async_inside_event_loop(tmp_path: Any) -> None:
    """事件循环内 await save_async offload 不阻塞崩。"""
    store = DaemonStore(str(tmp_path))
    store.register("bboard_b1", BboardData(board_id="b1"))

    async def run() -> None:
        await store.save_async("bboard_b1")

    asyncio.run(run())
    assert (tmp_path / "daemon" / "bboard_b1.json").exists()


def test_save_inside_running_loop_via_sync_does_not_deadlock(tmp_path: Any) -> None:
    """sync save 在事件循环内调用也不死锁（直接阻塞写，daemon save 频率低可接受）。"""
    store = DaemonStore(str(tmp_path))
    store.register("bboard_b1", BboardData(board_id="b1"))

    result: list[bool] = []

    async def run() -> None:
        # sync save 在事件循环内：直接阻塞写（非 to_thread，不死锁）
        store.save("bboard_b1")
        result.append((tmp_path / "daemon" / "bboard_b1.json").exists())

    asyncio.run(run())
    assert result == [True]


# ──────────────────────── DaemonSerializable Protocol ────────────────────────


def test_bboard_data_is_daemon_serializable() -> None:
    """BboardData 满足 DaemonSerializable Protocol（runtime_checkable）。"""
    assert isinstance(BboardData(), DaemonSerializable)


# ──────────────────────── 自定义 daemon 往返 ────────────────────────


@dataclass
class _Counters:
    """测试用自定义 daemon（验证 DaemonStore 不绑死 BboardData）。"""

    visits: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"visits": dict(self.visits)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> _Counters:
        return cls(visits=dict(d.get("visits", {})))


def test_custom_daemon_roundtrip(tmp_path: Any) -> None:
    """自定义 daemon（非 BboardData）也能 register/save/restore_all 往返。"""
    store = DaemonStore(str(tmp_path))
    store.register("counters", _Counters(visits={"room/a": 3, "room/b": 1}))
    store.save("counters")

    store2 = DaemonStore(str(tmp_path))
    store2.register("counters", _Counters())
    store2.restore_all()

    restored = store2.get("counters")
    assert restored is not None
    assert restored.visits == {"room/a": 3, "room/b": 1}  # type: ignore[attr-defined]


# ──────────────────────── job_data Protocol 占位 ────────────────────────


def test_job_data_like_can_register_and_save(tmp_path: Any) -> None:
    """job_data 这类对象可 register/save（空壳占位，完整建模留后续批，ADR-0057 决策不做）。"""

    @dataclass
    class _JobDataStub:
        """job_data 空壳（实现 DaemonSerializable 供 DaemonStore 接管）。"""

        loaded: bool = False

        def to_dict(self) -> dict[str, Any]:
            return {"loaded": self.loaded}

        @classmethod
        def from_dict(cls, d: dict[str, Any]) -> _JobDataStub:
            return cls(loaded=d.get("loaded", False))

    store = DaemonStore(str(tmp_path))
    store.register("job_data", _JobDataStub(loaded=True))
    store.save("job_data")
    assert (tmp_path / "daemon" / "job_data.json").exists()

    store2 = DaemonStore(str(tmp_path))
    store2.register("job_data", _JobDataStub())
    store2.restore_all()
    restored = store2.get("job_data")
    assert restored is not None
    assert restored.loaded is True  # type: ignore[attr-defined]


# ──────────────────────── 存档路径在同目录 ────────────────────────


def test_daemon_path_under_root_daemon(tmp_path: Any) -> None:
    """daemon 存档路径在 <root>/daemon/ 下（同 filesystem 保证 os.replace 原子）。"""
    store = DaemonStore(str(tmp_path))
    store.register("bboard_b1", BboardData(board_id="b1"))
    store.save("bboard_b1")
    target = tmp_path / "daemon" / "bboard_b1.json"
    # target 与其 tmp（同目录）在同一 filesystem（os.replace 原子前提）
    assert os.path.dirname(str(target)) == os.path.join(str(tmp_path), "daemon")


def test_root_absolute(tmp_path: Any) -> None:
    """root 转绝对路径。"""
    store = DaemonStore(str(tmp_path))
    assert os.path.isabs(store.root)
