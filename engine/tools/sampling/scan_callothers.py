"""扫描全仓库 LPC .c 文件的 -> call_other 调用点。

阶段 0 任务 6 抽样校准实验阶段 A：枚举 68771 调用点 + 分类统计。
方法论见 ADR-0046 / docs/xkx-arch/17-抽样校准实验实施计划.md。

输出（engine/tools/sampling/output/）：
  - callothers.jsonl : 每行一个调用点（file/line/method/dynamic/subsystem）
  - summary.json     : 汇总统计（总量/子系统分布/方法名 top-N/文件分布）

用法::

    cd engine
    uv run python -m tools.sampling.scan_callothers
    # 或
    uv run python tools/sampling/scan_callothers.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

# 仓库根：engine/tools/sampling/ -> parents[3]
ROOT = Path(__file__).resolve().parents[3]

# 扫描的 LPC 顶层目录
LPC_DIRS = ("d", "cmds", "adm", "kungfu", "feature", "inherit", "clone", "u")

# call_other 正则：caller->method(  /  caller->"method"(
# caller 为标识符/)/]/.（含链式）；method 为标识符或字符串字面量（动态）
CALLOTHER_RE = re.compile(r'([\w\)\]\.])\s*->\s*(\w+|"([^"]*)")\s*\(')


def strip_strings_comments(text: str) -> str:
    """把字符串/注释内容替换为等长空格（保留换行），便于行号定位 + -> 扫描。

    覆盖：// 行注释、/* */ 块注释、"..." 字符串（含转义）、'...' 字符、
    @"..." raw string。# 预处理指令行一般不含 ->，不特殊处理。
    """
    out: list[str] = []
    i = 0
    n = len(text)
    state = "normal"
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "normal":
            if c == "/" and nxt == "/":
                out.append("  ")
                i += 2
                state = "line_comment"
            elif c == "/" and nxt == "*":
                out.append("  ")
                i += 2
                state = "block_comment"
            elif c == "@" and nxt == '"':
                out.append("  ")
                i += 2
                state = "raw_string"
            elif c == '"':
                out.append(" ")
                i += 1
                state = "string"
            elif c == "'":
                out.append(" ")
                i += 1
                state = "char"
            else:
                out.append(c)
                i += 1
        elif state == "string":
            if c == "\\" and nxt:
                out.append("  ")
                i += 2
            elif c == '"':
                out.append(" ")
                i += 1
                state = "normal"
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        elif state == "char":
            if c == "\\" and nxt:
                out.append("  ")
                i += 2
            elif c == "'":
                out.append(" ")
                i += 1
                state = "normal"
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        elif state == "line_comment":
            if c == "\n":
                out.append("\n")
                state = "normal"
            else:
                out.append(" ")
            i += 1
        elif state == "block_comment":
            if c == "*" and nxt == "/":
                out.append("  ")
                i += 2
                state = "normal"
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        elif state == "raw_string":
            if c == '"':
                out.append(" ")
                i += 1
                state = "normal"
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
    return "".join(out)


def scan_file(path: Path) -> list[dict]:
    """扫描单个 .c 文件，返回调用点记录列表。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = strip_strings_comments(text)
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    subsystem = rel.parts[0] if rel.parts else "other"
    records: list[dict] = []
    for lineno, line in enumerate(stripped.splitlines(), 1):
        for m in CALLOTHER_RE.finditer(line):
            if m.group(3) is not None:
                method = m.group(3)
                dynamic = True
            else:
                method = m.group(2)
                dynamic = False
            records.append(
                {
                    "file": str(rel),
                    "line": lineno,
                    "method": method,
                    "dynamic": dynamic,
                    "subsystem": subsystem,
                }
            )
    return records


def iter_lpc_files() -> list[Path]:
    """收集所有待扫描的 LPC .c 文件。"""
    files: list[Path] = []
    for top in LPC_DIRS:
        top_dir = ROOT / top
        if top_dir.is_dir():
            files.extend(top_dir.rglob("*.c"))
    return files


def summarize(records: list[dict]) -> dict:
    """汇总统计。"""
    total = len(records)
    subsystem_counts = Counter(r["subsystem"] for r in records)
    method_counts = Counter(r["method"] for r in records)
    file_counts = Counter(r["file"] for r in records)
    dynamic_count = sum(1 for r in records if r["dynamic"])
    return {
        "total": total,
        "dynamic_count": dynamic_count,
        "dynamic_ratio": dynamic_count / total if total else 0.0,
        "method_unique": len(method_counts),
        "files_with_calls": len(file_counts),
        "subsystem": dict(subsystem_counts.most_common()),
        "method_top30": dict(method_counts.most_common(30)),
        "top_files": dict(file_counts.most_common(20)),
    }


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)

    files = iter_lpc_files()
    print(f"扫描 {len(files)} 个 .c 文件...", file=sys.stderr)

    records: list[dict] = []
    for path in files:
        records.extend(scan_file(path))

    jsonl_path = out_dir / "callothers.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = summarize(records)
    summary_path = out_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    total = summary["total"]
    print(f"总计 {total} 个 -> 调用点")
    print(f"含调用的文件: {summary['files_with_calls']}")
    print(f"动态方法名: {summary['dynamic_count']} ({summary['dynamic_ratio']:.1%})")
    print(f"唯一方法名: {summary['method_unique']}")
    print("\n子系统分布:")
    for k, v in summary["subsystem"].items():
        print(f"  {k}: {v} ({v / total:.1%})")
    print("\n方法名 top 15:")
    for k, v in list(summary["method_top30"].items())[:15]:
        print(f"  {k}: {v}")
    print(f"\n输出: {jsonl_path}")
    print(f"      {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
