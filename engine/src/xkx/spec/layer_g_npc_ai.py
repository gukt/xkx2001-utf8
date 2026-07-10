"""层 G：NPC AI -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``inherit/char/char.c`` -- heart_beat() 心跳主循环（七步管线骨架）+ setup()
- ``inherit/char/npc.c`` -- chat()（自动恢复 + 随机对话）/ random_move() / return_home()
- ``feature/attack.c`` -- init()（玩家进房间触发 auto_fight 三触发） /
  select_opponent() / clean_up_enemy()
- ``adm/daemons/combatd.c`` -- auto_fight() + start_hatred/start_vendetta/start_aggressive

核心契约要点：
1. **heart_beat 七步管线**（char.c:60-169）：每 1s 执行一次（set_heart_beat(1)），
   七步为：(1) 玩家频道清理 (2) 属性上限检查 (3) 濒死检查 (4) 昏迷/死亡检查
   (5) 战斗行动 (6) NPC chat (7) tick 衰减条件更新 + 自愈 + 空闲心跳关闭。
   前四步可提前 return（死亡/昏迷），第五步可提前 return（busy），第六步可提前
   return（chat 导致 destruct）。tick 为 5+random(10) 的非均匀周期，控制条件
   更新和自愈频率以节省 CPU。
2. **派生变更审计**（dissent 7）：heart_beat/chat/auto_fight 的所有副作用必须在
   规格中按交织顺序明确记录。chat() 的自动恢复（exert_function）和随机对话
   （say/evaluate）的副作用交织不可分离。
3. **auto_fight 三触发**（attack.c init + combatd.c auto_fight）：
   - **hatred**：NPC 仇恨列表中有此玩家 ID（is_killing(ob->query("id"))）
   - **vendetta**：NPC 有 vendetta_mark 且玩家有对应 vendetta 标记
   - **aggressive**：NPC attitude=="aggressive"，玩家进房间即触发
   三触发通过 COMBAT_D->auto_fight(me, ob, type) 入口，经 call_out 延迟 0 tick
   执行对应的 start_<type> 函数。call_out 给受害者一个"溜走"的机会。
4. **chat() 自动恢复**：neili>100 时按阈值触发 refresh（jingli<90%）/recover
   （qi<80%）/regenerate（jing<70%），通过 SKILL_D("force")->exert_function
   执行。恢复与随机对话在同一函数内交织执行。
5. **random_move()**：NPC 随机移动，需 jingli>=max_jingli/2，选择随机方向
   （exits+doors），关门自动 open，委托 command("go "+dir)。

关键不变量：
- **tick=1s + compute<100ms + 非均匀 tick**（CLAUDE.md 架构不变量）：
  heart_beat 每 1s 执行，但条件更新和自愈通过 tick 衰减降频（5+random(10)
  的非均匀周期），避免高频 heal_up/update_condition 的 CPU 开销。
- **空闲心跳关闭**：NPC 在完全和平（无战斗、无交互、房间无玩家）时
  set_heart_beat(0) 关闭心跳，由玩家进入房间时重新激活。
- **派生变更审计**（dissent 7）：heart_beat 中 chat() 可能导致 destruct
  （this_object 销毁），后续代码必须检查 this_object() 是否存在。
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
# 层 G 特定模型
# ---------------------------------------------------------------------------


class AutoFightTrigger(StrEnum):
    """auto_fight 三触发类型（LPC attack.c init + combatd.c auto_fight）。

    对应 COMBAT_D->auto_fight(me, ob, type) 的 type 参数，
    经 call_out("start_" + type, 0, me, obj) 延迟执行。
    """

    HATRED = "hatred"
    """仇恨触发：NPC 仇恨列表（killer 数组）中有此玩家 ID，
    is_killing(ob->query("id")) 为真。start_hatred 直接 kill_ob。"""

    VENDETTA = "vendetta"
    """仇杀触发：NPC 有 vendetta_mark 属性，且玩家有对应 vendetta 标记
    （ob->query("vendetta/" + vendetta_mark) 为真）。
    start_vendetta 直接 kill_ob。"""

    AGGRESSIVE = "aggressive"
    """主动攻击：NPC attitude=="aggressive"，玩家进入房间即触发。
    start_aggressive 直接 kill_ob。"""


class HeartBeatStep(StrEnum):
    """heart_beat 七步管线步骤标识（char.c:60-169）。

    前四步可提前 return（死亡/昏迷），第五步可提前 return（busy），
    第六步可提前 return（chat 导致 destruct）。第七步仅在 tick 衰减到 0 时执行。
    """

    CHANNEL_CLEANUP = "channel_cleanup"
    """玩家频道清理 + 刷屏检测（仅 userp）。clear_cmd_count + channel_msg_cnt 检查。"""

    ATTRIBUTE_CAP = "attribute_cap"
    """属性上限检查：neili/jingli/jing 封顶为 max*2。"""

    MORTAL_WOUND_CHECK = "mortal_wound_check"
    """濒死检查：eff_qi<0 或 eff_jing<0 -> remove_all_enemy + die + return。"""

    UNCONSCIOUS_CHECK = "unconscious_check"
    """昏迷/死亡检查：qi<0 或 jing<0 或 jingli<0 -> remove_all_enemy + unconcious/die + return。"""

    COMBAT_ACTION = "combat_action"
    """战斗行动：is_busy ? continue_action+return : wimpy_flee+attack。"""

    NPC_CHAT = "npc_chat"
    """NPC chat（仅 !userp）：调用 chat()，chat 可能 destruct(this_object)。"""

    TICK_DECAY = "tick_decay"
    """tick 衰减：tick-- 到 0 时执行 update_condition + heal_up + 空闲心跳关闭。"""


# ---------------------------------------------------------------------------
# char.c 函数规格
# ---------------------------------------------------------------------------

_heart_beat = FunctionSpec(
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
            description="若对象在步骤 3/4 死亡或昏迷，后续步骤不执行",
            state_change="die() 或 unconcious() 后 return",
            kind="effect",
        ),
        Postcondition(
            description="若 NPC 在步骤 6 被 chat() 内 destruct，后续步骤不执行",
            state_change="chat() 后 !this_object() 则 return",
            kind="effect",
        ),
        Postcondition(
            description="完全和平的 NPC 在步骤 7 可能 set_heart_beat(0) 关闭心跳",
            state_change="set_heart_beat(0)（无战斗、无交互、房间无玩家时）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="tick=1s + compute<100ms：heart_beat 每 1s 执行一次（set_heart_beat(1)）",
            lpc_expr="set_heart_beat(1)",
            scope="system",
        ),
        Invariant(
            description="非均匀 tick：条件更新和自愈通过 tick=5+random(10) 衰减降频，非每 tick 执行",
            lpc_expr="tick = 5 + random(10); if(tick--) return; else tick = 5 + random(10)",
            scope="function",
        ),
        Invariant(
            description="七步顺序不可重排：channel -> attr_cap -> mortal -> unconscious -> combat -> chat -> tick_decay",
            lpc_expr="order(channel) < order(attr_cap) < order(mortal) < order(unconscious) < order(combat) < order(chat) < order(tick_decay)",
            scope="function",
        ),
        Invariant(
            description="chat() 可能 destruct(this_object())，后续代码必须检查 this_object() 存在性",
            lpc_expr="chat() 后 if(!this_object()) return",
            scope="function",
        ),
        Invariant(
            description="heal_up() 优先于 is_fighting/interactive 检查（&& 短路求值保证 heal_up 先调用）",
            lpc_expr="(cnd_flag & CND_NO_HEAL_UP) || !heal_up() && !is_fighting() && !interactive()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 1（仅 userp）：clear_cmd_count 重置命令计数；channel_msg_cnt>10 时关闭频道",
            lpc_call="clear_cmd_count(); set('chblk_on', 1)（刷屏时）",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="步骤 1（仅 userp）：刷屏时 CHANNEL_D->do_channel 输出谣言消息",
            lpc_call='CHANNEL_D->do_channel(rum_ob, "rumor", ...)',
            target="channel",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 2：neili/jingli/jing 超过 max*2 时封顶",
            lpc_call='my["neili"] = my["max_neili"]*2 (etc.)',
            target="this_object.neili/jingli/jing",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 3：eff_qi<0 或 eff_jing<0 时 remove_all_enemy + die + return",
            lpc_call="remove_all_enemy(); die(); return",
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 4：qi<0/jing<0/jingli<0 时 remove_all_enemy；living 则 unconcious，昏迷中则 die",
            lpc_call="remove_all_enemy(); unconcious() 或 die()",
            target="this_object",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="步骤 5：is_busy 时 continue_action() 后 return（不执行后续步骤）",
            lpc_call="continue_action(); return",
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="步骤 5：非 busy 时 wimpy 逃跑判定（qi/jing/jingli 百分比 <= wimpy_ratio 则 GO_CMD->do_flee）",
            lpc_call="GO_CMD->do_flee(this_object())",
            target="this_object",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="步骤 5：调用 attack() 执行战斗行动（clean_up_enemy + select_opponent + COMBAT_D->fight）",
            lpc_call="attack()",
            target="this_object",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.EXTERNAL,
            description="步骤 6（仅 !userp）：调用 chat()，可能触发自动恢复 + 随机对话 + random_move",
            lpc_call="this_object()->chat()",
            target="this_object",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="步骤 6 后：chat() 可能 destruct(this_object())，检查后 return",
            lpc_call="if(!this_object()) return",
            target="this_object",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 7：tick-- 衰减，未到 0 则 return",
            lpc_call="if(tick--) return; else tick = 5 + random(10)",
            target="this_object.tick",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（tick 到 0 时）：update_condition() 更新所有状态条件",
            lpc_call="cnd_flag = update_condition()",
            target="this_object",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 7：heal_up() 自愈（qi/jing/jingli/neili 恢复），CND_NO_HEAL_UP 时跳过",
            lpc_call="heal_up()",
            target="this_object.qi/jing/jingli/neili",
        ),
        SideEffect(
            order=14,
            kind=SideEffectType.STATE_MUTATION,
            description="步骤 7：完全和平时 set_heart_beat(0) 关闭心跳（无战斗 + 无交互 + 房间无玩家）",
            lpc_call="set_heart_beat(0)",
            target="this_object.heart_beat",
        ),
        SideEffect(
            order=15,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（仅 interactive）：update_age() 更新玩家年龄",
            lpc_call="this_object()->update_age()",
            target="this_object",
        ),
        SideEffect(
            order=16,
            kind=SideEffectType.EXTERNAL,
            description="步骤 7（仅 interactive）：query_idle 超 IDLE_TIMEOUT 时 user_dump(DUMP_IDLE)",
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
            determinism_note="tick 周期随机性属 NPC AI 层，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "heart_beat 是 NPC AI 的核心驱动循环，七步管线覆盖自愈、状态更新、战斗、"
        "对话、移动等全部 NPC 自动行为。前四步（频道清理/属性封顶/濒死/昏迷）"
        "是保护性检查，可提前 return。第五步（战斗）是核心行动步骤。"
        "第六步（chat）仅 NPC 执行，可能 destruct。第七步（tick 衰减）"
        "以非均匀周期降频执行条件更新和自愈。\n"
        "CLAUDE.md 架构不变量：tick=1s + compute<100ms + 非均匀 tick。\n"
        "玩家 heart_beat 属层 I，本规格仅提取通用管线（NPC 路径），"
        "userp 分支的频道清理/年龄更新/idle 超时在副作用中标注但属层 I 范围。"
    ),
)


_setup = FunctionSpec(
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
    ],
    postconditions=[
        Postcondition(
            description="seteuid 设为对象自身 uid",
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
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置对象 euid 为自身 uid",
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
            determinism_note="tick 随机性属 NPC AI 层，不需要确定性 RNG",
        ),
    ],
    notes="setup 是 heart_beat 启动的入口，在 create 之后、对象进入世界之前调用。",
)


# ---------------------------------------------------------------------------
# npc.c 函数规格
# ---------------------------------------------------------------------------

_chat = FunctionSpec(
    signature=FunctionSignature(
        name="chat",
        params=[],
        return_type="int",
        lpc_file="inherit/char/npc.c",
        line_range=(99, 128),
    ),
    preconditions=[
        Precondition(
            description="NPC 有当前环境（environment() 非 null）",
            lpc_expr="environment()",
            kind="require",
        ),
        Precondition(
            description="NPC 是 living 状态",
            lpc_expr="living(this_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="无 chat_chance 配置时返回 0（不执行对话）",
            return_value="0=无 chat_chance 或无 chat_msg",
            kind="ensure",
        ),
        Postcondition(
            description="有 chat_chance 且随机命中时执行对话消息或函数，返回 1",
            return_value="1=对话已执行",
            kind="ensure",
        ),
        Postcondition(
            description="自动恢复可能已触发（neili>100 且对应属性低于阈值时）",
            state_change="jingli/qi/jing 可能通过 exert_function 恢复",
            kind="effect",
        ),
        Postcondition(
            description="对话消息为 functionp 时 evaluate 执行，可能产生任意副作用",
            state_change="evaluate(msg[rnd]) 的副作用（不可预测）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="自动恢复优先于随机对话：先检查 neili>100 和属性阈值，再检查 chat_chance",
            lpc_expr="exert_function 调用先于 random(100) < chance 判定",
            scope="function",
        ),
        Invariant(
            description="战斗状态使用 chat_chance_combat/chat_msg_combat，非战斗使用 chat_chance/chat_msg",
            lpc_expr="is_fighting() ? 'chat_chance_combat' : 'chat_chance'",
            scope="function",
        ),
        Invariant(
            description="chat() 可能调用 destruct(this_object())（通过 evaluate 函数型消息），"
            "调用方必须在 chat() 后检查 this_object() 存在性",
            lpc_expr="chat() 后 if(!this_object()) return",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="自动恢复：neili>100 且 jingli<90% 时 exert_function('refresh')",
            lpc_call='SKILL_D("force")->exert_function(this_object(), "refresh")',
            target="this_object.jingli",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="自动恢复：neili>100 且 qi<80%（相对 eff_qi）时 exert_function('recover')",
            lpc_call='SKILL_D("force")->exert_function(this_object(), "recover")',
            target="this_object.qi",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="自动恢复：neili>100 且 jing<70%（相对 eff_jing）时 exert_function('regenerate')",
            lpc_call='SKILL_D("force")->exert_function(this_object(), "regenerate")',
            target="this_object.jing",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="查询 chat_chance（战斗时用 chat_chance_combat），无则返回 0",
            lpc_call='chance = query(is_fighting() ? "chat_chance_combat" : "chat_chance")',
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="random(100) < chance 且 msg[rnd] 为 stringp 时 say(msg[rnd]) 输出对话",
            lpc_call="say(msg[rnd])",
            target="room",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="msg[rnd] 为 functionp 时 evaluate(msg[rnd]) 执行（可能产生任意副作用）",
            lpc_call="evaluate(msg[rnd])",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(100)",
            probability_model="P(触发对话) = chance/100",
            semantic="chat_chance 概率判定是否执行随机对话",
            seed_inputs=["chat_chance"],
            determinism_note="NPC 对话随机性属 NPC AI 层，非 combat 范围，不需要确定性 RNG",
        ),
        RandomSpec(
            lpc_call="random(sizeof(msg))",
            probability_model="1/sizeof(msg) 均匀分布选择对话消息",
            semantic="从 chat_msg 数组中随机选择一条对话消息",
            seed_inputs=["chat_msg"],
            determinism_note="NPC 对话随机性属 NPC AI 层，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "chat() 是 NPC 自动行为的核心调度函数，由 heart_beat 步骤 6 调用。"
        "它同时承担自动恢复（exert_function）和随机对话（say/evaluate）两个职责，"
        "副作用交织不可分离。functionp 型对话消息可产生任意副作用（包括 destruct），"
        "这是 heart_beat 中 if(!this_object()) return 检查的原因。\n"
        "派生变更审计（dissent 7）：chat 的所有副作用已按交织顺序记录。"
    ),
)


_random_move = FunctionSpec(
    signature=FunctionSignature(
        name="random_move",
        params=[],
        return_type="int",
        lpc_file="inherit/char/npc.c",
        line_range=(131, 152),
    ),
    preconditions=[
        Precondition(
            description="NPC 有当前环境（environment() 非 null）",
            lpc_expr="objectp(environment())",
            kind="require",
        ),
        Precondition(
            description="当前房间有 exits 映射",
            lpc_expr="mapp(exits = environment()->query('exits'))",
            kind="require",
        ),
        Precondition(
            description="NPC 精力 >= max_jingli/2（非精疲力尽）",
            lpc_expr='query("jingli") >= query("max_jingli") / 2',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功移动返回 1，无法移动返回 0",
            return_value="1=已移动, 0=无法移动",
            kind="ensure",
        ),
        Postcondition(
            description="成功时 NPC 已通过 command('go '+dir) 移动到随机相邻房间",
            state_change="NPC 位置变更到随机相邻房间",
            kind="effect",
        ),
        Postcondition(
            description="若选定方向有关闭的门，先执行 command('open '+dir) 开门",
            state_change="门状态可能从 DOOR_CLOSED 变为开启",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="random_move 委托 command('go '+dir) 执行移动，不直接 move",
            lpc_expr="command('go ' + dir) 委托 GO_CMD->main",
            scope="function",
        ),
        Invariant(
            description="方向候选集 = exits keys + doors keys（人类 NPC 含门方向）",
            lpc_expr="dirs = keys(exits) + (race=='人类' ? keys(doors) : [])",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="收集方向候选集：exits keys + doors keys（人类 NPC）",
            lpc_call="dirs = keys(exits); dirs += keys(doors)（人类）",
            target="dirs",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="随机选择一个方向",
            lpc_call="dir = dirs[random(sizeof(dirs))]",
            target="dir",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="若选定方向有关闭的门，command('open '+dir) 开门",
            lpc_call='command("open " + dir)',
            target="door",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="command('go '+dir) 委托 GO_CMD 执行移动",
            lpc_call='command("go " + dir)',
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(sizeof(dirs))",
            probability_model="1/sizeof(dirs) 均匀分布选择移动方向",
            semantic="从可用方向中随机选择一个移动方向",
            seed_inputs=["exits", "doors"],
            determinism_note="NPC 移动随机性属 NPC AI 层，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "random_move 是 chat_msg 中常用的默认函数，由 NPC 在 chat() 中通过 "
        "evaluate(functionp 型消息) 调用。它委托 GO_CMD->main 执行实际移动，"
        "移动管线（valid_leave/move/follow_me）的完整副作用见层 D 规格中的 go main。\n"
        "cross_layer_refs: valid_leave/go main 属层 D，command 属层 C。"
    ),
)


_return_home = FunctionSpec(
    signature=FunctionSignature(
        name="return_home",
        params=[
            LPCParam(name="home", lpc_type="object", description="NPC 的起始房间"),
        ],
        return_type="int",
        lpc_file="inherit/char/npc.c",
        line_range=(77, 94),
    ),
    preconditions=[
        Precondition(
            description="home 是有效对象",
            lpc_expr="objectp(home)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="已在 home 或无环境时返回 1（已在家）",
            return_value="1=已在家",
            kind="ensure",
        ),
        Postcondition(
            description="无法回家（非 living / 战斗中）时返回 0",
            return_value="0=无法回家",
            kind="ensure",
        ),
        Postcondition(
            description="成功回家时 NPC 已 move 到 home 房间",
            state_change="move(home) 已执行",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="非 living 或战斗中的 NPC 不会回家",
            lpc_expr="!living(this_object()) || is_fighting() => return 0",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向当前房间输出 '<NPC名>急急忙忙地离开了。'（不含 NPC 自身）",
            lpc_call='message("vision", name()+"急急忙忙地离开了。\\n", environment(), this_object())',
            target="current_room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="move(home) 将 NPC 移回起始房间",
            lpc_call="move(home)",
            target="this_object",
        ),
    ],
    random_specs=[],
    notes=(
        "return_home 由房间 reset() 调用（层 D make_inventory/reset 规格），"
        "用于将偏离起始房间的 NPC 召回。"
    ),
)


# ---------------------------------------------------------------------------
# attack.c 函数规格
# ---------------------------------------------------------------------------

_init_attack = FunctionSpec(
    signature=FunctionSignature(
        name="init",
        params=[],
        return_type="void",
        lpc_file="feature/attack.c",
        line_range=(229, 258),
    ),
    preconditions=[
        Precondition(
            description="另一个对象（通常是玩家）移动到 NPC 所在房间，触发 init",
            lpc_expr="this_player() 已设置 && environment(this_player()) == environment(this_object())",
            kind="require",
        ),
        Precondition(
            description="NPC 未在战斗中、是 living 状态、this_player 有效且在同一房间、living 且非 linkdead",
            lpc_expr="!is_fighting() && living(this_object()) && (ob=this_player()) && environment(ob)==environment() && living(ob) && !ob->query('linkdead')",
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="满足 auto_fight 触发条件时，已调用 COMBAT_D->auto_fight 启动战斗",
            state_change="COMBAT_D->auto_fight(this_object(), ob, type) 已调用",
            kind="effect",
        ),
        Postcondition(
            description="不满足任何触发条件时无副作用",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="前置守卫：is_fighting 或 !living 或 !this_player 或不同房间或 !living(ob) 或 linkdead 时直接返回",
            lpc_expr="!is_fighting() && living(this_object()) && (ob=this_player()) && environment(ob)==environment() && living(ob) && !ob->query('linkdead')",
            scope="function",
        ),
        Invariant(
            description="三触发优先级：hatred > vendetta > aggressive（if-else 链短路）",
            lpc_expr="hatred -> vendetta -> aggressive（首个命中即 return）",
            scope="function",
        ),
        Invariant(
            description="三触发均要求 userp(ob)（NPC 不主动攻击 NPC，auto_fight 内部再次验证）",
            lpc_expr="userp(ob)（hatred/aggressive）或 vendetta_mark 检查",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="触发 hatred：is_killing(ob->query('id')) 为真时调用 COMBAT_D->auto_fight(me, ob, 'hatred')",
            lpc_call='COMBAT_D->auto_fight(this_object(), ob, "hatred")',
            target="combat_system",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="触发 vendetta：vendetta_mark 匹配时调用 COMBAT_D->auto_fight(me, ob, 'vendetta')",
            lpc_call='COMBAT_D->auto_fight(this_object(), ob, "vendetta")',
            target="combat_system",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="触发 aggressive：attitude=='aggressive' 时调用 COMBAT_D->auto_fight(me, ob, 'aggressive')",
            lpc_call='COMBAT_D->auto_fight(this_object(), ob, "aggressive")',
            target="combat_system",
        ),
    ],
    random_specs=[],
    notes=(
        "init() 是 LPC driver 在对象移动到同一房间时自动调用的钩子。"
        "attack.c 的 init 覆盖了基类 init，专门处理 auto_fight 触发。\n"
        "三触发是 NPC AI 的核心入口：hatred 查 killer 数组，vendetta 查 "
        "vendetta_mark 映射，aggressive 查 attitude 属性。\n"
        "实际的战斗启动在 COMBAT_D->auto_fight -> call_out('start_'+type) 中完成，"
        "call_out 延迟 0 tick 给受害者一个'溜走'的机会。"
    ),
)


_auto_fight = FunctionSpec(
    signature=FunctionSignature(
        name="auto_fight",
        params=[
            LPCParam(name="me", lpc_type="object", description="发起攻击的 NPC"),
            LPCParam(name="obj", lpc_type="object", description="被攻击的目标（玩家）"),
            LPCParam(name="type", lpc_type="string", description="触发类型：hatred/vendetta/aggressive"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(852, 867),
    ),
    preconditions=[
        Precondition(
            description="me 和 obj 不能都是 NPC（至少一方是 userp）",
            lpc_expr="!(!userp(me) && !userp(obj))",
            kind="guard",
        ),
        Precondition(
            description="me 未有待处理的 auto_fight（looking_for_trouble 标记未设置）",
            lpc_expr='!me->query_temp("looking_for_trouble")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="me 的 looking_for_trouble 标记已设置",
            state_change='me->set_temp("looking_for_trouble", 1)',
            kind="effect",
        ),
        Postcondition(
            description="已通过 call_out 延迟 0 tick 调用 start_<type>(me, obj)",
            state_change='call_out("start_" + type, 0, me, obj)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="NPC 不 auto_fight NPC（双 NPC 时直接返回）",
            lpc_expr="!userp(me) && !userp(obj) => return",
            scope="function",
        ),
        Invariant(
            description="looking_for_trouble 防重入：同一 NPC 不会同时有多个 auto_fight 待处理",
            lpc_expr='query_temp("looking_for_trouble") => return',
            scope="function",
        ),
        Invariant(
            description="call_out 延迟 0 tick：给受害者一个在 start_<type> 执行前离开房间的机会",
            lpc_expr='call_out("start_" + type, 0, me, obj)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 looking_for_trouble 防重入标记",
            lpc_call='me->set_temp("looking_for_trouble", 1)',
            target="me.temp.looking_for_trouble",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.CALL_OUT,
            description="call_out 延迟 0 tick 调用 start_<type>(me, obj)",
            lpc_call='call_out("start_" + type, 0, me, obj)',
            target="call_out_queue",
        ),
    ],
    random_specs=[],
    notes=(
        "auto_fight 是三触发的统一入口，由 attack.c init() 调用。"
        "它不直接启动战斗，而是通过 call_out 延迟执行 start_hatred/start_vendetta/"
        "start_aggressive。延迟给受害者一个'溜走'的机会（在 call_out 执行前离开房间）。\n"
        "start_<type> 函数会再次检查 is_fighting/living/同房间/no_fight 等条件，"
        "确保战斗启动时条件仍然满足。start_hatred 有随机追猎消息（按 race 分类），"
        "start_berserk 有 neili 概率判定（非三触发之一，但共用 auto_fight 机制）。"
    ),
)


_start_hatred = FunctionSpec(
    signature=FunctionSignature(
        name="start_hatred",
        params=[
            LPCParam(name="me", lpc_type="object", description="发起攻击的 NPC"),
            LPCParam(name="obj", lpc_type="object", description="被攻击的目标"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(904, 926),
    ),
    preconditions=[
        Precondition(
            description="me 和 obj 仍然存在（未被 destruct）",
            lpc_expr="me && obj",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="条件不满足时（已战斗/非 living/不同房间/no_fight）直接返回",
            kind="ensure",
        ),
        Postcondition(
            description="条件满足时 me->kill_ob(obj) 启动杀戮战斗",
            state_change="me->kill_ob(obj)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="四重守卫：is_fighting/living/同房间/no_fight 任一不满足则返回",
            lpc_expr="!is_fighting(obj) && living(me) && environment(me)==environment(obj) && !environment(me)->query('no_fight')",
            scope="function",
        ),
        Invariant(
            description="looking_for_trouble 标记在进入时清除",
            lpc_expr='me->set_temp("looking_for_trouble", 0)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清除 looking_for_trouble 防重入标记",
            lpc_call='me->set_temp("looking_for_trouble", 0)',
            target="me.temp.looking_for_trouble",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="按 race 输出随机追猎消息（人类/野兽/飞禽各有独立消息列表）",
            lpc_call="message_vision(catch_hunt_<race>_msg[random(...)], me, obj)",
            target="room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="me->kill_ob(obj) 启动杀戮战斗（加入 killer+enemy 列表）",
            lpc_call="me->kill_ob(obj)",
            target="combat_system",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(sizeof(catch_hunt_human_msg))",
            probability_model="1/sizeof(catch_hunt_human_msg) 均匀分布选择追猎消息",
            semantic="从种族对应的追猎消息列表中随机选择一条",
            seed_inputs=["catch_hunt_msg"],
            determinism_note="NPC AI 随机性，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes="start_hatred 是 hatred 触发的实际战斗启动函数，由 auto_fight 经 call_out 延迟调用。",
)


_start_vendetta = FunctionSpec(
    signature=FunctionSignature(
        name="start_vendetta",
        params=[
            LPCParam(name="me", lpc_type="object", description="发起攻击的 NPC"),
            LPCParam(name="obj", lpc_type="object", description="被攻击的目标"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(928, 944),
    ),
    preconditions=[
        Precondition(
            description="me 和 obj 仍然存在",
            lpc_expr="me && obj",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="条件不满足时直接返回",
            kind="ensure",
        ),
        Postcondition(
            description="条件满足时 me->kill_ob(obj) 启动杀戮战斗",
            state_change="me->kill_ob(obj)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="四重守卫：is_fighting/living/同房间/no_fight",
            lpc_expr="!is_fighting(obj) && living(me) && environment(me)==environment(obj) && !environment(me)->query('no_fight')",
            scope="function",
        ),
        Invariant(
            description="looking_for_trouble 标记在进入时清除",
            lpc_expr='me->set_temp("looking_for_trouble", 0)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清除 looking_for_trouble 防重入标记",
            lpc_call='me->set_temp("looking_for_trouble", 0)',
            target="me.temp.looking_for_trouble",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="me->kill_ob(obj) 启动杀戮战斗（无追猎消息）",
            lpc_call="me->kill_ob(obj)",
            target="combat_system",
        ),
    ],
    random_specs=[],
    notes="start_vendetta 是 vendetta 触发的实际战斗启动函数。与 hatred 不同，不输出追猎消息。",
)


_start_aggressive = FunctionSpec(
    signature=FunctionSignature(
        name="start_aggressive",
        params=[
            LPCParam(name="me", lpc_type="object", description="发起攻击的 NPC"),
            LPCParam(name="obj", lpc_type="object", description="被攻击的目标"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(946, 962),
    ),
    preconditions=[
        Precondition(
            description="me 和 obj 仍然存在",
            lpc_expr="me && obj",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="条件不满足时直接返回",
            kind="ensure",
        ),
        Postcondition(
            description="条件满足时 me->kill_ob(obj) 启动杀戮战斗",
            state_change="me->kill_ob(obj)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="四重守卫：is_fighting/living/同房间/no_fight",
            lpc_expr="!is_fighting(obj) && living(me) && environment(me)==environment(obj) && !environment(me)->query('no_fight')",
            scope="function",
        ),
        Invariant(
            description="looking_for_trouble 标记在进入时清除",
            lpc_expr='me->set_temp("looking_for_trouble", 0)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清除 looking_for_trouble 防重入标记",
            lpc_call='me->set_temp("looking_for_trouble", 0)',
            target="me.temp.looking_for_trouble",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="me->kill_ob(obj) 启动杀戮战斗（无追猎消息）",
            lpc_call="me->kill_ob(obj)",
            target="combat_system",
        ),
    ],
    random_specs=[],
    notes=(
        "start_aggressive 是 aggressive 触发的实际战斗启动函数。"
        "与 hatred/vendetta 不同，aggressive 触发不输出追猎消息，直接 kill_ob。\n"
        "注意：LPC 源码中 aggressive 触发不涉及概率判定（init 中 attitude=='aggressive' "
        "即触发）。概率性在于 call_out 延迟——受害者可在 start_aggressive 执行前离开房间。"
    ),
)


_select_opponent = FunctionSpec(
    signature=FunctionSignature(
        name="select_opponent",
        params=[],
        return_type="object",
        lpc_file="feature/attack.c",
        line_range=(79, 88),
    ),
    preconditions=[
        Precondition(
            description="enemy 数组已初始化（可能为空）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="enemy 为空时返回 0",
            return_value="0=无敌人",
            kind="ensure",
        ),
        Postcondition(
            description="enemy 非空时返回随机选中的敌人对象",
            return_value="object=选中的敌人",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="选中范围限于 MAX_OPPONENT(4) 以内的敌人",
            lpc_expr="which = random(MAX_OPPONENT); which < sizeof(enemy) ? enemy[which] : enemy[0]",
            scope="function",
        ),
        Invariant(
            description="enemy 数量 > MAX_OPPONENT 时只从前 4 个中选；否则从全部中选",
            lpc_expr="random(4) < sizeof(enemy) ? enemy[random(4)] : enemy[0]",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="random(MAX_OPPONENT) 随机选择敌人索引",
            lpc_call="which = random(MAX_OPPONENT)",
            target="enemy_list",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(MAX_OPPONENT)",
            probability_model="1/min(MAX_OPPONENT, sizeof(enemy)) 均匀分布选择敌人",
            semantic="从最多 MAX_OPPONENT(4) 个敌人中随机选择一个攻击目标",
            seed_inputs=["enemy_list"],
            determinism_note="select_opponent 的随机性在 combat 范围内，层 E 需要确定性 RNG",
        ),
    ],
    notes=(
        "select_opponent 由 attack() 调用（heart_beat 步骤 5），"
        "用于从 enemy 列表中随机选择当前 tick 的攻击目标。\n"
        "MAX_OPPONENT=4 限制同时攻击的目标数量，是 LPC combat 的设计约束。\n"
        "确定性 RNG 注：此随机性属 combat 范围，层 E 实现时需要 seeded RNG。"
    ),
)


_clean_up_enemy = FunctionSpec(
    signature=FunctionSignature(
        name="clean_up_enemy",
        params=[],
        return_type="void",
        lpc_file="feature/attack.c",
        line_range=(64, 75),
    ),
    preconditions=[
        Precondition(
            description="enemy 数组已初始化",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="enemy 数组中无效的敌人已清除（设为 0 后移除）",
            state_change="enemy -= ({ 0 })",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="清除条件：对象不存在 / 不在同一房间 / 非living且非killing",
            lpc_expr="!objectp(enemy[i]) || environment(enemy[i])!=environment() || (!living(enemy[i]) && !is_killing(enemy[i]->query('id')))",
            scope="function",
        ),
        Invariant(
            description="killing 关系的敌人即使非 living 也不清除（继续追杀）",
            lpc_expr="is_killing(enemy[i]->query('id')) => 不清除（即使 !living）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="遍历 enemy 数组，无效敌人设为 0",
            lpc_call="enemy[i] = 0（无效时）",
            target="enemy_list",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="移除 enemy 数组中的 0 元素",
            lpc_call="enemy -= ({ 0 })",
            target="enemy_list",
        ),
    ],
    random_specs=[],
    notes=(
        "clean_up_enemy 由 attack() 在 select_opponent 之前调用，"
        "清理无效的敌人引用（已离开/已死亡/已 destruct 的敌人）。\n"
        "killing 关系的敌人是持久追杀目标，即使对方非 living 也不清除。"
    ),
)


# ---------------------------------------------------------------------------
# 层 G 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="G",
    layer_name="NPC AI",
    lpc_files=[
        "inherit/char/char.c",
        "inherit/char/npc.c",
        "feature/attack.c",
        "adm/daemons/combatd.c",
    ],
    function_specs=[
        _heart_beat,
        _setup,
        _chat,
        _random_move,
        _return_home,
        _init_attack,
        _auto_fight,
        _start_hatred,
        _start_vendetta,
        _start_aggressive,
        _select_opponent,
        _clean_up_enemy,
    ],
    cross_layer_refs=[
        "attack / fight_ob / kill_ob (层 E: combat)",  # heart_beat 步骤 5 调 attack
        "COMBAT_D->fight (层 E: combat)",  # attack() 内部调 COMBAT_D->fight
        "die / unconcious (层 F: 死亡轮回)",  # heart_beat 步骤 3/4
        "heal_up (层 F/D: damage.c)",  # heart_beat 步骤 7 自愈
        "update_condition (层 F: condition.c)",  # heart_beat 步骤 7 条件更新
        "continue_action / is_busy / start_busy (层 B/E: action.c)",  # heart_beat 步骤 5
        "GO_CMD->do_flee / GO_CMD->main (层 D: go.c)",  # heart_beat wimpy + random_move
        "valid_leave (层 D: room.c)",  # random_move 经 go 调 valid_leave
        "move (层 B: F_MOVE)",  # return_home 调 move
        "message / tell_room / say (层 B: F_MESSAGE)",  # 各处消息输出
        "receive_message (层 B: F_MESSAGE)",  # chat 的 say 消息
        "command (层 C: command_hook)",  # random_move 调 command('go '+dir)
        "set_heart_beat (层 A: driver)",  # setup/heart_beat 心跳控制
        "enable_player (层 C: command)",  # setup 调 enable_player
        "CHAR_D->setup_char (层 H: 核心守护进程)",  # setup 调属性计算
        "SKILL_D->exert_function (层 E: 技能系统)",  # chat 自动恢复
        "CHANNEL_D->do_channel (层 H: 频道系统)",  # heart_beat 频道清理
        "RANK_D->query_self_rude / query_rude (层 H)",  # start_berserk 称谓（非三触发但共用机制）
    ],
    notes=(
        "层 G 覆盖 NPC AI 的核心循环（heart_beat 七步管线）+ 自动行为（chat/random_move）"
        "+ 战斗触发（init/auto_fight 三触发）+ 敌人管理（select_opponent/clean_up_enemy）。\n"
        "heart_beat 七步管线是 NPC AI 的核心契约：\n"
        "  (1) 玩家频道清理（仅 userp）\n"
        "  (2) 属性上限检查（neili/jingli/jing 封顶 max*2）\n"
        "  (3) 濒死检查（eff_qi/eff_jing<0 -> die）\n"
        "  (4) 昏迷/死亡检查（qi/jing/jingli<0 -> unconcious/die）\n"
        "  (5) 战斗行动（busy -> continue_action; 否则 wimpy+attack）\n"
        "  (6) NPC chat（自动恢复 + 随机对话 + 可能 destruct）\n"
        "  (7) tick 衰减条件更新 + 自愈 + 空闲心跳关闭\n"
        "\n"
        "auto_fight 三触发条件：\n"
        "  - hatred: is_killing(ob->query('id')) -- 仇恨列表匹配\n"
        "  - vendetta: vendetta_mark + ob->query('vendetta/'+mark) -- 仇杀标记匹配\n"
        "  - aggressive: attitude=='aggressive' -- 主动攻击\n"
        "三触发经 call_out 延迟 0 tick 执行 start_<type>，给受害者溜走机会。\n"
        "\n"
        "派生变更审计（dissent 7）：所有副作用已按交织顺序记录在 SideEffect.order 中。\n"
        "边界：do_attack/attack/fight 属层 E（仅提取 init/auto_fight 触发入口）；"
        "NPC reset 生成属层 D（make_inventory/reset）；"
        "unique.c/trainee.c/任务 NPC 专属 AI 后置；"
        "玩家 heart_beat 细节属层 I。"
    ),
)
