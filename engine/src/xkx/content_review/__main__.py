"""CLI：内容审核 pipeline MVP（M3-3，ADR-0033）。

用法::

    # 预检 CPK + 落 _review.json + 打印摘要
    python -m xkx.content_review scenes/xueshan_micro

    # 预检后同步 manifest.review_status（会丢 YAML 注释，正式后置 ruamel）
    python -m xkx.content_review scenes/xueshan_micro --sync-manifest

    # 打印专家审核 checklist 模板
    python -m xkx.content_review --checklist

退出码：``passed``（无 block）= 0，``rejected``（有 block / license 不合规）= 1。
``needs_review`` 不阻塞（passed=True，检测非清洗）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from xkx.content_review.checklist import render_checklist_template
from xkx.content_review.precheck import precheck_cpk
from xkx.content_review.review_status import (
    derive_status,
    sync_manifest_status,
    write_review_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m xkx.content_review",
        description="内容审核 pipeline MVP（预检 + 审核状态 + checklist）",
    )
    parser.add_argument(
        "cpk_dir",
        nargs="?",
        help="CPK 目录（含 manifest.yaml + 资产 YAML）",
    )
    parser.add_argument(
        "--sync-manifest",
        action="store_true",
        help="预检后同步 manifest.review_status（丢 YAML 注释，正式后置 ruamel）",
    )
    parser.add_argument(
        "--checklist",
        action="store_true",
        help="打印专家审核 checklist 模板并退出",
    )
    args = parser.parse_args(argv)

    if args.checklist:
        print(render_checklist_template())
        return 0

    if not args.cpk_dir:
        parser.error("预检需要 cpk_dir（或用 --checklist 打印模板）")

    cpk_dir = Path(args.cpk_dir)
    report = precheck_cpk(cpk_dir)
    out_path = write_review_report(cpk_dir, report)
    status = derive_status(report)

    print(report.summary())
    print(f"derived_status: {status.value}")
    print(f"report: {out_path}")

    if args.sync_manifest:
        synced = sync_manifest_status(cpk_dir)
        if synced is not None:
            print(f"manifest review_status synced: {synced.value}")

    # passed（无 block）= 0；rejected（block / license 不合规）= 1
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
