"""CPK 加载器（M3-2，ADR-0031 决策 4）。

读 CPK 目录（``manifest.yaml`` + 资产 YAML）-> ``(CpkManifest, IR, rules)``。复用
[layer0](layer0.py) / [layer1](layer1.py) 加载 + [ir.compile_scene](ir.py)。manifest
校验：``entry_points.main_scene`` 引用完整 + ``theme`` 已注册（若传 registry）。

**dsl 不依赖 runtime**（避免循环：runtime.world 已 import dsl）。``registry`` 参数
类型用 ``TYPE_CHECKING`` 注解，运行时不 import runtime。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 4
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from xkx.dsl.cpk import CpkManifest
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items, load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules

if TYPE_CHECKING:
    from xkx.runtime.theme_registry import ThemeRegistry


def load_cpk(
    path: Path | str,
    *,
    registry: ThemeRegistry | None = None,
) -> tuple[CpkManifest, dict, list]:
    """读 CPK 目录 -> ``(manifest, IR, rules)``。

    流程（ADR-0031 决策 4）：

    1. 读 ``manifest.yaml`` -> ``CpkManifest``（pydantic 校验）
    2. 读资产 YAML（rooms / npcs / quests / items / rules，缺失跳过）-> 层0 / 层1 Def
    3. ``compile_scene`` -> IR（层0，复用 [ir.py](ir.py)）
    4. manifest 校验：``entry_points.main_scene`` 在 IR rooms / ``theme`` 已注册
       （若 registry 传入）/ ``dependencies`` 已加载（M3 线性空）

    Args:
        path: CPK 目录路径（含 ``manifest.yaml`` + 资产 YAML）。
        registry: 可选 ThemeRegistry，传入时校验 ``manifest.theme`` 已注册。

    Returns:
        ``(manifest, ir, rules)``：CpkManifest + 层0 IR dict + 层1 EventRule 列表。
        ``rules`` 与 IR 分离（03 §二四层 DSL：层0 IR 是唯一真相源，层1 规则单独
        求值）。

    Raises:
        FileNotFoundError: ``manifest.yaml`` 缺失。
        pydantic.ValidationError: manifest schema 校验失败。
        ValueError: ``entry_points.main_scene`` 不在 IR rooms / ``theme`` 未注册。
    """
    cpk_dir = Path(path)
    manifest_path = cpk_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"CPK manifest 缺失: {manifest_path}")

    manifest = CpkManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )

    # 读资产 YAML（缺失跳过：非每个 CPK 都有 quests/items，但 rooms/npcs/rules 必有）
    rooms = _load_optional(cpk_dir / "rooms.yaml", load_rooms)
    npcs = _load_optional(cpk_dir / "npcs.yaml", load_npcs)
    quests = _load_optional(cpk_dir / "quests.yaml", load_quests)
    items = _load_optional(cpk_dir / "items.yaml", load_items)
    rules = _load_optional(cpk_dir / "rules.yaml", load_rules)

    ir = compile_scene(rooms, npcs, quests, items)

    _validate_manifest(manifest, ir, registry)

    return manifest, ir, rules


def _load_optional(path: Path, loader):
    """资产 YAML 缺失时返回空列表，存在时加载。"""
    if not path.exists():
        return []
    return loader(path)


def _validate_manifest(
    manifest: CpkManifest, ir: dict, registry: ThemeRegistry | None
) -> None:
    """manifest 校验：entry_points 引用完整 + theme 已注册。"""
    # entry_points.main_scene 在 IR rooms
    main_scene = manifest.entry_points.get("main_scene")
    if main_scene is not None:
        room_ids = {r["id"] for r in ir["rooms"]}
        if main_scene not in room_ids:
            raise ValueError(
                f"CPK {manifest.cpk_id} entry_points.main_scene "
                f"'{main_scene}' 不在 rooms: {sorted(room_ids)}"
            )

    # theme 已注册（若 registry 传入）
    if registry is not None and manifest.theme not in registry:
        raise ValueError(
            f"CPK {manifest.cpk_id} theme '{manifest.theme}' 未注册 "
            f"(已注册: {registry.theme_ids()})"
        )


__all__ = ["load_cpk"]
