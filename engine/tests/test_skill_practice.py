"""练功系统单元测试（M3-1 ADR-0032 决策 2）。

覆盖 improve_skill 运行时函数 + learn/practice/dazuo/tuna/enable 命令 +
exercise/respirate busy condition。行为等价对照 LPC：

- [feature/skill.c](../../feature/skill.c)：improve_skill（learned 阈值升级）
- [cmds/skill/learn.c](../../cmds/skill/learn.c) / [practice.c](../../cmds/skill/practice.c) /
  [dazuo.c](../../cmds/skill/dazuo.c) / [tuna.c](../../cmds/skill/tuna.c) /
  [enable.c](../../cmds/skill/enable.c)：5 练功命令
- [feature/action.c](../../feature/action.c)：is_busy + start_busy（greenfield 翻译为 EffectComp）
"""

from __future__ import annotations

from xkx.combat.context import SkillData
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import NpcDef, RoomDef
from xkx.runtime.commands import (
    Game,
    dazuo,
    enable,
    learn,
    practice,
    tuna,
)
from xkx.runtime.components import (
    Attributes,
    FamilyComp,
    Identity,
    Marks,
    Progression,
    Skills,
    Vitals,
)
from xkx.runtime.conditions import ConditionSystem, apply_condition, query_condition
from xkx.runtime.skill import (
    BUSY_CONDITIONS,
    get_skill_data,
    improve_skill,
    is_busy,
    register_skill_data,
)
from xkx.runtime.world import build_world, spawn_player


def _game(
    *,
    player_skills: dict[str, int] | None = None,
    player_skill_map: dict[str, str] | None = None,
    master_skills: dict[str, int] | None = None,
    potential: int = 100,
    qi: int = 300,
    jing: int = 300,
    jingli: int = 100,
    max_jingli: int = 100,
    neili: int = 0,
    max_neili: int = 50,
    int_val: int = 20,
    con_val: int = 20,
    combat_exp: int = 500,
    apprentice: bool = True,
) -> tuple[Game, int, int]:
    """构建测试场景：1 房间 + 师傅 NPC「贡藏」+ 玩家。

    玩家默认已拜师贡藏（is_apprentice_of 通过）。返回 (game, player_eid, master_eid)。
    """
    npc = NpcDef(id="xueshan/gongcang", name="贡藏", aliases=["gongcang"], gender="男性")
    room = RoomDef(id="room/test", short="测试房", long="测试房间。", objects={npc.id: 1})
    ir = compile_scene([room], [npc])
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", "room/test")
    attrs = world.get(pid, Attributes)
    if attrs:
        attrs.int_ = int_val
        attrs.con_ = con_val
        attrs.family = "雪山派"
    prog = world.get(pid, Progression)
    if prog:
        prog.potential = potential
        prog.combat_exp = combat_exp
    vitals = world.get(pid, Vitals)
    if vitals:
        vitals.qi = qi
        vitals.jing = jing
        vitals.jingli = jingli
        vitals.max_jingli = max_jingli
        vitals.neili = neili
        vitals.max_neili = max_neili
    skills = world.get(pid, Skills)
    if skills:
        if player_skills:
            skills.levels.update(player_skills)
        if player_skill_map:
            skills.skill_map.update(player_skill_map)
    if apprentice:
        fam = world.get(pid, FamilyComp)
        if fam:
            fam.family_name = "雪山派"
            fam.generation = 13
            fam.master_id = "xueshan/gongcang"
            fam.master_name = "贡藏"
    game = Game(world, room_idx, rules=[])
    # 师傅 NPC 技能（learn 命令查 master_skill）
    master_eid = -1
    for eid in world.entities_in_room("room/test"):
        ident = world.get(eid, Identity)
        if ident and not ident.is_player:
            master_eid = eid
            break
    m_skills = world.get(master_eid, Skills)
    if m_skills is None:
        m_skills = Skills()
        world.add(master_eid, m_skills)
    if master_skills:
        m_skills.levels.update(master_skills)
    return game, pid, master_eid


def _advance(world, n: int, start: int = 0) -> None:
    """推进 ConditionSystem n 个 tick（每 tick 触发一次 busy handler）。"""
    cond = ConditionSystem()
    for i in range(n):
        cond.update(world, tick=start + i)


# ──────────────────────── improve_skill（对照 skill.c:149-182） ────────────────────────


