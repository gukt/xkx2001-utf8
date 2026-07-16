"""门派护甲草表 -> 去重分类 -> merge 进现有 items.yaml（ADR-0064 决策 6）。

读 [armor_extract](armor_extract.py) 产出的草表（默认 /tmp/armors_all.yaml，不存在
则自动重跑提取），执行 ADR-0064 决策 6：

1. 权威源去重：clone/armor > d/*/obj，同 id 取 clone/armor（护甲无 clone/unique）。
2. em -> emei 折叠（复制债，同 weapon_finalize）。
3. 跳过 COMBINED_ITEM（留方案 A M3）。
4. 分类：clone/armor 或多门派引用 -> common；d/<sect> 单门派 -> sect/<sect>。
5. 混合型条目前插 ``# 后置缺口`` 注释（do_tear/hit_by/female_only/armor_apply 等）。
6. **marker 文本追加**：护甲段用 ``# ── 护甲（ADR-0064）──`` 标记追加进现有
   items.yaml（武器段+注释完整保留，护甲段幂等剥离重追加）。不覆盖武器数据。

产出 [scenes/wuxia_common/items.yaml](../scenes/wuxia_common/) +
scenes/wuxia_<sect>/items.yaml（护甲追加进武器已落数据层 CPK，ADR-0062）。
幂等：重跑剥离旧护甲段重新追加。weapon_finalize 重跑会覆盖护甲段，须后再跑本脚本。

用法：cd engine && uv run python tools/armor_finalize.py [--in DRAFT] [--out-dir DIR]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from armor_extract import parse_armor
from weapon_finalize import _sect_of, _strip_meta

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE = Path(__file__).resolve().parents[1]
_DEFAULT_IN = Path("/tmp/armors_all.yaml")
_DEFAULT_OUT = _ENGINE / "scenes"

# 护甲段标记（追加进现有 items.yaml，幂等剥离重追加）
_ARMOR_MARK = "# ── 护甲（ADR-0064 wear 批，armor_finalize.py 追加）──"


def _rank(path: str) -> int:
    """权威源优先级：clone/armor=0 < d/*/obj=1（护甲无 clone/unique）。"""
    if path.startswith("clone/armor"):
        return 0
    return 1


def _load_or_extract(in_path: Path) -> list[dict]:
    """读草表；不存在则复用 armor_extract.parse_armor 全量提取。"""
    if in_path.exists():
        return yaml.safe_load(in_path.read_text(encoding="utf-8")) or []
    root = _REPO_ROOT
    files = list((root / "clone/armor").glob("*.c"))
    files += list((root / "d").glob("*/obj/*.c"))
    items = [parse_armor(f) for f in sorted(files)]
    return [i for i in items if i]


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
    for a in draft:
        by_id.setdefault(a["id"], []).append(a)

    common: list[_GapEntry] = []
    sects: dict[str, list[_GapEntry]] = {}
    skipped_combined: list[str] = []
    gap_ids: list[str] = []

    for aid, recs in by_id.items():
        recs_sorted = sorted(recs, key=lambda r: _rank(r["_path"]))
        auth = dict(recs_sorted[0])
        merged: list[str] = []
        for r in recs_sorted:
            for a in r.get("aliases", []):
                if a not in merged:
                    merged.append(a)
        auth["aliases"] = merged

        postpone = auth.get("_postpone", [])
        if any("COMBINED_ITEM" in p for p in postpone):
            skipped_combined.append(aid)
            continue

        sect_set = {
            s for r in recs_sorted for s in [_sect_of(r["_path"])] if s is not None
        }
        if auth["_path"].startswith("clone/") or len(sect_set) > 1:
            category = "common"
        elif len(sect_set) == 1:
            category = next(iter(sect_set))
        else:
            category = "common"

        gap = [p for p in postpone if "COMBINED_ITEM" not in p]
        if gap:
            gap_ids.append(aid)

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


def _dump_armors_segment(armors_with_gap: list[_GapEntry]) -> str:
    """护甲段 YAML（safe_dump + 混合型条目前插 # 后置缺口 注释）。"""
    items = [a for a, _ in armors_with_gap]
    gap_map = {a["id"]: g for a, g in armors_with_gap if g}
    text = yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=10000)
    if gap_map:
        out: list[str] = []
        for line in text.split("\n"):
            m = re.match(r"^- id: (.+)$", line)
            if m and m.group(1) in gap_map:
                out.append(
                    f"# 后置缺口(ADR-0064决策6): {'; '.join(gap_map[m.group(1)])}"
                )
            out.append(line)
        text = "\n".join(out)
    return text


def _append_armors(path: Path, armors_with_gap: list[_GapEntry]) -> int:
    """护甲段追加进现有 items.yaml（marker 幂等剥离重追加）。

    现有文件有武器段（含 header + # 后置缺口 注释）完整保留；无文件则新建。
    返回写入护甲条目数。
    """
    if not armors_with_gap:
        return 0
    segment = _dump_armors_segment(armors_with_gap)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        # 幂等：剥离旧护甲段（marker 之后），保留武器段
        if _ARMOR_MARK in existing:
            existing = existing.split(_ARMOR_MARK)[0].rstrip() + "\n"
        text = f"{existing}\n{_ARMOR_MARK}\n{segment}"
    else:
        text = f"{_ARMOR_MARK}\n{segment}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return len(armors_with_gap)


_MANIFEST_TEMPLATE = """\
cpk_id: wuxia_{sect}
schema_version: 1
theme: wuxia
pack_type: module_pack
version: 0.1.0
license: CC-BY-SA-4.0
author: xkx-core
dependencies: []
capabilities_required: []
"""


def _ensure_manifest(items_path: Path, sect: str) -> None:
    """新建数据层 CPK 目录时补 manifest（ADR-0062 决策 4，无 entry_points 纯物品台账）。

    护甲新增的门派目录（武器批未覆盖，如 foshan/shaolin 等）若无 manifest，
    cli.py ``_load_theme_data_items`` 会跳过导致护甲不进 item_registry。
    """
    mpath = items_path.parent / "manifest.yaml"
    if mpath.exists():
        return
    mpath.write_text(_MANIFEST_TEMPLATE.format(sect=sect), encoding="utf-8")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="护甲草表 -> 去重分类 -> merge 进 items.yaml")
    ap.add_argument("--in", dest="in_path", default=str(_DEFAULT_IN), help="草表路径")
    ap.add_argument("--out-dir", default=str(_DEFAULT_OUT), help="输出目录")
    args = ap.parse_args()

    draft = _load_or_extract(Path(args.in_path))
    common, sects, stats = finalize(draft)
    out_dir = Path(args.out_dir)

    common.sort(key=lambda e: e[0]["id"])
    _append_armors(out_dir / "wuxia_common" / "items.yaml", common)
    print(f"# common: {len(common)} 护甲", file=sys.stderr)
    for sect in sorted(sects):
        items = sorted(sects[sect], key=lambda e: e[0]["id"])
        sp = out_dir / f"wuxia_{sect}" / "items.yaml"
        _ensure_manifest(sp, sect)  # 新建数据层 CPK 目录补 manifest（ADR-0062 决策 4）
        n = _append_armors(sp, items)
        print(f"# {sect}: {n} 护甲", file=sys.stderr)

    print(
        f"# 草表 {stats['draft']} -> 唯一 id {stats['unique_ids']} -> "
        f"common {stats['common']} + sect {stats['sect_total']}"
        f"（{stats['sect_count']} 门派）"
        f" = {stats['common'] + stats['sect_total']} 条；"
        f"跳过 COMBINED_ITEM {stats['skipped_combined']}；"
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
