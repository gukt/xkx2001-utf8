"""门派武器数据提取脚本（ADR-0060 决策 6）。

半自动从 LPC 武器 .c 的 create() 提取标量数值 + init_* -> ItemDef YAML 草表。
flag 位掩码逐类型确认（sword/blade |EDGED，hammer/throwing 不合并，其余标
unknown 待人工查 inherit/weapon/<type>.c）。标注后置维度（do_cut/do_lian/
hit_ob/COMBINED_ITEM）。

人工校验重点（脚本不保证全对）：flag 位掩码、weapon_prop 子键完整性、
long 多行/颜色码、去重（em/emei 复制粘贴）。

用法：cd engine && uv run python tools/weapon_extract.py [LPC_GLOB ...] [--out FILE]
默认扫 clone/weapon + clone/unique + d/*/obj 下的 inherit WEAPON 文件。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# flag 合并位（ADR-0060 决策 5，逐类型查 inherit/weapon/<type>.c 的 set("flag",...) 确认）
FLAG_MERGE: dict[str, int | None] = {
    "sword": 4,      # |EDGED (sword.c)
    "blade": 4,      # |EDGED (blade.c)
    "hammer": 0,     # 不合并 (hammer.c)
    "throwing": 0,   # 不合并 (throwing.c)
    "staff": 16,     # |LONG (staff.c)
    "whip": 0,       # 不合并 (whip.c)
    "stick": 16,     # |LONG (stick.c)
    "club": 16,      # |LONG (club.c)
    "axe": 4,        # |EDGED (axe.c)
    "pike": 16,      # |LONG (pike.c)
    "bow": 0,        # 不合并 (bow.c)
    "hook": 16,      # |LONG (hook.c)
    "dagger": 6,     # |EDGED|SECONDARY (dagger.c)
    "fork": 8,       # |POINTED (fork.c)
    # halberd 未查，标 None 待人工查
}

# weapon.h flag 常量名 -> 位值（解析 init_ 第 2 参的符号名）
FLAG_CONSTS: dict[str, int] = {
    "TWO_HANDED": 1,
    "SECONDARY": 2,
    "EDGED": 4,
    "POINTED": 8,
    "LONG": 16,
    "SELF_ACTION": 32,
}

# weapon.h 类型宏 -> skill_type（init_<type> 第 1 参决定）
WEAPON_TYPES = {
    "sword", "blade", "hammer", "whip", "staff", "club", "stick",
    "bow", "axe", "throwing", "halberd", "pike", "dagger", "fork", "hook",
}

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _extract_create_body(text: str) -> str:
    """取 void create() 函数体（到文件末尾或下一个顶层函数定义）。"""
    m = re.search(r"void\s+create\s*\(\s*\)\s*\{", text)
    if not m:
        return ""
    rest = text[m.end():]
    # 简化：取到下一个顶层函数定义（行首 void/int/mapping/string + 标识符 + (）
    end = re.search(r"\n(?:void|int|mapping|string|object|mixed)\s+\w+\s*\(", rest)
    return rest[: end.start()] if end else rest


def _strip_ansi_macros(s: str) -> str:
    """去掉 ANSI 颜色宏（RED/NOR/HIG 等），保留引号内文本。"""
    return re.sub(
        r"\b(?:RED|NOR|HIG|HIY|HIC|HIB|HIM|HIW|BLK|GRN|YEL|BLU|MAG|CYN|WHT|BOLD)\b",
        "",
        s,
    )


def _parse_set_name(body: str) -> tuple[str, list[str]]:
    """set_name(name, ({aliases})) -> (name, aliases)。处理颜色码变体。"""
    m = re.search(
        r'set_name\s*\(\s*(?:[A-Z_]+\s*)?"([^"]+)"(?:\s*[A-Z_]+)?\s*,\s*\(\{([^}]*)\}\)\s*\)',
        body,
    )
    if not m:
        return "", []
    name = m.group(1)
    aliases = [
        a.strip().strip('"').strip("'")
        for a in m.group(2).split(",")
        if a.strip().strip('"').strip("'")
    ]
    return name, aliases


def _parse_init(body: str) -> tuple[str | None, int, str | None]:
    """init_<type>(damage, flag?) -> (type, damage, flag_arg_raw)。

    返回 flag_arg 原始串（符号名或数字或 None）。
    """
    for t in WEAPON_TYPES:
        m = re.search(
            rf"init_{t}\s*\(\s*(\d+)\s*(?:,\s*([A-Z_]+|\d+))?\s*\)", body
        )
        if m:
            return t, int(m.group(1)), m.group(2)
    return None, 0, None


def _parse_set_kv(body: str, key: str) -> str | None:
    """set("key", value) -> value 串（数字或去引号字符串）。"""
    m = re.search(
        rf'set\(\s*"{key}"\s*,\s*(?:[A-Z_]+\s*)?"?([^",)]+?)"?(?:\s*[A-Z_]+)?\s*\)',
        body,
    )
    if not m:
        return None
    return m.group(1).strip()


def _detect_postpone(text: str, body: str) -> list[str]:
    """检测后置维度（ADR-0060 决策 4）。"""
    postpone = []
    if re.search(r"\bCOMBINED_ITEM\b", text[:500]):
        postpone.append("COMBINED_ITEM(堆叠,留方案A)")
    if re.search(r"\b(?:void|int)\s+do_(?:cut|lian|study)\s*\(", text):
        postpone.append("自定义命令(留命令批)")
    if re.search(r"\bhit_ob\s*\(", text):
        postpone.append("hit_ob(留M3招式表)")
    return postpone


def parse_weapon(path: Path) -> dict | None:
    """解析单个 LPC 武器文件 -> ItemDef dict（含 _path/_postpone/_flag_unknown）。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    # 只处理 inherit WEAPON 类型宏的文件（过滤非武器 obj）
    if not re.search(
        r"\binherit\s+(?:SWORD|BLADE|HAMMER|WHIP|STAFF|CLUB|STICK|BOW|"
        r"AXE|THROWING|HALBERD|PIKE|DAGGER|FORK|HOOK|F_HAMMER|F_EQUIP)\b",
        text,
    ) and "init_" not in text:
        return None
    body = _extract_create_body(text)
    if not body:
        return None
    name, aliases = _parse_set_name(body)
    if not name:
        return None
    wtype, damage, flag_arg_raw = _parse_init(body)
    if wtype is None:
        return None  # 非 init_ 武器（纯物品），跳过

    # flag 合并（ADR-0060 决策 5）
    flag_arg = 0
    flag_unknown = False
    if flag_arg_raw is not None:
        flag_arg = FLAG_CONSTS.get(flag_arg_raw, 0) if flag_arg_raw.isalpha() else int(flag_arg_raw)
    merge = FLAG_MERGE.get(wtype)
    if merge is None:
        flag = flag_arg
        flag_unknown = True  # 该类型未确认合并位，待人工查 inherit/weapon/<type>.c
    else:
        flag = flag_arg | merge

    weight_m = re.search(r"set_weight\s*\(\s*(\d+)\s*\)", body)
    item: dict = {
        "id": path.stem,
        "name": name,
        "aliases": aliases,
        "skill_type": wtype,
        "weapon_prop": {"damage": damage} if damage else {},
        "flag": flag,
    }
    if weight_m:
        item["weight"] = int(weight_m.group(1))
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
    if flag_unknown:
        item["_flag_unknown"] = f"init_{wtype} 合并位未确认，查 inherit/weapon/{wtype}.c"
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description="提取 LPC 武器数据 -> ItemDef YAML 草表")
    ap.add_argument(
        "globs",
        nargs="*",
        help="LPC 文件/目录（默认 clone/weapon+clone/unique+d/*/obj）",
    )
    ap.add_argument("--out", default="-", help="输出文件（- = stdout）")
    args = ap.parse_args()

    if args.globs:
        files: list[Path] = []
        for g in args.globs:
            p = Path(g)
            files.extend(p.rglob("*.c") if p.is_dir() else [p])
    else:
        root = _REPO_ROOT
        files = list((root / "clone/weapon").glob("*.c"))
        files += list((root / "clone/unique").glob("*.c"))
        files += list((root / "d").glob("*/obj/*.c"))

    items: list[dict] = []
    skipped = 0
    for f in sorted(files):
        item = parse_weapon(f)
        if item is None:
            skipped += 1
            continue
        items.append(item)

    out = yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=1000)
    if args.out == "-":
        sys.stdout.write(out)
    else:
        Path(args.out).write_text(out, encoding="utf-8")
    print(f"# 提取 {len(items)} 个武器，跳过 {skipped} 个非武器文件", file=sys.stderr)
    postpone_count = sum(1 for i in items if i.get("_postpone"))
    flag_unknown_count = sum(1 for i in items if i.get("_flag_unknown"))
    print(
        f"# 标注后置 {postpone_count} 个，flag 未确认 {flag_unknown_count} 个"
        "（待人工校验）",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
