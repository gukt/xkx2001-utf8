#!/usr/bin/env python3
"""评分脚本：检查子系统调研初始化输出是否满足断言。

用法：
    python grade_research_init.py <eval-dir>

其中 <eval-dir> 是包含 with_skill/ 或 without_skill/ 的 eval 目录。
脚本会读取 eval_metadata.json 中的断言定义，并输出 grading.json。
"""

import json
import re
import sys
from pathlib import Path


def check_directory_structure(eval_dir: Path) -> tuple[bool, str]:
    """检查是否创建了结构化调研目录。"""
    outputs_dir = eval_dir / "outputs"
    if not outputs_dir.exists():
        return False, f"outputs 目录不存在: {outputs_dir}"

    # 查找 .scratch/research/NN-topic-name/ 下的子目录
    research_dirs = list(outputs_dir.rglob(".scratch/research/*"))
    topic_dirs = [d for d in research_dirs if d.is_dir() and re.match(r"^\d{2}-", d.name)]

    if not topic_dirs:
        return False, "未找到带序号主题目录（如 01-topic-name）"

    topic_dir = topic_dirs[0]
    expected_subdirs = [
        "00-brief",
        "01-raw-findings",
        "02-user-stories",
        "03-engine-insights",
        "04-redteam-review",
        "05-synthesis",
    ]
    missing = [d for d in expected_subdirs if not (topic_dir / d).is_dir()]
    if missing:
        return False, f"主题目录 {topic_dir.name} 缺少子目录: {', '.join(missing)}"

    return True, f"找到完整目录结构: {topic_dir.name}"


def check_brief_exists(eval_dir: Path) -> tuple[bool, str]:
    """检查是否生成了 brief.md。"""
    outputs_dir = eval_dir / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 00-brief/brief.md"
    return True, f"找到 brief.md: {brief_files[0]}"


def check_brief_content(eval_dir: Path, keywords: list[str]) -> tuple[bool, str]:
    """检查 brief.md 是否包含指定关键词。"""
    outputs_dir = eval_dir / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 brief.md"

    content = brief_files[0].read_text(encoding="utf-8")
    missing = [kw for kw in keywords if kw.lower() not in content.lower()]
    if missing:
        return False, f"brief.md 缺少关键词: {', '.join(missing)}"

    return True, f"brief.md 包含所有关键词: {', '.join(keywords)}"


def check_workflow_mention(eval_dir: Path) -> tuple[bool, str]:
    """检查输出中是否提到 Workflow / 多 Agent 并行。"""
    outputs_dir = eval_dir / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 brief.md"

    content = brief_files[0].read_text(encoding="utf-8")
    patterns = [r"workflow", r"多\s*agent", r"并行", r"phase\s*1", r"红队", r"评审委员会"]
    matched = [p for p in patterns if re.search(p, content, re.IGNORECASE)]

    if not matched:
        return False, "brief.md 未提到 Workflow / 多 Agent / 红队 / 评审委员会"

    return True, f"brief.md 提到: {', '.join(matched)}"


def check_modern_perspectives(eval_dir: Path) -> tuple[bool, str]:
    """检查是否提到现代设计/玩家心理/商业化视角。"""
    outputs_dir = eval_dir / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 brief.md"

    content = brief_files[0].read_text(encoding="utf-8")
    patterns = [r"现代", r"玩家心理", r"商业化", r"付费", r"留存", r"增长"]
    matched = [p for p in patterns if re.search(p, content, re.IGNORECASE)]

    if len(matched) < 2:
        return False, f"brief.md 现代视角关键词不足（仅匹配: {', '.join(matched)}）"

    return True, f"brief.md 包含现代视角关键词: {', '.join(matched)}"


