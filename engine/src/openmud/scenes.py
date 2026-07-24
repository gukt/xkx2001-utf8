"""M1 默认场景入口：从 YAML 文件加载场景数据构造 ``(world, player_id)``。

场景数据（房间/物品/静态展示型 NPC）与命令调度/ECS 存储代码分离--这是给未来
题材包"只提供数据、不触碰引擎实现"留的边界（M1 spec「场景数据与引擎能力的
边界」）。06 号票起，数据从内嵌 Python 元组迁移到 YAML 文件（M1 内部过渡
格式，M3 可能整体替换），加载逻辑在 ``scene_loader``，本模块只负责"默认场景
是哪份文件 + 调加载器"，不保留任何内嵌场景数据。
"""

from __future__ import annotations

from pathlib import Path

from openmud.scene_loader import load_scene
from openmud.world import EntityId, World

# 默认场景文件：engine/data/m1_default_scene.yaml。从本文件（src/openmud/）
# 往上三级回到 engine/ 根再进 data/。M1 始终从源码运行（uv run），路径解析稳定；
# 这份 YAML 不是正式 UGC DSL（见 scene_loader 模块文档）。
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_SCENE_PATH = _DATA_DIR / "m1_default_scene.yaml"
# M2 官方轻量武侠题材包（Wave 4+；六分区累加于同一文件，见 room-keys.md）。
MVP_SCENE_PATH = _DATA_DIR / "m2_mvp_scene.yaml"
# Pre-M4 官方机制切片（房间钩子 / 星宿同构机关；官方单文件轨道，无 manifest）。
XINGXIU_MECHANICS_PATH = _DATA_DIR / "xingxiu_mechanics.yaml"


def build_world(scene_path: Path | None = None) -> tuple[World, EntityId]:
    """构造 M1 默认空场景 world，返回 ``(world, 玩家实体 id)``。

    传入 scene_path 加载指定场景文件（测试用）；缺省加载 DEFAULT_SCENE_PATH。
    场景文件的结构性错误会抛 ``SceneLoadError``（见 scene_loader）。
    """
    return load_scene(scene_path if scene_path is not None else DEFAULT_SCENE_PATH)


def load_mvp_scene() -> tuple[World, EntityId]:
    """加载 M2 MVP 武侠题材包场景（``m2_mvp_scene.yaml``）。"""
    return load_scene(MVP_SCENE_PATH)


def load_xingxiu_mechanics() -> tuple[World, EntityId]:
    """加载 Pre-M4 官方机制切片（``xingxiu_mechanics.yaml``）。"""
    return load_scene(XINGXIU_MECHANICS_PATH)