def test_improve_skill_threshold_upgrade() -> None:
    """learned > (lvl+1)² 严格大于则升级，升级后 learned 清零。"""
    game, pid, _ = _game(player_skills={"lamaism": 0})
    world = game.world
    # lvl=0 -> 阈值 (0+1)²=1，learned=1 不升级（不严格大于），learned=2 升级
    assert improve_skill(world, pid, "lamaism", 1) is False
    assert world.get(pid, Skills).learned["lamaism"] == 1
    assert world.get(pid, Skills).levels["lamaism"] == 0
    assert improve_skill(world, pid, "lamaism", 1) is True  # learned=2 > 1
    assert world.get(pid, Skills).levels["lamaism"] == 1
    assert world.get(pid, Skills).learned["lamaism"] == 0  # 清零


def test_improve_skill_weak_mode_no_upgrade() -> None:
    """weak_mode=True 只累积 learned 点数，不升级（practice 限制特殊技能）。"""
    game, pid, _ = _game(player_skills={"lamaism": 5})
    world = game.world
    improve_skill(world, pid, "lamaism", 100, weak_mode=True)
    assert world.get(pid, Skills).learned["lamaism"] == 100
    assert world.get(pid, Skills).levels["lamaism"] == 5  # 不升级


def test_improve_skill_non_player_noop() -> None:
    """非玩家 improve_skill 无效（对照 LPC !userp -> return）。"""
    game, pid, _ = _game(player_skills={"lamaism": 0})
    master_eid = next(
        e for e in game.world.entities_in_room("room/test")
        if not game.world.get(e, Identity).is_player
    )
    # master 是 NPC（is_player=False）
    assert improve_skill(game.world, master_eid, "lamaism", 100) is False
    m_skills = game.world.get(master_eid, Skills)
    assert "lamaism" not in m_skills.learned


def test_improve_skill_multi_skill_penalty() -> None:
    """已学技能种类 > 30 时 amount 按超出量整除衰减（skill.c:164-168）。"""
    game, pid, _ = _game()
    world = game.world
    skills = world.get(pid, Skills)
    # 填 32 个 learned 条目（> 30 触发惩罚，amount //= 32-30=2）
    for i in range(32):
        skills.learned[f"skill{i}"] = 1
    # weak_mode=True 不升级，learned 累积衰减后 amount（10//(32-30)=5）
    improve_skill(world, pid, "lamaism", 10, weak_mode=True)
    assert skills.learned["lamaism"] == 5


# ──────────────────────── learn 命令（对照 learn.c:16-151） ────────────────────────


def test_learn_success(monkeypatch) -> None:
    """learn 消耗 potential + jing，learned 累积 gain（gain=Σ random(int)）。"""
    monkeypatch.setattr("xkx.runtime.commands.random.randint", lambda a, b: 10)
    game, pid, _ = _game(
        master_skills={"lamaism": 50}, player_skills={"lamaism": 0}, potential=100, jing=500
    )
    msgs = learn(game, pid, "贡藏", "lamaism", 1)
    world = game.world
    assert world.get(pid, Progression).potential == 99  # 扣 1
    assert world.get(pid, Vitals).jing < 500  # 扣 jing
    # gain=10 > 阈值 (0+1)²=1 -> 升级 levels=1，learned 清零
    assert world.get(pid, Skills).levels["lamaism"] == 1
    assert world.get(pid, Skills).learned["lamaism"] == 0
    assert any("请教" in m for m in msgs)


def test_learn_busy_blocked() -> None:
    """busy 期间 learn 被阻止（命令内 is_busy helper，对照 bai.c:15）。"""
    game, pid, _ = _game(master_skills={"lamaism": 50})
    apply_condition(game.world, pid, "exercise", duration=3, detail="force")
    assert is_busy(game.world, pid) is True
    msgs = learn(game, pid, "贡藏", "lamaism")
    assert msgs == ["你现在正忙着呢。"]


def test_learn_not_apprentice_rejected() -> None:
    """非师傅弟子不能 learn（对照 learn.c:52-56 is_apprentice_of）。"""
    game, pid, _ = _game(master_skills={"lamaism": 50}, apprentice=False)
    msgs = learn(game, pid, "贡藏", "lamaism")
    assert "弟子" in msgs[0]


