"""层 F-HELL：阴间流程 -- LPC 规格提取。

覆盖范围：
- ``d/death/gate.c`` -- 鬼门关（DEATH_ROOM）：create、init（剥离 inventory、
  清除状态）
- ``d/death/gateway.c`` -- 酆都城门：create、valid_leave（禁止往南返回）、init
- ``d/death/road1.c`` -- 鬼门大道：create、init
- ``d/death/road2.c`` -- 鬼门大道（五段迷雾）：create、valid_leave（5 步计数）、
  init
- ``d/death/inn1.c`` -- 小店（隐藏还阳路径）：create、redirect_ask、do_stuff
- ``d/death/inn2.c`` -- 黑店（墙上提示）：create、item_desc
- ``d/death/npc/wgargoyle.c`` -- 白无常：create、init、death_stage（5 段轮回）
- ``d/death/npc/bgargoyle.c`` -- 黑无常：create、init、death_stage（鬼魂检查）
- ``d/death/hell.c`` -- 第十八层地狱：init、block_cmd（命令白名单）
- ``d/death/death.c`` / ``d/death/block.c`` -- 死刑室：init、block_cmd（仅允许
  quit/suicide/goto）
- ``d/death/blkbot.c`` -- 作弊者监狱：create、reset、init、valid_leave
- ``d/death/noteroom.c`` -- 玩家犯罪记录室：create、init（仅巫师可进入）
- ``adm/daemons/logind.c:642-662`` -- 登录时 ghost 起始房间与 death_count 惩罚检查
- ``feature/damage.c`` -- ``is_ghost`` / ``reincarnate``（已在层 F-DEATH 详述，
  此处仅引用）
- ``include/login.h`` -- ``DEATH_ROOM`` / ``REVIVE_ROOM`` 宏

核心契约要点：
1. **鬼门关是阴间唯一入口**：``DEATH_ROOM = /d/death/gate.c``，
   ``feature/damage.c:die()`` 中通过 ``DEATH_ROOM->start_death(this_object())``
   触发阴间流程，但 ``gate.c`` 中并不存在 ``start_death`` 函数，
   该调用在 LPC 运行时是无害幻影（phantom call）。
2. **单向流程**：gateway.c ``valid_leave`` 禁止往南（返回 gate），
   road2.c 往北需累计 5 次 ``long_road`` 计数，往南则重置。
3. **无常自动还阳**：白无常/黑无常 ``init`` 对非巫师玩家安排
   ``call_out("death_stage", 30, ob, 0)``，经过 5 段消息后在 ``REVIVE_ROOM``
   还阳；黑无常额外检查 ``is_ghost()``，非鬼魂踢回 ``/d/city/wumiao``。
4. **隐藏还阳路径**：inn1.c 中玩家对自己 ask about 回家，
   直接调用 ``reincarnate()`` 并移到 ``/d/city/wumiao``。
5. **地狱命令白名单**：hell.c 的 block_cmd 仅放行
   say/tell/reply/who/look/quit/suicide/goto，其余命令被拦截；
   death.c/block.c 仅放行 quit/suicide/goto。
6. **登录检查**：logind.c 中 ghost 玩家登录直接送到 ``DEATH_ROOM``；
   ``death_count > 200`` 且 ``combat_exp < 50000`` 的玩家被强制移到
   ``/d/death/block.c``（死刑室）。

不做（边界）：
- ``die()`` / ``death_penalty()`` / ``killer_reward()`` / ``make_corpse()``
  已在层 F-DEATH 详述，此处不重复。
- 尸体腐烂、PvP 通缉、战斗上游触发逻辑均已在层 F-DEATH / E。
- ``start_death()`` 函数本身不存在，不做实现规格。
"""

from __future__ import annotations

from enum import StrEnum

from xkx.spec.base import (
    FunctionSignature,
    FunctionSpec,
    Invariant,
    LayerSpec,
    LPCParam,
    Postcondition,
    Precondition,
    SideEffect,
    SideEffectType,
)

# ---------------------------------------------------------------------------
# 层 F-HELL 特定常量
# ---------------------------------------------------------------------------

DEATH_ROOM: str = "/d/death/gate.c"
"""阴间入口房间路径（对应 include/login.h 宏）。"""

REVIVE_ROOM: str = "/d/city/wumiao.c"
"""还阳目标房间路径（对应 include/login.h 宏）。"""

XKD_START_ROOM: str = "/d/xiakedao/shatan"
"""侠客岛新手起始房间（白无常还阳分支）。"""

EXECUTION_ROOM: str = "/d/death/block.c"
"""death_count 惩罚房间（死刑室）。"""

WIZARD_ROOM: str = "/d/wizard/wizard_room"
"""犯罪记录室东侧出口（巫师房间）。"""


class HellCmd(StrEnum):
    """第十八层地狱（hell.c）命令白名单。"""

    SAY = "say"
    TELL = "tell"
    REPLY = "reply"
    WHO = "who"
    LOOK = "look"
    QUIT = "quit"
    SUICIDE = "suicide"
    GOTO = "goto"


class ExecutionCmd(StrEnum):
    """死刑室（death.c / block.c）命令白名单。"""

    QUIT = "quit"
    SUICIDE = "suicide"
    GOTO = "goto"


HELL_CMD_WHITELIST: frozenset[str] = frozenset(HellCmd)
EXECUTION_CMD_WHITELIST: frozenset[str] = frozenset(ExecutionCmd)

# ---------------------------------------------------------------------------
# 房间 create / init 规格
# ---------------------------------------------------------------------------

