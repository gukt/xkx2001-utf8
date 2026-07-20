# 25 - NPC 行为机制地基 Behavior + AIController（D1）

**What to build:** 新增 `Behavior`（行为列表 + 调度元数据）+ `AIController`（驱动源标记 + tick 频率）组件骨架；挂 `on_tick` 遍历 AIController 实体并逐个 `behavior.tick(context)`。M1 不实现战斗行为。玩家与 NPC 共用基础组件，区别只在驱动源组件。

**Blocked by:** 07 - 复用 `on_tick` 驱动。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] 存在 `Behavior` / `AIController` 组件骨架
- [x] 挂 `on_tick`：遍历带 AIController 的实体并调用 behavior.tick
- [x] tick 频率可配置（跳过不足间隔的 tick）
- [x] 无 AIController 的实体（含玩家、静态 NPC）不被遍历
- [x] 注册测试行为，`advance()` 后断言被调用
- [x] 不实现战斗行为
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
