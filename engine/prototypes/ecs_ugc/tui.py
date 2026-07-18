"""ECS / 继承 / Feature 三模型 UGC 手感原型 TUI（throwaway）。

运行：just proto-ecs-ugc
"""

from __future__ import annotations

import sys
import termios
import tty
from pathlib import Path

# 允许直接 python prototypes/ecs_ugc/tui.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import Friction, Snapshot, make_worlds  # noqa: E402

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
RED = "\x1b[31m"
YEL = "\x1b[33m"
GRN = "\x1b[32m"

QUESTION = (
    "问题：UGC 组合实体 / 热挂能力 / 跨实体查询时，"
    "ECS vs 继承 vs Feature 混入的摩擦差在哪？"
)


def _cost_color(cost: str) -> str:
    return {"low": GRN, "medium": YEL, "high": RED, "blocked": RED}.get(cost, "")


def _read_key() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x03":  # Ctrl-C
            return "q"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render(model_key: str, snap: Snapshot) -> None:
    print("\033[2J\033[H", end="")
    print(f"{BOLD}PROTOTYPE · ecs_ugc{RESET}  {DIM}{QUESTION}{RESET}")
    print()
    models = ["ecs", "inheritance", "feature"]
    tabs = []
    for i, m in enumerate(models, 1):
        label = f"[{i}] {m}"
        tabs.append(f"{BOLD}{label}{RESET}" if m == model_key else f"{DIM}{label}{RESET}")
    print("  ".join(tabs))
    print()

    print(f"{BOLD}entities{RESET}  {DIM}selected={snap.selected}{RESET}")
    if not snap.entities:
        print(f"  {DIM}(empty — 按 g/m/c 生成){RESET}")
    for e in snap.entities:
        mark = ">" if e["selected"] else " "
        parts = ",".join(e["parts"])
        # 压缩 state 一行
        state = e["state"]
        brief = _brief_state(state)
        print(f"  {mark} id={e['id']}  {BOLD}{e['kind']}{RESET}  [{parts}]")
        print(f"      {DIM}{brief}{RESET}")

    print()
    print(f"{BOLD}last query{RESET}")
    if snap.last_query:
        print(f"  {', '.join(snap.last_query)}")
    else:
        print(f"  {DIM}(none){RESET}")

    print()
    print(f"{BOLD}friction{RESET}  {DIM}(最近操作的架构代价){RESET}")
    if not snap.friction:
        print(f"  {DIM}(none yet){RESET}")
    for fr in snap.friction[-5:]:
        print(_fmt_friction(fr))

    print()
    print(f"{BOLD}log{RESET}")
    for line in snap.log[-4:] or [f"{DIM}(none){RESET}"]:
        print(f"  {DIM}{line}{RESET}" if not line.startswith("BLOCKED") else f"  {RED}{line}{RESET}")

    print()
    print(
        f"{BOLD}[1/2/3]{RESET}{DIM}模型  {RESET}"
        f"{BOLD}[g]{RESET}{DIM}守卫  {RESET}"
        f"{BOLD}[m]{RESET}{DIM}商人  {RESET}"
        f"{BOLD}[c]{RESET}{DIM}守卫+商人  {RESET}"
        f"{BOLD}[p]{RESET}{DIM}挂毒  {RESET}"
        f"{BOLD}[r]{RESET}{DIM}可骑乘  {RESET}"
    )
    print(
        f"{BOLD}[q]{RESET}{DIM}卖家  {RESET}"
        f"{BOLD}[f]{RESET}{DIM}战斗者  {RESET}"
        f"{BOLD}[l]{RESET}{DIM}活物  {RESET}"
        f"{BOLD}[t]{RESET}{DIM}tick  {RESET}"
        f"{BOLD}[n]{RESET}{DIM}下一实体  {RESET}"
        f"{BOLD}[x]{RESET}{DIM}退出{RESET}"
    )


def _brief_state(state: dict) -> str:
    if "props" in state and "features" in state:
        hp = state["props"].get("hp")
        feats = ",".join(state["features"])
        return f"hp={hp} features={feats}"
    if "hp" in state:
        extra = []
        if "rage" in state:
            extra.append(f"rage={state['rage']}")
        if "stock" in state:
            extra.append(f"stock={state['stock']}")
        if "poison_ticks" in state:
            extra.append(f"poison={state['poison_ticks']}")
        return f"hp={state['hp']}" + ((" " + " ".join(extra)) if extra else "")
    # ECS
    bits = []
    for k, v in state.items():
        if k == "Identity":
            bits.append(v.get("name", "?"))
        elif k == "Vitals":
            bits.append(f"hp={v.get('hp')}")
        elif k == "Combat":
            bits.append(f"rage={v.get('rage')}")
        elif k == "Shop":
            bits.append(f"stock={v.get('stock')}")
        elif k == "Poisoned":
            bits.append(f"poison={v.get('ticks_left')}")
        elif k == "Rideable":
            bits.append("rideable")
    return " ".join(bits)


def _fmt_friction(fr: Friction) -> str:
    col = _cost_color(fr.cost)
    return f"  {col}{BOLD}{fr.cost:7}{RESET} {BOLD}{fr.action}{RESET}  {fr.note}"


def main() -> None:
    worlds = make_worlds()
    model_key = "ecs"
    _render(model_key, worlds[model_key].snapshot())

    while True:
        key = _read_key()
        w = worlds[model_key]

        if key in ("x", "Q", "\x04"):
            print("\nbye.")
            return
        if key == "1":
            model_key = "ecs"
        elif key == "2":
            model_key = "inheritance"
        elif key == "3":
            model_key = "feature"
        elif key == "g":
            w.spawn_guard()
        elif key == "m":
            w.spawn_merchant()
        elif key == "c":
            w.spawn_guard_merchant()
        elif key == "p":
            w.attach_poison()
        elif key == "r":
            w.attach_rideable()
        elif key == "q":
            w.query_sellers()
        elif key == "f":
            w.query_combatants()
        elif key == "l":
            w.query_living()
        elif key == "t":
            w.tick()
        elif key == "n":
            w.select_next()
        # 忽略未知键

        _render(model_key, worlds[model_key].snapshot())


if __name__ == "__main__":
    main()
