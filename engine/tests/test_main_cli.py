"""M3-03：``python -m mud_engine`` 的 ``_main(argv) -> int`` seam。

不 fork 子进程；``run_repl`` 用 monkeypatch stub，避免真实 stdin。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mud_engine.__main__ import DEFAULT_SAVE_DIR, _main
from mud_engine.pack import load_manifest, load_pack
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

    def test_enters_repl_once(self, stub_repl: MagicMock) -> None:
        _main([])
        stub_repl.assert_called_once()

    def test_loads_default_scene_path(self, stub_repl: MagicMock) -> None:
        _main([])
        world, _player_id = stub_repl.call_args.args[:2]
        assert world.scene_path == DEFAULT_SCENE_PATH.resolve()

    def test_pack_manifest_stays_none(self, stub_repl: MagicMock) -> None:
        _main([])
        world, _player_id = stub_repl.call_args.args[:2]
        assert world.pack_manifest is None

    def test_uses_default_save_dir(
        self, stub_repl: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saved_dirs: list[Path] = []

        def fake_save(world, player_id, save_dir: Path) -> None:
            saved_dirs.append(save_dir)

        monkeypatch.setattr("mud_engine.__main__.save_world", fake_save)

        def capture_repl(world, player_id, *, tick_loop=None, **_kwargs):
            assert tick_loop is not None
            tick_loop.force_save()

        stub_repl.side_effect = capture_repl
        _main([])
        assert saved_dirs == [DEFAULT_SAVE_DIR]


class TestValidateRequiresPack:
    def test_returns_nonzero(self, stub_repl: MagicMock) -> None:
        assert _main(["--validate"]) != 0

    def test_mentions_both_flags_in_stderr(self, stub_repl: MagicMock, capsys) -> None:
        _main(["--validate"])
        err = capsys.readouterr().err
        assert "--validate" in err
        assert "--pack" in err

    def test_does_not_enter_repl(self, stub_repl: MagicMock) -> None:
        _main(["--validate"])
        stub_repl.assert_not_called()


class TestPackValidateSuccess:
    def test_returns_zero(self, tmp_path: Path, stub_repl: MagicMock) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        assert _main(["--pack", str(pack_dir), "--validate"]) == 0

    def test_stdout_contains_id(self, tmp_path: Path, stub_repl: MagicMock, capsys) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        assert "test-pack" in capsys.readouterr().out

    def test_stdout_contains_version(self, tmp_path: Path, stub_repl: MagicMock, capsys) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        assert "0.1.0" in capsys.readouterr().out

    def test_stdout_contains_room_count(self, tmp_path: Path, stub_repl: MagicMock, capsys) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        assert "2" in capsys.readouterr().out

    def test_does_not_enter_repl(self, tmp_path: Path, stub_repl: MagicMock) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        stub_repl.assert_not_called()

    def test_does_not_create_save_dir(self, tmp_path: Path, stub_repl: MagicMock) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        _main(["--pack", str(pack_dir), "--validate"])
        assert not (pack_dir / "save").exists()

    class WhenSaveDirAlreadyExists:
        def test_still_validates_against_pack_content(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            pack_dir = _write_pack(tmp_path / "pack")
            (pack_dir / "save").mkdir()
            (pack_dir / "save" / "junk").write_text("not a real save", encoding="utf-8")
            assert _main(["--pack", str(pack_dir), "--validate"]) == 0
            assert "test-pack" in capsys.readouterr().out


class TestPackValidateFailure:
    class WhenManifestIsInvalid:
        def test_returns_one(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            pack_dir = _write_pack(tmp_path / "pack", manifest="version: '1'\n")
            assert _main(["--pack", str(pack_dir), "--validate"]) == 1

        def test_stderr_mentions_pack_manifest(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            pack_dir = _write_pack(tmp_path / "pack", manifest="version: '1'\n")
            _main(["--pack", str(pack_dir), "--validate"])
            assert "包清单" in capsys.readouterr().err

    class WhenSceneIsInvalid:
        def test_returns_one(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
            pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
            assert _main(["--pack", str(pack_dir), "--validate"]) == 1

        def test_stderr_mentions_scene_content(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
            pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
            _main(["--pack", str(pack_dir), "--validate"])
            assert "场景内容" in capsys.readouterr().err


class TestPackPlayMode:
    class WhenPackIsFresh:
        def test_returns_zero(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            pack_dir = _write_pack(tmp_path / "pack")
            assert _main(["--pack", str(pack_dir)]) == 0

        def test_attaches_pack_manifest(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            pack_dir = _write_pack(tmp_path / "pack")
            _main(["--pack", str(pack_dir)])
            world, _player_id = stub_repl.call_args.args[:2]
            assert world.pack_manifest == load_manifest(pack_dir)

        def test_save_dir_is_under_pack(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            pack_dir = _write_pack(tmp_path / "pack")

            def capture_repl(world, player_id, *, tick_loop=None, **_kwargs):
                assert tick_loop is not None
                tick_loop.force_save()

            stub_repl.side_effect = capture_repl
            _main(["--pack", str(pack_dir)])
            assert has_save(pack_dir / "save") is True

    class WhenSaveAlreadyExists:
        def test_reattaches_pack_manifest(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            pack_dir = _write_pack(tmp_path / "pack")
            world, player_id = load_pack(pack_dir)
            before = world.pack_manifest
            assert before is not None
            save_world(world, player_id, pack_dir / "save")

            captured: list = []

            def capture_repl(world, player_id, **_kwargs):
                captured.append(world)

            stub_repl.side_effect = capture_repl
            _main(["--pack", str(pack_dir)])
            assert captured[0].pack_manifest == before

    class WhenPackDirectoryIsMissing:
        def test_returns_nonzero(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            assert _main(["--pack", str(tmp_path / "no-such-pack")]) != 0

        def test_stderr_is_not_a_traceback(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            _main(["--pack", str(tmp_path / "no-such-pack")])
            err = capsys.readouterr().err
            assert err.strip()
            assert "Traceback" not in err

        def test_stderr_does_not_use_pack_manifest_prefix(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            _main(["--pack", str(tmp_path / "no-such-pack")])
            assert "包清单" not in capsys.readouterr().err

        def test_does_not_enter_repl(self, tmp_path: Path, stub_repl: MagicMock) -> None:
            _main(["--pack", str(tmp_path / "no-such-pack")])
            stub_repl.assert_not_called()

    class WhenManifestIsMissing:
        def test_stderr_mentions_pack_manifest(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            pack_dir = tmp_path / "pack"
            pack_dir.mkdir()
            (pack_dir / "scene.yaml").write_text(_MINIMAL_SCENE, encoding="utf-8")
            _main(["--pack", str(pack_dir)])
            assert "包清单" in capsys.readouterr().err

    class WhenSceneIsInvalid:
        def test_stderr_mentions_scene_content(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
            pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
            _main(["--pack", str(pack_dir)])
            assert "场景内容" in capsys.readouterr().err

    class WhenValidateAndPlayFailTheSameWay:
        def test_stderr_messages_are_identical(
            self, tmp_path: Path, stub_repl: MagicMock, capsys
        ) -> None:
            pack_dir = _write_pack(tmp_path / "pack", manifest="version: '1'\n")
            _main(["--pack", str(pack_dir), "--validate"])
            validate_err = capsys.readouterr().err
            _main(["--pack", str(pack_dir)])
            play_err = capsys.readouterr().err
            assert validate_err == play_err


_SCENE_WITH_UNCONSUMED = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    typo_field: oops
    exits: {}
mystery_section:
  enabled: true
player:
  name: 你
  start_room: start_yard
"""


