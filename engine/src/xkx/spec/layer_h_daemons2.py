"""层 H-2：第二梯队守护进程 -- LPC 规格提取（ADR-0055）。

覆盖范围：
- ``adm/daemons/channeld.c`` -- CHANNEL_D：多频道消息分发、emote 支持、反刷屏
- ``adm/daemons/moneyd.c`` -- MONEY_D：三层货币（金/银/铜）、支付、现金流上限
- ``adm/daemons/updated.c`` -- UPDATE_D：登录数据归一化、反作弊物品检查
- ``adm/daemons/aliasd.c`` -- ALIAS_D：全局命令别名/方向快捷输入

核心契约要点：
1. **CHANNEL_D 频道配置驱动**：``channels`` 映射定义每个频道的格式字符串、权限
   （wiz_only / menpai_only / anonymous / intermud / filter / omit_address），
   ``do_channel`` 的行为完全由配置决定，不硬编码频道名语义。
2. **频道阻塞单向展开**：``chblk_on`` 被展开为 ``chblk_rumor`` / ``chblk_chat`` /
   ``chblk_gchat`` / ``chblk_menpai``，与 ``BLOCK_CHAT`` / ``BLOCK_RUMOR`` 编译期
   开关共同生效。
3. **MONEY_D 货币换算不变量**：``1 gold = 100 silver = 10000 coin``，所有金额函数
   以 coin 为最小单位运算；``MAX_CASHFLOW_ALLOWED = 400000``（silver 单位）是全局
   系统现金流硬上限。
4. **UPDATE_D 登录归一化**：为缺失字段填充默认值，按 ``combat_exp`` 反推并封顶
   非知识类技能等级，按门派给新手着装，最后调用 ``inventory_check``。
5. **UPDATE_D 反作弊**：低经验玩家携带 >50 黄金有概率被扒手扣减；唯一物品被
   destruct；背包 >30 件随机丢一件。所有惩罚均带 ``random()``。
6. **ALIAS_D 纯输入侧转换**：``process_global_alias`` 仅做字符串替换，不产生任何
   对象/状态副作用；``'`` 前缀展开为 ``say`` 与全局别名在同一代码路径处理。

不做（边界）：
- EMOTE_D / INQUIRY_D 内部实现细节（本层只记录 CHANNEL_D 对其调用点）。
- InterMUD 网络协议细节（gwiz/gchat 的 intermud 发送只记录接口契约）。
- 玩家自定义别名（``F_ALIAS`` / alias.c 的 ``set_alias``，后置）。
- 具体货币对象（gold_money / silver_money / coin_money）的内部方法（属层 B 物品）。
- 银行/任务/商人系统对 MONEY_D 的调用上游（只记录 MONEY_D 自身契约）。
- ``updated.c`` 中门派服装的 hardcoded 路径只作为示例，不做全量枚举。
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
# 领域常量
# ---------------------------------------------------------------------------

#: MONEY_D 三层货币换算（以 coin 为最小单位）。
CURRENCY_RATES: dict[str, int] = {
    "gold": 10000,
    "silver": 100,
    "coin": 1,
}

#: MONEY_D 全局现金流上限（silver 单位）。
MAX_CASHFLOW_ALLOWED: int = 400000

#: CHANNEL_D 内置频道清单（来自 channeld.c:18-52）。
BUILTIN_CHANNELS: list[str] = [
    "sys",
    "wiz",
    "chat",
    "rumor",
    "menpai",
    "gwiz",
    "gchat",
]

#: ALIAS_D 全局方向与常用别名（来自 aliasd.c:6-30）。
GLOBAL_ALIASES: dict[str, str] = {
    "l": "look",
    "n": "go north",
    "e": "go east",
    "w": "go west",
    "s": "go south",
    "nu": "go northup",
    "eu": "go eastup",
    "wu": "go westup",
    "su": "go southup",
    "nd": "go northdown",
    "ed": "go eastdown",
    "wd": "go westdown",
    "sd": "go southdown",
    "ne": "go northeast",
    "se": "go southeast",
    "nw": "go northwest",
    "sw": "go southwest",
    "u": "go up",
    "d": "go down",
    "i": "inventory",
    "tf": "team fight",
    "tt": "team talk",
    "tt*": "team talk*",
}

# ---------------------------------------------------------------------------
# 层 H-2 特定模型
# ---------------------------------------------------------------------------


class ChannelProp(StrEnum):
    """CHANNEL_D 频道配置字段。"""

    MSG_SPEAK = "msg_speak"
    MSG_EMOTE = "msg_emote"
    WIZ_ONLY = "wiz_only"
    MENPAI_ONLY = "menpai_only"
    ANONYMOUS = "anonymous"
    INTERMUD = "intermud"
    FILTER = "filter"
    OMIT_ADDRESS = "omit_address"
    INTERMUD_EMOTE = "intermud_emote"
    CHANNEL = "channel"
    EXTRA_LISTENER = "extra_listener"


class PayResult(StrEnum):
    """MONEY_D 支付函数返回值语义。"""

    SUCCESS = "1"
    """支付成功。"""

    INSUFFICIENT = "0"
    """余额不足。"""

    THOUSAND_CASH = "2"
    """余额不足但持有银票（thousand-cash），由调用方特殊处理。"""


# ---------------------------------------------------------------------------
# CHANNEL_D 规格
# ---------------------------------------------------------------------------

_do_channel = FunctionSpec(
    signature=FunctionSignature(
        name="do_channel",
        params=[
            LPCParam(name="me", lpc_type="object", description="发言者对象"),
            LPCParam(name="verb", lpc_type="string", description="频道名/命令动词"),
            LPCParam(name="arg", lpc_type="string", description="发言内容或 emote 参数"),
            LPCParam(
                name="emote", lpc_type="int", description="是否为 emote 形式", is_varargs_tail=True
            ),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="adm/daemons/channeld.c",
        line_range=(60, 225),
    ),
    preconditions=[
        Precondition(
            description="me 为非空对象",
            kind="require",
        ),
        Precondition(
            description="verb 为字符串且长度 >0",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="频道存在且检查通过时返回 1，消息已广播",
            kind="ensure",
        ),
        Postcondition(
            description="频道不存在或权限不足或被阻塞时返回 0 或 notify_fail",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="频道配置是行为的唯一来源，不硬编码频道语义",
            scope="system",
        ),
        Invariant(
            description="用户发言重复检测基于 last_channel_msg，刷屏计数基于 channel_msg_cnt",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若 verb 以 '*' 结尾则置 emote=1 并去掉尾星",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="检查 channels 映射，不存在则静默返回 0",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="arg 为空或空格时规范化为 '...'",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="chblk_on 展开为 chblk_rumor/chat/gchat/menpai",
            target="me",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="非巫师用户在 rumor 频道消耗 50 jingli",
            target="me",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="menpai_only 频道要求玩家有门派",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="按 verb 检查 chblk_* 与 BLOCK_CHAT/BLOCK_RUMOR 阻塞",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_channel_msg，增加 channel_msg_cnt",
            target="me",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="将 verb 加入 me->channels 列表（若未在列表中）",
            target="me",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="emote 模式下调用 EMOTE_D->do_emote 生成展示字符串",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="构造 speaker 身份字符串（anonymous 频道用匿名代词）",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.STATE_MUTATION,
            description="filter_listener 过滤在线用户得到接收者列表 ob",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="message() 向 ob 广播频道消息",
        ),
        SideEffect(
            order=14,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="extra_listener->relay_channel 转发给注册监听者",
        ),
        SideEffect(
            order=15,
            kind=SideEffectType.EXTERNAL,
            description="intermud 频道调用 send_msg 发送跨 MUD 消息",
        ),
    ],
    random_specs=[],
    notes=(
        "channeld.c 的 channels 映射是配置驱动核心；新增频道只需扩展该映射。"
        "gwiz/gchat 的 intermud 发送属于外部网络副作用，新引擎实现中如砍掉 "
        "intermud（ADR 决策），则相应配置字段视为预留。"
    ),
)

_filter_listener = FunctionSpec(
    signature=FunctionSignature(
        name="filter_listener",
        params=[
            LPCParam(name="ppl", lpc_type="object", description="待判断的在线用户"),
            LPCParam(name="ch", lpc_type="mapping", description="频道配置映射"),
        ],
        return_type="int",
        lpc_file="adm/daemons/channeld.c",
        line_range=(227, 237),
    ),
    preconditions=[
        Precondition(description="ppl 为在线对象", kind="require"),
        Precondition(description="ch 为频道配置映射", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示 ppl 应收听该频道，0 表示不应收听",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="无 environment(ppl) 的对象（登录中）被排除",
            scope="function",
        ),
        Invariant(
            description="wiz_only 频道只对巫师返回 1",
            scope="function",
        ),
        Invariant(
            description="menpai_only 频道只对同门派或巫师返回 1",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="无对象状态副作用，纯过滤函数。",
)

_register_relay_channel = FunctionSpec(
    signature=FunctionSignature(
        name="register_relay_channel",
        params=[
            LPCParam(name="channel", lpc_type="string", description="频道名"),
        ],
        return_type="void",
        lpc_file="adm/daemons/channeld.c",
        line_range=(239, 250),
    ),
    preconditions=[
        Precondition(description="channel 在 channels 映射中存在", kind="guard"),
        Precondition(description="previous_object() 非空", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="previous_object() 被加入 channels[channel]['extra_listener']",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="同一对象重复注册不添加重复项",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="将 previous_object() 加入频道 extra_listener 数组",
            target="channels[channel]['extra_listener']",
        ),
    ],
    random_specs=[],
    notes="用于外部系统（如机器人、日志）监听频道。",
)

_remove_addresses = FunctionSpec(
    signature=FunctionSignature(
        name="remove_addresses",
        params=[
            LPCParam(name="msg", lpc_type="string", description="原始消息字符串"),
            LPCParam(
                name="all", lpc_type="int", description="1=移除所有 @mud 地址，0=只移当前 MUD"
            ),
        ],
        return_type="string",
        lpc_file="adm/daemons/channeld.c",
        line_range=(252, 274),
    ),
    preconditions=[
        Precondition(description="msg 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回过滤掉 (Name@Mud) 地址后的字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="all=0 时只匹配 INTERMUD_MUD_NAME 后缀的地址",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="用于 emote 消息中隐藏跨 MUD 地址或统一地址格式。",
)

# ---------------------------------------------------------------------------
# MONEY_D 规格
# ---------------------------------------------------------------------------

_money_str = FunctionSpec(
    signature=FunctionSignature(
        name="money_str",
        params=[
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="string",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(30, 48),
    ),
    preconditions=[
        Precondition(description="amount 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回中文金额字符串，按 gold/silver/coin 从大到小拼接",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="1 gold = 100 silver = 10000 coin",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="用于显示，不保证金额 >=0。",
)

_price_str = FunctionSpec(
    signature=FunctionSignature(
        name="price_str",
        params=[
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="string",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(50, 77),
    ),
    preconditions=[
        Precondition(description="amount 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回中文价格字符串；amount<1 时按 1 处理；多币种时用 '又' 连接",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="1 gold = 100 silver = 10000 coin",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="与 money_str 类似，但价格展示用 '又' 连接。",
)

_pay_player = FunctionSpec(
    signature=FunctionSignature(
        name="pay_player",
        params=[
            LPCParam(name="who", lpc_type="object", description="收款对象"),
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="void",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(79, 104),
    ),
    preconditions=[
        Precondition(description="who 为有效对象", kind="require"),
        Precondition(description="amount >=1，否则按 1 处理", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="who 的 inventory 中新增/叠加 gold/silver/coin 对象，总额为 amount",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="优先生成高面值货币，剩余部分生成低面值",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="按 amount 生成 GOLD_OB 并 move 到 who",
            target="who",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="剩余金额生成 SILVER_OB 并 move 到 who",
            target="who",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="最后剩余生成 COIN_OB 并 move 到 who",
            target="who",
        ),
    ],
    random_specs=[],
    notes="会调用 seteuid(getuid()) 以获取创建对象权限。",
)

_player_pay = FunctionSpec(
    signature=FunctionSignature(
        name="player_pay",
        params=[
            LPCParam(name="who", lpc_type="object", description="付款对象"),
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(106, 158),
    ),
    preconditions=[
        Precondition(description="who 为有效对象", kind="require"),
        Precondition(description="amount >=0", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="余额充足时返回 1，who 的货币对象金额被扣减",
            kind="ensure",
        ),
        Postcondition(
            description="余额不足时返回 0；若持有 thousand-cash 则返回 2",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="扣减后货币总额 = 原总额 - amount",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="计算 who 身上 gold/silver/coin 总额",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="余额不足且存在 thousand-cash 时返回 2，无状态变更",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="余额充足时更新 gold/silver/coin 对象金额，必要时创建新对象",
            target="who",
        ),
    ],
    random_specs=[],
    notes="thousand-cash（银票）作为特殊支付方式，由调用方处理返回 2 的情况。",
)

_player_dealer_pay = FunctionSpec(
    signature=FunctionSignature(
        name="player_dealer_pay",
        params=[
            LPCParam(name="who", lpc_type="object", description="收款对象"),
            LPCParam(name="from", lpc_type="object", description="付款来源 NPC/商人"),
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(166, 180),
    ),
    preconditions=[
        Precondition(description="amount <= query_avalible_xkx_cashflow() 时才支付", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="现金流允许时返回 1 并调用 pay_player；否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="商人支付受全局现金流上限约束",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查可用现金流",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="允许时调用 pay_player(who, amount)",
            target="who",
        ),
    ],
    random_specs=[],
    notes="用于 vendor 收购玩家物品，防止系统无限印钞。",
)

_player_bank_pay = FunctionSpec(
    signature=FunctionSignature(
        name="player_bank_pay",
        params=[
            LPCParam(name="who", lpc_type="object", description="收款对象"),
            LPCParam(name="from", lpc_type="object", description="付款来源 NPC/银行"),
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(183, 197),
    ),
    preconditions=[
        Precondition(description="amount <= query_avalible_xkx_cashflow() 时才支付", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="现金流允许时返回 1 并调用 pay_player；否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="银行支付受全局现金流上限约束",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查可用现金流",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="允许时调用 pay_player(who, amount)",
            target="who",
        ),
    ],
    random_specs=[],
    notes="用于银行取款。",
)

_player_job_pay = FunctionSpec(
    signature=FunctionSignature(
        name="player_job_pay",
        params=[
            LPCParam(name="who", lpc_type="object", description="收款对象"),
            LPCParam(name="from", lpc_type="object", description="付款来源 NPC/任务"),
            LPCParam(name="amount", lpc_type="int", description="以 coin 为单位的金额"),
        ],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(200, 214),
    ),
    preconditions=[
        Precondition(description="amount <= query_avalible_xkx_cashflow() 时才支付", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="现金流允许时返回 1 并调用 pay_player；否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="任务奖励受全局现金流上限约束",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查可用现金流",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="允许时调用 pay_player(who, amount)",
            target="who",
        ),
    ],
    random_specs=[],
    notes="用于任务奖励发放。",
)

_query_avalible_xkx_cashflow = FunctionSpec(
    signature=FunctionSignature(
        name="query_avalible_xkx_cashflow",
        params=[],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(217, 227),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 MAX_CASHFLOW_ALLOWED - 当前总现金流；为负时返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="返回值 >=0",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="无状态副作用，只读计算。",
)

_query_total_xkx_cashflow = FunctionSpec(
    signature=FunctionSignature(
        name="query_total_xkx_cashflow",
        params=[],
        return_type="int",
        lpc_file="adm/daemons/moneyd.c",
        line_range=(230, 253),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回以 silver 为单位的当前全系统现金流总量",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="gold 按 100 silver 换算，coin 按 1/100 silver 换算",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="遍历 children(GOLD_OB/SILVER_OB/COIN_OB) 求和，性能开销大。",
)

# ---------------------------------------------------------------------------
# UPDATE_D 规格
# ---------------------------------------------------------------------------

_login_check = FunctionSpec(
    signature=FunctionSignature(
        name="login_check",
        params=[
            LPCParam(name="ob", lpc_type="object", description="待归一化的玩家对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/updated.c",
        line_range=(10, 132),
    ),
    preconditions=[
        Precondition(description="ob 为有效玩家对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="ob 的关键字段被填充默认值或修正到合法范围",
            kind="effect",
        ),
        Postcondition(
            description="非知识类技能等级按 combat_exp 公式封顶",
            kind="effect",
        ),
        Postcondition(
            description="最后调用 inventory_check(ob)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="balance 上限 10000000；低经验玩家 balance 上限 100000",
            scope="function",
        ),
        Invariant(
            description="combat_exp <0 时归 0；shen 绝对值不超过 combat_exp",
            scope="function",
        ),
        Invariant(
            description="potential 不超过 max_potential",
            scope="function",
        ),
        Invariant(
            description="death_count >= death_times",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="为缺失字段填充默认值：balance/combat_exp/mud_age/food/water/shen/age 等",
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="balance 按经验等级封顶",
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="新玩家 food/water 设为最大容量",
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="非知识类技能按 pow(level,3)/10 <= combat_exp 反推封顶",
            target="ob",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 rided 标记",
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="填充 behavior_exp/quest_exp/potential/max_potential 等",
            target="ob",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="按门派与 class 创建并穿着默认服装",
            target="ob",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 inventory_check(ob)",
            target="ob",
        ),
    ],
    random_specs=[],
    notes="只应在 LOGIN_D enter_world 时调用，避免运行时反复覆盖玩家数据。",
)

_inventory_check = FunctionSpec(
    signature=FunctionSignature(
        name="inventory_check",
        params=[
            LPCParam(name="ob", lpc_type="object", description="待检查的玩家对象"),
        ],
        return_type="int",
        lpc_file="adm/daemons/updated.c",
        line_range=(135, 170),
    ),
    preconditions=[
        Precondition(description="ob 为 interactive 玩家对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="发现违规时返回 1 并执行一项惩罚；无违规返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="每次调用最多执行一种惩罚并立即 return",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="低经验玩家携带 >50 黄金时随机扣除 1+random(amt/2) 黄金",
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="发现 unique 物品时 destruct 该物品并广播谣言",
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="背包 >30 件时随机丢弃一件",
            target="ob",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(amt/2)",
            probability_model="uniform [0, amt/2-1]",
            semantic="低经验玩家黄金被盗数量",
            seed_inputs=["amt"],
            determinism_note="非战斗随机性，登录时反作弊扰动",
        ),
        RandomSpec(
            lpc_call="random(10)",
            probability_model="uniform [0, 9]",
            semantic="unique 物品谣言广播 call_out 延迟",
            seed_inputs=["i"],
            determinism_note="非战斗随机性",
        ),
        RandomSpec(
            lpc_call="random(sizeof(inv))",
            probability_model="uniform [0, sizeof(inv)-1]",
            semantic="背包超限时随机丢弃物品索引",
            seed_inputs=["inv"],
            determinism_note="非战斗随机性",
        ),
    ],
    notes="三种惩罚互斥，命中其一即 return。",
)

# ---------------------------------------------------------------------------
# ALIAS_D 规格
# ---------------------------------------------------------------------------

_get_current_alias = FunctionSpec(
    signature=FunctionSignature(
        name="get_current_alias",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/aliasd.c",
        line_range=(32, 37),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回当前待处理命令字符串，带玩家 ID 与环境前缀（若可获取）",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="无对象状态副作用，仅读取 current_alias 与 this_player(1)",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="调试用，无状态副作用。",
)

_process_global_alias = FunctionSpec(
    signature=FunctionSignature(
        name="process_global_alias",
        params=[
            LPCParam(name="arg", lpc_type="string", description="玩家原始输入"),
        ],
        return_type="string",
        lpc_file="adm/daemons/aliasd.c",
        line_range=(39, 54),
    ),
    preconditions=[
        Precondition(description="arg 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="命中全局别名时返回展开后的字符串；否则返回原字符串",
            kind="ensure",
        ),
        Postcondition(
            description="以 ' 开头时返回 'say ' + arg[1..]",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只替换第一个单词，保留后续参数",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="更新模块级 current_alias 变量（调试用）",
        ),
    ],
    random_specs=[],
    notes="纯字符串转换；'say' 前缀展开与全局别名在同一代码路径。",
)

# ---------------------------------------------------------------------------
# FINGER_D 规格
# ---------------------------------------------------------------------------

_finger_ip_cmp = FunctionSpec(
    signature=FunctionSignature(
        name="ip_cmp",
        params=[
            LPCParam(name="s1", lpc_type="string", description="IP 或主机名 1"),
            LPCParam(name="s2", lpc_type="string", description="IP 或主机名 2"),
        ],
        return_type="int",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(8, 21),
    ),
    preconditions=[
        Precondition(description="s1/s2 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 strcmp 比较结果，非数字开头字符串会先反转",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="仅当首字符非数字时进行字符串反转",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="用于 sort_array 在线用户按 IP/主机名排序。",
)

_finger_age_string = FunctionSpec(
    signature=FunctionSignature(
        name="age_string",
        params=[
            LPCParam(name="time", lpc_type="int", description="以秒为单位的时间"),
        ],
        return_type="string",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(23, 37),
    ),
    preconditions=[
        Precondition(description="time 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 mud_age 的中文时长字符串（月/日/时/分）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="1 月 = 30 天，1 天 = 24 小时",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯格式化函数。",
)

_finger_all = FunctionSpec(
    signature=FunctionSignature(
        name="finger_all",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(39, 77),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回格式化后的在线用户列表字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="巫师视图显示 IP/年龄，普通玩家视图隐藏",
            scope="function",
        ),
        Invariant(
            description="不可见对象（visible 返回 0）被跳过",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="只读聚合 users()，无状态副作用。",
)

_finger_user = FunctionSpec(
    signature=FunctionSignature(
        name="finger_user",
        params=[
            LPCParam(name="name", lpc_type="string", description="玩家英文 ID 或 name@mud"),
        ],
        return_type="string",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(79, 146),
    ),
    preconditions=[
        Precondition(description="name 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="本地玩家存在时返回详细信息字符串",
            kind="ensure",
        ),
        Postcondition(
            description="跨 MUD 查询时返回等待提示字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="普通玩家只能看到设置了 env/public 的邮箱",
            scope="function",
        ),
        Invariant(
            description="巫师视图显示 last_from 与完整邮箱",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="创建临时 LOGIN_OB 并 restore",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="离线查询时创建 body、restore、destruct",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="最后 destruct 临时 LOGIN_OB",
        ),
    ],
    random_specs=[],
    notes="涉及临时对象创建与销毁；跨 MUD 分支依赖 GFINGER_Q。",
)

_finger_remote_finger_user = FunctionSpec(
    signature=FunctionSignature(
        name="remote_finger_user",
        params=[
            LPCParam(name="name", lpc_type="string", description="玩家英文 ID"),
            LPCParam(
                name="chinese_flag",
                lpc_type="int",
                description="1=返回中文，0=返回英文",
                is_varargs_tail=True,
            ),
        ],
        return_type="string",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(148, 184),
    ),
    preconditions=[
        Precondition(description="name 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回中文或英文的玩家信息字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="中文与英文模板字段一致",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="创建临时 LOGIN_OB 并 restore",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="最后 destruct 临时 LOGIN_OB",
        ),
    ],
    random_specs=[],
    notes="处理来自其它 MUD 的 finger 查询响应。",
)

_finger_acquire_login_ob = FunctionSpec(
    signature=FunctionSignature(
        name="acquire_login_ob",
        params=[
            LPCParam(name="id", lpc_type="string", description="玩家英文 ID"),
        ],
        return_type="object",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(186, 198),
    ),
    preconditions=[
        Precondition(description="id 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="玩家在线且 link_ob 存在时返回 link_ob",
            kind="ensure",
        ),
        Postcondition(
            description="否则创建 LOGIN_OB 并 restore 后返回，失败返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="返回对象 either 是 link_ob，either 是 restore 成功的 LOGIN_OB，要么为 0",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="可能创建新的 LOGIN_OB",
        ),
    ],
    random_specs=[],
    notes="用于获取玩家的登录对象以读取存档。",
)

_finger_get_killer = FunctionSpec(
    signature=FunctionSignature(
        name="get_killer",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/fingerd.c",
        line_range=(200, 223),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回带 killer condition 的玩家列表字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只查询 users() 中对象的 query_condition('killer')",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="法院/PK 通缉相关查询，只读。",
)

# ---------------------------------------------------------------------------
# BAN_D 规格
# ---------------------------------------------------------------------------

_ban_load_sites = FunctionSpec(
    signature=FunctionSignature(
        name="load_sites",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/band.c",
        line_range=(23, 40),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="Sites 数组被重新加载为 /adm/etc/banned_sites 中有效行",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="忽略空行、# 注释行、\n 行",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取配置文件并重置 Sites 数组",
        ),
    ],
    random_specs=[],
    notes="create() 时自动调用。",
)

_ban_is_banned = FunctionSpec(
    signature=FunctionSignature(
        name="is_banned",
        params=[
            LPCParam(name="site", lpc_type="string", description="待检查的 IP 或主机名"),
        ],
        return_type="int",
        lpc_file="adm/daemons/band.c",
        line_range=(42, 54),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="site 匹配 Sites 中任一正则时返回 1，否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="Sites 中每条作为 regexp 模式匹配",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="只读检查，无状态副作用。",
)

_ban_print = FunctionSpec(
    signature=FunctionSignature(
        name="print",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/band.c",
        line_range=(56, 61),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="向当前玩家输出 Sites 列表",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="输出顺序与 Sites 数组顺序一致",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 输出每条封禁规则",
        ),
    ],
    random_specs=[],
    notes="管理命令输出。",
)

_ban_add = FunctionSpec(
    signature=FunctionSignature(
        name="add",
        params=[
            LPCParam(name="site", lpc_type="string", description="要添加的封禁模式"),
        ],
        return_type="void",
        lpc_file="adm/daemons/band.c",
        line_range=(63, 70),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="site 被追加到 Sites 与配置文件",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="追加后 Sites 包含新 site",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="Sites += ({site})",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="write_file 追加到 /adm/etc/banned_sites",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="重新 load_sites",
        ),
    ],
    random_specs=[],
    notes="管理命令。",
)

_ban_remove = FunctionSpec(
    signature=FunctionSignature(
        name="remove",
        params=[
            LPCParam(name="site", lpc_type="string", description="要移除的封禁模式"),
        ],
        return_type="void",
        lpc_file="adm/daemons/band.c",
        line_range=(72, 80),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="Sites 中通过 strcmp 过滤掉 site 后写回配置文件",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="移除后 Sites 中不再包含与 site strcmp 相等的项",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="filter_array(Sites, (:strcmp:), site) 过滤",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="rm 配置文件",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="逐行写回 /adm/etc/banned_sites",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="重新 load_sites",
        ),
    ],
    random_specs=[],
    notes="管理命令。",
)

# ---------------------------------------------------------------------------
# REGBAN_D 规格
# ---------------------------------------------------------------------------

_regban_load_sites = FunctionSpec(
    signature=FunctionSignature(
        name="load_sites",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/regband.c",
        line_range=(25, 44),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="Sites 数组被重新加载为 /adm/etc/noreg_sites 中有效行",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="忽略空行、# 注释行、\n 行",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="读取配置文件并重置 Sites 数组",
        ),
    ],
    random_specs=[],
    notes="create() 时自动调用。",
)

_regban_is_banned = FunctionSpec(
    signature=FunctionSignature(
        name="is_banned",
        params=[
            LPCParam(name="site", lpc_type="string", description="待检查的 IP、主机名或邮箱"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regband.c",
        line_range=(46, 69),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="site 匹配 Sites 中任一正则时返回 1 并写日志，否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="site 含 @ 时只匹配同样含 @ 的规则",
            scope="function",
        ),
        Invariant(
            description="site 被 lower_case 后再匹配",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="写 /log/regban.log 记录 BANNED 或 PASS",
        ),
    ],
    random_specs=[],
    notes="注册时的 IP/邮箱封禁检查。",
)

_regban_print = FunctionSpec(
    signature=FunctionSignature(
        name="print",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/regband.c",
        line_range=(71, 78),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="向当前玩家输出注册封禁 Sites 列表",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="输出顺序与 Sites 数组顺序一致",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 输出每条封禁规则",
        ),
    ],
    random_specs=[],
    notes="管理命令输出。",
)

_regban_add = FunctionSpec(
    signature=FunctionSignature(
        name="add",
        params=[
            LPCParam(name="site", lpc_type="string", description="要添加的封禁模式"),
        ],
        return_type="void",
        lpc_file="adm/daemons/regband.c",
        line_range=(80, 88),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="site 被 lower_case 后追加到 Sites 与配置文件",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="追加后 Sites 包含小写后的 site",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="site 转小写",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="Sites += ({site})",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="write_file 追加到 /adm/etc/noreg_sites",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="重新 load_sites",
        ),
    ],
    random_specs=[],
    notes="管理命令。",
)

_regban_remove = FunctionSpec(
    signature=FunctionSignature(
        name="remove",
        params=[
            LPCParam(name="site", lpc_type="string", description="要移除的封禁模式"),
        ],
        return_type="void",
        lpc_file="adm/daemons/regband.c",
        line_range=(90, 98),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="Sites 中通过 strcmp 过滤掉 site 后写回配置文件",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="移除后 Sites 中不再包含与 site strcmp 相等的项",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="filter_array(Sites, (:strcmp:), site) 过滤",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="rm 配置文件",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="逐行写回 /adm/etc/noreg_sites",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="重新 load_sites",
        ),
    ],
    random_specs=[],
    notes="管理命令。",
)

_regban_check = FunctionSpec(
    signature=FunctionSignature(
        name="check",
        params=[
            LPCParam(name="site", lpc_type="string", description="待检查的 IP、主机名或邮箱"),
        ],
        return_type="void",
        lpc_file="adm/daemons/regband.c",
        line_range=(100, 125),
    ),
    preconditions=[
        Precondition(description="site 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="逐行输出检查过程与 BANNED/PASS 结果",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="site 先 lower_case 再参与匹配",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 输出待检查 site 与每条规则匹配情况",
        ),
    ],
    random_specs=[],
    notes="调试命令，逐条显示匹配过程。",
)

# ---------------------------------------------------------------------------
# REGI_D 规格
# ---------------------------------------------------------------------------

_regi_is_banned_email = FunctionSpec(
    signature=FunctionSignature(
        name="is_banned_email",
        params=[
            LPCParam(name="str", lpc_type="string", description="待检查的邮箱字符串"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regid.c",
        line_range=(21, 42),
    ),
    preconditions=[
        Precondition(description="str 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="不含 . 或 @ 返回 1；含 banned_string 或被 REGBAN_D 封禁返回 2；否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="邮箱先 lower_case 再检查",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯校验函数。",
)

_regi_random_password = FunctionSpec(
    signature=FunctionSignature(
        name="random_password",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/regid.c",
        line_range=(57, 62),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 5 个小写字母组成的随机密码",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="每个字符为 a-z",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[
        RandomSpec(
            lpc_call="random(26)",
            probability_model="uniform [0, 25]",
            semantic="密码每个字符的随机偏移",
            seed_inputs=[],
            determinism_note="非战斗随机性，注册密码生成",
        ),
    ],
    notes="生成随机注册密码。",
)

_regi_register_char = FunctionSpec(
    signature=FunctionSignature(
        name="register_char",
        params=[
            LPCParam(name="who", lpc_type="string", description="待注册玩家英文 ID"),
            LPCParam(name="where", lpc_type="string", description="电子邮箱地址"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regid.c",
        line_range=(64, 95),
    ),
    preconditions=[
        Precondition(description="who 对应的 LOGIN_OB 可 restore", kind="require"),
        Precondition(description="who 权限为 (player)", kind="guard"),
        Precondition(description="注册锁文件 /queue/register.lock 不存在", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="注册成功时返回 1，设置 email/password/registered",
            kind="effect",
        ),
        Postcondition(
            description="失败时返回 0 或 notify_fail",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="password 用 crypt(pass, 0) 存储",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="生成随机密码",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 LOGIN_OB 的 email / password / registered",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="save_data 写入 /queue/register",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="CHANNEL_D sys 广播注册完成",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="若玩家在线则通知新密码并设置 registered、save、destruct body",
            target="body",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="保存并 destruct LOGIN_OB",
        ),
    ],
    random_specs=[],
    notes="random_password 的 random 在副作用 1 中。",
)

_regi_change_password = FunctionSpec(
    signature=FunctionSignature(
        name="change_password",
        params=[
            LPCParam(name="who", lpc_type="string", description="玩家英文 ID"),
            LPCParam(name="what", lpc_type="string", description="新密码明文"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regid.c",
        line_range=(97, 111),
    ),
    preconditions=[
        Precondition(description="who 对应的 LOGIN_OB 可 restore", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 1 并保存新密码",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="新密码用 crypt(what, 0) 存储",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="定位或创建 LOGIN_OB 并 restore",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="设置 password 并 save",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 提示密码修改成功",
        ),
    ],
    random_specs=[],
    notes="巫师管理命令。",
)

_regi_change_name = FunctionSpec(
    signature=FunctionSignature(
        name="change_name",
        params=[
            LPCParam(name="who", lpc_type="string", description="玩家英文 ID"),
            LPCParam(name="what", lpc_type="string", description="新姓名"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regid.c",
        line_range=(113, 127),
    ),
    preconditions=[
        Precondition(description="who 对应的 LOGIN_OB 可 restore", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 1 并保存新姓名",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只修改 name 字段，不改动 id/password 等",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="定位或创建 LOGIN_OB 并 restore",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="设置 name 并 save",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write 提示姓名修改成功",
        ),
    ],
    random_specs=[],
    notes="巫师管理命令。",
)

_regi_change_id = FunctionSpec(
    signature=FunctionSignature(
        name="change_id",
        params=[
            LPCParam(name="who", lpc_type="string", description="原英文 ID"),
            LPCParam(name="what", lpc_type="string", description="新英文 ID"),
        ],
        return_type="int",
        lpc_file="adm/daemons/regid.c",
        line_range=(129, 168),
    ),
    preconditions=[
        Precondition(description="who 对应的 LOGIN_OB 与 USER_OB 均可 restore", kind="require"),
        Precondition(description="what 对应的 LOGIN_OB 不可 restore", kind="require"),
        Precondition(description="who 与 what 权限均为 (player)", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 1，登录与用户对象 ID 均改为 what 并保存，原存档文件被删除",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="不会覆盖已存在的 what 账号",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="restore who 的 LOGIN_OB 与 USER_OB",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="检查 what 是否已存在",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="设置两个对象的 id 为 what 并 save",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.PERSISTENCE,
            description="rm 原 LOGIN/USER 存档文件",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="destruct 三个临时对象",
        ),
    ],
    random_specs=[],
    notes="高风险账号改名，需要同时迁移 LOGIN_OB 与 USER_OB 存档。",
)

# ---------------------------------------------------------------------------
# MARRY_D 规格
# ---------------------------------------------------------------------------

_marry_setup_marriage = FunctionSpec(
    signature=FunctionSignature(
        name="setup_marriage",
        params=[
            LPCParam(name="p1", lpc_type="object", description="玩家 1"),
            LPCParam(name="p2", lpc_type="object", description="玩家 2"),
            LPCParam(name="r1", lpc_type="object", description="给 p2 的戒指对象"),
            LPCParam(name="r2", lpc_type="object", description="给 p1 的戒指对象"),
        ],
        return_type="int",
        lpc_file="adm/daemons/marryd.c",
        line_range=(14, 46),
    ),
    preconditions=[
        Precondition(description="p1/p2/r1/r2 均为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="返回 1，p1/p2 的 spouse 信息互相设置，已婚次数递增，戒指交换",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="spouse 信息对称：p1 的 spouse/id 等于 p2 的 id，反之亦然",
            scope="function",
        ),
        Invariant(
            description="title 按 gender 分配：男性为丈夫/女性为妻子",
            scope="function",
        ),
        Invariant(
            description="married_times 在更换配偶时递增",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="根据 gender 确定 title1/title2",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="互相设置 spouse/id、spouse/name、spouse/title",
            target="p1,p2",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="last_spouse_id 变化时递增 married_times",
            target="p1,p2",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.PERSISTENCE,
            description="save p1 与 p2",
            target="p1,p2",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="r1 move 到 p2，r2 move 到 p1",
        ),
    ],
    random_specs=[],
    notes="不校验婚姻合法性，由调用方保证。",
)

_marry_break_marriage = FunctionSpec(
    signature=FunctionSignature(
        name="break_marriage",
        params=[
            LPCParam(name="breaker", lpc_type="object", description="解除婚姻的一方"),
        ],
        return_type="int",
        lpc_file="adm/daemons/marryd.c",
        line_range=(49, 65),
    ),
    preconditions=[
        Precondition(description="breaker 有 spouse 映射", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 1 并删除 breaker 的 spouse；无配偶返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只修改 breaker 本地数据，不修改已离婚配偶的存档",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 breaker->spouse",
            target="breaker",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="若佩戴戒指则调用 ring->init() 重置",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="若配偶在线则调用 bad_news 通知",
        ),
    ],
    random_specs=[],
    notes="死亡时由 damage.c die() 调用，也可能由管理命令调用。",
)

_marry_validate_marriage = FunctionSpec(
    signature=FunctionSignature(
        name="validate_marriage",
        params=[
            LPCParam(name="me", lpc_type="object", description="登录后待验证婚姻状态的玩家"),
        ],
        return_type="int",
        lpc_file="adm/daemons/marryd.c",
        line_range=(68, 99),
    ),
    preconditions=[
        Precondition(description="me 为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="无配偶时返回 0",
            kind="ensure",
        ),
        Postcondition(
            description="配偶双方互为 spouse 时返回 1",
            kind="ensure",
        ),
        Postcondition(
            description="配偶不互认时返回 bad_news(me) 的结果（0）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="is_spouse_of 必须双向成立，否则视为离婚",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查 me->spouse/id",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="配偶在线时双向 is_spouse_of 校验",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="配偶离线时创建临时 USER_OB restore 后校验",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="校验失败时调用 bad_news(me) 清除 spouse",
            target="me",
        ),
    ],
    random_specs=[],
    notes="LOGIN_D enter_world 调用，处理离线期间配偶数据不一致。",
)
# ---------------------------------------------------------------------------
# EMOTE_D 规格
# ---------------------------------------------------------------------------

_emote_query_save_file = FunctionSpec(
    signature=FunctionSignature(
        name="query_save_file",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/emoted.c",
        line_range=(56, 56),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description='返回 DATA_DIR + "emoted" 存档路径',
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="返回值恒定，供 F_SAVE 的 restore/save 使用",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="F_SAVE 回调，无运行时状态副作用。",
)

_emote_normal_color = FunctionSpec(
    signature=FunctionSignature(
        name="normal_color",
        params=[
            LPCParam(name="arg", lpc_type="string", description="可能含 ANSI 转义序列的字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/emoted.c",
        line_range=(59, 72),
    ),
    preconditions=[
        Precondition(description="arg 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回去除 ANSI ESC 序列后的纯文本字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="输出长度不超过输入长度",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="频道 emote 消息发送前调用，避免 ANSI 污染广播内容。",
)

_emote_do_emote = FunctionSpec(
    signature=FunctionSignature(
        name="do_emote",
        params=[
            LPCParam(name="me", lpc_type="object", description="执行 emote 的玩家对象"),
            LPCParam(name="verb", lpc_type="string", description="表情动词"),
            LPCParam(name="arg", lpc_type="string", description="目标参数", is_varargs_tail=True),
            LPCParam(
                name="channel_emote",
                lpc_type="int",
                description="0=本地 1=chat 2=rumor 3=intermud",
                is_varargs_tail=True,
            ),
        ],
        return_type="mixed",
        is_varargs=True,
        lpc_file="adm/daemons/emoted.c",
        line_range=(79, 175),
    ),
    preconditions=[
        Precondition(description="me 为有 environment 的有效对象", kind="require"),
        Precondition(description="emote 映射中存在 verb 对应的定义", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="本地 emote 成功时返回 1 并已广播消息",
            kind="effect",
        ),
        Postcondition(
            description="channel_emote != 0 时返回处理后的消息字符串",
            kind="ensure",
        ),
        Postcondition(
            description="无目标或找不到定义时返回 0 或 notify_fail",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="channel_emote == 0 时直接发消息，否则返回字符串给 CHANNEL_D",
            scope="function",
        ),
        Invariant(
            description="本地 emote 使用 CYN + normal_color(str) + NOR 输出",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="解析目标对象：present / find_player / is_character / visible 检查",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="根据 channel_emote 与巫师隐身状态确定 myname 显示形式",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="用 $N/$n/$P/$p/$S/$s/$C/$c/$R/$r 替换模板变量",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="myself 分支向 me 发送 emote 消息",
            target="me",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="target 分支向 target 发送 emote 消息",
            target="target",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="others 分支向 environment(me) 除 me/target 外广播",
            target="environment(me)",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="存在目标时调用 target->relay_emote(me, verb)",
            target="target",
        ),
    ],
    random_specs=[],
    notes="同时被 command_hook（本地）和 CHANNEL_D（频道）调用，channel_emote 决定行为分支。",
)

_emote_do_intermud_emote = FunctionSpec(
    signature=FunctionSignature(
        name="do_intermud_emote",
        params=[
            LPCParam(
                name="myinfo",
                lpc_type="string",
                description="name:gender:rank_self:rank_self_rude:age:mud_age",
            ),
            LPCParam(name="verb", lpc_type="string", description="表情动词"),
            LPCParam(
                name="targetid", lpc_type="string", description="目标玩家 ID", is_varargs_tail=True
            ),
        ],
        return_type="mixed",
        is_varargs=True,
        lpc_file="adm/daemons/emoted.c",
        line_range=(178, 208),
    ),
    preconditions=[
        Precondition(description="emote 映射中存在 verb 定义", kind="guard"),
        Precondition(description="targetid 非空且 find_player 能找到目标", kind="require"),
        Precondition(description="myinfo 能被 sscanf 按 6 字段解析", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 normal_color(str) 字符串",
            kind="ensure",
        ),
        Postcondition(
            description="解析失败时无返回值，找不到目标或定义时返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="在 daemon 自身 dbase 临时设置 gender/age/mud_age 供称谓查询",
            scope="function",
        ),
        Invariant(
            description="只使用 others_target 模板生成跨 MUD 消息",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="在 daemon 对象上 set gender/age/mud_age",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="用 $N/$n/$P/$p/$S/$s/$C/$c/$R/$r 替换模板变量",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="返回 normal_color(str) 供 intermud 发送",
        ),
    ],
    random_specs=[],
    notes="InterMUD 已按 04/09 决策预留，新引擎如砍 intermud 则此函数无需实现网络发送。",
)

_emote_set_emote = FunctionSpec(
    signature=FunctionSignature(
        name="set_emote",
        params=[
            LPCParam(name="pattern", lpc_type="string", description="表情模式键"),
            LPCParam(name="def", lpc_type="mapping", description="表情定义映射"),
        ],
        return_type="int",
        lpc_file="adm/daemons/emoted.c",
        line_range=(212, 217),
    ),
    preconditions=[
        Precondition(description="pattern 为字符串", kind="input_constraint"),
        Precondition(description="def 为 mapping", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="恒返回 1",
            kind="ensure",
        ),
        Postcondition(
            description="emote[pattern] 被设置为 def 并持久化",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="调用 save() 写入 DATA_DIR/emoted",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="emote[pattern] = def",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="调用 save() 持久化全局 emote 映射",
        ),
    ],
    random_specs=[],
    notes="管理命令入口，直接修改全局 emote 数据库。",
)

_emote_delete_emote = FunctionSpec(
    signature=FunctionSignature(
        name="delete_emote",
        params=[
            LPCParam(name="pattern", lpc_type="string", description="要删除的表情模式键"),
        ],
        return_type="int",
        lpc_file="adm/daemons/emoted.c",
        line_range=(219, 224),
    ),
    preconditions=[
        Precondition(description="pattern 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="恒返回 1",
            kind="ensure",
        ),
        Postcondition(
            description="emote 中不再包含 pattern 键并持久化",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="即使 pattern 不存在也会调用 save()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="map_delete(emote, pattern)",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="调用 save() 持久化全局 emote 映射",
        ),
    ],
    random_specs=[],
    notes="管理命令入口。",
)

_emote_query_emote = FunctionSpec(
    signature=FunctionSignature(
        name="query_emote",
        params=[
            LPCParam(name="pattern", lpc_type="string", description="表情模式键"),
        ],
        return_type="mapping",
        lpc_file="adm/daemons/emoted.c",
        line_range=(226, 230),
    ),
    preconditions=[
        Precondition(description="pattern 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="存在时返回 emote[pattern]，否则返回空映射",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只读查询，不修改 emote",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯查询函数。",
)

_emote_query_all_emote = FunctionSpec(
    signature=FunctionSignature(
        name="query_all_emote",
        params=[],
        return_type="string *",
        lpc_file="adm/daemons/emoted.c",
        line_range=(232, 235),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 emote 映射所有键的数组",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只读查询，返回 keys(emote)",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯查询函数。",
)

# ---------------------------------------------------------------------------
# INQUIRY_D 规格
# ---------------------------------------------------------------------------

_inquiry_parse_inquiry = FunctionSpec(
    signature=FunctionSignature(
        name="parse_inquiry",
        params=[
            LPCParam(name="me", lpc_type="object", description="询问者"),
            LPCParam(name="ob", lpc_type="object", description="被询问的 NPC/玩家"),
            LPCParam(name="topic", lpc_type="string", description="话题关键词"),
        ],
        return_type="int",
        lpc_file="adm/daemons/inquiryd.c",
        line_range=(12, 31),
    ),
    preconditions=[
        Precondition(description="me 与 ob 为有效对象", kind="require"),
        Precondition(description="topic 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="匹配 name/here/rumors 时返回 1 并输出对话",
            kind="effect",
        ),
        Postcondition(
            description="未知话题返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="输出文本使用 RANK_D 称谓与 CYN/NOR 颜色包裹",
            scope="function",
        ),
        Invariant(
            description="未知话题不输出任何消息",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="name 话题询问尊姓大名",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="here 话题询问风土人情",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="rumors 话题询问消息",
        ),
    ],
    random_specs=[],
    notes="由 NPC 的 inquiry 行为调用，硬编码三个基础话题。",
)

# ---------------------------------------------------------------------------
# PIG_D 规格
# ---------------------------------------------------------------------------

_pig_is_validcard = FunctionSpec(
    signature=FunctionSignature(
        name="is_validcard",
        params=[
            LPCParam(name="str", lpc_type="string", description="2 字符牌面表示，如 SA"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(17, 39),
    ),
    preconditions=[
        Precondition(description="str 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="有效牌返回 0-51 的牌编号",
            kind="ensure",
        ),
        Postcondition(
            description="无效牌返回 -1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="牌编号 = 花色索引 * 13 + 点数索引",
            scope="function",
        ),
        Invariant(
            description="输入长度不为 2 时直接返回 -1",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数，拱猪牌面校验。",
)

_pig_is_validbid = FunctionSpec(
    signature=FunctionSignature(
        name="is_validbid",
        params=[
            LPCParam(name="c", lpc_type="int", description="牌编号"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(41, 52),
    ),
    preconditions=[
        Precondition(description="c 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="特殊牌返回对应 BID_* 常量",
            kind="ensure",
        ),
        Postcondition(
            description="非特殊牌返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只识别 SPIG/HACE/DSHEEP/CTRANS 四张牌",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_is_special = FunctionSpec(
    signature=FunctionSignature(
        name="is_special",
        params=[
            LPCParam(name="c", lpc_type="int", description="牌编号"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(54, 57),
    ),
    preconditions=[
        Precondition(description="c 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="特殊牌返回 1，否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="特殊牌包含猪、羊、变压器及全部红心",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_card_str = FunctionSpec(
    signature=FunctionSignature(
        name="card_str",
        params=[
            LPCParam(name="c", lpc_type="int", description="牌编号"),
        ],
        return_type="string",
        lpc_file="adm/daemons/pigd.c",
        line_range=(59, 64),
    ),
    preconditions=[
        Precondition(description="c 为整数", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="0 <= c <= 51 时返回中文牌面字符串",
            kind="ensure",
        ),
        Postcondition(
            description="越界返回空字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="输出格式为 花色中文 + 点数全角字符",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_refresh = FunctionSpec(
    signature=FunctionSignature(
        name="refresh",
        params=[
            LPCParam(name="cl", lpc_type="int *", description="牌数组"),
            LPCParam(name="b", lpc_type="int", description="起始索引"),
            LPCParam(name="e", lpc_type="int", description="结束索引"),
        ],
        return_type="string",
        lpc_file="adm/daemons/pigd.c",
        line_range=(66, 86),
    ),
    preconditions=[
        Precondition(description="b/e 为非负整数", kind="input_constraint"),
        Precondition(description="cl[b..e] 在 0-51 范围内", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回按花色分组格式化的手牌字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="花色变化时换行，同一花色点数连续输出",
            scope="function",
        ),
        Invariant(
            description="越界返回空字符串",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数，格式化展示用。",
)

_pig_has_suit = FunctionSpec(
    signature=FunctionSignature(
        name="has_suit",
        params=[
            LPCParam(name="cl", lpc_type="int *", description="牌数组"),
            LPCParam(name="b", lpc_type="int", description="起始索引"),
            LPCParam(name="e", lpc_type="int", description="结束索引"),
            LPCParam(name="s", lpc_type="int", description="花色 0-3"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(88, 95),
    ),
    preconditions=[
        Precondition(description="b/e 为有效索引范围", kind="input_constraint"),
        Precondition(description="s 在 0-3 范围内", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 cl[b..e] 中花色为 s 的牌数量",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只统计不修改数组",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_has_card = FunctionSpec(
    signature=FunctionSignature(
        name="has_card",
        params=[
            LPCParam(name="cl", lpc_type="int *", description="牌数组"),
            LPCParam(name="b", lpc_type="int", description="起始索引"),
            LPCParam(name="e", lpc_type="int", description="结束索引"),
            LPCParam(name="c", lpc_type="int", description="目标牌编号"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(96, 103),
    ),
    preconditions=[
        Precondition(description="b/e 为有效索引范围", kind="input_constraint"),
        Precondition(description="c 为 0-51 的牌编号", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="找到返回 1，未找到返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="线性查找，找到即返回",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_shuffle = FunctionSpec(
    signature=FunctionSignature(
        name="shuffle",
        params=[
            LPCParam(name="ol", lpc_type="int *", description="原牌组数组，引用传递"),
            LPCParam(name="nl", lpc_type="int *", description="新牌组数组，引用传递"),
            LPCParam(name="t", lpc_type="int", description="洗牌次数"),
        ],
        return_type="void",
        lpc_file="adm/daemons/pigd.c",
        line_range=(105, 122),
    ),
    preconditions=[
        Precondition(description="ol 与 nl 为可写数组", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="ol 与 nl 被重新排列为 t 次洗牌后的结果",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="数组长度不足 52 时先初始化为 0-51 有序排列",
            scope="function",
        ),
        Invariant(
            description="t <= 0 或 t >= 10 时强制 t = 1",
            scope="function",
        ),
        Invariant(
            description="洗牌后两数组内容一致",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="必要时将 ol/nl 初始化为 0-51",
            target="ol,nl",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="按 t 轮 Fisher-Yates 抽取并写入 nl",
            target="nl",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="每轮结束将 nl 拷回 ol",
            target="ol",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(k)",
            probability_model="uniform [0, k-1]",
            semantic="每轮从剩余牌中随机抽取的索引",
            seed_inputs=["k"],
            determinism_note="非战斗随机性，发牌洗牌",
        ),
    ],
    notes="通过引用修改传入数组，与 LPC 数组按引用语义一致。",
)

_pig_card_cmp4 = FunctionSpec(
    signature=FunctionSignature(
        name="card_cmp4",
        params=[
            LPCParam(name="cl", lpc_type="mapping", description="4 个玩家出牌映射"),
            LPCParam(name="s", lpc_type="int", description="花色 0-3"),
        ],
        return_type="string",
        lpc_file="adm/daemons/pigd.c",
        line_range=(124, 137),
    ),
    preconditions=[
        Precondition(description="s 在 0-3 范围内", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回花色 s 中点数最大的键",
            kind="ensure",
        ),
        Postcondition(
            description="mapping 不为 4 项时返回第一个 key",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只比较指定花色且点数 >= 当前最大值的牌",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_order_turn = FunctionSpec(
    signature=FunctionSignature(
        name="order_turn",
        params=[
            LPCParam(name="rw", lpc_type="string", description="赢家方位 east/north/west/其他"),
        ],
        return_type="string *",
        lpc_file="adm/daemons/pigd.c",
        line_range=(139, 149),
    ),
    preconditions=[
        Precondition(description="rw 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 4 元素座位顺序数组，从赢家开始顺时针",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="east 返回 east/north/west/south，其他以此类推",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数。",
)

_pig_count_score = FunctionSpec(
    signature=FunctionSignature(
        name="count_score",
        params=[
            LPCParam(name="fcl", lpc_type="int *", description="收到的所有牌数组"),
            LPCParam(name="bid_flag", lpc_type="int", description="叫牌掩码"),
        ],
        return_type="int",
        lpc_file="adm/daemons/pigd.c",
        line_range=(151, 224),
    ),
    preconditions=[
        Precondition(description="fcl 为整数数组", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回按规则计算的得分，正数为得分，负数为扣分",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="收到全部 16 张特殊牌直接返回 1000",
            scope="function",
        ),
        Invariant(
            description="bid_flag 中对应位为 1 时相关分值加倍",
            scope="function",
        ),
        Invariant(
            description="变压器 CTRANS 使最终得分乘以 1/2/4 倍",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯函数，支持 single pig 规则。",
)

# ---------------------------------------------------------------------------
# PROFILE_D 规格
# ---------------------------------------------------------------------------

_profile_log_command = FunctionSpec(
    signature=FunctionSignature(
        name="log_command",
        params=[
            LPCParam(name="entry", lpc_type="string", description="命令条目名"),
            LPCParam(name="mem", lpc_type="int", description="内存消耗"),
            LPCParam(name="stime", lpc_type="int", description="系统时间"),
            LPCParam(name="utime", lpc_type="int", description="用户时间"),
        ],
        return_type="void",
        lpc_file="adm/daemons/profiled.c",
        line_range=(19, 35),
    ),
    preconditions=[
        Precondition(description="entry 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="command_log 中对应 entry 的 count/mem/stime/utime 被累加或新建",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="command_log 条目数不超过 MAX_ENTRIES=300",
            scope="system",
        ),
        Invariant(
            description="超过 MAX_ENTRIES 时递增 overflowed_log 而不新增条目",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="累加或新建 command_log[entry] 子映射",
            target="command_log",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="超限时递增 overflowed_log",
            target="overflowed_log",
        ),
    ],
    random_specs=[],
    notes="性能分析采样入口。",
)

_profile_make_profile = FunctionSpec(
    signature=FunctionSignature(
        name="make_profile",
        params=[
            LPCParam(name="sort_by", lpc_type="string", description="排序字段名"),
        ],
        return_type="void",
        lpc_file="adm/daemons/profiled.c",
        line_range=(37, 56),
    ),
    preconditions=[
        Precondition(description="sort_by 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="生成 /PROFILE 性能报告文件",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="sort_by 为空时按 entry 名字母序排序",
            scope="function",
        ),
        Invariant(
            description="sort_by 非空时按 command_log[entry][sort_by] 排序",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置全局 sorting_by = sort_by",
            target="sorting_by",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="提取 command_log 键并排序",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="rm 旧 /PROFILE 文件",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.PERSISTENCE,
            description="write_file 写入格式化性能报告",
        ),
    ],
    random_specs=[],
    notes="生成并落盘性能剖析报告。",
)

_profile_sort_entry = FunctionSpec(
    signature=FunctionSignature(
        name="sort_entry",
        params=[
            LPCParam(name="entry1", lpc_type="string", description="条目 1"),
            LPCParam(name="entry2", lpc_type="string", description="条目 2"),
        ],
        return_type="int",
        lpc_file="adm/daemons/profiled.c",
        line_range=(58, 63),
    ),
    preconditions=[
        Precondition(description="entry1/entry2 在 command_log 中存在", kind="require"),
        Precondition(description="sorting_by 已设置", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="entry1 排序值小于 entry2 时返回 -1，否则返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="比较的是 command_log[entry][sorting_by]",
            scope="function",
        ),
        Invariant(
            description="大于和等于均返回 0，不满足严格弱序",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="LPC sort_array 回调函数，存在潜在排序不等价风险。",
)

# ---------------------------------------------------------------------------
# ADS_D 规格
# ---------------------------------------------------------------------------

_ads_init_ads_phase = FunctionSpec(
    signature=FunctionSignature(
        name="init_ads_phase",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/adsd.c",
        line_range=(18, 38),
    ),
    preconditions=[
        Precondition(description="ads_phase 已被 read_table 初始化", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="current_ads_phase 设置为当前时间所属阶段",
            kind="effect",
        ),
        Postcondition(
            description="已安排下一次 update_ads_phase 的 call_out",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="阶段切换基于当前分钟数与 ads_phase 时间范围匹配",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="localtime(TIME_TICK) 获取当前时间",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 current_ads_phase",
            target="current_ads_phase",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.CALL_OUT,
            description="call_out update_ads_phase 到下一阶段边界",
        ),
    ],
    random_specs=[],
    notes="create() 时调用，启动广告阶段调度。",
)

_ads_update_ads_phase = FunctionSpec(
    signature=FunctionSignature(
        name="update_ads_phase",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/adsd.c",
        line_range=(40, 72),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="current_ads_phase 循环递增并对 ads_phase 长度取模",
            kind="effect",
        ),
        Postcondition(
            description="向所有在线用户广播当前阶段广告",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="current_ads_phase == 0 时重新 init_ads_phase",
            scope="function",
        ),
        Invariant(
            description="广告消息按 ads_phase[current_ads_phase] 配置组装",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="remove_call_out update_ads_phase",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="必要时重新 init_ads_phase",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="current_ads_phase = (++current_ads_phase) % sizeof(ads_phase)",
            target="current_ads_phase",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="message channel:ads 向 users() 广播广告",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="log_file ADS 记录广告日志",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 this_object()->event_common()",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.CALL_OUT,
            description="安排下一次 update_ads_phase",
        ),
    ],
    random_specs=[],
    notes="周期性广告触发器。",
)

_ads_read_table = FunctionSpec(
    signature=FunctionSignature(
        name="read_table",
        params=[
            LPCParam(name="file", lpc_type="string", description="待读取的配置文件路径"),
        ],
        return_type="mapping *",
        lpc_file="adm/daemons/adsd.c",
        line_range=(75, 104),
    ),
    preconditions=[
        Precondition(description="file 为存在的可读文件路径", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="返回按 format 解析出的 mapping 数组",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="跳过空行和 # 开头的注释行",
            scope="function",
        ),
        Invariant(
            description="第一行解析字段名，第二行解析 sscanf format",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="read_file 读取整个配置文件",
        ),
    ],
    random_specs=[],
    notes="通用表格式配置解析器。",
)

_ads_query_ads_phase = FunctionSpec(
    signature=FunctionSignature(
        name="query_ads_phase",
        params=[],
        return_type="mapping *",
        lpc_file="adm/daemons/adsd.c",
        line_range=(107, 107),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回当前 ads_phase 数组",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只读返回全局 ads_phase，不修改",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯查询函数。",
)

# ---------------------------------------------------------------------------
# EDITOR_D 规格
# ---------------------------------------------------------------------------

_editor_add = FunctionSpec(
    signature=FunctionSignature(
        name="add",
        params=[
            LPCParam(name="arc", lpc_type="int", description="1=archive 路径，0=editor 路径"),
            LPCParam(name="article", lpc_type="string", description="文章内容"),
            LPCParam(
                name="fname",
                lpc_type="string",
                description="文件名，可为 NULL",
                is_varargs_tail=True,
            ),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="adm/daemons/editord.c",
        line_range=(16, 42),
    ),
    preconditions=[
        Precondition(description="article 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="write_file 成功返回 1，失败返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="arc=1 写入 /open/archive/，arc=0 写入 /open/wenxuan/",
            scope="function",
        ),
        Invariant(
            description="fname 为空时用 Unknown 作为文件名",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置全局 Articles = ({article})",
            target="Articles",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="file_size 检查目标文件是否存在",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="write_file 追加文章到目标文件",
        ),
    ],
    random_specs=[],
    notes="提交文章或投稿，Articles 每次调用被覆盖为单元素数组。",
)

_editor_get_file_num = FunctionSpec(
    signature=FunctionSignature(
        name="get_file_num",
        params=[
            LPCParam(name="arc", lpc_type="int", description="1=archive 路径，0=editor 路径"),
            LPCParam(name="year", lpc_type="string", description="年份"),
            LPCParam(name="month", lpc_type="string", description="月份"),
        ],
        return_type="int",
        lpc_file="adm/daemons/editord.c",
        line_range=(44, 91),
    ),
    preconditions=[
        Precondition(description="month 非空", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="month 为空返回 -1",
            kind="ensure",
        ),
        Postcondition(
            description="文件不存在返回 0",
            kind="ensure",
        ),
        Postcondition(
            description="否则返回文件中最后提取的期号",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="从文件末尾向前搜索 № 标记提取期号",
            scope="function",
        ),
        Invariant(
            description="mkdir 始终基于 /open/wenxuan/ 创建目录，与 arc 参数无关",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="file_size 检查目标文件是否存在",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="mkdir 创建 /open/wenxuan/year/month 目录",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="read_file 读取整个文件",
        ),
    ],
    random_specs=[],
    notes="计算期刊期号，mkdir 路径与 arc 参数不一致为 LPC 原实现细节。",
)

# ---------------------------------------------------------------------------
# WEAPON_D 规格
# ---------------------------------------------------------------------------

_weapon_query_action = FunctionSpec(
    signature=FunctionSignature(
        name="query_action",
        params=[],
        return_type="mapping",
        lpc_file="adm/daemons/weapond.c",
        line_range=(75, 87),
    ),
    preconditions=[
        Precondition(description='previous_object() 存在且能 query("verbs")', kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="返回 weapon_actions[verb] 映射",
            kind="ensure",
        ),
        Postcondition(
            description='verbs 非数组或 verb 未定义时返回 weapon_actions["hit"]',
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description='从 previous_object()->query("verbs") 中随机选取 verb',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description='读取 previous_object()->query("verbs")',
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="返回 weapon_actions 中对应动作映射",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(sizeof(verbs))",
            probability_model="uniform [0, sizeof(verbs)-1]",
            semantic="从武器动词列表中随机选择攻击动作",
            seed_inputs=["verbs"],
            determinism_note="战斗随机性，决定武器动作展示",
        ),
    ],
    notes="combat 中由武器对象调用选择攻击动作模板。",
)

_weapon_throw_weapon = FunctionSpec(
    signature=FunctionSignature(
        name="throw_weapon",
        params=[
            LPCParam(name="me", lpc_type="object", description="攻击者"),
            LPCParam(name="victim", lpc_type="object", description="受害者"),
            LPCParam(name="weapon", lpc_type="object", description="投掷武器对象"),
            LPCParam(name="damage", lpc_type="int", description="伤害值，本函数未使用"),
        ],
        return_type="void",
        lpc_file="adm/daemons/weapond.c",
        line_range=(89, 98),
    ),
    preconditions=[
        Precondition(description="weapon 为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="weapon 数量被扣减 1",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="数量为 1 时先 unequip 并提示用完",
            scope="function",
        ),
        Invariant(
            description="damage 参数不被使用",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="数量为 1 时调用 weapon->unequip()",
            target="weapon",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="数量为 1 时 tell_object(me) 提示武器用完",
            target="me",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 weapon->add_amount(-1)",
            target="weapon",
        ),
    ],
    random_specs=[],
    notes="投掷武器的 post_action，处理数量扣减。",
)

_weapon_bash_weapon = FunctionSpec(
    signature=FunctionSignature(
        name="bash_weapon",
        params=[
            LPCParam(name="me", lpc_type="object", description="攻击者"),
            LPCParam(name="victim", lpc_type="object", description="受害者"),
            LPCParam(name="weapon", lpc_type="object", description="攻击武器"),
            LPCParam(name="damage", lpc_type="int", description="伤害结果，需为 RESULT_PARRY"),
        ],
        return_type="void",
        lpc_file="adm/daemons/weapond.c",
        line_range=(100, 146),
    ),
    preconditions=[
        Precondition(description="weapon 为有效对象", kind="require"),
        Precondition(description="damage == RESULT_PARRY", kind="guard"),
        Precondition(description='victim 有临时武器 query_temp("weapon")', kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="根据 wap 与 wdp 比例触发断裂/脱手/震动/火星效果",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="wap 与 wdp 计算含武器重量/500、rigidity、力量、jiali、技能等级",
            scope="function",
        ),
        Invariant(
            description="wap > 3*wdp 时武器断裂并设为 value=0、weapon_prop=0",
            scope="function",
        ),
        Invariant(
            description="wap > 2*wdp 时武器脱手 move 到 environment(victim)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="计算攻击方 wap 与防守方 wdp",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="wap = random(wap)",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="根据比例输出断裂/脱手/震动/火星消息",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="断裂/脱手时调用 ob->unequip() 与 victim->reset_action()",
            target="victim",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="断裂/脱手时调用 ob->move(environment(victim))",
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="断裂时修改 ob name/value/weapon_prop",
            target="ob",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(wap)",
            probability_model="uniform [0, wap-1]",
            semantic="砸武器时的实际攻击力",
            seed_inputs=["wap"],
            determinism_note="战斗随机性，武器对抗判定",
        ),
    ],
    notes="砸武器 post_action，属于 combat 副作用交织的一部分。",
)

# ---------------------------------------------------------------------------
# LANGUAGE_D 规格
# ---------------------------------------------------------------------------

_language_GB2Big5 = FunctionSpec(
    signature=FunctionSignature(
        name="GB2Big5",
        params=[
            LPCParam(name="src", lpc_type="string", description="GB 编码源字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/languaged.c",
        line_range=(108, 123),
    ),
    preconditions=[
        Precondition(description="src 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 GB 转 Big5 后的字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只转换 0xa1-0xf7 / 0xa1-0xfe 范围内的 GB 字符对",
            scope="function",
        ),
        Invariant(
            description="非 GB 字符原样保留",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="Fetch 读取转换表并更新 G2B_Cache",
            target="G2B_Cache",
        ),
    ],
    random_specs=[],
    notes="GB2312 到 Big5 编码转换，带缓存。",
)

_language_Big52GB = FunctionSpec(
    signature=FunctionSignature(
        name="Big52GB",
        params=[
            LPCParam(name="src", lpc_type="string", description="Big5 编码源字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/languaged.c",
        line_range=(126, 141),
    ),
    preconditions=[
        Precondition(description="src 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="返回 Big5 转 GB 后的字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只转换 0xa1-0xfe / 0x40-0x7e 或 0xa1-0xfe 范围内的 Big5 字符对",
            scope="function",
        ),
        Invariant(
            description="非 Big5 字符原样保留",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="Fetch 读取转换表并更新 B2G_Cache",
            target="B2G_Cache",
        ),
    ],
    random_specs=[],
    notes="Big5 到 GB2312 编码转换，带缓存。",
)

_language_toBig5 = FunctionSpec(
    signature=FunctionSignature(
        name="toBig5",
        params=[
            LPCParam(name="str", lpc_type="string", description="待转换字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/languaged.c",
        line_range=(144, 148),
    ),
    preconditions=[
        Precondition(description="str 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="字符串输入时返回 GB2Big5(str)",
            kind="ensure",
        ),
        Postcondition(
            description="非字符串输入时返回空字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="仅做类型检查后委托 GB2Big5",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 GB2Big5 并可能更新 G2B_Cache",
            target="G2B_Cache",
        ),
    ],
    random_specs=[],
    notes="GB2Big5 的包装入口。",
)

_language_toGB = FunctionSpec(
    signature=FunctionSignature(
        name="toGB",
        params=[
            LPCParam(name="str", lpc_type="string", description="待转换字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/languaged.c",
        line_range=(150, 154),
    ),
    preconditions=[
        Precondition(description="str 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="字符串输入时返回 Big52GB(str)",
            kind="ensure",
        ),
        Postcondition(
            description="非字符串输入时返回空字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="仅做类型检查后委托 Big52GB",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="调用 Big52GB 并可能更新 B2G_Cache",
            target="B2G_Cache",
        ),
    ],
    random_specs=[],
    notes="Big52GB 的包装入口。",
)

# ---------------------------------------------------------------------------
# VIRTUAL_D 规格
# ---------------------------------------------------------------------------

_virtual_compile_object = FunctionSpec(
    signature=FunctionSignature(
        name="compile_object",
        params=[
            LPCParam(name="file", lpc_type="string", description="请求编译的虚拟对象文件名"),
        ],
        return_type="object",
        lpc_file="adm/daemons/virtuald.c",
        line_range=(16, 19),
    ),
    preconditions=[
        Precondition(description="file 为字符串", kind="input_constraint"),
    ],
    postconditions=[
        Postcondition(
            description="恒返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="本 MUD 不提供任何虚拟对象",
            scope="system",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="master object 回调占位，新引擎如无虚拟对象需求可保持返回 None。",
)

# ---------------------------------------------------------------------------
# 层 H-2 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="H-2",
    layer_name="第二梯队守护进程",
    lpc_files=[
        # 基础频道/经济/登录/别名
        "adm/daemons/channeld.c",
        "adm/daemons/moneyd.c",
        "adm/daemons/updated.c",
        "adm/daemons/aliasd.c",
        # 玩家/封禁/注册/婚姻
        "adm/daemons/fingerd.c",
        "adm/daemons/band.c",
        "adm/daemons/regband.c",
        "adm/daemons/regid.c",
        "adm/daemons/marryd.c",
        # 第二梯队工具/游戏 daemon
        "adm/daemons/emoted.c",
        "adm/daemons/inquiryd.c",
        "adm/daemons/pigd.c",
        "adm/daemons/profiled.c",
        "adm/daemons/adsd.c",
        "adm/daemons/editord.c",
        "adm/daemons/weapond.c",
        "adm/daemons/languaged.c",
        "adm/daemons/virtuald.c",
    ],
    function_specs=[
        # CHANNEL_D
        _do_channel,
        _filter_listener,
        _register_relay_channel,
        _remove_addresses,
        # MONEY_D
        _money_str,
        _price_str,
        _pay_player,
        _player_pay,
        _player_dealer_pay,
        _player_bank_pay,
        _player_job_pay,
        _query_avalible_xkx_cashflow,
        _query_total_xkx_cashflow,
        # UPDATE_D
        _login_check,
        _inventory_check,
        # ALIAS_D
        _get_current_alias,
        _process_global_alias,
        # FINGER_D
        _finger_ip_cmp,
        _finger_age_string,
        _finger_all,
        _finger_user,
        _finger_remote_finger_user,
        _finger_acquire_login_ob,
        _finger_get_killer,
        # BAN_D
        _ban_load_sites,
        _ban_is_banned,
        _ban_print,
        _ban_add,
        _ban_remove,
        # REGBAN_D
        _regban_load_sites,
        _regban_is_banned,
        _regban_print,
        _regban_add,
        _regban_remove,
        _regban_check,
        # REGI_D
        _regi_is_banned_email,
        _regi_random_password,
        _regi_register_char,
        _regi_change_password,
        _regi_change_name,
        _regi_change_id,
        # MARRY_D
        _marry_setup_marriage,
        _marry_break_marriage,
        _marry_validate_marriage,
        # EMOTE_D
        _emote_query_save_file,
        _emote_normal_color,
        _emote_do_emote,
        _emote_do_intermud_emote,
        _emote_set_emote,
        _emote_delete_emote,
        _emote_query_emote,
        _emote_query_all_emote,
        # INQUIRY_D
        _inquiry_parse_inquiry,
        # PIG_D
        _pig_is_validcard,
        _pig_is_validbid,
        _pig_is_special,
        _pig_card_str,
        _pig_refresh,
        _pig_has_suit,
        _pig_has_card,
        _pig_shuffle,
        _pig_card_cmp4,
        _pig_order_turn,
        _pig_count_score,
        # PROFILE_D
        _profile_log_command,
        _profile_make_profile,
        _profile_sort_entry,
        # ADS_D
        _ads_init_ads_phase,
        _ads_update_ads_phase,
        _ads_read_table,
        _ads_query_ads_phase,
        # EDITOR_D
        _editor_add,
        _editor_get_file_num,
        # WEAPON_D
        _weapon_query_action,
        _weapon_throw_weapon,
        _weapon_bash_weapon,
        # LANGUAGE_D
        _language_GB2Big5,
        _language_Big52GB,
        _language_toBig5,
        _language_toGB,
        # VIRTUAL_D
        _virtual_compile_object,
    ],
    cross_layer_refs=[
        "EMOTE_D->do_emote (层 H-2 / 第二梯队) -- CHANNEL_D emote 处理调用",
        "RANK_D->query_self / query_self_rude (层 H) -- CHANNEL_D/EMOTE_D 称谓组装",
        "REMOTE_Q->send_remote_q (分布式网关，已砍) -- CHANNEL_D intermud 发送，新引擎预留",
        "users() / environment() / wizardp() (层 A/B) -- CHANNEL_D filter_listener 依赖",
        "message() (层 B: F_MESSAGE) -- CHANNEL_D 广播消息",
        "chinese_number (层 H: CHINESE_D) -- MONEY_D 金额中文显示",
        "GOLD_OB / SILVER_OB / COIN_OB (层 B: 物品) -- MONEY_D 货币对象创建",
        "SKILL_D(sname)->type() (层 E: 技能) -- UPDATE_D 区分 knowledge 技能",
        "set_skill (层 E: 技能) -- UPDATE_D 登录时技能封顶",
        "command_hook (层 C: 命令) -- ALIAS_D process_global_alias 在 command_hook 前调用",
        "go (层 D: 世界构建) -- ALIAS_D 方向别名最终展开为 go 命令",
        "LOGIN_D->make_body / LOGIN_OB (层 H) -- FINGER_D 离线玩家查询",
        "SECURITY_D->get_status (层 H) -- FINGER_D 显示权限等级",
        "GFINGER_Q (分布式网关，已砍) -- FINGER_D 跨 MUD 查询，新引擎预留",
        "LOGIN_D->find_body (层 H) -- vote.c 查找投票目标",
        "CHANNEL_D->do_channel (层 H-2) -- REGI_D 注册成功系统广播",
        "REGBAN_D->is_banned (层 H-2) -- REGI_D 邮箱封禁检查",
        "find_player / destruct (层 A/B) -- MARRY_D 配偶在线查找与对象销毁",
        "RANK_D->query_respect / query_close (层 H) -- EMOTE_D/INQUIRY_D 称谓替换",
        "gender_pronoun / gender_self (层 H) -- EMOTE_D 代词替换",
        "find_player (层 A/B) -- EMOTE_D do_intermud_emote 查找目标",
        "message_vision (层 B: F_MESSAGE) -- WEAPON_D bash_weapon 文本输出",
        "F_EQUIP / reset_action (层 B: 物品) -- WEAPON_D 武器卸除与动作重置",
        "message() / users() (层 B/A) -- ADS_D 广告广播",
        "call_out / remove_call_out (层 A: 驱动) -- ADS_D 阶段调度",
        "write_file / read_file / mkdir (层 A: 驱动) -- EDITOR_D 与 PROFILE_D 文件操作",
        "master object->compile_object (层 A: 驱动) -- VIRTUAL_D 占位回调",
    ],
    notes=(
        "层 H-2 覆盖第二梯队守护进程：频道、经济、登录归一化、全局别名、玩家查询、"
        "IP 封禁、注册、婚姻、表情、询问、拱猪、性能剖析、广告、编辑器、武器动作、"
        "编码转换、虚拟对象十七个子系统。所有规格均为函数级契约，不深入具体对象实现。"
        "InterMUD 相关调用按 04 / 09 决策视为已砍/预留，规格中只记录接口形态。"
    ),
)
