# 07 - 事件总线 + on_tick 订阅分发

**What to build:** 引入一个钩子注册表/事件总线（按事件 key 路由到 handler 列表,注册接口与 `commands.register` 同构,ADR-0004 的 `register_condition` 同源）,作为 ADR-0004"骨架固定 + 钩子策略注入"手法推广到非战斗系统的共同地基。第一个落地的事件点是 `on_tick`:`TickLoop.advance` 增加 `on_tick` 订阅者分发,`save_fn` 退化为 `on_tick` 的一个订阅者（或保留 `save_fn` 并额外分发 `on_tick`,实现阶段定,但 `on_tick` 分发机制必须就位）。M1 唯一订阅者仍是存档。

这是 B1 Nature 时辰推进 + D1 NPC 行为 + 未来 Effect 衰减的共同地基--不补则 B/C/D 要改 `TickLoop` 接口。

- **事件总线/钩子注册表**:按事件 key（如 `on_tick`）路由到 handler 列表;注册接口 `register_xxx(name, handler)` 与 `commands.register` 同构。
- **on_tick 分发接入 `TickLoop.advance`**:每次 advance 遍历 `on_tick` 订阅者调用。
- **save_fn 退化为 `on_tick` 的一个订阅者**（或并行保留,实现定）,现有周期存档行为不变（周期触发 + `force_save` 仍生效）。
- **事件点签名尽量通用**并加契约测试锁定形状（防 M2 引入真实规则时改接口,同原 spec"解析失败信号形状被测试锁定"思路）。

**Blocked by:** None - 可立即开始（A 块地基,无前置）。

**Status:** resolved

- [x] 存在钩子注册表/事件总线,支持按事件 key 注册 handler 与分发
- [x] 注册接口与 `commands.register` 同构（`register_xxx(name, handler)` 形态）
- [x] `TickLoop.advance` 每次推进时把 `on_tick` 事件分发给所有订阅者
- [x] 现有周期存档行为不变（`save_fn` 作为 `on_tick` 订阅者之一或等价机制,周期触发 + `force_save` 仍生效）
- [x] 注册一个测试 `on_tick` handler,调 `advance()`,断言 handler 被调用且收到正确的 tick 上下文参数
- [x] 事件点签名有契约测试锁定形状
- [x] 现有测试全绿（不回归）

## 实现决策（2026-07-19 resolved）

- **EventBus 挂 `World`**（`world.events`）而非模块级单例：实例隔离（每个 world 自己的订阅者、测试间不泄漏、对应 CLAUDE.md 不变量 6"世界实例隔离"）；不进存档（save.py 只序列化 entities/components），restore 后为空，订阅者由各子系统在启动/restore 后重新注册。`events.py` 运行时不 import world（`from __future__ import annotations` + TYPE_CHECKING），无循环 import。
- **save_fn 路线选"保留 save_fn + 额外分发 on_tick"**（issue 允许的"等价机制"），不选"save 退化为 on_tick 订阅者"：`force_save` 语义清晰（退出前立即存档不分发 on_tick、不触发世界推进副作用）、save 的周期触发逻辑（interval）天然留在 TickLoop、05 号票行为零回归（`world` 可选，不传时 advance 只做周期存档）。M1 生产代码里 on_tick 暂无订阅者，事件总线机制就位为未来 Nature/NPC/Effect 衰减预留统一驱动点。
- **`TickContext` frozen dataclass（tick + world）**，契约测试锁定形状（test_events `TestTickContextContract`）；未来加字段不破坏 `handler(context)` 签名。`ON_TICK = "on_tick"` 常量锁定事件名。
- **`dispatch` fire-and-forget 不短路**（§12 多规则按 any/all 聚合不互斥）；遍历前复制 handler 列表防 handler 内部 register 干扰本次遍历。on_tick 分发在周期存档之前（未来订阅者推进态被同 tick 存档捕获）。
- **不预支**：未做命令 before/after、移动/物品/门事件点（08/09 号票）、when/do 规则引擎、受限 Python 钩子沙箱、Effect 系统、AST 解析器。
