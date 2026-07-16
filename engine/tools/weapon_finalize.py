"""门派武器草表 -> 去重分类 -> ItemDef YAML（ADR-0060 决策 6 收尾）。

读 [weapon_extract](weapon_extract.py) 产出的草表（默认 /tmp/weapons_all.yaml，不存在
则自动重跑提取），执行 ADR-0060 决策 1/2/4/5：

1. 去元字段（``_path``/``_postpone``/``_flag_unknown`` 保留用于分类/注释，不进 ItemDef）。
2. 权威源去重：clone/weapon > clone/unique > d/*/obj，同 id 取最高优先级源（决策 2）。
3. em -> emei 折叠：em 是 emei 复制债，门派集合里 em 重映射为 emei（决策 2，em/emei 复制粘贴）。
4. 跳过 COMBINED_ITEM（falun/shizi 等，留方案 A M3，决策 4 明确不进本批 ItemDef）。
5. 分类：权威 clone/* 或多门派引用 -> common；d/<sect> 单门派 -> sect/<sect>（决策 2）。
6. 混合型（自定义命令/hit_ob）条目前插 ``# 后置缺口`` 注释（决策 4，标注不完整定义）。
7. aliases 合并去重（多来源 aliases 保序合并）。

产出 [scenes/wuxia_weapons/](../scenes/wuxia_weapons/) common.yaml + sect/<sect>.yaml。
纯数据台账，不接 cli.py（CPK 接线后置，ADR-0062）。

用法：cd engine && uv run python tools/weapon_finalize.py [--in DRAFT] [--out-dir DIR]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from weapon_extract import parse_weapon  # 同目录（tools/ 在 sys.path[0]）

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE = Path(__file__).resolve().parents[1]
_DEFAULT_IN = Path("/tmp/weapons_all.yaml")
_DEFAULT_OUT = _ENGINE / "scenes" / "wuxia_weapons"


def _rank(path: str) -> int:
    """权威源优先级（决策 2）：clone/weapon=0 < clone/unique=1 < d/*/obj=2。"""
    if path.startswith("clone/weapon"):
        return 0
    if path.startswith("clone/unique"):
        return 1
    return 2


def _sect_of(path: str) -> str | None:
    """d/<sect>/obj/... -> sect（em -> emei 折叠，复制债）。非门派 obj 返回 None。"""
    m = re.match(r"d/([^/]+)/obj/", path)
    if not m:
        return None
    s = m.group(1)
    return "emei" if s == "em" else s  # em 是 emei 旧名/复制债


def _load_or_extract(in_path: Path) -> list[dict]:
    """读草表；不存在则复用 weapon_extract.parse_weapon 全量提取。"""
    if in_path.exists():
        return yaml.safe_load(in_path.read_text(encoding="utf-8")) or []
    # 自动重跑提取（草表在 /tmp，session 结束丢失）
    root = _REPO_ROOT
    files = list((root / "clone/weapon").glob("*.c"))
    files += list((root / "clone/unique").glob("*.c"))
    files += list((root / "d").glob("*/obj/*.c"))
    items = [parse_weapon(f) for f in sorted(files)]
    return [i for i in items if i]


def _strip_meta(w: dict) -> dict:
    """去除元字段（_path/_postpone/_flag_unknown），保留 ItemDef schema 内字段。"""
    return {k: v for k, v in w.items() if not k.startswith("_")}


# 条目：(去元字段 item dict, 后置缺口列表)
_GapEntry = tuple[dict, list[str]]


def finalize(
    draft: list[dict],
) -> tuple[list[_GapEntry], dict[str, list[_GapEntry]], dict]:
    """草表 -> 去重分类。

    Returns:
        (common_items, sect_items, stats)：common 条目 list of (item, gap)；
        sect dict[sect -> list of (item, gap)]；stats 统计。
    """
    by_id: dict[str, list[dict]] = {}
    for w in draft:
        by_id.setdefault(w["id"], []).append(w)

    common: list[tuple[dict, list[str]]] = []
    sects: dict[str, list[tuple[dict, list[str]]]] = {}
    skipped_combined: list[str] = []
    gap_ids: list[str] = []

    for wid, recs in by_id.items():
        recs_sorted = sorted(recs, key=lambda r: _rank(r["_path"]))
        auth = dict(recs_sorted[0])
        # aliases 合并去重保序（多来源）
        merged: list[str] = []
        for r in recs_sorted:
            for a in r.get("aliases", []):
                if a not in merged:
                    merged.append(a)
        auth["aliases"] = merged

        postpone = auth.get("_postpone", [])
        # 跳过 COMBINED_ITEM（决策 4，留方案 A M3，不进本批 ItemDef）
        if any("COMBINED_ITEM" in p for p in postpone):
            skipped_combined.append(wid)
            continue

        # 分类（决策 2）：权威 clone/* 或多门派引用 -> common；单门派 -> sect
        sect_set = {s for r in recs_sorted for s in [_sect_of(r["_path"])] if s is not None}
        if auth["_path"].startswith("clone/") or len(sect_set) > 1:
            category = "common"
        elif len(sect_set) == 1:
            category = next(iter(sect_set))
        else:
            category = "common"  # 兜底（权威 d/* 必有 sect，此处防御）

        # 缺口（决策 4）：去 COMBINED_ITEM 后剩余后置维度
        gap = [p for p in postpone if "COMBINED_ITEM" not in p]
        if gap:
            gap_ids.append(wid)

        entry = (_strip_meta(auth), gap)
        if category == "common":
            common.append(entry)
        else:
            sects.setdefault(category, []).append(entry)

    stats = {
        "draft": len(draft),
        "unique_ids": len(by_id),
        "common": len(common),
        "sect_total": sum(len(v) for v in sects.values()),
        "sect_count": len(sects),
        "skipped_combined": len(skipped_combined),
        "gap": len(gap_ids),
        "skipped_combined_ids": skipped_combined,
    }
    return common, sects, stats


def _dump_with_gaps(items_with_gap: list[tuple[dict, list[str]]], path: Path, header: str) -> None:
    """safe_dump + 混合型条目前插 # 后置缺口 注释（决策 4）。"""
    items = [w for w, _ in items_with_gap]
    gap_map = {w["id"]: g for w, g in items_with_gap if g}
    text = yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=10000)
    if gap_map:
        out: list[str] = []
        for line in text.split("\n"):
            m = re.match(r"^- id: (.+)$", line)
            if m and m.group(1) in gap_map:
                out.append(f"# 后置缺口(ADR-0060决策4): {'; '.join(gap_map[m.group(1)])}")
            out.append(line)
        text = "\n".join(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + text, encoding="utf-8")


_HEADER = """\
# 门派武器 ItemDef（ADR-0060 决策 6 落地，weapon_finalize.py 产出）。
# 纯数据台账：LPC create() 标量 + 静态 weapon_prop mapping（damage 走 weapon_prop/damage）。
# 不含：wield_msg/unwield_msg（决策3 留 wield 命令批）/ hit_ob 特效（留 M3 招式表）
# / do_cut/do_lian 命令（留命令批）/ COMBINED_ITEM 堆叠（留方案 A M3）。
# 混合型武器条目前有 # 后置缺口 注释（ADR-0060 决策 4，标注不完整定义）。
# 权威源去重：clone/weapon > clone/unique > d/*/obj；em 折叠到 emei（复制债）。
# 人工校验重点：flag 位掩码 / weapon_prop 子键 / long 颜色码与转义。
"""


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="武器草表 -> 去重分类 ItemDef YAML")
    ap.add_argument("--in", dest="in_path", default=str(_DEFAULT_IN), help="草表路径")
    ap.add_argument("--out-dir", default=str(_DEFAULT_OUT), help="输出目录")
    args = ap.parse_args()

    draft = _load_or_extract(Path(args.in_path))
    common, sects, stats = finalize(draft)
    out_dir = Path(args.out_dir)

    common.sort(key=lambda e: e[0]["id"])
    _dump_with_gaps(common, out_dir / "common.yaml", _HEADER)
    for sect in sorted(sects):
        items = sorted(sects[sect], key=lambda e: e[0]["id"])
        _dump_with_gaps(items, out_dir / "sect" / f"{sect}.yaml", _HEADER)

    print(
        f"# 草表 {stats['draft']} -> 唯一 id {stats['unique_ids']} -> "
        f"common {stats['common']} + sect {stats['sect_total']}（{stats['sect_count']} 门派）"
        f" = {stats['common'] + stats['sect_total']} 条；"
        f"跳过 COMBINED_ITEM {stats['skipped_combined']}（留方案 A）；"
        f"混合型缺口标注 {stats['gap']} 条",
        file=sys.stderr,
    )
    if stats["skipped_combined_ids"]:
        print(
            f"# 跳过的 COMBINED_ITEM: {stats['skipped_combined_ids']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
