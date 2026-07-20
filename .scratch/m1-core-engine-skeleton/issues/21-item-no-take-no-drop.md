# 21 - 标志位 no_get / no_drop（C4）

**What to build:** 物品可声明 `no_get`（拿不起，如固定家具）与 `no_drop`（丢不掉；支持字符串自定义提示，如"这是任务物品，不能丢弃"）。提示为声明式字符串字段，非闭包。

**Blocked by:** 19 - 标志位在 `transfer` reject 路径上生效。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] `no_get` 物品 take 失败并有提示
- [x] `no_drop` 物品 drop 失败；自定义提示字符串出现在消息中
- [x] 标志位经 YAML 声明式配置
- [x] 无标志位物品行为不变
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
