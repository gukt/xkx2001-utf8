"""C13 多文件路径引用 ``includes``（Polishing 票 11）。

接缝：S2 ``load_scene``（合并 items/npcs、路径/重复 id/嵌套失败）；
S3 见 ``test_load_pack.py`` 内容包轨扩展。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import Container, Identity, Position
from mud_engine.scene_loader import SceneLoadError, load_scene

_BASE_SCENE = """
includes:
  - templates/shared.yaml
rooms:
  yard:
    name: 院子
    long: 院子
    objects:
      shared_stone: 1
      shared_guard: 1
player:
  name: 你
  start_room: yard
"""

_SHARED_TEMPLATES = """
items:
  shared_stone:
    name: 共享石
    short: 一块共享石
npcs:
  shared_guard:
    name: 共享守卫
    short: 守卫
"""


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestSceneIncludesLoad:
    def test_merges_items_and_npcs_from_include(self, tmp_path: Path) -> None:
        scene = _write(tmp_path / "scene.yaml", _BASE_SCENE)
        _write(tmp_path / "templates" / "shared.yaml", _SHARED_TEMPLATES)

        world, player_id = load_scene(scene)
        room = world.require_component(player_id, Position).room
        floor_names = {
            world.require_component(e, Identity).name
            for e in world.require_component(room, Container).items
        }
        assert "共享石" in floor_names
        assert "shared_stone" in world.item_templates
        assert "shared_guard" in world.spawners
        assert any(
            world.require_component(e, Identity).name == "共享守卫"
            for e in world.entities_with(Identity)
        )

    def test_includes_not_in_extension_data(self, tmp_path: Path) -> None:
        scene = _write(tmp_path / "scene.yaml", _BASE_SCENE)
        _write(tmp_path / "templates" / "shared.yaml", _SHARED_TEMPLATES)

        world, _ = load_scene(scene)
        assert "includes" not in world.extension_data

    def test_main_file_templates_merge_with_includes(self, tmp_path: Path) -> None:
        scene_yaml = """
includes:
  - templates/shared.yaml
rooms:
  yard:
    name: 院子
    long: 院子
    objects:
      shared_stone: 1
      local_herb: 1
items:
  local_herb:
    name: 本地草药
npcs: {}
player:
  name: 你
  start_room: yard
"""
        scene = _write(tmp_path / "scene.yaml", scene_yaml)
        _write(
            tmp_path / "templates" / "shared.yaml",
            """
items:
  shared_stone:
    name: 共享石
npcs: {}
""",
        )
        world, player_id = load_scene(scene)
        room = world.require_component(player_id, Position).room
        names = {
            world.require_component(e, Identity).name
            for e in world.require_component(room, Container).items
        }
        assert names == {"共享石", "本地草药"}


class TestSceneIncludesFailures:
    def test_duplicate_item_id_across_files_fails(self, tmp_path: Path) -> None:
        scene_yaml = """
includes:
  - templates/shared.yaml
rooms:
  yard:
    name: 院子
    long: 院子
    objects:
      shared_stone: 1
items:
  shared_stone:
    name: 主文件石
player:
  name: 你
  start_room: yard
"""
        scene = _write(tmp_path / "scene.yaml", scene_yaml)
        _write(tmp_path / "templates" / "shared.yaml", _SHARED_TEMPLATES)
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "shared_stone" in msg
        assert "重复" in msg or "已定义" in msg

    def test_duplicate_id_across_two_includes_fails(self, tmp_path: Path) -> None:
        scene_yaml = """
includes:
  - templates/a.yaml
  - templates/b.yaml
rooms:
  yard:
    name: 院子
    long: 院子
    objects:
      shared_stone: 1
player:
  name: 你
  start_room: yard
"""
        scene = _write(tmp_path / "scene.yaml", scene_yaml)
        _write(
            tmp_path / "templates" / "a.yaml",
            "items:\n  shared_stone:\n    name: A石\n",
        )
        _write(
            tmp_path / "templates" / "b.yaml",
            "items:\n  shared_stone:\n    name: B石\n",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "shared_stone" in msg
        assert "重复" in msg or "已定义" in msg

    def test_path_escaping_parent_fails(self, tmp_path: Path) -> None:
        scene_dir = tmp_path / "scene_dir"
        outside = tmp_path / "outside.yaml"
        _write(outside, _SHARED_TEMPLATES)
        scene = _write(
            scene_dir / "scene.yaml",
            """
includes:
  - ../outside.yaml
rooms:
  yard:
    name: 院子
    long: 院子
player:
  name: 你
  start_room: yard
""",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "../outside.yaml" in msg or "outside.yaml" in msg
        assert "越界" in msg or "穿出" in msg or "不允许" in msg

    def test_missing_include_file_fails_with_path(self, tmp_path: Path) -> None:
        scene = _write(
            tmp_path / "scene.yaml",
            """
includes:
  - templates/missing.yaml
rooms:
  yard:
    name: 院子
    long: 院子
player:
  name: 你
  start_room: yard
""",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "templates/missing.yaml" in msg or "missing.yaml" in msg
        assert "不存在" in msg or "缺失" in msg or "找不到" in msg

    def test_nested_includes_fail(self, tmp_path: Path) -> None:
        scene = _write(tmp_path / "scene.yaml", _BASE_SCENE)
        _write(
            tmp_path / "templates" / "shared.yaml",
            """
includes:
  - deeper.yaml
items:
  shared_stone:
    name: 共享石
npcs:
  shared_guard:
    name: 共享守卫
""",
        )
        _write(tmp_path / "templates" / "deeper.yaml", "items: {}\n")
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "不允许嵌套" in msg

    def test_include_with_rooms_section_fails(self, tmp_path: Path) -> None:
        """被 include 文件不得贡献 rooms（仅 items/npcs）。"""
        scene = _write(tmp_path / "scene.yaml", _BASE_SCENE)
        _write(
            tmp_path / "templates" / "shared.yaml",
            """
rooms:
  other:
    name: 不该出现
    long: x
items:
  shared_stone:
    name: 共享石
npcs:
  shared_guard:
    name: 共享守卫
""",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(scene)
        msg = str(exc_info.value)
        assert "仅允许" in msg and "items" in msg and "npcs" in msg
        assert "rooms" in msg
