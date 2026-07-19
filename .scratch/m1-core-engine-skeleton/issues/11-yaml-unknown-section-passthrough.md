# 11 - YAML 未识别段透传

**What to build:** `scene_loader` 遇未识别段（`rules` / `on_use` / `effect` / `world_rules` / `dialogue` / `behaviors` / `nature` 等）时不报错,透传到一个"扩展数据"容器留着不丢（M1 不解析不执行）。这是"不锁死未来"的关键--M3 引入规则引擎时旧场景数据不必重写。且不违反"M1 不预支 M3 设计"（透传不是设计,只是不丢弃）。

- **未识别段透传到扩展数据容器**（挂 world 或 entity 上的 dict）,留着不丢。
- **已识别段非法值**（如 `door: ajar`）仍抛 `SceneLoadError` 带定位。
- **两者区分明确**:未识别段透传、已识别段非法值报错,不混着实现。
- **M1 不解析不执行未识别段**,只留数据;透传数据不进存档（声明式静态数据,非运行时可变态）。

**Blocked by:** None - 可立即开始（改 `scene_loader`,独立）。

**Status:** resolved（2026-07-19）

**实现摘要：** `scene_loader` 加 `_capture_top_level_unknown_sections`（顶层 `rules`/`world_rules`/`nature` 等透传到 `World.extension_data`）+ `_capture_entity_unknown_fields`（实体级 `on_use`/`effect`/`dialogue`/`behaviors` 等透传到 `World.entity_extension_data(entity)`，惰性 `setdefault` 返回引用），在各 `_build_*` 末尾按已知字段集合（`_*_KNOWN_FIELDS`）收集。透传数据挂 `World` 上而非做成实体组件，天然游离于存档序列化之外（`save.py` 只遍历 entities/components）：既满足"不进存档"（声明式静态数据、非运行时可变态），又不破坏 05 号票"未注册 codec 报 TypeError"护栏（做成组件会两难）。已识别段非法值（`door: ajar` 等）仍走原 `_door_state` 校验抛 `SceneLoadError` 带定位，与未识别段透传分支明确分离（spec"两者区分明确不混着实现"）。restore 路径不读 YAML 故不重建透传数据（符合"不进存档"语义）。新增 `TestUnknownSectionPassthrough`（7）+ `TestPassthroughDataDoesNotEnterSave`（2），212->221 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失，1 判断性异味重复场景 YAML 已正当化）。

- [x] 含 `rules` / `on_use` / `effect` / `world_rules` / `dialogue` 等未识别段的 YAML 加载成功不报错
- [x] 未识别段数据透传到扩展数据容器,可查询
- [x] 已识别段非法值（如 `door: ajar`）仍抛 `SceneLoadError` 带文件路径与出错条目定位
- [x] 未识别段不影响已识别段的正常加载（房间/物品/NPC/出口/门）
- [x] 透传数据不进存档（非运行时可变态）