def test_learn_combat_exp_gate(monkeypatch) -> None:
    """martial 技能 my_skill³/10 > combat_exp 阻止提升（仍消耗 jing，learn.c:120-122）。"""
    register_skill_data("sword_skill", SkillData(skill_type="martial"))
    monkeypatch.setattr("xkx.runtime.commands.random.randint", lambda a, b: 10)
    # my_skill=50 -> 50³/10=12500 > combat_exp=500 -> 阻止
    game, pid, _ = _game(
        master_skills={"sword_skill": 100}, player_skills={"sword_skill": 50}, combat_exp=500
    )
    jing_before = game.world.get(pid, Vitals).jing
    msgs = learn(game, pid, "贡藏", "sword_skill")
    assert game.world.get(pid, Vitals).jing < jing_before  # 仍消耗 jing
    assert "实战经验" in msgs[-1]
    # learned 不增加（blocked_by_exp 不调 improve_skill）
    assert "sword_skill" not in game.world.get(pid, Skills).learned


# ──────────────────────── practice 命令（对照 practice.c:9-81） ────────────────────────


def test_practice_requires_enable() -> None:
    """practice 须先 enable 特殊技能（query_skill_mapped，practice.c:49-50）。"""
    game, pid, _ = _game(player_skills={"sword": 30, "xueshan-jian": 20})
    msgs = practice(game, pid, "sword")
    assert "enable" in msgs[0]


def test_practice_basic_threshold() -> None:
    """skill_basic/2 <= skill/3 时基本功火候未到（practice.c:59-60）。"""
    # skill_basic=10, skill=20 -> 10/2=5 <= 20/3=6 -> 拒绝
    game, pid, _ = _game(
        player_skills={"sword": 10, "xueshan-jian": 20},
        player_skill_map={"sword": "xueshan-jian"},
    )
    msgs = practice(game, pid, "sword")
    assert "基本功" in msgs[0]


def test_practice_weak_mode_when_basic_le_skill() -> None:
    """skill_basic <= skill 时 weak_mode=1（只攒点不升级，practice.c:71）。"""
    # skill_basic=30, skill=30 -> weak_mode=1（30 > 30 否）
    game, pid, _ = _game(
        player_skills={"sword": 30, "xueshan-jian": 30},
        player_skill_map={"sword": "xueshan-jian"},
    )
    practice(game, pid, "sword", 1)
    skills = game.world.get(pid, Skills)
    # amount = 30/5+1=7，weak_mode 不升级但 learned 累积
    assert skills.learned["xueshan-jian"] == 7
    assert skills.levels["xueshan-jian"] == 30  # 不升级


def test_practice_upgrades_when_basic_gt_skill() -> None:
    """skill_basic > skill 时 weak_mode=0（可升级）。"""
    # skill_basic=100, skill=1 -> weak_mode=0（100>1），amount=100/5+1=21
    # lvl=1 阈值 4，learned=21 > 4 -> 升级到 2
    game, pid, _ = _game(
        player_skills={"sword": 100, "xueshan-jian": 1},
        player_skill_map={"sword": "xueshan-jian"},
    )
    msgs = practice(game, pid, "sword", 1)
    skills = game.world.get(pid, Skills)
    assert skills.levels["xueshan-jian"] == 2  # 升级
    assert any("进步" in m for m in msgs)


# ──────────────────────── dazuo 命令（对照 dazuo.c:12-72） ────────────────────────


def test_dazuo_requires_enable_force() -> None:
    """dazuo 须先 enable force（dazuo.c:45-46）。"""
    game, pid, _ = _game(player_skills={"force": 100})  # 无 skill_map force
    msgs = dazuo(game, pid, 100)
    assert "enable" in msgs[0] and "内功" in msgs[0]


