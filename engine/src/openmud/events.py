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
``dispatch`` 的 fire-and-forget 形态已为它们留出"调用方自行取聚合"的空间：
08 号票据此落地了 ``handlers_for``（自取 handler 列表副本自行聚合，不改 on_tick
的用法），届时按需加返回值收集或调用方直接遍历。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openmud.world import World

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
        异常会传播（M1 fail-fast，让 bug 暴露而非静默吞掉）；遍历 ``handlers_for``
        返回的副本，使 handler 内部 ``register`` 的新 handler 不影响本次遍历。
        """
        for handler in self.handlers_for(event_name):
            handler(*args, **kwargs)

    def handlers_for(self, event_name: str) -> tuple[EventHandler, ...]:
        """返回某事件 key 的全部 handler（按注册顺序），未注册时返回空元组。

        返回元组副本（与 ``dispatch`` 同样的"遍历副本"安全性：handler 内部
        ``register`` 的新 handler 不影响调用方已拿到的这份）。供需要收集返回值或
        自定义聚合的调用方使用--08 号票命令 before/after 钩子：before 要短路否决、
        after 要折叠消息，都不是 fire-and-forget，故不走 ``dispatch`` 而是自取
        handler 列表自行聚合（07 号票已为此预留"调用方自行取聚合"的空间，不改
        on_tick 的用法）。
        """
        return tuple(self._handlers.get(event_name, ()))


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


# 可否决事件点的否决信号与聚合（32/33 号票）：领域 before 事件点
# （``on_before_enter_room`` / ``on_get`` / ``on_drop``）的 handler 返回 ``Deny``
# 即否决本次操作；``run_vetoable`` 按 ``handlers_for`` 遍历、首个 ``Deny`` 短路。
# ``Deny`` 跨命令前置钩子（``on_command_before``，commands._run_before_hooks）与领域
# before 事件点共用--两者都是"执行前可否决"语义；命令前置钩子的另两个返回态
# ``Allow``/``Replace`` 是命令前置钩子专属，留在 commands。``Deny`` 定义归 events
# （commands re-import 保持命令钩子 API），``run_vetoable`` 是 commands 与 transfer
# 的公共聚合（原 commands._run_vetoable / transfer._run_transfer_veto 两处重复实现，
# 33 号票收敛为单一实现）。
@dataclass(frozen=True)
class Deny:
    """否决信号：可否决事件点的 handler 返回它即否决本次操作。

    ``message`` 作为拒绝提示返回给玩家。
    """

    message: str


def run_vetoable(world: World, event_name: str, ctx: Any) -> str | None:
    """跑可否决领域事件点的全部 handler，返回首个 ``Deny`` 的 message 或 ``None``。

    与 ``commands._run_before_hooks`` 同模式（按注册顺序遍历、首个 ``Deny`` 短路、
    ``Allow``/``None`` 容错为放行），区别是 handler 收单个领域上下文
    （如 ``EnterRoomContext`` / ``TransferContext``）而非 ``(world, player, intent)``，
    且无 ``Replace``--领域级不改写语义（领域钩子不能把"进 A 房间"改写成"进 B"）。
    M1 默认无 handler 注册时返回 ``None``（放行，零回归）。
    """
    for handler in world.events.handlers_for(event_name):
        result = handler(ctx)
        if isinstance(result, Deny):
            return result.message
        # Allow / None：放行，继续下一个
    return None


__all__ = ["Deny", "EventBus", "EventHandler", "ON_TICK", "TickContext", "run_vetoable"]
