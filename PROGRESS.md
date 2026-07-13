# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。

**最后更新**：2026-07-13
**当前阶段**：M3 Wave 1 完成（M3-2 CPK 格式化 + StdLib CPK 骨架，1628 tests 全绿）。下一步 Wave 2 M3-1 门派完整核心循环
**当前状态**：阶段 1 全部完成并合并 master（merge `bffce2c3`，T1-T10，1035 tests，kill criteria 3 GO）。阶段 2 实施计划文档已产出（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md)）。当前在 master 分支（阶段 2 已合并 master，merge `fee5dd25`）。**阶段 2 全部完成**（Wave 1 2.1 Query + Wave 2 2.2/2.3/2.5/2.6 + Wave 3 2.4 Combat + Wave 4 2.7 门派切割）。**Wave 4 2.7 门派切割完成**（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md) 落地：RaceProfile + FamilyBonus 声明式载体（race 层剥离，setup_race 纯函数 + apply_family_bonuses 分发不认识门派名）+ ThemeConfig 房间路径外提（governance/death/cli 改读 world.theme_config，源码无武侠房间路径字面量）+ test_theme_neutrality 扩展收官硬门禁（扫描 governance/death/cli/race/family 无门派名+武侠路径，dbase key 兼容层保真让步豁免）+ 非武侠微场景验证（海盗帮派 FamilyBonus + 武当派标准加成）+ Vitals 补 eff_jingli（2.2 遗漏）+ spec 层 layer_h_race.py（setup_race + apply_family_bonuses 最小契约），1598 tests 全绿，关联 dissent 1/5/10）。**阶段 2 -> M3 决策检查点全部通过**（门派内容包边界干净切割 ✅）。下一步 M3 单题材武侠完整可玩 demo。

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

- [x] **阶段 1 Wave 1 T1：ECS 骨架升级完成**（[ADR-0017](docs/adr/ADR-0017-ecs-sparse-set-effect-component.md) + [ADR-0018](docs/adr/ADR-0018-conditionhandler-on-tick-contract.md)）：
  - ADR-0017 SparseSet 选型 + Effect 一等公民：SparseSet（非 Archetype，1000 实体规模足够，dict -> SparseSet 平滑升级 API 兼容）；Effect 一等公民（即时 Effect combat-only + 持续 Effect EffectComp，可序列化/可中断/可崩溃恢复 04 §三硬约束）
  - ADR-0018 ConditionHandler.on_tick 契约：ConditionTickResult（effects/messages/condition_deltas/completed/flags/ledger 交织）；on_tick 纯函数不 mutate；非均匀 tick（对齐 LPC 5+random(10)）；dissent 7 派生变更审计轨迹
  - T1 实现：SparseSet 升级 [ecs.py](engine/src/xkx/runtime/ecs.py)（swap-remove + 交集查询）+ Progression 组件（combat_exp/potential/max_potential 从 Vitals 迁移，[components.py](engine/src/xkx/runtime/components.py) + [world.py](engine/src/xkx/runtime/world.py) + [commands.py](engine/src/xkx/runtime/commands.py) + 4 tests 调整）+ EffectComp 组件（持续 Effect，独立实体 attach 支持多 condition）+ [systems.py](engine/src/xkx/runtime/systems.py) System 基类 + [conditions.py](engine/src/xkx/runtime/conditions.py) ConditionHandler/ConditionSystem
  - 测试：[test_ecs.py](engine/tests/test_ecs.py) 7 tests（SparseSet swap-remove/覆盖/交集 + hypothesis 属性测试）+ [test_conditions.py](engine/tests/test_conditions.py) 14 tests（on_tick 纯函数/衰减/completed/flags/多 condition/非均匀 tick）
  - **701 tests 全绿（+21），ruff 全过**

- [x] **阶段 1 Wave 1 T2：SchemaRegistry 类型化组件完成**（[ADR-0019](docs/adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)）：
  - ADR-0019 SchemaRegistry 与 DSL SchemaValidator 边界：runtime 组件层（启动期/运行期，类型注册+字段名存在性）vs DSL IR 层（创作期/加载期，结构+语义+引用）；dissent 3 护栏--SchemaRegistry 只做拼写检查不做语义校验（名字存在性 ≠ 值合法性），语义留给 DSL SchemaValidator + System 不变量
  - T2 实现：[schema.py](engine/src/xkx/runtime/schema.py) SchemaRegistry（register/resolve/resolve_name/has_field/field_names，从 dataclasses.fields 自动提取字段集，with_builtins 注册 13 内置组件）+ [ecs.py](engine/src/xkx/runtime/ecs.py) World 可选注入 schema（schema=None 向后兼容测试；有 schema 时 get/add/has/remove/entities_with 调 resolve，未注册类型 raise SchemaError 非静默 None）+ [world.py](engine/src/xkx/runtime/world.py) build_world 用 World(SchemaRegistry.with_builtins()) 生产路径强制校验
  - 测试：[test_schema.py](engine/tests/test_schema.py) 17 tests（注册/解析/字段查询/重复注册幂等/类型名冲突/非 dataclass 拒绝/未注册 raise/with_builtins 全覆盖/World 校验集成/build_world 带 schema/hypothesis 字段集一致性）
  - **718 tests 全绿（+17），ruff 全过**

- [x] **阶段 1 Wave 1 T3：字段->组件映射表完成**（[13-dbase-key-map.md](docs/xkx-arch/13-dbase-key-map.md) / ADR-0019 覆盖）：
  - [dbase_map.py](engine/src/xkx/runtime/dbase_map.py)：DBASE_KEY_MAP（37 已映射简单 key -> 13 组件字段，覆盖 Identity/Attributes/Vitals/Progression/Skills/NpcBehavior/RoomComp）+ PATH_PREFIX_MAP（skill/xxx -> Skills.levels，marks/xxx -> Marks.flags，LPC dbase 路径访问语义）+ POSTPONED_KEYS（55 后置 key，分 5 类：战斗行为/角色长期/PK法院/频道消息/登录重连/对象房间扩展）+ validate_dbase_map（T2 has_field 启动期校验映射目标合法）+ resolve_dbase_key（简单 key + 路径前缀解析，未映射返回 None）
  - [world.py](engine/src/xkx/runtime/world.py)：build_world 调 validate_dbase_map，映射目标非法 raise SchemaError（T2-T3 衔接）
  - [13-dbase-key-map.md](docs/xkx-arch/13-dbase-key-map.md)：完整 key 枚举文档（spec 82 key 全归类：37 已映射 + 2 路径前缀 + 55 后置 + 动态拼接 eff_/max_ type 维度）
  - 测试：[test_dbase_map.py](engine/tests/test_dbase_map.py) 9 tests（validate 正常+空 schema 全报/resolve 简单+路径+未映射/POSTPONED 不污染已映射/hypothesis 映射目标合法）
  - **727 tests 全绿（+9），ruff 全过**
  - **Wave 1 全部完成（T1+T2+T3）**

