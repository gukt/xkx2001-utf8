"""M3-1 子任务 4 批量 v0 生成脚本（ADR-0036）。

调火山方舟 deepseek-v4-flash 从 LPC 源生成雪山派完整内容的 v0 草稿，落盘到
``tools/content_gen/output/xueshan_full_v0/``。人工修订为 v1（落盘
``xueshan_full_v1/``）后用 ``measure_revision`` 度量 semantic_ratio（kill
criteria 5 第 2 轮数据）。

本轮内容清单（对照 LPC）：
- 6 NPC：3 师傅（ling-zhi/jinlun/jiumo）+ 3 任务 giver（jiamu/fsgelun/lazhangfo）
- 8 武学：dashou-yin/shenkongxing/necromancy/riyue-lun/huoyan-dao/
          mingwang-jian/xiaowuxiang/yujiamu-quan
- 3 任务链：jiamu 工资（time-gate）/ fsgelun 法事（多步）/ lazhangfo 藏经（reach_room）
- ~12 新房间（rooms 列表，对照 LPC d/xueshan/*.c）

用法::

    PYTHONPATH=src python tools/content_gen/generate_v0.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml

from xkx.content_gen.generate import (
    generate_item,
    generate_npc,
    generate_quest,
    generate_room,
    generate_skill,
)
from xkx.content_gen.llm_client import VolcanoArkClient

# engine/ = parents[2]（本脚本在 engine/tools/content_gen/）
ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent  # 仓库根（LPC 规格源）
OUT = ROOT / "tools/content_gen/output/xueshan_full_v0"

# NPC：(目标 id, LPC 源路径)。师傅在 kungfu/class/xueshan/，任务 giver 在 d/xueshan/npc/
NPCS: list[tuple[str, Path]] = [
    ("xueshan/npc/ling-zhi", REPO / "kungfu/class/xueshan/ling-zhi.c"),
    ("xueshan/npc/jinlun", REPO / "kungfu/class/xueshan/jinlun.c"),
    ("xueshan/npc/jiumo", REPO / "kungfu/class/xueshan/jiumo.c"),
    ("xueshan/npc/jiamu", REPO / "d/xueshan/npc/jiamu.c"),
    ("xueshan/npc/fsgelun", REPO / "d/xueshan/npc/fsgelun.c"),
    ("xueshan/npc/lazhangfo", REPO / "d/xueshan/npc/lazhangfo.c"),
]

# 武学：(skill_id, LPC 源路径)
SKILLS: list[tuple[str, Path]] = [
    ("dashou-yin", REPO / "kungfu/skill/dashou-yin.c"),
    ("shenkongxing", REPO / "kungfu/skill/shenkongxing.c"),
    ("necromancy", REPO / "kungfu/skill/necromancy.c"),
    ("riyue-lun", REPO / "kungfu/skill/riyue-lun.c"),
    ("huoyan-dao", REPO / "kungfu/skill/huoyan-dao.c"),
    ("mingwang-jian", REPO / "kungfu/skill/mingwang-jian.c"),
    ("xiaowuxiang", REPO / "kungfu/skill/xiaowuxiang.c"),
    ("yujiamu-quan", REPO / "kungfu/skill/yujiamu-quan.c"),
]

# 任务链：(quest_id, LPC giver NPC 源路径)
QUESTS: list[tuple[str, Path]] = [
    ("xueshan/quest/jiamu", REPO / "d/xueshan/npc/jiamu.c"),
    ("xueshan/quest/fsgelun", REPO / "d/xueshan/npc/fsgelun.c"),
    ("xueshan/quest/lazhangfo", REPO / "d/xueshan/npc/lazhangfo.c"),
]

# 房间：(room_id, LPC 源路径)。对照 LPC d/xueshan/*.c，由房间调研结果填。
# 现有 8 房间（dshanlu/shanmen/guangchang/frontyard/yanwu/zoulang/jingang/chufang）
# 不重复生成。新增 ~12 房间衔接 + 放置 3 师傅。
ROOMS: list[tuple[str, Path]] = [
    # 占位：待房间调研 agent 结果填入
]

# 物品：本轮按需生成（如经书/法器），默认空
ITEMS: list[tuple[str, Path]] = []


def _dump_list(out_dir: Path, name: str, entries: list[dict]) -> None:
    """落盘 entry list 到 YAML（覆盖写，非追加；批量生成一次性写全）。"""
    path = out_dir / name
    path.write_text(
        yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"  -> {path.name} ({len(entries)} 条)")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = VolcanoArkClient()
    print(f"[generate_v0] model={client.model} out={OUT}")

    npcs: list[dict] = []
    for npc_id, lpc in NPCS:
        print(f"  NPC {npc_id} ...")
        try:
            src = lpc.read_text(encoding="utf-8", errors="replace")
            npcs.append(generate_npc(client, src, npc_id))
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {npc_id}: {e}")
    _dump_list(OUT, "npcs.yaml", npcs)

    skills: list[dict] = []
    for skill_id, lpc in SKILLS:
        print(f"  SKILL {skill_id} ...")
        try:
            skills.append(
                generate_skill(client, lpc.read_text(encoding="utf-8", errors="replace"), skill_id)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {skill_id}: {e}")
    _dump_list(OUT, "skills.yaml", skills)

    quests: list[dict] = []
    for quest_id, lpc in QUESTS:
        print(f"  QUEST {quest_id} ...")
        try:
            quests.append(
                generate_quest(client, lpc.read_text(encoding="utf-8", errors="replace"), quest_id)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {quest_id}: {e}")
    _dump_list(OUT, "quests.yaml", quests)

    rooms: list[dict] = []
    for room_id, lpc in ROOMS:
        print(f"  ROOM {room_id} ...")
        try:
            rooms.append(
                generate_room(client, lpc.read_text(encoding="utf-8", errors="replace"), room_id)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {room_id}: {e}")
    _dump_list(OUT, "rooms.yaml", rooms)

    items: list[dict] = []
    for item_id, lpc in ITEMS:
        print(f"  ITEM {item_id} ...")
        try:
            items.append(
                generate_item(client, lpc.read_text(encoding="utf-8", errors="replace"), item_id)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {item_id}: {e}")
    _dump_list(OUT, "items.yaml", items)

    print("[generate_v0] done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
