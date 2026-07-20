# 19 - 转移统一原语 transfer（C2）

**What to build:** 底层 `transfer(world, item, src, dst) -> TransferResult`，take/drop（及后续 put/give）收敛到它；携带成功/失败原因（`no_take`/`no_drop`/`over_capacity` 等由后续票填实）。reject 校验钩子复用已有 `on_take`/`on_drop` 事件点。转移逻辑只写一份。

**Blocked by:** 18 - 能力组件形状就绪后再收敛转移路径更稳（也可与标志位票协作；最低依赖现有 Container）。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] 存在 `transfer` 原语，返回成功/失败 + 原因
- [x] `_cmd_take` / `_cmd_drop` 走 `transfer`，外部可观察行为与现有一致
- [x] `on_take` / `on_drop` 否决仍生效
- [x] 契约测试锁定 `TransferResult` 形状
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
