"""层 C-VOTE：玩家自治投票系统 -- LPC 规格提取（ADR-0055）。

覆盖范围：
- ``cmds/std/vote.c`` -- vote 命令调度器 + ``valid_voters``
- ``cmds/std/vote/chblk.c`` -- 关闭频道投票
- ``cmds/std/vote/unchblk.c`` -- 打开频道投票
- ``kungfu/condition/vote_clear.c`` -- 投票过期/取消 condition
- ``kungfu/condition/vote_suspension.c`` -- 投票权剥夺 condition
- ``include/vote.h`` -- 投票常量

核心契约要点：
1. **vote.c 是调度器**：解析 ``vote <动议> <目标>``，动态加载
   ``/cmds/std/vote/<动议>.c`` 并调用 ``file_ob->vote(me, victim)``。
2. **投票资格**：age >=16 且未被剥夺投票权（``vote/deprived``）且非登录中
   （有 environment）。巫师不受年龄限制。
3. **滥用惩罚**：子命令返回 <=0 时若 ``vote/abuse" > 50，则剥夺投票权
   （``vote/deprived=1``）并施加 ``vote_suspension`` condition（120 ticks）。
4. **一人一票**：每个 vote/juror 数组记录投票者 ID，重复投票增加 abuse。
5. **chblk 阈值**：``valid_voters/4``，最低 4 票；unchblk 阈值：
   ``valid_voters/6``，最低 4 票。
6. **vote_clear condition**：duration <1 时清理 vote/reason、vote/juror、
   vote/count；duration > -5 表示因响应不足取消；duration <= -5 表示已通过。
7. **vote_suspension condition**：duration <1 时恢复投票权（删除 vote/deprived）。

不做（边界）：
- ``eject`` / ``jail`` 动议未实现，只记录常量预留。
- 投票动议的扩展（新增子命令）不属于本层核心契约，由内容层决定。
- condition 系统的通用 apply/update/clear 机制属层 E/F 框架，本层只记录 vote
  相关 condition 的行为。
"""

from __future__ import annotations

from enum import IntEnum

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
# 投票常量（来自 include/vote.h）
# ---------------------------------------------------------------------------


class VoteReason(IntEnum):
    """投票原因常量。"""

    FAIL = 0
    """投票失败/无。"""

    EJECT = 5
    """驱逐（未实现）。"""

    CHBLK = 6
    """关闭频道。"""

    UNCHBLK = 7
    """打开频道。"""

    ROBOT = 8
    """反机器人（未实现）。"""


class VoteThreshold(IntEnum):
    """投票阈值类型常量。"""

    ONETHIRD = 1
    HALF = 2
    TWOTHIRD = 3
    FIVE = 4


VOTE_MIN_VOTES: int = 3
"""vote.h 中 V_MIN：历史最小票数常量。"""

# ---------------------------------------------------------------------------
# vote.c 调度器规格
# ---------------------------------------------------------------------------

_vote_main = FunctionSpec(
    signature=FunctionSignature(
        name="main",
        params=[
            LPCParam(name="me", lpc_type="object", description="投票玩家"),
            LPCParam(name="arg", lpc_type="string", description="动议与目标，格式 '<动议> <目标>'"),
        ],
        return_type="int",
        lpc_file="cmds/std/vote.c",
        line_range=(14, 72),
    ),
    preconditions=[
        Precondition(description="me 为有效玩家对象", kind="require"),
        Precondition(description="age >=16 或巫师", kind="guard"),
        Precondition(description="vote/deprived 为 0", kind="guard"),
        Precondition(
            description="arg 可解析为 '<动议> <目标>' 且对应 .c 文件存在",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="投票成功时返回 1",
            kind="ensure",
        ),
        Postcondition(
            description="资格不符、文件不存在或子命令失败时返回 0 或 notify_fail",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="一人一票：重复投票由子命令通过 vote/juror 控制",
            scope="system",
        ),
        Invariant(
            description="滥用计数 vote/abuse >50 触发投票权剥夺",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="年龄/剥夺状态检查失败时返回 notify_fail",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="解析 arg 得到 act_name 与 victim_name",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="LOGIN_D->find_body 查找 victim",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="动态加载并调用 /cmds/std/vote/<act_name>.c->vote(me, victim)",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="子命令失败且 abuse >50 时设置 vote/deprived、施加 vote_suspension、清空 abuse",
            target="me",
        ),
    ],
    random_specs=[],
    notes="调度器本身不做一人一票检查，全部委托给子命令。",
)