_gate_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/gate.c",
        line_range=(8, 24),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '鬼门关'",
            state_change='set("short", HIW "鬼门关" NOR)',
            kind="effect",
        ),
        Postcondition(
            description="north 出口指向 /d/death/gateway",
            state_change='set("exits", (["north": "/d/death/gateway"]))',
            kind="effect",
        ),
        Postcondition(
            description="房间加载白无常 NPC（npc/wgargoyle）",
            state_change='set("objects", ([__DIR__"npc/wgargoyle": 1]))',
            kind="effect",
        ),
        Postcondition(
            description="no_fight=1 禁止战斗，cost=0 不消耗精力",
            state_change='set("no_fight", 1); set("cost", 0)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="DEATH_ROOM（/d/death/gate.c）是阴间流程起点",
            lpc_expr='DEATH_ROOM == "/d/death/gate.c"',
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/objects/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("objects", ...); set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup() 完成房间初始化",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="鬼门关是 DEATH_ROOM，由 feature/damage.c:die() move 到此触发阴间流程。",
)

_gate_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/gate.c",
        line_range=(26, 48),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入房间（this_player() 有效）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="玩家非角色类 inventory 物品全部被 destruct",
            state_change="all_inventory(me) 中非 is_character() 的物品 destruct",
            kind="effect",
        ),
        Postcondition(
            description="清除玩家所有 condition 状态",
            state_change="me->clear_condition()",
            kind="effect",
        ),
        Postcondition(
            description="若玩家有 sanxiao 临时标记，删除 sanxiao 与 smile 标记",
            state_change="me->delete_temp('sanxiao'); me->delete_temp('smile')",
            kind="effect",
        ),
        Postcondition(
            description="注册 suicide 命令拦截",
            state_change='add_action("do_suicide", "suicide")',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="进入鬼门关时玩家携带物品被剥离（仅保留角色对象）",
            lpc_expr="inv[i]->is_character() ? keep : destruct(inv[i])",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="遍历 inventory，非角色物品 destruct",
            lpc_call="for(inv=all_inventory(me); ...) if(!inv[i]->is_character()) destruct(inv[i])",
            target="player.inventory",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="me->clear_condition() 清除所有状态",
            lpc_call="me->clear_condition()",
            target="player.conditions",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 sanxiao / smile 临时标记",
            lpc_call='me->delete_temp("sanxiao"); me->delete_temp("smile")',
            target="player.temp",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 do_suicide 命令拦截",
            lpc_call='add_action("do_suicide", "suicide")',
            target="room.commands",
        ),
    ],
    notes="init 在玩家进入鬼门关时触发，剥离物品并清除状态是阴间入口的标准化操作。",
)

_gateway_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/gateway.c",
        line_range=(6, 26),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '酆都城门'",
            kind="effect",
        ),
        Postcondition(
            description="north 通 road1，south 通 gate",
            state_change='set("exits", (["north":"/d/death/road1", "south":"/d/death/gateway"]))',
            kind="effect",
        ),
        Postcondition(
            description="加载黑无常 NPC",
            state_change='set("objects", ([__DIR__"npc/bgargoyle": 1]))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="gateway.c 是 gate 之后第二个房间，呈现单向流程设计",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/objects/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("objects", ...); set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="酆都城门是 gate 的北侧邻居，加载黑无常。",
)

_gateway_valid_leave = FunctionSpec(
    signature=FunctionSignature(
        name="valid_leave",
        params=[
            LPCParam(name="me", lpc_type="object", description="离开者对象"),
            LPCParam(name="dir", lpc_type="string", description="离开方向"),
        ],
        return_type="int",
        lpc_file="d/death/gateway.c",
        line_range=(28, 37),
    ),
    preconditions=[
        Precondition(
            description="me 是有效对象，dir 是 exits 中存在的方向",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="巫师或 NPC 离开不受限制，返回 1",
            state_change="if(wizardp(me) || !userp(me)) return 1",
            kind="effect",
        ),
        Postcondition(
            description="玩家往南（返回 gate）被拦截并提示",
            state_change='if(dir=="south") notify_fail("没有回头路了!")',
            kind="effect",
        ),
        Postcondition(
            description="其他方向玩家允许离开，返回 1",
            return_value="1=允许, 0=拦截",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="阴间流程单向：gateway 禁止玩家往南返回鬼门关",
            lpc_expr='dir=="south" && userp(me) && !wizardp(me) => notify_fail',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="巫师或 NPC 直接返回 1",
            lpc_call="if(wizardp(me) || !userp(me)) return 1",
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="玩家往南时输出 '没有回头路了!'",
            lpc_call='notify_fail("一个空洞的声音在你耳边响起....\\n没有回头路了!\\n")',
            target="player",
        ),
    ],
    notes="单向流程守卫：玩家无法从酆都城门返回鬼门关。",
)

_gateway_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/gateway.c",
        line_range=(39, 49),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="注册 suicide 命令拦截，提示 '你还死着呢。'",
            state_change='add_action("do_suicide", "suicide")',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 do_suicide 命令",
            lpc_call='add_action("do_suicide", "suicide")',
            target="room.commands",
        ),
    ],
    notes="gateway 仅拦截 suicide 命令。",
)

_road1_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/road1.c",
        line_range=(6, 27),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '鬼门大道'",
            kind="effect",
        ),
        Postcondition(
            description="north 通 road2，south 通 gateway，west 通 inn1，east 通 inn2",
            state_change='set("exits", (["north":"/d/death/road2", "south":"/d/death/gateway", '
            '"west":"/d/death/inn1", "east":"/d/death/inn2"]))',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="road1 是阴间主路十字节点，连接 inn1/inn2 两个支线房间。",
)

_road1_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/road1.c",
        line_range=(29, 40),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="注册 suicide 命令拦截",
            state_change='add_action("do_suicide", "suicide")',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 do_suicide 命令",
            lpc_call='add_action("do_suicide", "suicide")',
            target="room.commands",
        ),
    ],
    notes="road1 仅拦截 suicide。",
)

_road2_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/road2.c",
        line_range=(6, 23),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '鬼门大道'",
            kind="effect",
        ),
        Postcondition(
            description="north 通 road3，south 通 road1",
            state_change='set("exits", (["north":"/d/death/road3", "south":"/d/death/road1"]))',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="road2 是五段迷雾路，往北需累计 5 次尝试。",
)

