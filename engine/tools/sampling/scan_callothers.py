"""扫描全仓库 LPC .c 文件的 -> call_other 调用点 + 函数级分布 + 已实现/待迁移分类。

阶段 0 任务 6 抽样校准实验：
  阶段 A（ADR-0046）：枚举 59270 调用点 + 分布统计 + 抽样方案 + 迁移单位建议
  阶段 B（本脚本扩展）：函数级分布 + 已实现/待迁移分类（greenfield 工时语义）+ 抽样候选

方法论见 ADR-0046 / ADR-0047 / docs/xkx-arch/17-抽样校准实验实施计划.md。

输出（engine/tools/sampling/output/）：
  - callothers.jsonl       : 每行一个调用点（含 func/category/status/func_kind）
  - summary.json           : 汇总统计（总量/子系统/方法 top-N/类别/状态）
  - func_dist.json         : 函数级分布（函数总数/每函数调用点/子系统×状态×kind）
  - classification.json    : 已实现/待迁移 + 内容填充/新逻辑 分类汇总
  - sample_candidates.json : 80 样本候选清单（分层抽样，固定种子可复现）

用法::

    cd engine
    uv run python -m tools.sampling.scan_callothers
"""

from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# 仓库根：engine/tools/sampling/ -> parents[3]
ROOT = Path(__file__).resolve().parents[3]

# 扫描的 LPC 顶层目录
LPC_DIRS = ("d", "cmds", "adm", "kungfu", "feature", "inherit", "clone", "u")

# call_other 正则：caller->method(  /  caller->"method"(
# caller 为标识符/)/]/.（含链式）；method 为标识符或字符串字面量（动态）
CALLOTHER_RE = re.compile(r'([\w\)\]\.])\s*->\s*(\w+|"([^"]*)")\s*\(')

# --- 函数解析 ---
# LPC 函数定义：[修饰符] 类型 名(参数) { 或 ;
# type 兼容 class Foo / string * / 普通单 word；兼容 ){ 紧贴（kungfu 实证）与换行 {
FUNC_DEF_RE = re.compile(
    r'^[ \t]*'
    r'(?:(?:nomask|private|public|static|varargs|protected|final)\s+)*'
    r'(?P<type>class\s+\w+|\w+\s*\*+|\w+)\s+'
    r'(?P<name>\w+)\s*'
    r'\((?P<params>[^)]*)\)\s*'
    r'(?P<end>[{;])',
    re.MULTILINE,
)
# 排除非类型词（return foo(); 会误匹配为函数声明）
NON_TYPE_KW = {
    "return", "if", "for", "while", "switch", "else", "do", "case", "default",
    "break", "continue", "catch", "foreach", "inherit", "include", "define",
}

# --- 方法类别（与 report.md §三聚类精确一致，可对账占比）---
CATEGORY_METHODS: dict[str, set[str]] = {
    "C1": {"query", "query_temp", "set", "add", "set_temp", "delete_temp",
           "add_temp", "delete"},  # dbase 读写 56.3%
    "C2": {"query_skill", "set_skill", "map_skill", "query_skill_mapped",
           "improve_skill"},  # 技能 11.0%
    "C3": {"is_fighting", "start_busy", "is_busy", "kill_ob", "do_attack",
           "receive_damage", "receive_wound"},  # 战斗 6.8%
    "C4": {"wear", "wield"},  # 装备 3.1%
    "C5": {"apply_condition", "query_condition"},  # 条件 2.0%
    "C6": {"move"},  # 移动 3.2%
    "C7": {"name", "query_respect", "is_character", "query_rude",
           "set_amount"},  # 其他 top30 7.0%
}
_METHOD_TO_CATEGORY: dict[str, str] = {m: c for c, ms in CATEGORY_METHODS.items() for m in ms}

# C1-C6 = 新引擎已实现等价（框架级）；C7/C8 = 待迁移（greenfield 工时语义，见 ADR-0047）
IMPLEMENTED_CATEGORIES = {"C1", "C2", "C3", "C4", "C5", "C6"}

# 数据函数（内容填充）vs 行为函数（新逻辑实现）
DATA_FUNC_NAMES = {"create", "setup", "reset", "init", "init_data"}


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


def classify_method(method: str) -> str:
    """方法名 -> 类别 C1-C8（C8 = 长尾，top30 之外）。"""
    return _METHOD_TO_CATEGORY.get(method, "C8")


