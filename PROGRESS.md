# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。

**最后更新**：2026-07-10
**当前阶段**：阶段 -1 垂直切片平台验证（2-3 月，★ 最高优先级）
**当前状态**：S4f Agent schema 映射文档完成，S4 全部实施子任务完成（99 tests）。阶段 -1 kill criteria 1 全量验证通过（8 房间 + 2 NPC + 1 任务 + 2 对话全 DSL）。S5 玩家试玩待推进。

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

- [x] **S4a 层1 谓词扩充（方向绑定 + 组合 + family/has_item）完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S4 / [ADR-0005](docs/adr/ADR-0005-layer1-predicate-expansion.md)）：
  - EventRule 加 `dir` 方向绑定（空=全方向向后兼容；对齐 LPC `valid_leave(me,dir)` 的 `if(dir=="north")`）
  - Predicate 支持 `all`/`any`/`not` 递归组合（任意布尔条件）
  - 新增 `family_eq`（LPC family/family_name）+ `has_item`（LPC present）谓词；EvalContext 加 actor_family/actor_items
  - allow-wins 不单独引入（`not + deny-wins` 等价）
  - xueshan + zhongnan 完整 valid_leave 逻辑（对照 LPC shanmen.c/gate.c），**无逃生舱**（KPI 达标）
  - 解决方向绑定缺口（守卫规则不再锁死场景，S5 试玩路径打通）
  - 兑现 ADR-0004 表达力缺口台账 5/7 类（方向绑定/family/has_item/AND-OR/allow-wins）
  - **64 tests 全绿（+12），ruff 全过**

- [x] **S4b accept_object 事件 + inquiry 对话 + set_flag 副作用完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S4 / [ADR-0006](docs/adr/ADR-0006-accept-object-inquiry-set-flag.md)）：
  - accept_object 事件（layer1）：EventRule 加 npc_id/item_id 绑定 + `set_flag` action；首匹配求值（对照 LPC `accept_object(who, ob)`）
  - inquiry 对话（layer0）：`NpcDef.inquiry`（topic -> reply 静态字符串）；`ask` 命令（对照 LPC `set("inquiry")`）
  - Marks 组件：存储玩家临时标记（LPC `set_temp("marks/X")`）；补全 S4a 遗漏（`go` 传 `actor_flags`，has_flag 谓词在 e2e 生效）
  - `give` 命令：give <npc> <item> -> accept_object 规则 -> set_flag/deny + 物品移出
  - xueshan gelun1 完整交互闭环：ask 对话 + give 酥油罐 -> set marks/酥 -> 物品消耗后 go north 仍放行（has_flag 替代 has_item）
  - 兑现 ADR-0004 缺口台账 accept_object 项（剩余 1 类：门状态机）
  - **75 tests 全绿（+11），ruff 全过**

- [x] **S4c 最小任务系统完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S4 / [ADR-0007](docs/adr/ADR-0007-minimal-quest-system.md)）：
  - QuestDef / QuestObjective / QuestReward（layer0）；QuestLog 组件跟踪玩家任务状态
  - `ask` 接任务（quest trigger 优先于 inquiry）、`give` 完成任务、`quest` 查询命令
  - 任务目标 S4 最小集：`give_item`（kill_npc/reach_room 后置）；奖励 S4 最小集：`exp` + `flag` + `message`
  - xueshan 供奉任务完整闭环：ask 还愿 -> `in_progress` -> give 酥油 -> `completed` + exp + flag 酥 -> go north 放行
  - **阶段 -1 kill criteria 1 的"1 任务 + 1 对话全 DSL"验证通过**
  - **83 tests 全绿（+8），ruff 全过**

- [x] **S4d SchemaValidator 四道校验完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S4 / [ADR-0008](docs/adr/ADR-0008-schema-validator-four-checks.md)）：
  - `SceneValidator` 四道校验（[validator.py](engine/src/xkx/dsl/validator.py)）：SchemaValidator（pydantic strict + 未知字段警告，捕获 `neili`/`max_neili` 类静默偏差）/ CapabilityAuditor（`attack_skill` 须在 `skills` 中）/ ResourceBudgetChecker（`max_qi` 等非负）/ DependencyResolver（room/npc/quest/rule 引用完整性）
  - 阶段 -1 最小实现，作为 warning/测试门禁不阻塞编译（完整 jsonschema/CPK/fuel/networkx 后置 M2/阶段 0）
  - [measure_revision.py](engine/tools/measure_revision.py) L2 后集成四道校验输出 warnings；xueshan_micro 四道校验问题为 (无)
  - **92 tests 全绿（+9），ruff 全过**

