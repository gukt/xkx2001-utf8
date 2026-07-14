"""端到端：xueshan_micro 场景 -> go(方向绑定守卫) / ask(对话) / give(物品交互) -> kill。

S4 ADR-0005：方向绑定 + 组合谓词完整表达 d/xueshan/shanmen.c valid_leave。
S4 ADR-0006：ask 对话（inquiry）+ give 物品交互（accept_object + set_flag），
  对照 d/xueshan/npc/gelun1.c 的 inquiry + accept_object。
完整交互闭环：give 葛伦布酥油罐 -> set marks/酥 -> go north 放行。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items, load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import Game, ask, drink, give, go, kill, take
from xkx.runtime.components import (
    CombatState,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
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
    item_defs = load_items(SCENE_DIR / "items.yaml")
    ir = compile_scene(rooms, npcs, quests, items=item_defs)
    world, room_idx, quest_idx = build_world(ir)
    pid = spawn_player(world, "玩家", start_room, family=family, items=items)
    item_registry = {i.id: i.model_dump() for i in item_defs}  # C4 ADR-0043 完整 dict
    game = Game(
        world, room_idx, rules, quests=quest_idx,
        seed_base=seed_base, item_registry=item_registry,
    )
    # ADR-0039：接入 Engine + CombatBridge（战斗 tick 驱动）+ 治理/恢复 System
    from xkx.runtime.conditions import ConditionSystem
    from xkx.runtime.doors import DoorSystem
    from xkx.runtime.engine import CombatBridge, Engine
    from xkx.runtime.governance import GovernanceSystem
    from xkx.runtime.heal import HealSystem

    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    engine.add_system(DoorSystem())  # C5 ADR-0042 门定时关门
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


# --- C4 ADR-0040：xlama2 交互闭环（ask set_flag + give clear_flag + spawn_items）---


def test_ask_xlama2_sets_tea_flag() -> None:
    """ask 小喇嘛 about 酥油茶 -> inquiry 消息 + set marks/茶（C4 ADR-0040，对照 ask_tea）。"""
    game, pid = _game(start_room="xueshan/chufang")
    msgs = ask(game, pid, "小喇嘛", "酥油茶")
    # 消息走 inquiry 字典（ask 规则 message 留空）
    assert any("酥油那麽贵" in m for m in msgs)
    # set_flag 副作用：玩家 marks 含"茶"
    marks = game.world.get(pid, Marks)
    assert marks is not None and "茶" in marks.flags


def test_give_xlama2_suyou_clears_flag_and_spawns_tea() -> None:
    """give 小喇嘛 酥油 -> clear marks/茶 + 厨房生成 buttertea（C4 ADR-0040）。"""
    game, pid = _game(start_room="xueshan/chufang", items={"suyou"})
    # 先 ask 设"茶"标记
    ask(game, pid, "小喇嘛", "酥油茶")
    assert "茶" in game.world.get(pid, Marks).flags
    # give 酥油 -> clear_flag + spawn buttertea 到厨房
    msgs = give(game, pid, "小喇嘛", "酥油")
    assert any("请用茶" in m for m in msgs)
    # "茶"标记已清
    assert "茶" not in game.world.get(pid, Marks).flags
    # 酥油已移出玩家物品栏
    assert "suyou" not in game.world.get(pid, Inventory).items
    # 厨房生成 buttertea（set 语义，count 简化为有/无）
    chufang = game.world.get(game.room_entities["xueshan/chufang"], RoomComp)
    assert "buttertea" in chufang.items


def test_xlama2_loop_take_buttertea() -> None:
    """完整闭环：ask 设茶 -> give 酥油生茶 -> take 酥油茶（C4 ADR-0040）。"""
    game, pid = _game(start_room="xueshan/chufang", items={"suyou"})
    ask(game, pid, "小喇嘛", "酥油茶")
    give(game, pid, "小喇嘛", "酥油")
    # take 酥油茶（中文名匹配 buttertea）
    msgs = take(game, pid, "酥油茶")
    assert any("捡起" in m for m in msgs)
    assert "buttertea" in game.world.get(pid, Inventory).items


# --- B-2 ADR-0039 决策 4：auto_fight 接入（aggressive NPC 主动攻击）---


def test_go_into_aggressive_npc_triggers_auto_fight() -> None:
    """go 进 aggressive NPC 房间触发 auto_fight（注册 handler 后，对照 LPC init()）。"""
    import xkx.runtime.auto_fight as auto_fight_mod
    from xkx.runtime.auto_fight import (
        FightType,
        aggressive_start_fight_handler,
        register_start_fight_handler,
    )

    game, pid = _game(start_room="xueshan/luyeyuan")
    register_start_fight_handler(FightType.AGGRESSIVE, aggressive_start_fight_handler)
    try:
        msgs = go(game, pid, "east")  # luyeyuan -> wangyou（yelang aggressive）
        # _trigger_room_enter_fight 触发：handler 建敌对关系 -> "你被攻击了！"
        assert any("被攻击" in m for m in msgs)
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.AGGRESSIVE, None)


def test_aggressive_npc_no_attack_without_handler() -> None:
    """未注册 handler -> aggressive NPC 不攻击（on_start_fight 默认 no-op）。"""
    from xkx.runtime.components import CombatState

    game, pid = _game(start_room="xueshan/luyeyuan")
    # 不注册 handler（默认 no-op）
    msgs = go(game, pid, "east")  # luyeyuan -> wangyou
    assert not any("被攻击" in m for m in msgs)
    cs = game.world.get(pid, CombatState)
    assert cs is None or not cs.is_fighting


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


# --- C4 ADR-0043：drink 命令 + 厨房初始物品 + 持茶挡路闭环 ---


def test_drink_buttertea_restores_and_consumes() -> None:
    """drink 酥油茶恢复 water/food/jing + 物品消失（对照 LPC buttertea.c do_drink）。"""
    game, pid = _game(start_room="xueshan/chufang")
    take(game, pid, "buttertea")  # 厨房初始 buttertea
    inv = game.world.get(pid, Inventory)
    assert "buttertea" in inv.items
    vitals = game.world.get(pid, Vitals)
    vitals.jing = 10
    vitals.water = 100
    vitals.food = 100
    msgs = drink(game, pid, "buttertea")
    assert any("神清气爽" in m for m in msgs)
    assert "buttertea" not in inv.items  # set 语义喝一次消失
    assert vitals.water == 150  # +50
    assert vitals.food == 130  # +30
    assert vitals.jing == 15  # 10 + 5（clamp eff_jing=150）


def test_drink_non_consumable_rejected() -> None:
    """无 consumable 字段的物品 drink 拒（对照 LPC 物品无 do_drink add_action）。"""
    game, pid = _game(start_room="xueshan/chufang")
    inv = game.world.get(pid, Inventory)
    inv.items.add("suyou")  # 酥油无 consumable
    msgs = drink(game, pid, "suyou")
    assert any("不能喝" in m for m in msgs)
    assert "suyou" in inv.items  # 未消耗


def test_chufang_tea_block_valid_leave() -> None:
    """持酥油茶朝 west 走被挡，喝完后放行（对照 LPC chufang.c valid_leave west）。"""
    game, pid = _game(start_room="xueshan/chufang")
    take(game, pid, "buttertea")
    msgs = go(game, pid, "west")  # 持茶被挡
    assert any("喝完茶" in m for m in msgs)
    assert game.world.get(pid, Position).room_id == "xueshan/chufang"
    drink(game, pid, "buttertea")  # 喝完
    go(game, pid, "west")  # 放行
    assert game.world.get(pid, Position).room_id == "xueshan/zoulang"


def test_take_by_alias_resolves() -> None:
    """take 按别名解析（C4 ADR-0043 _resolve_item_id 扩 aliases，修复不对称 gap）。"""
    game, pid = _game(start_room="xueshan/chufang")
    take(game, pid, "tea")  # 别名 tea -> buttertea
    inv = game.world.get(pid, Inventory)
    assert "buttertea" in inv.items


# --- B-2 ADR-0045：hatred（killer_ids 重触）+ vendetta（标记式追杀）---


def _find_npc_eid(game: Game, room_id: str, name: str) -> int:
    """按名称/别名找房间内 NPC 实体。"""
    for eid in game.world.entities_in_room(room_id):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player and name in (ident.name, *ident.aliases):
            return eid
    raise AssertionError(f"no npc {name} in {room_id}")


def test_hatred_retriggers_on_reentry() -> None:
    """NPC 记住玩家（killer_ids），重入房间 hatred 重触（对照 LPC is_killing）。"""
    from xkx.runtime import auto_fight as auto_fight_mod
    from xkx.runtime.auto_fight import (
        FightType,
        hatred_start_fight_handler,
        register_start_fight_handler,
    )

    game, pid = _game(start_room="xueshan/wangyou")
    yelang_eid = _find_npc_eid(game, "xueshan/wangyou", "野狼")
    # 手动设 yelang.killer_ids 含 pid（模拟曾 to_death 战斗过 + flee 中断，killer 保留）
    yelang_cs = game.world.get(yelang_eid, CombatState)
    yelang_cs.killer_ids.append(pid)
    register_start_fight_handler(FightType.HATRED, hatred_start_fight_handler)
    try:
        go(game, pid, "west")  # wangyou -> luyeyuan（离开）
        assert game.world.get(pid, Position).room_id == "xueshan/luyeyuan"
        msgs = go(game, pid, "east")  # luyeyuan -> wangyou（重入，hatred 触发）
        assert any("被攻击" in m for m in msgs)
    finally:
        auto_fight_mod._START_FIGHT_HANDLERS.pop(FightType.HATRED, None)


def test_vendetta_mark_written_on_kill() -> None:
    """杀 vendetta NPC -> 击杀者获 vendetta:<mark> flag（对照 LPC killer_reward）。"""
    game, pid = _game(start_room="xueshan/luyeyuan")
    kill(game, pid, "守卫")  # guard（vendetta_mark=guard）在 luyeyuan
    marks = game.world.get(pid, Marks)
    assert "vendetta:guard" in marks.flags


def test_decide_room_enter_fight_priority() -> None:
    """三触发优先级 hatred > vendetta > aggressive（对照 LPC init() if-else）。"""
    from xkx.runtime.auto_fight import FightType
    from xkx.runtime.commands import _decide_room_enter_fight

    game, pid = _game(start_room="xueshan/luyeyuan")
    guard_eid = _find_npc_eid(game, "xueshan/luyeyuan", "守卫")
    behavior = game.world.get(guard_eid, NpcBehavior)
    guard_cs = game.world.get(guard_eid, CombatState)
    player_flags = {f"vendetta:{behavior.vendetta_mark}"}  # 满足 vendetta 条件
    # 1. hatred 优先（killer_ids 含 pid）
    guard_cs.killer_ids.append(pid)
    assert (
        _decide_room_enter_fight(game.world, guard_eid, pid, behavior, player_flags)
        == FightType.HATRED
    )
    # 2. 清 killer_ids -> vendetta
    guard_cs.killer_ids.clear()
    assert (
        _decide_room_enter_fight(game.world, guard_eid, pid, behavior, player_flags)
        == FightType.VENDETTA
    )
    # 3. 清 player_flags -> guard 非 aggressive -> None
    assert (
        _decide_room_enter_fight(game.world, guard_eid, pid, behavior, set()) is None
    )
