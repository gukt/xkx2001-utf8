# 第三轮专家对抗复审 · 原始产出 Digest

> 6 位专家独立复审 + 3 个开放问题交叉质证 + 主持人收敛裁决的结构化原始产出。本 digest 为可读摘要，完整字段见同名 .json。

## 一、6 位专家独立复审

### 游戏服务器架构师（侧重：收缩后整体分层架构；单机 1000 在线+100 并发在纯 Python+a
- **裁定**: risky — 收缩方向正确且必要——v2 的"risky"很大程度源于分布式/Ray/K8s/全量事件溯源等过早复杂度，6 条约束精准拆除了这些承重风险。但收缩后的单机纯 Python+asyncio+内存JSON 存档架构在三个承重细节上未落地，足以在实现期造成返工或运行时故障：(1) 单进程 tick 计算与 WS I/O 共享一个事件循环，tick 预算硬约束、非均匀 tick、GC 调优均未规范——这是 1000 在线+100 并发唯一真正的可行性风险，阶段 0 micro-benchmark 是 go/no-go 门禁而非走过场；(2) JSON 定时存档的崩溃安全性（原子写 write-temp...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: 砍 Redis 全部依赖（session 路由表/ring buffer/限流令牌桶/placement/读穿透缓存/JobStore）——单进程内全部内存化（session di; 砍分布式网关全套（SO_REUSEPORT 多 worker / 会话粘附路由表 / NATS 跨节点扇出 / PlacementService 一致性哈希 / Migration; 砍 EntityAddr `world://<shard>/<region>/<room>#<uuid>` URL 寻址——单进程无 shard/region，直接用 entity; 砍 uvloop 硬依赖——1000 连接的 I/O 不是瓶颈（stdlib asyncio 可承载 10k+ 空闲连接），瓶颈是 compute；先用 stdlib asynci
- **承重论断(high)**: 1000 在线+100 并发在纯 Python 单进程 asyncio 下成立，但唯一前提是 tick 预算硬性受控（<50ms）+ 非均匀 tick（仅活跃实体，非全量 1000）+ 存档与 GC 不阻塞事件循环。否则 GIL 下单进程 ; 内存权威+JSON 存档 与 PG 权威+Redis 缓存 是两种不同一致性模型，策略模式存储接口必须以"持久化边界"（persist=崩溃恢复级耐久）为抽象而非"save=权威写"，否则迁 PG 时是架构变更非策略切换。; JSON 存档必须 write-temp+os.rename 原子写 + 事件循环外 offload + dirty-flag 分摊，否则崩溃即文件损坏或单 tick 冻结。LPC 的 save_object 正是无原子全量覆盖（featu

### 游戏引擎/ECS 专家（单进程 SparseSet ECS、tick 预算、GIL/IO 冲突、引擎
- **裁定**: risky — 收缩方向健康：砍掉分布式/K8s/Ray/PG 权威态，坍缩了上一轮最重的过度设计层，核心（SparseSet ECS、战斗七步管线、DSL 四层、存储策略模式）在单机+内存+1000 在线下是站得住的。但 v2 文档未按收缩重新校准，残留四处承重隐患：(1) tick 预算概念性错误——文档反复写"50ms/20Hz or 100ms/10Hz"，但 LPC heart_beat 实测是 1s（set_heart_beat(1) 已验证），把 20Hz 框架套到 1s-tick MUD 上是在解一个我们不存在的 MMO 问题，并直接驱动了上一轮 Rust-panic 与本轮仍残留的 comp...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: 砍掉全仿真确定性作为阶段 1 里程碑（所有 System seeded RNG+input log）；仅保留 combat 确定性（CombatContext+seeded RNG; 砍掉 50ms/20Hz or 100ms/10Hz 的 tick 预算框架；LPC heart_beat 实测是 1s（set_heart_beat(1) 已验证），该框架在解一; 砍掉 6 件工具链作为阶段 0 一等公民的排位；单机+内存+1000 在线下只保留 entity inspector（最小 REPL/dict-dump）+tick profile; 砍掉热重载安全窗口协议（schema migration+entity state migration+'无跨分片 handoff'条款）；handoff 在收缩下已不存在，简化为
- **承重论断(high)**: 1s tick（LPC heart_beat 默认，已验证 set_heart_beat(1)）使 GIL/IO 冲突与 compiled-core 紧迫感在 1000 在线下基本 evaporate。上一轮的 Rust-panic 是按 ; 全仿真确定性扩展到所有 System 是阶段1 的错误范围；combat-only 确定性（CombatContext+seeded RNG）才是正确范围且已是 combat-sim 等价性的前置。把全仿真塞进阶段1 是让每个 System; ECS 在 Python 是架构选择非性能优化——SparseSet 在 C++ 的 cache locality/SIMD 优势在 Python dict 存储下不存在。这意味着：保留 SparseSet（它是正确的组织选择，支持 UGC; Command 模式必须只覆盖玩家发起+触发器发起的状态变更，绝不能套到 tick 驱动的 System 内部 mutation。把每个 VitalsSystem.update/resolve_attack 包成 Command 会制造热路

