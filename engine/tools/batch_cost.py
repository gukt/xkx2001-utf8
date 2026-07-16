"""AI 迁移批次成本记录工具。

[ADR-0056](../../docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 5
执行回路：从 Claude Code session transcript 自动采集 token（避免 agent 自报不准，
重蹈 ADR-0056 弃用工时估算的"估算而非实测"覆辙），从首/末 timestamp 算运行时间。
记录到 [docs/batch-cost.md](../../docs/batch-cost.md) 台账。

用法::

    python tools/batch_cost.py tokens                  # 采集最新 session
    python tools/batch_cost.py tokens <transcript.jsonl>
    python tools/batch_cost.py record --batch <名> --adr <ADR-NNNN> [--tests N] [--note ...]

来源：[strategy-review](../../docs/strategy-review/04-对抗评审记录与综合裁决.md) 提案 8。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = REPO_ROOT / "docs" / "batch-cost.md"


def _project_dir() -> Path:
    """Claude Code project 目录（仓库根路径转 slug）。"""
    slug = str(REPO_ROOT).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def _latest_transcript() -> Path | None:
    files = sorted(_project_dir().glob("*.jsonl"), key=os.path.getmtime)
    return files[-1] if files else None


def _collect(transcript: Path) -> dict:
    tot = dict(input=0, output=0, cache_read=0, cache_creation=0)
    n_asst = 0
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    session_id = None
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = r.get("timestamp")
        if ts:
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if first_ts is None:
                    first_ts = d
                last_ts = d
            except ValueError:
                pass
        if not session_id:
            session_id = r.get("sessionId")
        msg = r.get("message")
        if isinstance(msg, dict) and r.get("type") == "assistant" and "usage" in msg:
            u = msg["usage"]
            n_asst += 1
            tot["input"] += u.get("input_tokens", 0)
            tot["output"] += u.get("output_tokens", 0)
            tot["cache_read"] += u.get("cache_read_input_tokens", 0)
            tot["cache_creation"] += u.get("cache_creation_input_tokens", 0)
    runtime_min = (
        (last_ts - first_ts).total_seconds() / 60 if first_ts and last_ts else 0.0
    )
    total = sum(tot.values())
    return {
        "session_id": session_id,
        "n_asst": n_asst,
        "input": tot["input"],
        "output": tot["output"],
        "cache_read": tot["cache_read"],
        "cache_creation": tot["cache_creation"],
        "total": total,
        "runtime_min": round(runtime_min, 1),
        "date": (
            first_ts.astimezone().strftime("%Y-%m-%d") if first_ts else "unknown"
        ),
    }


def _fmt(c: dict) -> str:
    sid = c["session_id"][:8] if c["session_id"] else "?"
    return (
        f"session={sid} date={c['date']} runtime={c['runtime_min']}min "
        f"asst={c['n_asst']} in={c['input']} out={c['output']} "
        f"cache_read={c['cache_read']} cache_create={c['cache_creation']} "
        f"total={c['total']}"
    )


def _resolve_transcript(path: str | None) -> Path | None:
    return Path(path) if path else _latest_transcript()


def cmd_tokens(args: argparse.Namespace) -> int:
    t = _resolve_transcript(args.transcript)
    if not t or not t.exists():
        print("未找到 transcript", file=sys.stderr)
        return 1
    print(_fmt(_collect(t)))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    t = _resolve_transcript(args.transcript)
    if not t or not t.exists():
        print("未找到 transcript", file=sys.stderr)
        return 1
    c = _collect(t)
    row = (
        f"| {args.batch} | {c['date']} | {args.adr} | {c['input']} | "
        f"{c['output']} | {c['cache_read']} | {c['total']} | "
        f"{c['runtime_min']} | {args.tests or ''} | {args.note or ''} |"
    )
    text = LEDGER.read_text(encoding="utf-8") if LEDGER.exists() else ""
    if "|---" not in text:
        print("台账表头缺失，先建 docs/batch-cost.md", file=sys.stderr)
        return 1
    lines = text.rstrip().splitlines()
    insert_at = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("|"):
            insert_at = i + 1
            break
    lines.insert(insert_at, row)
    LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已记录: {row}")
    print(f"采集自 {t.name}（session 进行中数值会增长，收尾重跑更新）")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AI 迁移批次成本记录工具")
    sub = p.add_subparsers(dest="cmd", required=True)
    pt = sub.add_parser("tokens", help="采集 transcript 的 token+运行时间")
    pt.add_argument("transcript", nargs="?", default=None)
    pt.set_defaults(func=cmd_tokens)
    pr = sub.add_parser("record", help="采集并追加一条记录到台账")
    pr.add_argument("--batch", required=True)
    pr.add_argument("--adr", required=True)
    pr.add_argument("--transcript", default=None)
    pr.add_argument("--tests", default=None)
    pr.add_argument("--note", default=None)
    pr.set_defaults(func=cmd_record)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
