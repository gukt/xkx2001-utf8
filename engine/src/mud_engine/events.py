"""事件总线 / 钩子注册表：按事件 key 路由到 handler 列表（07 号票，块 A 地基）。

ADR-0004 拍板的"骨架固定 + 钩子策略注入"手法三要素（声明式 policy 枚举 +
Protocol 钩子 + 注册表注入 ``register_condition``）推广到非战斗系统的共同地基。
本模块是"注册表注入"那条：题材包 / 子系统把自己的策略钩子按事件 key 挂进引擎，
引擎不知具体实现（spec 块 A user story 7、12）。

第一个落地的事件点是 ``on_tick``（见 tick.py：``TickLoop.advance`` 分发）。本票 M1
阶段唯一"随时间演化"的系统仍是存档，且存档继续走 ``save_fn``（issue 验收 #4
"或等价机制"允许保留 save_fn 并额外分发 on_tick--``force_save`` 语义清晰、周期
触发逻辑天然留在 TickLoop、现有 05 号票行为零回归）；on_tick 在生产代码里暂无
订阅者。事件总线机制就位后，未来 Nature 时辰推进（块 B）、NPC 行为（块 D）、
Effect 衰减（ADR-0004）都挂在同一个统一驱动点上，不需要回头改 TickLoop 接口
（spec 块 A user story 2、§8"随时间推进类规则必须挂 tick"）。

注册接口与 ``commands.register`` 同构、与 ADR-0004 ``register_condition`` 同源：
按 key 注册 handler。``dispatch`` 遍历该 key 的全部 handler 按注册顺序调用、
**不短路**（§12 多规则按 any/all 聚合不互斥，订阅者各自独立作用，一个 handler
不阻断其他 handler 被通知）。M1 只落地 on_tick 一个事件点；命令 before/after、
移动 / 物品 / 门事件点（含可否决聚合）是 08 / 09 号票的范围，本票不实现，但
``dispatch`` 的 fire-and-forget 形态已为它们留出"调用方自行取聚合"的空间
（届时按需加返回值收集或调用方直接遍历，不改 on_tick 的用法）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mud_engine.world import World

# 事件点 handler 签名：接收事件点约定的参数。用 ``Callable[..., None]`` 而非钉死
# 某组参数--不同事件点签名不同（on_tick 收一个 TickContext；未来命令前置收
# (world, player, intent)），事件总线只管按 key 路由，不关心具体签名形状（形状
# 由各事件点的契约测试锁定，见 TestTickContextContract）。
EventHandler = Callable[..., None]


class EventBus:
    """按事件 key 路由到 handler 列表的注册表，挂在 ``World`` 上（实例隔离）。

    挂在 World 而非模块级单例（如 commands._REGISTRY）：commands 是引擎内置的
    固定命令集，全局共享合理；事件总线的订阅者是运行时挂载的策略 / 钩子，属于
    world 运行时态，挂在 world 上让每个 world 有自己的订阅者、测试间不泄漏、
    未来多世界实例（CLAUDE.md 架构不变量第 6 条"世界实例隔离"）天然隔离。
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_name: str, handler: EventHandler) -> None:
        """把 handler 注册到某事件 key（追加到列表末尾，调用时按注册顺序）。

        与 ``commands.register`` 同构、与 ADR-0004 ``register_condition`` 同源
        （按 key 注册 handler 到注册表）。同一 handler 注册两次会被调用两次
        （不去重--注册即订阅，语义明确）。
        """
        self._handlers.setdefault(event_name, []).append(handler)

    def dispatch(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """把某事件分发给它的全部 handler，按注册顺序逐个调用。

        fire-and-forget：不收集返回值、不短路（§12 多规则不互斥）。handler 抛
        异常会传播（M1 fail-fast，让 bug 暴露而非静默吞掉）；遍历前复制一份
        handler 列表，使 handler 内部 ``register`` 的新 handler 不影响本次遍历。
        """
        for handler in list(self._handlers.get(event_name, ())):
            handler(*args, **kwargs)


# on_tick 事件名常量：``TickLoop.advance`` 每次推进时分发此事件，订阅者收一个
# ``TickContext``。M1 阶段存档走 save_fn 不订阅 on_tick；on_tick 为未来 Nature 时辰
# 推进 / NPC 行为 / Effect 衰减预留统一驱动点（spec 块 A user story 2）。
ON_TICK = "on_tick"


@dataclass(frozen=True)
class TickContext:
    """on_tick 分发给订阅者的 tick 上下文。形状被契约测试锁定（test_events）。

    frozen dataclass：M1 只有 ``tick`` + ``world``，未来加 ``dt`` / ``nature_state``
    等字段不破坏 handler 签名（``handler(context)`` 不变，只读自己要的字段）。这是
    spec 块 A user story 6"事件点签名尽量通用 + 契约测试锁定形状，防 M2 改接口"。

    ``world`` 用 ``from __future__ import annotations`` 延迟求值，运行时 events 模块
    不 import world（避免 world <-> events 循环 import）。
    """

    tick: int
    world: World


__all__ = ["EventBus", "EventHandler", "ON_TICK", "TickContext"]
