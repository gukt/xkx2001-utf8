"""任务链扩展测试（M3-1 ADR-0032 决策 3）。

覆盖 QuestObjective 4 kind（give_item/kill_npc/reach_room/fight_win）+ 多步 chain
+ time-gate 可重复 + QuestLog 序列化 + 向后兼容旧 IR。
"""

from __future__ import annotations

from xkx.dsl.ir import compile_quest, compile_scene
from xkx.dsl.layer0 import NpcDef, QuestDef, QuestObjective, QuestReward, RoomDef
from xkx.runtime.commands import (
    Game,
    _quest_objectives,
    ask,
    fight,
    give,
    go,
    kill,
    quest,
)
from xkx.runtime.components import Identity, Marks, Progression, QuestLog, Vitals
from xkx.runtime.serialization import deserialize_component, serialize_component
from xkx.runtime.world import build_world, spawn_player


def _game(
    quest_dicts: list[dict],
    *,
    npc_max_qi: int = 2,
    npc_combat_exp: int = 10,
    npc_skills: dict[str, int] | None = None,
    player_qi: int = 200,
    start_room: str = "test/room1",
    items: set[str] | None = None,
) -> tuple[Game, int]:
    """2 房间 + 1 NPC（room1）+ 玩家（room1），完全可控。

    NPC 默认 max_qi=2（玩家一击触发 fight_win 50% 阈值/击杀）。玩家默认属性
    （spawn_player：unarmed=30/max_qi=200），可调 player_qi 模拟弱玩家。
    """
    rooms = [
        RoomDef(
            id="test/room1",
            short="房一",
            long="测试房一",
            exits={"east": "test/room2"},
            objects={"test/npc": 1},
        ),
        RoomDef(
            id="test/room2", short="房二", long="测试房二", exits={"west": "test/room1"}
        ),
    ]
    npcs = [
        NpcDef(
            id="test/npc",
            name="沙袋",
            aliases=["shadai"],
            max_qi=npc_max_qi,
            max_jing=20,
            max_jingli=20,
            combat_exp=npc_combat_exp,
            skills=npc_skills or {},
        )
    ]
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", start_room, items=items)
    if player_qi != 200:
        vitals = world.get(pid, Vitals)
        if vitals:
            vitals.qi = player_qi
            vitals.max_qi = player_qi
            vitals.eff_qi = player_qi
    quest_idx = {q["id"]: q for q in quest_dicts}
    game = Game(world, room_idx, [], quests=quest_idx)
    # ADR-0039：接入 Engine + CombatBridge（战斗 tick 驱动）+ 治理/恢复 System
    from xkx.runtime.conditions import ConditionSystem
    from xkx.runtime.engine import CombatBridge, Engine
    from xkx.runtime.governance import GovernanceSystem
    from xkx.runtime.heal import HealSystem

    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    game.engine = engine  # type: ignore[attr-defined]
    return game, pid


def _quest(
    qid: str,
    kind: str = "kill_npc",
    *,
    npc_id: str = "test/npc",
    room_id: str = "test/room2",
    item_id: str = "",
    win_threshold: int = 50,
    objectives: list[QuestObjective] | None = None,
    exp: int = 50,
    flag: str = "",
    time_gate: int = 0,
) -> dict:
    """构造 quest IR dict（objectives 优先；否则单 objective）。"""
    if objectives is None:
        objectives = [
            QuestObjective(
                kind=kind,
                npc_id=npc_id,
                room_id=room_id,
                item_id=item_id,
                win_threshold=win_threshold,
            )
        ]
    q = QuestDef(
        id=qid,
        name=qid,
        giver="test/npc",
        trigger="任务",
        objectives=objectives,
        reward=QuestReward(exp=exp, flag=flag, time_gate=time_gate),
    )
    return compile_quest(q)


