# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。

**最后更新**：2026-07-11
**当前阶段**：阶段 0 已合并 master，阶段 1 实施计划已产出，待确认启动编码
**当前状态**：阶段 0 全部 9 任务完成并合并到 master（feat/s5-playtest `--no-ff` merge commit `1419d120`，118 files +28882 lines，push origin master）。从 master 开新分支 `feat/stage-1-core-loop`（feat/s5-playtest 保留作阶段 -1~0 历史标记）。阶段 1 实施计划文档产出（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)）：10 个里程碑分解为 T1-T10 任务 + 4 个 Wave（Wave 1 串行 T1-T3 / Wave 2 并行 T4-T6 / Wave 3 并行 T7-T9 / Wave 4 串行 T10 门禁）+ 8 个待写 ADR（ADR-0017~0024，ADR-0017/0018 为 Wave 1 前置）+ 05 §五 10 条 dissent 全映射 + kill criteria 3/6/8 触发条件。680 tests 全绿，ruff 全过。下一步：用户确认启动阶段 1 编码 -> 先写 ADR-0017/0018（ECS SparseSet + Effect 一等公民 + ConditionHandler.on_tick 契约）-> Wave 1 T1。

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

- [x] **阶段 0 任务 2：FluffOS 编译可行性评估完成**（[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md)）：
  - 发现仓库 `driver` 是 FluffOS 3.0.20170907 x86_64 macOS 二进制（非 config.xkx 注释的 MudOS 0.9.20）
  - 通过 Rosetta 2 + libevent 符号链接（2.1.6 -> 2.1.7）在 arm64 macOS 成功运行
  - 全部 daemon 加载成功，端口 8888 监听，nc 连接可见登录界面
  - 结论：现有二进制可运行，无需编译；golden trace 定位为辅助验证手段（非主线）
  - 修正 04 §六不做清单"旧系统不可运行"假设；为 dissent 4 基线测试提供运行时验证路径

- [x] **阶段 0 任务 1 前置：规格提取方法论与实施计划完成**（[ADR-0010](docs/adr/ADR-0010-lpc-spec-extraction-methodology.md) / [08-阶段-0-实施计划.md](docs/xkx-arch/08-阶段-0-实施计划.md)）：
  - 分析侠客行架构拆解说明书（14 份文档 / 36 子系统），发现 go/move/combat 三条路径不足以覆盖核心可玩循环
  - 定义 9 层范围（A-I）：驱动桥梁 / 对象基础 / 命令系统 / 世界构建 / 战斗 / 死亡轮回 / NPC AI / 核心守护进程 / 角色登录，约 4500-5000 行 LPC
  - 方法论：函数级契约（签名+前置/后置条件+不变量+副作用+随机性）+ pydantic v2 模型 + 3 个 Wave 并行提取
  - 避免穷尽细节：不碰 kungfu/(798) + d/(6414)，condition 只提取框架，阴间流程后置，不做 LPC 解析器自动化
  - 为新 session 准备好可直接执行的 9 层并行提取计划

