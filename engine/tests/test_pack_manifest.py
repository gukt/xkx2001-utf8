"""内容包 manifest 纯函数加载（M3-01）：``load_manifest`` seam。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.errors import PackManifestError
from mud_engine.pack import PackManifest, load_manifest


def _write_manifest(pack_dir: Path, text: str) -> Path:
    pack_dir.mkdir(parents=True, exist_ok=True)
    path = pack_dir / "manifest.yaml"
    path.write_text(text, encoding="utf-8")
    return pack_dir


class TestLoadManifestSuccess:
    def test_full_known_fields(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: derelict-outpost
version: "0.1.0"
creator: alice
title: 废弃探测站
""",
        )
        manifest = load_manifest(pack_dir)
        assert isinstance(manifest, PackManifest)
        assert manifest.id == "derelict-outpost"
        assert manifest.version == "0.1.0"
        assert manifest.creator == "alice"
        assert manifest.title == "废弃探测站"
        assert manifest.extra == {}

    def test_only_required_fields(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: minimal
version: "1"
""",
        )
        manifest = load_manifest(pack_dir)
        assert manifest.id == "minimal"
        assert manifest.version == "1"
        assert manifest.creator is None
        assert manifest.title is None
        assert manifest.extra == {}

    def test_creator_only_optional(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: with-creator
version: "2.0"
creator: bob
""",
        )
        manifest = load_manifest(pack_dir)
        assert manifest.creator == "bob"
        assert manifest.title is None

    def test_title_only_optional(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: with-title
version: "2.0"
title: 仅有标题
""",
        )
        manifest = load_manifest(pack_dir)
        assert manifest.creator is None
        assert manifest.title == "仅有标题"

    def test_unknown_fields_go_to_extra(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: tagged
version: "0.2"
tags:
  - scifi
  - demo
cover: art/cover.png
""",
        )
        manifest = load_manifest(pack_dir)
        assert manifest.id == "tagged"
        assert manifest.version == "0.2"
        assert manifest.creator is None
        assert manifest.title is None
        assert manifest.extra == {"tags": ["scifi", "demo"], "cover": "art/cover.png"}

    def test_extra_default_not_shared_across_instances(self) -> None:
        a = PackManifest(id="a", version="1")
        b = PackManifest(id="b", version="1")
        a.extra["x"] = 1
        assert b.extra == {}


class TestLoadManifestErrors:
    def test_missing_manifest_file(self, tmp_path: Path) -> None:
        pack_dir = tmp_path / "empty-pack"
        pack_dir.mkdir()
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "manifest.yaml" in msg

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(tmp_path / "pack", 'id: "未闭合')
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg

    def test_top_level_not_mapping(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
- just
- a
- list
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "映射" in msg

    def test_missing_id(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
version: "1.0"
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "id" in msg

    def test_missing_version(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: no-version
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "version" in msg

    def test_id_wrong_type(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: 42
version: "1.0"
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "id" in msg
        assert "字符串" in msg

    def test_version_wrong_type(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: ok
version: 1
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "version" in msg
        assert "字符串" in msg

    def test_creator_wrong_type(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: ok
version: "1"
creator: 123
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "creator" in msg
        assert "字符串" in msg

    def test_title_wrong_type(self, tmp_path: Path) -> None:
        pack_dir = _write_manifest(
            tmp_path / "pack",
            """
id: ok
version: "1"
title: ["not", "a", "string"]
""",
        )
        with pytest.raises(PackManifestError) as exc_info:
            load_manifest(pack_dir)
        msg = str(exc_info.value)
        assert str(pack_dir) in msg
        assert "title" in msg
        assert "字符串" in msg
