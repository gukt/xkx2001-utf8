"""S3 修订量度量：校验 DSL 场景四级可跑通性 + 度量 v0->v1 修订比例。

四级校验（逐级递进，任一级失败即停并记录）：
  L1 schema load  : pydantic 校验 rooms/npcs/rules YAML
  L2 IR 编译       : compile_scene
  L3 运行时加载    : build_world
  L4 端到端        : go(各方向不抛异常) + kill(resolve_attack) + 确定性重放

修订比例：v0 -> v1 的行级 diff（变化行 / v1 非空行），按文件分别统计后汇总。
缺口台账：收集 v0 中 `# GAP:` 注释（Agent 标注的"想表达但 DSL 不支持"项）。

可复用于 M2 Agent Orchestrator 产出校验。阶段 -1 为 copilot 近似（Agent =
人工驱动的 LLM 调用），M2 接独立 LLM + Langfuse 做真验证（见 ADR-0004）。

用法::

    python tools/measure_revision.py scenes/xueshan_micro
    python tools/measure_revision.py scenes/xueshan_micro --v0 scenes/xueshan_micro/_draft_v0
"""

from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 支持直接 `python tools/measure_revision.py` 运行（不依赖 pip install -e）
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from xkx.dsl.ir import compile_scene  # noqa: E402
from xkx.dsl.layer0 import load_npcs, load_rooms  # noqa: E402
from xkx.dsl.layer1 import load_rules  # noqa: E402
from xkx.runtime.commands import Game, go, kill  # noqa: E402
from xkx.runtime.components import Identity, Position, RoomComp  # noqa: E402
from xkx.runtime.world import build_world, spawn_player  # noqa: E402

GAP_PREFIX = "# GAP:"
SCENE_FILES = ("rooms.yaml", "npcs.yaml", "rules.yaml")


@dataclass
class CheckResult:
    """一级校验结果。"""

    level: str
    ok: bool
    error: str = ""


@dataclass
class FileDiff:
    """单个文件的 v0->v1 diff 统计。"""

    name: str
    v0_lines: int
    v1_lines: int
    changed: int  # 变化行数（增+删，排除 diff 头）
    v0_semantic: int = 0  # 非注释非空行数（v0）
    v1_semantic: int = 0  # 非注释非空行数（v1）
    semantic_changed: int = 0  # 非注释行的变化行数（排除注释重组噪声）


@dataclass
class SceneReport:
    """单个场景的度量报告。"""

    scene: str
    checks: list[CheckResult] = field(default_factory=list)
    file_diffs: list[FileDiff] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def structural_errors(self) -> int:
        """失败的校验级数（0 = 全过）。"""
        return sum(1 for c in self.checks if not c.ok)

    @property
    def revision_ratio(self) -> float:
        """v0->v1 总修订比例 = 总变化行 / v1 总非空行（含注释，受注释重组噪声影响）。"""
        changed = sum(d.changed for d in self.file_diffs)
        v1_nonblank = sum(d.v1_lines for d in self.file_diffs)  # v1_lines 已是非空行数
        return changed / v1_nonblank if v1_nonblank else 0.0

    @property
    def semantic_ratio(self) -> float:
        """v0->v1 语义修订比例 = 非注释行变化 / v1 非注释行（排除注释重组噪声）。

        kill criteria 5（>40% 走弱 / >30% 降级）应以此为准，避免 v0 的 GAP
        标注在 v1 迁移到 ADR 时被误计为"Agent 产出缺陷"。
        """
        changed = sum(d.semantic_changed for d in self.file_diffs)
        v1_sem = sum(d.v1_semantic for d in self.file_diffs)
        return changed / v1_sem if v1_sem else 0.0


def _first_npc_room(rooms: list, npc_defs: list) -> str:
    """第一个含 NPC 的房间 id（用于 kill 校验起点）。"""
    npc_ids = {n.id for n in npc_defs}
    for r in rooms:
        if any(nid in npc_ids for nid in r.objects):
            return r.id
    return rooms[0].id if rooms else ""