- [x] **阶段 0 任务 1：LPC 规格提取管线 9 层全部完成**（[ADR-0010](docs/adr/ADR-0010-lpc-spec-extraction-methodology.md) / [08-阶段-0-实施计划.md](docs/xkx-arch/08-阶段-0-实施计划.md)）：
  - 基础类型 [base.py](engine/src/xkx/spec/base.py)：FunctionSpec 六要素（签名/前置/后置/不变量/副作用/随机性）+ LayerSpec 集合
  - 3 个 Wave 串行启动、Wave 内 agent 并行提取（Wave 1: A+B+C+D / Wave 2: E+F+G / Wave 3: H+I），9 个 spec 文件 + 9 个 test 文件
  - **总计 160 FunctionSpec / 631 SideEffect / 52 RandomSpec / 151 跨层引用**，覆盖约 7000 行 LPC
  - 层 A 驱动桥梁（25 函数）：master.c 驱动回调 + simul_efun 核心路径（connect/epilog/valid_* / destruct/getoid/living）
  - 层 B 对象基础（24 函数）：F_DBASE 路径访问语义 + temp 变体差异 + F_NAME short() 状态修饰 + F_MOVE 负重级联
  - 层 C 命令系统（10 函数）：command_hook 四分支（direction_shortcut->normal->emote->channel）+ 18 条方向别名 + find_command 逆序搜索
  - 层 D 世界构建（9 函数）：valid_leave 基类契约 + 8 种 override 模式分类（516 文件实证扫描）+ go main() 14 个交织副作用
  - 层 E 战斗系统（26 函数，核心）：**do_attack 七步 49 个副作用严格交织**（state_mutation 与 message_output 不可分离）+ **31 处 random 概率模型**（闪避 dp/(ap+dp)、招架 pp/(ap+pp)、伤害随机化等）+ 三层资源不变量（0<=qi<=eff_qi<=max_qi）+ skill_power 公式
  - 层 F 死亡轮回（10 函数）：die vs unconcious 触发区别（eff_qi<0 直接死 vs qi<0 先昏迷，昏迷中再受创升级死亡）+ death_penalty 完全确定性 + make_corpse 物品转移
  - 层 G NPC AI（12 函数）：heart_beat 七步管线 + auto_fight 三触发优先级（hatred>vendetta>aggressive，call_out 延迟给受害者溜走机会）+ chat 随机对话
  - 层 H 核心守护进程（26 函数）：LOGIN_D 13 阶段状态机（logon->get_id->get_passwd->make_body->enter_world）+ SECURITY_D valid_cmd fail-closed（每条命令都过）+ NATURE_D 时间系统（真实 1 秒=游戏 1 分钟）+ 10 级 wiz_level
  - 层 I 角色与登录（18 函数）：visible() 三级判定（wiz_level > invisibility > 鬼魂）+ user.c save 三步交织（autoload->::save->clean_up）+ PronounContext viewer 不变量 + JSON 存档崩溃安全要求
  - 任务 1 验收标准（08 §四）全部满足：9 层规格产出 / 属性测试骨架 / go+move+combat 覆盖 / 29 处 random 提取 / 三层资源不变量 / do_attack 七步交织顺序 / ruff+pytest 全过
  - **599 tests 全绿（+481），ruff 全过**
  - agent teams 并行提取高效：Wave 内 4/3/2 agent 并行，9 层总提取时间约 25 分钟

- [x] **阶段 0 任务 3 路径 B：规格符合性检查器完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md)）：
  - impl_map（[impl_map.py](engine/src/xkx/spec/impl_map.py)）：do_attack 14 项检查条目三状态标注（12 implemented + 2 simplified），每条关联 ADR-0002 简化台账
  - ConformanceChecker（[conformance.py](engine/src/xkx/combat/conformance.py)）：8 项单次 result 检查（result_code 合法 / damage 非负 / 非命中 damage=0 / effect target 合法 / 命中有 DAMAGE / 闪避招架无 DAMAGE / 三层资源不变量 / 交织顺序）
  - CombatRoundResult 升级 ledger 字段（[result.py](engine/src/xkx/combat/result.py)）：记录 msg/eff 统一调用顺序，验证交织不变量；向后兼容（messages/effects 列表不变，S1 7 tests 不回归）
  - 统计性属性测试 6 项：确定性 / 三分支可达 / 闪避概率 ≈ dp/(ap+dp) / 招架条件概率 ≈ pp/(ap+pp) / ap-dp-pp>=1 / TYPE_QUICK damage<=TYPE_REGULAR
  - 核心价值：resolve_attack S1 简化版与 do_attack 规格的符合性可**自动区分"已知简化"与"真正违反"**（impl_map 三状态过滤），规格演进时检查项自动跟进
  - **612 tests 全绿（+13），ruff 全过**

