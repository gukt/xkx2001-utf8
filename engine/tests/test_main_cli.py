"""M3-03：``python -m mud_engine`` 的 ``_main(argv) -> int`` seam。

不 fork 子进程；``run_repl`` 用 monkeypatch stub，避免真实 stdin。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mud_engine.__main__ import _main
from mud_engine.pack import load_manifest
from mud_engine.save import has_save, save_world
from mud_engine.scenes import DEFAULT_SCENE_PATH

_MINIMAL_SCENE = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    exits:
      north: { to: corridor }
  corridor:
    name: 长廊
    long: 长廊
    exits:
      south: { to: start_yard }
player:
  name: 你
  start_room: start_yard
"""

_VALID_MANIFEST = """
id: test-pack
version: "0.1.0"
creator: tester
title: 测试包
"""


def _write_pack(
    pack_dir: Path,
    *,
    manifest: str = _VALID_MANIFEST,
    scene: str = _MINIMAL_SCENE,
) -> Path:
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    (pack_dir / "scene.yaml").write_text(scene, encoding="utf-8")
    return pack_dir


@pytest.fixture
def stub_repl(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stub = MagicMock()
    monkeypatch.setattr("mud_engine.__main__.run_repl", stub)
    return stub


class TestMainNoArgs:
    def test_returns_zero(self, stub_repl: MagicMock) -> None:
        assert _main([]) == 0
        stub_repl.assert_called_once()

    def test_loads_default_scene_path(self, stub_repl: MagicMock) -> None:
        _main([])
        world, _player_id = stub_repl.call_args.args[:2]
        assert world.scene_path == DEFAULT_SCENE_PATH.resolve()
        assert world.pack_manifest is None
        assert stub_repl.call_args.kwargs["tick_loop"] is not None


class TestValidateRequiresPack:
    def test_validate_alone_returns_nonzero(self, stub_repl: MagicMock, capsys) -> None:
        code = _main(["--validate"])
        assert code != 0
        err = capsys.readouterr().err
        assert "--validate" in err
        assert "--pack" in err
        stub_repl.assert_not_called()


class TestPackValidateSuccess:
    def test_returns_zero_and_prints_summary(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        code = _main(["--pack", str(pack_dir), "--validate"])
        assert code == 0
        out = capsys.readouterr().out
        assert "test-pack" in out
        assert "0.1.0" in out
        assert "2" in out  # 两个房间
        stub_repl.assert_not_called()

    def test_does_not_create_save_dir(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        assert not (pack_dir / "save").exists()

    def test_ignores_existing_save_contents(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        (pack_dir / "save").mkdir()
        (pack_dir / "save" / "junk").write_text("not a real save", encoding="utf-8")
        code = _main(["--pack", str(pack_dir), "--validate"])
        assert code == 0
        assert "test-pack" in capsys.readouterr().out
        stub_repl.assert_not_called()


class TestPackValidateFailure:
    def test_bad_manifest_returns_one_with_pack_prefix(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack", manifest="version: '1'\n")
        code = _main(["--pack", str(pack_dir), "--validate"])
        assert code == 1
        err = capsys.readouterr().err
        assert "包清单" in err
        stub_repl.assert_not_called()

    def test_bad_scene_returns_one_with_scene_prefix(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
        pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
        code = _main(["--pack", str(pack_dir), "--validate"])
        assert code == 1
        err = capsys.readouterr().err
        assert "场景内容" in err
        stub_repl.assert_not_called()


class TestPackPlayMode:
    def test_fresh_pack_enters_repl_with_loaded_manifest(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        code = _main(["--pack", str(pack_dir)])
        assert code == 0
        stub_repl.assert_called_once()
        world, _player_id = stub_repl.call_args.args[:2]
        expected = load_manifest(pack_dir)
        assert world.pack_manifest == expected

    def test_save_dir_is_under_pack(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")

        def capture_repl(world, player_id, *, tick_loop=None, **_kwargs):
            assert tick_loop is not None
            tick_loop.force_save()

        stub_repl.side_effect = capture_repl
        _main(["--pack", str(pack_dir)])
        assert has_save(pack_dir / "save") is True

    def test_restore_reattaches_pack_manifest(
        self, tmp_path: Path, stub_repl: MagicMock
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        # 模拟"已经玩过一次"：先写好存档。
        from mud_engine.pack import load_pack

        world, player_id = load_pack(pack_dir)
        before = world.pack_manifest
        assert before is not None
        save_world(world, player_id, pack_dir / "save")

        captured: list = []

        def capture_repl(world, player_id, **_kwargs):
            captured.append(world)

        stub_repl.side_effect = capture_repl
        code = _main(["--pack", str(pack_dir)])
        assert code == 0
        assert len(captured) == 1
        assert captured[0].pack_manifest == before

    def test_missing_directory_returns_nonzero(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        missing = tmp_path / "no-such-pack"
        code = _main(["--pack", str(missing)])
        assert code != 0
        err = capsys.readouterr().err
        assert err.strip()
        assert "Traceback" not in err
        stub_repl.assert_not_called()

    def test_missing_manifest_mentions_pack_清单(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "scene.yaml").write_text(_MINIMAL_SCENE, encoding="utf-8")
        code = _main(["--pack", str(pack_dir)])
        assert code != 0
        err = capsys.readouterr().err
        assert "包清单" in err
        stub_repl.assert_not_called()

    def test_bad_scene_mentions_场景内容(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
        pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
        code = _main(["--pack", str(pack_dir)])
        assert code != 0
        err = capsys.readouterr().err
        assert "场景内容" in err
        stub_repl.assert_not_called()

    def test_validate_and_play_share_same_error_message(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack", manifest="version: '1'\n")
        _main(["--pack", str(pack_dir), "--validate"])
        validate_err = capsys.readouterr().err
        _main(["--pack", str(pack_dir)])
        play_err = capsys.readouterr().err
        assert validate_err == play_err
        stub_repl.assert_not_called()
