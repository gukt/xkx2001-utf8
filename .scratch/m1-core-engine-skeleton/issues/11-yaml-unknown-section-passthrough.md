# 11 - YAML 未识别段透传

**What to build:** `scene_loader` 遇未识别段（`rules` / `on_use` / `effect` / `world_rules` / `dialogue` / `behaviors` / `nature` 等）时不报错,透传到一个"扩展数据"容器留着不丢（M1 不解析不执行）。这是"不锁死未来"的关键--M3 引入规则引擎时旧场景数据不必重写。且不违反"M1 不预支 M3 设计"（透传不是设计,只是不丢弃）。

- **未识别段透传到扩展数据容器**（挂 world 或 entity 上的 dict）,留着不丢。
- **已识别段非法值**（如 `door: ajar`）仍抛 `SceneLoadError` 带定位。
- **两者区分明确**:未识别段透传、已识别段非法值报错,不混着实现。
- **M1 不解析不执行未识别段**,只留数据;透传数据不进存档（声明式静态数据,非运行时可变态）。

**Blocked by:** None - 可立即开始（改 `scene_loader`,独立）。

**Status:** ready-for-agent

- [ ] 含 `rules` / `on_use` / `effect` / `world_rules` / `dialogue` 等未识别段的 YAML 加载成功不报错
- [ ] 未识别段数据透传到扩展数据容器,可查询
- [ ] 已识别段非法值（如 `door: ajar`）仍抛 `SceneLoadError` 带文件路径与出错条目定位
- [ ] 未识别段不影响已识别段的正常加载（房间/物品/NPC/出口/门）
- [ ] 透传数据不进存档（非运行时可变态）
