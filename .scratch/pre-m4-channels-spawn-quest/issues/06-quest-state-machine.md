---
Status: resolved
---

# 06 — 声明式 Quest 状态机 + 官方镖局→向导闭环

**What to build:** 场景 YAML 新增 `quests.<id>` 声明式表：接取条件（至少支持"同房间某 NPC 模板"）、完成条件（本波仅"交出指定物品"+"旗标满足"两类）、奖励（至少支持给钱）。玩家侧维护可序列化的任务旗标/进度（进存档、restore 后仍在）。玩家用 `quest accept <id>` 接取（不满足条件时清晰拒绝、状态不变；已在进行中重复接取被拒）。完成靠玩家对目标 NPC 执行 `give`（复用票 `01` 的命令）触发结算——命中该任务完成条件时状态转为已完成、发放奖励并给提示；`ask`/`Inquiry` 保持纯文案，不作为任务入口（回归测试锁定，故意与 LPC `ask ... about 工作` 手感不同）。官方场景挂**恰好一条**示例任务：在 `yangzhou_biaoju`（龙门镖局）与镖头（已存在的 NPC）同房 `quest accept` 接取镖运任务，携带镖货物品（新增物品模板，用票 `02` 的房间 `objects` 写法登记在合适房间，如镖局内）跨区域移动到 `huashan_guide`（华山向导房），对 `huashan_guide_npc`（已存在的 NPC）执行 `give` 交货完成任务并领钱。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US20–28。

**Blocked by:** 01（`give` 命令作为完成结算的挂载点）、02（镖货物品用新版房间 `objects` 写法登记，避免落地即用退役字段）。

- [ ] 玩家旗标/任务进度组件（新增，或复用现有存档友好组件模式）：记录每个 `quest_id` 的状态（未接取/进行中/已完成），随存档序列化、restore 后保留（`save.py` 对应 codec 扩展，参照现有组件存档写法）。
- [ ] 场景 YAML `quests.<id>` schema：接取条件（同房 NPC 模板键）、完成条件（`give_item: <模板键>` / 旗标满足，本波固定两类）、奖励（`currency: <amount>`，给物可选——若实现成本低可做，否则票内注明本波只给钱）。
- [ ] `commands.py` 新增 `quest accept <id>`：校验接取条件（含同房 NPC），成功写入"进行中"状态并给提示；条件不满足给清晰失败文案、状态不变；已是"进行中"或"已完成"重复接取被拒。
- [ ] `give` 命令（票 `01`）结算钩子：给予对象是任务声明的目标 NPC、物品匹配 `give_item` 模板键、且该任务处于"进行中"时，转为"已完成"、发放奖励（如 `Currency` 增加）、消耗该物品、给完成提示；不满足以上任一条件的 `give` 仍走票 `01` 的普通转移语义，不报任务相关文案。
- [ ] `ask`/`Inquiry` 不产生任何任务副作用（回归测试：对任务相关 NPC `ask` 不会触发接取/完成）。
- [ ] 官方场景新增：镖货物品模板 + 房间 `objects` 登记（票 `02` 写法）；`quests.<id>` 一条（`yangzhou_biaoju` 镖头同房接取 → `huashan_guide_npc` 处 `give` 完成 + 领钱奖励），任务 id 与镖货模板键命名稳定可测。
- [ ] 创作者契约 v0（`docs/creator-contract-v0.md`）新增顶层段 `quests` 与其已知字段集。
- [ ] 测试（S1+S3）：`quest accept` 成功/失败文案与状态；`give` 命中完成条件时的状态转移、奖励发放、消耗物品；重复接取被拒；`ask` 不接任务；官方场景端到端脚本（加载 `m2_mvp_scene.yaml` → 在 `yangzhou_biaoju` 接取 → 移动到 `huashan_guide` → `give` → 断言奖励与完成态）；任务旗标 save/restore 后仍在。
- [ ] `just test` 全绿。

## Comments

- 2026-07-22 实现：`QuestDef`/`QuestProgress`/`quest accept`；give 成功路径挂交物完成结算；旗标完成经 `set_quest_flag`；官方 `escort_delivery`（镖局→向导，赏 50 两）；契约增 `quests` 段。测：`test_quest.py`（含 S3 官方闭环 + save/restore）。
