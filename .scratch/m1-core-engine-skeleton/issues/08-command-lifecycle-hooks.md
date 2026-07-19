# 08 - 命令生命周期钩子 before/after

**What to build:** 在 `commands.execute` 外包一层 `on_command_before` / `on_command_after` 钩子环绕（调研指出当前 `execute` 是 `handler(world, player_id, intent)` 直接调用、无 before/after 环绕,是缺的核心基础设施;对应 Inform 7 四段式的"前置校验 -> 执行 -> 后置通知"精炼）。前置 `on_command_before` 返回 `Allow` / `Deny` / `Replace`（M1 默认 `Allow` 直接放行）;后置 `on_command_after` 可修饰消息列表。M1 空实现不改现有 11 个命令的行为。

这是"夜里 NPC 不卖酒""诅咒物品拿不起"等前置否决规则的挂载点--不补则 M2 引入时改 `execute` 签名。

- **on_command_before(world, player, intent) -> Allow | Deny | Replace**:M1 默认 `Allow`;`Deny` 否决并返回拒绝消息;`Replace` 替换意图。
- **on_command_after(world, player, intent, messages) -> messages**:可修饰返回消息。
- **挂在 `commands.execute` 外**（或 `parsing.execute_line` 调 `execute` 处）,现有命令行为不变。
- **签名通用 + 契约测试锁定**形状。

**Blocked by:** 07 - 复用其事件总线/钩子注册表基础设施注册命令生命周期 handler。

**Status:** ready-for-agent

- [ ] `commands.execute` 外包 `on_command_before` / `on_command_after` 环绕
- [ ] `on_command_before` 返回 `Allow` / `Deny` / `Replace`,M1 默认 `Allow` 放行
- [ ] 注册一个 deny handler 拦截某命令,该命令被否决并返回拒绝提示
- [ ] 注册一个 after handler 修饰某命令返回的消息,消息被正确修饰
- [ ] 不注册任何 handler 时,现有 11 个命令行为完全不变
- [ ] 签名有契约测试锁定形状
- [ ] 现有测试全绿（不回归）
