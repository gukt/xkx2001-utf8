# Pre-M4：官方房间钩子 + 星宿机制切片

> **排期窗口**：M3 停机加固 **整体完成之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（停机门闩）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与房间保真**：同属 Pre-M4 队列；**实现开工门闩** = [.scratch/pre-m4-engine-room-fidelity/](../pre-m4-engine-room-fidelity/) **整包关闭之后**（本目录可先落骨架 / ADR）。  
> **与频道/spawn/任务**：柔丝索硬门闩依赖已关闭批的双 `PlayerSession` seam。

## 一句话

在 M4 前用**官方可信房间钩子**（窄 `ctx`，非 UGC RestrictedPython）+ 官方机制切片 `xingxiu_mechanics`，交付星宿同构级房间机关硬门闩（动态出口/时限、岔路随机出口、多步状态机、迷途、jump/climb、时段秘道、磁力、劫匪刷拦、杀令介入、柔丝索捕获）。见 [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **骨架已落**（2026-07-22）；shared understanding 已确认；**实现未开工** |
| 决策 | [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)；[session-notes-2026-07-22.md](session-notes-2026-07-22.md) |
| Spec / 票 | **尚未** `/to-spec` / `/to-tickets`（等房间保真关闭后） |
| 验收资产（计划） | `engine/data/xingxiu_mechanics.yaml`（实现期创建；同构机关，非整区移植） |
| 下一步 | 房间保真关完 → 本 effort `/to-spec` → `/to-tickets` → `/implement` |
| 不走 | `/wayfinder`；并入房间保真改其 OOS 实现范围；UGC 脚本层；整区星宿移植；自动开 M4；本批 RestrictedPython 沙箱 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/) | 兄弟批；先关。风景/`details`/剧情门（翰林）归对方；本批不重做。对方 OOS「通用改出口」由 ADR-0012 **收窄含义**（UGC/契约仍禁；官方钩子 `ctx` 允许）。 |
| [pre-m4-channels-spawn-quest](../pre-m4-channels-spawn-quest/) | 已关；双会话 seam 供柔丝索验收。 |
| [ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md) | UGC 创作面仍声明式；本 ADR 部分修正「官方轨可信钩子」。 |
| [ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md) | 同构可玩，不做 LPC 行为等价。 |
| GAP 台账 | 实现收口时回写；骨架期不假装已支持。 |
| M4 | 本 effort 关完后仍**不**自动开 M4。 |

## 目录

- [session-notes-2026-07-22.md](session-notes-2026-07-22.md) — grill 决策底稿（shared understanding）
- `spec.md` — 待 `/to-spec`
- `issues/` — 待 `/to-tickets`
- `implement-plan.md` — 待拆票后
