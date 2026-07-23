"""内容包外壳：manifest 身份、组合加载与 restore 后重挂。

``manifest.yaml`` 描述包身份（id / version / 可选创作者字段）；``scene.yaml``
描述世界内容。两者是独立校验阶段——``load_manifest`` 只读清单；``load_pack``
先校验清单再委托 ``scene_loader.load_scene`` 加载场景（不修改 ``load_scene``）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mud_engine.errors import PackManifestError
from mud_engine.scene_loader import load_scene
from mud_engine.world import EntityId, World

# ``PackManifestError`` 规范在 ``mud_engine.errors``；本模块再导出以保持
# ``from mud_engine.pack import PackManifestError`` 与公共入口同路径可读。
_KNOWN_FIELDS = frozenset({"id", "version", "creator", "title"})


@dataclass
class PackManifest:
    """内容包身份描述（运行时数据）。

    由 ``load_pack`` / ``reattach_pack_manifest`` 挂到 ``World``。
    """

    id: str
    version: str
    creator: str | None = None
    title: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


def load_manifest(pack_dir: Path) -> PackManifest:
    """读 ``pack_dir/manifest.yaml``，校验后返回 ``PackManifest``。

    文件缺失、YAML 语法错误、顶层非映射、``id``/``version`` 缺失或类型不对、
    可选字段 ``creator``/``title`` 类型不对时，统一抛 ``PackManifestError``。
    已知字段集之外的键原样收进 ``extra``（透传不丢）。
    """
    manifest_path = Path(pack_dir) / "manifest.yaml"
    data = _read_manifest_yaml(manifest_path)

    pack_id = _require_string(data, "id", manifest_path=manifest_path)
    version = _require_string(data, "version", manifest_path=manifest_path)
    creator = _optional_string(data, "creator", manifest_path=manifest_path)
    title = _optional_string(data, "title", manifest_path=manifest_path)
    extra = {key: value for key, value in data.items() if key not in _KNOWN_FIELDS}
    return PackManifest(
        id=pack_id,
        version=version,
        creator=creator,
        title=title,
        extra=extra,
    )


def load_pack(pack_dir: Path) -> tuple[World, EntityId]:
    """加载内容包：先校验 manifest，再委托 ``load_scene`` 加载 ``scene.yaml``。

    成功时把 ``PackManifest`` 赋给返回 ``world.pack_manifest``。manifest 校验
    失败抛 ``PackManifestError``（不会调用 ``load_scene``）；场景结构性错误
    原样抛出 ``SceneLoadError``。

    内容包轨允许场景顶层 ``includes``（见 ``scene_loader``）：路径相对
    ``scene.yaml`` 所在目录，且不得穿出包目录；被 include 文件仅贡献
    ``items``/``npcs`` 模板。
    """
    pack_dir = Path(pack_dir)
    manifest = load_manifest(pack_dir)
    world, player_id = load_scene(
        pack_dir / "scene.yaml",
        pack_track=True,
        pack_root=pack_dir,
    )
    world.pack_manifest = manifest
    return world, player_id


def reattach_pack_manifest(world: World) -> None:
    """从 ``world.scene_path`` 同级 ``manifest.yaml`` 重挂 ``pack_manifest``。

    幂等：可在任意时刻安全重复调用。``scene_path`` 为空、或同级无
    ``manifest.yaml`` 时静默保持 / 置为 ``None``，不抛异常（默认官方场景
    走这条路径）。有文件时重新 ``load_manifest`` 填回字段。
    """
    if world.scene_path is None:
        return
    manifest_path = world.scene_path.parent / "manifest.yaml"
    if not manifest_path.is_file():
        world.pack_manifest = None
        return
    world.pack_manifest = load_manifest(world.scene_path.parent)


def _read_manifest_yaml(manifest_path: Path) -> dict:
    pack_dir = manifest_path.parent
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


def _require_string(data: Mapping, key: str, *, manifest_path: Path) -> str:
    if key not in data:
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {manifest_path.parent}）缺少必需字段 '{key}'"
        )
    return _as_string(data[key], key=key, manifest_path=manifest_path)


def _optional_string(data: Mapping, key: str, *, manifest_path: Path) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    return _as_string(value, key=key, manifest_path=manifest_path)


def _as_string(value: object, *, key: str, manifest_path: Path) -> str:
    if not isinstance(value, str):
        raise PackManifestError(
            f"内容包清单 {manifest_path}（内容包 {manifest_path.parent}）的 '{key}' "
            f"应是字符串，实际是 {type(value).__name__}"
        )
    return value


__all__ = [
    "PackManifest",
    "load_manifest",
    "load_pack",
    "reattach_pack_manifest",
    "PackManifestError",
]