_road2_valid_leave = FunctionSpec(
    signature=FunctionSignature(
        name="valid_leave",
        params=[
            LPCParam(name="me", lpc_type="object", description="离开者对象"),
            LPCParam(name="dir", lpc_type="string", description="离开方向"),
        ],
        return_type="int",
        lpc_file="d/death/road2.c",
        line_range=(24, 46),
    ),
    preconditions=[
        Precondition(
            description="me 是有效对象",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="往北时累加 long_road 计数，达到 5 才允许通过",
            state_change="i = me->query_temp('long_road') + 1; if(i==5) delete_temp; else set_temp",
            kind="effect",
        ),
        Postcondition(
            description="往南时删除 long_road 计数并允许离开",
            state_change='if(dir=="south") me->delete_temp("long_road"); return 1',
            kind="effect",
        ),
        Postcondition(
            description="其他方向直接允许",
            return_value="1=允许, 0=失败提示",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="往北必须通过 5 次 'long_road' 累积才离开（迷雾迷宫）",
            lpc_expr="long_road in [0,4] => notify_fail; long_road == 5 => return 1",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="往北：long_road + 1",
            lpc_call="i = me->query_temp('long_road') + 1; me->set_temp('long_road', i)",
            target="player.temp",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="未达 5 次时提示 '你发现四周景色居然都没有变....'",
            lpc_call='notify_fail("你走著走著..... 发现四周景色居然都没有变....\\n")',
            target="player",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="达到 5 次时删除 long_road 并返回 1",
            lpc_call="me->delete_temp('long_road'); return 1",
            target="player.temp",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="往南：删除 long_road 并返回 1",
            lpc_call='me->delete_temp("long_road"); return 1',
            target="player.temp",
        ),
    ],
    notes="5 步迷雾是阴间主路的小迷宫，往南重置计数。",
)

_road2_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/road2.c",
        line_range=(48, 59),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="注册 suicide 命令拦截",
            state_change='add_action("do_suicide", "suicide")',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 do_suicide 命令",
            lpc_call='add_action("do_suicide", "suicide")',
            target="room.commands",
        ),
    ],
    notes="road2 仅拦截 suicide。",
)

_inn1_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/inn1.c",
        line_range=(8, 35),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '小店'",
            kind="effect",
        ),
        Postcondition(
            description="east 出口指向 /d/death/road1",
            state_change='set("exits", (["east":"/d/death/road1"]))',
            kind="effect",
        ),
        Postcondition(
            description="item_desc shadows 描述黑影中的自己",
            state_change='set("item_desc", (["shadows": ...]))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="inn1 是隐藏还阳路径，不通过无常流程也可还阳",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/item_desc/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("item_desc", ...); set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="小店是阴间隐藏还阳点，墙上黑影暗示 ask 自己 about 回家。",
)

_inn1_redirect_ask = FunctionSpec(
    signature=FunctionSignature(
        name="redirect_ask",
        params=[
            LPCParam(name="str", lpc_type="string", description="玩家输入的 ask 命令参数字符串"),
        ],
        return_type="int",
        lpc_file="d/death/inn1.c",
        line_range=(51, 65),
    ),
    preconditions=[
        Precondition(
            description="玩家在小店房间内执行 ask",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="输入格式为 '<自己id> about 回家' 时触发 do_stuff",
            state_change='if(sscanf(str, "%s about %s", tmp1, tmp2)==2 && tmp1==id && tmp2=="回家") do_stuff(ob)',
            kind="effect",
        ),
        Postcondition(
            description="格式不匹配返回 0",
            return_value="1=触发还阳, 0=未匹配",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="必须 ask 自己 about 回家才会触发隐藏还阳",
            lpc_expr='tmp1 == ob->query("id") && tmp2 == "回家"',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="解析 sscanf '<id> about <topic>'",
            lpc_call='sscanf(str, "%s about %s", tmp1, tmp2)',
            target="local_vars",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="匹配成功时调用 do_stuff(ob) 执行还阳",
            lpc_call="do_stuff(ob)",
            target="player",
        ),
    ],
    notes="redirect_ask 是隐藏命令分发器，只有 ask 自己 about 回家才生效。",
)

_inn1_do_stuff = FunctionSpec(
    signature=FunctionSignature(
        name="do_stuff",
        params=[
            LPCParam(name="ob", lpc_type="object", description="玩家对象"),
        ],
        return_type="int",
        lpc_file="d/death/inn1.c",
        line_range=(67, 83),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效玩家对象",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="输出玩家走向壁炉与黑影交谈的消息",
            kind="observable",
        ),
        Postcondition(
            description="调用 ob->reincarnate() 清除 ghost 并恢复属性",
            state_change="ob->reincarnate()",
            kind="effect",
        ),
        Postcondition(
            description="将玩家移到 /d/city/wumiao",
            state_change='ob->move("/d/city/wumiao")',
            kind="effect",
        ),
        Postcondition(
            description="在新房间输出 '多了一个人影' 的 vision 消息",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="隐藏还阳路径绕开无常 5 段消息，直接 reincarnate",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 玩家上前询问的消息",
            lpc_call='write("你走上前去, 低声的向那个长得跟你一样的人询问回家的事.\\n")',
            target="player",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_room 玩家走向壁炉",
            lpc_call='tell_room(environment(ob), name+"往壁炉那走去...", ({this_object(), ob}))',
            target="room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_room 玩家消失",
            lpc_call='tell_room(environment(ob), name+"竟然不见了.\\n", ({this_object(), ob}))',
            target="room",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="调用 ob->reincarnate()",
            lpc_call="ob->reincarnate()",
            target="player",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="ob->move('/d/city/wumiao')",
            lpc_call='ob->move("/d/city/wumiao")',
            target="player",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="新房间输出 vision 消息",
            lpc_call='message("vision", "你忽然发现前面多了一个人影...", environment(ob), ob)',
            target="room",
        ),
    ],
    notes="inn1 是 Easter-egg 式还阳路径，行为上等同于无常还阳但省略 NPC 对话。",
)