def test_kill_npc_objective() -> None:
    """kill 击杀 NPC -> 完成 kill_npc objective + exp（对照 fsgelun kill corpse）。"""
    game, pid = _game([_quest("test/kill", "kill_npc", exp=60)])
    ask(game, pid, "沙袋", "任务")
    before = game.world.get(pid, Progression).combat_exp
    msgs = kill(game, pid, "沙袋")
    assert any("完成" in m for m in msgs)
    # kill 本身 +50（_handle_npc_death）+ 任务奖励 +60 + 战斗命中 exp（KIND_EXP，>=0）
    assert game.world.get(pid, Progression).combat_exp >= before + 50 + 60
    assert game.world.get(pid, QuestLog).statuses["test/kill"] == "completed"


def test_reach_room_objective() -> None:
    """go 移动到目标房间 -> 完成 reach_room objective（对照 shanmen go north）。"""
    game, pid = _game(
        [_quest("test/reach", "reach_room", room_id="test/room2", exp=40)]
    )
    ask(game, pid, "沙袋", "任务")
    before = game.world.get(pid, Progression).combat_exp
    msgs = go(game, pid, "east")
    assert any("完成" in m for m in msgs)
    assert game.world.get(pid, Progression).combat_exp == before + 40
    assert game.world.get(pid, QuestLog).statuses["test/reach"] == "completed"


