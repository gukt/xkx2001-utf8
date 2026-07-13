"""M3-1 完整雪山派房间 v0 生成（ADR-0036，kill criteria 5 第 2 轮）。

单独脚本：生成全部 20 房间 v0（对照 LPC d/xueshan/*.c）。
第 2 轮扩展到完整雪山派（子任务 1-3 的 8 房间 + 子任务 4 的 12 新房间），
v0/v1 范围一致，公平修订口径。

房间设计（基于 LPC 已读 + 调研）：
- 子任务 1-3（8 房间）：dshanlu/shanmen/guangchang/frontyard/yanwu/zoulang/jingang/chufang
- 子任务 4 新增（12 房间）：
  - dumudian（度母殿）：southdown->yanwu + north->changlang，放 jiamu + zrlama + tonggang
  - changlang（长廊）：north->dadian + south->dumudian，放 jlseng
  - dadian（大殿）：south->changlang，放 jiumo + zhirilama + xiang
  - hongdian（红殿）：southdown->zoulang，放 ling-zhi
  - songjing（诵经堂）：west->yanwu，放 lazhangfo（藏经阁主管）
  - jingtang（经堂）：east->yanwu + north->sengshe，放 fsgelun
  - sengshe（僧舍）：south->jingtang
  - luyeyuan（鹿野苑）：east->wangyou，放 jinlun + lx-jing
  - wangyou（忘忧）：west->luyeyuan
  - beilu（大雪山北麓）：south->dshanlu，放 hua（血刀门跨界）
  - houyuan（后院）：south->jingang + north->angqian
  - angqian（ Ang前）：south->houyuan

用法：PYTHONPATH=src python tools/content_gen/generate_rooms_v0.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml

from xkx.content_gen.generate import generate_room
from xkx.content_gen.llm_client import VolcanoArkClient

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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = VolcanoArkClient()
    print(f"[generate_rooms_v0] model={client.model} out={OUT}")
    rooms: list[dict] = []
    for room_id, lpc in ROOMS:
        print(f"  ROOM {room_id} ...")
        try:
            rooms.append(
                generate_room(client, lpc.read_text(encoding="utf-8", errors="replace"), room_id)
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
