"""段 1 别名解析（ADR-0020 决策 1，LPC process_input 历史替换 + 全局方向别名）。

LPC ``process_input`` 处理优先级：刷屏检测 -> 历史替换 -> 自定义别名 -> 全局别名。
本段处理历史替换 + 全局方向别名（自定义别名后置，ADR-0020 不做清单）。

**全局方向别名**（LPC ``aliasd.c`` ``DIRECTION_ALIASES``，18 项）：
``n`` -> ``go north``、``e`` -> ``go east`` 等。命中时重写 verb + raw_args。
非方向别名（``l`` -> ``look``、``i`` -> ``inventory``）同样在此段处理。

**历史替换**（LPC ``!``/``!N``）：``!`` 替换为最近一条命令，``!N`` 替换为第 N 条。
阶段 1 最小：历史缓冲区由调用方维护，本段接收 ``history`` 参数做替换。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xkx.runtime.action_context import Abort, ActionContext

# 全局方向别名（提取自 LPC aliasd.c global_alias，spec/layer_c_command.py DIRECTION_ALIASES）
DIRECTION_ALIASES: dict[str, str] = {
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
}

# 非方向全局别名（提取自 LPC aliasd.c，spec/layer_c_command.py NON_DIRECTION_ALIASES）
NON_DIRECTION_ALIASES: dict[str, str] = {
    "l": "look",
    "i": "inventory",
}

# 合并全局别名表（段 1 查找用）
GLOBAL_ALIASES: dict[str, str] = {**DIRECTION_ALIASES, **NON_DIRECTION_ALIASES}


@dataclass
class AliasState:
    """别名解析状态（每 actor 一个，管线调度器持有）。"""

    history: list[str] = field(default_factory=list)
    """命令历史缓冲区（LPC HISTORY_BUFFER_SIZE=10，环形覆盖）。"""

    def push(self, cmd: str) -> None:
        """命令执行后写入历史（环形，保留最近 10 条）。"""
        self.history.append(cmd)
        if len(self.history) > 10:
            self.history.pop(0)

    def resolve_history(self, arg: str) -> str | None:
        """历史替换：``!`` -> 最近一条，``!N`` -> 第 N 条。无历史返回 None。"""
        if not arg.startswith("!"):
            return None
        rest = arg[1:]
        if rest == "":
            return self.history[-1] if self.history else None
        if rest.isdigit():
            idx = int(rest)
            if 1 <= idx <= len(self.history):
                return self.history[idx - 1]
            return None
        return None


def _split_verb_args(cmd: str) -> tuple[str, str]:
    """拆分命令字符串为 (verb, raw_args)。"""
    cmd = cmd.strip()
    if not cmd:
        return "", ""
    parts = cmd.split(None, 1)
    verb = parts[0]
    raw_args = parts[1] if len(parts) > 1 else ""
    return verb, raw_args


def alias_resolve(
    ctx: ActionContext, state: AliasState | None = None
) -> ActionContext | Abort:
    """段 1：别名解析（ADR-0020 决策 1）。

    处理顺序（LPC process_input）：
    1. 历史替换（``!``/``!N``，需 state）
    2. 全局方向别名（``n`` -> ``go north``）
    3. 非方向全局别名（``l`` -> ``look``）

    命中别名时重写 verb + raw_args（``dataclasses.replace`` 生成新 ctx）。
    无 state 时仅做全局别名解析（跳过历史替换）。
    """
    import dataclasses

    verb = ctx.verb
    raw_args = ctx.raw_args

    # 1. 历史替换（verb 以 ! 开头）
    if state is not None and verb.startswith("!"):
        replaced = state.resolve_history(verb)
        if replaced is None:
            return Abort(reason="history_empty", messages=["没有历史命令。"])
        new_verb, new_args = _split_verb_args(replaced)
        verb, raw_args = new_verb, new_args

    # 2 & 3. 全局别名（仅当 raw_args 为空时，别名是完整命令）
    # LPC process_global_alias 只替换首个词；若 verb 是别名键且无参数，重写为别名值
    if not raw_args and verb in GLOBAL_ALIASES:
        expanded = GLOBAL_ALIASES[verb]
        verb, raw_args = _split_verb_args(expanded)

    if verb == ctx.verb and raw_args == ctx.raw_args:
        return ctx  # 无变更
    return dataclasses.replace(ctx, verb=verb, raw_args=raw_args)