_valid_voters = FunctionSpec(
    signature=FunctionSignature(
        name="valid_voters",
        params=[
            LPCParam(name="me", lpc_type="object", description="请求计数的玩家对象"),
        ],
        return_type="int",
        lpc_file="cmds/std/vote.c",
        line_range=(75, 95),
    ),
    preconditions=[
        Precondition(description="me 为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="返回满足投票资格的在线用户数量",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只统计有 environment 的在线用户",
            scope="function",
        ),
        Invariant(
            description="age <16 且非巫师、或被剥夺投票权的用户被排除",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="纯计数函数，无状态副作用。",
)

# ---------------------------------------------------------------------------
# chblk.c 规格
# ---------------------------------------------------------------------------

_chblk_vote = FunctionSpec(
    signature=FunctionSignature(
        name="vote",
        params=[
            LPCParam(name="me", lpc_type="object", description="投票者"),
            LPCParam(name="victim", lpc_type="object", description="被投票关闭频道者"),
        ],
        return_type="int",
        lpc_file="cmds/std/vote/chblk.c",
        line_range=(10, 84),
    ),
    preconditions=[
        Precondition(description="me 与 victim 为有效对象", kind="require"),
        Precondition(description="me != victim（自投增加 abuse）", kind="guard"),
        Precondition(
            description="victim 当前无其它进行中的投票或原因同为 V_CHBLK",
            kind="guard",
        ),
        Precondition(description="victim 频道未已被关闭", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="投票数达到阈值时设置 chblk_on=1 并清理各子频道阻塞标记",
            kind="effect",
        ),
        Postcondition(
            description="未达阈值时应用 vote_clear condition（duration=10）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="chblk 阈值 = max(valid_voters/4, 4)",
            scope="function",
        ),
        Invariant(
            description="一人一票：me->id 必须不在 victim->vote/juror 中",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="自投时以 50% 概率增加 vote/abuse",
            target="me",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="检查当前 vote/reason 是否冲突",
            target="victim",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 vote/reason = V_CHBLK",
            target="victim",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="将 me->id 加入 vote/juror",
            target="victim",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="vote/count 加 1",
            target="victim",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="shout/write 广播当前还差票数",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="未通过时 apply_condition('vote_clear', 10)",
            target="victim",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="通过时 apply_condition('vote_clear', -10) 并设置 chblk_on=1，清理子频道标记",
            target="victim",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(2)",
            probability_model="50%",
            semantic="自投时的 abuse 增加判定",
            seed_inputs=[],
            determinism_note="非战斗随机性，玩家行为惩罚",
        ),
    ],
    notes="chblk 禁止自投；unchblk 允许自投。",
)

# ---------------------------------------------------------------------------
# unchblk.c 规格
# ---------------------------------------------------------------------------

_unchblk_vote = FunctionSpec(
    signature=FunctionSignature(
        name="vote",
        params=[
            LPCParam(name="me", lpc_type="object", description="投票者"),
            LPCParam(name="victim", lpc_type="object", description="被投票打开频道者，允许等于 me"),
        ],
        return_type="int",
        lpc_file="cmds/std/vote/unchblk.c",
        line_range=(11, 104),
    ),
    preconditions=[
        Precondition(description="me 与 victim 为有效对象", kind="require"),
        Precondition(
            description="victim 当前无其它进行中的投票或原因同为 V_UNCHBLK",
            kind="guard",
        ),
        Precondition(description="victim 至少有一个频道被阻塞", kind="guard"),
    ],
    postconditions=[
        Postcondition(
            description="投票数达到阈值时清理所有 chblk_* 标记",
            kind="effect",
        ),
        Postcondition(
            description="未达阈值时应用 vote_clear condition（duration=10）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="unchblk 阈值 = max(valid_voters/6, 4)",
            scope="function",
        ),
        Invariant(
            description="一人一票：me->id 必须不在 victim->vote/juror 中",
            scope="function",
        ),
        Invariant(
            description="允许自投打开自己的频道",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="检查当前 vote/reason 是否冲突",
            target="victim",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 vote/reason = V_UNCHBLK",
            target="victim",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="将 me->id 加入 vote/juror",
            target="victim",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="vote/count 加 1",
            target="victim",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="shout/write 广播当前还差票数",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="未通过时 apply_condition('vote_clear', 10)",
            target="victim",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="通过时 apply_condition('vote_clear', -10) 并清理所有 chblk_* 标记",
            target="victim",
        ),
    ],
    random_specs=[],
    notes="unchblk 自投时消息中显示'自己'。",
)

# ---------------------------------------------------------------------------
# vote_clear condition 规格
# ---------------------------------------------------------------------------

_vote_clear_update = FunctionSpec(
    signature=FunctionSignature(
        name="update_condition",
        params=[
            LPCParam(name="me", lpc_type="object", description="condition 持有者"),
            LPCParam(name="duration", lpc_type="int", description="剩余 tick 数；负值表示已通过"),
        ],
        return_type="int",
        lpc_file="kungfu/condition/vote_clear.c",
        line_range=(8, 26),
    ),
    preconditions=[
        Precondition(description="me 为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="duration <1 时清理 vote/reason/juror/count 并返回 0",
            kind="ensure",
        ),
        Postcondition(
            description="duration > -5 且 <1 时广播'投票取消'",
            kind="ensure",
        ),
        Postcondition(
            description="duration <= -5 时不广播取消消息（已通过）",
            kind="ensure",
        ),
        Postcondition(
            description="duration >=1 时重新 apply_condition('vote_clear', duration-1) 并返回 1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="duration > -5 且 <1 时广播'投票取消'",
            scope="function",
        ),
        Invariant(
            description="duration <= -5 时不广播取消消息（已通过）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="duration > -5 且 <1 时 shout 与 tell_object 投票取消",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 vote/reason、vote/juror、vote/count",
            target="me",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="duration >=1 时递归 apply_condition 递减 duration",
            target="me",
        ),
    ],
    random_specs=[],
    notes="负 duration 是 vote 子命令在通过时设置的标记。",
)

# ---------------------------------------------------------------------------
# vote_suspension condition 规格
# ---------------------------------------------------------------------------

_vote_suspension_update = FunctionSpec(
    signature=FunctionSignature(
        name="update_condition",
        params=[
            LPCParam(name="me", lpc_type="object", description="condition 持有者"),
            LPCParam(name="duration", lpc_type="int", description="剩余 tick 数"),
        ],
        return_type="int",
        lpc_file="kungfu/condition/vote_suspension.c",
        line_range=(7, 16),
    ),
    preconditions=[
        Precondition(description="me 为有效对象", kind="require"),
    ],
    postconditions=[
        Postcondition(
            description="duration <1 时删除 vote/deprived 并返回 0",
            kind="ensure",
        ),
        Postcondition(
            description="duration >=1 时递归 apply_condition('vote_suspension', duration-1) 并返回 1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="观察期结束自动恢复投票权",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="duration <1 时 tell_object 恢复投票权",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 vote/deprived",
            target="me",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="duration >=1 时递归 apply_condition 递减 duration",
            target="me",
        ),
    ],
    random_specs=[],
    notes="由 vote.c 在 abuse >50 时施加，duration=120。",
)

# ---------------------------------------------------------------------------
# 层 C-VOTE 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="C-VOTE",
    layer_name="玩家自治投票系统",
    lpc_files=[
        "cmds/std/vote.c",
        "cmds/std/vote/chblk.c",
        "cmds/std/vote/unchblk.c",
        "kungfu/condition/vote_clear.c",
        "kungfu/condition/vote_suspension.c",
        "include/vote.h",
    ],
    function_specs=[
        _vote_main,
        _valid_voters,
        _chblk_vote,
        _unchblk_vote,
        _vote_clear_update,
        _vote_suspension_update,
    ],
    cross_layer_refs=[
        "LOGIN_D->find_body (层 H) -- vote.c 查找投票目标",
        "CHANNEL_D->do_channel (层 H-2) -- vote.c 滥用惩罚触发 sys 广播（实际代码在 vote.c 子命令返回失败路径，但 CHANNEL_D 是最终广播者）",
        "chinese_number (层 H: CHINESE_D) -- chblk/unchblk 广播票数中文",
        "shout / write / tell_object (层 B: F_MESSAGE) -- vote 广播与通知",
        "apply_condition (层 E/F: condition 框架) -- vote_clear / vote_suspension 调度",
        "command_hook (层 C: 命令) -- vote 作为标准命令被 command_hook 调用",
        "valid_cmd (层 H: SECURITY_D) -- vote 命令需过权限校验",
    ],
    notes=(
        "层 C-VOTE 覆盖玩家自治投票的最小可玩子集：chblk / unchblk。"
        "eject / jail / robot 动议在 vote.h 中预留常量但无对应实现文件，"
        "本层只记录为'未实现'。"
    ),
)
