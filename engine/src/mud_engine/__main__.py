"""真实终端入口：``python -m mud_engine``。"""

import sys

from mud_engine.cli import run_repl
from mud_engine.scene_loader import SceneLoadError
from mud_engine.scenes import build_world


def main() -> None:
    """构造 M1 空场景，启动真实终端的 CLI 主循环。

    场景数据加载失败（YAML 语法/结构性错误）时打印一句清晰的定位信息后退出，
    不抛裸 Python 异常堆栈（06 号票 acceptance 第 4 条）。
    """
    try:
        world, player_id = build_world()
    except SceneLoadError as exc:
        print(f"场景数据加载失败：{exc}", file=sys.stderr)
        sys.exit(1)
    run_repl(world, player_id)


if __name__ == "__main__":
    main()