- [x] **阶段 0 任务 3 路径 A：9 层规格一致性属性测试完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md)）：
  - 9 层 test_spec_*.py 从固定断言升级为 hypothesis 属性测试（4 类属性）：随机函数索引（签名完整 / order 递增连续 / kind 非空 / pre+post 条件）/ 副作用子集（随机子集 order 仍递增）/ random_specs 完整性（probability_model + semantic + lpc_call 非空）/ invariants-side_effects 对应（状态不变量 -> STATE_MUTATION）
  - 跨层一致性测试（[test_spec_cross_layer.py](engine/tests/test_spec_cross_layer.py)）：9 层完整性（layer_id A-I 唯一 / 层名不重 / 单层 lpc_files 不重）+ cross_layer_refs 跨层可解析（目标层 ID 在 A-I 范围 + 非全自引用）+ hypothesis 全局函数索引（跨层任意函数签名完整 / 有副作用或 notes）
  - agent teams 两批并行：批 1（B+C+D+E）+ 批 2（F+G+H+I），层 A 手动示范建立共享模式
  - 智能适配层特点：层 B/H 无前置条件函数仅断言 postcondition / 层 G 用 re 词边界匹配 max_ 避免 MAX_OPPONENT 误命中 / 层 F/I 否定语境排除（"不修改状态"不要求 STATE_MUTATION）/ 层 E 保留 do_attack 七步交织 + 三层资源不变量 + skill_power 公式等核心契约
  - 删除与 hypothesis 重复的固定断言（signature 完整 / order 连续 / random_spec 字段非空），保留层特有契约（do_attack 七步交织 / LOGIN_D 状态机 / visible 三级 / heart_beat 七步 / valid_leave 8 模式等）
  - **676 tests 全绿（+64），ruff 全过**

- [x] **阶段 0 任务 7：灵魂系统盘点完成**（[09-灵魂系统盘点.md](docs/xkx-arch/09-灵魂系统盘点.md)）：
  - 5 个 agent 并行盘点阴间/武林大会/vote/法院/intermud 五个子系统，每个按 7 项模板产出（文件清单/职责/数据流/核心循环关系/themed 治理属性/关键函数/后置建议）
  - **阴间系统**（d/death/ 15 文件）：死亡->阴间->还阳完整路径，黑白无常 5 段对话剧情 + inn1 隐藏还阳路径，gate.c 物品销毁是关键副作用，平台级 fail-closed，阶段 1 实现
  - **武林大会**（d/bwdh/ 297 文件）：个人赛（8 年龄组擂台赛）+ 团体赛（试剑山庄夺旗积分赛），exec 代理机制是 LPC 特有 hack，control.c 53KB 需拆分，sjsz/sjsz2/sjsz3 三份副本需参数化，平台级 fail-closed，阶段 2 实现
  - **vote 投票**（cmds/std/vote/ + condition）：玩家自治频道管理（chblk/unchblk），投票发起->计票->结果执行->超时清理，动议类型封闭枚举，平台级 fail-closed，阶段 2 实现
  - **法院系统**（combatd + condition + NPC）：PK 通缉 + 官府执法 + 监狱服刑 + 玩家投票治理四线交织，killer/xakiller/dlkiller/bjkiller 四种区域通缉，courthouse 反机器人审判是独立子系统，平台级 fail-closed，阶段 1 实现
  - **intermud**（adm/daemons/network/ 24 UDP 服务）：跨 MUD 网络通信，**违反收缩约束**（不考虑分布式架构/网关），建议砍掉/无限期后置，仅跨服频道广播接口预留
  - themed 治理属性汇总：五系统全部平台级 fail-closed，验证 CLAUDE.md 不变量
  - 题材文化系统台账：补充天雷/婚姻/师徒/门派/称号/频道/经济/邮件/emote/finger 十个系统定位
  - 验收标准（04 §三）"无遗漏"满足

- [x] **阶段 0 任务 4 阶段 0 部分：性能 micro-benchmark 完成**（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md)）：
  - [benchmark.py](engine/tools/benchmark.py)：resolve_attack μs 基准（timeit + 三分支 hit/dodge/parry + GC on/off 双测）+ GC 基准（tracemalloc 单次峰值 + gc.get_stats gen0 回收）+ PYTHONHASHSEED 跨进程验证（subprocess 跑 0/1/random 各 3 次比较输出）
  - [test_benchmark.py](engine/tests/test_benchmark.py)：4 项回归门禁（中位数 < 200μs / 单次 < 100KB / 5k 次 gen0 < 1000 / 同 seed 100 次一致），宽松阈值防退化（ADR-0012 决策 6）
  - **μs 基准数据**：hit median 25.9μs / dodge 17.2μs / parry 17.3μs（< 50μs 阈值，p99 < 18μs < 200μs 阈值）；GC on/off 差异 ~0.1μs（resolve_attack 几乎不触发 GC）
  - **GC 基准数据**：单次峰值 5336 bytes（~5KB，CombatRoundResult + Effect + LedgerEntry）；20k 次调用 gen0 回收 0 次（验证 04 §六"CombatRoundResult/Effect 对象池化...GC 是非问题"，对象池决策后置阶段 1 tick profiler 实测后）
  - **PYTHONHASHSEED 验证**：跨进程（0/1/random）输出完全一致（resolve_attack 用 random.Random(seed) 不依赖 hash，combat 确定性基础成立）
  - **go/no-go 判定：GO**（阶段 0 μs 前置数据点充分；1000+100 负载 + 1s tick 预算实测后置阶段 1 框架，kill criteria 3 完整判定需阶段 1）
  - 阈值推导：1000 实体 * tick<100ms，combat 占 50% 预算 -> 1000*X < 50,000μs -> X < 50μs（保守上界，实际 1000 在线活跃战斗者远少于此）
  - 不引入 pytest-benchmark（标准库 timeit 足够，符合 04 §一核心立场 7 收敛原则）
  - **680 tests 全绿（+4），ruff 全过**

