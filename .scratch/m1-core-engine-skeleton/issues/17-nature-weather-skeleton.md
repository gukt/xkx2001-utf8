# 17 - 天气晴雨骨架（B5）

**What to build:** 晴/雨两态按时辰 tick 随机切换；`NatureState.weather` + `is_raining` 谓词；户外描述升级为「时辰 × 天气」二维。不做对玩家机制影响（视野/移动等）。

**Blocked by:** 14 - 需要谓词协议与 NatureState。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] `NatureState` 有 weather 字段（晴/雨）
- [x] 天气按时辰 tick 可切换（测试用可注入 RNG，确定性）
- [x] `is_raining` 谓词随 weather 变化
- [x] 户外 `look` 文案体现时辰 × 天气二维
- [x] 天气变化可触发 `on_nature_change`（或等价通知）
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
