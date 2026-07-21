# 08 — 门派/阵营框架：FactionDefinition 全局注册表 + Faction 组件 + join 命令

**What to build:** 落地 spec Implementation Decisions「E1」的通用框架部分（少林具体内容是 24 号票）：`FactionDefinition(faction_id, display_name, join_condition: Condition | None, skill_pool: frozenset[str], map_skill: dict[str, str])` 全局注册表（`FACTIONS: dict[str, FactionDefinition]`，从新顶层段 `factions:` 加载——建议直接复用 03 号票"全局声明式注册表 + 顶层段解析"的写法模式，两处允许重复实现不强制抽共享 helper）；角色只挂轻量 `Faction(faction_id: str | None)` 组件（走 01 号票的 NPC/玩家级能力注册表）。新增 `join <门派>` 命令：求值 `FactionDefinition.join_condition`（复用 M1 已有的 `conditions.evaluate`，用 `StubContext` 或后续 09 号票的 `EntityGateContext` 都可以——本票如果 `join_condition` 需要查询玩家自身属性（如性别/是否已属其他门派），可以在本票内先用一个最小的、专属 `join` 命令的 context 实现，09 号票落地更通用的 `EntityGateContext` 后再考虑是否收拢复用，不强制本票等 09 号票）；条件满足则把玩家的 `Faction.faction_id` 设为目标门派，条件不满足给出明确原因文案。本票**不**实现 `learn` 命令（14 号票，需要 `map_skill` + `SkillData` 门槏联合校验）。

**Blocked by:** 01（`Faction` 组件走注册表挂载模式）。

**Status:** resolved

- [x] `FactionDefinition`/`FACTIONS` 全局注册表 + `factions:` 顶层段解析落地（加入 `_TOP_LEVEL_KNOWN_SECTIONS`），引用不存在的门派 id（如 NPC/玩家 `faction:` 字段引用了未声明的门派）在加载期报 `SceneLoadError`。
- [x] `Faction(faction_id: str | None)` 组件走 NPC/玩家级能力注册表；缺省 `faction_id=None` 表示无门派归属。
- [x] `join <门派>` 命令：门派 id 不存在给提示；`join_condition` 不满足给出具体缺什么（不是笼统"不满足条件"）；满足则设置 `Faction.faction_id` 并给出成功提示。
- [x] `join_condition` 是可选字段（`None` 表示无门派加入门槏，任何人都能加入）。
- [x] 命令层测试覆盖：无门槏门派直接加入成功、有门槏门派条件不满足给出具体原因、已有门派归属再次 join 的行为（是否允许换门派——实现阶段决定一个明确策略：建议 MVP 允许直接覆盖，不做"先退出旧门派"这层复杂度，写进代码注释即可，不算过度设计）。
- [x] `skill_pool`/`map_skill` 字段本票只需**声明并存储**（供 14 号票消费），不要求 `join` 命令本身用到它们。
- [x] 存档往返：`Faction.faction_id` save→restore 一致。
- [x] 现有测试全绿不回归。
