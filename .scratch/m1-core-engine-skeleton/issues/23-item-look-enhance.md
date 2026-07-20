# 23 - look 物品增强（C6）

**What to build:** `look <物品>`（或等价 examine）展示 long 描述；若是容器展示内容；若有堆叠/价值/重量展示数值。玩家能了解物品详情（房间 look 地面仍可只列名）。

**Blocked by:** 18 - 需要能力组件字段供展示。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] `look <物品>` 返回 long 描述
- [x] 容器物品展示内容列表
- [x] Stackable/Valuable/重量等有数值时出现在消息中
- [x] 找不到物品时有明确提示
- [x] 现有无参 `look`（房间）行为不回归
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