- [x] **阶段 0 任务 5：引擎工具链 PRD（最小三件）完成**（[ADR-0013](docs/adr/ADR-0013-engine-toolchain-prd.md)）：
  - 3 个 PRD 文档产出（[entity-inspector](docs/xkx-arch/10-引擎工具链PRD-entity-inspector.md) / [tick-profiler](docs/xkx-arch/10-引擎工具链PRD-tick-profiler.md) / [combat-replay-viewer](docs/xkx-arch/10-引擎工具链PRD-combat-replay-viewer.md)），统一**定位为阶段 1 开发期工具**（非生产运维工具），进程内模块
  - Entity Inspector：只读快照（< 0.1ms/查询）+ LPC F_DBASE 语义映射表（`query("skill/axe")`->`Skills.levels["axe"]`，`query_temp("marks/酥")`->`Marks.flags`）+ CLI `inspect` 命令 + 程序化 API
  - Tick Profiler：per-System compute 统计（mean/p99/max）+ `enabled=False` 零开销 contextmanager + ring buffer；与 ADR-0012 benchmark 分工（μs 微基准 vs tick 宏观，互补构成 kill criteria 3 完整 go/no-go）
  - Combat Replay Viewer：非侵入消费 CombatRoundResult ledger（不修改 combat 内核）+ 可离线回放 + 确定性 diff（同 seed 同 input->同输出）+ 与 ADR-0011 ConformanceChecker 联动（8 项检查）+ 战报归档格式衔接 M1 开源交付物
  - 关联 dissent 3/4/7（性能基线 / 规则冲突语义漂移 / 派生变更审计）
  - 阶段 0 -> 1 决策检查点"引擎工具链 PRD 评审通过"满足
  - agent teams 并行：3 agent 各写一件工具 PRD

- [x] **阶段 0 任务 8：32 守护进程职责重新设计完成**（[ADR-0014](docs/adr/ADR-0014-daemon-responsibility-redesign.md)）：
  - 2 个盘点文档产出（[核心运行时组 15 个](docs/xkx-arch/11-守护进程职责重新设计-核心运行时组.md) / [社交辅助组 16 个](docs/xkx-arch/11-守护进程职责重新设计-社交辅助组.md)），31 个 .c 守护进程逐一标注归属
  - 四类归属：6 ECS System（logind / natured / combatd / channeld / moneyd + ConnectionSystem）/ 12 无状态服务 / 2 新能力（securityd->PermissionService+CapabilityToken / regid->AccountService）/ 12 砍掉后置
  - 关键决策：securityd fail-closed + exclude 优先 trusted / combatd 七步交织 combat 确定性 / rankd PronounContext 三元组 viewer / intermud 三件套砍掉（dns_master/ftpd/socket）/ channeld chblk 平台级 fail-closed / languaged+languanged 完全副本砍掉
  - 关联 dissent 2/5/8（ECS 取代 daemon / themed 治理 / UGC 红线）
  - agent teams 并行：2 agent 各盘点一组

