"""段 0 刷屏检测（ADR-0020 决策 1，LPC process_input cnt 计数）。

LPC ``process_input`` 维护 tick 内命令计数，超过 ``CMDS_PER_TICK``（20）开始扣气/精，
超过 ``3*CMDS_PER_TICK``（60）触发天雷惩罚（50% 概率昏迷 + 强制 quit）。

阶段 1 最小实现（收敛优先于完备）：

- 计数 + 阈值检测，超阈值返回 Abort（命令丢弃）。
- 扣气/精 + 天雷惩罚后置（需 Vitals/天雷系统，阶段 2/M3）。
- tick 重置由调用方（管线调度器）每 tick 调 ``reset_flood_counter``。

刷屏检测必须最先（段顺序不变量），防刷屏命令绕过权限校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xkx.runtime.action_context import Abort, ActionContext

# LPC CMDS_PER_TICK = 20（feature/alias.c）
CMDS_PER_TICK = 20
# 超过 3*CMDS_PER_TICK 触发天雷（阶段 1 最小：Abort 命令）
FLOOD_HARD_LIMIT = 3 * CMDS_PER_TICK


@dataclass
class FloodState:
    """刷屏检测状态（每 actor 一个，管线调度器持有）。"""

    count: int = 0
    """tick 内已执行命令数。"""

    warned: bool = False
    """是否已发刷屏警告（避免重复刷屏消息）。"""

    messages: list[str] = field(default_factory=list)
    """本 tick 累积的刷屏警告消息。"""


def flood_check(ctx: ActionContext, state: FloodState | None = None) -> ActionContext | Abort:
    """段 0：刷屏检测（ADR-0020 决策 1）。

    阶段 1 最小：超过 ``FLOOD_HARD_LIMIT`` 返回 Abort（命令丢弃）。
    超过 ``CMDS_PER_TICK`` 追加警告消息（不 Abort，命令继续）。
    无 state 时跳过检测（测试/PrivilegedAction 路径可传 None）。
    """
    if state is None:
        return ctx  # 无状态对象，跳过刷屏检测（测试路径）
    state.count += 1
    if state.count > FLOOD_HARD_LIMIT:
        return Abort(
            reason="flood_hard_limit",
            messages=["你输入指令太快，被天雷劈中，昏迷过去。"],
        )
    if state.count > CMDS_PER_TICK and not state.warned:
        state.warned = True
        # 阶段 1 最小：仅标记，不扣气/精（后置阶段 2/M3 补 receive_damage）
        # 消息不进 ctx.result（刷屏警告是 process_input 阶段，命令尚未执行）
        state.messages.append("你输入指令太频繁了，请稍候。")
    return ctx


def reset_flood_counter(state: FloodState) -> None:
    """tick 重置刷屏计数（LPC ``clear_cmd_count`` 每 tick 减 2*CMDS_PER_TICK）。

    阶段 1 最小：直接清零（LPC 是递减，等价语义）。
    """
    state.count = 0
    state.warned = False
    state.messages.clear()