def classify_status(category: str) -> str:
    """类别 -> implemented/pending（greenfield 工时语义）。"""
    return "implemented" if category in IMPLEMENTED_CATEGORIES else "pending"


def classify_func_kind(func_name: str) -> str:
    """函数名 -> data（内容填充）/ logic（新逻辑实现）。"""
    if func_name in DATA_FUNC_NAMES or func_name.startswith("skill_set"):
        return "data"
    return "logic"


def func_status(cats: Counter) -> str:
    """函数调用点类别分布 -> 状态（pending 调用点数 >= implemented 即 pending，保守）。"""
    impl = sum(c for cat, c in cats.items() if cat in IMPLEMENTED_CATEGORIES)
    pend = sum(c for cat, c in cats.items() if cat not in IMPLEMENTED_CATEGORIES)
    return "pending" if pend >= impl else "implemented"


def find_matching_brace(text: str, open_pos: int) -> int:
    """从 open_pos 的 '{' 开始，找匹配的 '}' 位置（text 已 strip 字符串/注释）。"""
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n  # 未闭合，到末尾


def line_of(text: str, pos: int) -> int:
    """字符位置 -> 行号（1-based）。"""
    return text.count("\n", 0, pos) + 1


def parse_functions(stripped: str) -> list[dict]:
    """解析 stripped 文本中的函数定义，返回 [{name, start_line, end_line}]。

    仅保留有 body 的定义（`{` 结尾）；前向声明（`;`）不计（无调用点 body）。
    """
    funcs: list[dict] = []
    for m in FUNC_DEF_RE.finditer(stripped):
        type_token = m.group("type").split()[0]
        if type_token in NON_TYPE_KW:
            continue
        if m.group("end") != "{":
            continue  # 声明无 body
        brace_pos = m.end() - 1  # '{' 位置
        close_pos = find_matching_brace(stripped, brace_pos)
        funcs.append({
            "name": m.group("name"),
            "start_line": line_of(stripped, m.start()),
            "end_line": line_of(stripped, close_pos),
        })
    return funcs


def assign_func(funcs: list[dict], lineno: int) -> str:
    """调用点行号 -> 所属函数名（无归属返回 "<top-level>"）。"""
    for f in funcs:
        if f["start_line"] <= lineno <= f["end_line"]:
            return f["name"]
    return "<top-level>"


