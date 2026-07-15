"""Orchestrator CLI：M2 创作闭环命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from xkx.content_gen.llm_client import create_llm_client
from xkx.content_review.checklist import render_checklist_template
from xkx.orchestrator.loop import Orchestrator
from xkx.orchestrator.rag import load_bible
from xkx.orchestrator.state_machine import Job, JobState


def _load_job_state(output_dir: Path) -> dict:
    path = output_dir / "job_state.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到 job_state: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _print_summary(job: Job) -> None:
    print(f"job_id: {job.id}")
    print(f"state: {job.state.value}")
    print(f"review_status: {job.review_status}")
    print(f"revision_count: {job.revision_count}/{job.max_revisions}")
    print(f"token_estimate: {job.token_estimate}")
    print(f"output_dir: {job.output_dir}")
    if job.issues:
        print("final_issues:")
        for issue in job.issues:
            print(f"  - {issue}")


def cmd_create(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从意图 YAML 跑创作闭环")
    parser.add_argument("--intent", required=True, help="意图 YAML 路径")
    parser.add_argument("--out", required=True, help="CPK 输出根目录")
    parser.add_argument(
        "--bible", required=True, help="世界圣经 YAML 路径"
    )
    parser.add_argument(
        "--max-revisions", type=int, default=3, help="最大自动修订轮次"
    )
    parser.add_argument(
        "--skip-l4", action="store_true", help="跳过 measure L4 可跑通性校验"
    )
    parser.add_argument(
        "--provider",
        default="volcano",
        choices=["volcano", "claude"],
        help="LLM provider（默认 volcano）",
    )
    args = parser.parse_args(argv)

    bible = load_bible(args.bible)
    llm = create_llm_client(args.provider)
    orchestrator = Orchestrator(
        llm=llm,
        bible=bible,
        output_dir=args.out,
        max_revisions=args.max_revisions,
        skip_l4=args.skip_l4,
    )
    job = orchestrator.create_job(args.intent)
    orchestrator.run(job)
    _print_summary(job)
    return 0 if job.state == JobState.APPROVED else 1


def cmd_status(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="查看 Job 状态")
    parser.add_argument("dir", help="CPK 输出目录")
    args = parser.parse_args(argv)

    state = _load_job_state(Path(args.dir))
    print(yaml.safe_dump(state, allow_unicode=True, sort_keys=False))
    return 0


def cmd_continue(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="断点续跑创作闭环")
    parser.add_argument("dir", help="CPK 输出目录")
    parser.add_argument(
        "--bible", required=True, help="世界圣经 YAML 路径"
    )
    parser.add_argument(
        "--skip-l4", action="store_true", help="跳过 measure L4"
    )
    parser.add_argument(
        "--provider",
        default="volcano",
        choices=["volcano", "claude"],
        help="LLM provider（默认 volcano）",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.dir)
    state = _load_job_state(output_dir)
    if state["state"] == JobState.APPROVED.value:
        print("Job 已通过，无需续跑")
        return 0
    if state["state"] == JobState.REJECTED.value:
        print("Job 已拒绝，如需重新跑请用 create")
        return 1

    bible = load_bible(args.bible)
    llm = create_llm_client(args.provider)
    orchestrator = Orchestrator(
        llm=llm,
        bible=bible,
        output_dir=output_dir.parent,
        max_revisions=3,
        skip_l4=args.skip_l4,
    )
    intent = yaml.safe_load(
        (output_dir / "manifest.yaml").read_text(encoding="utf-8")
    )

    job = Job(
        intent=intent,
        bible=bible,
        output_dir=output_dir,
        max_revisions=3,
    )
    # 简单续跑：从当前状态继续跑完整 run 循环
    orchestrator.run(job)
    _print_summary(job)
    return 0 if job.state == JobState.APPROVED else 1


def cmd_review(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI 评审工作台预览")
    parser.add_argument("dir", help="CPK 输出目录")
    args = parser.parse_args(argv)

    cpk_dir = Path(args.dir)
    print(f"# CPK: {cpk_dir}")
    print("")

    # world-graph 摘要
    manifest_data = yaml.safe_load(
        (cpk_dir / "manifest.yaml").read_text(encoding="utf-8")
    )
    entry = manifest_data.get("entry_points", {}).get("main_scene", "")
    print(f"入口: {entry}")
    rooms = yaml.safe_load(
        (cpk_dir / "rooms.yaml").read_text(encoding="utf-8")
    ) if (cpk_dir / "rooms.yaml").exists() else []
    print(f"房间数: {len(rooms)}")
    if rooms:
        print("房间列表:")
        for r in rooms:
            exits = ", ".join(r.get("exits", {}).keys())
            print(f"  - {r.get('id')}: exits=[{exits}]")
    print("")

    # revision trace
    trace_path = cpk_dir / "revision_trace.json"
    if trace_path.exists():
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        print(f"修订轮次: {trace.get('revision_count', 0)}")
        print(f"token 估算: {trace.get('token_estimate', 0)}")
        final_issues = trace.get("final_issues", [])
        if final_issues:
            print("最终 issue:")
            for issue in final_issues:
                print(f"  - {issue}")
        else:
            print("最终 issue: 无")
    print("")

    # _review.json
    review_path = cpk_dir / "_review.json"
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        print(f"预检状态: {review.get('derived_status')}")
        findings = review.get("report", {}).get("findings", [])
        if findings:
            print(f"预检发现 ({len(findings)}):")
            for f in findings:
                print(
                    f"  - [{f.get('severity')}] {f.get('file')}:{f.get('field_path')} "
                    f"{f.get('rule_id')}({f.get('matched_term')})"
                )
        else:
            print("预检发现: 无")
    print("")

    # checklist
    print(render_checklist_template())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xkx.orchestrator")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create", help="跑创作闭环").set_defaults(func=cmd_create)
    sub.add_parser("status", help="查看 Job 状态").set_defaults(func=cmd_status)
    sub.add_parser("continue", help="断点续跑").set_defaults(func=cmd_continue)
    sub.add_parser("review", help="CLI 评审工作台").set_defaults(func=cmd_review)

    args = parser.parse_args(argv)
    return args.func()


if __name__ == "__main__":
    sys.exit(main())
