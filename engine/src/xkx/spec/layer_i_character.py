"""层 I：角色与登录 -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``inherit/char/char.c`` -- CHARACTER 基类：create / setup / heart_beat 骨架 / visible
- ``clone/user/user.c`` -- USER 对象：save / setup / update_age / restore_autoload /
  net_dead / reconnect / user_dump / reset / terminal_type
- ``clone/user/login.c`` -- LOGIN 对象：logon / time_out / net_dead / receive_message

核心契约要点：
1. **char.c create()**：seteuid(0) 让 LOGIN_D 可以 export uid 到此对象，
   是 LPC 安全模型中 "空 euid 等待赋权" 的模式。
2. **char.c setup()**：对象从 create 阶段进入运行阶段的转换点。
   set_heart_beat(1) + tick 初始化 + enable_player + CHAR_D->setup_char。
   层 G 已提取 setup 的 NPC 路径，本层补充玩家路径（user.c setup 覆盖）。
3. **char.c heart_beat() 骨架**：玩家 vs NPC 分支入口。七步细节属层 G（已提取），
   本层提取 "谁调用什么" 的骨架入口和玩家专属分支（频道清理 / update_age / idle 超时）。
4. **char.c visible()**：隐身/可见性判定。viewer 看 target 是否可见。
   巫师等级 > 目标等级则可见；invisibility 属性 > 查看者等级则不可见；
   鬼魂需 is_ghost() 或 astral_vision 才可见。PronounContext 必须携带 viewer
   （CLAUDE.md 架构不变量，rankd.c 实证 this_player() 依赖）。
5. **user.c save()**：玩家数据存档。save_autoload + ::save（F_SAVE 层 B）+ clean_up_autoload。
   JSON 存档崩溃安全是新引擎要求（write-temp+os.replace 原子写），LPC save_object
   全量覆盖无原子写是前车之鉴（CLAUDE.md 架构不变量）。
6. **user.c update_age()**：游戏时间 -> 玩家年龄。真实 1 秒 = 游戏 1 分钟（86400 秒 = 1 天）。
   age <= 24 时每 86400 秒（10 天）长 1 岁；age > 24 时每 259200 秒（30 天）长 1 岁。
   month 按 7200 秒（2 小时）为一个月份单位。
7. **user.c restore_autoload()**：恢复自动加载物品。接口契约，完整实现后置。
8. **user.c net_dead() / reconnect()**：断线 / 重连处理。
   断线关闭心跳 + 清除 link_ob + 安排 user_dump 定时器。
   重连恢复心跳 + 清除 netdead 标记 + 取消 user_dump 定时器。
9. **login.c**：LOGIN 对象是登录流程的连接载体。logon() 委托 LOGIN_D 状态机（层 H）。
   LOGIN_D 的完整状态机属层 H，login.c 仅提取委托接口。

不做（边界）：
- F_ATTACK / F_DAMAGE / F_SKILL / F_ATTRIBUTE / F_EQUIP 完整规格（层 E/G 已覆盖战斗相关，其余后置）
- F_AUTOLOAD 完整实现（后置，只提取 restore_autoload 接口契约）
- F_FINANCE / F_MARRY / F_TEAM 社交特性（后置）
- heart_beat 七步细节（属层 G，你提取骨架入口）
- LOGIN_D 状态机（属层 H，login.c 委托引用）
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
    RandomSpec,
    SideEffect,
    SideEffectType,
)

# ---------------------------------------------------------------------------
# 层 I 特定模型
# ---------------------------------------------------------------------------


class CharacterLifecycle(StrEnum):
    """角色对象生命周期阶段。"""

    CREATE = "create"
    """对象创建：seteuid(0)，等待 LOGIN_D 赋权。"""

    SETUP = "setup"
    """角色设置：set_heart_beat(1) + enable_player + CHAR_D->setup_char。"""

    ACTIVE = "active"
    """运行中：heart_beat 每 1s 执行，可接受命令。"""

    NET_DEAD = "net_dead"
    """断线：心跳关闭，等待 user_dump 超时或重连。"""

    RECONNECT = "reconnect"
    """重连：恢复心跳，清除 netdead 标记。"""


# ---------------------------------------------------------------------------
# char.c 函数规格
# ---------------------------------------------------------------------------

_char_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="inherit/char/char.c",
        line_range=(39, 42),
    ),
    preconditions=[
        Precondition(
            description="对象刚被创建，尚未赋权",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="seteuid(0) 设置为空 euid，使 LOGIN_D 可以 export uid 到此对象",
            state_change="seteuid(0)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="create 后 euid 为 0（空），等待 setup() 时由 seteuid(getuid()) 赋权",
            lpc_expr="geteuid(this_object()) == 0 after create()",
            scope="function",
        ),
        Invariant(
            description="create 不设置任何角色属性（属性在 setup/CHAR_D->setup_char 中初始化）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="seteuid(0) 设置空 euid，让 LOGIN_D 可以 export uid",
            lpc_call="seteuid(0)",
            target="this_object.euid",
        ),
    ],
    notes=(
        "create() 只做一件事：seteuid(0)。这是 LPC 安全模型中 '空 euid 等待赋权' 的模式。"
        "LOGIN_D 在连接流程中通过 export_uid 将玩家 uid 赋给 body 对象，"
        "之后 setup() 再 seteuid(getuid()) 完成赋权闭环。"
        "is_character() 是 apply 函数，返回 1 标识此对象为角色类型。"
    ),
)


_char_setup = FunctionSpec(
    signature=FunctionSignature(
        name="setup",
        params=[],
        return_type="void",
        lpc_file="inherit/char/char.c",
        line_range=(49, 58),
    ),
    preconditions=[
        Precondition(
            description="对象已通过 create() 初始化（seteuid(0) 已设置）",
            kind="require",
        ),
        Precondition(
            description="对象已有有效 uid（LOGIN_D 已 export_uid）",
            lpc_expr="getuid(this_object()) != 0",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="seteuid 设为对象自身 uid，完成赋权闭环",
            state_change="seteuid(getuid(this_object()))",
            kind="effect",
        ),
        Postcondition(
            description="heart_beat 已启用（set_heart_beat(1)），每 1s 执行一次",
            state_change="set_heart_beat(1)",
            kind="effect",
        ),
        Postcondition(
            description="tick 初始化为 5+random(10) 的非均匀周期",
            state_change="tick = 5 + random(10)",
            kind="effect",
        ),
        Postcondition(
            description="命令系统已启用（enable_player）",
            state_change="enable_player()",
            kind="effect",
        ),
        Postcondition(
            description="CHAR_D->setup_char 已调用（属性计算）",
            state_change="CHAR_D->setup_char(this_object())",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="setup 是对象从 create 阶段进入运行阶段的转换点",
            scope="class",
        ),
        Invariant(
            description="set_heart_beat(1) 确保心跳每 1s 执行一次（CLAUDE.md 架构不变量）",
            lpc_expr="set_heart_beat(1)",
            scope="system",
        ),
        Invariant(
            description="setup 后 geteuid() == getuid()（赋权闭环完成）",
            lpc_expr="geteuid(this_object()) == getuid(this_object())",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="seteuid(getuid()) 完成赋权闭环",
            lpc_call="seteuid(getuid(this_object()))",
            target="this_object.euid",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="启用心跳（每 1s 执行）",
            lpc_call="set_heart_beat(1)",
            target="this_object.heart_beat",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="初始化 tick 非均匀周期",
            lpc_call="tick = 5 + random(10)",
            target="this_object.tick",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="启用命令系统（注册 command_hook 等）",
            lpc_call="enable_player()",
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="调用 CHAR_D 计算角色属性",
            lpc_call="CHAR_D->setup_char(this_object())",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="tick = 5 + random(10)",
            probability_model="tick 初始值 = 5 + random(10)，范围 [5, 14]",
            semantic="初始化非均匀 tick 衰减周期",
            seed_inputs=["无外部 seed"],
            determinism_note="tick 随机性属角色生命周期，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "setup 是角色对象生命周期的关键转换点：create（空 euid）-> setup（赋权 + 心跳 + 命令系统）。"
        "层 G 已提取 setup 的 NPC 路径规格，本规格是 CHARACTER 基类版本，"
        "user.c 的 setup() 覆盖此函数，额外调用 update_age() 和 restore_autoload()。"
    ),
)


_heart_beat_skeleton = FunctionSpec(
    signature=FunctionSignature(
        name="heart_beat",
        params=[],
        return_type="void",
        lpc_file="inherit/char/char.c",
        line_range=(60, 169),
    ),
    preconditions=[
        Precondition(
            description="对象已通过 setup() 初始化（set_heart_beat(1) 已调用）",
            lpc_expr="setup() 已执行",
            kind="require",
        ),
        Precondition(
            description="heart_beat 已被驱动启用（set_heart_beat(1)），未关闭",
            lpc_expr="heart_beat == 1",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="每 tick 执行一次七步管线，副作用按步骤顺序产生",
            kind="ensure",
        ),
        Postcondition(
            description="玩家分支（userp）：频道清理 -> 频道刷屏检测 -> 属性封顶 -> "
            "濒死/昏迷检查 -> 战斗 -> tick 衰减 -> update_age -> idle 超时",
            kind="observable",
        ),
        Postcondition(
            description="NPC 分支（!userp）：属性封顶 -> 濒死/昏迷检查 -> 战斗 -> chat -> "
            "tick 衰减 -> 空闲心跳关闭",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="tick=1s + compute<100ms：heart_beat 每 1s 执行一次",
            lpc_expr="set_heart_beat(1)",
            scope="system",
        ),
        Invariant(
            description="玩家 vs NPC 分支：userp 分支执行频道清理和 update_age/idle 超时；"
            "!userp 分支执行 chat() 和空闲心跳关闭",
            lpc_expr="if(userp(this_object())) { 频道清理; ... update_age(); idle 检查 } "
            "else { chat(); ... 空闲心跳关闭 }",
            scope="function",
        ),
        Invariant(
            description="七步细节属层 G（已提取），本规格仅提取骨架入口和玩家专属分支",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 1（仅 userp）：clear_cmd_count 重置命令计数",
            lpc_call="clear_cmd_count()",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="步骤 1（仅 userp）：channel_msg_cnt>10 时关闭频道 + 输出谣言消息",
            lpc_call='CHANNEL_D->do_channel(rum_ob, "rumor", ...); set("chblk_on", 1)',
            target="channel",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 1（仅 userp）：set_temp('channel_msg_cnt', 0) 重置频道消息计数",
            lpc_call='set_temp("channel_msg_cnt", 0)',
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 2：neili/jingli/jing 超过 max*2 时封顶（通用）",
            lpc_call='my["neili"] = my["max_neili"]*2 (etc.)',
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="步骤 3-5：濒死/昏迷检查 + 战斗行动（属层 F/G，此处仅引用）",
            lpc_call="die()/unconcious()/attack()/continue_action()",
            target="this_object",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="步骤 6（仅 !userp）：chat()（属层 G，此处仅引用）",
            lpc_call="this_object()->chat()",
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 7：tick-- 衰减，未到 0 则 return",
            lpc_call="if(tick--) return; else tick = 5 + random(10)",
            target="this_object.tick",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（tick 到 0 时）：update_condition + heal_up（属层 E/F）",
            lpc_call="update_condition(); heal_up()",
            target="this_object",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 7：完全和平时 set_heart_beat(0) 关闭心跳（仅 !interactive）",
            lpc_call="set_heart_beat(0)",
            target="this_object.heart_beat",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（仅 interactive）：update_age() 更新玩家年龄",
            lpc_call="this_object()->update_age()",
            target="this_object",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（仅 interactive）：query_idle > IDLE_TIMEOUT 时 user_dump(DUMP_IDLE)",
            lpc_call="this_object()->user_dump(DUMP_IDLE)",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="tick = 5 + random(10)",
            probability_model="tick 周期 = 5 + random(10)，范围 [5, 14]，均匀分布",
            semantic="非均匀 tick 衰减周期：控制 update_condition/heal_up 频率，节省 CPU",
            seed_inputs=["无外部 seed，使用系统 RNG"],
            determinism_note="tick 周期随机性属角色生命周期，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "heart_beat 骨架入口：char.c heart_beat 是玩家和 NPC 的共用入口。"
        "七步管线细节属层 G（已提取），本规格仅提取骨架入口和玩家专属分支：\n"
        "  - 玩家分支（userp）：频道清理 + 刷屏检测（步骤 1）+ update_age + idle 超时（步骤 7）\n"
        "  - NPC 分支（!userp）：chat()（步骤 6）+ 空闲心跳关闭（步骤 7）\n"
        "  - 通用步骤 2-5：属性封顶 -> 濒死/昏迷 -> 战斗（层 F/G 已提取）\n"
        "  - 通用步骤 7：tick 衰减 -> update_condition + heal_up（层 E/F 已提取）\n"
        "CLAUDE.md 架构不变量：tick=1s + compute<100ms + 非均匀 tick。"
    ),
)


_visible = FunctionSpec(
    signature=FunctionSignature(
        name="visible",
        params=[
            LPCParam(name="ob", lpc_type="object", description="被查看的目标对象"),
        ],
        return_type="int",
        lpc_file="inherit/char/char.c",
        line_range=(171, 187),
    ),
    preconditions=[
        Precondition(
            description="this_object() 是有效的角色对象（查看者 viewer）",
            lpc_expr="this_object() && is_character()",
            kind="require",
        ),
        Precondition(
            description="ob 是有效的对象（被查看的目标 target）",
            lpc_expr="objectp(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示 viewer 可以看到 target",
            return_value="1=可见",
            kind="ensure",
        ),
        Postcondition(
            description="返回 0 表示 viewer 看不到 target（隐身/鬼魂/等级不足）",
            return_value="0=不可见",
            kind="ensure",
        ),
        Postcondition(
            description="viewer 巫师等级 > target 巫师等级 - userp(target) 时直接可见",
            state_change="if(wiz_level(me) > wiz_level(ob) - userp(ob)) return 1",
            kind="effect",
        ),
        Postcondition(
            description="target 的 invisibility 属性 > viewer 巫师等级时不可见",
            state_change="if(invis > wiz_level(me)) return 0",
            kind="effect",
        ),
        Postcondition(
            description="target 是鬼魂时：viewer 也是鬼魂或 has astral_vision 则可见，否则不可见",
            state_change="if(ob->is_ghost()) { if(is_ghost()||astral_vision) return 1; else return 0; }",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="visible 的 viewer/target 语义：this_object()=viewer，ob=target。"
            "PronounContext 必须携带 viewer（CLAUDE.md 架构不变量，rankd.c 实证 this_player() 依赖）",
            lpc_expr="visible(me, ob) where me=this_object()=viewer, ob=target",
            scope="system",
        ),
        Invariant(
            description="巫师等级判定：wiz_level(me) > wiz_level(ob) - userp(ob) 时可见。"
            "userp(ob) 使玩家比同等级 NPC 低 1 级（玩家更容易被看到）",
            lpc_expr="wiz_level(this_object()) > wiz_level(ob) - userp(ob)",
            scope="function",
        ),
        Invariant(
            description="invisibility 属性判定：invis > wiz_level(viewer) 时不可见。"
            "invisibility 来自 env/invisibility 属性（巫师隐身）",
            lpc_expr='invis = ob->query("env/invisibility"); invis > wiz_level(me) => return 0',
            scope="function",
        ),
        Invariant(
            description="鬼魂可见性：is_ghost() target 需 viewer 也 is_ghost() 或 has astral_vision",
            lpc_expr="ob->is_ghost() => (is_ghost() || query_temp('apply/astral_vision')) ? visible : invisible",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="计算 viewer 巫师等级 lvl = wiz_level(this_object())",
            lpc_call="lvl = wiz_level(this_object())",
            target="viewer",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="巫师等级判定：lvl > wiz_level(ob) - userp(ob) 时返回 1（可见）",
            lpc_call="if(lvl > wiz_level(ob) - userp(ob)) return 1",
            target="viewer",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="invisibility 判定：ob 的 env/invisibility > lvl 时返回 0（不可见）",
            lpc_call='invis = (int)ob->query("env/invisibility"); if(invis > lvl) return 0',
            target="target",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="鬼魂判定：ob->is_ghost() 时，viewer is_ghost() 或 astral_vision 则可见，否则不可见",
            lpc_call='if(ob->is_ghost()) { if(is_ghost()||query_temp("apply/astral_vision")) return 1; else return 0; }',
            target="target",
        ),
    ],
    notes=(
        "visible 是隐身/可见性判定的核心函数。viewer=this_object()，target=ob。\n"
        "判定优先级：(1) 巫师等级 > (2) invisibility 属性 > (3) 鬼魂状态。\n"
        "CLAUDE.md 架构不变量：PronounContext 必须携带 viewer（三元组 speaker/viewer/target）。"
        "visible 的 viewer/target 语义直接对应 PronounContext 的 viewer/target。\n"
        "userp(ob) 使玩家比同等级 NPC 低 1 级：wiz_level(ob) - userp(ob)，"
        "这意味着同等级的玩家比 NPC 更容易被看到（玩家不能像 NPC 一样隐藏等级）。"
    ),
)


# ---------------------------------------------------------------------------
# user.c 函数规格
# ---------------------------------------------------------------------------

_user_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(14, 18),
    ),
    preconditions=[
        Precondition(
            description="USER 对象刚被创建",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="调用父类 create()（CHARACTER::create -> seteuid(0)）",
            state_change="::create()",
            kind="effect",
        ),
        Postcondition(
            description="设置对象名称为 '使用者物件'（{ 'user object', 'user', 'object' }）",
            state_change='set_name("使用者物件", ({"user object", "user", "object"}))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="USER 对象继承 CHARACTER + F_AUTOLOAD + F_SAVE",
            lpc_expr="inherit CHARACTER; inherit F_AUTOLOAD; inherit F_SAVE",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="调用父类 create()（seteuid(0)）",
            lpc_call="::create()",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置对象名称",
            lpc_call='set_name("使用者物件", ({"user object", "user", "object"}))',
            target="this_object",
        ),
    ],
    notes="USER 对象的 create 调用父类 create 后设置默认名称，是 player body 对象的创建入口。",
)


_user_save = FunctionSpec(
    signature=FunctionSignature(
        name="save",
        params=[],
        return_type="int",
        lpc_file="clone/user/user.c",
        line_range=(52, 60),
    ),
    preconditions=[
        Precondition(
            description="对象必须实现 query_save_file() 且返回有效文件路径（继承自 F_SAVE）",
            lpc_expr="query_save_file() returns valid path",
            kind="require",
        ),
        Precondition(
            description="对象已有有效 uid（query_save_file 依赖 id/geteuid/getuid）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 save_object 的结果（1=成功, 0=失败）",
            return_value="int（1=成功, 0=失败）",
            kind="ensure",
        ),
        Postcondition(
            description="save_autoload() 已调用（保存自动加载物品列表）",
            state_change="save_autoload()",
            kind="effect",
        ),
        Postcondition(
            description="::save() 已调用（F_SAVE 层 B 的 save_object 执行实际持久化）",
            state_change="::save()",
            kind="effect",
        ),
        Postcondition(
            description="clean_up_autoload() 已调用（清理自动加载物品，释放内存）",
            state_change="clean_up_autoload()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="JSON 存档崩溃安全：新引擎要求 write-temp+os.replace 原子写。"
            "LPC save_object 全量覆盖无原子写是前车之鉴（CLAUDE.md 架构不变量）",
            lpc_expr="new_engine: write_temp + os.replace (atomic write)",
            scope="system",
        ),
        Invariant(
            description="存档路径由 query_save_file() 决定：DATA_DIR/user/<首字母>/<id>",
            lpc_expr='query_save_file() => DATA_DIR "user/%c/%s", id[0], id',
            scope="function",
        ),
        Invariant(
            description="save_autoload 在 ::save 之前执行（先保存物品列表，再保存角色数据）",
            lpc_expr="order(save_autoload) < order(::save)",
            scope="function",
        ),
        Invariant(
            description="clean_up_autoload 在 ::save 之后执行（存档完成后释放内存）",
            lpc_expr="order(::save) < order(clean_up_autoload)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="save_autoload() 保存自动加载物品列表到 dbase",
            lpc_call="save_autoload()",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="::save() 调用 F_SAVE 的 save_object 持久化角色数据到文件",
            lpc_call="::save()",
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="clean_up_autoload() 清理自动加载物品对象，释放内存",
            lpc_call="clean_up_autoload()",
            target="this_object",
        ),
    ],
    notes=(
        "user.c save() 是玩家级存档入口，三步交织：save_autoload -> ::save -> clean_up_autoload。\n"
        "save_autoload 在 ::save 之前执行，将自动加载物品信息写入 dbase（随 save_object 一起存档）。\n"
        "clean_up_autoload 在 ::save 之后执行，清理 autoload 物品对象以节省内存（存档已完成，物品可释放）。\n"
        "CLAUDE.md 架构不变量：JSON 存档崩溃安全。新引擎必须使用 write-temp+os.replace 原子写，"
        "不得重蹈 LPC save_object 全量覆盖无原子写的覆辙。"
        "存档路径：DATA_DIR/user/<首字母>/<id>，如 /data/user/a/alice。"
    ),
)


_user_setup = FunctionSpec(
    signature=FunctionSignature(
        name="setup",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(77, 85),
    ),
    preconditions=[
        Precondition(
            description="对象已通过 create() 初始化",
            kind="require",
        ),
        Precondition(
            description="对象已有有效 uid（LOGIN_D 已 export_uid）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="update_age() 已调用（先更新年龄，防止新玩家被随机年龄覆盖）",
            state_change="update_age()",
            kind="effect",
        ),
        Postcondition(
            description="::setup() 已调用（CHARACTER 基类 setup：seteuid + set_heart_beat + enable_player + CHAR_D->setup_char）",
            state_change="::setup()",
            kind="effect",
        ),
        Postcondition(
            description="restore_autoload() 已调用（恢复自动加载物品）",
            state_change="restore_autoload()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="update_age 在 ::setup 之前调用：先设置年龄，防止新玩家被随机年龄覆盖",
            lpc_expr="order(update_age) < order(::setup)",
            scope="function",
        ),
        Invariant(
            description="restore_autoload 在 ::setup 之后调用：先完成角色初始化，再恢复物品",
            lpc_expr="order(::setup) < order(restore_autoload)",
            scope="function",
        ),
        Invariant(
            description="user.c setup 覆盖 CHARACTER::setup，三步交织：update_age -> ::setup -> restore_autoload",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="update_age() 更新玩家年龄（先于 setup，防止随机年龄覆盖）",
            lpc_call="update_age()",
            target="this_object.age",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="::setup() 调用 CHARACTER 基类 setup（seteuid + set_heart_beat(1) + enable_player + CHAR_D->setup_char）",
            lpc_call="::setup()",
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="restore_autoload() 恢复自动加载物品（克隆并 move 到玩家 inventory）",
            lpc_call="restore_autoload()",
            target="this_object.inventory",
        ),
    ],
    notes=(
        "user.c setup() 覆盖 CHARACTER::setup，是玩家进入游戏的设置入口。"
        "三步交织顺序是关键不变量：\n"
        "  (1) update_age() 先执行 -- 注释说 'We want set age first before new player "
        "got initialized with random age'，防止 CHAR_D->setup_char 为新玩家生成随机年龄覆盖真实年龄\n"
        "  (2) ::setup() -- CHARACTER 基类初始化（赋权 + 心跳 + 命令系统 + 属性计算）\n"
        "  (3) restore_autoload() -- 恢复自动加载物品（后置，此处仅提取接口契约）"
    ),
)


_user_update_age = FunctionSpec(
    signature=FunctionSignature(
        name="update_age",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(63, 75),
    ),
    preconditions=[
        Precondition(
            description="对象是 USER（player body），update_age 仅在 user.c 中定义",
            lpc_expr="userp(this_object())",
            kind="require",
        ),
        Precondition(
            description="对象的 dbase 已初始化（mud_age / age_modify 等属性可 query）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="mud_age 累加自上次调用以来的真实时间差（time - last_age_set）",
            state_change='add("mud_age", time() - last_age_set)',
            kind="effect",
        ),
        Postcondition(
            description="last_age_set 更新为当前 time()",
            state_change="last_age_set = time()",
            kind="effect",
        ),
        Postcondition(
            description="age <= 24 时：age = 14 + age_modify + mud_age/86400（每 10 天长 1 岁）",
            state_change='set("age", 14 + age_modify + mud_age/86400)',
            kind="effect",
        ),
        Postcondition(
            description="age > 24 时：age = 24 + age_modify + (mud_age-864000)/259200（每 30 天长 1 岁）",
            state_change='set("age", 24 + age_modify + (mud_age-864000)/259200)',
            kind="effect",
        ),
        Postcondition(
            description="month 更新：age<=24 时 month = (mud_age-(age-14)*86400)/7200 + 1",
            state_change='set("month", (mud_age-(age-14)*86400)/7200 + 1)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="游戏时间映射：真实 1 秒 = 游戏 1 分钟。86400 秒（1 天真实时间）= 游戏 1 天 = 长 1 岁（age<=24）",
            lpc_expr="86400 real_seconds = 1 game_day = 1 year (age<=24)",
            scope="system",
        ),
        Invariant(
            description="last_age_set 记录上次调用时间，update_age 不需要每 tick 调用（增量计算）",
            lpc_expr="mud_age += time() - last_age_set; last_age_set = time()",
            scope="function",
        ),
        Invariant(
            description="初始年龄 14 岁：age = 14 + age_modify + mud_age/86400",
            lpc_expr="age_base = 14",
            scope="function",
        ),
        Invariant(
            description="24 岁后衰老减速：864000 秒（10 天真实）= 24 岁阈值，之后每 259200 秒（3 天真实）长 1 岁",
            lpc_expr="if(mud_age <= 864000) age = 14 + ... ; else age = 24 + (mud_age-864000)/259200 + ...",
            scope="function",
        ),
        Invariant(
            description="关联层 H NATURE_D：真实 1 秒 = 游戏 1 分钟的时间系统由 NATURE_D 维护",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="首次调用时 last_age_set = time()（初始化）",
            lpc_call="if(!last_age_set) last_age_set = time()",
            target="this_object.last_age_set",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="mud_age 累加时间差：add('mud_age', time() - last_age_set)",
            lpc_call='add("mud_age", time() - last_age_set)',
            target="this_object.mud_age",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="last_age_set 更新为当前时间",
            lpc_call="last_age_set = time()",
            target="this_object.last_age_set",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="age<=24 时：set('age', 14 + age_modify + mud_age/86400)",
            lpc_call='set("age", 14 + query("age_modify") + query("mud_age")/86400)',
            target="this_object.age",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="age<=24 时：set('month', ...)",
            lpc_call='set("month", (mud_age-(age-14)*86400)/7200 + 1)',
            target="this_object.month",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="age>24 时：set('age', 24 + age_modify + (mud_age-864000)/259200)",
            lpc_call='set("age", 24 + query("age_modify") + (query("mud_age")-864000)/259200)',
            target="this_object.age",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="age>24 时：set('month', ...)",
            lpc_call='set("month", ((mud_age-864000)-(age-24)*259200)/21600)',
            target="this_object.month",
        ),
    ],
    notes=(
        "update_age 将真实时间映射为游戏年龄。核心映射：真实 1 秒 = 游戏 1 分钟。\n"
        "86400 秒（真实 1 天）= 86400 游戏分钟 = 游戏 60 天。"
        "但 age 公式中 mud_age/86400 意味着 86400 秒真实时间 = 1 岁。\n"
        "age <= 24 时：初始 14 岁，每 86400 秒（约 1 天真实时间）长 1 岁。\n"
        "age > 24 时：每 259200 秒（约 3 天真实时间）长 1 岁（衰老减速）。\n"
        "last_age_set 是增量时间戳，update_age 不需要每 tick 调用，"
        "heart_beat 中注释明确说 'no need to be called every heart_beat'。"
        "关联层 H NATURE_D 的时间系统（真实 1 秒 = 游戏 1 分钟）。"
    ),
)


_user_restore_autoload = FunctionSpec(
    signature=FunctionSignature(
        name="restore_autoload",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(77, 85),
    ),
    preconditions=[
        Precondition(
            description="对象是 USER（player body），已通过 setup() 完成角色初始化",
            lpc_expr="setup() 已执行",
            kind="require",
        ),
        Precondition(
            description="存档中有 autoload 物品列表（save_autoload 保存的数据）",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="自动加载物品已克隆并 move 到玩家 inventory",
            state_change="autoload items cloned and moved to this_object()",
            kind="effect",
        ),
        Postcondition(
            description="无 autoload 数据时无副作用（不克隆任何物品）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="restore_autoload 在 ::setup 之后调用（先完成角色初始化，再恢复物品）",
            lpc_expr="order(::setup) < order(restore_autoload)",
            scope="function",
        ),
        Invariant(
            description="F_AUTOLOAD 的完整实现后置，此处仅提取接口契约",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="克隆自动加载物品并 move 到玩家 inventory",
            lpc_call="restore_autoload() (F_AUTOLOAD)",
            target="this_object.inventory",
        ),
    ],
    notes=(
        "restore_autoload 是 F_AUTOLOAD 的接口契约，完整实现后置。"
        "它在 user.c setup() 的第三步执行（update_age -> ::setup -> restore_autoload）。"
        "save_autoload 在 user.c save() 中调用，将自动加载物品列表保存到 dbase。"
        "restore_autoload 在 setup 时恢复这些物品。"
    ),
)


_user_net_dead = FunctionSpec(
    signature=FunctionSignature(
        name="net_dead",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(121, 141),
    ),
    preconditions=[
        Precondition(
            description="玩家失去网络连接（driver 检测到断线）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="heart_beat 已关闭（set_heart_beat(0)）",
            state_change="set_heart_beat(0)",
            kind="effect",
        ),
        Postcondition(
            description="link_ob 已销毁（destruct(link_ob)）",
            state_change="destruct(link_ob)",
            kind="effect",
        ),
        Postcondition(
            description="所有敌人已清除（remove_all_enemy()）",
            state_change="remove_all_enemy()",
            kind="effect",
        ),
        Postcondition(
            description="netdead 标记已设置（set_temp('netdead', 1)）",
            state_change='set_temp("netdead", 1)',
            kind="effect",
        ),
        Postcondition(
            description="玩家：安排 user_dump(DUMP_NET_DEAD) 定时器（NET_DEAD_TIMEOUT 后自动退出）",
            state_change='call_out("user_dump", NET_DEAD_TIMEOUT, DUMP_NET_DEAD)',
            kind="effect",
        ),
        Postcondition(
            description="玩家：向房间输出断线消息 + CHANNEL_D 系统频道消息",
            state_change='tell_room(env, name+"断线了。\\n", this_object()); CHANNEL_D->do_channel(sys, "断线了。")',
            kind="effect",
        ),
        Postcondition(
            description="NPC：set_temp('quit/forced', 1) + command('quit')（NPC 断线直接退出）",
            state_change='set_temp("quit/forced", 1); command("quit")',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="net_dead 后 heart_beat 关闭，不再执行 tick 逻辑",
            lpc_expr="set_heart_beat(0)",
            scope="function",
        ),
        Invariant(
            description="玩家断线后保留对象（等待重连），NPC 断线直接退出",
            lpc_expr="userp => keep + call_out user_dump; !userp => command('quit')",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="set_heart_beat(0) 关闭心跳",
            lpc_call="set_heart_beat(0)",
            target="this_object.heart_beat",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="若 link_ob 存在则 destruct(link_ob)（断开连接对象）",
            lpc_call="destruct(link_ob)",
            target="link_ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="remove_all_enemy() 清除所有敌人（停止战斗）",
            lpc_call="remove_all_enemy()",
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="set_temp('netdead', 1) 标记断线状态",
            lpc_call='set_temp("netdead", 1)',
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.CALL_OUT,
            description="玩家：call_out('user_dump', NET_DEAD_TIMEOUT, DUMP_NET_DEAD) 安排超时退出",
            lpc_call='call_out("user_dump", NET_DEAD_TIMEOUT, DUMP_NET_DEAD)',
            target="call_out_queue",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="玩家：tell_room 输出断线消息（不含自身）",
            lpc_call='tell_room(environment(), query("name") + "断线了。\\n", this_object())',
            target="room",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="玩家：CHANNEL_D->do_channel 系统频道消息",
            lpc_call='CHANNEL_D->do_channel(this_object(), "sys", "断线了。")',
            target="channel",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="NPC：set_temp('quit/forced', 1) + command('quit')（直接退出）",
            lpc_call='set_temp("quit/forced", 1); command("quit")',
            target="this_object",
        ),
    ],
    notes=(
        "net_dead 由 driver 在玩家失去网络连接时调用。"
        "玩家断线后保留对象等待重连（reconnect），NPC 断线直接退出。"
        "NET_DEAD_TIMEOUT 后 user_dump(DUMP_NET_DEAD) 自动退出断线玩家。"
    ),
)


_user_reconnect = FunctionSpec(
    signature=FunctionSignature(
        name="reconnect",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(144, 150),
    ),
    preconditions=[
        Precondition(
            description="玩家处于 net_dead 状态（query_temp('netdead') == 1）",
            lpc_expr='query_temp("netdead") == 1',
            kind="require",
        ),
        Precondition(
            description="LOGIN_D 检测到同名玩家重连，调用 reconnect",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="heart_beat 已恢复（set_heart_beat(1)）",
            state_change="set_heart_beat(1)",
            kind="effect",
        ),
        Postcondition(
            description="netdead 标记已清除（set_temp('netdead', 0)）",
            state_change='set_temp("netdead", 0)',
            kind="effect",
        ),
        Postcondition(
            description="user_dump 定时器已取消（remove_call_out('user_dump')）",
            state_change="remove_call_out('user_dump')",
            kind="effect",
        ),
        Postcondition(
            description="向玩家输出 '重新连线完毕。' 消息",
            state_change='tell_object(this_object(), "重新连线完毕。\\n")',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="reconnect 是 net_dead 的逆操作：恢复心跳 + 清除 netdead + 取消定时器",
            scope="function",
        ),
        Invariant(
            description="reconnect 后 heart_beat 重新启用（set_heart_beat(1)）",
            lpc_expr="set_heart_beat(1) after reconnect()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="set_heart_beat(1) 恢复心跳",
            lpc_call="set_heart_beat(1)",
            target="this_object.heart_beat",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="set_temp('netdead', 0) 清除断线标记",
            lpc_call='set_temp("netdead", 0)',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.CALL_OUT,
            description="remove_call_out('user_dump') 取消超时退出定时器",
            lpc_call='remove_call_out("user_dump")',
            target="call_out_queue",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_object 输出 '重新连线完毕。'",
            lpc_call='tell_object(this_object(), "重新连线完毕。\\n")',
            target="this_object",
        ),
    ],
    notes="reconnect 由 LOGIN_D 在 netdead 玩家重连时调用，是 net_dead 的逆操作。",
)


_user_dump = FunctionSpec(
    signature=FunctionSignature(
        name="user_dump",
        params=[
            LPCParam(name="type", lpc_type="int", description="dump 类型：DUMP_NET_DEAD 或 DUMP_IDLE"),
        ],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(87, 117),
    ),
    preconditions=[
        Precondition(
            description="type 是 DUMP_NET_DEAD 或 DUMP_IDLE 之一",
            lpc_expr="type in (DUMP_NET_DEAD, DUMP_IDLE)",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="DUMP_NET_DEAD：向房间输出断线超时消息 + command('quit')",
            state_change='tell_room(env, name+"断线超过 N 分钟，自动退出。"); command("quit")',
            kind="effect",
        ),
        Postcondition(
            description="DUMP_IDLE：非巫师玩家向自身和房间输出 idle 超时消息 + command('quit')",
            state_change='tell_object + tell_room + command("quit")',
            kind="effect",
        ),
        Postcondition(
            description="DUMP_IDLE 时巫师（admin/arch/wizard）不退出（有特权）",
            state_change='if(wiz_type in ("(admin)","(arch)","(wizard)")) return (idle 不踢)',
            kind="guard",
        ),
        Postcondition(
            description="强制退出前 set_temp('quit/forced', 1) 标记",
            state_change='set_temp("quit/forced", 1)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="DUMP_IDLE 时巫师有 idle 豁免权（Rank Has Its Privileges）",
            lpc_expr='wizhood not in ("(admin)", "(arch)", "(wizard)") => kick on idle',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="DUMP_NET_DEAD：tell_room 输出断线超时退出消息",
            lpc_call='tell_room(environment(), query("name") + "断线超过 " + NET_DEAD_TIMEOUT/60 + " 分钟，自动退出。\\n")',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="DUMP_NET_DEAD：set_temp('quit/forced', 1) 标记强制退出",
            lpc_call='set_temp("quit/forced", 1)',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="DUMP_NET_DEAD：command('quit') 执行退出",
            lpc_call='command("quit")',
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="DUMP_IDLE：tell_object 向玩家输出 idle 超时消息",
            lpc_call='tell_object(this_object(), "对不起，您已经发呆超过 " + IDLE_TIMEOUT/60 + " 分钟了...")',
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="DUMP_IDLE：tell_room 输出 idle 超时消失消息（飞灰效果）",
            lpc_call='tell_room(environment(), "一阵风吹来，将发呆中的" + query("name") + "化为一堆飞灰，消失了。\\n", ({this_object()}))',
            target="room",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="DUMP_IDLE：set_temp('quit/forced', 1) 标记强制退出",
            lpc_call='set_temp("quit/forced", 1)',
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="DUMP_IDLE：command('quit') 执行退出",
            lpc_call='command("quit")',
            target="this_object",
        ),
    ],
    notes=(
        "user_dump 由 call_out 触发（net_dead 时 DUMP_NET_DEAD，heart_beat idle 时 DUMP_IDLE）。"
        "DUMP_IDLE 时巫师有 idle 豁免权（admin/arch/wizard 不被踢）。"
        "源码中有注释掉的 'Rank Has Its Privileges' 消息，说明设计意图是巫师有特权。"
    ),
)


_user_reset = FunctionSpec(
    signature=FunctionSignature(
        name="reset",
        params=[],
        return_type="void",
        lpc_file="clone/user/user.c",
        line_range=(26, 38),
    ),
    preconditions=[
        Precondition(
            description="对象是 USER（player body），dbase 已初始化",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="potential 低于 max_potential 时 +1（潜在能力缓慢恢复）",
            state_change='if(potential < max_potential) add("potential", 1)',
            kind="effect",
        ),
        Postcondition(
            description="thief > 0 时 -1（偷窃标记衰减）",
            state_change='if(thief > 0) add("thief", -1)',
            kind="effect",
        ),
        Postcondition(
            description="combat_exp 增长过快时记录日志（3*c > m 时 log_file('CombatExp')）",
            state_change='if(3*c > m) log_file("CombatExp", ...)',
            kind="effect",
        ),
        Postcondition(
            description="combat_exp_last 和 mud_age_last 更新为当前值",
            state_change='set("combat_exp_last", combat_exp); set("mud_age_last", mud_age)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="reset 是周期性调用（由 driver reset 机制触发），非每 tick 执行",
            scope="system",
        ),
        Invariant(
            description="combat_exp 增长检测：3*combat_exp_delta > time_delta 时记录异常日志（防刷经验）",
            lpc_expr="3 * (combat_exp - combat_exp_last) > (mud_age - mud_age_last) => log",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="potential 低于 max 时 +1",
            lpc_call='if(query("potential") < query("max_potential")) add("potential", 1)',
            target="this_object.potential",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="thief > 0 时 -1（偷窃标记衰减）",
            lpc_call='if(query("thief") > 0) add("thief", -1)',
            target="this_object.thief",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="combat_exp 增长过快时记录日志（防刷经验检测）",
            lpc_call='if(3*c > m) log_file("CombatExp", sprintf(...))',
            target="log",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="更新 combat_exp_last 和 mud_age_last 为当前值",
            lpc_call='set("combat_exp_last", query("combat_exp")); set("mud_age_last", query("mud_age"))',
            target="this_object",
        ),
    ],
    notes=(
        "reset 由 driver 周期性调用（非每 tick），用于潜在能力恢复、偷窃标记衰减、"
        "和 combat_exp 异常增长检测（防刷经验）。"
    ),
)


# ---------------------------------------------------------------------------
# login.c 函数规格
# ---------------------------------------------------------------------------

_login_logon = FunctionSpec(
    signature=FunctionSignature(
        name="logon",
        params=[],
        return_type="void",
        lpc_file="clone/user/login.c",
        line_range=(9, 13),
    ),
    preconditions=[
        Precondition(
            description="LOGIN 对象刚被创建（由 master.c 的 connect() 创建）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="call_out('time_out', LOGIN_TIMEOUT) 安排登录超时定时器",
            state_change='call_out("time_out", LOGIN_TIMEOUT)',
            kind="effect",
        ),
        Postcondition(
            description="LOGIN_D->logon(this_object()) 委托登录流程给 LOGIN_D 状态机",
            state_change="LOGIN_D->logon(this_object())",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="login.c 的 logon 仅是 LOGIN_D 状态机的委托入口，实际登录流程属层 H",
            scope="system",
        ),
        Invariant(
            description="LOGIN_TIMEOUT 超时后 time_out() 销毁 LOGIN 对象（防止占用连接）",
            lpc_expr='call_out("time_out", LOGIN_TIMEOUT)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="call_out('time_out', LOGIN_TIMEOUT) 安排登录超时定时器",
            lpc_call='call_out("time_out", LOGIN_TIMEOUT)',
            target="call_out_queue",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="LOGIN_D->logon(this_object()) 委托登录流程给 LOGIN_D 状态机（层 H）",
            lpc_call="LOGIN_D->logon(this_object())",
            target="LOGIN_D",
        ),
    ],
    notes=(
        "login.c 的 logon 是登录流程的连接对象入口。"
        "它只做两件事：安排超时定时器 + 委托 LOGIN_D 状态机。"
        "LOGIN_D 的完整状态机（输入用户名/密码/选择角色等）属层 H。"
    ),
)


_login_time_out = FunctionSpec(
    signature=FunctionSignature(
        name="time_out",
        params=[],
        return_type="void",
        lpc_file="clone/user/login.c",
        line_range=(23, 29),
    ),
    preconditions=[
        Precondition(
            description="LOGIN 对象存在，可能处于登录流程中或已完成",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="若 body_ob 已存在（登录完成）则直接返回（不销毁）",
            state_change='if(objectp(query_temp("body_ob"))) return',
            kind="effect",
        ),
        Postcondition(
            description="若仍 interactive（连接中），输出超时消息",
            state_change='if(interactive(this_object())) write("您花在连线进入手续的时间太久了...")',
            kind="effect",
        ),
        Postcondition(
            description="destruct(this_object()) 销毁 LOGIN 对象",
            state_change="destruct(this_object())",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="body_ob 已存在时不销毁（登录已完成，LOGIN 对象可安全销毁但不影响玩家）",
            lpc_expr='objectp(query_temp("body_ob")) => return (不执行 destruct)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查 body_ob 是否存在，存在则 return（登录已完成）",
            lpc_call='if(objectp(query_temp("body_ob"))) return',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="仍 interactive 时输出超时消息",
            lpc_call='if(interactive(this_object())) write("您花在连线进入手续的时间太久了，下次想好再来吧。\\n")',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="destruct(this_object()) 销毁 LOGIN 对象",
            lpc_call="destruct(this_object())",
            target="this_object",
        ),
    ],
    notes="time_out 是登录超时的回调，由 logon 中的 call_out 安排。",
)


_login_net_dead = FunctionSpec(
    signature=FunctionSignature(
        name="net_dead",
        params=[],
        return_type="void",
        lpc_file="clone/user/login.c",
        line_range=(17, 21),
    ),
    preconditions=[
        Precondition(
            description="LOGIN 对象的连接断开（driver 检测到断线）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="取消原 time_out 定时器",
            state_change='remove_call_out("time_out")',
            kind="effect",
        ),
        Postcondition(
            description="安排 1 秒后 time_out（延迟销毁，避免 Double call to remove_interactive 错误）",
            state_change='call_out("time_out", 1)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="不在 net_dead 中直接 destruct(this_object())，而是延迟 1 秒，"
            "避免 'Double call to remove_interactive()' 错误",
            lpc_expr='call_out("time_out", 1) instead of destruct(this_object())',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="remove_call_out('time_out') 取消原超时定时器",
            lpc_call='remove_call_out("time_out")',
            target="call_out_queue",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.CALL_OUT,
            description="call_out('time_out', 1) 延迟 1 秒后执行 time_out（避免 Double call）",
            lpc_call='call_out("time_out", 1)',
            target="call_out_queue",
        ),
    ],
    notes=(
        "login.c 的 net_dead 不直接 destruct，而是延迟 1 秒后通过 time_out 销毁。"
        "注释明确说明：不在 net_dead interactive apply 中直接 destruct(this_object())，"
        "否则会产生 'Double call to remove_interactive()' 错误。"
        "这是 LPC driver 的已知陷阱，新引擎需注意避免类似问题。"
    ),
)


_login_receive_message = FunctionSpec(
    signature=FunctionSignature(
        name="receive_message",
        params=[
            LPCParam(name="type", lpc_type="string", description="消息类型"),
            LPCParam(name="str", lpc_type="string", description="消息内容"),
        ],
        return_type="void",
        lpc_file="clone/user/login.c",
        line_range=(41, 45),
    ),
    preconditions=[
        Precondition(
            description="LOGIN 对象已创建，连接活跃",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="仅 type=='write' 时调用 receive(str) 发送到客户端",
            state_change='if(type != "write") return; receive(str)',
            kind="effect",
        ),
        Postcondition(
            description="非 'write' 类型的消息被丢弃（LOGIN 对象只接收 write 类型）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="LOGIN 对象只处理 write 类型消息，其他类型（如 combat/system）被过滤",
            lpc_expr='type != "write" => return (丢弃)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="type=='write' 时 receive(str) 发送消息到客户端",
            lpc_call='if(type != "write") return; receive(str)',
            target="client",
        ),
    ],
    notes="LOGIN 对象的 receive_message 过滤非 write 消息，只传递登录流程文本到客户端。",
)


_login_set = FunctionSpec(
    signature=FunctionSignature(
        name="set",
        params=[
            LPCParam(name="prop", lpc_type="string", description="属性名"),
            LPCParam(name="data", lpc_type="mixed", description="属性值"),
        ],
        return_type="mixed",
        lpc_file="clone/user/login.c",
        line_range=(53, 57),
    ),
    preconditions=[
        Precondition(
            description="调用者的 euid 必须是 ROOT_UID（否则返回 0，防黑客篡改登录数据）",
            lpc_expr='geteuid(previous_object()) == ROOT_UID',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非 ROOT_UID 调用时返回 0（拒绝写入）",
            return_value="0=权限不足",
            kind="ensure",
        ),
        Postcondition(
            description="ROOT_UID 调用时执行 ::set(prop, data) 并返回结果",
            state_change="::set(prop, data)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="LOGIN 对象的 set 被 nomask 覆盖，防止非 ROOT 对象篡改登录数据",
            lpc_expr="nomask set => geteuid(previous_object()) == ROOT_UID",
            scope="class",
        ),
        Invariant(
            description="这是安全防护：LOGIN 对象存储账号密码等敏感数据，不可被普通对象修改",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查调用者 euid，非 ROOT_UID 时返回 0",
            lpc_call='if(geteuid(previous_object()) != ROOT_UID) return 0',
            target="caller",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="ROOT_UID 时执行 ::set(prop, data) 写入属性",
            lpc_call="::set(prop, data)",
            target="this_object",
        ),
    ],
    notes=(
        "LOGIN 对象的 set 被 nomask 覆盖，是安全防护措施。"
        "注释明确说 'Protect login object's data against hackers'。"
        "只有 ROOT_UID 的对象（如 LOGIN_D）才能修改 LOGIN 对象的属性，"
        "防止恶意对象篡改账号密码等敏感数据。"
    ),
)


# ---------------------------------------------------------------------------
# 层 I 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="I",
    layer_name="角色与登录",
    lpc_files=[
        "inherit/char/char.c",
        "clone/user/user.c",
        "clone/user/login.c",
    ],
    function_specs=[
        # char.c (CHARACTER 基类)
        _char_create,
        _char_setup,
        _heart_beat_skeleton,
        _visible,
        # user.c (USER 对象)
        _user_create,
        _user_save,
        _user_setup,
        _user_update_age,
        _user_restore_autoload,
        _user_net_dead,
        _user_reconnect,
        _user_dump,
        _user_reset,
        # login.c (LOGIN 对象)
        _login_logon,
        _login_time_out,
        _login_net_dead,
        _login_receive_message,
        _login_set,
    ],
    cross_layer_refs=[
        "set_heart_beat (层 A: driver) -- setup/heart_beat 心跳控制",
        "destruct (层 A: driver) -- net_dead 中销毁 link_ob / time_out 中销毁 LOGIN 对象",
        "seteuid / getuid / geteuid (层 A: driver) -- create/setup 中的赋权",
        "save_object / restore_object (层 A: driver) -- F_SAVE 的 efun",
        "call_out / remove_call_out (层 A: driver) -- logon 超时 / net_dead 定时器 / user_dump",
        "set / query / add / set_temp / query_temp (层 B: F_DBASE) -- 状态读写",
        "set_name (层 B: F_NAME) -- user.c create 中设置名称",
        "save / restore (层 B: F_SAVE) -- user.c save 委托 ::save",
        "save_autoload / restore_autoload / clean_up_autoload (层 B: F_AUTOLOAD) -- 玩家存档物品",
        "enable_player (层 C: command) -- setup 中启用命令系统",
        "command (层 C: command_hook) -- user_dump / net_dead 中 command('quit')",
        "move (层 B: F_MOVE) -- restore_autoload 中物品 move 到 inventory",
        "tell_room / tell_object / write / receive (层 B: F_MESSAGE) -- 消息输出",
        "receive_message (层 B: F_MESSAGE) -- login.c 的消息过滤",
        "message (层 B: F_MESSAGE) -- terminal_type 中的系统消息",
        "heart_beat 七步 (层 G: NPC AI) -- 本层仅提取骨架入口和玩家分支",
        "die / unconcious / heal_up (层 F: 死亡轮回) -- heart_beat 中调用",
        "attack / is_fighting / remove_all_enemy (层 E: combat) -- heart_beat/net_dead 中调用",
        "update_condition (层 B: F_CONDITION) -- heart_beat 步骤 7",
        "is_busy / continue_action (层 B: F_ACTION) -- heart_beat 步骤 5",
        "GO_CMD->do_flee (层 D: world) -- heart_beat wimpy 自动逃跑",
        "LOGIN_D->logon (层 H: LOGIN_D 状态机) -- login.c logon 委托",
        "CHAR_D->setup_char (层 H: 核心守护进程) -- setup 中属性计算",
        "CHANNEL_D->do_channel (层 H: 频道系统) -- heart_beat 频道清理 / net_dead 系统消息",
        "NATURE_D (层 H: 时间系统) -- update_age 的时间映射基础",
        "wiz_level / wizhood (层 H: 安全系统) -- visible 巫师等级判定 / user_dump 巫师豁免",
        "is_character / is_ghost (层 B: F_DBASE) -- visible 中的类型/状态判定",
        "query_idle (层 A: driver) -- heart_beat 中 idle 超时检测",
        "log_file (层 A: driver) -- reset 中 combat_exp 异常日志",
    ],
    notes=(
        "层 I 覆盖角色对象生命周期（create -> setup -> active -> net_dead/reconnect）+ "
        "登录连接载体（login.c）+ 玩家专属功能（save/update_age/restore_autoload/user_dump/reset）。\n"
        "\n"
        "核心契约要点：\n"
        "1. visible 判定逻辑：巫师等级 > invisibility > 鬼魂状态（优先级递减）。\n"
        "   PronounContext 必须携带 viewer（CLAUDE.md 架构不变量）。\n"
        "2. JSON 存档崩溃安全：user.c save 的三步交织（save_autoload -> ::save -> clean_up_autoload），\n"
        "   新引擎要求 write-temp+os.replace 原子写（CLAUDE.md 架构不变量）。\n"
        "3. heart_beat 玩家 vs NPC 分支：本层提取骨架入口和玩家专属分支\n"
        "   （频道清理/update_age/idle 超时），七步细节属层 G。\n"
        "4. update_age 时间系统：真实 1 秒 = 游戏 1 分钟，age<=24 每 86400 秒长 1 岁，\n"
        "   age>24 每 259200 秒长 1 岁（衰老减速）。\n"
        "5. login.c 委托 LOGIN_D 状态机（层 H），仅提取连接载体接口。\n"
        "\n"
        "边界：\n"
        "- F_ATTACK/F_DAMAGE/F_SKILL/F_ATTRIBUTE/F_EQUIP 完整规格后置\n"
        "- F_AUTOLOAD 完整实现后置（仅提取 restore_autoload 接口契约）\n"
        "- F_FINANCE/F_MARRY/F_TEAM 社交特性后置\n"
        "- heart_beat 七步细节属层 G\n"
        "- LOGIN_D 状态机属层 H"
    ),
)
