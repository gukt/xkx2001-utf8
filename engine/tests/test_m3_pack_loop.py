"""M3-05：端到端内容包闭环（示例包剧本 + ``--validate`` 坏包 + CLI 存档恢复）。

Seams：
- 剧本：``tmp_path`` 复制的包 + ``load_pack`` + ``execute_line``（可观察消息 / 位置）
- 坏包：``_main([..., "--validate"])``（退出码 / stderr 前缀 / 无 save 副作用）
- 存档恢复：``_main(["--pack", ...])`` + stub ``run_repl``（真实 CLI 层存档/重挂）
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from mud_engine.__main__ import _main
from mud_engine.components import Container, Currency, Identity, Position
from mud_engine.pack import load_manifest, load_pack
from mud_engine.parsing import execute_line
from mud_engine.world import EntityId, World

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_PACK = (
    _REPO_ROOT / ".scratch" / "m3-ugc-loop-creation-surface" / "example-pack"
)


def _copy_example_pack(dest: Path) -> Path:
    shutil.copytree(_EXAMPLE_PACK, dest)
    return dest


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _inventory_names(world: World, player_id: EntityId) -> set[str]:
    bag = world.require_component(player_id, Container)
    return {world.require_component(item, Identity).name for item in bag.items}


def _player_room_name(world: World, player_id: EntityId) -> str:
    """用房间 Identity.name 定位（restore 后 ``room_ids`` 为空，不能靠键映射）。"""
    room = world.require_component(player_id, Position).room
    return world.require_component(room, Identity).name


def _combined(messages: list[str]) -> str:
    return "\n".join(messages)


@pytest.fixture
def stub_repl(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stub = MagicMock()
    monkeypatch.setattr("mud_engine.__main__.run_repl", stub)
    return stub


class TestM3PackJourney:
    """04 号票命令清单的自动化锁死（包在任意 tmp 路径）。"""

    def test_look_shows_airlock(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        messages = execute_line(world, player_id, "look")
        assert "气闸舱" in _combined(messages)

    def test_go_east_reaches_supply(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        messages = execute_line(world, player_id, "go east")
        assert "补给舱" in _combined(messages)
        assert world.require_component(player_id, Position).room == _room(
            world, "outpost_supply"
        )

    def test_get_access_card(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        execute_line(world, player_id, "go east")
        messages = execute_line(world, player_id, "get 通行卡")
        assert "通行卡" in _combined(messages)
        assert "通行卡" in _inventory_names(world, player_id)

    def test_unlock_open_and_enter_control(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "get 通行卡")
        unlock = execute_line(world, player_id, "unlock east")
        assert "解锁" in _combined(unlock)
        open_msgs = execute_line(world, player_id, "open east")
        assert "打开" in _combined(open_msgs)
        enter = execute_line(world, player_id, "go east")
        assert "主控室" in _combined(enter)
        assert world.require_component(player_id, Position).room == _room(
            world, "outpost_control"
        )

    def test_ask_inquiry_topic(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        self._arrive_control(world, player_id)
        messages = execute_line(world, player_id, "ask 维修机器人 about 站点")
        assert "废弃探测站" in _combined(messages)

    def test_ask_inquiry_default(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        self._arrive_control(world, player_id)
        messages = execute_line(world, player_id, "ask 维修机器人 about 未知话题xyz")
        assert "可询问" in _combined(messages)

    def test_buy_power_cell(self, tmp_path: Path) -> None:
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        self._arrive_control(world, player_id)
        before = world.require_component(player_id, Currency).amount
        messages = execute_line(world, player_id, "buy 备用能量芯")
        assert "备用能量芯" in _combined(messages)
        assert world.require_component(player_id, Currency).amount == before - 25
        assert "备用能量芯" in _inventory_names(world, player_id)

    def test_full_loop_ends_in_control_room(self, tmp_path: Path) -> None:
        """整条 04 号票序列串跑一遍，终点为主控室。"""
        world, player_id = load_pack(_copy_example_pack(tmp_path / "pack"))
        execute_line(world, player_id, "look")
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "get 通行卡")
        execute_line(world, player_id, "unlock east")
        execute_line(world, player_id, "open east")
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "ask 维修机器人 about 站点")
        execute_line(world, player_id, "ask 维修机器人 about 未知话题xyz")
        execute_line(world, player_id, "buy 备用能量芯")
        look = execute_line(world, player_id, "look")
        assert "主控室" in _combined(look)
        assert world.require_component(player_id, Position).room == _room(
            world, "outpost_control"
        )

    @staticmethod
    def _arrive_control(world: World, player_id: EntityId) -> None:
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "get 通行卡")
        execute_line(world, player_id, "unlock east")
        execute_line(world, player_id, "open east")
        execute_line(world, player_id, "go east")


class TestM3ValidateBadPacks:
    def test_missing_manifest_id_returns_nonzero(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._drop_manifest_id(pack_dir)
        assert _main(["--pack", str(pack_dir), "--validate"]) == 1

    def test_missing_manifest_id_stderr_uses_pack_prefix(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._drop_manifest_id(pack_dir)
        _main(["--pack", str(pack_dir), "--validate"])
        err = capsys.readouterr().err
        assert "包清单" in err
        assert "id" in err

    def test_missing_manifest_id_does_not_create_save(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._drop_manifest_id(pack_dir)
        _main(["--pack", str(pack_dir), "--validate"])
        assert not (pack_dir / "save").exists()

    def test_bad_exit_target_returns_nonzero(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._break_exit_target(pack_dir)
        assert _main(["--pack", str(pack_dir), "--validate"]) == 1

    def test_bad_exit_target_stderr_uses_scene_prefix(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._break_exit_target(pack_dir)
        _main(["--pack", str(pack_dir), "--validate"])
        err = capsys.readouterr().err
        assert "场景内容" in err

    def test_bad_exit_target_does_not_create_save(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        self._break_exit_target(pack_dir)
        _main(["--pack", str(pack_dir), "--validate"])
        assert not (pack_dir / "save").exists()

    @staticmethod
    def _drop_manifest_id(pack_dir: Path) -> None:
        path = pack_dir / "manifest.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        del data["id"]
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    @staticmethod
    def _break_exit_target(pack_dir: Path) -> None:
        path = pack_dir / "scene.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("to: outpost_supply", "to: nonexistent_room"),
            encoding="utf-8",
        )


class TestM3PackCliSaveRestore:
    def test_restores_position_after_save(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        saved_room: list[str] = []

        def play_and_save(world, player_id, *, tick_loop=None, **_kwargs):
            execute_line(world, player_id, "go east")
            execute_line(world, player_id, "get 通行卡")
            saved_room.append(_player_room_name(world, player_id))
            assert tick_loop is not None
            tick_loop.force_save()

        stub_repl.side_effect = play_and_save
        assert _main(["--pack", str(pack_dir)]) == 0

        restored: list[World] = []

        def capture_restore(world, player_id, **_kwargs):
            restored.append(world)
            assert _player_room_name(world, player_id) == saved_room[0]

        stub_repl.side_effect = capture_restore
        assert _main(["--pack", str(pack_dir)]) == 0
        assert len(restored) == 1

    def test_restores_inventory_after_save(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        saved_inv: list[set[str]] = []

        def play_and_save(world, player_id, *, tick_loop=None, **_kwargs):
            execute_line(world, player_id, "go east")
            execute_line(world, player_id, "get 通行卡")
            saved_inv.append(_inventory_names(world, player_id))
            assert tick_loop is not None
            tick_loop.force_save()

        stub_repl.side_effect = play_and_save
        _main(["--pack", str(pack_dir)])

        def capture_restore(world, player_id, **_kwargs):
            assert _inventory_names(world, player_id) == saved_inv[0]

        stub_repl.side_effect = capture_restore
        _main(["--pack", str(pack_dir)])

    def test_reattaches_pack_manifest_after_restore(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _copy_example_pack(tmp_path / "pack")
        expected = load_manifest(pack_dir)

        def play_and_save(world, player_id, *, tick_loop=None, **_kwargs):
            execute_line(world, player_id, "go east")
            assert tick_loop is not None
            tick_loop.force_save()

        stub_repl.side_effect = play_and_save
        _main(["--pack", str(pack_dir)])

        restored_manifest: list = []

        def capture_restore(world, player_id, **_kwargs):
            restored_manifest.append(world.pack_manifest)

        stub_repl.side_effect = capture_restore
        _main(["--pack", str(pack_dir)])
        assert restored_manifest == [expected]
