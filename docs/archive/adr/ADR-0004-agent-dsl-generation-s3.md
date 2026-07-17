# ADR-0004：Agent 生成 DSL 初稿与修订量度量（S3 copilot 验证）

- 状态：已采纳（S3）
- 日期：2026-07-10
- 阶段：-1 切片 S3
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2（层1 唯一规则表示层）/ §五 dissent 3（层1 原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1 / 4 / 5

## 背景

[06](../xkx-arch/06-阶段-1-实施计划.md) S3 目标：验证阶段 -1 核心价值主张"DSL+Agent 让非程序员创作可玩世界"的两个可量化子项--[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 1（DSL+Agent 创作闭环）+ 5（Agent 修订量）。具体为：Agent（LLM）从 LPC 规格生成垂直切片 DSL 初稿，度量人工修订量，检测 DSL 表达力缺口。

[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 裁决层1 是唯一规则表示层，§五 dissent 3 警示层1 原语蠕变风险（扩充需 ADR + KPI 护栏）。S3 通过让 Agent 真实生成场景，暴露层1 谓词集是否够用，为 S4 扩谓词评估提供真实需求清单。

## 决策

1. **copilot 近似**：阶段 -1 不接入独立 LLM API + Langfuse（M2 才做 Orchestrator），Agent = 本 session 的 LLM（我）基于 LPC 规格源 + layer0/layer1 schema 文档生成初稿。诚实声明范式污染偏差（见下）。
2. **双载体对比**：选两个互补 LPC 区域作为规格输入--xueshan 大轮寺山门（守卫在场+门派+物品供奉 valid_leave）+ zhongnan 重阳宫大门（门派+物品 valid_leave + 门状态机），覆盖两类不同 DSL 建模挑战，修订量有 2 个数据点。
3. **表达力缺口延后 S4**：v0/v1 用现有谓词（present_npc + has_flag）近似核心守卫拦截，无法表达的逻辑（门派/物品/组合/方向/门状态机）记入缺口台账，S4 统一评估扩谓词（按 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3 护栏走 ADR）。
4. **可复用度量框架**：建 `tools/measure_revision.py`（四级校验 + 双比例 diff + GAP 台账），为 M2 Orchestrator 产出校验打基础。

## 度量方法

`tools/measure_revision.py` 对每个场景跑：

- **四级校验**（逐级递进，失败即停）：L1 schema load（pydantic）-> L2 IR 编译 -> L3 build_world -> L4 端到端 go+kill+确定性重放。结构错误 = 失败级数。
- **双比例 diff**：v0 -> v1 的行级 diff。"含注释修订比例"（总览）+"语义修订比例"（过滤纯注释行后 diff）。**kill criteria 5 必须用语义比例**--v0 的 `# GAP:` 标注在 v1 迁移到本 ADR 时会被行级 diff 误计为修订噪声（实测含注释 59.6% vs 语义 24.5%，差异全由注释重组造成）。
- **GAP 台账**：收集 v0 中 `# GAP:` 注释（Agent 初稿自标的表达力缺口）。

## 度量结果

| 场景 | 结构错误 | 含注释修订 | 语义修订 | v0 GAP 数 |
|---|---|---|---|---|
| xueshan_micro | 0 | 61.8% | 28.3% | 4 |
| zhongnan_micro | 0 | 57.4% | 20.7% | 6 |
| **平均** | **0** | **59.6%** | **24.5%** | **5** |

两场景 v1 端到端跑通（go deny/allow + kill resolve_attack + 确定性重放），52 tests 全绿（44 原有 + 8 新 e2e），ruff 全过。

**Agent 典型偏差**（v0->v1 语义修订来源，三类反复出现）：

1. **LPC 字段名混淆**：`neili`（LPC `set("neili")`）误填，schema 字段是 `max_neili`。pydantic `extra=ignore` 静默忽略未知字段，放大此类偏差（不报错但字段缺失用默认值）。
2. **map_skill 推断**：`attack_skill` 从武器类别误推（staff/sword），应查 LPC `map_skill` 映射到招式技能（jingang-chu / quanzhen-jian）。
3. **武器物品 id vs 类别**：`weapon` 填 LPC 物品 id（fachu/changjian）而非武器类别（staff/sword）。

## 表达力缺口台账（S4 统一评估）

去重后 7 类缺口，按层分类：

| 类别 | 缺口 | 来源场景 |
|---|---|---|
| 层1 谓词缺失 | `family`（门派判断） | xueshan + zhongnan |
| 层1 谓词缺失 | `has_item`（物品持有） | zhongnan |
| 谓词组合 | AND 组合（守卫在场 AND 无 flag） | xueshan |
| 谓词组合 | OR 组合（全真教 OR 持香 放行） | zhongnan |
| 规则语义 | allow-wins（deny-wins 无法表达"满足条件放行"） | xueshan + zhongnan |
| 规则语义 | **方向绑定**（EventRule 无 dir 字段，规则全方向生效，守卫规则锁死场景） | e2e 发现，xueshan + zhongnan |
| 事件覆盖 | `accept_object`（物品供奉/交互事件，非 valid_leave） | xueshan |
| 有状态交互对象 | 门状态机（do_knock / call_out 定时关 / 跨房间 exits 同步） | zhongnan |

**方向绑定缺口**（e2e 调试发现，非 v0 自标）：LPC `valid_leave(me, dir)` 是方向绑定的（`if (dir == "north")` 才查守卫），但现有 layer1 `EventRule` 无 dir 字段，`present_npc -> deny` 对所有方向生效，导致守卫房间的所有出口被锁死。Agent v0 未发现此问题（未运行场景），只有 e2e 才暴露--**支持 M2 Orchestrator 必须自动跑四级校验 + e2e**，否则 Agent 产出的"能编译不能玩"缺陷无法捕获。

## 诚实声明

- **范式污染偏差**：我已见 wuxia_micro/academy_micro/age_of_sail_micro 范式 + layer0/layer1 schema 源码，v0 生成时 schema 错误偏少（结构错误 0），修订量可能**偏低**。真实 Agent（无范式先验）修订量预计更高。
- **结构错误 0 是 schema 不足的信号，非 Agent 产出好**：pydantic 仅类型校验 + 无引用完整性 + 无语义校验 + `extra=ignore` 静默忽略未知字段，Agent 错误难以自动捕获。S4 应加强 SchemaValidator（[ir.py](../../engine/src/xkx/dsl/ir.py) 注释提到的四道校验：引用完整性 / Capability / Resource / Dependency）。
- **真实验证延后 M2**：独立 LLM + Langfuse 自动追踪修订量趋势，消除范式污染，覆盖 30 文件表达力校准（[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 4）。本 ADR 数据为 copilot 近似，仅作 S4 扩谓词的需求输入。

## 判定（kill criteria）

- **criteria 5（Agent 修订量）**：语义修订 24.5% < 30% 降级线，**未触发降级**。但 xueshan 28.3% 接近 30%，瓶颈是 LPC->schema 映射文档不足（字段名混淆 / map_skill 推断）。建议 M2 给 Agent 提供 schema 字段映射表 + map_skill 推断规则，预期可降至 < 20%。
- **criteria 1（DSL 表达力）**：7 类缺口说明现有层1 谓词集 + valid_leave 单事件**无法表达典型武侠 valid_leave 逻辑**。这是 kill criteria 1 的真实信号，但按 Q2 决策延后 S4 统一评估，S3 不扩谓词。
- **criteria 4（30 文件表达力校准）**：S3 是 2 文件微观版，不触发 30 文件校准，但本台账为 S4 提供真实需求清单。

## 不做（范围边界）

- 不接入 LLM API / Langfuse（M2）。
- 不扩层1 谓词（S4 统一评估，走 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3 护栏）。
- 不做任务 / 对话 / accept_object 事件 schema（S4）。
- 不做门状态机运行时（有状态交互对象 + 跨房间副作用 + 定时器，S4+ 或阶段 0）。
- 不做 SchemaValidator 四道校验（S4 / 阶段 0，本 ADR 仅记录需求）。
- 不修改 LPC 源（只读规格）。

## 产出位置

- 度量脚本：[tools/measure_revision.py](../../engine/tools/measure_revision.py)
- 场景 v1：[scenes/xueshan_micro/](../../engine/scenes/xueshan_micro/) + [scenes/zhongnan_micro/](../../engine/scenes/zhongnan_micro/)
- 场景 v0 初稿（供 diff）：`scenes/{xueshan,zhongnan}_micro/_draft_v0/`
- e2e 测试：[tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py) + [tests/test_zhongnan_e2e.py](../../engine/tests/test_zhongnan_e2e.py)

## 关联

- [06](../xkx-arch/06-阶段-1-实施计划.md) S3（本切片）/ S4（全量场景 + 扩 schema，下一步）
- [ADR-0002](ADR-0002-resolve-attack-extraction.md) resolve_attack 提取（attack_skill/weapon_label 字段语义来源）
- [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 主题无关性（attack_skill/weapon_label 由题材数据声明的契约，Agent v0 的 map_skill 推断偏差即对此契约理解不足）

## 后续（S4 输入）

1. **层1 谓词扩充评估**（走 dissent 3 护栏 + ADR）：`family_eq` / `has_item` / AND-OR 组合 / `dir` 方向绑定 / allow-wins 语义。其中**方向绑定**最紧迫（否则任何守卫型 valid_leave 都锁死场景，S5 玩家试玩无法进行）。
2. **事件扩充**：`accept_object`（物品交互闭环）。
3. **schema 校验加强**：SchemaValidator 四道校验 + `extra` 字段警告（捕获 neili/max_neili 类静默偏差）。
4. **Agent schema 映射文档**：LPC 字段 -> schema 字段映射表 + map_skill 推断规则，预期降修订量至 < 20%。
5. **有状态交互对象 + 跨房间副作用 + 定时器**（门状态机）：评估是否需阶段 0 子系统规格先行。