_inn2_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/inn2.c",
        line_range=(6, 38),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '黑店'",
            kind="effect",
        ),
        Postcondition(
            description="west 出口指向 /d/death/road1",
            state_change='set("exits", (["west":"/d/death/road1"]))',
            kind="effect",
        ),
        Postcondition(
            description="item_desc wall 给出还阳提示（ask 自己 about 回家）",
            state_change='set("item_desc", (["wall": ...]))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="inn2 墙上提示是 inn1 隐藏路径的线索",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/item_desc/cost/no_fight",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("item_desc", ...); set("cost", 0); set("no_fight", 1)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
    ],
    notes="黑店仅提供 wall 提示，本身不还阳。",
)

# ---------------------------------------------------------------------------
# 无常 NPC 规格
# ---------------------------------------------------------------------------

_wgargoyle_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/npc/wgargoyle.c",
        line_range=(19, 40),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="NPC 名称为 '白无常'，id 为 white gargoyle / gargoyle",
            state_change='set_name("白无常", ({"white gargoyle", "gargoyle"}))',
            kind="effect",
        ),
        Postcondition(
            description="attitude 为 peaceful，chat_chance=15",
            state_change='set("attitude", "peaceful"); set("chat_chance", 15)',
            kind="effect",
        ),
        Postcondition(
            description="基础属性 max_jing/max_jingli/max_qi/max_neili=900，年龄 217",
            state_change='set("max_jing", 900); ...',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 name/long/attitude/chat_chance/age/属性/skills",
            lpc_call='set_name(...); set("long", ...); set_skill("dodge", 40); ...',
            target="npc",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="npc",
        ),
    ],
    notes="白无常是 gate.c 加载的引导 NPC，负责自动还阳流程。",
)

_wgargoyle_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/npc/wgargoyle.c",
        line_range=(42, 49),
    ),
    preconditions=[
        Precondition(
            description="previous_object() 存在且为玩家，且非巫师",
            lpc_expr="previous_object() && userp(previous_object()) && !wizardp(previous_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="30 秒后调用 death_stage(previous_object(), 0)",
            state_change='call_out("death_stage", 30, previous_object(), 0)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="白无常 init 不对巫师和 NPC 触发",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="安排 30 秒后 death_stage(ob, 0)",
            lpc_call='call_out("death_stage", 30, previous_object(), 0)',
            target="npc",
        ),
    ],
    notes="白无常在玩家进入 gate 时启动 5 段还阳倒计时。",
)

_wgargoyle_death_stage = FunctionSpec(
    signature=FunctionSignature(
        name="death_stage",
        params=[
            LPCParam(name="ob", lpc_type="object", description="玩家对象"),
            LPCParam(name="stage", lpc_type="int", description="当前消息阶段 0-4"),
        ],
        return_type="void",
        lpc_file="d/death/npc/wgargoyle.c",
        line_range=(51, 72),
    ),
    preconditions=[
        Precondition(
            description="ob 有效且仍在 NPC 所在房间",
            lpc_expr="ob && present(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="向玩家输出 death_msg[stage]",
            state_change="tell_object(ob, death_msg[stage])",
            kind="effect",
        ),
        Postcondition(
            description="stage < 4 时 5 秒后递归调用 death_stage(ob, stage+1)",
            state_change='call_out("death_stage", 5, ob, stage+1)',
            kind="effect",
        ),
        Postcondition(
            description="stage == 4 时调用 ob->reincarnate()",
            state_change="ob->reincarnate()",
            kind="effect",
        ),
        Postcondition(
            description="还阳后掉落 inventory 物品",
            state_change="DROP_CMD->do_drop(ob, inv[i])",
            kind="effect",
        ),
        Postcondition(
            description="根据 xkd/set 标志决定目标房间：侠客岛沙滩或 REVIVE_ROOM",
            state_change='if(ob->query("xkd/set", 1)) move("/d/xiakedao/shatan"); else move(REVIVE_ROOM)',
            kind="effect",
        ),
        Postcondition(
            description="在新房间输出 vision 消息",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="death_msg 数组固定 5 条消息，依次输出",
            scope="function",
        ),
        Invariant(
            description="还阳后 inventory 物品全部掉落（DROP_CMD）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_object(ob, death_msg[stage])",
            lpc_call="tell_object(ob, death_msg[stage])",
            target="player",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.CALL_OUT,
            description="stage < 4 时递归安排 death_stage",
            lpc_call='call_out("death_stage", 5, ob, stage+1)',
            target="npc",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="stage == 4 时 ob->reincarnate()",
            lpc_call="ob->reincarnate()",
            target="player",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="掉落 inventory 中所有物品",
            lpc_call="for(inv=all_inventory(ob); ...) DROP_CMD->do_drop(ob, inv[i])",
            target="player.inventory",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="移到侠客岛沙滩或 REVIVE_ROOM",
            lpc_call='ob->move(ob->query("xkd/set", 1) ? "/d/xiakedao/shatan" : REVIVE_ROOM)',
            target="player",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="新房间输出 vision 消息",
            lpc_call='message("vision", "你忽然发现前面多了一个人影...", environment(ob), ob)',
            target="room",
        ),
    ],
    notes="白无常 5 段消息还阳流程，不检查 ghost 状态（已在 gate 保证）。",
)

_bgargoyle_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/npc/bgargoyle.c",
        line_range=(19, 42),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="NPC 名称为 '黑无常'，id 为 black gargoyle / gargoyle",
            state_change='set_name("黑无常", ({"black gargoyle", "gargoyle"}))',
            kind="effect",
        ),
        Postcondition(
            description="attitude 为 peaceful，chat_chance=15",
            kind="effect",
        ),
        Postcondition(
            description="基础属性 max_jing/max_jingli/max_qi/max_neili=900，临时护甲/伤害加成",
            state_change='set_temp("apply/armor", 60); set_temp("apply/damage", 20)',
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 name/long/attribution/属性/skills/temp apply",
            lpc_call='set_name(...); set_temp("apply/armor", 60); set_temp("apply/damage", 20)',
            target="npc",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="npc",
        ),
    ],
    notes="黑无常是 gateway.c 加载的引导 NPC，负责鬼魂检查与自动还阳。",
)

