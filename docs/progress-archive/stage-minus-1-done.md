# Done 归档 - 阶段 -1（前置 + S1-S5b 垂直切片）

> 从 PROGRESS.md 归档于 2026-07-14。阶段 -1 已完成条目的历史记录，按需检索。
> 当前活状态见 [PROGRESS.md](../../PROGRESS.md)。

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

- [x] **S5a 试玩技术准备完成**（[06](docs/xkx-arch/06-阶段-1-实施计划.md) S5 / kill criteria 3 前置）：
  - 最小可玩 CLI REPL（[cli.py](engine/src/xkx/cli.py)）：input loop 解析 go/get/kill/ask/give/quest/look/inventory/hp/help/quit + 方向简写（n/s/e/w/ed/wu 等），加载 xueshan_micro 场景
  - 补试玩缺口 1 玩家物品获取：RoomDef/RoomComp 加 `items` 字段（房间地面物品）+ `get`/`take` 命令拾取 + `look` 显示房间/NPC/物品/出口 + `inventory` 查物品栏；dshanlu 放 suyou_guan
  - 补试玩缺口 2 多回合战斗：`kill` 从 S1 单回合改为多回合循环（最多 30 回合，每回合 player 攻 + npc 反击，至一方倒下或回合上限）；CLI 逐条打印 + 0.25s 停顿模拟 LPC heart_beat 节奏
  - 补试玩缺口 3 死亡/复活：NPC 死亡移除 Position（从房间消失）+ 击杀者 +50 exp；玩家死亡传送回 `Game.spawn_room` + 恢复 qi/jingli；昏迷文本用 LPC 原文（"眼前一黑..." / "有了知觉..."，对照 feature/damage.c:125,146）
  - LPC 保真打磨（对照 LPC 源码）：
    - look 改 LPC 格式：NPC 每行 `名字(id)` 如 `葛伦布(ge lunbu)`（feature/name.c short）；出口 `这里明显的出口是 A、B 和 C。`（cmds/std/look.c 末两个用"和"连接）
    - `get` 命令为主（cmds/std/get.c），`take` 保留别名
    - 方向简写：直接输入 n/s/e/w 等即移动（LPC room init 为每个 exit 注册 add_action），对齐 go.c default_dirs
    - ItemDef 层0 定义（id + name + aliases）+ Game.item_registry；look/inventory 显示 `酥油罐(suyou_guan)` 中文名(id) 格式（对照 d/xueshan/obj/suyouguan.c set_name）
    - take/give 支持按 id 或中文名查找（对齐 LPC present）
  - 完整试玩路径打通：look -> go eastdown -> get 酥油罐 -> go westup -> ask 还愿 -> give 葛伦布 酥油罐 -> quest 完成 -> go north 放行 -> 探索 8 房间 -> kill 小喇嘛/葛伦布
  - 4 个 e2e 测试适配多回合 kill（kill 前保存 NPC eid，NPC 倒下后 Position 移除不影响 Vitals 查询）
  - **118 tests 全绿（+19），ruff 全过**
  - 分支 `feat/s5-playtest` 已 push，4 个提交：4ec0b2d2 / 6bc75498 / d808b8d9 / a3dbaf42

- [x] **S5b 玩家试玩（创建者自评）完成**（kill criteria 3）：
  - 创建者自评：保真度与原版侠客行相当，"觉得好玩"达可继续投入阈值
  - 完整试玩路径验证通过：look -> go eastdown -> get 酥油罐 -> go westup -> ask 还愿 -> give 葛伦布 酥油罐 -> quest 完成 -> go north 放行 -> 探索 8 房间 -> kill 小喇嘛/葛伦布
  - kill criteria 3 判定通过（创建者近似 = 目标玩家画像，M3 前补外部玩家测试）
  - **阶段 -1 决策检查点 5/5 全部为是**：DSL 表达力 ✅ / Agent 修订量 24.5% ✅ / 觉得好玩 ✅ / resolve_attack 纯函数 ✅ / 非武侠主题无关性 ✅

