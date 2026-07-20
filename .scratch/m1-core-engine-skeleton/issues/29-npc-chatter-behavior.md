# 29 - Chatter 行为（D5，DSL 动态规则试金石）

**What to build:** NPC 挂 Chatter 行为（预设消息列表 + 触发概率），tick 时按概率 `say` 一条。行为条件（如「只在夜里」「只在玩家在场」）用条件求值器表达。第一个不依赖战斗/状态/死亡的行为，验证事件点 + 条件求值器 + 注册表注入手法。

**Blocked by:** 25 - Behavior/AIController 骨架；28 - say 广播通道；10 - 条件求值器（行为条件）。

**Status:** resolved

- [x] Chatter 行为可经 YAML/组件配置（消息列表 + 概率）
- [x] `advance()` 驱动下 Chatter 会触发 say（测试用确定性概率或断言至少触发）
- [x] 行为条件用条件求值器表达（如只在夜里才闲聊）
- [x] 无 AIController / 无 Chatter 的 NPC 不说话
- [x] 经 `tick_loop.advance` seam 可观察
- [x] 现有测试全绿（不回归）