_bgargoyle_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/npc/bgargoyle.c",
        line_range=(44, 51),
    ),
    preconditions=[
        Precondition(
            description="previous_object() 存在且为玩家",
            lpc_expr="previous_object() && userp(previous_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="30 秒后调用 death_stage(previous_object(), 0)",
            state_change='call_out("death_stage", 30, previous_object(), 0)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="黑无常 init 不对 NPC 触发（未检查 wizardp）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="安排 30 秒后 death_stage(ob, 0)",
            lpc_call='call_out("death_stage", 30, previous_object(), 0)',
            target="npc",
        ),
    ],
    notes="黑无常在玩家进入 gateway 时启动还阳倒计时。",
)

_bgargoyle_death_stage = FunctionSpec(
    signature=FunctionSignature(
        name="death_stage",
        params=[
            LPCParam(name="ob", lpc_type="object", description="玩家对象"),
            LPCParam(name="stage", lpc_type="int", description="当前消息阶段 0-4"),
        ],
        return_type="void",
        lpc_file="d/death/npc/bgargoyle.c",
        line_range=(53, 84),
    ),
    preconditions=[
        Precondition(
            description="ob 有效且仍在 NPC 所在房间",
            lpc_expr="ob && present(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非鬼魂玩家被踢回 /d/city/wumiao",
            state_change='if(!ob->is_ghost()) { command("say 喂！阳人来阴间做什么？"); ob->move("/d/city/wumiao"); return; }',
            kind="effect",
        ),
        Postcondition(
            description="向玩家输出 death_msg[stage]",
            kind="effect",
        ),
        Postcondition(
            description="stage < 4 时递归调用 death_stage",
            kind="effect",
        ),
        Postcondition(
            description="stage == 4 时 reincarnate 并掉落物品、移到还阳房间",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="黑无常在 stage 开始处检查 is_ghost()，非鬼魂不执行还阳",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="非鬼魂时输出 say 并 move 到 /d/city/wumiao",
            lpc_call='command("say 喂！阳人来阴间做什么？"); ob->move("/d/city/wumiao"); return;',
            target="player",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_object(ob, death_msg[stage])",
            lpc_call="tell_object(ob, death_msg[stage])",
            target="player",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.CALL_OUT,
            description="stage < 4 时递归安排 death_stage",
            lpc_call='call_out("death_stage", 5, ob, stage+1)',
            target="npc",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="stage == 4 时 ob->reincarnate()",
            lpc_call="ob->reincarnate()",
            target="player",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="掉落 inventory 物品",
            lpc_call="for(inv=all_inventory(ob); ...) DROP_CMD->do_drop(ob, inv[i])",
            target="player.inventory",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="移到侠客岛沙滩或 REVIVE_ROOM",
            lpc_call='ob->move(ob->query("xkd/set", 1) ? "/d/xiakedao/shatan" : REVIVE_ROOM)',
            target="player",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="新房间输出 vision 消息",
            lpc_call='message("vision", "你忽然发现前面多了一个人影...", environment(ob), ob)',
            target="room",
        ),
    ],
    notes="黑无常与白无常流程相同，但额外检查 is_ghost()，防止阳间玩家误入。",
)

# ---------------------------------------------------------------------------
# 地狱 / 死刑室 / 监狱规格
# ---------------------------------------------------------------------------

_hell_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/hell.c",
        line_range=(13, 21),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入第十八层地狱房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非巫师玩家被添加 block_cmd 命令拦截",
            state_change="if(!wizardp(ob)) add_action('block_cmd', '', 1)",
            kind="effect",
        ),
        Postcondition(
            description="非巫师玩家的 startroom 设为 /d/death/hell",
            state_change='ob->set("startroom", "/d/death/hell")',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="第十八层地狱仅对非巫师玩家启用命令白名单",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="非巫师玩家注册 block_cmd 拦截所有命令",
            lpc_call='if(!wizardp(ob)) add_action("block_cmd", "", 1)',
            target="room.commands",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置玩家 startroom 为 /d/death/hell",
            lpc_call='ob->set("startroom", "/d/death/hell")',
            target="player.startroom",
        ),
    ],
    notes="第十八层地狱限制玩家只能使用白名单命令。",
)

_hell_block_cmd = FunctionSpec(
    signature=FunctionSignature(
        name="block_cmd",
        params=[],
        return_type="int",
        lpc_file="d/death/hell.c",
        line_range=(23, 32),
    ),
    preconditions=[
        Precondition(
            description="block_cmd 已通过 add_action 注册",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="命令在白名单中返回 0（允许后续处理）",
            return_value="0=允许, 1=拦截",
            kind="ensure",
        ),
        Postcondition(
            description="命令不在白名单中返回 1（拦截）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="白名单固定 8 条命令：say/tell/reply/who/look/quit/suicide/goto",
            lpc_expr="cmd in ('say','tell','reply','who','look','quit','suicide','goto') => return 0",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取当前命令 query_verb()",
            lpc_call="cmd = query_verb()",
            target="local_vars",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="白名单内返回 0，否则返回 1",
            lpc_call="if(cmd in whitelist) return 0; else return 1",
            target="return_value",
        ),
    ],
    notes="第十八层地狱命令白名单，其余命令被静默拦截。",
)