def check_no_premature_source_dive(eval_dir: Path) -> tuple[bool, str]:
    """检查 brief.md 是否以方法论/范围为主，而非直接深入源码细节。"""
    outputs_dir = eval_dir / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 brief.md"

    content = brief_files[0].read_text(encoding="utf-8")
    # brief.md 应该包含范围、目标、团队、方法等章节，而不是大段代码引用
    required_sections = ["范围", "目标", "团队", "方法", "产出"]
    matched_sections = [s for s in required_sections if s in content]

    if len(matched_sections) < 3:
        return False, f"brief.md 缺少必要方法论章节（仅含: {', '.join(matched_sections)}）"

    # 检查是否过早出现大量代码细节（例如行号引用、大量函数名列表）
    code_reference_pattern = re.compile(r"(::[a-zA-Z_]+|第?\s*\d+\s*行|\.c\s*第)")
    code_refs = len(code_reference_pattern.findall(content))
    if code_refs > 10:
        return False, f"brief.md 出现过多源码细节引用（{code_refs} 处），可能过早深入源码"

    return True, "brief.md 以方法论和范围为主，未过早深入源码"


def check_grilling_alignment(d: Path) -> tuple[bool, str]:
    """检查 brief 是否覆盖 grilling 对齐的核心要素：范围、目标、团队、方法/执行方式、约束。"""
    outputs_dir = d / "outputs"
    brief_files = list(outputs_dir.rglob("00-brief/brief.md"))
    if not brief_files:
        return False, "未找到 brief.md"

    content = brief_files[0].read_text(encoding="utf-8").lower()
    required = {
        "范围": "范围" in content,
        "目标": "目标" in content,
        "团队": "团队" in content or "角色" in content,
        "方法/执行方式": "方法" in content or "执行方式" in content or "workflow" in content,
        "约束": "约束" in content or "不" in content,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        return False, f"brief.md 缺少 grilling 对齐要素: {', '.join(missing)}"
    return True, "brief.md 覆盖 grilling 对齐要素: 范围、目标、团队、方法/执行方式、约束"


ASSERTION_CHECKS = {
    "starts_with_grilling_or_alignment": check_grilling_alignment,
    "creates_structured_research_directory": check_directory_structure,
    "generates_brief_md": check_brief_exists,
    "proposes_multi_agent_workflow": check_workflow_mention,
    "includes_modern_perspectives": check_modern_perspectives,
    "emphasizes_modern_and_commercial_perspectives": check_modern_perspectives,
    "no_premature_source_dive": check_no_premature_source_dive,
}


def grade_eval(eval_dir: Path) -> dict:
    """对一个 eval 目录下的 with_skill 或 without_skill run 进行评分。"""
    metadata_path = eval_dir.parent / "eval_metadata.json"
    if not metadata_path.exists():
        return {"error": f"未找到 eval_metadata.json: {metadata_path}"}

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assertions = metadata.get("assertions", [])

    results = []
    for assertion in assertions:
        name = assertion["name"]
        description = assertion["description"]
        checker = ASSERTION_CHECKS.get(name)

        if checker is None:
            results.append({
                "text": description,
                "passed": False,
                "evidence": f"未知的断言检查器: {name}",
            })
            continue

        passed, evidence = checker(eval_dir)
        results.append({
            "text": description,
            "passed": passed,
            "evidence": evidence,
        })

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    return {
        "eval_id": metadata.get("eval_id"),
        "eval_name": metadata.get("eval_name"),
        "prompt": metadata.get("prompt"),
        "run_type": eval_dir.name,
        "pass_rate": passed / total if total > 0 else 0,
        "assertions": results,
    }


def main():
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <eval-dir>", file=sys.stderr)
        sys.exit(1)

    eval_dir = Path(sys.argv[1])
    if not eval_dir.exists():
        print(f"目录不存在: {eval_dir}", file=sys.stderr)
        sys.exit(1)

    # 如果传入的是 eval 根目录，分别评分 with_skill 和 without_skill
    if eval_dir.name in ("with_skill", "without_skill"):
        result = grade_eval(eval_dir)
        output_path = eval_dir / "grading.json"
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Grading saved to: {output_path}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for run_type in ("with_skill", "without_skill"):
            run_dir = eval_dir / run_type
            if run_dir.exists():
                result = grade_eval(run_dir)
                output_path = run_dir / "grading.json"
                output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Grading saved to: {output_path}")


if __name__ == "__main__":
    main()
