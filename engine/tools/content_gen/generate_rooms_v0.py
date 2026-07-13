"""M3-1 完整雪山派房间 v0 生成（ADR-0036，kill criteria 5 第 4 轮）。

单独脚本：生成全部 20 房间 v0（对照 LPC d/xueshan/*.c）。

第 4 轮强化（方向 A）：注入已知 20 房间 id + 11 NPC id 列表，让 LLM 只保留
范围内的 exits/objects，消除幻觉引用（第 3 轮 rooms 63.1% 主因是 LPC 源码
exits/objects 指向范围外房间/NPC，v1 人工裁剪了）。

用法：PYTHONPATH=src python tools/content_gen/generate_rooms_v0.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml

# 让 import generate_v0 可用（取 NPCS 列表）
sys.path.insert(0, str(Path(__file__).parent))

from generate_v0 import NPCS  # noqa: E402

from xkx.content_gen.generate import generate_room  # noqa: E402
from xkx.content_gen.llm_client import VolcanoArkClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
OUT = ROOT / "tools/content_gen/output/xueshan_full_v0"

ROOMS: list[tuple[str, Path]] = [
    # 子任务 1-3 子集（8 房间，第 1 轮已生成 v0，第 2 轮完整覆盖重生成）
    ("xueshan/dshanlu", REPO / "d/xueshan/dshanlu.c"),
    ("xueshan/shanmen", REPO / "d/xueshan/shanmen.c"),
    ("xueshan/guangchang", REPO / "d/xueshan/guangchang.c"),
    ("xueshan/frontyard", REPO / "d/xueshan/frontyard.c"),
    ("xueshan/yanwu", REPO / "d/xueshan/yanwu.c"),
    ("xueshan/zoulang", REPO / "d/xueshan/zoulang.c"),
    ("xueshan/jingang", REPO / "d/xueshan/jingang.c"),
    ("xueshan/chufang", REPO / "d/xueshan/chufang.c"),
    # 子任务 4 新增（12 房间）
    ("xueshan/dumudian", REPO / "d/xueshan/dumudian.c"),
    ("xueshan/changlang", REPO / "d/xueshan/changlang.c"),
    ("xueshan/dadian", REPO / "d/xueshan/dadian.c"),
    ("xueshan/hongdian", REPO / "d/xueshan/hongdian.c"),
    ("xueshan/songjing", REPO / "d/xueshan/songjing.c"),
    ("xueshan/jingtang", REPO / "d/xueshan/jingtang.c"),
    ("xueshan/sengshe", REPO / "d/xueshan/sengshe.c"),
    ("xueshan/luyeyuan", REPO / "d/xueshan/luyeyuan.c"),
    ("xueshan/wangyou", REPO / "d/xueshan/wangyou.c"),
    ("xueshan/beilu", REPO / "d/xueshan/beilu.c"),
    ("xueshan/houyuan", REPO / "d/xueshan/houyuan.c"),
    ("xueshan/angqian", REPO / "d/xueshan/angqian.c"),
]

# 第 4 轮强化（方向 A）：已知 id 列表，注入 prompt 做范围裁剪
ROOM_IDS = [rid for rid, _ in ROOMS]
NPC_IDS = [nid for nid, _ in NPCS]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = VolcanoArkClient()
    print(f"[generate_rooms_v0] model={client.model} out={OUT}")
    print(f"  已知房间 id ({len(ROOM_IDS)}) + NPC id ({len(NPC_IDS)}) 注入范围裁剪")
    rooms: list[dict] = []
    for room_id, lpc in ROOMS:
        print(f"  ROOM {room_id} ...", flush=True)
        try:
            rooms.append(
                generate_room(
                    client,
                    lpc.read_text(encoding="utf-8", errors="replace"),
                    room_id,
                    ROOM_IDS,
                    NPC_IDS,
                )
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {room_id}: {e}")
    path = OUT / "rooms.yaml"
    path.write_text(
        yaml.safe_dump(rooms, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"  -> rooms.yaml ({len(rooms)} 条)")
    print("[generate_rooms_v0] done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