_death_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/death.c",
        line_range=(19, 28),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入死刑室",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非巫师玩家被添加 block_cmd 命令拦截",
            state_change="if(!wizardp(ob)) add_action('block_cmd', '', 1)",
            kind="effect",
        ),
        Postcondition(
            description="非巫师玩家的 startroom 设为 /d/death/death",
            state_change='ob->set("startroom", "/d/death/death")',
            kind="effect",
        ),
        Postcondition(
            description="非巫师玩家设置 block=1 标记",
            state_change='ob->set("block", 1)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="死刑室仅允许 quit/suicide/goto，是比地狱更严格的限制",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="非巫师玩家注册 block_cmd",
            lpc_call='if(!wizardp(ob)) add_action("block_cmd", "", 1)',
            target="room.commands",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 startroom 为 /d/death/death",
            lpc_call='ob->set("startroom", "/d/death/death")',
            target="player.startroom",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 block=1 标记",
            lpc_call='ob->set("block", 1)',
            target="player.block",
        ),
    ],
    notes="死刑室用于 death_count 惩罚和严重违规监禁。",
)

_death_block_cmd = FunctionSpec(
    signature=FunctionSignature(
        name="block_cmd",
        params=[],
        return_type="int",
        lpc_file="d/death/death.c",
        line_range=(30, 37),
    ),
    preconditions=[
        Precondition(
            description="block_cmd 已注册",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="quit/suicide/goto 返回 0 允许",
            return_value="0=允许, 1=拦截",
            kind="ensure",
        ),
        Postcondition(
            description="其他命令返回 1 拦截",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="死刑室白名单仅 3 条命令：quit/suicide/goto",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取 query_verb()",
            lpc_call="cmd = query_verb()",
            target="local_vars",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="quit/suicide/goto 返回 0，否则返回 1",
            lpc_call="if(cmd in ('quit','suicide','goto')) return 0; else return 1",
            target="return_value",
        ),
    ],
    notes="死刑室 block_cmd 比第十八层地狱更严格（仅 3 条命令）。",
)

_block_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/block.c",
        line_range=(13, 22),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入 block.c 死刑室",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非巫师玩家注册 block_cmd",
            state_change="if(!wizardp(ob)) add_action('block_cmd', '', 1)",
            kind="effect",
        ),
        Postcondition(
            description="设置 startroom 为 /d/death/death",
            state_change='ob->set("startroom", "/d/death/death")',
            kind="effect",
        ),
        Postcondition(
            description="设置 block=1 标记",
            state_change='ob->set("block", 1)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="block.c 与 death.c 行为等价，仅源文件不同",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="非巫师玩家注册 block_cmd",
            lpc_call='if(!wizardp(ob)) add_action("block_cmd", "", 1)',
            target="room.commands",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 startroom 为 /d/death/death",
            lpc_call='ob->set("startroom", "/d/death/death")',
            target="player.startroom",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 block=1 标记",
            lpc_call='ob->set("block", 1)',
            target="player.block",
        ),
    ],
    notes="block.c 是 death.c 的复本，logind 中死亡惩罚房间指向 block.c。",
)

_block_block_cmd = FunctionSpec(
    signature=FunctionSignature(
        name="block_cmd",
        params=[],
        return_type="int",
        lpc_file="d/death/block.c",
        line_range=(24, 31),
    ),
    preconditions=[
        Precondition(
            description="block_cmd 已注册",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="quit/suicide/goto 返回 0 允许",
            return_value="0=允许, 1=拦截",
            kind="ensure",
        ),
        Postcondition(
            description="其他命令返回 1 拦截",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="block.c block_cmd 与 death.c 行为等价",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取 query_verb()",
            lpc_call="cmd = query_verb()",
            target="local_vars",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="quit/suicide/goto 返回 0，否则返回 1",
            lpc_call="if(cmd in ('quit','suicide','goto')) return 0; else return 1",
            target="return_value",
        ),
    ],
    notes="block.c 与 death.c 的 block_cmd 完全一致。",
)

_blkbot_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/blkbot.c",
        line_range=(5, 17),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '空房间'，long 为 '自首吧...'",
            kind="effect",
        ),
        Postcondition(
            description="east 出口指向 noteroom",
            state_change='set("exits", (["east": __DIR__"noteroom"]))',
            kind="effect",
        ),
        Postcondition(
            description="valid_startroom=1，no_fight=1，cost=0",
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/valid_startroom/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("valid_startroom", 1); set("no_fight", 1); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="调用留言板 foo()",
            lpc_call='"/clone/board/emptyroom_b"->foo()',
            target="board",
        ),
    ],
    notes="blkbot 是作弊/机器人嫌疑玩家的监禁房间。",
)

_blkbot_reset = FunctionSpec(
    signature=FunctionSignature(
        name="reset",
        params=[],
        return_type="void",
        lpc_file="d/death/blkbot.c",
        line_range=(19, 23),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="调用父类 reset 后设置 no_clean_up=1",
            state_change="::reset(); set('no_clean_up', 1)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="blkbot 房间不会被清理（no_clean_up=1）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="调用父类 reset",
            lpc_call="::reset()",
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 no_clean_up=1",
            lpc_call='set("no_clean_up", 1)',
            target="room",
        ),
    ],
    notes="reset 保证监禁房间长期保留。",
)

_blkbot_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/blkbot.c",
        line_range=(24, 44),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入 blkbot 房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="注册大量技能/修炼/quit 命令的 do_practice 拦截",
            state_change='add_action("do_practice", "practice/lian/dazuo/...")',
            kind="effect",
        ),
        Postcondition(
            description="非巫师玩家 startroom 设为 /d/death/blkbot",
            state_change='ob->set("startroom", "/d/death/blkbot")',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="blkbot 中玩家无法进行练习、打坐、吐纳、读书、睡觉、炼内等命令",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 practice/lian/dazuo/exercise/tuna/du/study/sleep/"
            "respirate/xuelian/lianneili/lianqi/quit 命令拦截",
            lpc_call='add_action("do_practice", "practice"); ...',
            target="room.commands",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="非巫师玩家设置 startroom",
            lpc_call='if(!wizardp(ob)) ob->set("startroom", "/d/death/blkbot")',
            target="player.startroom",
        ),
    ],
    notes="blkbot 中所有成长类命令被拦截，仅允许有限交互。",
)

