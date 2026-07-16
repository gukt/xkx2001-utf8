"""门派护甲数据提取脚本（ADR-0064 决策 6，对标 weapon_extract.py ADR-0060 决策 6）。

半自动从 LPC 护甲 .c 的 create() 提取标量数值 + armor_prop/* -> ItemDef YAML 草表。
与武器的关键差异：护甲无 init_<type>(damage,flag)，armor_type 由 inherit
HEAD/CLOTH/... 宏推断（11 类型，对照 armor.h TYPE_*）；armor_prop/* 直接 set。
setup() 副作用模拟：weight>3000 且无 armor_prop/dodge 时设 dodge=-weight/3000
（inherit/armor/<type>.c setup() 重甲降闪避，greenfield 台账需预计算）。
标注后置维度（do_tear/hit_by/自定义命令/female_only/COMBINED_ITEM/armor_apply）。

人工校验重点：armor_prop 子键完整性、setup dodge 副作用、long 多行/颜色码、
去重（em/emei 复制粘贴）。

用法：cd engine && uv run python tools/armor_extract.py [LPC_GLOB ...] [--out FILE]
默认扫 clone/armor + d/*/obj 下 inherit ARMOR/CLOTH/HEAD/... 的护甲文件。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from weapon_extract import (
    _extract_create_body,
    _parse_set_kv,
    _parse_set_name,
)

# inherit 宏 -> armor_type（对照 include/armor.h TYPE_*，11 类型）
INHERIT_TYPE_MAP: dict[str, str] = {
    "HEAD": "head",
    "NECK": "neck",
    "CLOTH": "cloth",
    "ARMOR": "armor",
    "SURCOAT": "surcoat",
    "WAIST": "waist",
    "WRISTS": "wrists",
    "SHIELD": "shield",
    "FINGER": "finger",
    "HANDS": "hands",
    "BOOTS": "boots",
}

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_armor_type(text: str) -> str | None:
    """inherit <TYPE> 宏 -> armor_type。匹配 11 类型 inherit 宏（HEAD/CLOTH/...）。"""
    for macro, atype in INHERIT_TYPE_MAP.items():
        if re.search(rf"\binherit\s+{macro}\b", text):
            return atype
    return None


def _parse_weight(body: str) -> int | None:
    """set_weight(N) 或 set("weight", N) -> N（护甲两种写法都有，earring 用后者）。"""
    m = re.search(r"set_weight\s*\(\s*(\d+)\s*\)", body)
    if m:
        return int(m.group(1))
    v = _parse_set_kv(body, "weight")
    return int(v) if v and v.isdigit() else None


def _parse_armor_prop(body: str) -> dict[str, int]:
    """set("armor_prop/<key>", N) -> {key: N}。解析全部子键（armor/dodge 等）。"""
    props: dict[str, int] = {}
    for m in re.finditer(r'set\(\s*"armor_prop/(\w+)"\s*,\s*(-?\d+)\s*\)', body):
        props[m.group(1)] = int(m.group(2))
    return props


def _detect_postpone(text: str, body: str) -> list[str]:
    """检测后置维度（ADR-0064 决策 6，对标 ADR-0060 决策 4）。"""
    postpone = []
    if re.search(r"\bCOMBINED_ITEM\b", text[:500]):
        postpone.append("COMBINED_ITEM(堆叠,留方案A)")
    if re.search(r"\b(?:void|int)\s+do_(?:tear|cut|lian|study|wear|remove)\s*\(", text):
        postpone.append("自定义命令(留命令批)")
    if re.search(r"\bhit_by\s*\(", text):
        postpone.append("hit_by(留M3招式表)")
    if re.search(r'\bset\(\s*"female_only"', body):
        postpone.append("female_only(留物品系统批)")
    if re.search(r'\bset\(\s*"armor_apply/', body):
        postpone.append("armor_apply(留物品系统批,dodge副作用需人工校验)")
    return postpone


def parse_armor(path: Path) -> dict | None:
    """解析单个 LPC 护甲文件 -> ItemDef dict（含 _path/_postpone 元字段）。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    armor_type = _parse_armor_type(text)
    if armor_type is None:
        return None  # 非护甲（无 inherit ARMOR/CLOTH/... 宏）
    body = _extract_create_body(text)
    if not body:
        return None
    name, aliases = _parse_set_name(body)
    if not name:
        return None
    props = _parse_armor_prop(body)
    weight = _parse_weight(body)
    # setup() 副作用模拟（inherit/armor/<type>.c 行 13-15）：
    # weight>3000 且无 armor_prop/dodge 时设 dodge=-weight/3000（重甲降闪避）。
    # greenfield 台账需预计算（equipment.wear 不调 setup）。
    if weight and weight > 3000 and "dodge" not in props:
        props["dodge"] = -(weight // 3000)
    item: dict = {
        "id": path.stem,
        "name": name,
        "aliases": aliases,
        "armor_type": armor_type,
        "armor_prop": props,
    }
    if weight:
        item["weight"] = weight
    for key in ("value", "rigidity"):
        v = _parse_set_kv(body, key)
        if v and v.isdigit():
            item[key] = int(v)
    for key in ("material", "unit"):
        v = _parse_set_kv(body, key)
        if v:
            item[key] = v
    long_v = _parse_set_kv(body, "long")
    if long_v:
        item["long"] = long_v  # 多行/颜色码可能不全，人工校验
    item["_path"] = str(path.relative_to(_REPO_ROOT))
    item["_postpone"] = _detect_postpone(text, body)
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description="提取 LPC 护甲数据 -> ItemDef YAML 草表")
    ap.add_argument("globs", nargs="*", help="LPC 文件/目录（默认 clone/armor+d/*/obj）")
    ap.add_argument("--out", default="-", help="输出文件（- = stdout）")
    args = ap.parse_args()

    if args.globs:
        files: list[Path] = []
        for g in args.globs:
            p = Path(g)
            files.extend(p.rglob("*.c") if p.is_dir() else [p])
    else:
        root = _REPO_ROOT
        files = list((root / "clone/armor").glob("*.c"))
        files += list((root / "d").glob("*/obj/*.c"))

    items: list[dict] = []
    skipped = 0
    for f in sorted(files):
        item = parse_armor(f)
        if item is None:
            skipped += 1
            continue
        items.append(item)

    out = yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=1000)
    if args.out == "-":
        sys.stdout.write(out)
    else:
        Path(args.out).write_text(out, encoding="utf-8")
    print(f"# 提取 {len(items)} 个护甲，跳过 {skipped} 个非护甲文件", file=sys.stderr)
    postpone_count = sum(1 for i in items if i.get("_postpone"))
    print(f"# 标注后置 {postpone_count} 个（待人工校验）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
