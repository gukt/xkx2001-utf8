"""S5a 试玩缺口补全测试：take/look/inventory + 多回合战斗 + 死亡处理 + CLI REPL。

覆盖 PROGRESS.md S5a 三缺口：
- 玩家物品获取（take + 房间地面物品）
- 多回合战斗（kill 循环至一方倒下）
- 死亡/复活（NPC 死移除 + 玩家死传送回 spawn + 恢复）
- CLI REPL（parse_and_run 命令分发 + 完整试玩流程）
"""

from __future__ import annotations

from pathlib import Path

from xkx.cli import load_game, parse_and_run
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items, load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.commands import (
    Game,
    ask,
    give,
    go,
    hp,
    inventory,
    kill,
    look,
    take,
)
from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Inventory,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    Skills,
    Vitals,
)
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game(
    seed_base: int = 0,
    start_room: str = "xueshan/shanmen",
    spawn_room: str = "xueshan/shanmen",
    family: str = "",
    items: set[str] | None = None,
) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    item_defs = load_items(SCENE_DIR / "items.yaml")
    ir = compile_scene(rooms, npcs, quests, item_defs)
    world, room_idx, quest_idx = build_world(ir)
    item_registry = {i["id"]: i["name"] for i in ir.get("items", [])}
    pid = spawn_player(world, "玩家", start_room, family=family, items=items)
    game = Game(
        world,
        room_idx,
        rules,
        quests=quest_idx,
        seed_base=seed_base,
        spawn_room=spawn_room,
        item_registry=item_registry,
    )
    return game, pid


def _spawn_weak_npc(game: Game, room_id: str, name: str = "木桩", max_qi: int = 1) -> int:
    """创建极弱 NPC 供战斗测试（dodge/parry=0 + qi=1，一回合可击杀）。"""
    world = game.world
    eid = world.new_entity()
    world.add(eid, Identity(name=name, prototype_id="test/weak"))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Attributes())
    world.add(eid, Vitals(qi=max_qi, max_qi=max_qi, eff_qi=max_qi, jingli=100, max_jingli=100))
    world.add(eid, Skills(levels={"dodge": 0, "parry": 0}))
    world.add(eid, CombatState())
    world.add(eid, NpcBehavior())
    world.add(eid, Progression())
    return eid


# --- take / look / inventory（S5a 物品获取缺口）---


def test_take_picks_up_room_item() -> None:
    """dshanlu 有 suyou_guan，take 后移入玩家物品栏 + 房间移除 + 显示中文名。"""
    game, pid = _game(start_room="xueshan/dshanlu")
    msgs = take(game, pid, "suyou_guan")
    assert any("捡起" in m and "酥油罐" in m for m in msgs)
    assert "suyou_guan" in game.world.get(pid, Inventory).items
    room_eid = game.room_entities["xueshan/dshanlu"]
    from xkx.runtime.components import RoomComp

    assert "suyou_guan" not in game.world.get(room_eid, RoomComp).items


def test_take_by_chinese_name() -> None:
    """S5a：支持按中文名拾取（对齐 LPC present）。"""
    game, pid = _game(start_room="xueshan/dshanlu")
    msgs = take(game, pid, "酥油罐")
    assert any("捡起" in m and "酥油罐" in m for m in msgs)
    assert "suyou_guan" in game.world.get(pid, Inventory).items


def test_take_missing_item() -> None:
    """take 不存在的物品 -> 提示没有。"""
    game, pid = _game()
    msgs = take(game, pid, "不存在的物品")
    assert any("没有" in m for m in msgs)


def test_look_shows_room_info() -> None:
    """look 显示房间名/描述/NPC(id)/出口（LPC 风格）。"""
    game, pid = _game()
    msgs = look(game, pid)
    text = "\n".join(msgs)
    assert "山门" in text
    assert "葛伦布(ge lunbu)" in text  # NPC 名字(id) 格式
    assert "出口" in text


def test_look_shows_floor_items() -> None:
    """dshanlu 有 suyou_guan，look 显示「酥油罐(suyou_guan)」。"""
    game, pid = _game(start_room="xueshan/dshanlu")
    msgs = look(game, pid)
    text = "\n".join(msgs)
    assert "酥油罐(suyou_guan)" in text


def test_inventory_empty() -> None:
    """无物品时 inventory 提示空。"""
    game, pid = _game()
    msgs = inventory(game, pid)
    assert any("没有" in m for m in msgs)


def test_inventory_shows_items() -> None:
    """有物品时 inventory 列出（中文名(id) 格式）。"""
    game, pid = _game(items={"suyou_guan"})
    msgs = inventory(game, pid)
    assert any("酥油罐(suyou_guan)" in m for m in msgs)


def test_hp_shows_vitals() -> None:
    """hp 显示玩家气/精力/经验。"""
    game, pid = _game()
    msgs = hp(game, pid)
    text = "\n".join(msgs)
    assert "气" in text
    assert "200" in text  # max_qi
    assert "经验" in text


def test_go_auto_look() -> None:
    """go 移动成功后自动 look 新房间（消息含目标房间描述）。"""
    game, pid = _game()
    msgs = go(game, pid, "eastdown")
    text = "\n".join(msgs)
    assert "走去" in text
    assert "山路" in text  # dshanlu 房间描述