_blkbot_valid_leave = FunctionSpec(
    signature=FunctionSignature(
        name="valid_leave",
        params=[
            LPCParam(name="me", lpc_type="object", description="离开者对象"),
            LPCParam(name="dir", lpc_type="string", description="离开方向"),
        ],
        return_type="int",
        lpc_file="d/death/blkbot.c",
        line_range=(51, 56),
    ),
    preconditions=[
        Precondition(
            description="me 尝试离开房间",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="往东（noteroom）且非巫师时被拦截",
            state_change='if(dir=="east" && !wizardp(me)) notify_fail("那里只有巫师才能进去。")',
            kind="effect",
        ),
        Postcondition(
            description="其他情况调用父类 valid_leave",
            return_value="父类返回值",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="玩家不能进入 noteroom（仅巫师可进）",
            lpc_expr='dir=="east" && !wizardp(me) => notify_fail',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="往东且非巫师时拦截",
            lpc_call='if(dir=="east" && !wizardp(me)) return notify_fail("那里只有巫师才能进去。\\n")',
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="其他方向调用 ::valid_leave(me, dir)",
            lpc_call="return ::valid_leave(me, dir)",
            target="room",
        ),
    ],
    notes="blkbot 东侧 noteroom 仅限巫师进入。",
)

_noteroom_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="d/death/noteroom.c",
        line_range=(10, 29),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="short 设为 '玩家犯罪记录室'",
            kind="effect",
        ),
        Postcondition(
            description="east 通 wizard_room，west 通 blkbot",
            state_change='set("exits", (["east":"/d/wizard/wizard_room", "west":__DIR__"blkbot"]))',
            kind="effect",
        ),
        Postcondition(
            description="valid_startroom=1，no_fight='1'，cost=0",
            kind="effect",
        ),
    ],
    invariants=[],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 short/long/exits/valid_startroom/no_fight/cost",
            lpc_call='set("short", ...); set("long", ...); set("exits", ...); '
            'set("valid_startroom", 1); set("no_fight", "1"); set("cost", 0)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 setup()",
            lpc_call="setup()",
            target="room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="调用留言板 ???",
            lpc_call='call_other("/clone/board/note1_b", "???")',
            target="board",
        ),
    ],
    notes="noteroom 是巫师记录玩家犯罪原因的房间。",
)

_noteroom_init = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="d/death/noteroom.c",
        line_range=(30, 40),
    ),
    preconditions=[
        Precondition(
            description="玩家已进入 noteroom",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="普通玩家被提示并强制移回 /d/death/death.c",
            state_change='if(wizhood(me)=="(player)") { write("这不是你该来的地方"); me->move("/d/death/death.c"); return 0; }',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="noteroom 仅巫师可停留，玩家进入即被驱逐到死刑室",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="普通玩家看到 '这不是你该来的地方'",
            lpc_call='write(HIW "\\n这不是你该来的地方\\n\\n" NOR)',
            target="player",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置玩家 startroom 为 /d/death/death",
            lpc_call='me->set("startroom", "/d/death/death")',
            target="player.startroom",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="强制玩家移到 /d/death/death.c",
            lpc_call='me->move("/d/death/death.c")',
            target="player",
        ),
    ],
    notes="noteroom 是巫师专用房间，玩家误入会被驱逐。",
)

# ---------------------------------------------------------------------------
# 登录相关规格
# ---------------------------------------------------------------------------