def test_fight_win_objective_npc_survives() -> None:
    """fight 切磋击败 NPC -> 完成 fight_win + 设标记，NPC 不死（对照 darba 点到为止）。"""
    game, pid = _game([_quest("test/fight", "fight_win", flag="引", exp=30)])
    ask(game, pid, "沙袋", "任务")
    msgs = fight(game, pid, "沙袋")
    assert any("完成" in m for m in msgs)
    assert "引" in game.world.get(pid, Marks).flags
    assert game.world.get(pid, QuestLog).statuses["test/fight"] == "completed"
    # NPC 不死（Position 保留，对照 darba 点到为止不杀死）
    npc_eid = None
    for eid in game.world.entities_in_room("test/room1"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            npc_eid = eid
            break
    assert npc_eid is not None


def test_fight_win_player_loses_no_complete() -> None:
    """玩家弱 + NPC 强 -> fight 玩家输，不完成 objective（fight 点到为止不致死）。"""
    q = _quest("test/fight_lose", "fight_win", flag="赢")
    game, pid = _game(
        [q],
        npc_max_qi=200,
        npc_combat_exp=1000,
        npc_skills={"unarmed": 50},
        player_qi=2,
    )
    ask(game, pid, "沙袋", "任务")
    msgs = fight(game, pid, "沙袋")
    assert not any("完成" in m for m in msgs)
    assert game.world.get(pid, QuestLog).statuses["test/fight_lose"] == "in_progress"
    assert "赢" not in game.world.get(pid, Marks).flags


def test_multi_step_chain() -> None:
    """多步 chain：kill_npc -> reach_room，按序完成才发奖（对照 fsgelun 多步）。"""
    q = _quest(
        "test/chain",
        objectives=[
            QuestObjective(kind="kill_npc", npc_id="test/npc"),
            QuestObjective(kind="reach_room", room_id="test/room2"),
        ],
        exp=80,
    )
    game, pid = _game([q])
    ask(game, pid, "沙袋", "任务")
    log = game.world.get(pid, QuestLog)
    assert log.current_step["test/chain"] == 0
    kill(game, pid, "沙袋")  # 步骤 1 完成
    assert log.current_step["test/chain"] == 1
    assert log.statuses["test/chain"] == "in_progress"  # 未全完成
    before = game.world.get(pid, Progression).combat_exp
    msgs = go(game, pid, "east")  # 步骤 2 完成 + 发奖
    assert any("完成" in m for m in msgs)
    assert game.world.get(pid, Progression).combat_exp == before + 80
    assert log.statuses["test/chain"] == "completed"


def test_quest_progress_display() -> None:
    """quest 命令显示多步进度 current_step/total。"""
    q = _quest(
        "test/progress",
        objectives=[
            QuestObjective(kind="kill_npc", npc_id="test/npc"),
            QuestObjective(kind="reach_room", room_id="test/room2"),
        ],
    )
    game, pid = _game([q])
    ask(game, pid, "沙袋", "任务")
    msgs = quest(game, pid, "test/progress")
    assert any("0/2" in m for m in msgs)
    kill(game, pid, "沙袋")
    msgs = quest(game, pid, "test/progress")
    assert any("1/2" in m for m in msgs)


def test_time_gate_cooldown() -> None:
    """time_gate 可重复任务：完成 -> 冷却期 ask 拒绝 -> 推进 tick 可再接（对照 jiamu）。"""
    q = _quest("test/wage", "fight_win", time_gate=100, exp=50)
    game, pid = _game([q])
    ask(game, pid, "沙袋", "任务")
    fight(game, pid, "沙袋")  # fight_win 完成（NPC 不死，可再 ask）
    log = game.world.get(pid, QuestLog)
    assert log.statuses["test/wage"] == "not_started"  # time_gate 重置可再接
    assert log.claimed_at["test/wage"] == 0
    # 立即 ask -> 冷却中（current_tick=0，0-0=0 < 100）
    msgs = ask(game, pid, "沙袋", "任务")
    assert any("冷却中" in m for m in msgs)
    # 推进 tick=100 -> 可再接
    game.world.current_tick = 100
    msgs = ask(game, pid, "沙袋", "任务")
    assert any("接下任务" in m for m in msgs)
    assert log.statuses["test/wage"] == "in_progress"


def test_time_gate_repeatable_reward() -> None:
    """time_gate 可重复领奖：两次完成共领两次 exp。"""
    q = _quest("test/wage2", "fight_win", time_gate=100, exp=50)
    game, pid = _game([q])
    ask(game, pid, "沙袋", "任务")
    fight(game, pid, "沙袋")
    after_first = game.world.get(pid, Progression).combat_exp
    game.world.current_tick = 100
    ask(game, pid, "沙袋", "任务")
    fight(game, pid, "沙袋")
    after_second = game.world.get(pid, Progression).combat_exp
    # 第二次领奖（任务 +50，含战斗命中 exp KIND_EXP）
    assert after_second - after_first >= 50


def test_quest_log_serialization_roundtrip() -> None:
    """QuestLog current_step + claimed_at 序列化往返（ADR-0022 可序列化）。"""
    log = QuestLog()
    log.statuses = {"q1": "in_progress", "q2": "completed"}
    log.current_step = {"q1": 2}
    log.claimed_at = {"q3": 100}
    data = serialize_component(log)
    restored = deserialize_component(QuestLog, data)
    assert restored.statuses == log.statuses
    assert restored.current_step == log.current_step
    assert restored.claimed_at == log.claimed_at


def test_backward_compat_old_ir_single_objective() -> None:
    """旧 IR（objective 单数，无 objectives list）_quest_objectives 兼容解析。"""
    old_ir = {
        "id": "q",
        "objective": {
            "kind": "kill_npc",
            "npc_id": "x",
            "item_id": "",
            "room_id": "",
            "win_threshold": 50,
        },
    }
    objs = _quest_objectives(old_ir)
    assert len(objs) == 1
    assert objs[0]["kind"] == "kill_npc"


def test_give_item_in_multi_step_chain() -> None:
    """give_item objective 在多步 chain 中推进（向后兼容 S4 give_item）。"""
    q = _quest(
        "test/give",
        objectives=[
            QuestObjective(kind="give_item", npc_id="test/npc", item_id="suyou_guan"),
            QuestObjective(kind="reach_room", room_id="test/room2"),
        ],
        exp=70,
    )
    game, pid = _game([q], items={"suyou_guan"})
    ask(game, pid, "沙袋", "任务")
    msgs = give(game, pid, "沙袋", "suyou_guan")
    assert any("完成一步" in m for m in msgs)  # 步骤 1 完成，未全完成
    log = game.world.get(pid, QuestLog)
    assert log.current_step["test/give"] == 1
    assert log.statuses["test/give"] == "in_progress"
