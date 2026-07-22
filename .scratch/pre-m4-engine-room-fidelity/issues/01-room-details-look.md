---
Status: resolved
---

# 01 — 房间风景 details + look 优先级

**What to build:** 场景作者可在房间上声明 `details`（键 → 描述文本）；玩家 `look <键>` 在同房无同名实体时看到该文本。同房实体（地面物品与 NPC）优先于同名风景键。风景不占 `objects`、不可 `get`。官方扬州 MVP 场景至少一处户外/房间挂上可 `look` 的风景，作为局部 S3 锚点。

对应 spec：US1–US5；Testing S1/S2 + 局部 S3。

**Blocked by:** None — 可立即开始。

- [x] 房间 YAML 一等字段 `details`：字符串键 → 描述字符串；加载期消费（进房间能力/组件，不透传进 `entity_extension_data` 了事）。
- [x] `look <名>` 解析顺序：同房实体（物品 + NPC）→ `details` 键 → 既有失败提示；无括号 id 语法。
- [x] 风景键不出现在地面物品列表、不可 `get`、不占 `objects` 槽位。
- [x] 创作者契约 / 加载器已知字段对本字段做加法（可与票 `07` 最终措辞对齐，本票至少让 `--validate` 认识并消费 `details`）。
- [x] 官方 `m2_mvp_scene` 至少一处扬州户外/房间声明可玩 `details`（可与票 `02` 的语义色后交织，本票允许纯文本）。
- [x] 测试（S1）：`details` 命中；实体优先于同名风景键；`get` 风景键失败。测试（S2）：字段被加载消费。
- [x] `just test` 全绿。

## Comments

实现摘要（供 07 回写契约）：

- **字段**：房间 YAML `details: { <键>: <描述字符串> }`；组件 `RoomDetails.entries: dict[str, str]`；经 `ROOM_CAPABILITIES` 消费（`known_fields` 含 `details`）。
- **命令**：`look <名>` / `l <名>`；解析顺序物品 → 同房 Identity 实体（NPC）→ 执行层查 `RoomDetails.entries`；失败文案仍为 `这里没有 {名}。`
- **官方锚点**：`m2_mvp_scene.yaml` → `yangzhou_guangchang` 挂 `石狮` / `旗杆`。
- **契约**：`docs/creator-contract-v0.md` `rooms.*` 已知字段已加 `details`。
