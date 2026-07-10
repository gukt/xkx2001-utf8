# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。

**最后更新**：2026-07-10
**当前阶段**：阶段 -1 垂直切片平台验证（2-3 月，★ 最高优先级）
**当前状态**：S3 Agent 生成 + 修订量度量完成（52 tests），语义修订 24.5% < 30% 降级线，准备 S4 全量场景 + 扩 schema。

## Done

- [x] 三轮架构复审完成，v3 收敛版定稿（[docs/xkx-arch/](docs/xkx-arch/) 00-06 + README）
- [x] 3 个开放问题裁决（Q1 有条件采纳 / Q2 否决 6:0 / Q3 有条件采纳），见 [02](docs/xkx-arch/02-三个开放架构问题裁决.md)
- [x] 交接系统：[PROGRESS.md](PROGRESS.md) + [CLAUDE.md](CLAUDE.md) + [docs/adr/](docs/adr/) ADR
- [x] [engine/](engine/) Python 项目骨架（[ADR-0001](docs/adr/ADR-0001-python-toolchain-and-skeleton.md)）
- [x] **S1 第一垂直切片完成**（[06 实施计划](docs/xkx-arch/06-阶段-1-实施计划.md) / [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md)）：
  - resolve_attack 纯函数（从 combatd.c do_attack 七步提取，dodge/parry/hit + seeded RNG + 副作用账本）
  - 层0 schema（RoomDef/NpcDef + IR 编译）
  - 层1 事件规则（valid_leave + deny-wins 薄求值器）
  - 最小 ECS + 场景加载 + 战斗桥接（to_snapshot/apply_effects）
  - 命令管线（go 移动 + valid_leave / kill 战斗 + resolve_attack）
  - 最小场景（2 房间 + 1 官兵 + 1 valid_leave 规则）
  - 端到端：YAML -> IR -> ECS -> go(deny/allow) -> kill(resolve_attack) -> 确定性重放
  - **30 tests 全绿，ruff 全过**

- [x] 04 补后置能力条目：输入侧 AI 意图识别 + 语音（自然语言/语音 -> 标准 Command 前置层），记入 [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三后置阶段表 + §六不做清单；触发条件 = 外部玩家测试阶段（与迁 PG 同分界），边界 = 管线第 0 段前置、翻译后 Command 进 input log 保 Q3 确定性重放（类比 Agent NPC "LLM 在边界"）。

- [x] **S2 非武侠微场景验证 CombatKernel 主题无关性完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S2 / [ADR-0003](docs/adr/ADR-0003-combatkernel-theme-neutrality.md)）：
  - S1 留口审查发现 3 个武侠硬编码点：武器->技能映射（`_select_attack_skill`）、武器->标签映射（`_WEAPON_LABEL`）、neili 进核心签名
  - 最小重构：attack_skill/weapon_label 外提到题材数据声明，resolve_attack 删 `_select_attack_skill`/`_WEAPON_LABEL`，neili 移出 CombatantSnapshot（Vitals 保留）
  - 非武侠微场景：大航海（火枪 firearm，attr_lt）+ 书院（戒尺 ruler，present_npc），端到端 go+kill+确定性重放
  - 主题无关性硬门禁自动化（test_theme_neutrality.py）：非武侠 snapshot 走声明映射 + resolve_attack 源码无 sword/blade 字面量 + neili 不在核心签名
  - **44 tests 全绿，ruff 全过**

- [x] **S3 Agent 生成 DSL 初稿 + 修订量度量完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S3 / [ADR-0004](docs/adr/ADR-0004-agent-dsl-generation-s3.md)）：
  - copilot 近似：Agent（LLM）从 LPC 规格生成 xueshan + zhongnan 两场景 v0 初稿 -> 专家修订 v1
  - 度量脚本 [tools/measure_revision.py](engine/tools/measure_revision.py)：四级校验（schema/IR/build_world/e2e）+ 双比例 diff（含注释 vs 语义）+ GAP 台账
  - 度量结果：结构错误 0（schema 弱校验信号，非 Agent 产出好）、语义修订 24.5%（< 30% 降级线）、Agent 典型偏差 3 类（neili/max_neili 混淆、map_skill 推断、武器 id vs 类别）
  - 表达力缺口台账 7 类：family/has_item 谓词、AND-OR 组合、allow-wins、**方向绑定（e2e 发现，EventRule 无 dir 字段锁死场景，S4 最紧迫）**、accept_object 事件、门状态机
  - 诚实声明：阶段 -1 copilot（Agent = 本 session LLM，范式污染偏差，M2 独立 LLM + Langfuse 真验证）
  - **52 tests 全绿，ruff 全过**

## In Progress

（无 -- S3 已完成，S4 待启动）

## Blocked

（无）

## Next Up

**S4：全量场景 + 扩 schema 评估**（阶段 -1 kill criteria 1/4 收尾）：

- 扩展到 5-10 房间 + 2 NPC + 1 任务 + 1 对话全 DSL
- 层1 谓词扩充评估（走 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3 护栏 + ADR）：**方向绑定（最紧迫，否则守卫型 valid_leave 锁死场景，S5 无法试玩）** / family / has_item / AND-OR / allow-wins
- 事件扩充：accept_object（物品交互闭环）
- 任务 / 对话 schema
- SchemaValidator 四道校验加强（捕获 neili/max_neili 类静默偏差）
- Agent schema 映射文档（LPC -> schema 字段 + map_skill 推断，预期降修订量 < 20%）

S2/S3 简化项（门状态机运行时、riposte 递归、hit_ob/hit_by mapping、action_* 外提）按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md) / [ADR-0003](docs/adr/ADR-0003-combatkernel-theme-neutrality.md) / [ADR-0004](docs/adr/ADR-0004-agent-dsl-generation-s3.md) 表在 S4+ 或阶段 0 补全。阶段 -1 剩余子任务（S5 玩家试玩）见 [06](docs/xkx-arch/06-阶段-1-实施计划.md)。

## 阶段 -1 的 kill criteria（开工必读）

- DSL+Agent 创作闭环验证失败（垂直切片无法用 DSL+Agent 完成且行为等价）-> **停项**，不投入引擎重构。
- 非武侠微场景无法验证 CombatKernel 内核主题无关性 -> **暂停**，先做内核主题无关性重构。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`pytest /home/gukt/github/xkx2001-utf8/engine`；lint：`ruff check /home/gukt/github/xkx2001-utf8/engine/src /home/gukt/github/xkx2001-utf8/engine/tests`。