- [x] **阶段 0 任务 9（30 文件表达力校准）完成**（[ADR-0015](docs/adr/ADR-0015-layer-calibration-methodology.md) + [ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md)）：
  - 30 文件 5 批 agent 并行转译，290 语义单元，30 YAML + 30 MD 标注表（[stats.md](engine/tools/layer_calibration/stats.md)）
  - 修正 KPI = 逃生舱层3 11/171 ≈ 6.4% < 15% ✓（区分预期层3 ~56 项 vs 逃生舱层3 ~11 项）
  - KPI 定义修正：回归 03/04 "逃生舱使用率"原意（非"所有层3 占比"），原始层3 35.7% 超标是定义失真非表达力不足
  - 谓词集 8 类缺口扩充决策（attr_eq/is_wizard/has_item 扩展/has_flag 扩展/derived_state/status_eq 系列/has_inquiry+attr_in/命令事件钩子），实现后置阶段 1
  - **阶段 0 -> 1 决策检查点全部满足**，不触发 kill criteria 4
  - agent teams 并行：5 agent 各转译 6 文件

- [x] **分支合并 + 阶段 1 实施计划产出**（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)）：
  - feat/s5-playtest 合并到 master（`--no-ff` merge commit `1419d120`，118 files +28882 lines），push origin master；从 master 开新分支 `feat/stage-1-core-loop`（feat/s5-playtest 保留作阶段 -1~0 历史标记）
  - 阶段 1 实施计划文档：10 个里程碑（M1-1~M1-10，对应 04 §三）分解为 T1-T10 任务 + 依赖图 + 4 个 Wave（Wave 1 串行 T1-T3 基础层 / Wave 2 并行 T4-T6 / Wave 3 并行 T7-T9 / Wave 4 串行 T10 门禁）+ 8 个待写 ADR（ADR-0017~0024，关联 05 §五 dissent）+ 05 §五 10 条 dissent 全映射到任务 + kill criteria 3/6/8 触发条件 + 性能优化备选 6 步
  - 现状盘点：阶段 -1/0 产出 16979 行可复用（combat/dsl/runtime/spec 四模块 + 680 tests），阶段 1 是"从 stub 到真实引擎"跃迁而非从零开始
  - 启动前置：ADR-0017/0018（Wave 1 前置）+ 用户确认启动编码

## 已知技术债（后置，不阻塞阶段 0）

- **CLI 命令解析缺陷**：`cli.py` 用 `line.strip().split()` 解析，NPC/物品名含空格时拆错（如"小 喇嘛"）。需改用引号感知的 tokenizer 或 LPC 风格的 `parse_command`（阶段 0 命令管线 8 段中间件时一并处理）
- **`drop` 命令未实现**：`commands.py` 有 take/give 无 drop。阶段 0 物品系统规格提取时补全
- **xlama2 交互闭环未完成**（S4e GAP）：ask_tea 的 set_flag 茶 + accept_object 酥油的 clear_flag + 物品生成需 ask->action 机制 / clear_flag action / 物品系统（阶段 0）
- **门状态机运行时未实装**（S3 GAP）：do_knock / call_out 定时关 / 跨房间 exits 同步（阶段 0）
- **LPC 规格提取跳过部分**：本次 9 层覆盖核心循环约 7000 行，跳过 condition 具体类型 / 第二梯队守护进程 / 后置系统 / kungfu+d/ 内容。补充计划见 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md)（3 类分阶段补充，"实现到时才补"原则，不提前批量提取）

## In Progress

**阶段 1 实施计划已产出**（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)），待用户确认启动编码。

**启动前置**（Wave 1 前置，确认后先写）：
- ADR-0017 ECS SparseSet vs Archetype + Effect 一等公民设计（关联 dissent 7 派生变更审计）
- ADR-0018 ConditionHandler.on_tick 组合返回值契约（关联 dissent 7）
- 用户确认启动阶段 1 编码

**剩余可选任务**（非阶段 1 前置，可穿插）：
- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）-- 为工时承诺提供数据支撑，可后置
- golden trace 定点辅助（driver PID 22753 运行中）-- dissent 4 验证（valid_leave 命中行为 + do_attack 七步时序基线），Wave 2/3 期间穿插
- [ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md) 实现（层1 谓词集扩充 8 类）-- T2/T4 期间穿插

## Blocked

**当前无阻塞项。**

**driver UE 问题已解除**（2026-07-11 用户重启电脑后验证）：

