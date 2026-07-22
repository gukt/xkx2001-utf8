---
Status: resolved
---

# 02 — 房间中心 `objects` 放置迁移（弃用 `placed_in`/`in_room`）

**What to build:** 场景 YAML 里 NPC/物品的"放在哪、几份"改由房间字段 `objects`（模板键 → 数量）声明；全局 `items`/`npcs` 段收窄为纯模板定义（属性），不再携带位置字段。加载器（`scene_loader.py`）按房间 `objects` 逐条实例化对应数量的物品/NPC 到该房间；旧权威写法 `placed_in`（物品）/`in_room`（NPC）若出现在场景数据中，加载直接失败并给出指向 ADR-0010 的清晰错误（不静默兼容、不做双轨过渡——见 ADR-0010 已选 C）。官方 `engine/data/m2_mvp_scene.yaml` 与内容包范本（`example-pack`）全部迁移到新写法。`startroom`（NPC 出生房，与运行时位置分开的 spawn meta）若仍需要保留，与 `objects` 声明的位置字段语义要说清楚谁是权威（`objects` 决定初始位置，`startroom` 只在 respawn 时兜底，若无额外覆盖两者应一致）。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US11–14、US19；[ADR-0010](../../../docs/adr/0010-room-centric-objects-placement.md)。

**Blocked by:** None — 可立即开始。

- [x] 房间 YAML schema 新增 `objects` 字段（`{template_key: count}`），`scene_loader.py` 按此建物品/NPC 实例，替代当前 `_build_items` 读 `placed_in`、`_build_npcs` 读 `in_room` 的权威路径。
- [x] `items.*`/`npcs.*` 模板段移除 `placed_in`/`in_room` 作为**权威**字段；场景数据中若仍出现这两个字段（在模板段或任何位置被当作放置依据），`SceneLoadError` 明确拒绝并指向 `objects` 写法（不是警告，是加载失败）。
- [x] NPC 现有 `count`/`respawn`（`SpawnerBlueprint.desired_count`/`respawn`）改为从房间 `objects` 的数量 + 模板 `respawn` 字段推导，而不是模板段自带 `count`。
- [x] `engine/data/m2_mvp_scene.yaml` 全量迁移到 `objects` 写法（物品与 NPC 都迁），迁移后场景可正常加载、既有 e2e/命令测试断言的实体位置不变。
- [x] `example-pack`（内容包范本）同步迁移，保持双轨（官方轨/内容包轨）一致（参照 [场景创作双轨说明](../../../docs/scene-authoring-guide.md)）。
- [x] 创作者契约 v0（`docs/creator-contract-v0.md`）已知字段表回写：房间段新增 `objects`；`items.*`/`npcs.*` 已知字段表移除 `placed_in`/`in_room`。
- [x] 校验/`--validate --strict` 已知字段集同步更新（不新增平行登记表，复用现有常量收敛点）。
- [x] 测试（S2）：`objects` 加载出期望数量实例；旧 `placed_in`/`in_room` 写法被拒且报错信息可读；官方/示例场景加载测试与既有位置断言仍通过。
- [x] `just test` 全绿，M2/M3 既有回归不破。

## Comments

- 2026-07-22：落地 ADR-0010。`scene_loader` 以房间 `objects` 为唯一放置权威；拒绝 `placed_in`/`in_room`/模板 `count`；NPC `desired_count` 由 objects 数量推导，`startroom` 须与 objects 房一致。官方 m1/m2 场景与 example-pack 已迁；契约 v0 与测试夹具同步。
