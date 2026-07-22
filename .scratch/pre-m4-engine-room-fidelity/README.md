# Pre-M4：引擎房间 / 交互保真补全

> **排期窗口**：M3 停机加固 **整体完成之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（那是停机门闩 S0 + 选定 B3）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与频道/spawn/任务**：同属 Pre-M4；**建议** [.scratch/pre-m4-channels-spawn-quest/](../pre-m4-channels-spawn-quest/) **先于本 effort**（机制先于房间表达力）。

## 一句话

对照 LPC 房间写法补引擎能力：硬门闩为房间风景（`details`）、语义色（ADR-0011）、完整藏书；本波另含日间店铺与剧情门（非硬门闩）。液体灌装后置。

> **放置模型已不在本 effort**：由兄弟批 + [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md) 落地；**不得重开**。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **spec 已发布**（`ready-for-agent`）；grill + S1/S2/S3 接缝已确认 |
| 入口文档 | [spec.md](spec.md)；[session-notes-2026-07-21.md](session-notes-2026-07-21.md)；[CONTEXT.md](../../CONTEXT.md)；[ADR-0011](../../docs/adr/0011-semantic-color-tokens.md) |
| 下一步 skill | `/to-tickets` → `/implement` |
| 不走 | `/wayfinder`；不直接 `/implement`；不重开放置模型；不自动开 M4 |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| M3 停机加固票 `11` GAP 台账 | **文档**：「声明式 YAML 表达不了什么」。本 effort 是 **补能力**；加固期可先把本清单若干条写入 GAP，实现落地后再改「已支持」。 |
| 创作者契约 v0（加固票 `06`） | 本波能力若进 YAML schema，需回写契约 / `--validate`。放置字段变更由兄弟批 + ADR-0010 先改契约。 |
| [Pre-M4 频道/spawn/任务](../pre-m4-channels-spawn-quest/) | 兄弟 effort（假多人频道 + **房间 `objects` 放置/槽位补刷** + 声明式任务）。**建议该批优先于本房间保真**；放置与物品 count/respawn **归该批**，见 [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)。 |
| [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md) | 放置模型已决；本 effort 议程删除「维持 `placed_in`/`in_room` vs objects」未决项。 |
| M4 | 本 effort **插入在加固与 M4 之间**（与上表兄弟 effort 同窗口）；关完后再决定是否开 M4。 |

## 建议目录（grill / to-spec 之后）

- `spec.md` — grill 塌缩后产出  
- `issues/` — `/to-tickets` 产出  
- `implement-plan.md` — 可选  

已有 [spec.md](spec.md)；`issues/` 待 `/to-tickets`。
