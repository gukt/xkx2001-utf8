"""命令 8 段管线数据信封 ActionContext + Abort 信号（阶段 1 Wave 2 T4，ADR-0020）。

ActionContext 是 8 段中间件管线的数据信封（非类层级，Q3 裁决"不另起类抽象"）。
携带三元组 actor/source/viewer/target + CapabilityToken + seq + result/effects。

**三元组语义**（PronounContext 不变量，ADR-0021）：

- ``actor``：命令发起者（LPC ``this_player()`` / ``this_object()``）。
- ``source``：调用源（LPC ``previous_object()``，greenfield 显式传参）。
- ``viewer``：代词求值观察者（LPC ``rankd.c`` / ``visible`` 中的 ``this_player()``）。
  玩家命令路径下 viewer == actor；PrivilegedAction 路径下 viewer == actor（被代执行者）。
- ``target``：命令目标（LPC ``visible(me, ob)`` 的 ``ob``），None=无目标命令。

**不变量**：

- actor/viewer/source 在段 6 注入完成，段 7 执行段可依赖三者已就位。
- PronounContext 求值必须从 ActionContext.viewer 取，不得从全局 this_player() 取
  （greenfield 无全局 this_player()，单进程 asyncio 下无等价物）。
- capability_token 段 2 注入，段 3-7 可读不可改（frozen dataclass）。

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md)
[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xkx.combat.result import Effect
    from xkx.runtime.capability import CapabilityToken


@dataclass(frozen=True, slots=True)
class Abort:
    """管线短路信号（任一段返回 Abort 则管线终止，后续段不执行）。

    ``reason`` 是短路原因（权限不足 / 命令未找到 / 刷屏超限等）。
    ``messages`` 是要返回给调用方的提示消息（如"命令不存在"）。
    """

    reason: str
    messages: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ActionContext:
    """8 段管线数据信封（ADR-0020 决策 2）。

    frozen dataclass，段间传递用 ``dataclasses.replace`` 生成新实例（不可变）。
    段 0-6 各段是纯函数 ``(ctx) -> ActionContext | Abort``，段 7 执行 + 审计。
    """

    verb: str
    """命令动词（LPC ``query_verb()``）。"""

    raw_args: str
    """原始参数（去动词后的剩余字符串）。"""

    parsed_args: list[str]
    """段 5 解析后参数（引号感知 tokenizer 产出）。"""

    actor: int
    """发起者 entity_id（LPC ``this_player()`` / ``this_object()``）。"""

    source: int
    """调用源 entity_id（LPC ``previous_object()``，ADR-0021 显式化）。
    玩家命令路径下 source == actor；PrivilegedAction 路径下 source == 系统调用者。"""

    viewer: int
    """观察者 entity_id（PronounContext 不变量，``rankd``/``visible`` 的 viewer）。
    玩家命令路径下 viewer == actor；PrivilegedAction 路径下 viewer == actor。"""

    target: int | None
    """目标 entity_id（LPC ``visible(me, ob)`` 的 ``ob``），None=无目标命令。"""

    capability_token: CapabilityToken | None
    """段 2 注入的能力令牌，None=未授权（fail-closed）。"""

    seq: int
    """命令序列号（input log 重放用，每条命令递增）。"""

    result: list[str] = field(default_factory=list)
    """段 7 执行产出消息。"""

    effects: list[Effect] = field(default_factory=list)
    """段 7 执行产出的副作用账本。"""

    # 段 3 注入：查找到的命令执行函数（终端执行段）
    command_fn: Any | None = None
    """段 3 命令查找注入的终端执行函数 ``(game, ctx) -> list[str]``。None=未找到。"""


def new_context(
    *,
    verb: str,
    raw_args: str,
    actor: int,
    source: int | None = None,
    viewer: int | None = None,
    target: int | None = None,
    capability_token: CapabilityToken | None = None,
    seq: int = 0,
) -> ActionContext:
    """构造初始 ActionContext（段 0 入口）。

    ``source``/``viewer`` 默认 = ``actor``（玩家命令路径下三者相同）。
    PrivilegedAction 路径显式传 ``source=系统调用者``。
    """
    return ActionContext(
        verb=verb,
        raw_args=raw_args,
        parsed_args=[],
        actor=actor,
        source=source if source is not None else actor,
        viewer=viewer if viewer is not None else actor,
        target=target,
        capability_token=capability_token,
        seq=seq,
    )
