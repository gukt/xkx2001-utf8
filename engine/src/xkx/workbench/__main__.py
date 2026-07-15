"""评审工作台启动入口：``python -m xkx.workbench``。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover - 无 workbench extra 时占位
    uvicorn = None  # type: ignore[assignment]
    _UVICORN_ERROR = exc
else:
    _UVICORN_ERROR = None

from xkx.workbench.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xkx.workbench", description="M2-2 评审工作台")
    parser.add_argument(
        "--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）"
    )
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument(
        "--output-dir",
        default="tools/content_gen/output",
        help="Orchestrator 输出根目录（默认 tools/content_gen/output）",
    )
    parser.add_argument(
        "--static-dir",
        default=None,
        help="自定义静态文件目录（默认使用内置 static/）",
    )
    args = parser.parse_args(argv)

    if uvicorn is None:
        print(f"uvicorn 未安装：{_UVICORN_ERROR}", file=sys.stderr)
        return 2

    static_dir = Path(args.static_dir) if args.static_dir else None
    app = create_app(args.output_dir, static_dir=static_dir)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