- [x] **阶段 1 Wave 2 前置 ADR 全部产出**（[ADR-0020](docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) / [ADR-0021](docs/adr/ADR-0021-previous-object-explicit-mapping.md) / [ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) / [ADR-0023](docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md)）：
  - ADR-0020 命令 8 段中间件管线（对照 LPC command_hook 四分支 + process_input）+ ActionContext 三元组（actor/viewer/target，PronounContext viewer 不变量）+ CapabilityToken（HS256 + 内存吊销）+ force_me=PrivilegedAction（ROOT 门控 + 强制审计 + 调用点白名单）；关联 dissent 6
  - ADR-0021 previous_object 155 处显式化映射表（this_player()->actor / previous_object()->source）+ A/B/C 三类处置 + 调用点审计策略（source 显式传参 + 白名单 + ROOT 签发审计 + 两类审计分离）；关联 dissent 6
  - ADR-0022 持久化边界抽象（persist=崩溃恢复级耐久，非 save=权威写，为迁 PG 留策略切换）+ 原子写三步（write-temp + fsync + os.replace）+ 事件循环外 offload + dirty-flag 分摊 + 丢失语义台账 5 项（kill criteria 8 止损线）+ Effect 崩溃恢复 + 冷重启协议；关联 dissent 8
  - ADR-0023 combat-only 确定性边界（范围内/范围外 + 边界红线）+ CombatSystem（tick 驱动 + 快照边界 + input log + replay 入口 + 不套 Command）+ 简化台账 6 项补全（hit_ob/hit_by mapping / riposte 递归 / 武器类型 / skill_power / combat_exp 防御折减 / 技能 action）+ test_theme_neutrality 硬门禁兜底；关联 dissent 1
  - agent teams 3 路并行写 ADR（T4 一个 agent 写 0020+0021 / T5 一个写 0022 / T6 一个写 0023），审查收敛后修复 1 处交叉引用链接
  - **727 tests 全绿（无回归），ruff 全过**

