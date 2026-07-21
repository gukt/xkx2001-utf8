"""真实终端入口：``python -m mud_engine``。

启动时若存在已发布的存档则从存档恢复（崩溃恢复级耐久，见 save.py），否则加载
fresh 场景；构造 ``TickLoop`` 接入 CLI，使普通游玩周期性存档、``quit`` 立即存档
（05 号票验收 #1/#2）。

M3-03：``--pack <目录>`` 指向包外内容包；``--validate``（须搭配 ``--pack``）只校验
不进入 REPL。逻辑在 ``_main(argv) -> int``，``main()`` 只做 ``sys.exit`` 胶水。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mud_engine.cli import run_repl
from mud_engine.errors import PackManifestError
from mud_engine.pack import load_pack, reattach_pack_manifest
from mud_engine.runtime import wire_runtime
from mud_engine.save import has_save, restore_world, save_world
from mud_engine.scene_loader import SceneLoadError
from mud_engine.scenes import DEFAULT_SCENE_PATH, build_world
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World

# 默认存档目录：engine/save/（与场景数据同级，回 engine/ 根再进 save/）。
# 从源码运行（uv run）时路径稳定；首次运行无存档走 fresh scene。
DEFAULT_SAVE_DIR = DEFAULT_SCENE_PATH.parent.parent / "save"


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


def _main(argv: list[str]) -> int:
    """解析参数 → 选择分支 → 返回退出码（不直接 ``sys.exit``）。"""
    args = _parse_args(argv)
    if args.validate and args.pack is None:
        print("错误：--validate 须搭配 --pack", file=sys.stderr)
        return 2

    if args.pack is not None:
        pack_dir = Path(args.pack)
        if not pack_dir.is_dir():
            print(f"内容包目录不存在或不是目录：{pack_dir}", file=sys.stderr)
            return 1
        if args.validate:
            return _validate_pack(pack_dir)
        return _run_pack(pack_dir)

    return _run_default()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mud_engine")
    parser.add_argument(
        "--pack",
        metavar="PATH",
        type=Path,
        default=None,
        help="加载指定内容包目录（含 manifest.yaml 与 scene.yaml）",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="只校验内容包，不进入 REPL（须搭配 --pack）",
    )
    return parser.parse_args(argv)


def _run_default() -> int:
    save_dir = DEFAULT_SAVE_DIR
    try:
        world, player_id = _load_or_restore_default(save_dir)
    except SceneLoadError as exc:
        # 默认路径文案保持开工前不变（M3-03 验收：无 --pack 零改动）。
        print(f"场景数据加载失败：{exc}", file=sys.stderr)
        return 1
    _enter_repl(world, player_id, save_dir)
    return 0


def _run_pack(pack_dir: Path) -> int:
    save_dir = pack_dir / "save"
    try:
        world, player_id = _load_or_restore_pack(pack_dir, save_dir)
    except (PackManifestError, SceneLoadError) as exc:
        print(_format_pack_or_scene_error(exc), file=sys.stderr)
        return 1
    _enter_repl(world, player_id, save_dir)
    return 0


def _validate_pack(pack_dir: Path) -> int:
    try:
        world, _player_id = load_pack(pack_dir)
    except (PackManifestError, SceneLoadError) as exc:
        print(_format_pack_or_scene_error(exc), file=sys.stderr)
        return 1
    manifest = world.pack_manifest
    assert manifest is not None  # load_pack 成功必挂
    room_count = len(world.room_ids)
    print(
        f"校验通过：{manifest.id} v{manifest.version}，{room_count} 个房间",
        file=sys.stdout,
    )
    return 0


def _enter_repl(world: World, player_id: EntityId, save_dir: Path) -> None:
    tick_loop = TickLoop(lambda: save_world(world, player_id, save_dir), world=world)
    run_repl(world, player_id, tick_loop=tick_loop)


def _format_pack_or_scene_error(exc: BaseException) -> str:
    if isinstance(exc, PackManifestError):
        return f"包清单错误：{exc}"
    return f"场景内容错误：{exc}"


def _load_or_restore_default(save_dir: Path) -> tuple[World, EntityId]:
    """有已发布存档则从存档恢复，否则加载 fresh 默认场景。

    存档存在但恢复后无玩家（玩家条目损坏）时 ``restore_world`` 返回 None，
    回退到 fresh scene--进程仍能启动（05 验收 #5 "不拒绝启动"）。
    """
    if has_save(save_dir):
        restored = restore_world(save_dir)
        if restored is not None:
            world, player_id = restored
            wire_runtime(world, world.scene_path or DEFAULT_SCENE_PATH)
            return world, player_id
    return build_world()


def _load_or_restore_pack(pack_dir: Path, save_dir: Path) -> tuple[World, EntityId]:
    """``--pack``：有存档则 restore + 重挂（含 ``reattach_pack_manifest``），否则 ``load_pack``。"""
    if has_save(save_dir):
        restored = restore_world(save_dir)
        if restored is not None:
            world, player_id = restored
            wire_runtime(world, world.scene_path or DEFAULT_SCENE_PATH)
            reattach_pack_manifest(world)
            return world, player_id
    return load_pack(pack_dir)


if __name__ == "__main__":
    main()
