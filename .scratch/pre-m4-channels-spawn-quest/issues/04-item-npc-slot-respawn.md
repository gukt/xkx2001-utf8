---
Status: resolved
---

# 04 — 物品/NPC 槏位补刷（respawn 收敛到槏位指针语义）

**What to build:** 物品获得与 NPC 对称的补刷能力：仿照现有 `SpawnerBlueprint`/`spawn_scan`（`ai.py`），为房间 `objects`（票 `02`）登记的物品建立槏位蓝图（模板键 → 期望数量 + `respawn` 标志），补刷扫描判定改为"登记的具体实例是否仍存在于世界任意处"（在玩家背包、被丢到别的房间都算存在），而不是"某模板全图存活数够不够"。`get`/`drop` 不产生补刷缺口；只有实例被销毁（如消耗掉）且模板 `respawn: true` 时，下次扫描才在登记房间补齐缺口。NPC 现有的 `spawn_scan`（当前按"全图存活数"聚合）在本票收敛到同一槏位指针语义（对齐侠客行 `reset`，spec 明确允许此收敛，不必另开决策票；若发现改动破坏性过大，停下来做一次短 grill 说明再继续，不要静默留两套说法）。门钥匙等"唯一实体引用"的场景约束：若某物品模板被声明为 `count > 1` 或允许补刷、但同时被门锁等逻辑当作唯一引用消费，加载期报错拒绝（或在契约文档里写清楚禁止组合）。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US15–18；[ADR-0010](../../../docs/adr/0010-room-centric-objects-placement.md)。

**Blocked by:** 02（需要房间 `objects` 声明的模板键→数量作为槏位蓝图来源）。

- [ ] 物品槏位蓝图（类似 `SpawnerBlueprint`，可复用或新增等价结构）：由 `scene_loader.py` 按房间 `objects` + 物品模板 `respawn`/等价字段登记，记录期望数量与出生房间。
- [ ] 补刷扫描（复用/扩展 `spawn_scan` 心智）判定存活："该模板登记的实例 id 是否仍在世界中任意位置存在"，不是"该模板当前全图数量"；`get`/`drop` 不触发缺口；销毁（实体从 `World` 移除）+ `respawn: true` 时下次扫描补齐。
- [ ] NPC 现有补刷逻辑（`ai.py` 的 `spawn_scan`）收敛到同一"登记实例是否存在"判定，替换当前"存活数聚合"计数方式；已有 NPC 补刷回归测试保持通过（行为对齐侠客行 `reset` 语义后，既有单实例场景下结果不变）。
- [ ] 门钥匙等唯一引用物品：加载期若检测到"该模板被判定为唯一引用"（如与门锁/`entry_guard` 等逻辑耦合，或按约定标记）却同时声明 `count > 1` 或 `respawn: true`，`SceneLoadError` 拒绝并给出清晰原因；若判定实现成本过高，允许改为契约文档明确禁止 + 不做运行时校验，但需在票内注明选择哪种。
- [ ] 物品模板已知字段（`docs/creator-contract-v0.md`）新增 `count`/`respawn`（或等价字段名，与 NPC 对齐用词）。
- [ ] 测试（S2）：`objects` 加载出期望数量实例；拾取后不补；丢到别房后原房不补；销毁且 `respawn: true` 后下次扫描补齐；`respawn: false` 销毁后不补；门钥匙类冲突组合被拒绝（或按选定方案验证契约文档存在对应说明）。
- [ ] `just test` 全绿。

## Comments

- 2026-07-22 实现：`ItemSpawnerBlueprint` + `world.item_spawners[(room_key, template)]`；`spawn_scan` 收敛为槽位指针（NPC/物品共用语义）；物品模板 `respawn` 入契约；门锁 `key` 与 `count>1`/`respawn` 冲突加载期拒绝。测：`test_item_slot_respawn.py`。
