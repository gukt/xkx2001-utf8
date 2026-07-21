---
Status: accepted
---

# Effect 生命周期延期：收窄 M2/M3 停机不变量

[ADR-0004](0004-combat-effects-boundary-engine.md) 仍成立：战斗七步骨架与 Effect 调度/衰减/移除机制**归属引擎**，数值与具体 handler 归题材包。M3 停机加固拍板（2026-07-21）：**持续 Effect 生命周期不是 M2/M3 停机必须兑现的不变量**——当前停机只要求七步骨架 + AP/DP 结构 + `SkillBehavior` 瞬时钩子；完整 Effect 列入加固之后的 backlog，本窗口不实现。动机：M2 票 16 已刻意降级，停机优先规格诚实而非半套状态系统。

## 考虑过的选项

- **本窗口最小实现 Effect 骨架**：能字面兑现 0004，但易在加固窗口膨胀。
- **把 Effect 降为可选或改归题材包**：削弱 0004 的归属结论，重开边界战。
- **延期兑现、归属不变（选定）**。

## 影响

- 0004 顶部标注由本 ADR **部分收窄**（归属不改，停机范围改）。
- [CLAUDE.md](../../CLAUDE.md) 摘要与对外叙事不得再写「ADR-0004 字面 Effect 生命周期已齐」。
- 术语上 **Effect ≠ SkillBehavior 瞬时副作用**（见根目录 [CONTEXT.md](../../CONTEXT.md)）。
