---
Status: resolved
---

# 06 — 剧情门三件套 + 翰林

**What to build:** 在现有门/出口模型上做声明式扩展（不平行第二套门系统）：（1）解锁时消耗钥匙；（2）未解锁时该向无出口或等价不可走，解锁后可走；（3）某 NPC 在场则挡某向。官方翰林后院（或同构房）走通三件套。标准门「钥匙不消耗」默认保持。不把通用运行时 `add_exit`/`remove_exit` 写入创作者契约作本波必达。

对应 spec：US27–US31；Testing S1/S2/S3。

**Blocked by:** None — 可立即开始（可与 Wave 1 并行；建议仍按 Wave 2）。

- [x] 声明式耗钥解锁：成功路径消耗钥匙；失败不改门/出口状态。
- [x] 未解锁：该向不可走（无向或等价拒走）；解锁后可走。
- [x] 声明「某 NPC 在场则挡某向」；NPC 不在场时该向按既有出口/门规则。
- [x] 标准门锁默认仍为钥匙不消耗；耗钥为显式声明的剧情门行为。
- [x] 官方 `m2_mvp_scene` 扩展翰林后院（或同构）承载三件套验收；可从既有扬州图到达。
- [x] 字段/命令形状钉死后写入本票 Comments，供票 `07` 回写契约。
- [x] 测试（S1）：耗钥、无向、NPC 挡向的命令层结果。测试（S3）：翰林路径走通。
- [x] 本票为**非硬门闩**：可止损；止损时记 Comments + PROGRESS Blocked，不堵硬门闩。
- [x] `just test` 全绿。

## Comments

### Schema / 行为（供 07 回写）

- 出口字段 `consume_key: true`：`unlock` 成功后销毁钥匙；默认 `false`（标准门不耗钥）。
- 出口字段 `hidden_until_unlocked: true`：加载时进 `HiddenExits`（不进 `Exits`）；`look`/`go` 不可见；门命令可 `unlock`；成功后迁入 `Exits` 且门直接 `open`。
- 房间 `block_exits: { <dir>: {npc: <模板键>} }`：该向在对应 `NpcSpawnMeta.template_key` 在场时拒走。
- 官方：`yangzhou_hanlin`（东大街 `northeast`）+ `yangzhou_hanlin_neiyuan` + `yangzhou_hanlin_garden`；`ling_hanlin` 挡西；`hanlin_key` 耗钥揭东。
