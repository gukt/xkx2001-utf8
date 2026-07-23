# Polishing（打磨抛光）

> **排期窗口**：Pre-M4 三批（房间保真 / 频道-spawn-任务 / 房间钩子-星宿）**关闭之后**、开启 **M4 之前** 的可选命名 effort，与三批 Pre-M4 同级，**不是**新的 M 编号，也**不是** M4 的一部分。
> **纳入即做**：13 项一旦纳入本 effort，不论体量，落地时必须实现（可拆更细 ticket，不得再悄悄后置出本阶段）。
> 关完仍**不**自动开 M4。

## 一句话

对照 LPC/创作体验收束缺口，经 grill 逐项拍板纳入的 13 项打磨：出口导航别名、YAML 简写规范化、房间风景 details 升级、`block_exits` 拒走文案、步行精力消耗、客店三件套、条件 DSL 文档化、液体/eat/drink、随机 objects 表、刷怪条件扩展、多文件 includes、局部天气继承（先出 ADR）。

## 状态

| 项 | 值 |
|---|---|
| 状态 | `/to-spec` 已完成；`/to-tickets` 已拆 13 票（`01`–`13`），待 `/implement` |
| 决策 | grill 拍板 [session-notes-2026-07-23.md](../polishing-candidate-review/session-notes-2026-07-23.md) + [session-qa-provenance-2026-07-23.md](../polishing-candidate-review/session-qa-provenance-2026-07-23.md) |
| Spec / 票 | [spec.md](spec.md)；[issues/](issues/) `01`–`13`；拆票分析见 [to-tickets-notes.md](to-tickets-notes.md) |
| 下一步 | 工作票 `01`（无阻塞）起 `/implement`；`14`（C14 ADR）也可与其它票并行开工 |
| 不走 | `/wayfinder`；`--strict`/`--validate`/加载器代码本 session 已改；把打磨项并入 M4 商业化叙事；关完自动滑入 M4 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| [pre-m4-room-hooks-xingxiu](../pre-m4-room-hooks-xingxiu/) | 已关；C12 复用其 `room_hooks.py`/`bandit_ambush`，不重开信任边界（ADR-0012）。 |
| [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/) | 已关；A4/A5 在其交付的 `details`/`block_exits` 基础上做加法升级。 |
| [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md) | 正交；M4 评估与本 effort 独立拍板，见 [PROGRESS.md](../../PROGRESS.md) Next Up §2。 |
