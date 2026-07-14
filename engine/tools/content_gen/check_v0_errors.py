"""检查 v0 生成结果的 4 类高频错误（kill criteria 5 第 3 轮对比工具）。

针对第 2 轮 v0 的 4 类错误，逐项检查 v0 是否改进：
1. id 引用规范：giver/npc_id/exit/objects 是否用完整 xueshan/ 前缀
2. quest 结构：trigger 是否单值、objectives 是否非空
3. item_id 是否英文 id（非中文）
4. 文本字段：long/inquiry 是否单行、gender 是否中文、short 是否含 ANSI 码、
   skill_type 是否误填 force

用法::

    PYTHONPATH=src python tools/content_gen/check_v0_errors.py <v0_dir>

对照第 2 轮 v0（xueshan_full_v0_round2）和第 3 轮 v0 跑，对比错误数。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# re.ASCII：让 \b 只基于 ASCII，HIY 紧跟中文时仍识别为词边界
# （Python 3 默认 Unicode 模式下中文算 \w，HIY大殿NOR 的 \b 会失配）
_ANSI_RE = re.compile(
    r"\b(HIY|NOR|HIG|HIR|RED|HIM|BLU|GRN|MAG|CYN|WHT|YEL|HIB|HIC|HIW)\b",
    re.ASCII,
)


def _check_quests(quests: list[dict]) -> list[str]:
    errs: list[str] = []
    for q in quests:
        qid = q.get("id", "?")
        giver = q.get("giver", "")
        if giver and not giver.startswith("xueshan/npc/"):
            errs.append(f"quest {qid}: giver 非 xueshan/npc/ 前缀: {giver!r}")
        trig = q.get("trigger")
        if not isinstance(trig, str):
            errs.append(f"quest {qid}: trigger 非单值字符串: {type(trig).__name__}")
        objs = q.get("objectives") or []
        # S4 向后兼容：objective 单数合并到 objectives（v1 人工 quests 用单数）
        if not objs and q.get("objective"):
            objs = [q["objective"]]
        if not objs:
            errs.append(f"quest {qid}: objectives 为空")
            continue
        for o in objs:
            kind = o.get("kind", "?")
            npc_id = o.get("npc_id", "")
            if npc_id and not npc_id.startswith("xueshan/npc/"):
                errs.append(
                    f"quest {qid} obj {kind}: npc_id 非 xueshan/npc/: {npc_id!r}"
                )
            item_id = o.get("item_id", "")
            if item_id and not item_id.isascii():
                errs.append(
                    f"quest {qid} obj give_item: item_id 非英文 id: {item_id!r}"
                )
            room_id = o.get("room_id", "")
            if room_id and not room_id.startswith("xueshan/"):
                errs.append(
                    f"quest {qid} obj reach_room: room_id 非 xueshan/: {room_id!r}"
                )
    return errs


def _check_rooms(rooms: list[dict]) -> list[str]:
    errs: list[str] = []
    for r in rooms:
        rid = r.get("id", "?")
        for direction, target in (r.get("exits") or {}).items():
            if not str(target).startswith("xueshan/"):
                errs.append(
                    f"room {rid} exit {direction}: 目标非 xueshan/: {target!r}"
                )
        for obj_id in r.get("objects") or {}:
            if not obj_id.startswith("xueshan/npc/"):
                errs.append(f"room {rid} object: 非 xueshan/npc/: {obj_id!r}")
        long_ = r.get("long", "")
        if isinstance(long_, str) and "\n" in long_:
            errs.append(f"room {rid}: long 含换行（非单行）")
        short = r.get("short", "")
        if isinstance(short, str) and _ANSI_RE.search(short):
            errs.append(f"room {rid}: short 含 ANSI 码: {short!r}")
    return errs


def _check_npcs(npcs: list[dict]) -> list[str]:
    errs: list[str] = []
    for n in npcs:
        nid = n.get("id", "?")
        gender = n.get("gender", "")
        if gender and gender not in ("男性", "女性"):
            errs.append(f"npc {nid}: gender 非中文: {gender!r}")
        for topic, reply in (n.get("inquiry") or {}).items():
            if isinstance(reply, str) and "\n" in reply:
                errs.append(
                    f"npc {nid} inquiry {topic!r}: reply 含换行（非单行）"
                )
        # kneel message 单行检查
        appr = n.get("apprentice") or {}
        kneel = appr.get("kneel") or {}
        msg = kneel.get("message", "")
        if isinstance(msg, str) and "\n" in msg:
            errs.append(f"npc {nid} kneel.message: 含换行（非单行）")
        succ = appr.get("success_message", "")
        if isinstance(succ, str) and "\n" in succ:
            errs.append(f"npc {nid} success_message: 含换行（非单行）")
    return errs


def _check_skills(skills: list[dict]) -> list[str]:
    errs: list[str] = []
    for s in skills:
        sid = s.get("skill_id", "?")
        st = s.get("skill_type", "")
        if st == "force":
            errs.append(f"skill {sid}: skill_type=force（应为 martial）")
    return errs


def check(v0_dir: Path) -> list[str]:
    """返回 v0 目录的 4 类错误清单。"""
    errs: list[str] = []
    for name, fn in (
        ("quests.yaml", _check_quests),
        ("rooms.yaml", _check_rooms),
        ("npcs.yaml", _check_npcs),
        ("skills.yaml", _check_skills),
    ):
        path = v0_dir / name
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if isinstance(data, list):
            errs.extend(fn(data))
    return errs


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    v0_dir = Path(args[0]).resolve() if args else Path(
        "tools/content_gen/output/xueshan_full_v0"
    )
    errs = check(v0_dir)
    print(f"=== v0 错误检查 ({v0_dir.name}) ===")
    print(f"总错误数: {len(errs)}")
    for e in errs:
        print(f"  - {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
