"""内容包组合加载（M3-02）：``load_pack`` / ``reattach_pack_manifest`` seam。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mud_engine.components import Exits, Identity, Position
from mud_engine.errors import PackManifestError
from mud_engine.pack import load_manifest, load_pack, reattach_pack_manifest
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import SceneLoadError, load_scene
from mud_engine.world import World

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


class TestWorldPackManifestField:
    def test_defaults_to_none(self) -> None:
        world = World()
        assert world.pack_manifest is None


class TestLoadPackSuccess:
    def test_attaches_manifest_and_matches_load_scene(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        expected_manifest = load_manifest(pack_dir)
        scene_world, scene_player = load_scene(pack_dir / "scene.yaml")

        world, player_id = load_pack(pack_dir)

        assert world.pack_manifest == expected_manifest
        assert player_id == scene_player
        assert world.scene_path == (pack_dir / "scene.yaml").resolve()
        room = world.require_component(player_id, Position).room
        assert world.require_component(room, Identity).name == "起始庭院"
        corridor = world.require_component(room, Exits).by_direction["north"].target
        assert world.require_component(corridor, Identity).name == "长廊"
        assert len(list(world.all_entities())) == len(list(scene_world.all_entities()))


class TestLoadPackFailures:
    def test_bad_manifest_raises_before_load_scene(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(
            tmp_path / "pack",
            manifest="version: '1'\n",  # 缺 id
        )
        with patch("mud_engine.pack.load_scene") as spy_load_scene:
            with pytest.raises(PackManifestError) as exc_info:
                load_pack(pack_dir)
            spy_load_scene.assert_not_called()
        assert "manifest" in str(exc_info.value).lower() or "id" in str(exc_info.value)

    def test_bad_scene_raises_scene_load_error(self, tmp_path: Path) -> None:
        bad_scene = _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
        pack_dir = _write_pack(tmp_path / "pack", scene=bad_scene)
        with pytest.raises(SceneLoadError) as exc_info:
            load_pack(pack_dir)
        assert "nonexistent_room" in str(exc_info.value)


class TestReattachPackManifest:
    def test_fills_manifest_when_sibling_file_exists(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, _ = load_pack(pack_dir)
        expected = world.pack_manifest
        world.pack_manifest = None

        reattach_pack_manifest(world)

        assert world.pack_manifest == expected

    def test_keeps_none_when_no_manifest_beside_scene(self, tmp_path: Path) -> None:
        scene_path = tmp_path / "data" / "scene.yaml"
        scene_path.parent.mkdir(parents=True)
        scene_path.write_text(_MINIMAL_SCENE, encoding="utf-8")
        world, _ = load_scene(scene_path)
        assert world.pack_manifest is None

        reattach_pack_manifest(world)

        assert world.pack_manifest is None

    def test_noop_when_scene_path_is_none(self) -> None:
        world = World()
        assert world.scene_path is None
        reattach_pack_manifest(world)
        assert world.pack_manifest is None


class TestSaveRestoreReattach:
    def test_manifest_survives_save_restore_via_reattach(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        before = world.pack_manifest
        assert before is not None

        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored = restore_world(save_dir)
        assert restored is not None
        world2, _ = restored
        assert world2.pack_manifest is None
        assert world2.scene_path == (pack_dir / "scene.yaml").resolve()

        reattach_pack_manifest(world2)
        assert world2.pack_manifest == before
