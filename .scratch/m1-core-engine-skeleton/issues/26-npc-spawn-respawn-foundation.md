# 26 - NPC 生成/重生地基（D2）

**What to build:** 场景 npcs 段支持 `count` / `respawn` / `startroom`；挂低频 Spawn/Reset 扫描到 tick。对应 LPC「唯一召回 / 多实例补齐」。M1 NPC 不死不触发重生，机制地基先埋；`Behavior` 形状为未来可变状态进存档留好。

**Blocked by:** 25 - 重生扫描与行为驱动同属 tick 侧 NPC 基础设施。

**Status:** resolved（2026-07-20：经批量 review-fix 认证，未走独立 /implement；398 测试绿）

- [x] YAML npcs 支持 `count` / `respawn` / `startroom`（或与 `in_room` 关系明确）
- [x] 加载时按 `count` 生成对应实例数
- [x] 低频 Spawn/Reset 扫描挂 tick（M1 可空转或只补齐缺失实例）
- [x] 现有单实例静态 NPC 加载行为不破
- [x] 现有测试全绿（不回归）


## Comments

### 2026-07-20 review-fix 认证

经上一 session 批量 code-review + fix 认证（commits eca7830c / e687d43f / 79b831ef / cbfe8084 / bab2f44f）：代码已在 fc74e73b 首轮落地、bug 已修、398 测试绿。**未走独立 /implement TDD seam**，AC 勾选基于 review-fix 后代码状态，非逐条 TDD 验证；如需逐条独立认证仍可后续补 /implement。
