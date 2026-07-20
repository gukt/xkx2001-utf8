# 14 - Nature 结构化查询谓词（B2）

**What to build:** Nature 暴露结构化查询谓词 `phase` / `is_night` / `is_day` / `game_time_str` / `is_raining`，实现块 A 条件求值器的 `ConditionContext` 协议，替换 10 号票的 stub。门/物品/NPC 动态规则共用同一查询源，不用散落字符串比较。

**Blocked by:** 13 - 需要真实 NatureState 作为查询源；10 - 条件求值器协议形状已定。

**Status:** resolved

- [x] Nature 实现 `ConditionContext` 协议（`phase` / `is_night` / `is_day` / `is_raining`）
- [x] 暴露 `game_time_str`（可读游戏时间字符串）
- [x] `evaluate(condition, nature_context)` 对真实 Nature 求值正确（替换 stub）
- [x] 相位切换后谓词返回值随之变化（经 `advance()` 驱动）
- [x] 现有 `StubContext` 测试不破（stub 仍可用于纯函数单测）
- [x] 现有测试全绿（不回归）

## Comments

**re-pass (2026-07-20):** 架构审查缺口已修——`is_night` 不再仅 `phase == "night"`。固定集合：`NIGHT_PHASES = {night, midnight, dawn}`（对齐 research 夜条件）、`DAY_PHASES = {day, dusk}`。`TestQueryPredicates` 覆盖 dawn/dusk/midnight 语义与 `advance()` 后谓词翻转；`StubContext` / `test_conditions` 不变。全量套件中 NPC ask（票 27）失败与本票无关。