- [x] **S4e 扩展到 8 房间全量验证完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S4 / kill criteria 1 全量）：
  - xueshan_micro 从 3 房间扩到 8 房间（+ frontyard/yanwu/zoulang/jingang/chufang，对照 LPC 同名 .c），guangchang 加 north exit 接入扩展路径
  - 第二 NPC 小喇嘛 xlama2（chufang，对照 d/xueshan/npc/xlama2.c）：inquiry 酥油茶静态回复
  - GAP（后置）：xlama2 ask_tea 的 set_flag 茶 + accept_object 酥油的 clear_flag + 物品生成需 ask->action 机制 / clear_flag action / 物品系统（S4+/阶段 0）
  - **阶段 -1 kill criteria 1 全量验证通过**（8 房间 + 2 NPC + 1 任务 + 2 对话全 DSL，无逃生舱）
  - measure_revision L1-L4 + 四道校验全绿，结构错误 0；修订比例 75% 系规模扩展（3->8 房间）非 Agent 质量信号
  - **99 tests 全绿（+7），ruff 全过**

- [x] **S4f Agent schema 映射文档完成**（[07](docs/xkx-arch/07-agent-schema-mapping.md) / [ADR-0004](docs/adr/ADR-0004-agent-dsl-generation-s3.md) §后续 4）：
  - [07-agent-schema-mapping.md](docs/xkx-arch/07-agent-schema-mapping.md)：LPC -> schema 字段映射表（NpcDef/RoomDef/EventRule/QuestDef）+ map_skill 推断三规则 + 三类偏差陷阱（neili/max_neili、attack_skill 武器类别、weapon 物品 id）
  - 目标：M2 独立 LLM 按此文档生成初稿，预期降修订量 < 20%（ADR-0004 copilot 24.5% -> < 20%）
  - 完整示例：gelun1 LPC -> DSL 推断全过程（weapon 类别 / attack_skill map_skill 推断 / inquiry 函数式转静态）
  - **S4 全部实施子任务完成（S4a-S4f）**

## In Progress

（无 -- S4 全部实施子任务完成 S4a-S4f，阶段 -1 两个技术 kill criteria 通过，S5 待启动）

## Blocked

（无）

## Next Up

**S5：3-5 名玩家试玩**（阶段 -1 kill criteria 3，"觉得好玩"达可继续投入阈值）--8 房间扩展路径 + 物品交互 + 任务闭环已打通，试玩路径可行。
- S5a 技术准备：最小可玩 CLI REPL（input loop 解析 go/kill/ask/give/quest）+ 补试玩缺口（玩家物品获取、多回合战斗、死亡/复活）
- S5b 找 3-5 名玩家试玩 + 收集"好玩"反馈

**后置项**（S4+/阶段 0）：
- 门状态机运行时（do_knock / call_out 定时关 / 跨房间 exits 同步）
- ask->action 机制 / clear_flag action / 物品生成（xlama2 酥油茶交互闭环，S4e GAP）

S2-S4f 简化项（门状态机运行时、riposte 递归、hit_ob/hit_by mapping、action_* 外提、动态回复函数、kill_npc/reach_room 任务目标、物品/金钱奖励、ask->action/clear_flag/物品生成）按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md) / [ADR-0003](docs/adr/ADR-0003-combatkernel-theme-neutrality.md) / [ADR-0004](docs/adr/ADR-0004-agent-dsl-generation-s3.md) / [ADR-0005](docs/adr/ADR-0005-layer1-predicate-expansion.md) / [ADR-0006](docs/adr/ADR-0006-accept-object-inquiry-set-flag.md) / [ADR-0007](docs/adr/ADR-0007-minimal-quest-system.md) / [ADR-0008](docs/adr/ADR-0008-schema-validator-four-checks.md) 表在 S4+ 或阶段 0 补全。

## 阶段 -1 的 kill criteria（开工必读）

- DSL+Agent 创作闭环验证失败（垂直切片无法用 DSL+Agent 完成且行为等价）-> **停项**，不投入引擎重构。
- 非武侠微场景无法验证 CombatKernel 内核主题无关性 -> **暂停**，先做内核主题无关性重构。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`cd engine && .venv/bin/python -m pytest`（venv 在 `engine/.venv`；系统 Python 受 PEP 668 限制需 venv）；lint：`cd engine && .venv/bin/ruff check src tests`。
