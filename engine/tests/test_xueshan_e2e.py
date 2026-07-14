"""端到端：xueshan_micro 场景 -> go(方向绑定守卫) / ask(对话) / give(物品交互) -> kill。

S4 ADR-0005：方向绑定 + 组合谓词完整表达 d/xueshan/shanmen.c valid_leave。
S4 ADR-0006：ask 对话（inquiry）+ give 物品交互（accept_object + set_flag），
  对照 d/xueshan/npc/gelun1.c 的 inquiry + accept_object。
完整交互闭环：give 葛伦布酥油罐 -> set marks/酥 -> go north 放行。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, ask, give, go, kill, take
from xkx.runtime.components import (
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    QuestLog,
    Vitals,
)
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(
    seed_base: int = 0,
    start_room: str = "xueshan/shanmen",
    family: str = "",
    items: set[str] | None = None,
) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs, quests)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room, family=family, items=items)
    game = Game(world, room_idx, rules, quests=quest_idx, seed_base=seed_base)
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


def _gelun_eid(game: Game) -> int:
    for eid in game.world.entities_in_room("xueshan/shanmen"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("no npc in shanmen")


# --- go（S4 ADR-0005 方向绑定 + 组合谓词）---


def test_go_north_denied_by_guard() -> None:
    """无门派无物品无标记 -> north 被 deny（葛伦布在场）。"""
    game, pid = _game()
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/shanmen"
    assert any("供奉" in m for m in msgs)


def test_go_eastdown_allowed() -> None:
    """eastdown 方向不受 north 守卫规则拦截（方向绑定，S4 ADR-0005）。"""
    game, pid = _game()
    msgs = go(game, pid, "eastdown")
    assert game.world.get(pid, Position).room_id == "xueshan/dshanlu"
    assert any("走去" in m for m in msgs)


def test_go_north_allowed_with_family() -> None:
    """雪山派玩家 -> north 放行（family_eq 谓词，LPC 门派放行）。"""
    game, pid = _game(family="雪山派")
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
    assert any("走去" in m for m in msgs)


def test_go_north_allowed_with_item() -> None:
    """持酥油供 -> north 放行（has_item 谓词，LPC present 供奉放行）。"""
    game, pid = _game(items={"suyou_guan"})
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
    assert any("走去" in m for m in msgs)


# --- ask（S4 ADR-0006 对话）---


def test_ask_gelun1_inquiry() -> None:
    """ask 葛伦布 about 烧香 -> inquiry 回复（LPC set("inquiry") + do_huanyuan）。"""
    game, pid = _game()
    msgs = ask(game, pid, "葛伦布", "烧香")
    assert any("孝敬佛爷" in m for m in msgs)


def test_ask_gelun1_quest_trigger() -> None:
    """ask 葛伦布 about 还愿 -> 接任务（quest trigger 优先于 inquiry，ADR-0007）。"""
    game, pid = _game()
    msgs = ask(game, pid, "葛伦布", "还愿")
    assert any("接下任务「供奉佛爷」" in m for m in msgs)
    assert game.world.get(pid, QuestLog).statuses.get("xueshan/tribute") == "in_progress"


def test_ask_unknown_topic() -> None:
    """ask 未知话题 -> NPC 摇头（无 inquiry 条目）。"""
    game, pid = _game()
    msgs = ask(game, pid, "葛伦布", "天气")
    assert any("摇了摇头" in m for m in msgs)


# --- give（S4 ADR-0006 物品交互）---


def test_give_suyou_sets_flag_and_removes_item() -> None:
    """give 葛伦布酥油罐 -> set marks/酥 + 物品移出（LPC accept_object + set_temp）。"""
    game, pid = _game(items={"suyou_guan"})
    msgs = give(game, pid, "葛伦布", "suyou_guan")
    assert any("佛爷保佑" in m for m in msgs)
    # 物品已移出
    assert "suyou_guan" not in game.world.get(pid, Inventory).items
    # 标记已设置
    assert "酥" in game.world.get(pid, Marks).flags


def test_give_wrong_item_no_side_effect() -> None:
    """无匹配 accept_object 规则的物品 -> 默认接受（物品移出，无 set_flag）。

    gelun1 只对 suyou_guan 有 accept_object 规则；其他物品默认接受无副作用。
    """
    game, pid = _game(items={"random_thing"})
    give(game, pid, "葛伦布", "random_thing")
    assert "random_thing" not in game.world.get(pid, Inventory).items
    assert game.world.get(pid, Marks).flags == set()


def test_give_without_item_fails() -> None:
    """give 不持有的物品 -> 提示没有。"""
    game, pid = _game()
    msgs = give(game, pid, "葛伦布", "suyou_guan")
    assert any("没有" in m for m in msgs)


# --- 完整交互闭环（give -> set_flag -> go 放行）---


def test_give_then_go_north_allowed_via_flag() -> None:
    """完整闭环：give 酥油罐 -> set marks/酥 -> 物品移出后仍放行（has_flag 替代 has_item）。

    对照 LPC gelun1.c accept_object 设 marks/酥 + shanmen.c valid_leave 查 marks/酥 放行。
    持酥油时 has_item 放行；give 后物品消耗，has_flag 维持放行。
    S4 核心验证：DSL 能表达"物品交互 -> 状态变更 -> 移动放行"闭环。
    """
    game, pid = _game(items={"suyou_guan"})
    # give 酥油罐 -> 物品移出 + set 酥标记
    give(game, pid, "葛伦布", "suyou_guan")
    assert "suyou_guan" not in game.world.get(pid, Inventory).items
    assert "酥" in game.world.get(pid, Marks).flags
    # 物品已消耗，但有酥标记 -> north 放行（has_flag 放行条件，替代 has_item）
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
    assert any("走去" in m for m in msgs)


# --- kill（战斗，S1 基线）---


def test_kill_combat_runs() -> None:
    """kill 葛伦布触发 resolve_attack 一回合，qi 只减不增。"""
    game, pid = _game(seed_base=42)
    before = game.world.get(_gelun_eid(game), Vitals).qi
    msgs = kill(game, pid, "葛伦布")
    after = game.world.get(_gelun_eid(game), Vitals).qi
    assert len(msgs) >= 2
    assert after <= before


def test_kill_deterministic_seed() -> None:
    """同 seed 两次 kill 结果一致（combat 确定性穿透到命令层）。"""
    g1, p1 = _game(seed_base=42)
    g2, p2 = _game(seed_base=42)
    assert kill(g1, p1, "葛伦布") == kill(g2, p2, "葛伦布")


# --- 任务完整闭环（S4 ADR-0007） ---


def test_quest_complete_closes_loop() -> None:
    """任务完整闭环：ask 还愿接任务 -> give 酥油完成 -> 奖励 + 标记 -> go north 放行。"""
    game, pid = _game(items={"suyou_guan"})
    ask(game, pid, "葛伦布", "还愿")
    before_exp = game.world.get(pid, Progression).combat_exp
    give(game, pid, "葛伦布", "suyou_guan")
    assert game.world.get(pid, QuestLog).statuses["xueshan/tribute"] == "completed"
    assert game.world.get(pid, Progression).combat_exp == before_exp + 100
    assert "酥" in game.world.get(pid, Marks).flags
    # 完成任务后 north 放行（reward.flag + valid_leave has_flag）
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
    assert any("走去" in m for m in msgs)


# --- S4 扩展：5-10 房间全量验证（frontyard/yanwu/zoulang/jingang/chufang）---


def _walk_to_chufang(game: Game, pid: int) -> None:
    """从 shanmen 走到 chufang（雪山派放行 north，对照扩展路径）。"""
    go(game, pid, "north")  # shanmen -> guangchang
    go(game, pid, "north")  # guangchang -> frontyard
    go(game, pid, "north")  # frontyard -> yanwu
    go(game, pid, "north")  # yanwu -> zoulang
    go(game, pid, "east")  # zoulang -> chufang


def test_go_north_from_guangchang_to_frontyard() -> None:
    """guangchang north -> frontyard（扩展路径入口，对照 LPC frontyard.c）。"""
    game, pid = _game(family="雪山派")
    go(game, pid, "north")  # shanmen -> guangchang
    msgs = go(game, pid, "north")  # guangchang -> frontyard
    assert game.world.get(pid, Position).room_id == "xueshan/frontyard"
    assert any("走去" in m for m in msgs)


def test_walk_to_chufang() -> None:
    """完整路径 shanmen -> guangchang -> frontyard -> yanwu -> zoulang -> chufang。"""
    game, pid = _game(family="雪山派")
    _walk_to_chufang(game, pid)
    assert game.world.get(pid, Position).room_id == "xueshan/chufang"


def test_go_to_jingang() -> None:
    """zoulang north -> jingang（金刚院，对照 LPC jingang.c）。"""
    game, pid = _game(family="雪山派")
    for _ in range(4):
        go(game, pid, "north")  # -> guangchang/frontyard/yanwu/zoulang
    msgs = go(game, pid, "north")  # zoulang -> jingang
    assert game.world.get(pid, Position).room_id == "xueshan/jingang"
    assert any("走去" in m for m in msgs)


def test_go_no_exit_from_jingang_east() -> None:
    """jingang 有 south+north exit（子任务 4 加 north->houyuan），east 无出口 -> '没有'。"""
    game, pid = _game(family="雪山派", start_room="xueshan/jingang")
    msgs = go(game, pid, "east")
    assert game.world.get(pid, Position).room_id == "xueshan/jingang"
    assert any("没有" in m for m in msgs)


def test_ask_xlama2_inquiry() -> None:
    """chufang ask 小喇嘛 about 酥油茶 -> inquiry 静态回复（第二 NPC 对话，对照 LPC xlama2.c）。"""
    game, pid = _game(family="雪山派")
    _walk_to_chufang(game, pid)
    msgs = ask(game, pid, "小喇嘛", "酥油茶")
    assert any("酥油" in m and "贵" in m for m in msgs)


def test_ask_xlama2_unknown_topic() -> None:
    """ask 小喇嘛未知话题 -> 摇头。"""
    game, pid = _game(family="雪山派")
    _walk_to_chufang(game, pid)
    msgs = ask(game, pid, "小喇嘛", "天气")
    assert any("摇了摇头" in m for m in msgs)


def test_kill_xlama2_combat_runs() -> None:
    """kill 小喇嘛触发 resolve_attack（第二 NPC 战斗，peaceful 仍可被攻击）。"""
    game, pid = _game(family="雪山派", seed_base=42)
    _walk_to_chufang(game, pid)
    msgs = kill(game, pid, "小喇嘛")
    assert len(msgs) >= 2


def test_multi_step_quest_chain() -> None:
    """M3-1 ADR-0032 决策 3：多步任务 chain e2e（reach_room -> give_item）。

    ask 葛伦布跑腿 -> go eastdown 到 dshanlu（步骤1 reach_room 完成）-> get 酥油罐
    -> go westup 回 shanmen -> give 葛伦布酥油罐（步骤2 give_item 完成 + 发奖）。
    对照 LPC 多步任务（fsgelun kill->give corpse 多步）。
    """
    game, pid = _game()
    msgs = ask(game, pid, "葛伦布", "跑腿")
    assert any("接下任务「朝山跑腿」" in m for m in msgs)
    log = game.world.get(pid, QuestLog)
    assert log.current_step["xueshan/pilgrimage"] == 0
    # go eastdown -> dshanlu（reach_room 步骤1完成）
    msgs = go(game, pid, "eastdown")
    assert any("完成一步" in m for m in msgs)
    assert log.current_step["xueshan/pilgrimage"] == 1
    assert log.statuses["xueshan/pilgrimage"] == "in_progress"
    # get suyou_guan -> go westup 回 shanmen -> give（用 id，item_registry 未加载）
    take(game, pid, "suyou_guan")
    go(game, pid, "westup")
    before = game.world.get(pid, Progression).combat_exp
    msgs = give(game, pid, "葛伦布", "suyou_guan")
    assert any("完成" in m for m in msgs)
    assert game.world.get(pid, Progression).combat_exp >= before + 150
    assert log.statuses["xueshan/pilgrimage"] == "completed"
    assert "跑腿" in game.world.get(pid, Marks).flags
