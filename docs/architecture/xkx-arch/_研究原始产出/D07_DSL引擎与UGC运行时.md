# 方案设计·DSL引擎与UGC运行时

## 设计概述
设计目标是把 XKX 现有"文件即对象、set() 键值袋、inherit+feature 组合"的 LPC 内容模型，重构为以"内容包(CPK)+分层混合 DSL+JSON IR"为核心的 UGC 运行时。核心理念：声明为主、脚本为辅的双轨制。统计显示 8148 个 LPC 文件中 2482 个是纯声明式房间(replace_program)、288 个 inquiry 对话、359 个技能 action 数组、72 个 condition 状态机、1113 个 add_action 事件、890 个 call_out 定时——其中约 30% 是纯数据可直接转 YAML，70% 含事件/对话/定时逻辑需要规则 DSL 或脚本逃生舱。据此采用分层混合 DSL：层0 YAML 声明式(场景/角色/技能/条件数据)、层1 事件规则(condition->action)、层2 Ink 语义对话树、层3 WASM 沙箱脚本逃生舱。所有层编译为统一的 JSON IR 作为唯一真相源，运行时只消费 IR，与创作语法解耦，便于可视化双向编辑与跨节点分发。IR 经 schema 校验+能力审核+资源预算检查三道门后方可注册运行。WASM 沙箱提供燃料计量+能力令牌+内存隔离，对齐 config.xkx 的 eval_cost 语义但可配置、按 CPK 配额。热重载走"文件监听->校验->编译->注册表原子切换->客户端重同步"流程，用 set_temp 旗标做存档点保留进行中状态。内容打包为 CPK(内容包)+manifest(清单)+依赖图+内容寻址版本库，provenance 链从第一个 CPK 内建以支持后期市场计费。多题材通过 ThemeRegistry 插件化，泛化现有 19 门派 class 为主题包机制，wuxia/nautical/academy/modern 各自注册条件谓词/动作动词/组件 schema。

