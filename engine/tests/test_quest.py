"""任务系统单元测试（S4 ADR-0007）：QuestDef + QuestLog + ask/give/quest 命令。"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, ask, give, quest
from xkx.runtime.components import Marks, Progression, QuestLog
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(items: set[str] | None = None) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs, quests)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "玩家", "xueshan/shanmen", items=items)
    return Game(world, room_idx, rules, quests=quest_idx), pid


def test_ask_accept_quest() -> None:
    """ask giver about trigger -> 接任务（status in_progress）。"""
    game, pid = _game()
    msgs = ask(game, pid, "葛伦布", "还愿")
    assert any("接下任务「供奉佛爷」" in m for m in msgs)
    assert game.world.get(pid, QuestLog).statuses.get("xueshan/tribute") == "in_progress"


def test_ask_already_in_progress() -> None:
    """重复 ask trigger -> 提示进行中。"""
    game, pid = _game()
    ask(game, pid, "葛伦布", "还愿")
    msgs = ask(game, pid, "葛伦布", "还愿")
    assert any("进行中" in m for m in msgs)


def test_give_completes_quest_and_rewards() -> None:
    """give 任务物品 -> 完成 quest + 奖励 exp + 设置 reward.flag。"""
    game, pid = _game(items={"suyou_guan"})
    ask(game, pid, "葛伦布", "还愿")
    before_exp = game.world.get(pid, Progression).combat_exp
    msgs = give(game, pid, "葛伦布", "suyou_guan")
    assert any("完成" in m for m in msgs)
    assert game.world.get(pid, QuestLog).statuses.get("xueshan/tribute") == "completed"
    assert game.world.get(pid, Progression).combat_exp == before_exp + 100
    assert "酥" in game.world.get(pid, Marks).flags


def test_ask_completed_shows_done() -> None:
    """任务完成后 ask trigger -> 提示已完成。"""
    game, pid = _game(items={"suyou_guan"})
    ask(game, pid, "葛伦布", "还愿")
    give(game, pid, "葛伦布", "suyou_guan")
    msgs = ask(game, pid, "葛伦布", "还愿")
    assert any("已完成" in m for m in msgs)


def test_quest_list_and_status() -> None:
    """quest 只列进行中（not_started 折叠为可接提示）；quest <id> 查单个。"""
    game, pid = _game()
    # 未接任务时 quest 不列 not_started 详情，只给可接提示
    msgs = quest(game, pid)
    assert not any("供奉佛爷" in m for m in msgs)
    assert any("可接任务" in m for m in msgs)
    ask(game, pid, "葛伦布", "还愿")
    # 接任务后 quest 列出 in_progress
    msgs = quest(game, pid)
    assert any("供奉佛爷" in m for m in msgs)
    assert any("in_progress" in m for m in msgs)
    # quest <id> 查单个
    msgs = quest(game, pid, "xueshan/tribute")
    assert any("in_progress" in m for m in msgs)


def test_quest_unknown_id() -> None:
    """quest 未知 id -> 提示没有。"""
    game, pid = _game()
    msgs = quest(game, pid, "no_such_quest")
    assert any("没有任务" in m for m in msgs)
