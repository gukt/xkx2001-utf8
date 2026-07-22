# Grill 暂停快照（2026-07-22）

> **人可读暂停点**。完整对话浓缩与下一 session 指令以 OS tmp 的 `/handoff` 文件为准（路径见该次 handoff 输出）。  
> 底稿：[session-notes-2026-07-22.md](session-notes-2026-07-22.md) · Spec：[spec.md](spec.md) · 调研：[research-channels-lpc-2026-07-22.md](research-channels-lpc-2026-07-22.md) · 索引：[README.md](README.md)

## 状态

| 项 | 值 |
|---|---|
| 主流程 | Pre-M4 频道/spawn/任务 · **grill 完成 + spec 已发布** |
| Spec | [spec.md](spec.md)（`Status: ready-for-agent`） |
| 下一步 | `/to-tickets` → `/implement` |
| 加固前置 | M3 停机加固 P0+B3 **已完成** |

## 本 grill 已决（全清单）

见 [spec.md](spec.md) 与下方摘要；shared understanding 与测试接缝 S1/S2/S3 均已确认（2026-07-22）。

1. 总体策略 B；本批先于房间保真  
2. 假多人 seam + Channel `chat`/`system`（显式 `chat`；system API-only；默认订两者；无 `tune`）  
3. 物品/放置：LPC 槽位指针 + 房间 `objects`（[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)）  
4. Quest：`quest accept <id>`；完成 = 交物 + 旗标；官方 1 条镖局→华山向导  
5. [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) 已追加澄清  

## 未决

- 无 grill 项。拆票与实现见下一 skill。