## 组件
- **Layer0YAMLCompiler（层0声明式编译器）**：将 YAML 方言编译为 JSON IR。直接吸收 LPC 的 set() 调用：short/long/exits/objects/item_desc/cost/outdoors/no_fight 映射为 YAML 字段；set('objects',[path:amount]) 的声明式重生清单映射为 reconcile 期望态声明。这是覆盖面最广、收益最大的层（3703 房间 + NPC 基础属性 + 359 技能 action 数组）。支持 heredoc 多行文本（对应 LPC @LONG）。（技术：Python + PyYAML 6.0.2（已验证）+ 自研 schema 方言；用 Pydantic v2 建模 IR 数据类，提供类型校验与序列化）
- **Layer1RuleCompiler（层1事件规则编译器）**：将 condition->action 事件规则 DSL 编译为 JSON IR。覆盖 init/add_action/valid_leave/inquiry 回调等事件钩子。规则语法用 when/do 表达式，条件谓词（actor.has_temp/scene.has_flag/count_gt）与动作动词（say/tell/set_temp/deny_leave/allow_leave/spawn/give_item/schedule）从主题包注册表查询。复杂分支用嵌套 when/else。（技术：Python 自研规则 DSL 词法/语法分析（用 lark 或 textX 构建外部 DSL 文法）；条件求值用受限表达式解释器（AST 白名单节点，禁止任意属性访问））
- **Layer2DialogueCompiler（层2对话树编译器）**：将对话树编译为 JSON IR。采用 Ink 的 knot/stitch/divert/weave 语义模型，解决现有 inquiry 的临时旗标状态机退化问题（qiu.c 的 set_temp('marks/丸') 即对话树退化为手写状态机）。对话节点可挂副作用（set_temp/give_item/quest_progress）与跳转 divert。YAML 表达 Ink 子集避免外部二进制依赖，但保留 inklecate 集成选项供高级创作。（技术：YAML 表达 Ink 语义子集 + 自研对话状态机；可选集成 inkpy/inklecate 处理 weave 复杂流）
- **Layer3WasmCompiler（层3脚本逃生舱编译器）**：加载与绑定 WASM 模块，处理无法用声明式表达的复杂逻辑（两仪剑法双人和合、perform 持续效果状态机、NewRandom 加权随机）。逃生舱默认关闭，按能力审核逐项放开。可信编辑者可用受限 Python（经 RestrictedPython 翻译），UGC 一律走 WASM。宿主 API 通过显式导入绑定。（技术：wasmtime-py（Bytecode Alliance，需 pip install；近原生速度+内存安全+燃料计量）；宿主语言 Rust/AssemblyScript/Python(Rustython) 编译为 wasm32-wasi）
- **IRValidator（IR 校验器）**：编译后的 JSON IR 经四道校验：SchemaValidator 做结构校验；CapabilityAuditor 审核脚本引用的能力是否在 CPK manifest 声明范围内；ResourceBudgetChecker 检查 fuel/wall_time/memory/call_out_quota 是否超限；DependencyResolver 解析依赖图验证引用的资产/主题包存在。校验失败拒绝注册并返回结构化错误。（技术：jsonschema 4.24.0（已验证）做结构校验；networkx 构建依赖图做拓扑排序与环检测；自研能力审计器）
- **SceneRuntime（场景运行时解释器）**：解释 JSON IR 驱动场景。IRInterpreter 加载 IR 为内存对象图；EventBus 订阅/分发场景事件；RuleEngine 对 condition->action 规则求值（dirty 标记缓存）；DialogueMachine 维护对话状态机游标；ConditionScheduler 调度 tick/call_out（替代 heart_beat 全局心跳，改为按需事件驱动）；StateStore 持久/瞬态两层分离（对应 dbase/tmp_dbase）。（技术：Python asyncio 事件循环 + 自研 SparseSet ECS 集成；状态存储抽象层（热 Redis / 冷 PostgreSQL））
- **Sandbox（沙箱执行环境）**：WasmRuntime 执行层3脚本；CapabilityGate 校验每次宿主 API 调用的能力令牌；ResourceQuota 强制 fuel（指令配额，对应 eval_cost）/wall_time/memory/recursion_depth/call_out_quota；HostBinding 提供安全宿主 API（read_world/say/move_self/spawn_in_scene/schedule 等显式能力）。燃料耗尽即中止（对应 LPC 'Too long evaluation' 但可配置、按作者配额）。（技术：wasmtime 燃料计量 + epoch 中断；能力令牌为带签名的 capability claim（JWT 风格）；宿主 API 用 wasm host function 绑定）
- **HotReloader（热重载器）**：FileWatcher 监听 CPK 源文件变更；ReloadCoordinator 执行 校验->编译->注册表原子切换 流程；CheckpointManager 用 set_temp 旗标做存档点保留进行中状态（对话进行中/任务中途）；ClientResync 通知受影响客户端重同步。切换采用 copy-on-write 不可变快照+指针交换保证原子性。（技术：watchdog（已验证）文件监听 + asyncio.Task 调度；注册表为不可变快照+版本号原子切换）
- **ContentPackager（内容打包器）**：CPKBuilder 构建内容包；ManifestManager 管理 CPK 清单（schema_version/license/provenance/dependencies/capabilities/quota）；DependencyGraph 维护 CPK 间依赖与资产引用关系；ContentAddressStore 内容寻址版本库（SHA256 资产哈希，支持版本回滚）；MarketPublisher 市场分发（后期）。（技术：hashlib（标准库）内容寻址；networkx 依赖图；tar/zstd 打包；可选兼容 OCI 镜像格式便于 registry 分发）
- **ThemeRegistry（主题注册表）**：管理多题材主题包（wuxia/nautical/academy/modern/cross）。每主题注册自己的条件谓词/动作动词/组件 schema/默认资产。泛化现有 19 门派 class 模式为主题包机制：kungfu/class/* 即 wuxia 主题下的门派子包。DSL 核心主题无关，每主题扩展词汇表。支持运行时挂载/卸载主题。（技术：Python entry_points 插件机制 + Pydantic 主题 schema 基类；主题包为独立 CPK，可热加载）
- **MigrationAdapter（迁移适配器）**：LPCtoDSLTranspiler 将 8400 LPC 文件批量转译为 DSL 入仓形成基线回归集；PatternExtractor 识别 replace_program 纯数据房间（2482个）优先转层0、inquiry 对话（288个）转层2、add_action 事件（1113个）转层1、perform 复杂技能转层3。基线既验证 DSL 表达力完备性（不能表达即 schema 缺陷），又为后续 UGC 增量提供不变量保护网。（技术：Python LPC 语法分析（基于 lark 解析 LPC 子集）+ 规则化模式匹配；批量转译任务可并行）

## 关键接口/事件
- DSLSource -> compile(sources, theme_pack) -> JSONIR：分层编译器统一入口，返回带 schema_version 的 IR 包
- IRValidator.validate(ir, manifest) -> ValidationResult{ok, errors[]：schema/能力/配额/依赖四道校验，返回结构化错误（位置+原因+修复建议）
- ContentAddressStore.put(cpk) -> ContentHash（SHA256）；get(hash) -> CPK；list_versions(cpk_id) -> [Version]：内容寻址版本库，不可变快照
- DependencyGraph.resolve(cpk_id) -> ResolvedGraph{order, conflicts[]：拓扑排序依赖，检测循环与版本冲突
- SceneRuntime.load_scene(scene_id) -> SceneHandle：按需激活场景（对应 LPC load_object），从存储重建或缓存命中
- EventBus.publish(event) -> seq：场景事件发布，返回单调递增序号
- EventBus.subscribe(topic, handler, filter) -> SubscriptionID：按 topic 路由 + 谓词过滤（对应 message class 过滤）
- RuleEngine.eval(condition, context) -> bool：受限表达式求值，AST 白名单节点
- RuleEngine.fire(event, rules[]) -> [Action]：匹配规则并产出动作序列
- DialogueMachine.enter(dialogue_id, actor_id) -> DialogueCursor；.choose(option_id) -> {response, side_effects, next_node}：对话树状态机游标
- ConditionScheduler.schedule(after_s, action, cancel_token=None) -> TaskID；.cancel(task_id)：持久化延迟调度，支持取消语义（对应 remove_call_out）
- Sandbox.exec(wasm_module, host_api, fuel, caps) -> Result{ok, value, fuel_used, cycles：WASM 执行带燃料计量与能力校验
- CapabilityGate.check(token, action, resource) -> bool：每次宿主 API 调用的能力校验
- HotReloader.reload(cpk_id) -> ReloadResult{ok, affected_clients[], checkpoint_id：原子切换 + 存档点 + 客户端重同步
- ThemeRegistry.register_theme(theme_pack) -> ThemeID；.resolve_predicate(name)/.resolve_verb(name)：多题材词汇表注册与查询
- CPKBuilder.build(asset_dir, manifest) -> CPKBundle；.sign(private_key) -> SignedCPK：内容包构建与签名
- 事件类型枚举（抽象自 LPC 钩子）：scene.enter_room/leave_room（init/valid_leave）、scene.command（add_action）、scene.inquiry（对话触发）、scene.tick（heart_beat）、combat.hit/round_resolved、actor.death/kill、economy.transfer、inventory.pickup/drop、scene.reset（房间重生）

## 数据模型
数据模型采用分层 IR + 内容寻址版本库。\n\n1) Scene IR（JSON 中间表示，schema_version 控制演进）：每资产（room/npc/skill/condition/dialogue）为类型化 JSON 节点。room 含 short/long/exits[dir->ref]/objects[list]/item_desc/cost/tags/events[]；npc 含 identity/attributes/vitals/skills/inquiry_ref/chat_msg/events[]；skill 含 action[]数组（force/dodge/damage/lvl/damage_type/skill_name）+ valid_enable/valid_learn 规则；condition 含 update_fn + ttl + CND_CONTINUE 标志。\n\n2) Event（事件消息）：{type, version, seq, scene_id, actor_id, payload, context}。type 命名空间化（scene.enter_room/combat.hit/economy.transfer）。seq 单调递增支持断线重连 delta 重放。context 携带 capability_token + origin。\n\n3) 持久/瞬态分层（对应 dbase/tmp_dbase）：持久层存于 PostgreSQL（场景实例状态 + autoload 引用），瞬态层存于 Redis（AOI 内活跃实体 + ModifierStack apply 临时加成）。static 修饰语义映射为 @transient 字段不持久化。\n\n4) CPK Manifest（内容包清单）：{cpk_id, schema_version, theme, version, license, provenance{content_hash, parents[]}, dependencies[], capabilities_required[], resource_quota{fuel_per_tick, wall_time_ms, memory_mb, call_out_quota}, assets{}, entry_points{}}。provenance 从第一个 CPK 内建版权溯源链。\n\n5) Prefab（原型模板）：武器/防具/NPC 的只读定义作为 Prefab 资源（升级 default_ob），克隆时实例化组件副本，与 UGC 场景定义统一。\n\n6) CapabilityClaim（能力令牌）：{subject, capabilities[], resource_limits, expires, signature}，JWT 风格签名，显式化 previous_object 隐式信任链。\n\n7) Checkpoint（热重载存档点）：{scene_id, temp_flags{}, dialogue_cursor, quest_states{}, version}，热重载时保留进行中状态。

## 旧->新映射
- set("exits",([dir:path])) 硬编码绝对路径出口映射 -> **YAML exits: {dir: room_ref} + 图模型 edge**（路径=ID 解耦为稳定实体 ID，房间可在区域间迁移而不破坏引用；exit 成为图边支持寻路与 DSL）
- set("objects",([path:amount])) reset 声明式重生清单 -> **YAML objects 声明 + ReconcileService 期望态收敛**（保留'声明式清单+系统收敛到期望态'的不可变基础设施思想，去掉全量扫描改为分片/按需/事件驱动刷新）
- set("item_desc",([key:heredoc])) 可检查物品描述 -> **YAML item_desc + LookAction 规则**（heredoc 多行文本直接映射 YAML 块标量，保留语义化）
- set("inquiry",([kw:resp|func])) 对话映射（288个） -> **Ink 语义对话树（层2）**（qiu.c 的 set_temp('marks/丸') 临时旗标是对话树退化为手写状态机；Ink 的 knot/stitch/divert/weave 更简洁，支持复杂分支与跳转）
- mapping *action 技能招式数组（359个技能） -> **YAML 技能定义 + SkillDSL schema**（action/force/dodge/damage/lvl/damage_type 字段直接映射为类型化 schema；这是技能 DSL 雏形，保留数据驱动）
- update_condition(me,duration)+CND_CONTINUE 状态机（72个） -> **ConditionComponent + ConditionSystem tick**（CND_CONTINUE 自主存活语义保留为 Condition 实体的 ttl 衰减；状态守护进程映射为 ECS System）
- void init(){add_action(...)} 事件注册（1113个） -> **events: [{on: command, verb: X}] 规则**（init/add_action 声明式事件注册从代码下沉为 DSL 事件规则，可静态分析）
- int valid_leave(me,dir) 离开校验钩子 -> **events: [{on: leave_room, direction: X}] 规则**（房间级离开校验是天然 UGC 剧情触发点，保留为事件钩子；deny_leave/allow_leave 动作替代 return notify_fail/return 1）
- call_out(func,delay) 非持久延迟调度（890处+3728全库） -> **schedule: {after: Xs, do: [...]} 持久化调度**（call_out 绑定对象生命周期、崩溃即丢；改为持久化分布式调度器，支持取消语义（remove_call_out -> cancel token））
- perform 持续效果用递归 call_out(回调闭包) -> **Effect 对象 + tick 调度（可序列化可中断）**（回调闭包捕获对象引用无法序列化跨进程；改为显式 Effect 对象，两仪剑法等复杂状态机走 WASM 逃生舱）
- default_ob 单级原型回退（blueprint/clone） -> **Prefab/Archetype 模板实体 + 多级原型链**（blueprint 存只读默认、clone 存差异的模式升级为完整原型/深克隆；UGC 场景定义即 Prefab，多题材即不同组件集）
- dbase 斜杠路径 set/query（F_TREEMAP） -> **嵌套 dict + 类型化 Component schema**（保留路径式访问灵活性，但散落全库的字符串键 query('xxx') 替换为类型化组件杜绝拼写错误；functionp 自动 evaluate 保留为 lazy property）
- eval cost 6亿全局执行预算 -> **per-CPK fuel/wall_time/memory 配额**（单线程全局预算替换为每租户资源隔离；燃料耗尽即中止但可配置、按作者配额（对应 config.xkx 的 maximum evaluation cost））
- kungfu/class/* 19门派硬编码 if-else 加成 -> **ThemePack 主题包注册表**（门派专属加成从 race/human.c if-else 链外提为可声明数据；泛化为多题材主题机制（武侠/航海/书院共享运行时各自演进））
- set_temp('marks/X') 临时旗标状态机 -> **CheckpointManager 存档点 + QuestState**（保留旗标做热重载存档点；任务进度显式化为 QuestState 实体可序列化）
- 文件路径即对象身份 file_name(path#id) -> **稳定实体 ID + CPK 内容寻址**（解耦身份与代码路径，支持热重载与多版本共存（UGC 必需）；资产 SHA256 哈希支持版本回滚）

## 分布式扩展策略
分布式扩展策略以 CPK 为分片与隔离单元，WASM 沙箱天然无状态可水平扩展。\n\n1) 分片单元=CPK+区域共同体：借鉴空间分片研究结论，按区域共同体（出口图社区凝聚，Louvain 检测得 5-8 共同体）切分。每题材世界独立 supervision 与资源配额，Actor 边界即租户隔离边界。热区（city 扬州）做内部微分区。\n\n2) 事件总线跨分片路由：场景内事件走本地 EventBus（低延迟），跨分片事件（tell 跨区/频道广播）经 NATS JetStream 扇出。边界房间建立跨分片事件代理，AOI 跨分片订阅通过边界房间转发，避免每条消息走全局总线。\n\n3) WASM 沙箱无状态横向扩展：沙箱执行不持有状态，可在任意 worker 执行。场景实例状态外部化（Redis 热/PostgreSQL 冷），actor 钝化时落盘、激活时恢复。按活跃度感知缓存逐出（对应 clean_up 环境感知回收）。\n\n4) 热重载跨节点协调：注册表版本号 + 广播失效信号。源 CPK 变更时编译新 IR -> 原子切换本地注册表 -> 向 NATS 发布 cpk.invalidated 事件 -> 其他节点收到后各自重载。最终一致性窗口内旧版本继续服务避免中断。\n\n5) 内容寻址存储全局共享：ContentAddressStore 作为共享对象存储（或兼容 OCI registry），所有节点按哈希拉取，避免每节点存全量。CDN 分发大资产。\n\n6) 资源隔离按 CPK 配额：每 CPK 的 fuel/wall_time/memory 配额由 ResourceQuota 在调度时强制，恶意/失控 CPK 不影响其他租户（对应 eval_cost 但分布式 per-tenant 隔离）。分布式调度器按负载将场景实例迁移到空闲 worker。\n\n7) Agent 协作创作作为 actor：LLM Agent 向 region 投递'创作消息'，产出物走与人类相同的 DSL->校验->打包流程，provenance 链标记作者为 agent_id。多 Agent 协作编排者-工作者分工，生成-评审-修订循环。

## 技术选型
- Python 3.12（已验证可用）作为运行时主干，asyncio 事件循环驱动场景
- PyYAML 6.0.2（已验证）解析层0/层2 YAML 方言
- Pydantic v2 建 IR 数据类与 schema，提供类型校验+序列化+演进迁移
- jsonschema 4.24.0（已验证）做 IR 结构校验
- lark 或 textX 构建层1 事件规则 DSL 文法（EBNF 外部 DSL）
- wasmtime-py（Bytecode Alliance，pip install wasmtime）执行层3 WASM 脚本，提供燃料计量+epoch 中断
- watchdog（已验证）文件监听驱动热重载
- networkx 构建依赖图与拓扑排序，做 CPK 依赖解析与环检测
- hashlib（标准库）内容寻址 SHA256 资产哈希，支持版本回滚
- RestrictedPython 处理可信编辑者的受限 Python 脚本（翻译为安全 AST）
- inkpy 或自研 Ink 语义子集解析器处理对话树（避免 inklecate 外部二进制依赖）
- tar+zstd 打包 CPK，可选兼容 OCI 镜像格式便于 registry 分发
- Redis（热状态/AOI 活跃实体）+ PostgreSQL（权威事件/快照）状态外部化
- NATS JetStream 跨分片事件扇出与热重载失效信号广播

## 风险
- DSL 表达力不足导致逃生舱滥用：perform 持续效果状态机（两仪剑法双人和合）、NewRandom 加权随机等复杂逻辑难以用声明式表达，若层3 WASM 门槛过低会被滥用回到脚本即代码。对策：层1-2 持续扩充表达力，层3 严格审核+能力提升机制
- 8400 LPC 文件迁移完整性：含复杂逻辑的 perform 技能（call_out 闭包）、auto_perform 门派 AI、conditions 状态机可能无法机械转译。对策：PatternExtractor 分级，无法表达的触发 schema 缺陷反馈迭代 DSL；保留 LPC 适配器桥接期
- 热重载进行中状态丢失风险：对话进行中/任务中途/战斗进行中时热重载可能破坏状态。CheckpointManager 的 set_temp 存档点机制需精确捕获所有进行中态，遗漏即玩家体验断裂。对策：灰度切换+战斗中禁止重载+回滚机制
- WASM 沙箱宿主 API 边界设计复杂度：能力清单与宿主 API 绑定的粒度难以把握，过细则脚本编写繁琐，过粗则安全边界模糊。对策：从 read_world/say/move_self 等高频能力先行，迭代收敛
- Ink 对话树与层1事件规则的职责重叠：对话副作用（give_item/quest_progress）既可在对话树节点也可在事件规则触发，职责边界模糊。对策：对话树只管流程与文案，副作用统一委托事件规则
- WASM 编译工具链门槛：UGC 作者需掌握 Rust/AssemblyScript 编译为 wasm32-wasi，抬高创作门槛。对策：提供受限 Python->WASM 工具链（RestrictedPython + Nuitka/Pyodide），可信编辑者可用
- 内容寻址版本库存储膨胀：8400 LPC 转 CPK + 后续 UGC 增量，内容寻址存储可能快速膨胀。对策：去重（相同内容共享 blob）+ GC（无引用版本回收）+ LRU 冷存储分层
- 多题材 schema family 一致性：武侠/航海/书院等主题包各自演进可能导致 DSL 分裂。对策：核心 IR 保持主题无关，主题包只扩展词汇表不修改核心 schema；schema 演进走 deprecation 周期
- 分布式下热重载跨节点一致性：原子切换在单节点简单，跨节点需协调。对策：注册表版本号+广播失效信号+最终一致性窗口；灰度切换避免一刀切
- 安全模型重建依赖：securityd.c 的能力权限模型本分支已损坏（authorized_cmds['cmd'] 拼写 bug），需先重建能力服务再开放 UGC 协作，否则多人创作的安全边界无法成立。这是前置硬约束

---

## 🔍 对抗验证

**裁定**：risky — 架构方向正确（分层混合 DSL + JSON IR 单一真相源 + 内容寻址版本库 + 能力令牌安全模型 + 状态外部化），且 current->new 映射绝大多数准确（经代码验证 qiu.c 状态机退化、hebi.c 闭包、securityd.c 拼写 bug、30% 纯数据占比均属实）。但存在三个承重级缺陷使其在当前形态下落地会失败：①WASM 沙箱'天然无状态'与 perform 多 actor 有状态协调逃舱自相矛盾，hebi.c 这类双人和合逻辑无法在无状态沙箱中正确运行；②'替代 heart_beat 全局心跳改为事件驱动'严重误判——heart_beat 是战斗回合驱动器（feature/attack.c 注释明确），非可替代的周期清理，189 个 auto_perform NPC AI 循环是连续行为不是离散事件；③inquiry 对话本质是交易状态机（101 个 NPC 同时耦合 inquiry+accept_object+set_temp），Ink 叙事分支模型不匹配交易原子性需求。此外统计存在偏差（inquiry 434 非 288、技能约 182-209 非 359），会影响迁移工作量估算。建议在启动批量迁移前先做表达力校准实验。

**严重度**：high

### 问题与修复
- **WASM 沙箱'天然无状态可水平扩展'与 perform 状态机逃舱自相矛盾。实测 hebi.c(kungfu/skill/liangyi-dao/hebi.c) 的双刀和璧是深度有状态多 actor 协调：两玩家共享 buff、递归 check_fight 监控双方是否仍在共同战斗、条件清理(liangyi_check)、跨对象消息协调。用 start_call_out(: call_other, __FILE__, "check_fight", me, target, victim, skill/2 :) 捕获对象引用。无状态 WASM 模块无法维护这种跨 actor 协调态，方案虽提'Effect 对象可序列化'但未说明无状态沙箱如何驱动有状态多 actor 状态机。**
  - 影响：两仪剑法双人和合(hebi.c)、perform 持续效果状态机等核心玩法逻辑无法在无状态 WASM 中正确实现；若强行外部化状态，每次状态访问经宿主 API 往返 Redis，延迟与一致性代价未被评估
  - 修复：明确将 WASM 定位为无状态计算单元（pure function：input state -> compute -> output action），所有状态（Effect 对象、双人和合协调态）外部化为可序列化 Effect/QuestState 实体存于 Redis/PG；WASM 每次调用只做单步状态转移计算，多步状态机由 ConditionScheduler 驱动 tick 反复调用 WASM。但这引入每次状态访问经宿主 API 往返 Redis 的延迟，需在 IR 层做状态局部性优化（相关 Effect 同节点 co-locate）。或者：对这类强状态多 actor 协调，不进 WASM，而是扩展层1规则 DSL 的 Effect 原语（apply_buff_to_actors/spawn_coordinated_effect），承认它是规则而非脚本。
- **'替代 heart_beat 全局心跳改为按需事件驱动'严重误判 heart_beat 的角色。实测 feature/attack.c:'This is called in heart_beat() to perform attack action'——战斗回合由 heart_beat 驱动；feature/action.c:busy 状态(战斗延迟)由 heart_beat 驱动；inherit/char/char.c 的 heart_beat() 处理命令计数清理/频道防刷/内力上限校验；condition.c 注释:'update_condition is called by heart_beat'。heart_beat 是整个战斗与生存模拟的主循环，不是'可替代的周期清理'。事件驱动适用于触发器(进房/命令/对话)但不适用于连续模拟(战斗回合/NPC AI 循环/持续效果 tick)。实测 189 个文件使用 auto_perform 递归 call_out 做 NPC 战斗 AI——这是连续行为循环不是离散事件。**
  - 影响：若按'事件驱动替代全局心跳'实施，战斗回合、NPC AI、持续伤害/治疗等核心模拟将失去驱动机制，或需事后补回周期调度，造成架构返工
  - 修复：保留周期性 tick 作为一等公民：ConditionScheduler 应明确同时支持事件触发与周期 tick 两种模式，而非'替代'heart_beat。将 heart_beat 重新定位为'distributed tick scheduler with per-scene/per-actor frequency control'而非'被替代的全局心跳'。auto_perform AI 循环(189处)应建模为 ECS System 的连续行为组件(ContinuousBehaviorComponent)，由 System 按频率驱动，而非试图塞进事件规则。
- **inquiry 对话本质是交易状态机而非对话树，Ink 语义模型不匹配。实测 d/huanghe/npc/qiu.c:inquiry(:ask_me_1:) 设 set_temp('marks/丸') -> accept_object 检查 marks/丸 + 银两>=5000 + wan_count>0 -> 给物品 + 减库存 + 删旗标。这是'询问->设旗标->收物->校验->交付'的原子交易流程耦合于对话入口。实测全库 101 个 NPC 同时含 inquiry+accept_object+set_temp。Ink 的 knot/stitch/divert/weave 是叙事分支模型，不天然表达'给我5000两并校验前置旗标与库存的原子交易'。方案风险#5 说'对话树只管流程与文案副作用委托事件规则'但对话流程本身就是副作用触发点，拆分反而引入一致性风险。**
  - 影响：强行套 Ink 对话树会丢失交易原子性：对话节点到达但交易副作用未执行，或交易执行但对话流程不一致。迁移 434(非288)个 inquiry 文件时大量需手写适配
  - 修复：在层2引入'交易节点'(transaction node)语义：dialogue node 可挂载原子交易(give_item + take_money + decrement_stock + set_flag 为单一原子单元)，与 Ink 的纯流程 divert 区分。或更激进：inquiry 不全转 Ink，简单的字符串响应转层0，带交易的转'对话+交易'混合节点而非强行套对话树。先做 inquiry 子分类统计：纯字符串响应 vs 函数回调带交易，分别走不同迁移路径。
- **逃生舱使用率将远超预期。方案自评约70%逻辑需规则或脚本，但实测的复杂面比预估更大：189个 auto_perform NPC AI 循环、101个 inquiry+accept_object 交易 NPC、75个 call_out 闭包(:...:)、172个 perform 状态机、40个 CND_CONTINUE 条件守护。层1规则 DSL 的动词集(say/tell/set_temp/deny_leave/allow_leave/spawn/give_item/schedule)缺少'对多 actor 同时施加 buff''监控两 actor 是否仍共同战斗''加权随机选择'等原语，这些逻辑会大量落入层3。**
  - 影响：逃生舱滥用使'声明为主脚本为辅'退化为'脚本为主声明为辅'，UGC 安全模型与可视化编辑目标落空；大量逻辑在 WASM 中无法静态分析，迁移回归集失效
  - 修复：加大层1规则 DSL 的表达力投入，优先实现 perform 效果原语与状态机模式，缩小逃生舱需求面。设置逃生舱使用率 KPI（如 <15% 逻辑走 WASM），超标触发 DSL 表达力迭代。对 189 个 auto_perform 做专项模式提取，抽象为可声明 NPC AI DSL 而非全进 WASM。先做分类统计：多少 perform 真正需要 WASM，多少可用扩展后的规则 DSL 表达。
- **CheckpointManager 存档点模型遗漏 NPC 本地持久态。实测 qiu.c 用 set('wan_count',5)/set('dan_count',5) 作为 NPC 自身库存计数，这是 NPC 本地持久态(dbase)非 temp_flag。方案的 Checkpoint 模型 {scene_id, temp_flags{}, dialogue_cursor, quest_states{}, version} 只覆盖玩家临时旗标与对话游标与任务态，未纳入 NPC 本地 dbase 持久字段。热重载切换时若不保存 NPC 的 wan_count，重载后库存重置为初始值，玩家可重复刷物品。**
  - 影响：热重载后 NPC 库存等本地状态可能重置，玩家体验断裂；接受物品交易中途重载可能导致物品复制或丢失
  - 修复：扩展 Checkpoint 模型为 {scene_id, temp_flags{}, npc_local_state{}, dialogue_cursor, quest_states{}, active_effects[], version}，显式纳入 NPC 本地持久态。对热重载采用分场景粒度的写时复制快照，而非全局旗标。战斗中禁止热重载规则需明确'战斗中'的判定（任何 actor 处于 combat 状态即锁定）。
- **RestrictedPython 被当作可信编辑者脚本层但非安全边界，方案未充分警示。RestrictedPython 有长期逃逸漏洞历史，它是'劝退层'非'安全边界'。方案说'可信编辑者可用受限 Python'但'可信'的界定与旋转（编辑者被攻破后）未定义。**
  - 影响：若将 RestrictedPython 暴露给半可信或被攻破的可信编辑者，可能导致沙箱逃逸
  - 修复：明确声明 RestrictedPython 仅用于可信编辑者且非安全边界；UGC 脚本一律 WASM。为可信编辑者的受限 Python 增加额外的运行时资源配额(fuel)与能力令牌校验作为纵深防御，不依赖 AST 过滤单独把关。
- **分布式 fuel 聚合执行模型缺失。单进程 LPC 的 eval_cost 由驱动解释器统一强制；分布式 WASM 的 fuel 由 wasmtime 按 module-invocation 计。但 CPK 逻辑跨多模块/多 actor/多节点时，谁聚合 fuel？一个恶意 CPK 可发起大量小调用，每次低于单次 fuel 上限但累计无界。方案提 call_out_quota 但未说明跨调用聚合执行。**
  - 影响：恶意/失控 CPK 可通过大量小调用累计消耗无界资源，绕过 per-invocation fuel 限制，影响其他租户
  - 修复：设计分布式燃料聚合器：按 CPK 维度聚合跨调用 fuel（用 Redis 计数器或分布式限流），设置 CPK 级别滑动窗口配额，超限熔断该 CPK 调度。call_out_quota 需明确为'CPK 可挂起的未完成延迟任务总数'上限，由调度器在入队时校验。
- **Louvain 社区检测分片是静态的，UGC 动态新增房间后需 re-shard。方案说'按出口图社区凝聚 Louvain 检测切分'但 UGC 作者持续加房，出口图动态变化，每次 re-run Louvain 并 re-shard 开销大且打断在线玩家跨区移动。**
  - 影响：UGC 增量改动房间图后 re-shard 开销大且可能中断在线玩家
  - 修复：改用增量/在线社区检测（如动态 Louvain 或标签传播），CPK 变更只影响局部社区。明确 re-shard 期间的玩家迁移协议（粘性会话 + 旧分片宽限期内继续服务）。定义'区域共同体'的稳定性阈值，避免高频 re-shard。
- **4 层 DSL 对 UGC 作者心智负担过大。作者写一个带对话与物品交换的 NPC 需懂层0(NPC数据)+层2(对话树)+层1(事件副作用)+可能层3(复杂逻辑)。这比当前 LPC 单文件模型在某些场景更复杂。**
  - 影响：UGC 创作门槛过高，影响平台普及
  - 修复：提供可视化编辑器作为首选创作入口（底层生成多分层 DSL），降低作者心智负担。明确各层使用率目标（如 L0 覆盖 60%+ 内容）并监控，若某层使用率异常说明门槛过高需降层。先做小批量迁移验证：取 20 个代表性文件人工转译，统计各层分布与耗时，校准预估。

### 改进建议
- 重新定位 heart_beat：不提'替代'而提'分布式化'。ConditionScheduler 明确同时支持事件触发与周期 tick 两种模式，战斗回合/NPC AI/持续效果保留周期语义，由 per-scene/per-actor 频率控制驱动，auto_perform(189处)建模为 ECS ContinuousBehaviorSystem 而非事件规则。这是最关键修正——当前'事件驱动替代全局心跳'的框架会导致战斗与 AI 子系统返工。
- 先做表达力校准实验：取 30 个代表性文件(含 hebi.c 双人和合、auto_perform AI、inquiry 交易、condition 状态机)人工转译为 DSL，统计落入各层的分布与无法表达的比例。若层3占比超 20%，说明层1-2 表达力不足，需先扩充规则 DSL 原语(apply_buff_to_actors/weighted_random/monitor_cooperation)再推进迁移。不要在表达力未验证前启动 8400 文件批量迁移。
- 对 inquiry(434个非288个)做子分类迁移：纯字符串响应转层0、带交易流程的转'对话+交易原子节点'混合模型而非强行套 Ink。接受 accept_object 是 inquiry 的必要配套(101个文件耦合)，对话树需内建交易原子节点语义而非事后委托事件规则。
- WASM 逃生舱定位为无状态计算单元(pure function)，多 actor 协调态外部化为可序列化 Effect 实体；或对强状态 perform 扩展层1规则 DSL 的 Effect 原语。设定逃生舱使用率 KPI(<15%)超标触发 DSL 迭代。明确 RestrictedPython 非安全边界仅用于可信编辑者，UGC 一律 WASM。
- 扩展 Checkpoint 模型纳入 NPC 本地持久态(npc_local_state{})与活跃效果(active_effects[])，战斗中(actor 处于 combat)禁止热重载。分布式 fuel 设计 CPK 级滑动窗口聚合配额防小调用累计攻击。分片改增量社区检测避免频繁全量 re-shard。
- 迁移优先级建议：层0 纯数据房间(2280个)先行建立基线回归集验证 schema 完备性；securityd.c 能力模型重建作为 UGC 协作前置硬约束先行修复(已验证 authorized_cmds['cmd'] 拼写 bug 在 line 756)；复杂 perform/inquiry 分级渐进迁移，保留 LPC 适配器桥接期。
