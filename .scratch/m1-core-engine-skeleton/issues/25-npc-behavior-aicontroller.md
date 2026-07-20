# 25 - NPC 行为机制地基 Behavior + AIController（D1）

**What to build:** 新增 `Behavior`（行为列表 + 调度元数据）+ `AIController`（驱动源标记 + tick 频率）组件骨架；挂 `on_tick` 遍历 AIController 实体并逐个 `behavior.tick(context)`。M1 不实现战斗行为。玩家与 NPC 共用基础组件，区别只在驱动源组件。

**Blocked by:** 07 - 复用 `on_tick` 驱动。

**Status:** ready-for-agent

- [ ] 存在 `Behavior` / `AIController` 组件骨架
- [ ] 挂 `on_tick`：遍历带 AIController 的实体并调用 behavior.tick
- [ ] tick 频率可配置（跳过不足间隔的 tick）
- [ ] 无 AIController 的实体（含玩家、静态 NPC）不被遍历
- [ ] 注册测试行为，`advance()` 后断言被调用
- [ ] 不实现战斗行为
- [ ] 现有测试全绿（不回归）