# --- 多回合战斗 + 死亡处理（S5a 战斗/死亡缺口）---


def test_kill_multi_round_npc_death() -> None:
    """多回合战斗打死弱 NPC -> NPC 从房间移除 + 玩家加经验。"""
    game, pid = _game()
    weak = _spawn_weak_npc(game, "xueshan/shanmen", "木桩", max_qi=1)
    before_exp = game.world.get(pid, Progression).combat_exp
    msgs = kill(game, pid, "木桩")
    assert any("死了" in m for m in msgs)
    assert game.world.get(weak, Position) is None
    # _handle_npc_death +50；resolve_attack 战斗中也可能给玩家 +exp，故用 >=
    assert game.world.get(pid, Progression).combat_exp >= before_exp + 50


def test_kill_player_death_respawn() -> None:
    """玩家 qi=1 被打死 -> die() 进阴间（ghost + death_room + death_stage）。

    M3-1 ADR-0032 决策 4：玩家死亡走完整死亡轮回（die + 阴间 + 还阳），替代
    S5a 简化版（传送 spawn_room + 恢复）。还阳由 GovernanceSystem tick 推进
    death_stage 到 stage 4 触发（reincarnate_at），不在 kill 命令内完成。
    """
    from xkx.runtime.components import EffectComp, Marks

    game, pid = _game(spawn_room="xueshan/shanmen")
    game.world.get(pid, Vitals).qi = 1
    msgs = kill(game, pid, "葛伦布")
    assert any("眼前一黑" in m for m in msgs)
    # die() 进阴间：ghost 标记 + move death_room（default theme = test/death）
    assert "ghost" in game.world.get(pid, Marks).flags
    assert game.world.get(pid, Position).room_id == "test/death"
    # death_stage EffectComp 启动（阴间 5 段剧情，GovernanceSystem 推进到还阳）
    has_death_stage = False
    for e in game.world.entities_with(EffectComp):
        eff = game.world.get(e, EffectComp)
        if eff is not None and eff.effect_id == "death_stage":
            has_death_stage = True
            break
    assert has_death_stage


def test_kill_deterministic_multi_round() -> None:
    """多回合战斗确定性：同 seed 同结果。"""
    g1, p1 = _game(seed_base=42)
    g2, p2 = _game(seed_base=42)
    assert kill(g1, p1, "葛伦布") == kill(g2, p2, "葛伦布")


# --- 完整试玩路径（take -> ask -> give -> quest -> go）---


def test_full_playtest_loop() -> None:
    """完整试玩闭环：take 酥油 -> ask 还愿 -> give -> quest 完成 -> go north 放行。"""
    game, pid = _game(spawn_room="xueshan/shanmen")
    go(game, pid, "eastdown")
    take(game, pid, "suyou_guan")
    assert "suyou_guan" in game.world.get(pid, Inventory).items
    go(game, pid, "westup")
    ask(game, pid, "葛伦布", "还愿")
    give(game, pid, "葛伦布", "suyou_guan")
    assert game.world.get(pid, QuestLog).statuses["xueshan/tribute"] == "completed"
    msgs = go(game, pid, "north")
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
    assert any("走去" in m for m in msgs)


# --- CLI REPL ---


def test_cli_load_game() -> None:
    """load_game 返回可用的 game + player（起点 shanmen）。"""
    game, pid = load_game()
    assert game.world.get(pid, Position).room_id == "xueshan/shanmen"


def test_cli_parse_quit_returns_false() -> None:
    """parse_and_run quit/exit 返回 False。"""
    game, pid = load_game()
    assert parse_and_run(game, pid, "quit") is False
    assert parse_and_run(game, pid, "exit") is False


def test_cli_parse_help() -> None:
    """parse_and_run help/h 不崩溃。"""
    game, pid = load_game()
    assert parse_and_run(game, pid, "help") is True
    assert parse_and_run(game, pid, "h") is True


def test_cli_parse_look() -> None:
    """parse_and_run look/l 显示房间。"""
    game, pid = load_game()
    assert parse_and_run(game, pid, "look") is True
    assert parse_and_run(game, pid, "l") is True


def test_cli_parse_unknown() -> None:
    """parse_and_run 未知命令不崩溃。"""
    game, pid = load_game()
    assert parse_and_run(game, pid, "乱七八糟") is True


def test_cli_playtest_flow() -> None:
    """CLI 完整试玩流程：go eastdown -> take -> go westup -> ask -> give -> go north。"""
    game, pid = load_game()
    assert parse_and_run(game, pid, "go eastdown") is True
    assert parse_and_run(game, pid, "take suyou_guan") is True
    assert "suyou_guan" in game.world.get(pid, Inventory).items
    assert parse_and_run(game, pid, "go westup") is True
    assert parse_and_run(game, pid, "ask 葛伦布 about 还愿") is True
    assert parse_and_run(game, pid, "give 葛伦布 suyou_guan") is True
    assert parse_and_run(game, pid, "go north") is True
    assert game.world.get(pid, Position).room_id == "xueshan/guangchang"
