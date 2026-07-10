# ADR-0007：最小任务系统（QuestDef + QuestLog + ask/give/quest 命令）

- 状态：已采纳（S4）
- 日期：2026-07-10
- 阶段：-1 切片 S4
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 / §五 dissent 3（原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1；[ADR-0006](ADR-0006-accept-object-inquiry-set-flag.md)（accept_object/inquiry 已铺路）

## 背景

阶段 -1 kill criteria 1 要求垂直切片"5-10 房间 + 2 NPC + 1 战斗 + 1 任务 + 1 对话全 DSL"。对话（inquiry）已在 [ADR-0006](ADR-0006-accept-object-inquiry-set-flag.md) 落地；本 ADR 覆盖"1 任务"。

LPC 任务交互散见于 NPC 回调（如 `d/xueshan/npc/gelun1.c`：ask about 还愿 -> 提示给酥油；`accept_object` 收酥油 -> 设标记/放行；又如 `d/forest/npc/qiu.c`：ask about 药丸 -> 设购买标记；给钱 -> 给药）。本 ADR 从中抽象最小任务 DSL，不覆盖完整 job_system（clone/obj/job.sav/ 太复杂，阶段 0 再评估）。

## 决策

1. **QuestDef（layer0 数据）**：任务声明 = id + name + giver(NPC) + trigger(ask 话题) + description + objective + reward。
2. **QuestObjective（S4 最小集）**：仅 `kind="give_item"` + `npc_id` + `item_id`。kill_npc/reach_room 等目标后置。
3. **QuestReward（S4 最小集）**：`exp` + `flag`（完成后设置标记）+ `message`。物品/金钱奖励后置。
4. **QuestLog 组件**：玩家任务状态 `{quest_id: "not_started" | "in_progress" | "completed"}`。
5. **ask 接任务**：`ask <giver> about <trigger>` 且 QuestLog 为 `not_started` 时 -> `in_progress`，返回 description。
6. **give 完成任务**：`give <npc> <item>` 后，若匹配某 `in_progress` 任务的 `give_item` objective -> 发放 reward + `completed`。
7. **quest 查询命令**：`quest list` 列出所有任务状态；`quest status <id>` 查单个任务。

## dissent 3 护栏（原语蠕变控制）

新增 3 个数据模型（QuestDef/QuestObjective/QuestReward）+ 1 组件（QuestLog）+ 1 命令（quest）+ ask/give 的任务分支。**规格源为 LPC NPC 任务交互模式**（gelun1.c ask + accept_object），非预判抽象。

**不引入**：任务链/日常/限时、完整 job_system 集成、kill_npc/reach_room 目标、物品/金钱奖励、任务面板 UI、任务共享。均后置阶段 0 / M2。

## 产出位置

- [layer0.py](../../engine/src/xkx/dsl/layer0.py)：QuestDef / QuestObjective / QuestReward
- [ir.py](../../engine/src/xkx/dsl/ir.py)：`compile_quest` + `compile_scene` 加 quests
- [components.py](../../engine/src/xkx/runtime/components.py)：`QuestLog` 组件
- [commands.py](../../engine/src/xkx/runtime/commands.py)：ask 接任务 + give 完成任务 + quest 查询
- [world.py](../../engine/src/xkx/runtime/world.py)：`build_world` 加 quest 索引 + `spawn_player` 加 QuestLog
- [scenes/xueshan_micro/quests.yaml](../../engine/scenes/xueshan_micro/quests.yaml)：xueshan 供奉任务
- [test_quest.py](../../engine/tests/test_quest.py) + [test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)

## 结果

- **83 tests 全绿**（75 原有 + 8 新增），ruff 全过。
- **QuestDef / QuestObjective / QuestReward（layer0）+ QuestLog 组件落地**：任务状态 `{quest_id: not_started | in_progress | completed}` 可序列化。
- **命令落地**：ask 接任务（quest trigger 优先于 inquiry）、give 完成任务、quest 查询。
- **完整任务闭环验证**：xueshan 供奉任务 `ask 还愿 -> in_progress -> give 酥油 -> completed + exp + flag 酥 -> go north 放行`。DSL 能表达"接任务 -> 完成目标 -> 获得奖励 -> 状态变更影响世界规则"闭环，**无逃生舱**。
- **阶段 -1 kill criteria 1 的"1 任务 + 1 对话全 DSL"验证通过**（对话 S4b、任务 S4c）。
- **度量脚本 [measure_revision.py](../../engine/tools/measure_revision.py) L1-L4 全绿**，结构错误 0。
- 新增 8 测试：`test_quest.py` 6（接任务/重复接/完成奖励/完成后 ask/quest 查询/未知 id）+ `test_xueshan_e2e.py` 2（quest trigger / 完整闭环）。

## 不做（范围边界）

- 不做 kill_npc / reach_room 目标类型（S4+ / 阶段 0）。
- 不做物品/金钱奖励（S4+）。
- 不做任务链/日常/限时/共享（阶段 0 / M2）。
- 不做完整 job_system 迁移（阶段 0 评估）。
- 不修改 LPC 源（只读规格）。

## 关联

- [06](../xkx-arch/06-阶段-1-实施计划.md) S4（本切片）
- [ADR-0006](ADR-0006-accept-object-inquiry-set-flag.md) accept_object/inquiry（本 ADR 在其上叠加任务层）
