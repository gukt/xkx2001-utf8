# 08 - 命令生命周期钩子 before/after

**What to build:** 在 `commands.execute` 外包一层 `on_command_before` / `on_command_after` 钩子环绕（调研指出当前 `execute` 是 `handler(world, player_id, intent)` 直接调用、无 before/after 环绕,是缺的核心基础设施;对应 Inform 7 四段式的"前置校验 -> 执行 -> 后置通知"精炼）。前置 `on_command_before` 返回 `Allow` / `Deny` / `Replace`（M1 默认 `Allow` 直接放行）;后置 `on_command_after` 可修饰消息列表。M1 空实现不改现有 11 个命令的行为。

这是"夜里 NPC 不卖酒""诅咒物品拿不起"等前置否决规则的挂载点--不补则 M2 引入时改 `execute` 签名。

- **on_command_before(world, player, intent) -> Allow | Deny | Replace**:M1 默认 `Allow`;`Deny` 否决并返回拒绝消息;`Replace` 替换意图。
- **on_command_after(world, player, intent, messages) -> messages**:可修饰返回消息。
- **挂在 `commands.execute` 外**（或 `parsing.execute_line` 调 `execute` 处）,现有命令行为不变。
- **签名通用 + 契约测试锁定**形状。

**Blocked by:** 07 - 复用其事件总线/钩子注册表基础设施注册命令生命周期 handler。

**Status:** resolved

- [x] `commands.execute` 外包 `on_command_before` / `on_command_after` 环绕
- [x] `on_command_before` 返回 `Allow` / `Deny` / `Replace`,M1 默认 `Allow` 放行
- [x] 注册一个 deny handler 拦截某命令,该命令被否决并返回拒绝提示
- [x] 注册一个 after handler 修饰某命令返回的消息,消息被正确修饰
- [x] 不注册任何 handler 时,现有 11 个命令行为完全不变
- [x] 签名有契约测试锁定形状
- [x] 现有测试全绿（不回归）

## 实现决策（2026-07-19 resolved）

- **挂载点选 `commands.execute` 内部**（issue 允许的"execute 外"或"execute_line 调 execute 处"两选其一）而非 `parsing.execute_line`：`execute` 已持 `world`（钩子要走 `world.events`）、是"执行意图"的单一咽喉，`execute_line`（解析+执行）与未来 NPC 直接调 `execute`（如 auto-perform 一个 buy）都自动过钩子。`_cmd_go` 移动后自动 `_cmd_look` 是直接调处理函数不经 `execute`，故不被 before/after 包（auto-look 属 `go` 实现细节非独立玩家命令；M2 若要 auto-look 过钩子再单独议）。
- **复用 07 的 `world.events` 注册表**（`register(ON_COMMAND_BEFORE, handler)` 与 `commands.register` 同构、与 ADR-0004 `register_condition` 同源），不另起注册表。给 `EventBus` 加 `handlers_for(event_name) -> tuple[handler, ...]`（返回副本）暴露 handler 列表：before 要否决短路、after 要折叠消息，都不是 fire-and-forget，故不走 `dispatch` 而自取列表自行聚合（07 已为"调用方自行取聚合"预留空间）；`dispatch` 顺手 DRY 复用 `handlers_for`，on_tick 行为零回归。
- **`Allow` / `Deny(message)` / `Replace(intent)` 三态用 frozen dataclass**（非 Enum：三者载荷不同--Deny 带消息、Replace 带意图、Allow 无载荷，union of dataclasses 比 Enum 干净）。形状被 `TestCommandLifecycleContract` 契约锁定（常量 + frozen + 字段，同 `TestTickContextContract` 思路）。
- **before 聚合**：按注册顺序遍历，`Replace` 改写"生效意图"（后续钩子看到改写后的、链式传递），首个 `Deny` 即否决并**短路**（其后钩子不跑）。`Allow` / `None`（容错忘写 return）都视为放行。短路否决与 07 的 on_tick fire-and-forget 不矛盾--on_tick 的订阅者是观察者不否决，before 的钩子是投票者，07 明确把 before/after 的聚合留给"调用方自行取"。
- **`Replace` 改写动词后按生效意图重新解析处理函数**（实现中由测试抓出的真 bug：原按原动词查的 handler 执行改写后的意图是错的）。原动词未知时 before/after 不挂（否决一个不存在的命令无意义）；`Replace` 改写到未知动词按生效意图给未知命令提示（不崩溃）。
- **`Deny` 跳过 after**：处理函数没跑就没有"后置"可通知，拒绝消息原样返回。
- **钩子挂 `world.events` 天然实例隔离**（07 设计的回报）：每 `build_world()` 一个新 world 一个空 `EventBus`，测试间不泄漏、无需 finally 清理（对比 commands._REGISTRY 模块级要清）。`TestHookIsolationBetweenWorlds` 锁这条。
