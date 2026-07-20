"""真实终端入口：``python -m mud_engine``。

启动时若存在已发布的存档则从存档恢复（崩溃恢复级耐久，见 save.py），否则加载
fresh 场景；构造 ``TickLoop`` 接入 CLI，使普通游玩周期性存档、``quit`` 立即存档
（05 号票验收 #1/#2）。
"""

import sys
from pathlib import Path

from mud_engine.ai import attach_ai_system
from mud_engine.cli import run_repl
from mud_engine.nature import attach_nature
from mud_engine.save import has_save, restore_world, save_world
from mud_engine.scene_loader import SceneLoadError
from mud_engine.scenes import DEFAULT_SCENE_PATH, build_world
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World

# 默认存档目录：engine/save/（与场景数据同级，回 engine/ 根再进 save/）。
# 从源码运行（uv run）时路径稳定；首次运行无存档走 fresh scene。
DEFAULT_SAVE_DIR = DEFAULT_SCENE_PATH.parent.parent / "save"


def main() -> None:
    save_dir = DEFAULT_SAVE_DIR
    try:
        world, player_id = _load_or_restore(save_dir)
    except SceneLoadError as exc:
        print(f"场景数据加载失败：{exc}", file=sys.stderr)
        sys.exit(1)
    tick_loop = TickLoop(lambda: save_world(world, player_id, save_dir), world=world)
    run_repl(world, player_id, tick_loop=tick_loop)


def _load_or_restore(save_dir: Path) -> tuple[World, EntityId]:
    """有已发布存档则从存档恢复，否则加载 fresh 场景。

    存档存在但恢复后无玩家（玩家条目损坏）时 ``restore_world`` 返回 None，
    回退到 fresh scene--进程仍能启动（05 验收 #5 "不拒绝启动"）。
    """
    if has_save(save_dir):
        restored = restore_world(save_dir)
        if restored is not None:
            world, player_id = restored
            # Nature 不进存档：restore 后按时钟重新挂载默认相位（场景 YAML 的
            # nature 段只在 load_scene 路径可读；崩溃恢复用默认四相即可）。
            attach_nature(world)
            # AI 订阅者不进存档：restore 后重新挂 on_tick（幂等）。
            attach_ai_system(world)
            return world, player_id
    return build_world()


if __name__ == "__main__":
    main()
