"""段 5 参数解析（ADR-0020 决策 1，引号感知 tokenizer 替代 split()）。

LPC 命令 main 函数接收原始 arg 字符串，各命令自行 ``split()`` 拆空格（12 文档技术债）。
新引擎段 5 统一用引号感知 tokenizer 解析 ``raw_args`` -> ``parsed_args``（list[str]），
替代各命令散乱的 ``split()``。

阶段 1 最小集（ADR-0020 不做全量 LPC parse_command）：

- 空格分割 token
- 双引号包裹的 token 保留内部空格（如 ``give npc "long sword"`` -> ``["npc", "long sword"]``）

不实现完整 LPC ``parse_command``（介词/量词/指代语义后置）。
"""

from __future__ import annotations

from xkx.runtime.action_context import ActionContext


def tokenize_args(raw: str) -> list[str]:
    """引号感知 tokenizer（ADR-0020 决策 1）。

    空格分割 + 双引号包裹保留内部空格。示例：
    - ``"north"`` -> ``["north"]``
    - ``"npc long sword"`` -> ``["npc", "long", "sword"]``
    - ``'npc "long sword"'`` -> ``["npc", "long sword"]``

    不剥离引号外的成对引号字符（引号仅作分组语义，不出现在结果 token 中）。
    未闭合引号按剩余字符串作为一个 token（容错，LPC parse_command 容错语义）。
    """
    tokens: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        # 跳过前导空白
        while i < n and raw[i].isspace():
            i += 1
        if i >= n:
            break
        if raw[i] == '"':
            # 双引号分组
            i += 1  # 跳过开引号
            start = i
            while i < n and raw[i] != '"':
                i += 1
            tokens.append(raw[start:i])
            if i < n:
                i += 1  # 跳过闭引号
        else:
            # 普通 token
            start = i
            while i < n and not raw[i].isspace():
                i += 1
            tokens.append(raw[start:i])
    return tokens


def parse_args(ctx: ActionContext) -> ActionContext:
    """段 5：参数解析（ADR-0020 决策 1）。

    引号感知 tokenizer 解析 ``ctx.raw_args`` -> ``ctx.parsed_args``。
    纯函数，不会 Abort（参数解析失败不短路，留给终端命令处理）。
    """
    import dataclasses

    parsed = tokenize_args(ctx.raw_args)
    return dataclasses.replace(ctx, parsed_args=parsed)
