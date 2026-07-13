"""第 3 轮断点续跑：只生成 skills + quests（NPC 已生成，rooms 用 generate_rooms_v0.py）。

背景：第 3 轮 generate_v0.py 跑完 11 NPC + 3 skill 后被会话切换停掉。
NPC 已写入 npcs.yaml（质量验证通过：gender 中文 + inquiry 单行），无需重跑。
本脚本只续跑 skills（11）+ quests（6），rooms 由 generate_rooms_v0.py 单独跑。

用法::

    cd engine && PYTHONPATH=src .venv/bin/python -u tools/content_gen/generate_v0_resume.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# 让 import generate_v0 可用（tools/content_gen 加入 sys.path）
sys.path.insert(0, str(Path(__file__).parent))

from generate_v0 import OUT, QUESTS, SKILLS, _dump_list  # noqa: E402

from xkx.content_gen.generate import generate_quest, generate_skill  # noqa: E402
from xkx.content_gen.llm_client import VolcanoArkClient  # noqa: E402


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = VolcanoArkClient()
    print(f"[resume] model={client.model} out={OUT}")

    skills: list[dict] = []
    for sid, lpc in SKILLS:
        print(f"  SKILL {sid} ...", flush=True)
        try:
            skills.append(
                generate_skill(client, lpc.read_text(encoding="utf-8", errors="replace"), sid)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {sid}: {e}")
    _dump_list(OUT, "skills.yaml", skills)

    quests: list[dict] = []
    for qid, lpc in QUESTS:
        print(f"  QUEST {qid} ...", flush=True)
        try:
            quests.append(
                generate_quest(client, lpc.read_text(encoding="utf-8", errors="replace"), qid)
            )
        except Exception as e:  # noqa: BLE001
            print(f"    ERR {qid}: {e}")
    _dump_list(OUT, "quests.yaml", quests)

    print("[resume] done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
