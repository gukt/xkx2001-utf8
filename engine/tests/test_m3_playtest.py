"""M3-1 子任务 5 可玩 demo 整合 e2e：完整核心循环闭环测试。

覆盖 ADR-0032 决策 4（死亡轮回整合）+ 子任务 5（CLI 接 Engine 自动推进 +
消息缓冲）的完整闭环：拜师 gongcang 剃度 -> 练功（dazuo/tuna/learn）->
darba fight_win -> 战斗 -> 死亡轮回 -> 还阳 -> samu 拜师。

用 Engine + 直接调命令 + ``engine.tick()`` 推进（不依赖 CLI 自动推进，测试可控）。
对照 LPC kungfu/class/xueshan/ + feature/damage.c 阴间还阳。
"""

from __future__ import annotations

import random
from pathlib import Path

from xkx.dsl.cpk_loader import load_cpk
from xkx.runtime.commands import (
    Game,
    ask,
    bai,
    dazuo,
    enable,
    fight,
    give,
    go,
    kill,
    kneel,
    learn,
    tuna,
)
from xkx.runtime.components import (
    EffectComp,
    FamilyComp,
    Identity,
    Marks,
    Position,
    Progression,
    QuestLog,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.conditions import ConditionSystem
from xkx.runtime.engine import CombatBridge, Engine
from xkx.runtime.governance import GovernanceSystem
from xkx.runtime.heal import HealSystem
from xkx.runtime.skill import register_skill_defs
from xkx.runtime.world import build_world, spawn_player
from xkx.themes import default_registry

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"

_AUTO_EFFECTS = frozenset({"exercise", "respirate", "death_stage"})


def _game(
    start_room: str = "xueshan/shanmen",
    family: str = "",
    items: set[str] | None = None,
) -> tuple[Game, int, Engine]:
    """加载 xueshan CPK + Engine + 玩家，返回 (game, pid, engine)。"""
    registry = default_registry()
    manifest, ir, rules, skills = load_cpk(SCENE_DIR, registry=registry)
    descriptor = registry.require(manifest.theme)
    world, room_idx, quest_idx = build_world(
        ir, theme_config=descriptor.theme_config
    )
    register_skill_defs(skills)
    item_registry = {i["id"]: i["name"] for i in ir.get("items", [])}
    pid = spawn_player(world, "玩家", start_room, family=family, items=items)
    game = Game(
        world,
        room_idx,
        rules,
        quests=quest_idx,
        spawn_room=start_room,
        item_registry=item_registry,
    )
    engine = Engine(world)
    engine.add_system(CombatBridge())
    engine.add_system(HealSystem())
    engine.add_system(ConditionSystem())
    engine.add_system(GovernanceSystem())
    game.engine = engine  # type: ignore[attr-defined]
    return game, pid, engine


def _set_skills(
    game: Game, pid: int, levels: dict[str, int], skill_map: dict[str, str] | None = None
) -> None:
    skills = game.world.get(pid, Skills)
    if skills is None:
        skills = Skills()
        game.world.add(pid, skills)
    skills.levels.update(levels)
    if skill_map:
        skills.skill_map.update(skill_map)


def _set_vitals(game: Game, pid: int, **overrides: int) -> None:
    vitals = game.world.get(pid, Vitals)
    for k, v in overrides.items():
        setattr(vitals, k, v)


def _advance_until_idle(game: Game, engine: Engine, pid: int, max_ticks: int = 200) -> None:
    """推进 tick 直到玩家无 exercise/respirate/death_stage EffectComp。"""
    for _ in range(max_ticks):
        active = False
        for e in game.world.entities_with(EffectComp):
            eff = game.world.get(e, EffectComp)
            if (
                eff is not None
                and eff.target_id == pid
                and eff.effect_id in _AUTO_EFFECTS
            ):
                active = True
                break
        if not active:
            return
        engine.tick()


def _has_effect(game: Game, pid: int, effect_id: str) -> bool:
    for e in game.world.entities_with(EffectComp):
        eff = game.world.get(e, EffectComp)
        if eff is not None and eff.target_id == pid and eff.effect_id == effect_id:
            return True
    return False


# --- 拜师 gongcang 剃度闭环（M3-1 子任务 5）---


def test_bai_gongcang_kneel_tonsure() -> None:
    """bai gongcang 收徒设 pending -> kneel 剃度设 class=lama（子任务 5 闭环修复）。"""
    game, pid, engine = _game(start_room="xueshan/guangchang")
    msgs = bai(game, pid, "昌齐大喇嘛")
    # bai 成功收徒 + 设 pending/join_lama（gongcang 剃度闭环修复）
    assert any("受戒许可" in m for m in msgs)
    assert "pending/join_lama" in game.world.get(pid, Marks).flags
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.master_name == "昌齐大喇嘛"
    assert fam.generation == 13  # 师傅 gen12 + 1
    # kneel 剃度：设 class=lama + 清 pending（对照 gongcang.c do_kneel）
    msgs = kneel(game, pid)
    assert game.world.get(pid, TitleComp).char_class == "lama"
    assert "pending/join_lama" not in game.world.get(pid, Marks).flags


# --- 练功闭环（dazuo/tuna/learn + Engine tick 自动推进）---


def test_dazuo_max_neili_advance() -> None:
    """dazuo 启动 exercise busy -> Engine tick 推进 -> max_neili 提升。"""
    game, pid, engine = _game(start_room="xueshan/guangchang", family="雪山派")
    # force=0 + skill_map force=longxiang-banruo(100) -> 有效 force=100
    _set_skills(
        game, pid, {"force": 0, "longxiang-banruo": 100}, {"force": "longxiang-banruo"}
    )
    _set_vitals(
        game, pid, max_neili=5, neili=0, qi=500, max_qi=500, eff_qi=500,
        jing=500, max_jing=500, eff_jing=500,
    )
    enable(game, pid, "force", "longxiang-banruo")
    before = game.world.get(pid, Vitals).max_neili
    msgs = dazuo(game, pid, 100)
    assert any("盘膝坐下" in m for m in msgs)
    assert _has_effect(game, pid, "exercise")  # busy EffectComp 启动
    _advance_until_idle(game, engine, pid)
    assert not _has_effect(game, pid, "exercise")  # busy 结束
    after = game.world.get(pid, Vitals).max_neili
    assert after > before  # max_neili 提升（未瓶颈，threshold=100*20*2/3=1333）


def test_tuna_max_jingli_advance() -> None:
    """tuna 启动 respirate busy -> Engine tick 推进 -> max_jingli 提升。"""
    game, pid, engine = _game(start_room="xueshan/guangchang", family="雪山派")
    _set_skills(game, pid, {"force": 100})  # tuna 用原始 force，不要求 enable
    _set_vitals(
        game, pid, max_jingli=5, jingli=0, jing=500, max_jing=500, eff_jing=500,
        qi=500, max_qi=500, eff_qi=500,
    )
    before = game.world.get(pid, Vitals).max_jingli
    msgs = tuna(game, pid, 100)
    assert any("盘膝坐下" in m for m in msgs)
    assert _has_effect(game, pid, "respirate")
    _advance_until_idle(game, engine, pid)
    assert not _has_effect(game, pid, "respirate")
    after = game.world.get(pid, Vitals).max_jingli
    assert after > before  # max_jingli 提升


def test_learn_gongcang_skill_up() -> None:
    """bai gongcang 成弟子 -> learn longxiang-banruo 技能提升。"""
    random.seed(42)  # learn gain 用系统 RNG，固定 seed 确定性
    game, pid, engine = _game(start_room="xueshan/guangchang")
    bai(game, pid, "昌齐大喇嘛")  # 成为 gongcang 弟子（learn 须 _is_apprentice_of）
    _set_vitals(game, pid, jing=5000, max_jing=5000, eff_jing=5000)
    game.world.get(pid, Progression).potential = 1000
    before = game.world.get(pid, Skills).levels.get("longxiang-banruo", 0)
    msgs = learn(game, pid, "昌齐大喇嘛", "longxiang-banruo", 50)
    after = game.world.get(pid, Skills).levels.get("longxiang-banruo", 0)
    assert after > before  # 技能提升（gain = Σ random(0,19) for 50 ≈ 475，必升多级）
    assert any("进步了" in m for m in msgs)


# --- darba fight_win 任务（M3-1 ADR-0032 决策 3）---


def test_darba_in_yanwu() -> None:
    """darba 放置在 yanwu 演武场（子任务 5 内容修补）。"""
    game, pid, engine = _game(start_room="xueshan/yanwu")
    found = False
    for eid in game.world.entities_in_room("xueshan/yanwu"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player and ident.prototype_id == "xueshan/npc/darba":
            found = True
            break
    assert found


def test_darba_fight_win() -> None:
    """强玩家 ask darba 引见接任务 -> fight darba 赢 -> fight_win 完成 + flag jlfw。"""
    game, pid, engine = _game(start_room="xueshan/yanwu")
    # 设强玩家（碾压 darba 130 级，e2e 测逻辑非平衡，保真不弱化 darba）
    _set_skills(
        game, pid, {"unarmed": 500, "dodge": 500, "parry": 500, "force": 500}
    )
    _set_vitals(
        game, pid, qi=50000, max_qi=50000, eff_qi=50000,
        jing=50000, max_jing=50000, eff_jing=50000,
    )
    game.world.get(pid, Progression).combat_exp = 5000000
    # ask darba 引见接 fight_win 任务
    msgs = ask(game, pid, "达尔巴", "引见")
    assert any("接下任务「引见金轮法王」" in m for m in msgs)
    assert (
        game.world.get(pid, QuestLog).statuses["xueshan/quest/darba"] == "in_progress"
    )
    # fight darba（切磋，玩家赢 -> darba qi 降到 50% 认输，不致死）
    msgs = fight(game, pid, "达尔巴")
    assert any("认输" in m for m in msgs)
    # fight_win objective 完成 + flag jlfw（解锁 jinlun 拜师，后置子任务 4 扩展）
    log = game.world.get(pid, QuestLog)
    assert log.statuses["xueshan/quest/darba"] == "completed"
    assert "jlfw" in game.world.get(pid, Marks).flags


# --- 死亡轮回（ADR-0032 决策 4：die + 阴间 5 段 + 还阳）---


def test_player_death_underworld_reincarnate() -> None:
    """弱玩家 kill 葛伦布被反杀 -> die 进阴间 -> tick 推进 5 段 -> 还阳。"""
    game, pid, engine = _game(start_room="xueshan/shanmen")
    game.world.get(pid, Vitals).qi = 1  # 极弱，一回合被反杀
    msgs = kill(game, pid, "葛伦布")
    assert any("眼前一黑" in m for m in msgs)
    # die() 进阴间：ghost + death_room（wuxia = death/gate）+ death_stage EffectComp
    assert "ghost" in game.world.get(pid, Marks).flags
    assert game.world.get(pid, Position).room_id == "death/gate"
    assert _has_effect(game, pid, "death_stage")
    # tick 推进阴间 5 段到还阳（首延 30 + 5 段每段 5 = 55 tick）
    _advance_until_idle(game, engine, pid)
    # 还阳：ghost 清 + move revive_room（wuxia = city/wumiao）+ Vitals 恢复
    assert "ghost" not in game.world.get(pid, Marks).flags
    assert game.world.get(pid, Position).room_id == "city/wumiao"
    vitals = game.world.get(pid, Vitals)
    assert vitals.qi == vitals.max_qi  # reincarnate 完整恢复


# --- samu 拜师（min_skills 门槛 + 辈分）---


def test_bai_samu_requires_skill() -> None:
    """设 longxiang-banruo 30 -> bai samu 收徒（gen12，min_skills 门槛通过）。"""
    game, pid, engine = _game(start_room="xueshan/jingang")
    _set_skills(game, pid, {"longxiang-banruo": 30})  # 满足 samu min_skills
    bai(game, pid, "萨木活佛")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.master_name == "萨木活佛"
    assert fam.generation == 12  # samu gen11 + 1


def test_bai_samu_reject_low_skill() -> None:
    """longxiang-banruo 不足 30 -> bai samu 拒绝（min_skills 门槛）。"""
    game, pid, engine = _game(start_room="xueshan/jingang")
    _set_skills(game, pid, {"longxiang-banruo": 10})  # 不足 30
    msgs = bai(game, pid, "萨木活佛")
    assert any("还不够纯熟" in m for m in msgs)
    assert game.world.get(pid, FamilyComp).family_name == ""  # 未拜师


# --- M3-1 子任务 4：3 任务链完整闭环（jiamu/fsgelun/lazhangfo）---
# 对照 d/xueshan/npc/{jiamu,fsgelun,lazhangfo}.c + quests.yaml。
# jiamu time_gate 可重复（完成后重置 not_started），fsgelun/lazhangfo 一次性 completed。


def test_jiamu_wage_quest() -> None:
    """jiamu 工资任务（time-gate 可重复）：ask 供奉 -> reach dumudian -> 发奖 + flag 工资。"""
    game, pid, engine = _game(start_room="xueshan/angqian")
    msgs = ask(game, pid, "嘉木活佛", "供奉")
    assert any("接下任务" in m for m in msgs)
    # angqian -> south houyuan -> south jingang -> south zoulang -> south yanwu -> northup dumudian
    go(game, pid, "south")
    go(game, pid, "south")
    go(game, pid, "south")
    go(game, pid, "south")
    go(game, pid, "northup")
    log = game.world.get(pid, QuestLog)
    # time_gate>0：完成后重置 not_started + 记 claimed_at（可再接，ask 冷却门控）
    assert log.statuses["xueshan/quest/jiamu"] == "not_started"
    assert "xueshan/quest/jiamu" in log.claimed_at
    assert "工资" in game.world.get(pid, Marks).flags


def test_fsgelun_quest_multi_step() -> None:
    """fsgelun 法事多步：ask 准备法事 -> reach_room dumudian -> give fsgelun suyou_guan。"""
    game, pid, engine = _game(start_room="xueshan/jingtang", items={"suyou_guan"})
    ask(game, pid, "葛伦布", "准备法事")
    # jingtang -> east yanwu -> northup dumudian（reach_room 完成第一步）
    go(game, pid, "east")
    go(game, pid, "northup")
    # 回 jingtang give fsgelun：dumudian southdown yanwu -> west jingtang
    go(game, pid, "southdown")
    go(game, pid, "west")
    give(game, pid, "葛伦布", "suyou_guan")
    log = game.world.get(pid, QuestLog)
    assert log.statuses["xueshan/quest/fsgelun"] == "completed"
    assert "法事" in game.world.get(pid, Marks).flags


def test_lazhangfo_scripture_quest() -> None:
    """lazhangfo 藏经任务：ask 藏经 -> reach_room jingtang -> 完成 + flag 读经。"""
    game, pid, engine = _game(start_room="xueshan/songjing")
    ask(game, pid, "拉章活佛", "藏经")
    # songjing -> west yanwu -> west jingtang（reach_room 完成）
    go(game, pid, "west")
    go(game, pid, "west")
    log = game.world.get(pid, QuestLog)
    assert log.statuses["xueshan/quest/lazhangfo"] == "completed"
    assert "读经" in game.world.get(pid, Marks).flags


# --- M3-1 子任务 4：3 师傅拜师（ling-zhi/jinlun/jiumo 完整拜师链）---


def test_bai_lingzhi_skill_threshold() -> None:
    """ling-zhi（gen10 红殿）min_skills longxiang-banruo 45：设 45 -> bai 成功（gen11）。"""
    game, pid, engine = _game(start_room="xueshan/hongdian", family="雪山派")
    _set_skills(game, pid, {"longxiang-banruo": 45})
    bai(game, pid, "灵智上人")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.generation == 11  # ling-zhi gen10 + 1


def test_bai_lingzhi_reject_low_skill() -> None:
    """ling-zhi longxiang-banruo 不足 45 -> 拒绝。"""
    game, pid, engine = _game(start_room="xueshan/hongdian", family="雪山派")
    _set_skills(game, pid, {"longxiang-banruo": 30})
    bai(game, pid, "灵智上人")
    assert game.world.get(pid, FamilyComp).family_name == ""


def test_bai_jinlun_requires_jlfw() -> None:
    """jinlun（gen9 鹿野苑）需 require_flags jlfw：无 -> 拒绝；有 + 技能 60 -> 成功（gen10）。"""
    game, pid, engine = _game(start_room="xueshan/luyeyuan", family="雪山派")
    _set_skills(game, pid, {"longxiang-banruo": 60})
    bai(game, pid, "金轮法王")
    assert game.world.get(pid, FamilyComp).family_name == ""  # 无 jlfw 拒绝
    game.world.get(pid, Marks).flags.add("jlfw")
    bai(game, pid, "金轮法王")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.generation == 10  # jinlun gen9 + 1


def test_bai_jiumo_skill_threshold() -> None:
    """jiumo（gen6 掌门 大殿）min_skills longxiang-banruo 60：设 60 -> bai 成功（gen7）。"""
    game, pid, engine = _game(start_room="xueshan/dadian", family="雪山派")
    _set_skills(game, pid, {"longxiang-banruo": 60})
    bai(game, pid, "鸠摩智")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.generation == 7  # jiumo gen6 + 1


# --- M3-1 子任务 4：3 任务链 giver 接任务（jiamu/fsgelun/lazhangfo）---


def test_jiamu_wage_quest_accept() -> None:
    """jiamu（angqian）ask 供奉 -> 接工资任务（time_gate 86400 可重复）。"""
    game, pid, engine = _game(start_room="xueshan/angqian", family="雪山派")
    msgs = ask(game, pid, "嘉木活佛", "供奉")
    assert any("接下任务" in m for m in msgs)
    assert (
        game.world.get(pid, QuestLog).statuses["xueshan/quest/jiamu"] == "in_progress"
    )


def test_fsgelun_quest_accept() -> None:
    """fsgelun（jingtang）ask 准备法事 -> 接多步法事任务。"""
    game, pid, engine = _game(start_room="xueshan/jingtang", family="雪山派")
    msgs = ask(game, pid, "葛伦布", "准备法事")
    assert any("接下任务" in m for m in msgs)
    assert (
        game.world.get(pid, QuestLog).statuses["xueshan/quest/fsgelun"] == "in_progress"
    )


def test_lazhangfo_quest_accept() -> None:
    """lazhangfo（songjing）ask 藏经 -> 接藏经任务。"""
    game, pid, engine = _game(start_room="xueshan/songjing", family="雪山派")
    msgs = ask(game, pid, "拉章活佛", "藏经")
    assert any("接下任务" in m for m in msgs)
    assert (
        game.world.get(pid, QuestLog).statuses["xueshan/quest/lazhangfo"]
        == "in_progress"
    )


# --- M3-1 子任务 4：房间连通（shanmen -> 各师傅所在可达）---


def test_rooms_reachable_to_masters() -> None:
    """从 yanwu 出发可达 3 师傅所在（songjing/dadian/hongdian），验证子任务 4 新房间连通。"""
    game, pid, engine = _game(start_room="xueshan/yanwu")
    # yanwu -> east -> songjing（lazhangfo）
    go(game, pid, "east")
    assert game.world.get(pid, Position).room_id == "xueshan/songjing"
    # 回 yanwu -> northup -> dumudian -> changlang -> dadian（jiumo）
    go(game, pid, "west")  # songjing -> yanwu
    go(game, pid, "northup")  # yanwu -> dumudian
    go(game, pid, "north")  # dumudian -> changlang
    go(game, pid, "north")  # changlang -> dadian（jiumo）
    assert game.world.get(pid, Position).room_id == "xueshan/dadian"
    # dadian 回 -> yanwu -> zoulang -> northup -> hongdian（ling-zhi）
    go(game, pid, "south")  # dadian -> changlang
    go(game, pid, "south")  # changlang -> dumudian
    go(game, pid, "southdown")  # dumudian -> yanwu
    go(game, pid, "north")  # yanwu -> zoulang
    go(game, pid, "northup")  # zoulang -> hongdian（ling-zhi）
    assert game.world.get(pid, Position).room_id == "xueshan/hongdian"
