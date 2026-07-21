# 04 — Spawner 蓝图注册表：修复模板全灭后扫描失效（PROGRESS.md 复核点）

**What to build:** 修复 `engine/src/mud_engine/ai.py` 的 `_spawn_scan` 已在代码注释里明确点名的缺口（"若某 template 实例全灭，template_key 从存活实例聚合的 metas 里消失，扫描无法发现缺口"），这是 [PROGRESS.md](../../../PROGRESS.md) 与 spec Implementation Decisions「C2」明确点名的 M2 复核项。新增 `SpawnerBlueprint`（重建一个 NPC 实例所需的全部数据快照：`Identity`/`Description` 字段、`startroom`、可选 `Inquiry`/`Behaviors`/`tick_interval`/未来的 `Faction`/`Vitals` 等）与 `world.spawners: dict[str, SpawnerBlueprint]`（运行时态，纯内存不进存档，与 `world.nature`/`world.ai` 同构，由 `scene_loader._build_npcs` 建 NPC 时顺带注册）。`_spawn_scan` 改为遍历 `world.spawners`（不再从 `entities_with(NpcSpawnMeta)` 反向聚合）：对每个 `template_key`，统计当前存活实例数（仍查 `NpcSpawnMeta.template_key` 匹配的实体），"期望值"来自独立注册表而非从存活实例本身推断；不足且 `respawn=True` 时按 `SpawnerBlueprint` 重建缺口数量的新实例。本票**验证方式不依赖真实死亡机制**（06/17/18 号票才有）——测试直接手工把某模板的全部存活实体从 `world` 移除（模拟"全灭"），断言下一次 `_spawn_scan` 仍能发现缺口并补齐；这是这条回归测试的关键：旧实现在这个场景下会因为 `template_key` 从聚合结果里消失而静默跳过。

**Blocked by:** None — 独立于战斗/死亡系统，只需现有 `NpcSpawnMeta`/`AIController`/`scene_loader`，可与 01/02/03 并行开工。

**Status:** resolved

- [x] `SpawnerBlueprint` 数据形状落地（足够重建一个实例：身份/描述/出生房间/可选 Inquiry/Behaviors/tick_interval，为未来 Faction/Vitals 等预留扩展空间但本票不强制填充）。
- [x] `world.spawners: dict[str, SpawnerBlueprint]` 运行时态字段（不进存档，`save.py` 不涉及）；`scene_loader._build_npcs` 建 NPC 时为每个 `template_key` 注册一条（同一 template 多个 `count` 实例只注册一条蓝图）。
- [x] `_spawn_scan` 改为遍历 `world.spawners`，不再从存活实例反向聚合 `template_key -> desired_count`（`desired_count`/`respawn` 现在从 `SpawnerBlueprint` 读，不从某个存活 `NpcSpawnMeta` 读）。
- [x] **核心回归测试**：`desired_count=1` 的 NPC（如未来的单例门派 NPC）在存活实例被手工全部移除后（不经过真实死亡流程，直接操作 `world`），下一次 `_spawn_scan`（或直接调用扫描函数）仍能发现缺口并按 `SpawnerBlueprint` 重建出一个新实例，新实例的身份/描述/出生房间与原蓝图一致。
- [x] 缺口不足且 `respawn=False` 的模板扫描后**不**补齐（保持 M1 既有"不 respawn 就不补"语义，不引入回归）。
- [x] 新实例重建后带一份**全新**的 `NpcSpawnMeta`（不带上一实例任何累积可变状态——为 18 号票"NPC 重生不带上一实例状态"的验收铺路，但本票只需保证蓝图重建路径本身正确，不需要真实战斗触发）。
- [x] `engine/tests/test_npc_extension.py` 现有测试全绿；新增专门测试文件或用例覆盖上述回归场景，测试名/注释直接引用"template 全灭"这一场景描述，方便未来读代码的人对上 PROGRESS.md 的历史记录。
