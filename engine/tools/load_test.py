"""T10 1000+100 集成测试压测脚本（kill criteria 3 完整判定）。

构建 1000 实体 + 100 并发会话 + 50 活跃战斗对 + 50 EffectComp，跑 N tick，
用 TickProfiler 测量 per-System compute，验证 tick compute<100ms + 存档不阻塞。

非均匀 tick（CLAUDE.md 不变量）：tick=1s + compute<100ms。
go/no-go：tick p99 < 100ms -> GO；否则 NO-GO（触发 kill criteria 3/6）。

async 模式：StorageSystem offload persist 到线程（asyncio.to_thread），tick p99
不含 persist 时间（fire-and-forget）。即使全量 checkpoint persist 耗时 >100ms，
tick 仍 <100ms（offload 生效）。

用法::

    python tools/load_test.py              # 默认 1000+100 跑 300 tick
    python tools/load_test.py --json       # JSON 输出
    python tools/load_test.py --ticks 100  # 自定义 tick 数
    python tools/load_test.py --scale 500  # 降级 500+50（kill criteria 3 触发时）

[12](../../docs/xkx-arch/12-阶段1-核心循环实施计划.md) T10
[ADR-0012](../../docs/adr/ADR-0012-performance-microbenchmark.md) μs 基准
[ADR-0022](../../docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) 存档 offload
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from xkx.runtime.components import (  # noqa: E402
    Attributes,
    CombatState,
    EffectComp,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.conditions import ConditionSystem  # noqa: E402
from xkx.runtime.connection import ConnectionSystem, SessionState  # noqa: E402
from xkx.runtime.ecs import World  # noqa: E402
from xkx.runtime.engine import CombatBridge, Engine  # noqa: E402
from xkx.runtime.profiler import TickProfiler  # noqa: E402
from xkx.runtime.schema import SchemaRegistry  # noqa: E402
from xkx.runtime.storage import JsonFileBackend, StorageSystem  # noqa: E402

TICK_BUDGET_MS = 100  # CLAUDE.md 不变量 compute<100ms


@dataclass
class LoadTestConfig:
    """压测配置。

    1000 在线 = 1000 玩家会话（04 §一立场 6，MAX_USERS=50 的 20 倍）。
    100 并发 = 100 同时活跃命令（tick compute 不含命令处理，不体现于此）。
    """

    n_rooms: int = 50
    n_npcs: int = 200
    n_players: int = 1000  # 1000 在线玩家
    n_fighters: int = 50  # 活跃战斗对数（player <-> npc 互打）
    n_effects: int = 50
    n_sessions: int = 1000  # 1000 会话（1000 在线）
    ticks: int = 300
    persist_interval: int = 30
    checkpoint_interval: int = 10
    combat_seed_base: int = 42

    @property
    def total_entities(self) -> int:
        return self.n_rooms + self.n_npcs + self.n_players + self.n_effects

    @classmethod
    def scaled(cls, scale: int) -> LoadTestConfig:
        """按 scale 降级（500+50 等，kill criteria 3 触发时）。"""
        r = scale / 1000
        return cls(
            n_rooms=int(50 * r),
            n_npcs=int(200 * r),
            n_players=int(1000 * r),
            n_fighters=int(50 * r),
            n_effects=int(50 * r),
            n_sessions=int(1000 * r),
        )


def build_load_world(config: LoadTestConfig) -> tuple[World, list[int]]:
    """构建压测世界：房间 + NPC + 玩家 + 战斗对 + EffectComp。"""
    schema = SchemaRegistry.with_builtins()
    world = World(schema)
    room_ids = [f"room{i}" for i in range(config.n_rooms)]

    # 房间
    for rid in room_ids:
        eid = world.new_entity()
        world.add(eid, RoomComp(room_id=rid, short=rid, long=rid))

    # NPC
    npc_start = world._next_id  # type: ignore[attr-defined]
    for i in range(config.n_npcs):
        eid = world.new_entity()
        world.add(eid, Identity(name=f"npc{i}", prototype_id=f"npc{i}"))
        world.add(eid, Position(room_id=room_ids[i % config.n_rooms]))
        world.add(eid, Attributes(str_=20, dex_=20, int_=20, con_=20))
        world.add(
            eid, Vitals(qi=200, max_qi=200, eff_qi=200, max_jingli=100, jingli=100)
        )
        world.add(eid, Progression(combat_exp=500))
        world.add(eid, Skills(levels={"unarmed": 30, "dodge": 20}))
        world.add(eid, CombatState())
        world.add(eid, NpcBehavior(attitude="aggressive"))

    # 玩家
    player_eids: list[int] = []
    for i in range(config.n_players):
        eid = world.new_entity()
        world.add(
            eid, Identity(name=f"player{i}", is_player=True, prototype_id="player")
        )
        world.add(eid, Position(room_id=room_ids[i % config.n_rooms]))
        world.add(eid, Attributes(str_=20, dex_=20, int_=20, con_=20))
        world.add(
            eid, Vitals(qi=200, max_qi=200, eff_qi=200, max_jingli=100, jingli=100)
        )
        world.add(eid, Progression(combat_exp=500))
        world.add(eid, Skills(levels={"unarmed": 30, "dodge": 20}))
        world.add(eid, CombatState())
        world.add(eid, Inventory())
        world.add(eid, Marks())
        world.add(eid, QuestLog())
        player_eids.append(eid)

    # 战斗对：n_fighters 个 player <-> npc 互打
    for i in range(config.n_fighters):
        peid = player_eids[i]
        npc_eid = npc_start + i
        p_cs = world.get(peid, CombatState)
        n_cs = world.get(npc_eid, CombatState)
        if p_cs and n_cs:
            p_cs.is_fighting = True
            p_cs.enemy_ids = [npc_eid]
            n_cs.is_fighting = True
            n_cs.enemy_ids = [peid]

    # EffectComp（持续效果，ConditionSystem 处理）
    for i in range(config.n_effects):
        eid = world.new_entity()
        target = player_eids[i % len(player_eids)]
        world.add(
            eid,
            EffectComp(
                effect_id=f"eff{i}",
                kind="poison",
                target_id=target,
                amount=5,
                duration=config.ticks + 100,  # 不过期，全程触发
                tick_interval=1,
                next_tick=1,
            ),
        )

    return world, player_eids


def build_engine(
    world: World, config: LoadTestConfig, storage_root: str
) -> tuple[Engine, ConnectionSystem]:
    """构建 Engine + 注册 System。

    注册 ConditionSystem / CombatBridge / StorageSystem / ConnectionSystem。
    """
    # window 够大避免截断（ticks * system 数 * 2，留余量）
    window = max(500, config.ticks * 10)
    profiler = TickProfiler(enabled=True, window=window)
    engine = Engine(world, profiler=profiler)
    engine.add_system(ConditionSystem())
    engine.add_system(CombatBridge(seed_base=config.combat_seed_base))
    backend = JsonFileBackend(storage_root)
    storage = StorageSystem(
        backend,
        schema=world._schema,  # type: ignore[arg-type]
        persist_interval=config.persist_interval,
        checkpoint_interval=config.checkpoint_interval,
    )
    engine.add_system(storage)
    conn = ConnectionSystem()
    engine.add_system(conn)
    return engine, conn


def build_sessions(
    conn: ConnectionSystem, player_eids: list[int], n_sessions: int
) -> None:
    """创建 n_sessions 个 ACTIVE 会话（绕过 activate 避免造 token，直接设状态）。"""
    for i in range(n_sessions):
        sid = f"session{i}"
        session = conn.create_session(sid)
        session.account_id = f"acct{i}"
        session.body_eid = player_eids[i % len(player_eids)]
        session.state = SessionState.ACTIVE
        session.last_active = time.time()


def _percentile(sorted_us: list[int], pct: float) -> int:
    if not sorted_us:
        return 0
    idx = min(len(sorted_us) - 1, int(len(sorted_us) * pct))
    return sorted_us[idx]


@dataclass
class LoadTestReport:
    """压测报告。"""

    config: LoadTestConfig
    tick_count: int
    tick_p50_us: int
    tick_p99_us: int
    tick_max_us: int
    tick_mean_us: float
    per_system: list[dict]
    persist_cost_p99_ms: float
    go: bool
    reason: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        lines = ["=== T10 1000+100 集成测试报告 ==="]
        c = self.config
        lines.append(
            f"配置: {c.total_entities} 实体 "
            f"({c.n_rooms} 房间 + {c.n_npcs} NPC + {c.n_players} 玩家 + "
            f"{c.n_effects} Effect) + {c.n_sessions} 会话 + {c.n_fighters} 战斗对"
        )
        lines.append(f"ticks: {self.tick_count}")
        lines.append("")
        lines.append("tick compute (μs):")
        lines.append(f"  p50:  {self.tick_p50_us}")
        lines.append(f"  p99:  {self.tick_p99_us}")
        lines.append(f"  max:  {self.tick_max_us}")
        lines.append(f"  mean: {self.tick_mean_us:.0f}")
        lines.append("")
        lines.append("per-System (μs):")
        lines.append(
            f"  {'System':<20} {'mean':>8} {'p99':>8} {'max':>8} "
            f"{'total(ms)':>10} {'ticks':>6} {'%tick':>6}"
        )
        for s in self.per_system:
            lines.append(
                f"  {s['system_name']:<20} {s['mean_us']:>8.0f} "
                f"{s['p99_us']:>8.0f} {s['max_us']:>8} "
                f"{s['total_us'] / 1000:>10.1f} {s['ticks']:>6} {s['pct_tick']:>5.0f}%"
            )
        lines.append("")
        lines.append(
            f"存档 offload: 全量 persist p99={self.persist_cost_p99_ms:.1f}ms "
            f"(async to_thread，tick p99 不含 persist)"
        )
        lines.append("")
        p99_ms = self.tick_p99_us / 1000
        verdict = "GO" if self.go else "NO-GO"
        lines.append(
            f"判定: {verdict} (tick p99={p99_ms:.1f}ms, 预算<{TICK_BUDGET_MS}ms)"
        )
        lines.append(f"  {self.reason}")
        return "\n".join(lines)


async def run_load_test(config: LoadTestConfig) -> LoadTestReport:
    """跑压测（async：StorageSystem offload 生效，persist 不阻塞 tick）。"""
    with tempfile.TemporaryDirectory() as tmp:
        world, player_eids = build_load_world(config)
        engine, conn = build_engine(world, config, tmp)
        build_sessions(conn, player_eids, config.n_sessions)

        tick_times: list[int] = []
        for _ in range(config.ticks):
            start = time.perf_counter_ns()
            engine.tick()
            elapsed_us = (time.perf_counter_ns() - start) // 1000
            tick_times.append(elapsed_us)
            # 让 persist task 有机会跑（模拟事件循环 tick 间隙）
            await asyncio.sleep(0)

        # per-System 报告
        summary = engine.profiler.report().system_summary()
        per_system = [asdict(s) for s in summary]

        # 全量 persist 耗时（确认 offload 必要性）
        storage = engine.get_system("StorageSystem")
        assert storage is not None
        persist_times: list[float] = []
        for _ in range(5):
            storage.mark_all_dirty(world)  # type: ignore[attr-defined]
            start = time.perf_counter_ns()
            await storage.persist_now(world)  # type: ignore[attr-defined]
            elapsed_ms = (time.perf_counter_ns() - start) / 1e6
            persist_times.append(elapsed_ms)
        persist_times.sort()
        persist_p99_ms = persist_times[-1]

        sorted_times = sorted(tick_times)
        n = len(sorted_times)
        p50 = _percentile(sorted_times, 0.50)
        p99 = _percentile(sorted_times, 0.99)
        mx = sorted_times[-1] if sorted_times else 0
        mean = sum(sorted_times) / n if n else 0.0

        budget_us = TICK_BUDGET_MS * 1000
        go = p99 < budget_us
        if go:
            reason = (
                f"tick p99 {p99 / 1000:.1f}ms < {TICK_BUDGET_MS}ms 预算，"
                f"存档 offload 生效（persist p99 {persist_p99_ms:.1f}ms 在后台）"
            )
        else:
            reason = (
                f"tick p99 {p99 / 1000:.1f}ms >= {TICK_BUDGET_MS}ms，"
                f"触发 kill criteria 3/6（降级 500+50 或优化热路径）"
            )

        return LoadTestReport(
            config=config,
            tick_count=config.ticks,
            tick_p50_us=p50,
            tick_p99_us=p99,
            tick_max_us=mx,
            tick_mean_us=mean,
            per_system=per_system,
            persist_cost_p99_ms=persist_p99_ms,
            go=go,
            reason=reason,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T10 1000+100 集成测试压测")
    parser.add_argument("--ticks", type=int, default=300, help="tick 数（默认 300）")
    parser.add_argument("--scale", type=int, default=1000, help="规模（1000 或 500）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    if args.scale == 1000:
        config = LoadTestConfig(ticks=args.ticks)
    else:
        config = LoadTestConfig.scaled(args.scale)
        config.ticks = args.ticks

    report = asyncio.run(run_load_test(config))
    if args.json:
        print(report.to_json())
    else:
        print(report.to_text())
    return 0 if report.go else 1


if __name__ == "__main__":
    raise SystemExit(main())