### MUD 玩法与文化专家（侧重：Command 模式对 LPC 命令语义/previous_objec
- **裁定**: risky — 收缩方向正确，MUD 文化保真的承重设计（七步管线、PronounContext 服务端求值、技能三层、5 灵魂系统、命令中间件管线）在单机纯 Python 下反而比分布式更容易保真——call_other 退化为进程内同步调用天然契合 LPC 语义，单房间串行是 MUD 固有硬约束而非缺陷，previous_object 信任链在单进程内可干净映射为 ActionContext。但裁定 risky 而非 solid 有三层原因：(1) v2 子系统设计文档（02-v2）仍残留 20 处分布式脚手架（CombatCoordinator/Region Supervisor/handoff out...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: 砍掉子系统 2 的分布式脚手架（CombatCoordinator/Region Supervisor/MigrationCoordinator/handoff outbox 协议; 砍掉 ThemeRegistry 运行时热插拔机制（注册/卸载/依赖解析/版本隔离）——武侠题材尚未完整，无第二个题材校验接口契约，热插拔是凭空发明抽象；初期只做静态加载; 否决自定义规则引擎（Q2）——533 个 valid_leave 触发器已证明 DSL 层1 condition->action 是正确抽象层，themed 治理（天雷/阴间/vo; 砍掉'每个状态变更（含 NPC/系统 tick/call_out）都走 Command 模式'的扩张解读——LPC command_hook 只处理玩家输入，heart_beat/
- **承重论断(high)**: do_attack 七步管线的文本与副作用是交织不可分离的——hit_ob/weapon->hit_ob 返回 polymorphic（string/int/mapping），可同时追加战斗文案与修改伤害；exp/jingli 在管线中途直; RANK_D 的 query_close/query_self_close 是观察者相对的二元关系函数，依赖 this_player() 获取说话者 age/gender 与目标比较——代词求值不是单实体属性而是 (speaker, vie; 533 个 valid_leave 触发器证明 DSL 层1（condition->action）是 LPC 事件触发器的正确且充分的抽象层，无需额外自定义规则引擎。引入规则引擎是冗余抽象，且会因无法统一表达异构 themed 治理而平庸化

### UGC 平台/插件架构专家（侧重：题材包/模块包热插拔三层边界、热插拔机制、受信任开发者扩展模型、规
- **裁定**: risky — 收缩方向对 UGC 平台是净利好：砍掉分布式/分片/Louvain/跨分片 handoff 后，UGC 创作闭环不再背负"先验证分布式再验证创作"的串行债务，单进程纯 Python + 内存 JSON 让 CPK/manifest/依赖图能在阶段-1 垂直切片里直接验证。v2 的承重设计（四层 DSL 编译 JSON IR、CPK 内容寻址、能力令牌安全模型、ThemeRegistry 多题材）在收缩后大部分仍成立且更易落地。但存在三个承重级缺口使其未达 solid：(1) 单进程纯 Python 收缩后 v2 的 WASM（平台级）/RestrictedPython（UGC）双沙箱语言边界失...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: WASM 沙箱用于平台级扩展：单进程纯 Python 下引入 Rust/AssemblyScript 编译为 wasm32-wasi 的工具链负担不抵收益，收缩已排除多租户进程隔离; 分布式燃料聚合器（按 CPK 维度聚合跨调用 fuel 的滑动窗口配额）：这是为跨分片 CPK 脚本设计的，单进程内 per-CPK fuel 就是一个进程内计数器，无需 Redi; CRDT/OT 结构化合并的多创作者 CPK 协作工作流：单机阶段 UGC 验证不需要多人实时同编一个 CPK，砍到单作者 CPK + 简单 fork-merge（人工 merge; 内容市场/分发/计费的任何实现代码：阶段-1~2 只在 manifest 预留字段（author_id/revenue_share/price/title/tags），不实现浏览/
- **承重论断(high)**: 三层边界（核心引擎/题材包/UGC）是正确的抽象且必须早期确立，但'热插拔'应降级为'安全窗口冷插拔'——单进程纯 Python+内存态下运行中热卸载有活跃实体的题材包是悬挂引用研究题，不可承诺。; 19 门派是 wuxia 题材下的内容包（module pack）不是独立题材，v2 把门派当题材会让 schema family 机制退化为扁平命名空间。三层粒度应为 Theme（词汇表）> Module Pack（门派 CPK）> UG; 独立的自定义规则引擎是过早抽象——DSL 层1 condition->action 就是 UGC 触发层，系统级治理策略是题材包内 Python 策略对象，condition-action 逻辑有两处存放地就多了一处。1000 在线下事件触; WASM 沙箱在纯 Python 单进程收缩下不划算——其价值是多租户进程级隔离，而收缩已明确排除分布式/多租户。应用 RestrictedPython 统一两层，靠审查门+能力令牌+配额区分信任级，WASM 留作后置选项。

### DSL/规则引擎专家（侧重：自定义规则引擎统一 condition-action 的设计；与 DSL
- **裁定**: solid — 6 条收缩约束移除了会诱发重型规则引擎机制（分布式 fuel 聚合、PG 权威+Redis 读穿透、多分片规则一致性）的分布式/K8s 复杂度，留下一个本领域内健全的切分：层1 事件规则 DSL（编译为 JSON IR）管触发器、ECS System 管 tick/调度/heart_beat 仿真、命令管线中间件管玩家意图源变更、PermissionService 作唯一 fail-closed 的 (subject,action,resource) 策略引擎。在"单机纯 Python + 内存 JSON 存档 + 1000 在线/100 并发"内，一个薄 Python RuleEvaluat...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: 独立自定义规则引擎框架（Q2 的字面提议）--层1 DSL 编译为 IR 后由轻量 RuleEvaluator 求值即可，再叠一层'统一规则引擎'是重复抽象，且会把 4 种不同调度; RETE/前向链/通用推理及外部引擎（OPA/Rego、Drools 类）--1000 在线/100 并发下每事件规则扇出仅几十条、AST 白名单求值微秒级、无组合爆炸，RETE ; '每个状态变更（含 NPC 行为/系统 tick）都走 Command 模式'（Q3 的激进解读）--NPC 不按键、限流/历史/别名/解码中间件对仿真无意义，强制走 Comman; 分布式燃料聚合器（D07 提案）--单机进程内 per-CPK 燃料计数器即可，跨调用滑动窗口聚合是分布式多租户才需要的复杂度，收缩约束下纯多余。
- **承重论断(high)**: 独立自定义规则引擎是过度设计，层1 DSL + Python 策略对象 + ECS System 已按调度语义正确切分 condition-action 空间，无须再叠一层'统一引擎'。; themed 治理（天雷/阴间/vote/法院）必须是非 UGC 可编辑的平台级 fail-closed Python，不能落入规则引擎或 UGC 可触的规则层。

### 游戏制作人/范围管理
- **裁定**: risky — 收缩方向正确——砍分布式/K8s/Rust 正是上一轮制作人警告的"greenfield 最大风险是过度设计"的直接执行，与范围纪律一致。但收缩执行留下三处承重缺口，使风险从"过度设计"转移到"隐性范围变更"：（1）存储收缩（内存+JSON）不是"换存储"而是对 v2 子系统6（EventStore/SnapshotStore/ReferenceStore/SchedulerStore/outbox/CommandBus乐观并发/CPK内容寻址）的隐性重新设计，策略模式接口对但未标注丢失的语义（事务原子性/崩溃恢复/并发写/CAS/关系完整性）；（2）1000在线+100并发是从实测 MAX_...
- **Q1 题材包热插拔**: 有条件采纳
- **Q2 规则引擎**: 否决
- **Q3 Command模式**: 有条件采纳
- **该砍(前4)**: 砍全仿真确定性扩展到所有 System：单机验证期只保留战斗级确定性（CombatContext+seeded RNG+input log），它已是 M1 交付物且满足反作弊；全引; 砍逻辑热重载协议（importlib.reload+entity state migration+schema migration）至验证期之后：它是 P3，且'热重载安全窗口（无; 砍残留的分布式机械（handoff outbox 两阶段提交/PlacementService 一致性哈希/BoundaryRoomAgent/Region Supervisor ; 砍 Redis 为必需基础设施：约束5已改为内存+JSON存档，Redis 读穿透缓存/JobStore/路由表/outbox 全部失效；v2 子系统6 仍列 Redis，需一并剪
- **承重论断(high)**: 存储收缩（内存+JSON）不是'换存储'而是对 v2 子系统6的隐性重新设计——子系统6把 PG+Redis 贯穿于 EventStore/SnapshotStore/ReferenceStore/SchedulerStore/outbox; 1000在线+100并发在单进程纯 Python 上是从实测 MAX_USERS=50 的 20 倍跃升，v2 共识9已明确 GIL/GC/PYTHONHASHSEED 三重天花板，本轮约束4又砍掉 Rust/Go 退路，且无'基准达不到'; 收缩砍了基础设施复杂度但未重新排序创作平台复杂度——4层DSL/Agent编排/6维评估/CPK+provenance/ThemeRegistry/沙箱+配额/审核pipeline/创作者经济仍是并行范围，这些平台特性远超'单机1000+1

## 二、3 个开放问题交叉质证

### Q1 题材包/模块包热插拔：三层边界（核心引擎/题材包/UGC）、热插拔机制、受信任开发者扩展模型、与 ThemeRegistry 关系、对武侠玩法深度影响。
- **收敛建议**: 有条件采纳三层边界，砍运行时热插拔。

决策：6 位专家全部“有条件采纳”，共识远大于分歧。本轮只做三层边界的文档化 + 启动时静态加载，运行时热插拔/冷插拔/版本协商/沙箱隔离全部砍掉，等第二个题材真实存在且需不停服切换时再议（YAGNI，6 专家一致）。

关键设计：
1. 三层边界（文档化 + 最小实现）：核心引擎（题材无关骨架：ECS+tick+CombatKernel+DSL 编译器+沙箱，不可插拔）/ 题材包（schema family+谓词/动词词汇表+themed 治理策略+SkillBehavior 带代码资产，受信任开发者，进程级无沙箱 Python）/ UGC（data-only：层0 YAML+层1 规则+层2 对话树，沙箱受限）。
2. 三层粒度采纳 UGC 专家划分（human.c 19 门派硬编码实证支持）：Theme（词汇表+themed 治理策略）> Module Pack（门派/区域 CPK，受信任开发者）> UGC CPK（创作者内容）。门派是 wuxia 题材下的内容包不是独立题材。
3. 门派灵魂归属武侠题材包资产（MUD 专家），非核心引擎硬...
- **最强反论**: 最强反论来自 UGC 平台专家与制作人的对冲。UGC 专家主张三层边界必须 Day1 内建而非后置，并以源码实证支撑：adm/daemons/race/human.c 第 92-185 行对武当/全真/峨嵋/少林/大理段家/雪山/血刀门/丐帮/华山/桃花岛/古墓派等 19 门派做硬编码 if-else 加成——这正是“没有抽象层”的现实后果，证明核心引擎已深度硬编码武侠语义；若不早期确立题材包边界，迁移会继续把武侠烙印焊死进核心引擎，未来第二题材到来时须重铺核心而非换题材包，“砍掉会怎样：多题材退化为硬编码 if-else，UGC 平台扩展性归零”。制作人则从相反方向给出更深的反论：真正的风险...
- **未消分歧**: 三处分歧未消除：(1) 热插拔降级程度——架构师/引擎专家/制作人主张纯静态加载（load-time registration，ThemeRegistry=Python dict），UGC 专家主张“安全窗口冷插拔”（mark-for-removal->迁移活跃实体->确认无悬挂引用->注销），DSL 专家主张“MVP 只支持热加载与停服卸载”。收敛方向：取最简（静态加载），冷插拔/热加载均后置。(2) 三层粒度命名——UGC 专家提出 Theme > Module Pack > UGC CPK 三层（实证 human.c 19 门派硬编码证明门派是 wuxia 下内容包不是独立题材），其余专...

### Q2 自定义规则引擎统一 condition-action：是否引入自定义规则引擎，统一管理 condition-action 对，UGC 创作者的触发器也落到这一层？涉及与 DSL 层1 关系、与 Command/themed 治理关系、UGC 触发器落入、1000 在线性能、是否过度设计。
- **收敛建议**: 决策：否决独立自定义规则引擎（6/6 共识，源码验证支撑）。但这不等于"不做 condition-action 统一处理"——Q2 的核心诉求（统一 condition-action）部分成立，只是载体不是独立引擎，而是层1 IR + 薄求值器 + System 三分。

关键设计：
1. 规则表示层 = DSL 层1（condition->action 编译为 JSON IR），唯一规则表示层，只覆盖事件触发器（init/valid_leave/accept_object/add_action/chat_msg）。UGC 触发器只能声明式层1，从题材包注册表查询受限谓词/动词，不能注册新词。
2. 求值器 = 层1 的薄求值子模块（命名 RuleEvaluator 或 dispatch table，非独立"引擎"组件）：事件触发即时求值（非前向链），dirty-flag 缓存，主题注册动词派发。这是专家5 与专家2 描述的同一物，收敛为"层1 的求值子模块，不命名为引擎、不建框架"。
3. 调度语义四分（专家5 核心，源码验证）：事件触发器=层1 求值；call_out=进程内 Ac...
- **最强反论**: 规则引擎的核心价值场景是"让非开发者编写大量同类规则而不碰代码"——这正是 UGC 平台的长期愿景。若规则散落在"DSL 层1 声明式 + Python 策略对象硬编码"两处，会产生四类真实代价：(1) 交互边界语义不清——当一条 UGC 层1 规则与一个 Python PunishmentPolicy 在同一事件上都想 act 时，跨层优先级无法统一表达；(2) 审计轨迹割裂——规则命中记录分散在层1 求值器日志与 System 日志两套流中，无法回溯一次状态变更的完整规则链路；(3) 层1 表达力不足时的中间地带被反复试探——扩充层1 原语（专家1/6 倾向）会蠕变成事实上的规则引擎，下沉...
- **未消分歧**: 6 位专家一致否决"独立规则引擎组件"，无根本分歧。但收敛前有 4 处细节分歧需明确裁决：

1. 层1 表达力不足时的去向：专家1/6 倾向"扩充层1 原语"（专家6 附 30 文件校准实验的可测量方法），专家5 倾向"走层3 逃生舱"且明确禁止中间层。二者不矛盾（扩层1 + 层3 兜底可并存），但"何时扩层1、何时下沉层3"的判定标准未定，存在层1 原语无界膨胀蠕变成事实规则引擎的风险。
2. 薄求值器的命名与组件边界：专家5 称之为"薄 RuleEvaluator 函数"，专家2 称"无独立引擎组件，就是固定 dispatch table"。二者是同一物的不同描述，但"命名为 RuleE...

### Q3 玩家行为->世界状态是否统一封装为 Command 模式？包括：与命令管线中间件关系、Command 职责边界、与 ECS/规则引擎关系、LPC 保真、是否所有操作（含 NPC/系统 tick）走 Command。
- **收敛建议**: 有条件采纳：Command 模式仅覆盖玩家/管理员外部意图，System.update 覆盖 tick 派生变更。6/6 专家一致有条件采纳，边界高度一致。\n\n关键设计：\n(1) Command = 8 段中间件管线信封的形式化命名 {verb, args, ActionContext(actor, source, capability_token, seq), result, effects}，不另起类层级——它就是现有 ResolvedAction+ActionContext+ActionResult 的命名（采纳 Expert 5 的反冗余立场）。管线 8 段（解码->限流->历史->别名->路由->授权->执行->审计）即 Command 的生命周期。路由段保真 command_hook 四分支（exits 回退->verb 路由->emote->channel，feature/command.c:50-64 已验证）。\n(2) 玩家/管理员输入 -> Command 经完整 8 段管线。ActionContext+CapabilityToken 替换 previous...
- **最强反论**: "Command 仅覆盖外部意图、System tick 不走 Command"的干净边界是理想化，LPC 自身并不遵守它。force_me（feature/command.c:89-95）允许任何 ROOT_UID 对象调用完整命令路径（process_input -> command_hook）——即系统 daemon 与可信对象在 LPC 中本就混合了"仿真"与"命令"。代码验证 4 个真实调用点：updated.c:177 强制传闻广播（系统发起）、cost.c:18 巫师工具、to.c:20-21 语音重定向。若新架构把 force_me 映射为 Command（Privileged...
- **未消分歧**: 三处未消除分歧：(1) force_me/特权调用归属：Expert 5 提 PrivilegedAction API（Command 变体）保持 LPC 保真但使"仅外部意图"边界泄漏；其余专家未深入处理。代码验证 force_me 仅 4 调用点（updated.c 传闻/cost.c 巫师/to.c 语音×2），低频但真实存在，且 NPC AI 未用它做战斗/移动（走 heart_beat/do_attack），故泄漏面可控但需显式审计约束。(2) System 路径是否携带 ActionContext：Expert 5 主张 NPC/tick"携带 ActionContext 但无解码...

## 三、主持人收敛裁决

### 3 个开放问题决策

**Q1 题材包/模块包热插拔：三层边界、热插拔机制、受信任开发者扩展模型、与 ThemeRegistry 关系、对武侠玩法深度影响。**

- **决策**: 有条件采纳：保留三层边界（文档化+最小静态实现），砍运行时热插拔。
- **依据**: 三层边界（核心引擎/题材包/UGC）是 UGC 平台天然结构且 greenfield 下应 Day1 文档化，但运行时热插拔是过早抽象（当前 1 题材+1 开发者）。采纳 UGC 专家的三层粒度划分（源码实证 adm/daemons/race/human.c 第92-185 行对武当/全真/峨嵋/少林/大理段家/雪山/血刀门/丐帮/华山/桃花岛/古墓派等 19 门派硬编码 if-else 加成，证明门派是 wuxia 题材下内容包非独立题材，v2 把门派当题材会让 schema family 退化为扁平命名空间）。门派灵魂（SkillBehavior Python 策略，含隐藏大招/hit_by/auto_perform）归属武侠题材包资产，非核心引擎硬编码，非 UGC 可创作；human.c 19 门派加成迁移时须从 race/核心层剥离为题材包内容。ThemeRegistry = 启动...
- **何时重新评估**: 运行时热插拔（register/unload/version/isolation 完整机制）等第二个题材真实存在且需不停服切换时再议。届时须先预研悬挂引用问题（组件注销但实体持有引用、in-flight Effect 引用已注销 condition schema、活跃对话游标引用已卸载对话树）。CombatKernel 抽象时机张力靠阶段-1 非武侠微场景硬门禁兜底：实现从武侠 do_attack...

**Q2 自定义规则引擎统一 condition-action：与 DSL 层1 关系、与 Command/themed 治理关系、UGC 触发器落入、1000 在线性能、是否过度设计。**

- **决策**: 否决独立自定义规则引擎组件（6/6 共识，源码验证支撑）。
- **依据**: 源码实证否决：LPC 的 condition-action 实为 4 种调度语义不同的机制（事件触发器 init 1668 处/valid_leave 533 处/accept_object/add_action 1134 处，离散即时求值；call_out 694 文件/3109 处，延迟或自递归调度；condition daemon，heart_beat 周期驱动+CND_CONTINUE/CND_NO_HEAL_UP 位标志，feature/condition.c:15 注释'called by heart_beat'坐实；heart_beat 连续仿真）。一个'统一规则引擎'要么误模周期 tick（重蹈'事件驱动替代 heart_beat'覆辙），要么自己长成第二个 ECS 调度器。规则表示层=DSL 层1（condition->action 编译为 JSON IR），唯一规则表示...
- **何时重新评估**: 若未来 UGC 规模化后，'层1+Python 策略对象'两分法的统一 condition-action 诉求重新强烈（跨层优先级无法统一表达、审计轨迹割裂、层1 原语反复蠕变），再评估是否引入轻量统一求值入口--但本轮明确不建独立引擎。themed 治理运营期反作弊策略调整需改代码重启，是 fail-closed 的正确取舍，接受'反作弊迭代慢'代价，不为此引入可热改的规则配置。RETE/前向链...

**Q3 玩家行为->世界状态是否统一封装为 Command 模式：与命令管线中间件关系、Command 职责边界、与 ECS/规则引擎关系、LPC 保真、是否所有操作（含 NPC/系统 tick）走 Command。**

- **决策**: 有条件采纳：Command 仅覆盖玩家/管理员外部意图，System.update 覆盖 tick 派生变更。
- **依据**: Command = 现有 8 段中间件管线（解码->限流->历史->别名->路由->授权->执行->审计）信封的形式化命名 {verb, args, ActionContext(actor, source, capability_token, seq), result, effects}，不另起类层级（采纳 DSL 专家反冗余立场：Command 即现有 ResolvedAction+ActionContext+ActionResult 的命名，零成本形式化）。覆盖玩家/管理员外部意图输入，走完整 8 段管线；路由段保真 command_hook 四分支（exits 回退->verb 路由->emote->channel，feature/command.c:50-64 实证）。ActionContext+CapabilityToken 替换 previous_object/geteuid ...
- **何时重新评估**: 若未来 force_me 调用点增长或 NPC AI/触发器大量使用 PrivilegedAction 侵蚀'仅外部意图'边界，则重新评估是否收紧（强制走 System.update）或显式扩展边界并补审计。派生变更审计粒度逐 System 落地后，若发现关键 System 变更不可审计，再补 System 级审计轨迹。Command 全信封 GC 压力若 tick profiler 实测超预算，...

### 架构 delta（相对 v2）

- **砍(22)**: 分布式全套：分片/Louvain 社区检测/一致性哈希路由/handoff 两阶段提交/MigrationCoordinator/BoundaryRoomAge; Redis 全部依赖：session 路由表/ring buffer/限流令牌桶/placement/读穿透缓存/JobStore（单进程内全部内存化：sess; 分布式网关：SO_REUSEPORT 多 worker/会话粘附路由表/NATS 跨节点扇出；收敛为单进程 WS 服务器; 运维重型件：K8s/Helm/ArgoCD/OpenSearch/ClickHouse/KEDA；仅保留 OpenTelemetry+Grafana+Langf; EntityAddr `world://<shard>/<region>/<room>#<uuid>` URL 寻址（单机无 shard/region，直接用 ; uvloop 硬依赖（降级为可选依赖，默认 stdlib asyncio，按阶段0 基准决定是否启用）; JWT RS256 非对称签名+refresh token+Redis 黑名单吊销（单进程用 HS256 或纯内存 session token+内存吊销集合；a; 题材包运行时热插拔机制（register/unload/version/isolation 完整插件系统）
...
- **留(24)**: 自研 SparseSet ECS 单存储（不用 Archetype）；架构选择非性能优化（Python dict+dataclass 无 cache local; 战斗七步管线+CombatContext 快照+seeded RNG+管线副作用账本（按文本与状态交织真实顺序记录，非'先算后 apply'）；全仿真确定性的 ; resolve_attack 纯函数提取+combat-sim 调同一纯函数（非独立简化模型）；combat 确定性回放唯一必需范围; 命令中间件管线（解码->限流->历史->别名->路由->授权->执行->审计）+ActionContext+CapabilityToken+fail-close; 存储策略模式接口（StorageBackend 抽象）--但须设计为'持久化边界'抽象（persist=崩溃恢复级耐久）非'权威写'语义; PYTHONHASHSEED=0+禁 set 直接迭代+序列化 key 排序（即使只做 combat 确定性也必需，do_attack 29 处 random(; heart_beat 1s tick+非均匀/分级 tick 桶（仅活跃实体 tick）；LPC 固有不可被事件驱动替代，层1 只覆盖触发器; 技能三层（SkillData YAML/SkillBehavior Python 策略/SkillEffect 状态机）+UGC 只编辑层1；门派灵魂 70%+
...
- **加(20)**: tick=1s（LPC heart_beat 实证 set_heart_beat(1)）+ compute<100ms（10%）+ 硬告警 200ms + I/; 阶段0 micro-benchmark 为 go/no-go 硬门禁：单 do_attack μs 基准 + 1000 实体 tick 预算 + 1000在线+; JSON 存档崩溃安全规范：write-temp + os.replace/os.rename 原子写（POSIX 同文件系统原子）+ 序列化 offload ; StorageBackend 策略接口重设计为'持久化边界'抽象：persist(entity_id,state) 契约='达到崩溃恢复级耐久'，JSON 实现; 崩溃重连语义规范：进程崩溃=冷重启（从最近 JSON checkpoint 加载世界）+ 客户端连接拒绝/重试 + 重启后重新认证 + 服务端发全量 snaps; 权限策略规范：启动时加载的可信配置/代码（非可变存档），进程内求值，永远可用（进程在则策略在）；fail-closed 重定义为'策略加载失败则拒绝启动'非'运; entity_id: UUID（64位整数或 UUID4）+ 进程内对象引用/SparseSet 查询；world:// URL 格式仅作文档中分布式阶段'未来; 战斗副作用账本按文本与状态交织真实顺序记录（hit_ob/weapon->hit_ob 返回 polymorphic string/int/mapping 可同
...

### kill_criteria (9)

- 阶段-1：DSL+Agent 创作闭环验证失败（垂直切片无法用 DSL+Agent 完成 5-10 房间+2NPC+1 战斗+1 任务+1 对话且行为等价）-> 停项，不投入引擎重构
- 阶段-1：非武侠微场景无法验证 CombatKernel 内核主题无关性（核心引擎硬编码武侠语义无法剥离）-> 暂停，先做内核主题无关性重构再继续
- 阶段0：micro-benchmark 单 do_attack 超阈值 -> 先优化热路径（对象池/避免分配/缓存）；1000 实体 tick 超预算 -> 降 tick 频率或裁剪 System；1000+100 经优化仍不达标且无 Rust 退路 -> 降级目标到 500 在线+50 并发（仍是当前 10 倍）并重新评估 Rust/Go 热路径
- 阶段0：30 文件表达力校准实验显示层3 逃生舱使用率经原语扩充后仍 >15% -> 暂停 Agent 投入，先扩层1-2 表达力（超标触发层1-2 迭代而非放松 KPI）
- Agent 创作：单 CPK 经 3 轮生成-修订迭代后人工修订量仍 >40% -> DSL+Agent 假设走弱，先扩 DSL 层1-2 表达力再继续；扩后仍 >30% -> Agent 降级为辅助（人工为主 Agent 建议为辅）；LLM token 预算耗尽且未产出通过闭环的 CPK -> 停止 Agent 投入回退人工创作 DSL
- 阶段1：单进程核心循环集成测试无法支撑 1000+100 -> 冻结功能范围，纯做性能优化直至达标或触发目标降级
- 项目级：18 个月未达 M3（单题材可玩 demo）-> 冻结迁移，聚焦已迁移内容产品化
- JSON 存储：任何外部玩家测试开始前必须迁 PG（崩溃丢 30s 对外部玩家不可接受）--这是硬止损线非可选
- 性能后置触发：do_attack 微基准与 1000+100 负载测试双失败且 Python 优化穷尽 -> 重新评估 Rust/Go 热路径（compiled core 重新引入的唯一触发条件）
