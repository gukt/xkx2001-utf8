"""内容包组合加载（M3-02）：``load_pack`` / ``reattach_pack_manifest`` seam。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mud_engine.components import Container, Engaged, Exits, Identity, Position
from mud_engine.errors import PackManifestError
from mud_engine.pack import load_manifest, load_pack, reattach_pack_manifest
from mud_engine.parsing import execute_line
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
    def test_attaches_manifest_equal_to_load_manifest(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        expected = load_manifest(pack_dir)
        world, _ = load_pack(pack_dir)
        assert world.pack_manifest == expected

    def test_scene_path_is_pack_scene_absolute(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, _ = load_pack(pack_dir)
        assert world.scene_path == (pack_dir / "scene.yaml").resolve()

    def test_player_starts_in_configured_room(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        room = world.require_component(player_id, Position).room
        assert world.require_component(room, Identity).name == "起始庭院"

    def test_exits_match_scene_graph(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        room = world.require_component(player_id, Position).room
        corridor = world.require_component(room, Exits).by_direction["north"].target
        assert world.require_component(corridor, Identity).name == "长廊"

    def test_entity_count_matches_direct_load_scene(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        scene_world, scene_player = load_scene(pack_dir / "scene.yaml")
        world, player_id = load_pack(pack_dir)
        assert player_id == scene_player
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
        assert "id" in str(exc_info.value)

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
    def test_restore_leaves_pack_manifest_none(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        world2, _ = restored
        assert world2.pack_manifest is None

    def test_restore_keeps_scene_path(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        world2, _ = restored
        assert world2.scene_path == (pack_dir / "scene.yaml").resolve()

    def test_reattach_after_restore_matches_pre_save(self, tmp_path: Path) -> None:
        pack_dir = _write_pack(tmp_path / "pack")
        world, player_id = load_pack(pack_dir)
        before = world.pack_manifest
        assert before is not None
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        world2, _ = restored
        reattach_pack_manifest(world2)
        assert world2.pack_manifest == before

    def test_engaged_and_pack_manifest_survive_save_restore(self, tmp_path: Path) -> None:
        """B3-4：pack 模式建立 Engaged 后 save→restore，交战与 manifest 均恢复。"""
        combat_scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      bandit: 1
skills:
  basic_fist:
    type: martial
    level_req: 0
    moves:
    - name: 直拳
      force: 20
      dodge: 0
      damage_type: blunt
      damage: 10
npcs:
  bandit:
    name: 山贼
    vitals:
      qi_current: 40
      qi_max: 40
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 10
      con: 10
      dex: 0
      int: 5
    skills:
      basic_fist:
        level: 1
        exp: 0
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
  attributes:
    str: 20
    con: 10
    dex: 0
    int: 10
  skills:
    basic_fist:
      level: 1
      exp: 0
"""
        pack_dir = _write_pack(tmp_path / "pack", scene=combat_scene)
        world, player_id = load_pack(pack_dir)
        before_manifest = world.pack_manifest
        assert before_manifest is not None
        execute_line(world, player_id, "attack 山贼")
        bandit = next(
            e
            for e in world.entities_with(Identity)
            if e != player_id and world.require_component(e, Identity).name == "山贼"
        )
        assert world.require_component(player_id, Engaged).opponent == bandit
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        world2, rid = restored
        assert world2.require_component(rid, Engaged).opponent == bandit
        assert world2.require_component(bandit, Engaged).opponent == rid
        reattach_pack_manifest(world2)
        assert world2.pack_manifest == before_manifest


# --- C13 includes（Polishing 票 11）：内容包轨 ---

_SCENE_WITH_INCLUDES = """
includes:
  - templates/shared.yaml
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    objects:
      shared_stone: 1
    exits: {}
player:
  name: 你
  start_room: start_yard
"""

_INCLUDE_TEMPLATES = """
items:
  shared_stone:
    name: 共享石
    short: 一块共享石
"""

_INCLUDE_WITH_TYPO = """
items:
  shared_stone:
    name: 共享石
    short: 一块共享石
    typo_field: oops
"""


class TestLoadPackIncludes:
    def test_merges_include_templates(self, tmp_path: Path) -> None:
        pack_dir = tmp_path / "pack"
        _write_pack(pack_dir, scene=_SCENE_WITH_INCLUDES)
        (pack_dir / "templates").mkdir()
        (pack_dir / "templates" / "shared.yaml").write_text(
            _INCLUDE_TEMPLATES, encoding="utf-8"
        )
        world, player_id = load_pack(pack_dir)
        assert world.pack_manifest is not None
        assert "shared_stone" in world.item_templates
        room = world.require_component(player_id, Position).room
        names = {
            world.require_component(e, Identity).name
            for e in world.require_component(room, Container).items
        }
        assert "共享石" in names

    def test_escape_outside_pack_fails(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside.yaml"
        outside.write_text(_INCLUDE_TEMPLATES, encoding="utf-8")
        pack_dir = tmp_path / "pack"
        scene = """
includes:
  - ../outside.yaml
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    exits: {}
player:
  name: 你
  start_room: start_yard
"""
        _write_pack(pack_dir, scene=scene)
        with pytest.raises(SceneLoadError) as exc_info:
            load_pack(pack_dir)
        msg = str(exc_info.value)
        assert "越界" in msg or "穿出" in msg

    def test_validate_strict_flags_include_unconsumed_fields(
        self, tmp_path: Path
    ) -> None:
        from mud_engine.__main__ import _main

        pack_dir = tmp_path / "pack"
        _write_pack(pack_dir, scene=_SCENE_WITH_INCLUDES)
        (pack_dir / "templates").mkdir()
        (pack_dir / "templates" / "shared.yaml").write_text(
            _INCLUDE_WITH_TYPO, encoding="utf-8"
        )
        assert _main(["--pack", str(pack_dir), "--validate"]) == 0
        assert _main(["--pack", str(pack_dir), "--validate", "--strict"]) != 0