_logind_hell_checks = FunctionSpec(
    signature=FunctionSignature(
        name="enter_world_hell_checks",
        params=[
            LPCParam(name="ob", lpc_type="object", description="连接对象"),
            LPCParam(name="user", lpc_type="object", description="玩家 body 对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(642, 662),
    ),
    preconditions=[
        Precondition(
            description="user 是有效玩家 body 对象，登录流程已执行到 enter_world",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="若 user 是 ghost，startroom 强制设为 DEATH_ROOM",
            state_change="if(user->is_ghost()) startroom = DEATH_ROOM",
            kind="effect",
        ),
        Postcondition(
            description="非 ghost 且无有效 startroom 或新手条件时设为侠客岛沙滩",
            state_change='else if(!stringp(startroom) || (!user->query("family") && user->query("combat_exp") < 1)) startroom = "/d/xiakedao/shatan"',
            kind="effect",
        ),
        Postcondition(
            description="未注册或邮箱被封禁的玩家移到 /d/xiakedao/shatan1",
            state_change='if((registered!="yes" || is_banned_email) && wizhood=="(player)") user->move("/d/xiakedao/shatan1")',
            kind="effect",
        ),
        Postcondition(
            description="death_count > 200 且 combat_exp < 50000 的玩家移到 /d/death/block.c",
            state_change='else if(death_count>200 && combat_exp<50000) user->move("/d/death/block.c")',
            kind="effect",
        ),
        Postcondition(
            description="否则尝试移到 startroom，加载失败则回退 START_ROOM",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="ghost 玩家登录必回 DEATH_ROOM，优先级最高",
            lpc_expr="user->is_ghost() => startroom = DEATH_ROOM",
            scope="function",
        ),
        Invariant(
            description="death_count 惩罚检查次于注册检查，优先进入 block.c",
            lpc_expr='death_count>200 && combat_exp<50000 => move("/d/death/block.c")',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="ghost 检查：startroom = DEATH_ROOM",
            lpc_call="if(user->is_ghost()) startroom = DEATH_ROOM",
            target="startroom",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="非 ghost 新手检查：startroom = /d/xiakedao/shatan",
            lpc_call='else if(!stringp(startroom) || (!user->query("family") && user->query("combat_exp")<1)) startroom = "/d/xiakedao/shatan"',
            target="startroom",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="未注册/邮箱被封玩家移到 /d/xiakedao/shatan1",
            lpc_call='if((registered!="yes" || REGI_D->is_banned_email(ob->query("email"))) && wizhood(user)=="(player)") user->move("/d/xiakedao/shatan1")',
            target="player",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="death_count 惩罚：移到 /d/death/block.c",
            lpc_call='else if(user->query("death_count")>200 && user->query("combat_exp")<50000) user->move("/d/death/block.c")',
            target="player",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="尝试 load_object(startroom) 成功后 move",
            lpc_call="if(!catch(load_object(startroom))) user->move(startroom)",
            target="player",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="startroom 加载失败时回退 START_ROOM",
            lpc_call="user->move(START_ROOM); startroom = START_ROOM; user->set('startroom', START_ROOM)",
            target="player",
        ),
    ],
    notes="enter_world 中的地狱相关检查决定玩家登录起始房间。",
)

# ---------------------------------------------------------------------------
# 层 F-DEATH 已覆盖函数（引用）
# ---------------------------------------------------------------------------

_is_ghost = FunctionSpec(
    signature=FunctionSignature(
        name="is_ghost",
        params=[],
        return_type="int",
        lpc_file="feature/damage.c",
        line_range=(11, 11),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 ghost 标志当前值（0=非鬼，1=鬼魂）",
            return_value="int: 0 或 1",
            kind="ensure",
        ),
    ],
    invariants=[],
    side_effects=[],
    notes="已在层 F-DEATH 中通过 die() / reincarnate() 间接覆盖，此处仅引用。",
)

_reincarnate_ref = FunctionSpec(
    signature=FunctionSignature(
        name="reincarnate",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(255, 264),
    ),
    preconditions=[
        Precondition(
            description="对象当前为 ghost 状态",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="ghost=0，qi/jing/eff_qi/eff_jing/jingli/neili 恢复到 max",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="reincarnate 后 is_ghost() 返回 0",
            scope="class",
        ),
    ],
    side_effects=[],
    notes="完整规格见层 F-DEATH（_reincarnate）。此处仅作为阴间流程引用。",
)

# ---------------------------------------------------------------------------
# 层 F-HELL 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="F-HELL",
    layer_name="阴间流程",
    lpc_files=[
        "d/death/gate.c",
        "d/death/gateway.c",
        "d/death/road1.c",
        "d/death/road2.c",
        "d/death/inn1.c",
        "d/death/inn2.c",
        "d/death/npc/wgargoyle.c",
        "d/death/npc/bgargoyle.c",
        "d/death/hell.c",
        "d/death/death.c",
        "d/death/block.c",
        "d/death/blkbot.c",
        "d/death/noteroom.c",
        "adm/daemons/logind.c",
        "feature/damage.c",
        "include/login.h",
    ],
    function_specs=[
        _gate_create,
        _gate_init,
        _gateway_create,
        _gateway_valid_leave,
        _gateway_init,
        _road1_create,
        _road1_init,
        _road2_create,
        _road2_valid_leave,
        _road2_init,
        _inn1_create,
        _inn1_redirect_ask,
        _inn1_do_stuff,
        _inn2_create,
        _wgargoyle_create,
        _wgargoyle_init,
        _wgargoyle_death_stage,
        _bgargoyle_create,
        _bgargoyle_init,
        _bgargoyle_death_stage,
        _hell_init,
        _hell_block_cmd,
        _death_init,
        _death_block_cmd,
        _block_init,
        _block_block_cmd,
        _blkbot_create,
        _blkbot_reset,
        _blkbot_init,
        _blkbot_valid_leave,
        _noteroom_create,
        _noteroom_init,
        _logind_hell_checks,
        _is_ghost,
        _reincarnate_ref,
    ],
    cross_layer_refs=[
        "die() (层 F-DEATH) -- 死亡入口，move 到 DEATH_ROOM",
        "reincarnate() (层 F-DEATH) -- 还阳状态恢复",
        "is_ghost() (层 F-DEATH) -- 鬼魂状态查询",
        "clear_condition() (层 B: F_CONDITION) -- gate.c 与 death_penalty 中清除状态",
        "move() (层 B: F_MOVE) -- 房间间移动",
        "DROP_CMD->do_drop() (层 D: world) -- 无常还阳时掉落物品",
        "add_action() (层 C: command) -- 房间命令拦截注册",
        "command() (层 C: command) -- 黑无常 say",
        "message() / tell_room() / tell_object() (层 B: F_MESSAGE) -- 消息输出",
        "call_out() (层 A: driver) -- 无常还阳定时器",
        "query_verb() (层 A: driver) -- block_cmd 读取当前命令",
        "setup() (层 B: ROOM) -- 房间初始化",
        "REGI_D->is_banned_email() (层 H) -- 登录邮箱封禁检查",
        "wizhood() (层 H: SECURITY_D) -- 巫师等级判断",
        "START_ROOM / DEATH_ROOM / REVIVE_ROOM 宏 (include/login.h)",
    ],
    notes=(
        "层 F-HELL 覆盖 LPC 阴间世界流程与相关登录检查。"
        "核心契约：单向流程（gateway 禁止往南）、5 段迷雾路（road2 需 5 次）、"
        "无常自动还阳（30 秒延迟 + 5 段消息 + reincarnate）、隐藏还阳路径（inn1 ask 自己 about 回家）、"
        "地狱/死刑室命令白名单、登录时 ghost 与 death_count 惩罚检查。"
        "\n\n"
        "重要：feature/damage.c:die() 中调用 DEATH_ROOM->start_death(this_object())，"
        "但 /d/death/gate.c 中并不存在 start_death() 函数，该调用在 LPC 运行时"
        "是幻影调用（phantom call），不触发任何动作；真正的阴间流程由 gate.c 的 init() "
        "剥离物品/清除状态以及加载的白无常 init() 触发。"
        "\n\n"
        "缺失文件：/d/death/noloseroom 在 LPC 源码中不存在（可能为历史遗留或未提交房间），"
        "本层不为其创建规格。"
    ),
)