def _first_npc_name(game: Game, room_id: str) -> str | None:
    """房间内第一个 NPC 的 name（用于 kill 校验）。"""
    for eid in game.world.entities_in_room(room_id):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return ident.name
    return None


def _build_game(scene_dir: Path, seed_base: int = 0) -> tuple[Game, int, str]:
    """加载场景并构建 game，返回 (game, 玩家 eid, 起点房间 id)。"""
    rooms = load_rooms(scene_dir / "rooms.yaml")
    npcs = load_npcs(scene_dir / "npcs.yaml")
    rules = load_rules(scene_dir / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    start = _first_npc_room(rooms, npcs)
    pid = spawn_player(world, "玩家", start)
    return Game(world, room_idx, rules, seed_base=seed_base), pid, start


def check_scene(scene_dir: Path) -> tuple[list[CheckResult], bool]:
    """四级校验。返回 (结果列表, 是否全过)。"""
    results: list[CheckResult] = []

    # L1 schema load
    try:
        rooms = load_rooms(scene_dir / "rooms.yaml")
        npcs = load_npcs(scene_dir / "npcs.yaml")
        load_rules(scene_dir / "rules.yaml")
        results.append(CheckResult("L1 schema load", True))
    except Exception as e:  # noqa: BLE001
        results.append(CheckResult("L1 schema load", False, f"{type(e).__name__}: {e}"))
        return results, False

    # L2 IR 编译
    try:
        compile_scene(rooms, npcs)
        results.append(CheckResult("L2 IR compile", True))
    except Exception as e:  # noqa: BLE001
        results.append(CheckResult("L2 IR compile", False, f"{type(e).__name__}: {e}"))
        return results, False

    # L3 运行时加载
    try:
        game, pid, start = _build_game(scene_dir)
        results.append(CheckResult("L3 build_world", True))
    except Exception as e:  # noqa: BLE001
        results.append(CheckResult("L3 build_world", False, f"{type(e).__name__}: {e}"))
        return results, False

    # L4 端到端：go + kill + 确定性重放
    try:
        pos = game.world.get(pid, Position)
        assert pos is not None
        room = game.world.get(game.room_entities[pos.room_id], RoomComp)
        # go：从起点对各方向各试一次（每次重置回起点；deny/allow 都算通过，不抛异常即可）
        for direction in list(room.exits.keys()):
            pos.room_id = start
            go(game, pid, direction)
        pos.room_id = start
        # kill：起点房间第一个 NPC
        target = _first_npc_name(game, start)
        if target is None:
            raise RuntimeError("起点房间无 NPC，无法校验 kill")
        kill(game, pid, target)
        # 确定性重放：两个干净 game 各自第一次 kill，messages 须一致
        ga, pa, _ = _build_game(scene_dir, seed_base=0)
        gb, pb, _ = _build_game(scene_dir, seed_base=0)
        msgs_a = kill(ga, pa, target)
        msgs_b = kill(gb, pb, target)
        if msgs_a != msgs_b:
            raise RuntimeError("确定性重放失败：同 seed 两次 kill 结果不一致")
        results.append(CheckResult("L4 e2e (go+kill+replay)", True))
    except Exception as e:  # noqa: BLE001
        results.append(CheckResult("L4 e2e (go+kill+replay)", False, f"{type(e).__name__}: {e}"))
        return results, False

    return results, True


def _count_nonblank(lines: list[str]) -> int:
    return sum(1 for ln in lines if ln.strip())


def _semantic_lines(lines: list[str]) -> list[str]:
    """非空且非纯注释行（过滤行首 # 注释；行内注释所在行保留）。"""
    return [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def measure_revision(v0_dir: Path, v1_dir: Path) -> tuple[list[FileDiff], list[str]]:
    """度量 v0 -> v1 的 diff + 收集 v0 的 GAP 注释。返回 (文件 diff 列表, 缺口列表)。"""
    file_diffs: list[FileDiff] = []
    gaps: list[str] = []
    for name in SCENE_FILES:
        v0_file = v0_dir / name
        v1_file = v1_dir / name
        v0_lines = v0_file.read_text(encoding="utf-8").splitlines() if v0_file.exists() else []
        v1_lines = v1_file.read_text(encoding="utf-8").splitlines() if v1_file.exists() else []
        # GAP 注释来自 v0（Agent 初稿标注的表达力缺口）
        for ln in v0_lines:
            stripped = ln.strip()
            if stripped.startswith(GAP_PREFIX):
                gaps.append(f"{name}: {stripped[len(GAP_PREFIX):].strip()}")
        # 行级 diff（unified_diff，统计 +/- 行，排除 +++/--- 头）
        diff = list(difflib.unified_diff(v0_lines, v1_lines, lineterm=""))
        changed = sum(
            1
            for ln in diff
            if (ln.startswith("+") and not ln.startswith("+++"))
            or (ln.startswith("-") and not ln.startswith("---"))
        )
        # 语义 diff（过滤纯注释行后再 diff，排除注释重组噪声）
        v0_sem = _semantic_lines(v0_lines)
        v1_sem = _semantic_lines(v1_lines)
        sem_diff = list(difflib.unified_diff(v0_sem, v1_sem, lineterm=""))
        sem_changed = sum(
            1
            for ln in sem_diff
            if (ln.startswith("+") and not ln.startswith("+++"))
            or (ln.startswith("-") and not ln.startswith("---"))
        )
        file_diffs.append(
            FileDiff(
                name,
                _count_nonblank(v0_lines),
                _count_nonblank(v1_lines),
                changed,
                len(v0_sem),
                len(v1_sem),
                sem_changed,
            )
        )
    return file_diffs, gaps


def format_report(report: SceneReport) -> str:
    """格式化报告为文本。"""
    lines = [f"=== 场景: {report.scene} ==="]
    for c in report.checks:
        mark = "✓" if c.ok else "✗"
        line = f"  {mark} {c.level}"
        if not c.ok and c.error:
            line += f"  -> {c.error}"
        lines.append(line)
    lines.append(f"  结构性错误级数: {report.structural_errors}")
    lines.append(f"  v0->v1 修订比例（含注释）: {report.revision_ratio:.1%}")
    lines.append(f"  v0->v1 语义修订比例（非注释）: {report.semantic_ratio:.1%}")
    for d in report.file_diffs:
        lines.append(
            f"    {d.name}: v0={d.v0_lines} v1={d.v1_lines}"
            f" 变化={d.changed} 语义={d.semantic_changed}"
        )
    if report.gaps:
        lines.append(f"  表达力缺口台账 ({len(report.gaps)}):")
        for g in report.gaps:
            lines.append(f"    - {g}")
    else:
        lines.append("  表达力缺口台账: (无)")
    return "\n".join(lines)


def run(scene_dir: Path, v0_dir: Path | None = None) -> SceneReport:
    """跑一个场景的完整度量。v0_dir 默认 scene_dir/_draft_v0。"""
    report = SceneReport(scene=scene_dir.name)
    checks, _ = check_scene(scene_dir)
    report.checks = checks
    if v0_dir is None:
        v0_dir = scene_dir / "_draft_v0"
    if v0_dir.exists():
        file_diffs, gaps = measure_revision(v0_dir, scene_dir)
        report.file_diffs = file_diffs
        report.gaps = gaps
    return report


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(__doc__)
        return 2
    scene_dir = Path(args[0]).resolve()
    v0_dir = Path(args[1]).resolve() if len(args) > 1 else None
    if not scene_dir.is_dir():
        print(f"场景目录不存在: {scene_dir}", file=sys.stderr)
        return 2
    report = run(scene_dir, v0_dir)
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
