"""content_gen CLI（ADR-0036）：从 LPC 源生成层0 DSL v0 初稿。

用法::

    python -m xkx.content_gen generate --type npc \\
        --id xueshan/npc/gongcang --lpc kungfu/class/xueshan/gongcang.c \\
        --out tools/content_gen/output/xueshan_subset_v0

生成 v0 落盘到 ``--out`` 目录（measure_revision 兼容的 scene 文件名：npcs.yaml /
skills.yaml / quests.yaml / rooms.yaml / items.yaml）。人工修订 v0 -> v1 入 CPK 后，
用 ``tools/measure_revision.py`` 度量 semantic_ratio（kill criteria 5）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from xkx.content_gen.generate import (
    generate_item,
    generate_npc,
    generate_quest,
    generate_room,
    generate_skill,
)
from xkx.content_gen.llm_client import create_llm_client

# 类型 -> (生成函数, 落盘文件名)
_GENERATORS = {
    "npc": (generate_npc, "npcs.yaml"),
    "skill": (generate_skill, "skills.yaml"),
    "quest": (generate_quest, "quests.yaml"),
    "room": (generate_room, "rooms.yaml"),
    "item": (generate_item, "items.yaml"),
}


def _append_yaml(path: Path, entry: dict[str, Any]) -> None:
    """把单个 entry 追加到 YAML list 文件（measure_revision 兼容）。"""
    existing: list[Any] = []
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            existing = loaded
        elif isinstance(loaded, dict):
            existing = [loaded]
    existing.append(entry)
    path.write_text(
        yaml.safe_dump(existing, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xkx.content_gen", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="从 LPC 生成 v0 DSL")
    gen.add_argument("--type", required=True, choices=list(_GENERATORS))
    gen.add_argument("--id", required=True, help="目标 id（如 xueshan/npc/gongcang）")
    gen.add_argument("--lpc", required=True, help="LPC 源文件路径")
    gen.add_argument(
        "--out",
        required=True,
        help="v0 输出目录（measure_revision 兼容 scene 文件名）",
    )
    gen.add_argument("--model", default=None, help="覆盖默认 model")
    gen.add_argument(
        "--provider",
        default="volcano",
        choices=["volcano", "claude"],
        help="LLM provider（默认 volcano）",
    )

    args = parser.parse_args(argv)

    if args.cmd != "generate":
        return 2

    lpc_path = Path(args.lpc)
    if not lpc_path.is_file():
        print(f"LPC 源不存在: {lpc_path}", file=sys.stderr)
        return 2
    lpc_source = lpc_path.read_text(encoding="utf-8", errors="replace")

    gen_fn, out_name = _GENERATORS[args.type]
    client = create_llm_client(args.provider, model=args.model)
    print(f"[content_gen] 生成 {args.type} id={args.id} (provider={args.provider}, "
          f"model={client.model}) ...")
    entry = gen_fn(client, lpc_source, args.id)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    _append_yaml(out_path, entry)
    print(f"[content_gen] v0 追加到 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
