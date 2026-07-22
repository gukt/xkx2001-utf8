# Pre-M4：官方房间钩子 + 星宿机制切片

> **排期窗口**：M3 停机加固 **整体完成之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（停机门闩）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与房间保真**：同属 Pre-M4 队列；实现开工门闩 = [.scratch/pre-m4-engine-room-fidelity/](../pre-m4-engine-room-fidelity/) **整包关闭之后**（已满足）。  
> **与频道/spawn/任务**：柔丝索硬门闩依赖已关闭批的双 `PlayerSession` seam。

## 一句话

在 M4 前用**官方可信房间钩子**（窄 `ctx`，非 UGC RestrictedPython）+ 官方机制切片 `xingxiu_mechanics`，交付星宿同构级房间机关硬门闩（动态出口/时限、岔路随机出口、多步状态机、迷途、jump/climb、时段秘道、磁力、劫匪刷拦、杀令介入、柔丝索捕获）。见 [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **已关闭**（2026-07-22，Wave 1–7 / 票 `01`–`11` 全关）；**不自动开 M4** |
| 决策 | [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)；[session-notes-2026-07-22.md](session-notes-2026-07-22.md) |
| Spec / 票 | [spec.md](spec.md)；[issues/](issues/) `01`–`11` 均为 `resolved`；执行手册 [implement-plan.md](implement-plan.md)（7 Wave） |
| 验收资产 | `engine/data/xingxiu_mechanics.yaml`（十类机关切片；与 `m2_mvp_scene` 分文件） |
| 契约 / GAP | [creator-contract-v0.md](../../docs/creator-contract-v0.md)「官方轨专属：房间钩子」；[gap-ledger.md](../../docs/gap-ledger.md)「运行时改世界机关」 |
| 下一步 | 回到 [PROGRESS.md](../../PROGRESS.md)「M4 评估」——**不得**因本 effort 关闭自动开 M4 |
| 不走 | `/wayfinder`；并入房间保真改其 OOS 实现范围；UGC 脚本层；整区星宿移植；自动开 M4；本批 RestrictedPython 沙箱 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/) | 兄弟批；先关。风景/`details`/剧情门（翰林）归对方；本批不重做。对方 OOS「通用改出口」由 ADR-0012 **收窄含义**（UGC/契约仍禁；官方钩子 `ctx` 允许）。 |
| [pre-m4-channels-spawn-quest](../pre-m4-channels-spawn-quest/) | 已关；双会话 seam 供柔丝索验收。 |
| [ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md) | UGC 创作面仍声明式；本 ADR 部分修正「官方轨可信钩子」。 |
| [ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md) | 同构可玩，不做 LPC 行为等价。 |
| GAP 台账 | 收口已回写「运行时改世界机关」行。 |
| M4 | 本 effort 关完后仍**不**自动开 M4。 |

## 目录

- [session-notes-2026-07-22.md](session-notes-2026-07-22.md) — grill 决策底稿（shared understanding）
- [spec.md](spec.md) — `/to-spec` 产出
- [to-tickets-notes.md](to-tickets-notes.md) — `/to-tickets` 拆票分析笔记
- [issues/](issues/) — 11 张票（`01`–`11`，编号即依赖顺序）
- [implement-plan.md](implement-plan.md) — 7 Wave 执行手册（`/implement` → `/code-review` → fix 循环）
