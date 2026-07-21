"""内容包外壳：manifest 身份与校验（与 ``scene_loader`` 分工独立）。

``manifest.yaml`` 描述包身份（id / version / 可选创作者字段）；``scene.yaml``
描述世界内容。两者是独立校验阶段——本模块只读清单，不碰场景数据或 ``World``。
场景内容仍由 ``scene_loader.load_scene`` 负责（M3 spec A1）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mud_engine.errors import PackManifestError

_KNOWN_FIELDS = frozenset({"id", "version", "creator", "title"})


@dataclass
class PackManifest:
    """内容包身份描述（运行时数据；本模块不负责挂到 ``World``）。"""

    id: str
    version: str
    creator: str | None = None
    title: str | None = None
    extra: dict = field(default_factory=dict)


def load_manifest(pack_dir: Path) -> PackManifest:
    """读 ``pack_dir/manifest.yaml``，校验后返回 ``PackManifest``。

    文件缺失、YAML 语法错误、顶层非映射、``id``/``version`` 缺失或类型不对、
    可选字段 ``creator``/``title`` 类型不对时，统一抛 ``PackManifestError``。
    已知字段集之外的键原样收进 ``extra``（透传不丢）。
    """
    pack_dir = Path(pack_dir)
    manifest_path = pack_dir / "manifest.yaml"
    data = _read_manifest_yaml(pack_dir, manifest_path)

    pack_id = _require_string(data, "id", pack_dir=pack_dir, manifest_path=manifest_path)
    version = _require_string(data, "version", pack_dir=pack_dir, manifest_path=manifest_path)
    creator = _optional_string(data, "creator", pack_dir=pack_dir, manifest_path=manifest_path)
    title = _optional_string(data, "title", pack_dir=pack_dir, manifest_path=manifest_path)
    extra = {key: value for key, value in data.items() if key not in _KNOWN_FIELDS}
    return PackManifest(
        id=pack_id,
        version=version,
        creator=creator,
        title=title,
        extra=extra,
    )


def _read_manifest_yaml(pack_dir: Path, manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        raise PackManifestError(f"内容包 {pack_dir} 缺少 manifest.yaml（期望路径 {manifest_path}）")
    try:
        with manifest_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise PackManifestError(
            f"无法解析内容包清单 {manifest_path}（内容包 {pack_dir}）：{exc}"
        ) from exc
    except OSError as exc:
        raise PackManifestError(
            f"无法读取内容包清单 {manifest_path}（内容包 {pack_dir}）：{exc}"
        ) from exc
    if not isinstance(data, Mapping):
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {pack_dir}）顶层应是映射，"
            f"实际是 {type(data).__name__}"
        )
    return dict(data)


def _require_string(data: Mapping, key: str, *, pack_dir: Path, manifest_path: Path) -> str:
    if key not in data:
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {pack_dir}）缺少必需字段 '{key}'"
        )
    value = data[key]
    if not isinstance(value, str):
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {pack_dir}）的 '{key}' "
            f"应是字符串，实际是 {type(value).__name__}"
        )
    return value


def _optional_string(data: Mapping, key: str, *, pack_dir: Path, manifest_path: Path) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {pack_dir}）的 '{key}' "
            f"应是字符串，实际是 {type(value).__name__}"
        )
    return value


__all__ = ["PackManifest", "load_manifest", "PackManifestError"]
