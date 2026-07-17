# ADR-0006：accept_object 事件 + inquiry 对话 + set_flag 副作用

- 状态：已采纳（S4）
- 日期：2026-07-10
- 阶段：-1 切片 S4
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2（层1 唯一规则表示层）/ §五 dissent 3（原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1；[ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 缺口台账（accept_object）；[ADR-0005](ADR-0005-layer1-predicate-expansion.md)（层1 扩充护栏先例）

## 背景

[ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 缺口台账列 `accept_object` 为 S4 子任务。`d/xueshan/npc/gelun1.c` 实证两类 NPC 级交互：

- `accept_object(who, ob)`：检查物品名 == "酥油罐" -> `set_temp("marks/酥", 1)` + 消息"佛爷保佑施主，里边请。"；否则迷惑拒绝。
- `set("inquiry", ...)`：`ask about 还愿/烧香/供佛` -> `do_huanyuan` -> `say("你拿什麽孝敬佛爷呀？")`。

阶段 -1 kill criteria 1 要求"1 任务 + 1 对话全 DSL"。本 ADR 覆盖对话（inquiry）+ 物品交互（accept_object），为任务系统铺路。

## 决策

1. **inquiry 对话（layer0 数据）**：`NpcDef.inquiry: dict[str, str]`（topic -> reply 静态字符串）。`ask <npc> about <topic>` 查询。动态回复函数后置。
2. **accept_object 事件（layer1 规则）**：`EventRule` 加 `npc_id` + `item_id` 绑定。`event="accept_object"`。**首匹配求值**（按 priority 降序，第一个 condition 匹配的规则触发；不同于 valid_leave 的 deny-wins，给物品是一次性事件）。
3. **set_flag 副作用 action**：`action="set_flag"` + `flag` 字段。命中时设置 actor 标记（LPC `set_temp("marks/X", 1)`）。与 deny/allow 并列。
4. **Marks 组件**：新增 `Marks` ECS 组件（`flags: set[str]`）存储玩家临时标记。补全 S4a 遗漏（`go` 未传 `actor_flags`，has_flag 谓词在 e2e 恒 False）。
5. **give 命令**：`give <npc> <item>` -> 查 accept_object 规则 -> set_flag/deny + 消息。
6. **ask 命令**：`ask <npc> about <topic>` -> 查 NPC inquiry -> reply。

## dissent 3 护栏（原语蠕变控制）

新增 1 事件（accept_object）+ 1 action（set_flag）+ 2 EventRule 字段（npc_id/item_id/flag）+ 1 NpcDef 字段（inquiry）+ 1 组件（Marks）+ 2 命令（ask/give）。**均有 gelun1.c 规格源实证**，非预判抽象。

**不引入**：完整对话树/状态机（后置 M2+/阶段 0）；动态回复函数（后置）；物品堆叠/装备/容器（后置）；任务状态机（S4 后续子任务）；ask 的模糊匹配/别名（第 4 段别名段，纯规则后置）。

## accept_object 求值模型

- 玩家给 NPC 物品 -> 找 `event=accept_object` + `npc_id` 匹配 + `item_id` 匹配的规则
- 按 priority 降序，第一个 condition 匹配的触发（首匹配）
- `set_flag`：接受 + 设置 flag + 消息；`deny`：拒绝 + 消息；`allow`：接受 + 消息
- 无匹配规则：默认接受（无副作用）

## 产出位置

- [layer0.py](../../engine/src/xkx/dsl/layer0.py)：`NpcDef.inquiry`
- [layer1.py](../../engine/src/xkx/dsl/layer1.py)：accept_object 事件 + set_flag + `evaluate_accept_object`
- [components.py](../../engine/src/xkx/runtime/components.py)：`Marks` 组件 + `NpcBehavior.inquiry`
- [commands.py](../../engine/src/xkx/runtime/commands.py)：`ask` + `give` + `go` 传 actor_flags
- [world.py](../../engine/src/xkx/runtime/world.py)：`_spawn_npc` inquiry + `spawn_player` Marks
- [scenes/xueshan_micro/npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml) + [rules.yaml](../../engine/scenes/xueshan_micro/rules.yaml)
- [test_event_rule.py](../../engine/tests/test_event_rule.py) + [test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)

## 结果

- **75 tests 全绿**（64 原有 + 11 新增），ruff 全过。
- **accept_object 事件 + set_flag 副作用落地**：gelun1 接受酥油罐 -> set marks/酥 + 消息 + 物品移出（对照 LPC `accept_object` + `set_temp`）。
- **inquiry 对话落地**：ask 葛伦布 about 还愿/烧香/供佛 -> 静态回复（对照 LPC `set("inquiry")` + `do_huanyuan`）。
- **完整交互闭环验证**：give 酥油罐 -> set marks/酥 -> 物品消耗后 go north 仍放行（has_flag 替代 has_item）。这是阶段 -1 kill criteria 1 的核心信号--DSL 能表达"物品交互 -> 状态变更 -> 移动放行"闭环。
- **补全 S4a 遗漏**：`go` 命令现在传 `actor_flags`（S4a 的 has_flag 谓词在 e2e 中此前恒 False，现已生效）。
- **兑现 [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 缺口台账 accept_object 项**（剩余 1 类：门状态机，S4+ / 阶段 0）。
- **度量脚本 [measure_revision.py](../../engine/tools/measure_revision.py) L1-L4 全绿**，结构错误 0。
- 新增 11 测试：accept_object 求值 5（set_flag/deny/no_match/npc_item_filter/priority_first_match）+ xueshan e2e 6（ask 2 + give 3 + 闭环 1）。

## 不做（范围边界）

- 不做任务 schema（S4 后续子任务，需状态机/目标/奖励）。
- 不做 SchemaValidator 四道校验（S4 / 阶段 0）。
- 不做 Agent schema 映射文档（S4 后续子任务）。
- 不做门状态机运行时（S4+ / 阶段 0）。
- 不修改 LPC 源（只读规格）。

## 关联

- [06](../xkx-arch/06-阶段-1-实施计划.md) S4（本切片）
- [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 缺口台账（本 ADR 兑现 accept_object 项）
- [ADR-0005](ADR-0005-layer1-predicate-expansion.md) 层1 扩充护栏先例（本 ADR 延续同模式）