def test_dazuo_cost_too_low() -> None:
    """exercise_cost < 10 拒绝（dazuo.c:50-51）。"""
    game, pid, _ = _game(
        player_skills={"force": 100, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
    )
    msgs = dazuo(game, pid, 5)
    assert "境界" in msgs[0]


def test_dazuo_starts_busy() -> None:
    """dazuo 后 is_busy=True + pending/exercise mark 设置。"""
    game, pid, _ = _game(
        player_skills={"force": 100, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
        qi=300, jing=300,
    )
    dazuo(game, pid, 50)
    assert is_busy(game.world, pid) is True
    assert "pending/exercise" in game.world.get(pid, Marks).flags
    assert query_condition(game.world, pid, "exercise") > 0


def test_dazuo_neili_growth_per_tick() -> None:
    """dazuo 每 tick neili 增长（1+有效force/10），qi 消耗（dazuo.c:80-83）。"""
    # levels["force"]=0, skill_map force=xueshan-neigong(100) -> 有效 force=100 -> gain=11
    game, pid, _ = _game(
        player_skills={"force": 0, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
        qi=500, jing=500, max_neili=1000,  # max_neili 大避免 clamp
    )
    dazuo(game, pid, 12)  # duration=ceil(12/11)=2
    neili_before = game.world.get(pid, Vitals).neili
    qi_before = game.world.get(pid, Vitals).qi
    _advance(game.world, 1)  # 1 tick
    vitals = game.world.get(pid, Vitals)
    assert vitals.neili == neili_before + 11  # neili += gain
    assert vitals.qi == qi_before - 11  # qi -= gain


def test_dazuo_max_neili_increase_at_cap() -> None:
    """neili 达 max_neili*2 且未瓶颈则 max_neili++ + neili 重置（dazuo.c:99-103）。"""
    # 有效 force=100, con=20 -> threshold=100*20*2//3=1333。max_neili=5(<=1333) 可涨
    # gain=11, cost=12 -> duration=2, 2 tick neili=22>=max_neili*2=10 -> 涨
    game, pid, _ = _game(
        player_skills={"force": 0, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
        qi=500, jing=500, max_neili=5,
    )
    dazuo(game, pid, 12)
    _advance(game.world, 2)  # duration=2 结束
    vitals = game.world.get(pid, Vitals)
    assert vitals.max_neili == 6  # 涨 1
    assert vitals.neili == 6  # 重置为新 max
    assert is_busy(game.world, pid) is False  # busy 结束
    assert "pending/exercise" not in game.world.get(pid, Marks).flags


def test_dazuo_bottleneck_no_increase() -> None:
    """max_neili > force*con*2/3 时瓶颈，不涨 max（dazuo.c:95-98）。"""
    # force_eff=0（levels 全 0），threshold=0*20*2//3=0。max_neili=5 > 0 瓶颈
    # gain=1+0=1, cost=12 -> duration=12, neili 累积达 max_neili*2=10 -> 触发瓶颈
    game, pid, _ = _game(
        player_skills={"force": 0, "xueshan-neigong": 0},
        player_skill_map={"force": "xueshan-neigong"},
        qi=500, jing=500, max_neili=5,
    )
    dazuo(game, pid, 12)
    _advance(game.world, 12)
    vitals = game.world.get(pid, Vitals)
    assert vitals.max_neili == 5  # 瓶颈不涨
    assert vitals.neili == 5  # 重置为 max（不涨）
    assert is_busy(game.world, pid) is False


# ──────────────────────── tuna 命令（对照 tuna.c:11-58） ────────────────────────


def test_tuna_jingli_growth_per_tick() -> None:
    """tuna 每 tick jingli 增长（1+原始force/10），jing 消耗（tuna.c:65-68）。"""
    # raw force=100（levels["force"]=100），gain=1+10=11
    game, pid, _ = _game(
        player_skills={"force": 100, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
        qi=500, jing=500, jingli=0, max_jingli=1000,
    )
    tuna(game, pid, 12)  # duration=ceil(12/11)=2
    jingli_before = game.world.get(pid, Vitals).jingli
    jing_before = game.world.get(pid, Vitals).jing
    _advance(game.world, 1)
    vitals = game.world.get(pid, Vitals)
    assert vitals.jingli == jingli_before + 11  # jingli += gain
    assert vitals.jing == jing_before - 11  # jing -= gain


def test_tuna_max_jingli_increase_at_cap() -> None:
    """jingli 达 max_jingli*2 且未瓶颈则 eff_jingli++ & max_jingli++（tuna.c:85-89）。"""
    # raw force=100 -> gain=11。有效 force=0+100//2+100=150（levels force=100, neigong=100）
    # threshold=150*20//2=1500。max_jingli=5 <= 1500 未瓶颈 -> 涨
    # cost=12 -> duration=2, 2 tick jingli=22>=max_jingli*2=10 -> 涨
    game, pid, _ = _game(
        player_skills={"force": 100, "xueshan-neigong": 100},
        player_skill_map={"force": "xueshan-neigong"},
        qi=500, jing=500, jingli=0, max_jingli=5,
    )
    tuna(game, pid, 12)
    _advance(game.world, 2)
    vitals = game.world.get(pid, Vitals)
    assert vitals.max_jingli == 6  # 涨 1
    assert vitals.eff_jingli == 1  # 涨 1
    assert vitals.jingli == 6  # 重置
    assert is_busy(game.world, pid) is False


# ──────────────────────── enable 命令（对照 enable.c:40-128） ────────────────────────


def test_enable_set_map() -> None:
    """enable <type> <map_to> 设映射（须会该技能，enable.c:96-97）。"""
    game, pid, _ = _game(player_skills={"xueshan-jian": 50})
    msgs = enable(game, pid, "sword", "xueshan-jian")
    assert game.world.get(pid, Skills).skill_map["sword"] == "xueshan-jian"
    assert any("xueshan-jian" in m for m in msgs)


def test_enable_unknown_skill_rejected() -> None:
    """未学会的技能不能 enable（enable.c:96-97）。"""
    game, pid, _ = _game()
    msgs = enable(game, pid, "sword", "xueshan-jian")
    assert "不会" in msgs[0]
    assert "sword" not in game.world.get(pid, Skills).skill_map


def test_enable_force_clears_neili() -> None:
    """切换 force 清 neili（enable.c:116-119）。"""
    game, pid, _ = _game(player_skills={"xueshan-neigong": 50}, neili=80)
    assert game.world.get(pid, Vitals).neili == 80
    enable(game, pid, "force", "xueshan-neigong")
    assert game.world.get(pid, Vitals).neili == 0


def test_enable_none_clears_map() -> None:
    """enable <type> none 取消映射（enable.c:86-90）。"""
    game, pid, _ = _game(
        player_skills={"xueshan-jian": 50},
        player_skill_map={"sword": "xueshan-jian"},
    )
    msgs = enable(game, pid, "sword", "none")
    assert "sword" not in game.world.get(pid, Skills).skill_map
    assert "基本功夫" in msgs[0]


def test_enable_invalid_type_rejected() -> None:
    """无效技能种类拒绝（enable.c:83-84 valid_types）。"""
    game, pid, _ = _game(player_skills={"foo": 50})
    msgs = enable(game, pid, "foo", "foo")
    assert "不是有效" in msgs[0]


def test_enable_list_no_args() -> None:
    """enable 无参列出当前 skill_map（enable.c:48-69）。"""
    game, pid, _ = _game(
        player_skills={"xueshan-jian": 50, "force": 0, "xueshan-neigong": 100},
        player_skill_map={"sword": "xueshan-jian", "force": "xueshan-neigong"},
    )
    msgs = enable(game, pid)
    text = "\n".join(msgs)
    assert "sword" in text and "xueshan-jian" in text


# ──────────────────────── busy 阻止其他命令 ────────────────────────


def test_busy_blocks_all_practice_commands() -> None:
    """dazuo busy 期间 learn/practice/dazuo/tuna 均被 is_busy 阻止。"""
    game, pid, _ = _game(
        player_skills={"force": 100, "xueshan-neigong": 100, "sword": 30, "xueshan-jian": 20},
        player_skill_map={"force": "xueshan-neigong", "sword": "xueshan-jian"},
        master_skills={"lamaism": 50},
        qi=500, jing=500,
    )
    dazuo(game, pid, 50)  # 启动 exercise busy
    assert is_busy(game.world, pid) is True
    assert learn(game, pid, "贡藏", "lamaism") == ["你现在正忙着呢。"]
    assert practice(game, pid, "sword") == ["你现在正忙着呢。"]
    assert dazuo(game, pid, 50) == ["你现在正忙着呢。"]
    assert tuna(game, pid, 50) == ["你现在正忙着呢。"]


def test_busy_conditions_set() -> None:
    """BUSY_CONDITIONS 含 exercise + respirate（dazuo/tuna 两种 busy）。"""
    assert "exercise" in BUSY_CONDITIONS
    assert "respirate" in BUSY_CONDITIONS
    assert len(BUSY_CONDITIONS) == 2


def test_get_skill_data_default_stub() -> None:
    """get_skill_data 未注册返回默认 SkillData（全允许，M3-1 stub）。"""
    data = get_skill_data("nonexistent-skill")
    assert data.valid_learn is True
    assert data.practice_skill is True
    assert data.valid_enable == []
    assert data.skill_type == ""
