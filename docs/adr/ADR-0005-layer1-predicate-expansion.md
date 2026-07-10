# ADR-0005：层1 谓词扩充（方向绑定 + 组合 + family/has_item）

- 状态：已采纳（S4）
- 日期：2026-07-10
- 阶段：-1 切片 S4
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2（层1 唯一规则表示层）/ §五 dissent 3（层1 原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1；[ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 表达力缺口台账

## 背景

[ADR-0004](ADR-0004-agent-dsl-generation-s3.md) S3 暴露 7 类表达力缺口，其中**方向绑定**最紧迫--[06](../xkx-arch/06-阶段-1-实施计划.md) S3 记录"EventRule 无 dir 字段，规则全方向生效，守卫规则锁死场景"，S5 玩家试玩无法进行。LPC `valid_leave(me, dir)` 是方向绑定的（`if (dir == "north")` 才查守卫），但 S1 layer1 `EventRule` 无方向维度，`present_npc -> deny` 对所有出口生效。

两个 LPC 规格源验证缺口真实性：

- `d/xueshan/shanmen.c`：`dir=="north"` + 葛伦布在场 + NOT(雪山派 OR 血刀门 OR 持酥油 OR 有"酥"标记) -> `notify_fail` deny
- `d/zhongnan/gate.c`：`dir=="north"` + NOT(全真教 OR 持香) -> `notify_fail` deny

[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 裁决层1 是唯一规则表示层，§五 dissent 3 警示层1 原语蠕变风险（扩充需 ADR + KPI 护栏）。本 ADR 即该护栏落地。

## 决策

1. **方向绑定**：`EventRule` 加 `dir: str = ""`。空 = 全方向生效（向后兼容 S1-S3 场景）；非空 = 仅该方向匹配时规则参与求值。
2. **组合谓词**：`Predicate` 支持 `all`(AND) / `any`(OR) / `not`(取反) 递归组合。叶子谓词（`always`/`attr_lt`/`age_lt`/`present_npc`/`has_flag`/`family_eq`/`has_item`）+ 组合节点可表达任意布尔条件，无需更多谓词类型。
3. **`family_eq` 谓词**：actor 门派 == value（LPC `me->query("family/family_name")`）。映射 LPC 门派判断。
4. **`has_item` 谓词**：actor 持有指定物品（LPC `present(obj, me)`）。映射 LPC 物品持有判断。
5. **allow-wins 不单独引入**：`not + deny-wins` 等价表达"满足条件放行"。zhongnan"全真教或持香放行" = `NOT(family_eq(全真教) OR has_item(incense)) -> deny` 的反面。避免新增规则语义维度。

## dissent 3 护栏（原语蠕变控制）

- 新增 1 个规则维度（dir）+ 3 个组合节点（all/any/not）+ 2 个叶子谓词（family_eq/has_item），**均有 LPC 规格源实证**（xueshan/zhongnan valid_leave），非预判抽象、非为泛化而泛化。
- **不引入**：独立规则引擎 / RETE / OPA / Drools（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q2 否决）；独立 DSL 语法（层1 IR 即唯一规则表示层）；allow-wins 独立语义（not 等价）；更多叶子谓词（按需走 ADR）。
- **KPI**（kill criteria 1 信号）：xueshan + zhongnan 完整 `valid_leave` 逻辑可用扩充后谓词集表达，**无逃生舱**（不依赖 Python 回调 / 不退化为 raw code）。本 ADR 实现后验证。

## EvalContext 扩展

`EvalContext` 加 `actor_family: str = ""` + `actor_items: set[str]`，由 `commands.go` 从 ECS 组件（`Attributes.family` + `Inventory`）构造。`evaluate` 在规则遍历时先做方向过滤（`rule.dir` 非空且 `!= ctx.dir` 则跳过），再求 condition。

## 产出位置

- [layer1.py](../../engine/src/xkx/dsl/layer1.py)：dir + 组合谓词 + family_eq/has_item + EvalContext 扩展
- [components.py](../../engine/src/xkx/runtime/components.py)：`Attributes.family` + 新 `Inventory` 组件
- [commands.py](../../engine/src/xkx/runtime/commands.py)：`go` 传 family/items
- [world.py](../../engine/src/xkx/runtime/world.py)：`spawn_player` 加 family/inventory 参数
- [scenes/xueshan_micro/rules.yaml](../../engine/scenes/xueshan_micro/rules.yaml) + [scenes/zhongnan_micro/rules.yaml](../../engine/scenes/zhongnan_micro/rules.yaml)：完整 valid_leave 逻辑
- [test_event_rule.py](../../engine/tests/test_event_rule.py) + [test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py) + [test_zhongnan_e2e.py](../../engine/tests/test_zhongnan_e2e.py)

## 结果

- **64 tests 全绿**（52 原有 + 12 新增），ruff 全过。
- **KPI 达标（kill criteria 1 信号）**：xueshan + zhongnan 完整 `valid_leave` 逻辑（含方向绑定 / 门派 / 物品 / AND-OR 组合）可用扩充后谓词集表达，**无逃生舱**（不依赖 Python 回调 / raw code）。
- **方向绑定缺口解决**：守卫规则不再锁死场景所有出口。xueshan/shanmen 的 `eastdown` 方向、zhongnan/gate 的 `southdown` 方向现在放行（测试 `test_go_eastdown_allowed` / `test_go_southdown_allowed` 验证），S5 玩家试玩路径打通。
- **兑现 [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 表达力缺口台账 5/7 类**：方向绑定 / `family` / `has_item` / AND-OR 组合 / allow-wins（`not + deny-wins` 等价）。剩余 2 类（`accept_object` 事件 / 门状态机）属 S4 后续子任务。
- **e2e 放行路径验证**：xueshan 雪山派/持酥油 -> north 放行；zhongnan 全真教/持香 -> north 放行（对照 LPC `return 1` 放行分支）。
- **度量脚本 [measure_revision.py](../../engine/tools/measure_revision.py) L1-L4 全绿**，结构错误 0（场景 v1 四级校验通过）。
- 新增 12 测试：方向绑定 2 + 组合谓词 5（all/any/not/family_eq/has_item）+ 嵌套组合 1（xueshan 完整模式）+ e2e 放行 4（xueshan family/item + zhongnan family/item）。

## 不做（范围边界）

- 不做 `accept_object` 事件 schema（S4 后续子任务）。
- 不做任务 / 对话 schema（S4 后续子任务）。
- 不做 SchemaValidator 四道校验（S4 / 阶段 0）。
- 不做门状态机运行时（S4+ / 阶段 0）。
- 不做 Agent schema 映射文档（S4 后续子任务）。
- 不修改 LPC 源（只读规格）。

## 关联

- [06](../xkx-arch/06-阶段-1-实施计划.md) S4（本切片）
- [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 表达力缺口台账（本 ADR 兑现其中 5 类：方向绑定 / family / has_item / AND-OR / allow-wins）
