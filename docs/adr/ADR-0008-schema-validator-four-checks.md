# ADR-0008：SchemaValidator 四道校验（阶段 -1 最小实现）

- 状态：已采纳（S4）
- 日期：2026-07-10
- 阶段：-1 切片 S4
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2（层1 唯一规则表示层）/ §五 dissent 3（原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1 / 5；[ADR-0004](ADR-0004-agent-dsl-generation-s3.md)（schema 弱校验导致 Agent 偏差无法捕获）

## 背景

[ADR-0004](ADR-0004-agent-dsl-generation-s3.md) 诚实声明：阶段 -1 pydantic 仅类型校验 + 无引用完整性 + 无语义校验 + `extra=ignore` 静默忽略未知字段，Agent 错误（如 `neili`/`max_neili` 混淆、未知字段拼写）难以自动捕获。结构错误 0 是 schema 不足的信号，非 Agent 产出好。

[03](../xkx-arch/03-DSL-UGC与Agent协作.md) §三 定义 IR 经四道校验：SchemaValidator（结构）/ CapabilityAuditor（能力清单）/ ResourceBudgetChecker（资源配额）/ DependencyResolver（依赖图）。该定义面向 M2/CPK 阶段（jsonschema、CPK manifest、fuel、networkx）。本 ADR 将其收缩到阶段 -1 可用的最小实现，作为 Agent 产出校验护栏。

## 决策

阶段 -1 保留四道校验框架，但做最小实现：

1. **SchemaValidator**：pydantic strict 模式 + 未知字段警告。捕获 `neili`（应为 `max_neili`）、拼写错误等 Agent 典型偏差。
2. **CapabilityAuditor**：NPC 能力声明检查。S4 最小：``attack_skill`` 必须在 ``skills`` 中（题材数据声明的武器-招式映射）。
3. **ResourceBudgetChecker**：数值非负检查。``max_qi``/``max_jing``/``max_jingli``/``max_neili``/``combat_exp`` 及任务 ``reward.exp`` 不得为负。
4. **DependencyResolver**：引用完整性。room.objects 引用 npc、room.exits 引用 room、quest.giver/objective.npc_id 引用 npc、rule.npc_id 引用 npc。

实现为 `SceneValidator`（``engine/src/xkx/dsl/validator.py``），提供 ``validate(ir) -> list[str]``。阶段 -1 作为 warning/测试门禁，不阻塞编译（兼容 S1-S4 的宽松校验）。

## dissent 3 护栏（原语蠕变控制）

- 四道校验均有明确目标：捕获 Agent 产出偏差、保证场景可加载、保证引用可达。不引入独立规则引擎/jsonschema/networkx 等额外依赖。
- 阶段 -1 仅做最小检查，完整能力（jsonschema 4.x、CPK manifest 审计、fuel/wall_time 配额、networkx 依赖图）后置 M2/阶段 0。

## 产出位置

- [validator.py](../../engine/src/xkx/dsl/validator.py)：`SceneValidator` 四道校验
- [test_validator.py](../../engine/tests/test_validator.py)：校验器回归测试
- [measure_revision.py](../../engine/tools/measure_revision.py)：L2 后调用 validator，输出 warnings（阶段 -1 不阻塞）

## 结果

- **92 tests 全绿**（83 原有 + 9 新增：`test_validator.py` 9），ruff 全过。
- **四道校验框架落地**：`engine/src/xkx/dsl/validator.py` 提供 `SceneValidator` + `validate(ir)`。
- **SchemaValidator**：pydantic strict + 未知字段警告。可捕获 `neili`（应为 `max_neili`）等 Agent 典型偏差。
- **CapabilityAuditor**：NPC ``attack_skill`` 必须在 ``skills`` 中（题材数据声明的武器-招式映射）。
- **ResourceBudgetChecker**：``max_qi``/``max_jing``/``max_jingli``/``max_neili``/``combat_exp`` 及任务 ``reward.exp`` 非负。
- **DependencyResolver**：room.objects/exits、quest.giver/objective.npc_id、rule.npc_id 等引用完整性。
- **度量脚本 [measure_revision.py](../../engine/tools/measure_revision.py) 集成**：L2 后自动跑四道校验，输出 warnings（阶段 -1 不阻塞 L3/L4）。xueshan_micro 当前四道校验问题为 **(无)**。
- **SCENE_FILES 扩展**：加入 `quests.yaml`，修订比例统计覆盖全部场景文件。

## 不做（范围边界）

- 不做完整 jsonschema 结构校验（M2/阶段 0）。
- 不做 CPK manifest 能力审计（M2）。
- 不做 fuel/wall_time/memory/call_out_quota 配额检查（M2）。
- 不做 networkx 依赖图拓扑排序与环检测（阶段 0）。
- 不修改 LPC 源（只读规格）。

## 关联

- [06](../xkx-arch/06-阶段-1-实施计划.md) S4（本切片）
- [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) Agent 偏差与 schema 弱校验问题
- [03](../xkx-arch/03-DSL-UGC与Agent协作.md) §三 四道校验原始定义