def scan_file(path: Path) -> tuple[list[dict], list[dict]]:
    """扫描单个 .c 文件，返回 (调用点记录列表, 函数列表)。

    每调用点记录含 file/line/method/dynamic/subsystem/func/category/status；
    每函数含 name/start_line/end_line/file/subsystem。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = strip_strings_comments(text)
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    rel_str = str(rel)
    subsystem = rel.parts[0] if rel.parts else "other"
    funcs = parse_functions(stripped)
    for f in funcs:
        f["file"] = rel_str
        f["subsystem"] = subsystem
    records: list[dict] = []
    for lineno, line in enumerate(stripped.splitlines(), 1):
        for m in CALLOTHER_RE.finditer(line):
            if m.group(3) is not None:
                method = m.group(3)
                dynamic = True
            else:
                method = m.group(2)
                dynamic = False
            category = classify_method(method)
            records.append({
                "file": rel_str,
                "line": lineno,
                "method": method,
                "dynamic": dynamic,
                "subsystem": subsystem,
                "func": assign_func(funcs, lineno),
                "category": category,
                "status": classify_status(category),
            })
    return records, funcs


def iter_lpc_files() -> list[Path]:
    """收集所有待扫描的 LPC .c 文件。"""
    files: list[Path] = []
    for top in LPC_DIRS:
        top_dir = ROOT / top
        if top_dir.is_dir():
            files.extend(top_dir.rglob("*.c"))
    return files


def summarize(records: list[dict]) -> dict:
    """汇总统计（阶段 A 兼容 + 类别/状态扩展）。"""
    total = len(records)
    subsystem_counts = Counter(r["subsystem"] for r in records)
    method_counts = Counter(r["method"] for r in records)
    file_counts = Counter(r["file"] for r in records)
    dynamic_count = sum(1 for r in records if r["dynamic"])
    category_counts = Counter(r["category"] for r in records)
    status_counts = Counter(r["status"] for r in records)
    func_counts = Counter(r["func"] for r in records)
    return {
        "total": total,
        "dynamic_count": dynamic_count,
        "dynamic_ratio": dynamic_count / total if total else 0.0,
        "method_unique": len(method_counts),
        "files_with_calls": len(file_counts),
        "subsystem": dict(subsystem_counts.most_common()),
        "method_top30": dict(method_counts.most_common(30)),
        "top_files": dict(file_counts.most_common(20)),
        "category": dict(category_counts.most_common()),
        "status": dict(status_counts.most_common()),
        "top_funcs": dict(func_counts.most_common(20)),
    }


def build_all_funcs(all_records: list[dict]) -> list[dict]:
    """聚合每个有调用点的函数的统计（迁移单位 = 函数）。

    返回 [{file, name, subsystem, call_count, categories, status, func_kind}]。
    无调用点函数不计（不在 59270 调用点框架内）。
    """
    by_func: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in all_records:
        by_func[(r["file"], r["func"])].append(r)
    all_funcs: list[dict] = []
    for (file, name), recs in by_func.items():
        if name == "<top-level>":
            continue
        cats = Counter(r["category"] for r in recs)
        all_funcs.append({
            "file": file,
            "name": name,
            "subsystem": recs[0]["subsystem"],
            "call_count": len(recs),
            "categories": cats,
            "status": func_status(cats),
            "func_kind": classify_func_kind(name),
        })
    return all_funcs


def build_func_dist(all_funcs: list[dict]) -> dict:
    """函数级分布。"""
    calls = sorted(f["call_count"] for f in all_funcs)

    def pct(p: float) -> int:
        if not calls:
            return 0
        return calls[min(int(len(calls) * p), len(calls) - 1)]

    by_subsystem = Counter(f["subsystem"] for f in all_funcs)
    by_status = Counter(f["status"] for f in all_funcs)
    by_func_kind = Counter(f["func_kind"] for f in all_funcs)
    cross = defaultdict(int)
    for f in all_funcs:
        cross[f"{f['subsystem']}/{f['status']}/{f['func_kind']}"] += 1
    return {
        "total_funcs": len(all_funcs),
        "by_subsystem": dict(by_subsystem.most_common()),
        "by_status": dict(by_status.most_common()),
        "by_func_kind": dict(by_func_kind.most_common()),
        "call_count_dist": {
            "min": calls[0] if calls else 0,
            "p50": pct(0.5),
            "p90": pct(0.9),
            "p99": pct(0.99),
            "max": calls[-1] if calls else 0,
            "mean": round(sum(calls) / len(calls), 2) if calls else 0,
        },
        "subsystem_status_funckind": dict(sorted(cross.items())),
    }


def build_classification(records: list[dict], all_funcs: list[dict]) -> dict:
    """已实现/待迁移 + 内容填充/新逻辑 分类汇总。"""
    cat_status: dict[str, dict[str, int]] = defaultdict(
        lambda: {"implemented": 0, "pending": 0}
    )
    for r in records:
        cat_status[r["category"]][r["status"]] += 1
    pending_kind = Counter(f["func_kind"] for f in all_funcs if f["status"] == "pending")
    impl_kind = Counter(f["func_kind"] for f in all_funcs if f["status"] == "implemented")
    return {
        "callpoints_by_category_status": {c: dict(s) for c, s in sorted(cat_status.items())},
        "pending_funcs_by_kind": dict(pending_kind.most_common()),
        "implemented_funcs_by_kind": dict(impl_kind.most_common()),
        "note": (
            "C1-C6=implemented（新引擎框架级已实现等价，工时≈0/数据录入）；"
            "C7/C8=pending 待迁移。pending 函数再分 data（内容填充）/logic（新逻辑实现）。"
            "C8 含少量应归 C2-C7 的变体方法，已实现判定偏保守（高估待迁移面）。"
        ),
    }


def build_sample_candidates(all_funcs: list[dict]) -> dict:
    """分层抽样 80 样本候选清单（status × func_kind × subsystem，层内 tier 均衡）。

    配额：implemented 确认（每子系统 1）/ pending-data 内容填充（每子系统 2）/
          pending-logic 新逻辑实现（按子系统比例分剩余，重点工时变异源）。
    层内按复杂度档（call_count low≤5/mid≤20/high>20）高复杂度优先 + 固定种子选取。
    """
    rng = random.Random(42)
    for f in all_funcs:
        c = f["call_count"]
        f["tier"] = "low" if c <= 5 else ("mid" if c <= 20 else "high")
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for f in all_funcs:
        groups[(f["status"], f["func_kind"], f["subsystem"])].append(f)

    def pick(funcs: list[dict], n: int) -> list[dict]:
        if n >= len(funcs):
            return list(funcs)
        by_tier: dict[str, list[dict]] = defaultdict(list)
        for f in funcs:
            by_tier[f["tier"]].append(f)
        for t in by_tier:
            rng.shuffle(by_tier[t])
        result: list[dict] = []
        queues = [by_tier["high"], by_tier["mid"], by_tier["low"]]  # 高复杂度优先
        idx = 0
        while len(result) < n and any(queues):
            q = queues[idx % 3]
            if q:
                result.append(q.pop())
            idx += 1
        return result

    TARGET = 80
    candidates: list[dict] = []
    # implemented 每子系统 1（确认工时≈0，logic+data 合并选）
    for sub in sorted({k[2] for k in groups if k[0] == "implemented"}):
        pool = (groups.get(("implemented", "logic", sub), [])
                + groups.get(("implemented", "data", sub), []))
        candidates += pick(pool, 1)
    # pending-data 每子系统 2（确认内容填充低工时规律）
    for sub in sorted({k[2] for k in groups if k[:2] == ("pending", "data")}):
        candidates += pick(groups.get(("pending", "data", sub), []), 2)
    # pending-logic 按子系统比例分剩余（重点工时变异源）
    sub_ratios = {
        "d": 40, "kungfu": 25, "clone": 10, "cmds": 10,
        "adm": 8, "inherit": 4, "feature": 3,
    }
    logic_target = TARGET - len(candidates)
    plogic_subs = sorted({k[2] for k in groups if k[:2] == ("pending", "logic")})
    total_r = sum(sub_ratios.get(s, 0) for s in plogic_subs) or 1
    for sub in plogic_subs:
        n = round(logic_target * sub_ratios.get(sub, 0) / total_r)
        candidates += pick(groups.get(("pending", "logic", sub), []), n)

    out = [{
        "file": f["file"], "func": f["name"], "subsystem": f["subsystem"],
        "status": f["status"], "func_kind": f["func_kind"], "tier": f["tier"],
        "call_count": f["call_count"], "categories": dict(f["categories"]),
    } for f in candidates]
    by_sf = Counter(f"{f['status']}/{f['func_kind']}" for f in out)
    return {
        "target": TARGET,
        "actual": len(out),
        "by_status_funckind": dict(by_sf.most_common()),
        "note": (
            "分层抽样候选清单（status×func_kind×subsystem，层内 tier 均衡）。"
            "implemented/pending-data 欠采样确认低工时；pending-logic 过采样为工时变异源。"
            "实测时按此清单选取，可调整。固定种子 random.Random(42) 可复现。"
        ),
        "candidates": out,
    }


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)

    files = iter_lpc_files()
    print(f"扫描 {len(files)} 个 .c 文件...", file=sys.stderr)

    all_records: list[dict] = []
    for path in files:
        records, _funcs = scan_file(path)
        all_records.extend(records)

    all_funcs = build_all_funcs(all_records)

    jsonl_path = out_dir / "callothers.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = summarize(all_records)
    func_dist = build_func_dist(all_funcs)
    classification = build_classification(all_records, all_funcs)
    samples = build_sample_candidates(all_funcs)

    for name, obj in [
        ("summary.json", summary),
        ("func_dist.json", func_dist),
        ("classification.json", classification),
        ("sample_candidates.json", samples),
    ]:
        (out_dir / name).write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    total = summary["total"]
    print(f"总计 {total} 个 -> 调用点")
    print(f"有调用点的函数: {func_dist['total_funcs']}")
    print(f"类别分布: {summary['category']}")
    print(f"状态分布: {summary['status']}")
    print(f"函数状态: {func_dist['by_status']}")
    print(f"pending 函数 kind: {classification['pending_funcs_by_kind']}")
    print(f"样本候选: {samples['actual']} / 目标 {samples['target']}")
    print(f"  按状态/kind: {samples['by_status_funckind']}")
    print(f"\n输出目录: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
