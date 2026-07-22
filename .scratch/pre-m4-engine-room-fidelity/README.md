# Pre-M4：引擎房间 / 交互保真补全

> **排期窗口**：M3 停机加固 **整体完成之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（那是停机门闩 S0 + 选定 B3）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与频道/spawn/任务**：同属 Pre-M4；[.scratch/pre-m4-channels-spawn-quest/](../pre-m4-channels-spawn-quest/) **已先于本 effort 关闭**。

## 一句话

对照 LPC 房间写法补引擎能力：硬门闩为房间风景（`details`）、语义色（ADR-0011）、完整藏书；本波另含日间店铺与剧情门（非硬门闩）。液体灌装后置。

> **放置模型已不在本 effort**：由兄弟批 + [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md) 落地；**不得重开**。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **已关闭**（2026-07-22；票 `01`–`07` 全 resolved；Wave 1–3 落地） |
| 入口文档 | [spec.md](spec.md)；[issues/](issues/)；[implement-plan.md](implement-plan.md)；[to-tickets-notes.md](to-tickets-notes.md)；[session-notes-2026-07-21.md](session-notes-2026-07-21.md)；[CONTEXT.md](../../CONTEXT.md)；[ADR-0011](../../docs/adr/0011-semantic-color-tokens.md) |
| 下一步 | 不自动开 M4；后继 [pre-m4-room-hooks-xingxiu](../pre-m4-room-hooks-xingxiu/)（实现门闩：本 effort 已关） |
| 不走 | `/wayfinder`；重开放置模型；自动开 M4 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| M3 停机加固票 `11` GAP 台账 | **文档**：「声明式 YAML 表达不了什么」。本 effort 已补能力并回写 GAP「已支持」行。 |
| 创作者契约 v0（加固票 `06`） | 本波字段已加法回写契约 / `--validate` 同源校验。 |
| [Pre-M4 频道/spawn/任务](../pre-m4-channels-spawn-quest/) | 兄弟 effort（已关）；放置归该批 + ADR-0010。 |
| [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md) | 放置模型已决；本 effort 未重开。 |
| [Pre-M4 房间钩子 / 星宿](../pre-m4-room-hooks-xingxiu/) | 后继；实现门闩为本 effort 关闭。 |
| M4 | 本 effort **插入在加固与 M4 之间**；关完**不**自动开 M4。 |

## 目录

- [spec.md](spec.md) — grill 塌缩后产出  
- [issues/](issues/) — `/to-tickets` 产出（`01`–`07`）  
- [to-tickets-notes.md](to-tickets-notes.md) — 拆票决策  
- [implement-plan.md](implement-plan.md) — Wave 执行手册（多 session）
