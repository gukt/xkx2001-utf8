---
Status: accepted
---

# 场景放置改为房间中心 `objects`（弃用 `placed_in` / `in_room`）

Pre-M4 频道/spawn/任务 grill（2026-07-22）拍板：场景里 NPC/物品的**放置声明**改为房间中心的 `objects`（模板键 → 数量），与侠客行房间 `set("objects", …)` 同构；实体自带位置字段 `placed_in`（物品）与 `in_room`（NPC）在本 effort **退役**（加载器不再接受为权威写法，官方/示例场景迁完）。运行时补刷计数与侠客行 `reset()` 一致：按登记槽位记住实例，**对象仍存在（在哪都行）则占名额**，不因 `get`/`drop` 产生缺口，仅销毁后且 `respawn: true` 时补齐。动机：放置写法与 reset/槽位语义同一心智，避免「先按 `placed_in` 做物品 respawn、再在房间保真里二次搬家」。本决定由 [.scratch/pre-m4-channels-spawn-quest/](../../.scratch/pre-m4-channels-spawn-quest/) **落地**；[.scratch/pre-m4-engine-room-fidelity/](../../.scratch/pre-m4-engine-room-fidelity/) **不得再把放置模型当未决项重开**，其议程中的「维持 `placed_in`/`in_room` / 糖衣 / 物品 count」以本 ADR 为准收口。不做 LPC 行为等价验证（ADR-0001）；全局模板段（物品/NPC 定义）仍可与房间 `objects` 引用并存。

## Considered Options

- **A**：保留 `placed_in`/`in_room`，只加物品 `count`/`respawn`——切片最小，但与刚选定的槽位语义分裂，房间保真仍可能再迁一次。
- **B**：双写法（旧字段 + 房间引用清单糖衣）——迁移软，长期两套权威源。
- **C（采纳）**：本批直接改房间中心 `objects`，弃用旧字段。
