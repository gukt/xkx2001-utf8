# Pre-M4：假多人频道 + 物品 respawn + 声明式任务

> **排期窗口**：M3 停机加固 **整体完成（P0+B3）之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（那是停机门闩 S0 + 选定 B3）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与房间保真的关系**：同属 Pre-M4 队列；**建议本 effort 优先于** [.scratch/pre-m4-engine-room-fidelity/](../pre-m4-engine-room-fidelity/)（先补机制缺口，再补房间表达力）；最终顺序可在加固关完后的 grill 再确认。

## 一句话

在进 M4 前，用**严格切片**补齐三块引擎能力：同 World 双 `PlayerSession` 测试 seam + 1～2 个频道；物品 `count`/`respawn` 对齐 NPC spawner；YAML `quests.<id>` 旗标状态机（官方挂 1～2 条）。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **排队**：等 M3 停机加固 Wave B3（`08`–`11`）关完 |
| 入口文档 | [session-notes-2026-07-22.md](session-notes-2026-07-22.md)（本 session 范围拍板） |
| 下一步 skill | 加固完成后新 session：`/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement` |
| 不走 | `/wayfinder`；不直接 `/implement`；不改现有单玩家 REPL 为验收标准 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) | 停机门闩仍有效（频道非 S0）。本 effort **落地后**需追加/修订 ADR：单机阶段引入「双会话 seam + 频道」不等于多人联网/登录层。 |
| [ADR-0009](../../docs/adr/0009-single-process-single-world.md) | 仍约束单进程单 World；假多人不引入多 World。 |
| M3 停机加固票 `11` GAP 台账 | 加固期可把「多人频道 / 物品 respawn / 任务」写进 GAP；本 effort 落地后再改「已支持」。 |
| Pre-M4 房间保真 | 兄弟 effort；建议本批先做。 |
| M4 | 本 effort（及建议顺序下的房间保真）**插入在加固与 M4 之间**；关完后再决定是否开 M4。 |

## 建议目录（grill / to-spec 之后）

- `spec.md` — grill 塌缩后产出  
- `issues/` — `/to-tickets` 产出  
- `implement-plan.md` — 可选  

当前仅有 session 笔记，**尚未**开 `/to-spec`。
