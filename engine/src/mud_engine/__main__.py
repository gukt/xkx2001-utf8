"""真实终端入口：``python -m mud_engine``。"""

from mud_engine.cli import run_repl
from mud_engine.scenes import build_world


def main() -> None:
    """构造 M1 空场景，启动真实终端的 CLI 主循环。"""
    world, player = build_world()
    run_repl(world, player)


if __name__ == "__main__":
    main()