class TestValidateStrictUnconsumed:
    def test_strict_requires_validate(self, stub_repl: MagicMock, capsys) -> None:
        assert _main(["--strict"]) != 0
        err = capsys.readouterr().err
        assert "--strict" in err
        assert "--validate" in err
        stub_repl.assert_not_called()

    def test_validate_warns_but_exits_zero(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack", scene=_SCENE_WITH_UNCONSUMED)
        assert _main(["--pack", str(pack_dir), "--validate"]) == 0
        captured = capsys.readouterr()
        assert "警告" in captured.err
        assert "typo_field" in captured.err or "mystery_section" in captured.err
        assert "test-pack" in captured.out

    def test_validate_strict_exits_nonzero(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack", scene=_SCENE_WITH_UNCONSUMED)
        assert _main(["--pack", str(pack_dir), "--validate", "--strict"]) != 0
        err = capsys.readouterr().err
        assert "未消费" in err or "校验失败" in err
        assert "typo_field" in err or "mystery_section" in err

    def test_clean_pack_strict_exits_zero_no_warn(
        self, tmp_path: Path, stub_repl: MagicMock, capsys
    ) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        assert _main(["--pack", str(pack_dir), "--validate", "--strict"]) == 0
        captured = capsys.readouterr()
        assert "警告" not in captured.err
        assert "未消费" not in captured.err
        assert "test-pack" in captured.out
