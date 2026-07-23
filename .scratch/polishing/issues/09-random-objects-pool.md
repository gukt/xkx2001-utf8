---
Status: resolved
---

# 09 — C11 随机 objects 表（补刷期候选组抽签）

**What to build:** 房间 `objects` 某槏位支持新形状 `{ random_of: [tpl_a, tpl_b, tpl_c], count?: <int> }`（与既有「模板键 → 数量」写法并存，只做加法）；`ai.py::spawn_scan` 在补刷/初始生成该槏位时按 rng 从候选组抽签选定具体模板后再创建实例（补刷期求值，不是加载期一次性选定）。与既有出口 `random_of`（加载期一次性选定、落地为普通 `to` 出口，此后固定）是两个正交概念、互不覆盖，不共用同一段求值代码路径。

对应 spec：`.scratch/polishing/spec.md` §C11（User Stories 32–34；Implementation Decisions「C11」）；LPC 出处 [session-qa-provenance-2026-07-23.md](../../polishing-candidate-review/session-qa-provenance-2026-07-23.md) Q7（落日林三选一）。

**Blocked by:** None — 可立即开始。

- [x] `scene_loader.py`：房间 `objects.<slot>` 解析支持新形状 `{ random_of: [...], count?: int }`（`count` 缺省 1）；与既有「模板键→数量」写法并存的加载期校验（形状互斥检查：单槏位只能是其中一种写法，不可同时写 `random_of` 与数量）。
- [x] `ai.py::spawn_scan`：补刷/初始生成该槏位时，从候选组按 rng 抽签选定具体模板后再创建实例；同一槏位在多次补刷之间允许连续抽到同一模板（纯独立抽签，不做「不放回」）。
- [x] rng 注入：评估并落地 `spawn_scan` 的确定性 rng 注入参数（供测试断言候选分布/避免不稳定测试），若现有 `spawn_scan` 签名不支持 rng 参数则本票新增（只做加法，不改变既有调用方默认行为）。
- [x] 契约新增字段：`rooms.*.objects.<slot>` 的 `random_of`/`count` 形状——`docs/creator-contract-v0.md` 同步补写。
- [x] `docs/gap-ledger.md`：把「多套 objects 抽一套」相关缺口更新为「已支持」并指向新契约字段。
- [x] 明确不与出口 `random_of` 共用求值代码路径（避免破坏出口 `random_of` 现有「加载期定死」的既有测试预期）——实现时需有代码注释或测试双重锚定这一边界。
- [x] `test_spawner.py` 扩展：多次触发补刷得到不同候选（用注入的确定性 rng 或多次运行统计分布断言）；S2 加载期形状校验（合法/互斥非法两类）。
- [x] `just test` 全绿。

## Comments

**实现摘要（2026-07-23）**

- 数据形状：`objects.<slot_key>: { random_of: [tpl…], count?: int }`（`count` 缺省 1）；槽位键不得与模板键同名；候选须同 kind；各候选 `respawn` 须一致。
- 运行时：`RandomObjectSlotBlueprint` + `world.random_object_slots[(room_key, slot_key)]`；抽签函数 `draw_random_object_template`（补刷/初始共用）。
- 与出口边界：出口仍只走 `_exit_random_of_target`（加载期）；objects 池**不**调用该函数——`test_spawner.py::test_spawn_scan_redraws_independent_of_exit_random_of` 双重锚定。
- rng：`spawn_scan(world, *, rng=None)` 只做加法；缺省 `world.ai.rng` → `Random()`。`load_scene(rng=)` 兼作初始抽签种子（与出口共用注入点，但求值函数分离）。
- 候选模板在 `world.spawners` 登记 `desired_count=0` / `respawn=False`，避免普通 spawn_scan 双刷。
- 单槽位候选须同 kind（全物品或全 NPC）；LPC「落日林」式物品+NPC 混表用**多个槽位**或分次抽签表达，不在单 `random_of` 列表混写（US32 示例是能力意图，非单列表字面混种）。
- 额外加载约束（Comments 钉死）：槽位键≠模板键；候选 `respawn` 一致；同一模板不得既固定放置又进池 / 跨多池。
