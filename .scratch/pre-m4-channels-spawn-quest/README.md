# Pre-M4：假多人频道 + 物品 respawn + 声明式任务

> **排期窗口**：M3 停机加固 **整体完成（P0+B3）之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（那是停机门闩 S0 + 选定 B3）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与房间保真的关系**：同属 Pre-M4 队列；**建议本 effort 优先于** [.scratch/pre-m4-engine-room-fidelity/](../pre-m4-engine-room-fidelity/)（先补机制缺口，再补房间表达力）；最终顺序可在加固关完后的 grill 再确认。

## 一句话

在进 M4 前，用**严格切片**补齐：同 World 双 `PlayerSession` 测试 seam + Channel（`chat`/`system`）；**房间中心 `objects` 放置**（弃用 `placed_in`/`in_room`，见 [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)）+ 物品/NPC 槽位补刷；YAML `quests.<id>` 旗标状态机（官方挂 1～2 条）。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **已拆票**（`/to-tickets` 已完成）→ 下一步按票 `/implement` |
| Spec | [spec.md](spec.md) |
| 票 | [issues/](issues/)（`01`–`07`，依赖顺序编号；frontier：`01`/`02`/`03` 可并行开始） |
| 入口文档 | [session-notes-2026-07-22.md](session-notes-2026-07-22.md) · [grill-paused-2026-07-22.md](grill-paused-2026-07-22.md) |
| 频道调研 | [research-channels-lpc-2026-07-22.md](research-channels-lpc-2026-07-22.md) |
| 放置决策 | [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)（本 effort 落地；房间保真不得重开） |
| 下一步 skill | 按票 `/implement`（从 frontier `01`/`02`/`03` 任一张开始） |
| 不走 | `/wayfinder`；不改现有单玩家 REPL 为验收标准 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) | 停机门闩仍有效（频道非 S0）。本 effort **落地后**需追加/修订 ADR：单机阶段引入「双会话 seam + 频道」不等于多人联网/登录层。 |
| [ADR-0009](../../docs/adr/0009-single-process-single-world.md) | 仍约束单进程单 World；假多人不引入多 World。 |
| [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md) | **本 effort 范围**：房间 `objects` + 槽位补刷；官方/示例场景迁移；加载器弃用 `placed_in`/`in_room`。 |
| M3 停机加固票 `11` GAP 台账 | 加固期可把「多人频道 / 物品 respawn / 任务」写进 GAP；本 effort 落地后再改「已支持」。 |
| Pre-M4 房间保真 | 兄弟 effort；建议本批先做。**放置模型已不在其 scope**（见对方 README / ADR-0010）。 |
| M4 | 本 effort（及建议顺序下的房间保真）**插入在加固与 M4 之间**；关完后再决定是否开 M4。 |

## 目录

- `spec.md` — grill 塌缩后产出  
- `issues/` — `/to-tickets` 产出（`01`–`07`）：
  1. `01` give 命令（无阻塞）
  2. `02` 房间中心 `objects` 放置迁移（无阻塞）
  3. `03` 假多人 seam：按会话收件箱（无阻塞）
  4. `04` 物品/NPC 槏位补刷（阻塞于 `02`）
  5. `05` Channel：`chat`+`system`（阻塞于 `03`）
  6. `06` 声明式 Quest 状态机 + 官方闭环（阻塞于 `01`、`02`）
  7. `07` 收口：GAP 台账 + CONTEXT/PROGRESS 回写（阻塞于 `04`、`05`、`06`）
- `implement-plan.md` — 可选

[spec.md](spec.md) 已发布；**已 `/to-tickets`**，下一步按票 `/implement`。
