#!/usr/bin/env python3
"""汇总子系统调研 skill 的 benchmark 结果。

用法：
    python3 aggregate_benchmark.py <workspace/iteration-N> --skill-name <name>
"""

import argparse
import json
import statistics
from pathlib import Path


def load_grading(run_dir: Path) -> dict:
    grading_path = run_dir / "grading.json"
    if not grading_path.exists():
        return {}
    return json.loads(grading_path.read_text(encoding="utf-8"))


def load_timing(run_dir: Path) -> dict:
    timing_path = run_dir / "timing.json"
    if not timing_path.exists():
        return {}
    return json.loads(timing_path.read_text(encoding="utf-8"))


def aggregate(workspace_dir: Path, skill_name: str) -> dict:
    eval_dirs = [d for d in workspace_dir.iterdir() if d.is_dir() and d.name.startswith("eval-")]
    eval_dirs.sort()

    results = []
    for eval_dir in eval_dirs:
        eval_result = {"eval_name": eval_dir.name, "runs": {}}

        for run_type in ("with_skill", "without_skill"):
            run_dir = eval_dir / run_type
            if not run_dir.exists():
                continue

            grading = load_grading(run_dir)
            timing = load_timing(run_dir)

            eval_result["runs"][run_type] = {
                "pass_rate": grading.get("pass_rate", 0),
                "time_seconds": timing.get("total_duration_seconds", 0),
                "tokens": timing.get("total_tokens", 0),
            }

        results.append(eval_result)

    # 计算汇总统计
    with_skill_rates = [r["runs"]["with_skill"]["pass_rate"] for r in results if "with_skill" in r["runs"]]
    without_skill_rates = [r["runs"]["without_skill"]["pass_rate"] for r in results if "without_skill" in r["runs"]]
    with_skill_times = [r["runs"]["with_skill"]["time_seconds"] for r in results if "with_skill" in r["runs"]]
    without_skill_times = [r["runs"]["without_skill"]["time_seconds"] for r in results if "without_skill" in r["runs"]]

    def mean_std(values):
        if not values:
            return {"mean": 0, "std": 0}
        return {"mean": statistics.mean(values), "std": statistics.stdev(values) if len(values) > 1 else 0}

    benchmark = {
        "skill_name": skill_name,
        "workspace": str(workspace_dir),
        "evaluations": results,
        "summary": {
            "with_skill": {
                "pass_rate": mean_std(with_skill_rates),
                "time_seconds": mean_std(with_skill_times),
            },
            "without_skill": {
                "pass_rate": mean_std(without_skill_rates),
                "time_seconds": mean_std(without_skill_times),
            },
        },
    }

    if with_skill_rates and without_skill_rates:
        benchmark["summary"]["delta"] = {
            "pass_rate": mean_std(with_skill_rates)["mean"] - mean_std(without_skill_rates)["mean"],
            "time_seconds": mean_std(with_skill_times)["mean"] - mean_std(without_skill_times)["mean"],
        }

    return benchmark


def render_benchmark_md(benchmark: dict) -> str:
    lines = [f"# Benchmark: {benchmark['skill_name']}", ""]
    lines.append(f"**Workspace**: {benchmark['workspace']}")
    lines.append("")

    lines.append("## Per-Evaluation Results")
    lines.append("")
    lines.append("| Eval | With Skill Pass Rate | With Skill Time (s) | Without Skill Pass Rate | Without Skill Time (s) |")
    lines.append("|------|---------------------:|--------------------:|------------------------:|-----------------------:|")

    for eval_result in benchmark["evaluations"]:
        name = eval_result["eval_name"]
        ws = eval_result["runs"].get("with_skill", {})
        wos = eval_result["runs"].get("without_skill", {})
        lines.append(
            f"| {name} | {ws.get('pass_rate', 0):.2%} | {ws.get('time_seconds', 0):.1f} | "
            f"{wos.get('pass_rate', 0):.2%} | {wos.get('time_seconds', 0):.1f} |"
        )

    lines.append("")
    lines.append("## Summary")
    lines.append("")

    summary = benchmark["summary"]
    ws = summary["with_skill"]
    wos = summary["without_skill"]
    delta = summary.get("delta", {})

    lines.append(f"- **With Skill Pass Rate**: {ws['pass_rate']['mean']:.2%} ± {ws['pass_rate']['std']:.2%}")
    lines.append(f"- **Without Skill Pass Rate**: {wos['pass_rate']['mean']:.2%} ± {wos['pass_rate']['std']:.2%}")
    lines.append(f"- **Pass Rate Delta**: {delta.get('pass_rate', 0):+.2%}")
    lines.append("")
    lines.append(f"- **With Skill Time**: {ws['time_seconds']['mean']:.1f}s ± {ws['time_seconds']['std']:.1f}s")
    lines.append(f"- **Without Skill Time**: {wos['time_seconds']['mean']:.1f}s ± {wos['time_seconds']['std']:.1f}s")
    lines.append(f"- **Time Delta**: {delta.get('time_seconds', 0):+.1f}s")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate benchmark results for subsystem research skill")
    parser.add_argument("workspace", type=Path, help="Path to workspace/iteration-N directory")
    parser.add_argument("--skill-name", default="subsystem-research-workflow", help="Skill name")
    args = parser.parse_args()

    benchmark = aggregate(args.workspace, args.skill_name)

    benchmark_path = args.workspace / "benchmark.json"
    benchmark_path.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Benchmark JSON saved to: {benchmark_path}")

    md_path = args.workspace / "benchmark.md"
    md_content = render_benchmark_md(benchmark)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Benchmark Markdown saved to: {md_path}")


if __name__ == "__main__":
    main()