- [x] **阶段 1 Wave 2 T4 命令 8 段管线 + ActionContext + CapabilityToken 完成**（[ADR-0020](docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) + [ADR-0021](docs/adr/ADR-0021-previous-object-explicit-mapping.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T4）：
  - 8 段中间件管线（[middleware/](engine/src/xkx/runtime/middleware/) 8 文件：s0 刷屏检测 / s1 别名 / s2 权限 / s3 命令查找 / s4 方向快捷 / s5 参数解析 / s6 previous_object 注入 / s7 执行+审计），对照 LPC command_hook 四分支 + process_input
  - [ActionContext](engine/src/xkx/runtime/action_context.py) frozen dataclass 三元组（actor/source/viewer/target + capability_token + seq + result/effects），PronounContext viewer 不变量
  - [CapabilityToken](engine/src/xkx/runtime/capability.py) HS256 签名 + 内存吊销集合 + 能力集映射 LPC 权限模型（exclude 优先 authorized）+ PermissionService 签发/验签/吊销
  - [PrivilegedAction](engine/src/xkx/runtime/privileged.py) force_me=PrivilegedAction（ROOT 门控 + 强制审计 + 调用点白名单 4 处 + 走完整 8 段管线 + NPC AI 禁用）
  - [previous_object_map.py](engine/src/xkx/runtime/previous_object_map.py) PREVIOUS_OBJECT_MAP（A/B/C 三类 11 条典型调用点）+ 启动期 MappingError 校验；[pronoun.py](engine/src/xkx/runtime/pronoun.py) PronounService（viewer/target 显式传参）；[system_context.py](engine/src/xkx/runtime/system_context.py) SystemContext（System.update 路径轻量）
  - [commands.py](engine/src/xkx/runtime/commands.py) 重构接入管线（COMMAND_REGISTRY + run_pipeline + dispatch），10 命令行为等价
  - 测试：[test_command_pipeline.py](engine/tests/test_command_pipeline.py) 26 + [test_capability_token.py](engine/tests/test_capability_token.py) 20 + [test_privileged_action.py](engine/tests/test_privileged_action.py) 13 + [test_previous_object_map.py](engine/tests/test_previous_object_map.py) 21
  - **80 新测试全绿，61 e2e 不回归，ruff 全过**；关联 dissent 6

- [x] **阶段 1 Wave 2 T5 内存权威 + JSON 存档完成**（[ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T5）：
  - [storage.py](engine/src/xkx/runtime/storage.py) StorageBackend 抽象基类（persist=崩溃恢复级耐久，非 save=权威写）+ JsonFileBackend（原子写 write-temp+fsync+os.replace + offload asyncio.to_thread + per-entity dirty-flag）+ StorageSystem（tick 驱动周期 persist + mark_dirty + 全量 checkpoint 周期重置 + persist_now + restore_world 冷重启协议）
  - [serialization.py](engine/src/xkx/runtime/serialization.py) 组件 dataclass <-> JSON 序列化（dataclasses.fields 提取 + SchemaRegistry 字段名衔接 + set 字段 sorted list 往返 + 多余/缺失字段容忍）
  - [world.py](engine/src/xkx/runtime/world.py) 最小接入 StorageSystem（build_world 加可选 storage_backend 参数，world.storage_system 动态属性，零破坏现有调用）
  - Effect 崩溃恢复：duration 不衰减（时间冻结）+ next_tick 对齐 current_tick+tick_interval（不补执行）+ 悬空 target_id 跳过 + 悬空 source_id 保留
  - 丢失语义台账 5 项（ADR §5 已记录，PG 后置 kill criteria 8）
  - 测试：[test_storage.py](engine/tests/test_storage.py) 25 tests（原子写崩溃 + offload 不阻塞 + dirty-flag + 冷重启 + Effect 崩溃恢复 + hypothesis 序列化往返 6 property）
  - **25 新测试全绿，ruff 全过**；关联 dissent 8

- [x] **阶段 1 Wave 2 T6 combat 确定性扩展 + 简化台账 6 项补全完成**（[ADR-0023](docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T6）：
  - 6 项简化台账补全（[resolve_attack.py](engine/src/xkx/combat/resolve_attack.py)）：
    1. hit_ob/hit_by mapping 分支：[HitCallbackResult](engine/src/xkx/combat/context.py) 声明式载体（message/damage_delta/override，主题无关 + 可序列化），内核只做返回类型分发，按规格 order=23/25/26/32/33 交织入 ledger
    2. riposte 递归：TYPE_REGULAR + damage<1 + victim guarding 时递归调 resolve_attack，子回合经 [embed_subresult](engine/src/xkx/combat/result.py) 嵌入父回合 ledger（LEDGER_SUBRESULT，非独立账本），_RIPOSTE_MAX_DEPTH=4 防死循环
    3. 武器类型：不在内核枚举（test_theme_neutrality 源码无 sword/blade 硬门禁持续通过），attack_skill/weapon_label 由题材数据声明
    4. skill_power 完整公式：level³/3 + jingli_bonus(上限 150) + str/dex 加成 + is_fighting DEFENSE 折减 + level<1 低技能经验补偿（LPC _skill_power invariants）
    5. combat_exp 防御折减：defense_factor 折半自然终止（while 循环，每次 rng.rand），替代 S1 的固定 5 次上限
    6. 技能 action：[SkillData](engine/src/xkx/combat/context.py) 载体（action/dodge/parry/damage/force/damage_type/post_action），快照从 SkillData 取值，post_action 声明式副作用入 ledger（order=47）
  - CombatSystem（[system.py](engine/src/xkx/combat/system.py) 新建）：tick 驱动 + 快照构建 + input log 记录 + apply_effects + replay 入口 + flatten_messages/effects（展开 riposte 子回合）+ 不套 Command。独立实现（不继承 runtime.System，避免 combat->runtime 依赖），不接入 world.py System 注册（后续整合）
  - replay 纯函数（[replay.py](engine/src/xkx/combat/replay.py) 新建）：replay(snapshot, seed, input_log) -> list[CombatRoundResult]，同 snapshot+seed+input_log -> 同输出（combat-only 确定性，不依赖运行时 ECS）
  - impl_map 升级（[impl_map.py](engine/src/xkx/spec/impl_map.py)）：three_layer_resource_invariant / interleaving_order 状态 simplified -> implemented（14 implemented + 0 simplified）
  - DeterministicRNG 加 derive_seed（riposte 子回合 seed 派生，确定性）
  - 测试：[test_simplification_ledger.py](engine/tests/test_simplification_ledger.py) 20 tests（6 项补全回归 + 主题无关性断言）+ [test_combat_system.py](engine/tests/test_combat_system.py) 13 tests（tick 驱动 + 确定性重放 + apply_effects 三层不变量 + flatten 子回合展开）
  - test_conformance.py 最小适配 2 处：test_ap_dp_pp_lower_bound（完整公式 level<1 边界行为，skill_power>=0 + resolve_attack max(1,ap) 修正）+ test_implemented_count（14/0）
  - **840 tests 全绿（+33），ruff 全过**；test_theme_neutrality 5 断言全绿（硬门禁不回归）；ConformanceChecker 8 项全通过（riposte 场景验证）

- [x] **阶段 1 Wave 3 T7 单进程 WS 服务器 + 认证 + 重连完成**（[ADR-0024](docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T7）：
  - [account.py](engine/src/xkx/runtime/account.py) AccountService（argon2id 密码哈希替换 LPC crypt + check_legal_id/name + random_gift 天赋生成不变量 str+int+con+dex+end=100 + JSON 存储账号）
  - [login.py](engine/src/xkx/runtime/login.py) LoginMachine 状态机（WS 登录子协议驱动；老玩家 GET_ID->GET_PASSWD->DONE + 新玩家注册流程；阶段 1 简化跳过 CONFIRM_BIG5/wiz_lock/GET_GIFT/GET_EMAIL）
  - [connection.py](engine/src/xkx/runtime/connection.py) ConnectionSystem（ADR-0014 第 6 个 System；tick 驱动会话超时 LOGIN/NET_DEAD/IDLE + ring buffer 重连 ring/snapshot 降级 + 进程内内存非持久化 dissent 8 取舍）
  - [ws_server.py](engine/src/xkx/runtime/ws_server.py) WSServer（JSON 帧编解码 7 类帧 + 登录子协议 + command->dispatch 8 段管线 + resume 重连 + 事件推送；session token 复用 T4 CapabilityToken HS256；核心逻辑不依赖网络库可单元测试 + serve 方法用 websockets 库）
  - 依赖：argon2-cffi + websockets 加 pyproject.toml；测试 28+14+23+16
  - **81 新测试全绿，ruff 全过**；关联 dissent 8

- [x] **阶段 1 Wave 3 T8 引擎工具链三件完成**（[ADR-0013](docs/adr/ADR-0013-engine-toolchain-prd.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T8）：
  - [inspector.py](engine/src/xkx/runtime/inspector.py) EntityInspector（只读快照 + LPC F_DBASE 语义映射表 43 key 含 skill//marks/ 路径访问 + 程序化 API 6 方法 + CLI inspect --map；只读不修改 world）
  - [profiler.py](engine/src/xkx/runtime/profiler.py) TickProfiler（per-System compute 统计 mean/p99/max/total/%tick + enabled=False 零开销 contextmanager + ring buffer 滑动窗口 + CLI profile tick + --json）
  - [tools/replay.py](engine/src/xkx/tools/replay.py) Combat Replay Viewer（CombatLog JSON 归档 M1 前身 + 逐回合回放 + 交织时序展示 + ConformanceChecker 集成 + 确定性 diff 定位首次分歧 + CLI replay --step/--round/--diff/--conformance/--json；非侵入消费 ledger 仅依赖 xkx.combat）
  - 测试 [test_inspector.py](engine/tests/test_inspector.py) + [test_profiler.py](engine/tests/test_profiler.py) + [test_replay_viewer.py](engine/tests/test_replay_viewer.py)
  - **57 新测试全绿，ruff 全过**；关联 dissent 3/4/7

- [x] **阶段 1 Wave 3 T9 combat-sim 行为等价验证完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T9）：
  - [combat_sim.py](engine/src/xkx/combat/combat_sim.py) run_combat_sim（replay + ConformanceChecker 8 项检查 + CombatSimReport/RoundReport + JSON 序列化 + CLI python -m xkx.combat.combat_sim）
  - [replay.py](engine/src/xkx/combat/replay.py) 扩展 replay_with_context（返回 ctx+result 对供符合性检查用 ctx；replay 接口不变向后兼容）
  - 测试 [test_combat_sim.py](engine/tests/test_combat_sim.py) 端到端无 violation + 确定性 + JSON 往返 + CLI
  - **16 新测试全绿，ruff 全过**；greenfield 主门禁（不依赖运行 LPC）；impl_map 14 implemented + 0 simplified 自动区分

- [x] **阶段 1 Wave 4 T10 1000+100 集成测试完成（kill criteria 3 完整判定 GO）**（[12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T10 / [14 压测报告](docs/xkx-arch/14-T10-压测报告.md)）：
  - 整合遗留收纳：[engine.py](engine/src/xkx/runtime/engine.py) Engine 统一 tick 循环（System 注册 + TickProfiler 集成）+ CombatBridge 适配器（CombatSystem 接入，按 enemy_ids 构建 input_log O(活跃对) 非 O(n²)）+ CombatState 扩展 guarding/is_fighting/fight_dodge + to_snapshot 传递 + mark_dirty 整合（CombatBridge/ConditionSystem mutation 后标记）
  - [load_test.py](engine/tools/load_test.py) 压测脚本：1300 实体（50 房间 + 200 NPC + 1000 玩家 + 50 Effect）+ 1000 会话 + 50 战斗对 + 300 tick；async 模式 StorageSystem offload 生效
  - **tick p99 12.6ms < 100ms 预算 -> GO**；CombatSystem 5.3ms mean（占 92%），ConditionSystem 238μs，ConnectionSystem 236μs（1000 会话线性扩展），StorageSystem 6μs（persist tick 深拷贝 1.8ms）
  - 存档 offload 验证：全量 persist p99 389.8ms 在后台（asyncio.to_thread），tick p99 不含 persist（[ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) §3 生效）
  - 测试 [test_engine.py](engine/tests/test_engine.py) 12（Engine tick 循环 + CombatBridge + CombatState 扩展 + 完整整合）+ [test_load_test.py](engine/tests/test_load_test.py) 4（CI 回归门禁 tick p99 < 100ms + JSON 往返 + scaled 降级）
  - **kill criteria 3 完整判定通过**，不触发 kill criteria 6/降级；阶段 1 -> 2 决策检查点全部通过
  - **1035 tests 全绿（+16），ruff 全过**

- [x] **阶段 2 Wave 1 2.1 Query/索引层完成**（[ADR-0025](docs/adr/ADR-0025-query-index-layer.md) / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1）：
  - [ADR-0025](docs/adr/ADR-0025-query-index-layer.md) Query/索引层设计（Wave 1 前置）：query() 语义对齐 LPC F_DBASE 8 函数 + 未映射 key 三类区分（mapped/postponed/unknown，dissent 2 拼写错误不静默）+ 索引层线性扫描 + 后置 key 激活策略 + 映射表收敛（inspector.LPC_KEY_MAP 从 DBASE_KEY_MAP 派生）
  - [query.py](engine/src/xkx/runtime/query.py) 新建：8 函数（query/query_temp/set/set_temp/add/add_temp/delete/delete_temp，对照层 B 规格）+ 索引层（entities_with_family/entities_by_prototype/find_in_room/find_item）+ Identity/Position/Inventory 语义函数（id_match/short/move_to/environment/present_item/all_inventory）
  - [dbase_map.py](engine/src/xkx/runtime/dbase_map.py) 扩展：DbaseKeyError（SchemaError 子类）+ is_postponed + classify_key（三类区分）+ KeyClass Literal
  - [inspector.py](engine/src/xkx/runtime/inspector.py) 重构：LPC_KEY_MAP 从 DBASE_KEY_MAP + PATH_PREFIX_MAP + POSTPONED_KEYS 派生（删除 _LPC_ENTRIES 硬编码，单一信源收敛）；lpc_key_mapping 复用 classify_key + resolve_dbase_key
  - greenfield 简化台账 12 项（ADR-0025 §简化台账）：raw/evaluate/default_ob/完整 treemap 砍掉（LPC 特有）；short 状态修饰后置 2.5；move 负重级联后置 2.3；greenfield 不区分 dbase vs tmp_dbase（query/query_temp 行为一致）
  - [test_query.py](engine/tests/test_query.py) 66 tests：8 函数 + 三类处理 + 索引层 + 语义函数 + hypothesis 属性测试（路径前缀往返 + key 三类分类 + add 增量 + marks/ 往返）+ marks/ 自动创建
  - **实现 bug 修复**：query.py `def set` 覆盖内置 `set` 类型 -> `builtins.set`/`builtins.frozenset`（3 处 isinstance + 1 处 all_inventory 副本构造）
  - **1101 tests 全绿（+66），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - agent teams 并行：2 agent（inspector 重构 + test_query 编写），inspector 重构无回归，test_query 发现 set 覆盖 bug 后修复
  - 关联 dissent 2（query 语义不偏离 LPC F_DBASE）+ dissent 8（不新增组件，无序列化需求）

- [x] **阶段 2 Wave 2 2.2 Vitals/Heal/Condition 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.2 / [ADR-0018](docs/adr/ADR-0018-conditionhandler-on-tick-contract.md) 契约演进）：
  - Vitals 扩展 eff_jing/water/food 字段（heal_up 恢复上限 + 饥饿/脱水门控，对照 feature/damage.c:270-331）+ dbase_map 激活（POSTPONED 移除 eff_jing/no_death，加 water/food）
  - [heal.py](engine/src/xkx/runtime/heal.py) HealSystem + heal_up 完整语义（jing/qi/eff_jing/eff_qi/jingli/neili 恢复 + 战斗 1/3 速率 + water/food 门控 + 三层不变量 0<=qi<=eff_qi<=max_qi + eff_jing 达上限后才涨 + 完全确定性无 random）
  - [death.py](engine/src/xkx/runtime/death.py) 死亡轮回 9 函数（die/unconcious/revive/reincarnate/death_penalty/killer_reward/make_corpse/announce/check_death，对照 layer_f 规格 + LPC 原文精确公式）：
    - check_death 双层触发（eff_qi<0 直接 die / qi<0 先 unconcious 昏迷中再触发 die）
    - die 主流程（no_death 房转 unconcious / 玩家 ghost=1 move DEATH_ROOM / NPC destruct）
    - death_penalty 三段扣减（combat_exp>5000 扣 amount+potential 半 / 20<exp<=5000 扣 20 / <=20 不扣，确定性）
    - killer_reward（killer condition 100 tick 城区 + pker +120 双玩家，PKS/MKS/shen 后置 2.5）
    - make_corpse（ghost 物品掉环境 / 正常生成尸体实体 + 物品转移，装备重穿后置 2.3）
  - [conditions.py](engine/src/xkx/runtime/conditions.py) 扩展：apply_condition/query_condition/clear_condition/clear_one_condition 运行时函数（对齐 LPC F_CONDITION，直接覆盖语义，叠加由调用方 query+delta）+ condition handler 注册机制 + 7 个具体类型（poisoned 壳/snake_poison DoT/drunk 分档 debuff/blind 静默/killer 计时器/pker 叠加/revive 苏醒）
    - **ADR-0018 契约演进**：condition_deltas/completed 改用 EffectComp 实体 eid（int）作 key（支持多 target 同名 condition 独立衰减，原 effect_id 假设全局唯一被 apply_condition 打破）
  - combat/result.py 加 5 个 Effect kind（KIND_HEAL/KIND_HEAL_JING/KIND_DAMAGE_JING/KIND_WOUND_JING/KIND_CLEAR_MARK，condition 驱动的恢复/扣减/标记清除）+ world.apply_effects 扩展
  - **2.2 范围控制**（收敛）：阴间剧情后置 2.6（die 玩家 ghost=1 move DEATH_ROOM 为止）/ break_marriage/log_file/谣言后置 M3 / skill_death_penalty 简化 stub（所有技能 -1，真实 learned 公式后置 2.3）/ PKS/MKS/shen 后置 2.5 TitleComp / winner_reward stub / make_corpse 装备重穿后置 2.3
  - **确定性**：death_penalty/killer_reward 无 random（对齐 LPC）；unconcious 的 revive 延时 random(100-con)+30 用系统 RNG（非 combat 确定性范围）
  - 测试：[test_heal.py](engine/tests/test_heal.py) 16 + [test_condition_types.py](engine/tests/test_condition_types.py) 21 + [test_death.py](engine/tests/test_death.py) 21（含 hypothesis 三层不变量 + 多 target 同名 condition 独立衰减 + death_penalty 确定性）
  - **1159 tests 全绿（+58），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 8（新组件可序列化，Vitals 扩展字段全基本类型）+ dissent 7（condition handler 交织账本，ConditionTickResult ledger）+ ADR-0018 契约演进（effect_eid key）

- [x] **阶段 2 Wave 2 2.3 Attribute/Skill/Equipment 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.3 / [ADR-0026](docs/adr/ADR-0026-modifier-stack-and-skill-layers.md) + 实现期细化 6 项）：
  - [equipment.py](engine/src/xkx/runtime/equipment.py) 新建：wield/wear/unequip（对照 [equip.c](feature/equip.c)，prop 注入/反向扣减 + 槽位 flag TWO_HANDED/SECONDARY + reset_action 更新 CombatState）+ is_equipped/total_weight/add_encumbrance
  - Equipment 组件（weapon/secondary_weapon/armors + per-slot prop 副本 weapon_props/secondary_weapon_props/armor_props + encumbrance/max_encumbrance，可序列化）
  - Skills 扩展 apply_speed/skill_map/skill_prepare/learned（learned 衔接 skill_death_penalty 真实公式）
  - [query.py](engine/src/xkx/runtime/query.py) query_skill 三层叠加（apply/{skill} + levels/2 + skill_map，对照 [skill.c:94-109](feature/skill.c)）+ effective_apply/effective_skill_level
  - dbase_map 激活 apply_speed/weight/encumbrance + apply/ 前缀分发（APPLY_SUBPATH_MAP）+ equipped 语义 key（SEMANTIC_KEY_MAP）+ POSTPONED 移除 equipped/apply
  - ModifierStack 三类叠加（永久基础值 levels + 临时修正 apply_* + 装备加成注入 apply_* 标量，对照 LPC query 链）
  - [death.py](engine/src/xkx/runtime/death.py) 衔接 2.2 stub：make_corpse 装备重穿（unequip 所有 + 装备物品转移尸体）+ skill_death_penalty 真实 learned 公式（[skill.c:121-147](feature/skill.c)，修正 LPC learned 覆盖 bug）
  - CombatantSnapshot 加 apply_speed（快照边界，resolve_attack 不变，ADR-0023 第 4 项定稿）
  - **ADR-0026 实现期细化 6 项**：Skills 加 learned / Equipment per-slot prop 副本 / equipped 语义 key（非 DBASE_KEY_MAP）/ apply 未知子路径读返回 0 / skill_death_penalty 修正 LPC 覆盖 bug / wield 不自动算重量
  - 测试 [test_modifier_stack.py](engine/tests/test_modifier_stack.py) 36 tests（Equipment + ModifierStack + query_skill + apply 前缀 + equipped 语义 + death 衔接 + hypothesis 三类叠加交换律/unequip 回归 condition-only + 主题无关性）
  - **1196 tests 全绿（+37），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 3（三类叠加语义明确 + apply_* 不落入层1 DSL）+ 专家 3 承重（技能三层 levels+skill_map）+ dissent 8（Equipment 可序列化）+ dissent 7（per-slot prop 副本来源可追溯）

- [x] **阶段 2 Wave 2 2.5 TitleSystem 称谓完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5 / [ADR-0028](docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md)）：
  - [title.py](engine/src/xkx/runtime/title.py) 新建：RANK_D 7 函数无状态纯函数（query_rank/respect/rude/self/self_rude/query_close/query_self_close，对照 [rankd.c](adm/daemons/rankd.c) 行 8-651 精确对齐）+ 5 张可注入 class 表（CLASS_RANK/RESPECT/RUDE/SELF/SELF_RUDE_TABLE）+ WIZHOOD_TITLES + set/reset_class_tables + query_wizhood 钩子
  - 求值顺序不变量：is_ghost 最先(行19) -> wizhood 优先(行60-78) -> PKS>100 且 PKS>MKS(行80) -> class 注入表(行85-318) -> shen 阈值分级(行147-316，正降序/负升序/default 平民) -> rank_info 四键覆盖优先(行327/411/468/520)
  - **主题中立**（ADR-0028 开放问题 2 裁决）：核心引擎不硬编码武侠门派职业字面量（bonze/taoist 等），class 分支表数据从题材包注入，test_theme_neutrality 硬门禁 grep 无武侠字面量
  - [pronoun.py](engine/src/xkx/runtime/pronoun.py) 扩展：PronounContext frozen dataclass slots 10 字段（name_me/you + pronoun_me/you + close/close_rev + respect/respect_rev + self/self_rude）+ PronounService 7 函数委托 + build_context（$C/$c 角色互换 viewer 翻转：close=query_close(speaker,target)/close_rev=query_close(target,speaker)）+ render（10 占位符 $N/$n/$P/$p/$C/$c/$R/$r/$S/$s 替换）+ build_context_for_system（System tick viewer=speaker 回退，决策 4）+ visible 补 is_ghost 判定 + 可见性门控（不可见时 $n/$p/$C/$c/$R/$r 退化避免泄露隐身目标）
  - TitleComp 第 14 组件（13 字段：title/nickname/shen/rank_info 四键/pks/mks/char_class/dali_rank/family_rank/is_ghost，可序列化 ADR-0022）+ dbase_map 激活 7 key（title/nickname/shen/PKS/MKS/class/rank）+ 2 路径前缀分发（rank_info->四字段，dali->dali_rank）
  - [query.py](engine/src/xkx/runtime/query.py) short 状态修饰：short(world, eid, *, raw=False)，严格按 [name.c](feature/name.c) 行 99-147 顺序（打坐/吐纳/静坐提前 return -> title/nickname 前缀 -> 鬼气前缀 -> 断线/昏迷尾部），raw=True 纯函数
  - [spec/layer_h_daemons.py](engine/src/xkx/spec/layer_h_daemons.py) 补 RANK_D 7 函数 FunctionSpec（行号精确 + 不变量完整 + this_player 依赖标注 + cross_layer_refs 19->24），LAYER_SPEC.function_specs 26->33
  - [world.py](engine/src/xkx/runtime/world.py) spawn 衔接：_spawn_npc/spawn_player 加 TitleComp() 默认实例
  - **agent teams 3 路并行**：批次 0 单 agent 根依赖（TitleComp+dbase_map+schema）-> 批次 1 三路并行（A: title.py+pronoun.py+spawn，B: spec FunctionSpec，C: query.py short，改不同文件无冲突）-> 批次 2 单 agent test_title.py 107 tests
  - **穿插 ADR-0016** 层1 谓词扩充 8 类（独立 dsl 层，后台并行，不碰 runtime）
  - 测试 [test_title.py](engine/tests/test_title.py) 107 tests：7 函数行为等价（gender/class/shen/PKS/age/wizhood/ghost 全分支）+ PronounContext 10 变量（$C/$c 翻转 + 可见性门控 + System 回退）+ TitleComp 序列化往返 + short 集成 + PKS 称号 + 5 hypothesis 属性测试（rank_info 覆盖 + query_close 辈分 + is_ghost 短路）
  - **1339 tests 全绿（+143：107 test_title + 12 test_query short + 24 其他适配），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 6（PronounContext viewer 显式传参 + $C/$c 翻转实证专家 3 承重论断 2）+ dissent 8（TitleComp 可序列化）+ dissent 3（class 分支表数据非层1 谓词，主题中立）

- [x] **穿插 ADR-0016 层1 谓词扩充第二批完成**（[ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md) 8 类缺口，2.5 推进期间后台并行）：
  - [layer1.py](engine/src/xkx/dsl/layer1.py) 扩展 8 类谓词（attr_eq / is_wizard / has_item 扩展 item_category+item_name / has_flag 扩展 source=temp / derived_state / status_eq+same_object+mud_age_lt / has_inquiry+attr_in / command 事件钩子）
  - [spec/layer_c_command.py](engine/src/xkx/spec/layer_c_command.py) 命令 deny 规格补充（kill.c 7 条 + ask.c 分支）
  - 测试 [test_layer1_predicates_batch2.py](engine/tests/test_layer1_predicates_batch2.py) 24 tests passed
  - 护栏遵守：不引入 attr_gt/le/ge、不引入 has_item_count、derived_state 统一抽象、command 仅前置 deny
  - **全量 1339 tests 含 ADR-0016 24 tests，ruff 全过**；独立 dsl 层不碰 runtime/components（与 2.5/2.6 无文件冲突）
  - agent 最终 task-notification 未到，基于文件状态（layer1.py 25 处谓词 + 24 tests passed + 24 分钟无改）确认实质完成
  - 关联 dissent 3（层1 原语蠕变护栏，8 类均有 LPC 实证）

- [x] **阶段 2 Wave 2 2.6 WorldGovernanceSystem 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 / [ADR-0029](docs/adr/ADR-0029-world-governance-system.md)）：
  - [governance.py](engine/src/xkx/runtime/governance.py) 新建（~590 行）：GovernanceSystem 平台级 fail-closed System（独立遍历 effect_id="death_stage" EffectComp，非均匀 tick，不混入 ConditionSystem on_tick）+ 阴间死亡轮回（enter_underworld gate.c 物品销毁 + 启动 death_stage EffectComp 首延 30 秒 5 段每段 5 秒 / death_stage_handler 纯函数 / reincarnate_at 主路径丢弃物品 + 隐藏路径不丢弃）+ 法院通缉（apply_wanted/query_wanted + WANTED_REGIONS 四区域 city/xa/dl/bj 统一为 WantedCondition）+ 审判收监（proceed_sentencing PKS 分级 99/74/49=>500/300/200 + 累犯加重 city_jail>4=>600 + 穿琵琶骨 + 经验转移上限 3000 + bribe_clear_wanted 受贿销案）+ 监狱（release_from_jail + JAIL_ROOMS city_jail/dali_jail/bonze_jail）
  - **2.2 已完成使阴间闭环可做完整**（ADR-0029 决策 6 原计划只做骨架，但 2.2 death.py die/reincarnate/make_corpse 已就绪）：[death.py](engine/src/xkx/runtime/death.py) die() 衔接调 enter_underworld（加 tick 参数 + 延迟 import 规避循环依赖）+ check_death 透传 tick + [engine.py](engine/src/xkx/runtime/engine.py) GovernanceSystem 注册
  - [conditions.py](engine/src/xkx/runtime/conditions.py) 扩展：3 jail handler（city_jail/dali_jail/bonze_jail 到期衔接 release_from_jail，延迟 import governance）+ JAIL_CONDITIONS 集合
  - **累犯加重 bug 修复**：proceed_sentencing 原 clear_condition 在 query_condition("city_jail") 之前致累犯分支死代码（LPC kexiu.c:229 顺序相反），修复为 clear 前先查 existing_jail，累犯加重生效
  - 3 个开放问题按 ADR-0029 倾向裁决：death_stage 归 GovernanceSystem 独立遍历（开放问题 1）/ 通缉衰减归 ConditionSystem（开放问题 2）/ 阴间位置 room_id 常量（开放问题 3）
  - 测试 [test_governance.py](engine/tests/test_governance.py) 77 tests（1263 行）：A 平台 fail-closed 边界 + B 阴间完整闭环（die->gate.c 销毁->5 段->还阳主/隐藏）+ C gate.c 物品销毁副作用顺序 + D death_stage 崩溃恢复 + E 黑无常 is_ghost + F 法院通缉四区域 + G 审判收监 PKS 分级 + H 受贿销案 + I 监狱释放 + J 可序列化 + K hypothesis 3 属性（通缉衰减/量刑单调/PKS>99 恒 500）+ L test_theme_neutrality 硬门禁
  - **1421 tests 全绿（+82：test_governance 77 + test_death +5 衔接），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 5（themed 治理平台级 fail-closed Python 不入 UGC 规则层）+ dissent 10（5 灵魂系统只含 2 代表性元素，276 文件武林大会/vote/intermud 后置 M3）+ dissent 5 延伸（call_out 翻译为 EffectComp，GovernanceSystem 自有 handler）

- [x] **ADR-0027 产出（2.4 Combat 前置）**（[ADR-0027](docs/adr/ADR-0027-combat-callout-formation-golden-trace.md)）：
  - 覆盖 ADR-0023 未触及的 3 项承重决策：call_out -> Effect 翻译（dissent 1/7）+ s_combatd 阵法合击 CombatModifier（dissent 1）+ golden trace 录制/diff 协议（dissent 4）
  - **call_out 翻译**：2.4 只翻译 combat 核心路径（revive + start_ + remove_call_out 约 10 处），非全库 144 处穷尽；闭包型 call_out -> EffectComp（duration + 可中断 + 崩溃恢复 + 参数载荷），复用 ADR-0017 EffectComp + ADR-0022 崩溃恢复 + ADR-0018 ledger；revive 的 `random(100-con)+30` 用系统 RNG（非 combat 确定性范围）；start_ 延迟 0 秒倾向同步执行 + 防御检查
  - **阵法合击关键发现**：`s_combatd.c` 是 combatd 的"带 damage_msg 文本"副本（**非阵法**）；真正阵法入口是 [feature/attack.c:197](feature/attack.c#L197) `special_attack` 检查 `stand/anubis` 标记 -> `S_COMBAT_D->fight`，具体阵法在 [kungfu/skill/](kungfu/skill/) 题材脚本（pozhen/buzhen/heji）
  - **CombatModifier 主题无关接口**：阵法合击是题材内容（kungfu/skill/），走 SkillData/FormationData 声明不进内核；CombatModifier 声明式载体（modifier_type/participants/attack_modifier/defense_modifier/message/post_action）内核只做分发；2.4 只定接口 + special_attack 调用点，具体阵法后置 2.7/M3
  - **golden trace diff 三层协议**：L1 概率分布 diff（多次采样对照 layer_e 31 处 random 概率模型，卡方检验非逐字）+ L2 文本结构 diff（七步结构 + ANSI 剥离 + 伤害描述分类映射）+ L3 语义 diff（占位符对照 PronounContext）；定位辅助验证非主线门禁（主线是单元级行为规约 + ConformanceChecker + combat-sim）；diff 工具 [engine/tools/golden_trace/diff.py](engine/tools/golden_trace/diff.py) 新建
  - LPC 源码勘察：combatd.c call_out 1 处（行 866 start_ 延迟）+ damage.c call_out 3 处（revive 延迟 + remove_call_out）+ attack.c special_attack 阵法入口 + kungfu/skill/ 阵法脚本
  - 待用户评审，评审通过启动 2.4 编码

- [x] **阶段 2 Wave 3 2.4 Combat 编码完成**（[ADR-0027](docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) 落地 / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.4）：
  - **call_out -> Effect 翻译**（ADR-0027 §1）：revive + remove_call_out 2.2 已完成（EffectComp 化），2.4 补测试 + 文档化中断契约；start_* 同步执行 + 5 防御检查（[auto_fight.py](engine/src/xkx/runtime/auto_fight.py) 新建，§1.2 决策同步执行非 duration=0 EffectComp；具体 fight 逻辑 kill_ob/fight_ob 后置 M3 NPC AI）。实现期细化：start_* 放 runtime/auto_fight.py（非 conditions.py，因同步执行不用 EffectComp）
  - **CombatModifier 协同修正接口**（ADR-0027 §2）：[modifier.py](engine/src/xkx/combat/modifier.py) 新建 frozen dataclass 主题无关字段 + CombatantSnapshot 加 formation_modifier 字段（快照边界注入）+ [system.py](engine/src/xkx/combat/system.py) CombatSystem.tick special_attack 调用点（只读 formation_modifier，ap/dp 修正 + message + post_action 透传）。实现期细化：阵法标记检查移到快照构建边界（combat 包自包含不查 Marks，runtime 层 CombatBridge 后置整合）；具体阵法逻辑（pozhen/buzhen/heji）后置 2.7/M3
  - **golden trace diff 三层协议**（ADR-0027 §3）：[diff.py](engine/tools/golden_trace/diff.py) 新建 L1 概率分布 diff（边际概率链 + 卡方检验）+ L2 文本结构 diff（七步结构 + ANSI 剥离 + 伤害分类映射）+ L3 语义 diff（占位符 PronounContext 渲染）+ CLI + DiffReport；非侵入设计（只消费 ledger + baseline）
  - **关键发现**：LPC 概率模型 `parry_p=pp/(ap+pp)` 是理论公式，resolve_attack 顺序判定（dodge 成功则 return）需用边际概率链 `P(parry)=(1-dodge_p)*pp/(ap+pp)` 匹配实际行为，卡方 p=0.069>0.05 通过
  - **主题无关硬门禁**：test_theme_neutrality 扩展阵法/合击/anubis/sword/blade 字面量黑名单（扫描 modifier.py + system.py + auto_fight.py）；impl_map 加 COMBAT_EXTENSION_IMPL_MAP 3 条 implemented 标注（callout_revive/start_translation + formation_modifier_interface）
  - agent teams 2 批次 4 agent：批次 1 三路并行（A modifier.py + 13 tests / B auto_fight.py + 23 tests / C diff.py + 49 tests，改不同文件无冲突）+ 批次 2 串行（D system.py special_attack + 7 tests / E theme_neutrality 扩展 + impl_map 标注自做）
  - 测试：[test_combat_modifier.py](engine/tests/test_combat_modifier.py) 20（13 接口 + 7 special_attack）+ [test_callout_translation.py](engine/tests/test_callout_translation.py) 23 + [test_golden_trace_diff.py](engine/tests/test_golden_trace_diff.py) 49 = 92 新测试
  - **1514 tests 全绿（+93），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过；golden trace diff CLI 端到端三层全 PASS
  - 关联 dissent 1（CombatKernel 主题无关，阵法合击题材内容不进内核）+ dissent 4（golden trace diff 定位辅助验证非主线门禁）+ dissent 7（call_out 翻译 EffectComp 审计轨迹）

- [x] **阶段 2 Wave 4 2.7 门派切割完成**（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md) 落地 / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.7）：
  - **race 层剥离**（决策 1）：[race.py](engine/src/xkx/runtime/race.py) RaceProfile 数据声明 + setup_race 纯函数（年龄分层 max_jing/max_qi/max_jingli 公式 + 70 岁衰减 + max_potential/max_encumbrance/weight，公式参数从 profile 读取不硬编码门派名）+ [family.py](engine/src/xkx/runtime/family.py) FamilyBonus 声明式载体 + apply_family_bonuses 分发函数（family_name 字符串匹配 + 条件检查 + 公式计算，不认识具体门派名）
  - **ThemeConfig 房间路径外提**（决策 2）：[theme.py](engine/src/xkx/runtime/theme.py) ThemeConfig（start_room/death_room/revive_room/jail_rooms + default 非武侠/wuxia 武侠）+ [world.py](engine/src/xkx/runtime/world.py) build_world 加 theme_config 参数 + governance.py/death.py/cli.py 改读 world.theme_config（源码无武侠房间路径字面量）
  - **dbase key 兼容层保真让步豁免**（决策 3）：dbase_map.py 的 "dali/rank" + TitleComp.dali_rank 字段名保留（LPC dbase key 兼容，类比 ADR-0003 qi/jing 拼音保留），test_theme_neutrality 硬门禁豁免
  - **test_theme_neutrality 扩展收官硬门禁**（决策 4）：扫描范围扩展到 governance/death/cli/race/family，黑名单加门派名（武当/少林/峨嵋/华山/丐帮/桃花/古墓/灵鹫/星宿/白驼/明教/雪山派/血刀/大理段/全真）+ 武侠房间路径（shaolin//dali//xueshan//huashan//wudang//emei/），+4 tests
  - **1-2 门派验证**（决策 5）：武当派保气标准加成（FamilyBonus 标准载体）+ 海盗帮派航行加成（非武侠 FamilyBonus 边界验证）
  - **Vitals 补 eff_jingli**（2.2 遗漏补全）：LPC human.c 行 212/404 引用 eff_jingli，2.2 扩展 eff_jing 漏了 eff_jingli，2.7 补全 + dbase_map 激活
  - **spec 层规格补充**（开放问题 1）：[layer_h_race.py](engine/src/xkx/spec/layer_h_race.py) setup_race + apply_family_bonuses 最小 FunctionSpec 契约（不穷尽 13 门派公式）+ [test_spec_race.py](engine/tests/test_spec_race.py) 41 tests
  - **max_jingli 下限保护**：con<14 时 (con-14) 为负致 max_jingli 为负（LPC 边界 bug），加 max_jingli = max(max_jingli, 1) 下限保护（对照 human.c 行 417 setup_char 兜底）
  - agent teams 3 路并行：A race.py+family.py+test / B theme.py+world/governance/death/cli 改 / C spec 层；A+C 完成后修复 B 的 test 适配 + test_theme_neutrality 扩展
  - **1598 tests 全绿（+84：80 test_race_family + 41 test_spec_race + 4 test_theme_neutrality 扩展 - 适配调整），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 1（CombatKernel 主题无关性延伸：race 层 + 门派加成是 combat 之外的主题无关性收官）+ dissent 5（themed 治理，门派内容是题材包资产非治理逻辑）+ dissent 10（平台特性范围过载，只切割不全量迁移）

- [x] **M3 启动前置完成**（[ADR-0031](docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) 评审通过 + [16-M3](docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) 实施计划产出）：
  - ADR-0031 CPK 格式固化 + ThemeRegistry 静态加载（M3-2 Wave 1 前置）：7 决策（CpkManifest 数据模型对齐 03 §四 M3 简化 + CPK 目录扁平加 manifest + ThemeRegistry 静态加载 wuxia/default + CPK 加载器 load_cpk 复用 compile_scene + 5 微场景重整为 StdLib CPK + cli.py 改读 ThemeRegistry + 范围边界 module_pack only）+ 5 开放问题倾向裁决（扁平目录/2 题材/线性依赖/独立 schema_version/class_tables 落地）+ kill criteria（CPK 过度设计/ThemeRegistry 滑向热插拔/主题无关性回归）
  - 16-M3 M3 实施计划（上个 session 提交 30a2ea1d 产出，本 session 更新开放问题为已裁决）：5 Wave 分解（Wave 1 M3-2 CPK 格式化 / Wave 2 M3-1 门派核心循环★主线 / Wave 3 M3-3+M3-4 审核+版权并行 / Wave 4 M3-5 全仿真确定性评估收官）+ ADR 编号映射（ADR-0031 已通过 / ADR-0032~0034 待写）+ 依赖图 + 5 开放问题裁决（M2 独立 LLM 兼顾 Wave 2/雪山派旗舰/CLI REPL 内部验证/版权方案+1-2 示范/provenance 后置门3）+ kill criteria（5 Agent 修订量/7 项目级 18 月/8 PG 硬止损 + M3-2/1 内部）+ 时间预估 8-12 周（04 估计 6-8 月吻合）
  - **分支修正**：上个 session 16-M3 在 feat/stage-3-m3 分支提交（30a2ea1d），本 session 初在 master 误判为"未落盘"并重写，已切换到 feat/stage-3-m3 以远端版本为基础，更新开放问题为已裁决 + 加 ADR-0031
  - 关联 dissent 5/10/3（ADR-0031）+ dissent 1/5/7/10（16-M3 M3-1 映射）

- [x] **M3-2 CPK 格式化 + StdLib CPK 骨架完成**（[ADR-0031](docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) 落地 / [16-M3](docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) Wave 1）：
  - CpkManifest 数据模型（[cpk.py](engine/src/xkx/dsl/cpk.py)）：对齐 03 §四 M3 简化（provenance/resource_quota 后置 None + market Day1 预留 + module_pack only，ugc 后置 Wave 3）+ CPK_MANIFEST_SCHEMA_VERSION=1 + CpkDependency/MarketFields/Provenance/ResourceQuota 子模型
  - ThemeRegistry 静态加载（[theme_registry.py](engine/src/xkx/runtime/theme_registry.py) ThemeDescriptor 8 字段 + ThemeRegistry 注册表 require/get）+ 题材包数据层 [themes/](engine/src/xkx/themes/)（wuxia 武当派 FamilyBonus + default 海盗帮 FamilyBonus，与 runtime/ 分离避免主题无关性硬门禁，类比 theme.py ThemeConfig.wuxia() 题材包配置数据）
  - CPK 加载器（[cpk_loader.py](engine/src/xkx/dsl/cpk_loader.py) load_cpk -> manifest + IR + rules，复用 compile_scene + manifest 校验 entry_points.main_scene 在 rooms + theme 已注册；dsl 不依赖 runtime 用 TYPE_CHECKING）
  - 5 微场景重整为 StdLib CPK（各加 manifest.yaml：xueshan/zhongnan/wuxia=wuxia 主题，academy/age_of_sail=default 主题，pack_type 全 module_pack）
  - [cli.py](engine/src/xkx/cli.py) 改造：load_game 改读 ThemeRegistry + load_cpk（theme_config 从 registry[manifest.theme] 注入，不再硬编码 ThemeConfig.wuxia()，向后兼容 scene 参数）
  - 测试：test_cpk 9 + test_theme_registry 9 + test_cpk_loader 11 = 29 新测试（含 5 微场景 parametrize + manifest 校验 + 主题无关性硬门禁扩展 theme_registry.py 无门派字面量）
  - **1628 tests 全绿（+30），ruff 全过**；test_theme_neutrality（主题无关性，themes/ 分离）+ test_load_test（tick p99 < 100ms）硬门禁持续通过
  - 关联 dissent 5（themed 治理，CPK 题材包资产载体）+ dissent 10（平台特性范围过载，M3 只 StdLib CPK 骨架，UGC 沙箱/市场后置）+ dissent 3（层1 原语护栏，capabilities_required 衔接层1 词汇表）

## 已知技术债（后置，不阻塞阶段 0）

- **CLI 命令解析缺陷**：`cli.py` 用 `line.strip().split()` 解析，NPC/物品名含空格时拆错（如"小 喇嘛"）。需改用引号感知的 tokenizer 或 LPC 风格的 `parse_command`（阶段 0 命令管线 8 段中间件时一并处理）
- **`drop` 命令未实现**：`commands.py` 有 take/give 无 drop。阶段 0 物品系统规格提取时补全
- **xlama2 交互闭环未完成**（S4e GAP）：ask_tea 的 set_flag 茶 + accept_object 酥油的 clear_flag + 物品生成需 ask->action 机制 / clear_flag action / 物品系统（阶段 0）
- **门状态机运行时未实装**（S3 GAP）：do_knock / call_out 定时关 / 跨房间 exits 同步（阶段 0）
- **LPC 规格提取跳过部分**：本次 9 层覆盖核心循环约 7000 行，跳过 condition 具体类型 / 第二梯队守护进程 / 后置系统 / kungfu+d/ 内容。补充计划见 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md)（3 类分阶段补充，"实现到时才补"原则，不提前批量提取）

## In Progress

**阶段 2 全部完成并合并 master**（merge `fee5dd25`，Wave 1-4 七子系统 2.1-2.7，1598 tests 全绿）。阶段 2 -> M3 决策检查点全部通过。

**无进行中任务**。下一步 M3 单题材武侠完整可玩 demo（见 Next Up）。

**剩余可选任务**（非 M3 前置，可穿插）：
- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）-- 为工时承诺提供数据支撑，可后置
- golden trace 定点辅助（driver PID 22753 运行中）-- do_attack 七步基线已录制（dissent 4 验证），M3 可扩展更多场景

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

**M3-2 Wave 1 完成**：[ADR-0031](docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) 落地（CpkManifest + ThemeRegistry 静态加载 + load_cpk + 5 微场景重整 + cli.py 改造，1628 tests 全绿）。**下一步 Wave 2 M3-1 门派完整核心循环**（拜师/练功/战斗/任务/死亡轮回，需 ADR-0032 前置 + 独立 LLM 接入准备）。

**阶段 1 -> 2 决策检查点**（04 §八，全通过）：
- [x] 单进程 asyncio 核心循环跑通？（T1-T9 ✅）
- [x] **1000 在线+100 并发达标？**（T10 ✅ kill criteria 3 GO，tick p99 12.6ms < 100ms）
- [x] combat 确定性可重放？（T6 ✅ [ADR-0023](docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md)）
- [x] Effect/ConditionHandler 契约落定？（T1 ✅ [ADR-0017](docs/adr/ADR-0017-ecs-sparse-set-effect-component.md)/[0018](docs/adr/ADR-0018-conditionhandler-on-tick-contract.md)）
- [x] 内存权威 + JSON 存档稳定？（T5 ✅ [ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md)，原子写 + offload + 崩溃恢复）

**下一步主线**：M3 单题材武侠完整可玩 demo（6-8 月）。2.7 门派切割已完成（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md) 落地，RaceProfile + FamilyBonus + ThemeConfig + test_theme_neutrality 收官硬门禁，1598 tests 全绿）。M3 在阶段 2 基础上：武侠核心循环可玩（拜师/练功/战斗/任务/死亡轮回）+ 官方 StdLib CPK（武侠内容以 CPK 形式入库，2.7 边界已切）+ 内容审核 pipeline MVP + 版权清洗（金庸衍生 71 文件）+ 全仿真确定性决策点（M3 后评估）。

**阶段 2 Wave 划分**（[15 §四](docs/xkx-arch/15-阶段2-子系统实施计划.md)，Wave 2 改串行）：
- Wave 1：2.1 Query/索引层 ✅ 完成（基础，1101 tests）
- Wave 2：2.2 ✅ / 2.3 ✅ / 2.5 ✅ / 2.6 ✅ 全部完成（逐个串行，用户裁决避免共享文件合并冲突）
- Wave 3：2.4 Combat ✅ 完成（高风险，ADR-0027 落地，1514 tests）
- Wave 4：2.7 门派切割 ✅ 完成（主题无关性硬门禁收官，ADR-0030 落地，1598 tests）

**阶段 2 -> M3 决策检查点**（04 §八，待阶段 2 完成）：
- [x] Combat 迁移行为等价验证 + 文本体验流 diff？（2.4 ✅，golden trace diff 三层全 PASS + ConformanceChecker 8 项全通过）
- [x] 技能三层明确？（2.3 ✅）
- [x] 称谓系统、世界观治理层落地？（2.5 ✅ / 2.6 ✅）
- [x] 门派内容包边界干净切割？（2.7 ✅，ADR-0030 落地，test_theme_neutrality 收官硬门禁全通过）

**可穿插推进**（非阶段 2 前置）：
- [x] **golden trace combat 基线录制完成**（[engine/tools/golden_trace/](engine/tools/golden_trace/)）：do_attack 七步文本 + 概率统计 dodge 27%/hit 73%（dissent 4 基线测试路径打通）；valid_leave 命中行为基线后置（layer1 已有属性测试）
- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）
- [x] [ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md) 层1 谓词集扩充 8 类（已完成，穿插 2.5 期间）

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

**阶段 1**（已完成，全通过）：
- 1000+100 集成测试达标 ✅（[14 压测报告](docs/xkx-arch/14-T10-压测报告.md)，tick p99 12.6ms < 100ms，kill criteria 3 GO）

**阶段 2**（已完成，全通过）：
- Combat 迁移行为等价验证 ✅（2.4 golden trace diff 三层全 PASS + ConformanceChecker 8 项全通过）
- 门派内容包边界干净切割 ✅（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)，test_theme_neutrality 收官硬门禁全通过，核心引擎无武侠烙印，kill criteria 2 GO）

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`cd engine && .venv/bin/python -m pytest`（venv 在 `engine/.venv`；系统 Python 受 PEP 668 限制需 venv）；lint：`cd engine && .venv/bin/ruff check src tests`。
