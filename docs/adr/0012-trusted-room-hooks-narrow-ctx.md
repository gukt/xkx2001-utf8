---
Status: accepted
---

# 官方可信房间钩子经窄 ctx 改世界；UGC 仍禁止可执行逻辑

Pre-M4 房间机关 grill（2026-07-22）拍板：星宿同构级机关（动态出口 / 时限崩塌 / 多步状态机 / 迷途 / 柔丝索等）不靠「每玩法加一条声明式原语」硬撑（防原语膨胀），也不在本批引入 UGC 可用的 RestrictedPython 沙箱。落地形态为 **官方 / 题材包可信 Python 模块**（与 `SkillBehavior` 同信任级），房间 YAML 只引用钩子入口；改世界必须走窄 `ctx` API（如 `add_exit` / `remove_exit` / `schedule` / `message_*`），禁止钩子直接摸 `World` 私有结构。UGC 内容包 **禁止** 携带钩子；`--validate` 遇 UGC 钩子应失败。加载期 `random_of` 出口可作为小声明式原语（不必进钩子）。验收挂官方机制切片 `xingxiu_mechanics`（同构可玩路径，非整区移植，非 LPC 行为等价）。本决策 **部分修正** [ADR-0005](0005-m3-ugc-loop-creation-surface.md)：M3「创作面 = 声明式」对 UGC 仍成立；Pre-M4 起 **官方轨** 可挂可信房间钩子。亦收窄房间保真 spec 中「不做通用 `add_exit`/`remove_exit`」的含义——禁止的是 **创作者契约 / UGC 任意脚本面**，不是官方钩子经 `ctx` 的出口变更。由 [.scratch/pre-m4-room-hooks-xingxiu/](../../.scratch/pre-m4-room-hooks-xingxiu/) 落地；**实现开工门闩**为兄弟批 [pre-m4-engine-room-fidelity](../../.scratch/pre-m4-engine-room-fidelity/) 整包关闭之后。

## Considered Options

- **A（采纳）**：可信 Python 模块 + 窄 `ctx`；UGC 禁钩子；不上本批 RestrictedPython。
- **B**：YAML 内联 + RestrictedPython——T1 信任边界下安全收益低、成本高。
- **C**：纯声明式动作/时限原语覆盖 γ——星宿机关密度下易原语膨胀。
- **D**：UGC 包也可嵌钩子——沙箱产品化，超出本批。