- 重启清掉 UE 状态旧进程（PID 6740），端口 8888 释放
- libevent-2.1.6 符号链接在（`/usr/local/opt/libevent/lib/libevent-2.1.6.dylib -> libevent-2.1.7.dylib`）
- driver 重启成功（PID 22753 监听 8888，日志 "Accepting connections on 0.0.0.0:8888." + "Initializations complete."）
- golden trace 定点辅助路径已打通，可在任务 9 执行期间并行推进
- ADR-0009 记录的风险仍有效：未来 kill -9 driver 可能再次触发 UE，建议用 SIGTERM 优雅退出或等待自行退出

**不阻塞主线**：golden trace 定位为辅助验证手段（ADR-0009），单元级行为规约（任务 3 已完成）是 greenfield 主门禁，不依赖运行旧系统

## Next Up

**阶段 0 已合并 master，阶段 1 实施计划已产出**（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)），待确认启动编码。

**阶段 0 -> 1 决策检查点**（04 §八）：
- [x] LPC 规格提取覆盖 go/move/combat 核心路径？（任务 1 ✅）
- [x] FluffOS 编译可行或降级为单元规约？（任务 2 ✅，现有二进制可运行）
- [x] 性能 micro-benchmark 达标？（任务 4 阶段 0 部分 ✅，1000+100 后置阶段 1）
- [x] 引擎工具链 PRD 评审通过？（任务 5 ✅）
- [x] 30 文件表达力校准层3 <15%？（任务 9 ✅，修正 KPI 6.4%）

**下一步主线**：启动阶段 1 编码（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)）。需用户确认。确认后先写 ADR-0017/0018（Wave 1 前置），再进 Wave 1 T1（ECS 骨架升级）。

**可穿插推进**（非阶段 1 前置）：
- golden trace 定点辅助（[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md)，driver PID 22753 运行中）：录制 valid_leave 命中行为 + do_attack 七步副作用时序基线（dissent 4 验证）
- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）
- [ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md) 实现：层1 谓词集扩充 8 类（阶段 1 层1 运行时落地时）

**任务 4 后置部分**（阶段 1）：1000+100 负载压测 + 1s tick 预算实测需阶段 1 ECS + WS 服务器框架（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md) 后置章节）

**规格补充建议**（任务 7 盘点产出，按 08 §七"实现到时才补"原则）：
- 层 H 第二梯队：CHANNEL_D 的 chblk 检查规格、fingerd.c 的 get_killer() 规格、rankd.c 的 PKS 称号逻辑
- 层 C：vote 命令规格
- 层 I：human.c 的属性计算公式规格（武林大会用）
- 层 F：补全阴间世界流程规格（黑白无常剧情/还阳路径/gate.c 物品销毁，当前标注"后置"）

S2-S4f 简化项（门状态机运行时、riposte 递归、hit_ob/hit_by mapping、action_* 外提、动态回复函数、kill_npc/reach_room 任务目标、物品/金钱奖励、ask->action/clear_flag/物品生成）按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md) / [ADR-0003](docs/adr/ADR-0003-combatkernel-theme-neutrality.md) / [ADR-0004](docs/adr/ADR-0004-agent-dsl-generation-s3.md) / [ADR-0005](docs/adr/ADR-0005-layer1-predicate-expansion.md) / [ADR-0006](docs/adr/ADR-0006-accept-object-inquiry-set-flag.md) / [ADR-0007](docs/adr/ADR-0007-minimal-quest-system.md) / [ADR-0008](docs/adr/ADR-0008-schema-validator-four-checks.md) 表在 S4+ 或阶段 0 补全。

## kill criteria 状态（开工必读）

**阶段 -1**（已完成，全通过）：
- DSL+Agent 创作闭环验证 ✅
- 非武侠微场景验证 CombatKernel 主题无关性 ✅

**阶段 0**（已完成，全通过）：
- 性能 micro-benchmark 达标 ✅（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md)，1000+100 后置阶段 1）
- 30 文件表达力校准层3 <15% ✅（[ADR-0015](docs/adr/ADR-0015-layer-calibration-methodology.md)，修正 KPI 6.4%）

**阶段 1**（待启动，关注）：
- 单进程核心循环集成测试无法支撑 1000+100 -> 冻结功能范围，纯做性能优化直至达标或触发目标降级（[04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md) 第 6 条）

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`cd engine && .venv/bin/python -m pytest`（venv 在 `engine/.venv`；系统 Python 受 PEP 668 限制需 venv）；lint：`cd engine && .venv/bin/ruff check src tests`。
