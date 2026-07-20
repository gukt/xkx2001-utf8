# 15 - 户外房间文案动态拼接（B3）

**What to build:** `Description` 加 `outdoors` 字段；`look` 渲染时户外房间追加当前时辰（及天气，若已有）desc_msg，室内房间不追加。玩家在户外能感知世界随时辰演化。

**Blocked by:** 14 - 需要 Nature 谓词/desc_msg 查询。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] `Description` 组件有 `outdoors: bool` 字段（默认 false）
- [x] 场景 YAML 房间可声明 `outdoors: true`
- [x] `look` 户外房间消息含当前时辰 desc_msg
- [x] `look` 室内房间不追加 Nature 文案
- [x] 推进相位后户外 `look` 文案随之变化
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
