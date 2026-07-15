"""pilot 样本 id=10：clone/beast/snake.c:init 迁移代码。

对照 LPC clone/beast/snake.c L33-44 init 函数体（含第 5 行 inherit NPC_TRAINEE
声明）。snake 的 attitude=peaceful，但进房间时按玩家 kar+per 随机概率触发
攻击，是引擎 _decide_room_enter_fight 三态（hatred/vendetta/aggressive）之外
的"peaceful+属性概率"第四态。本文件为一次性测量代码（ADR-0048 决策 8）。

LPC init 三步（L36-43）：
1. ::init() 父类钩子（引擎等价 _trigger_room_enter_fight，本函数即 init 本体，
   不递归调用）
2. add_action("convert","bian") per-object 命令注册（COMMAND_REGISTRY 仅全局
   verb 表，无 per-NPC 注册机制，缺口跳过）
3. interactive(player) && family!="白驼山" && random(kar+per)<30 ->
   remove_call_out("kill_ob") 防重入 + call_out("kill_ob",1,player) 延迟 1
   tick 攻击（引擎 NPC 主动攻击已同步即时化，ADR-0027 §1.2，call_out 延迟 1
   tick 翻译为同步 initiate_combat）
"""

from __future__ import annotations

import random

from xkx.runtime.auto_fight import initiate_combat
from xkx.runtime.commands import Game
from xkx.runtime.components import Identity, Position
from xkx.runtime.query import query

# random(kar+per)<30 的概率门阈值（对照 snake.c L40 < 30）
_PROB_THRESHOLD = 30


def query_kar(world, eid: int) -> int:
    """玩家福缘 kar（对照 LPC ob->query_kar()）。

    缺口桩：kar 仅在 AccountRecord 账号层（account.py:52）生成，未进运行时
    角色组件，query(world,eid,'kar') 会 raise DbaseKeyError。本桩默认回落 0，
    测试用 monkeypatch 注入具体 kar 值验证概率分支。真实需在 Attributes 增
    kar/per 字段 + query_kar/query_per sefun。
    """
    return 0


def query_per(world, eid: int) -> int:
    """玩家容貌 per（对照 LPC ob->query_per()）。

    缺口桩：同 query_kar，per 仅账号层（account.py:54，per=60-kar-pat），
    未进角色组件。默认回落 0，测试用 monkeypatch 注入。
    """
    return 0


def snake_c_init(game: Game, npc_eid: int) -> list[str]:
    """snake.c:init 迁移（对照 L33-44）。

    这是 NPC 侧 init：玩家进入 NPC 所在房间时触发。返回 actor（玩家）可见
    消息列表（init 非命令，LPC 无返回值；这里返回触发攻击的提示消息对齐
    引擎 _trigger_room_enter_fight 的 ["你被攻击了！"] 惯例，无触发则返回 []）。

    补全的第四态分支（peaceful + kar/per 概率攻击）：snake attitude=peaceful
    不走 _decide_room_enter_fight 的 aggressive 分支，本函数补这个特有概率
    判定。call_out("kill_ob",1,ob) 延迟 1 tick 在引擎已同步即时化（ADR-0027
    §1.2），remove_call_out 防重入语义由 auto_fight 的 looking_for_trouble
    标记承接，此处直接 initiate_combat。

    缺口（不迁移，仅记）：
    - inherit NPC_TRAINEE 驯兽能力（trainable/wildness/auto_follow）全引擎无
    - add_action per-object bian 命令注册（COMMAND_REGISTRY 仅全局 verb 表）
    """
    world = game.world

    # L36：::init() 父类钩子——本函数即 init 本体，不递归调 _trigger_room_enter_fight
    # （那会再次遍历房间 NPC，含 snake 自身，导致无限递归）。snake 特有逻辑在下面。

    # L37：add_action("convert","bian") per-object 命令注册——缺口跳过
    # （新引擎无 per-NPC 自定义命令注册机制，convert 不在 COMMAND_REGISTRY）

    # L38-43：interactive(player) && family!="白驼山" && random(kar+per)<30
    pos = world.get(npc_eid, Position)
    if pos is None:
        return []

    # 找房间内第一个玩家（对齐 LPC this_player() 是进房间的玩家）
    player_eid: int | None = None
    for eid in world.entities_in_room(pos.room_id):
        if eid == npc_eid:
            continue
        ident = world.get(eid, Identity)
        if ident is not None and ident.is_player:
            player_eid = eid
            break
    if player_eid is None:
        return []

    # interactive(ob) —— 引擎用 Identity.is_player 近似（缺 link-dead 断线区分，
    # triage partial_apis 记）。上面已筛 is_player。

    # L39：family != "白驼山"——白驼山弟子不被蛇攻击
    family = query(world, player_eid, "family_name") or ""
    if family == "白驼山":
        return []

    # L40：random(kar+per) < 30——peaceful+属性概率第四态
    kar = query_kar(world, player_eid)
    per = query_per(world, player_eid)
    if random.randint(0, max(0, kar + per - 1)) >= _PROB_THRESHOLD:
        return []

    # L41-42：remove_call_out("kill_ob") + call_out("kill_ob", 1, ob)
    # remove_call_out 防重入：引擎由 auto_fight 的 looking_for_trouble 标记承接
    # （auto_fight.py:192 _has_flag 跳过已有标记的触发）。call_out 延迟 1 tick：
    # 引擎 NPC 主动攻击已同步即时化（ADR-0027 §1.2），直接 initiate_combat
    # （对齐 LPC kill_ob，to_death=True，双向写 killer_ids）。
    initiate_combat(world, npc_eid, player_eid, to_death=True)

    return ["你被攻击了！"]
