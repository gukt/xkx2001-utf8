### 资深游戏架构师（20 年游戏服务器与引擎架构经验，主导过多个大型 MMO/MUD 类项目，对 LPC/MudOS/现代游戏引擎有深度理解，专注架构承重性、ECS/Actor 选型、分布式性能、技术债务长期代价、复用 vs 自研权衡）
裁定: risky — LPC 源码分析与 40 条修正极见功底（多经源码验证属实），但整个方案框架仍建立在「增量重构」假设上（迁移适配层/双栈/差分测试对照运行中 LPC），与用户明确的 greenfield 定位根本矛盾；同时缺标杆引擎核心能力（全仿真确定性/逻辑热重载/可视化调试/compiled core），以「够用」冒充「标杆」。

**缺口**:
- [high] Greenfield 与增量重构的根本性概念混淆：方案全文以「迁移」(migration) 为主框架，但用户明确这是 0-1 全新项目、LPC 是规格源(spec/source)不是运行系统。阶段0 整个「录制 LPC 侧命令流为 golden trace」、阶段2「逐子系统替换 LPC 行为」、02 文档第102行「迁移适配层：单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System」、§30「过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源」、§31d「双栈过渡一致性测试」、§19「修 securityd.c bug 恢复运维可用」--全部是增量重构概念。greenfield 项目不存在「适配层」「双栈」「过渡期」「逐步替换」「修旧 bug」这些概念，应改为「从规格实现」「行为等价验证」「从 spec 构建新权限模型」。这个混淆是整个方案的承重级概念缺陷。 -> 重写迁移路径章节：阶段0 改为「LPC 规格提取与验证基建」(spec extraction + equivalence verification)；删除所有「适配层」「双栈」「过渡期」概念；阶段2 改为「子系统按规格实现」而非「逐子系统替换 LPC 行为」；securityd 不修旧代码，而是从 LPC securityd.c 提取权限规格后从零实现新 PermissionService。
- [high] 缺全仿真确定性模式(full deterministic simulation)：方案只在战斗子域做了 CombatContext + seeded RNG，但没有全世界的确定性仿真。标杆游戏引擎(如 Deterministic Lockstep RTS、Photon Quantum)的核心能力是「给定相同输入序列 + 初始快照 = 完全相同的仿真结果」。MUD 虽非帧同步，但全仿真确定性是「确定性回放 / 时间旅行调试 / 反作弊 / 自动化测试生成」的共享底座。方案只在战斗层做了这个，没有扩展到 condition/heal/NPC AI/经济等所有 System。 -> 将「全仿真确定性」作为引擎一等能力：所有 System 的 RNG 走 seeded DeterministicRNG（不仅战斗）；记录所有外部输入（玩家命令、定时器触发、跨分片消息）为 input log；支持任意 tick 边界的 state snapshot + input log = 完整重放。这是标杆引擎 vs 够用引擎的分水岭。
- [high] 缺 Python 游戏逻辑的热重载(hot reload of game logic)：方案只覆盖了 DSL/CPK 内容热重载与 DamageFormulaConfig 热重载，但完全没有 Python System 代码的热重载。LPC 的 destruct()+clone()+call_other 本质是一种热重载机制，MUD 运营高度依赖「巫师在线改代码即时生效」。标杆 MUD 引擎必须支持运行时替换 System 逻辑而不重启进程、不中断在线玩家。 -> 设计 System 热重载管线：基于 importlib.reload + entity state migration（旧 System 退出前序列化所有受影响实体状态，新 System 加载后反序列化并做 schema migration）。定义「热重载安全窗口」（无进行中战斗、无跨分片 handoff）。这是 MUD 引擎 vs 普通 WebSocket 服务器的核心差异点。
- [high] 缺可视化调试工具链：方案除了 UGC 评审工作台的「场景图/对话图可视化预览」外，完全没有引擎级调试工具。标杆游戏引擎(Unity Inspector / Unreal Blueprints / Photon Quantum Explorer)都有：entity inspector(查看任意实体全部组件)、tick profiler(按 System 拆解 tick 耗时)、event flow visualizer(事件在 System 间的传播链)、combat replay viewer(战斗回放可视化)、world graph visualizer(房间拓扑/实体位置)。方案只在可观测性里提了 metrics/logs/traces，这是运维级而非开发级工具。 -> 将引擎调试工具链作为独立子系统设计，至少包含：entity inspector(WebSocket 实时查任意实体组件树)、tick profiler(per-system 耗时火焰图)、combat replay viewer(CombatContext 快照可视化回放)、world graph visualizer(room 出口图 + 实时实体分布)。这些工具同时服务于 UGC 创作者与平台开发者。
- [high] Python 性能天花板未被正面回应：方案声称标杆引擎但选 Python 纯解释器做核心仿真，且未评估 PyPy/Cython/Rust 热路径。§S 自己承认「真实单分片容量可能是 1000-2000」却仍按 2000-3000 规划。单次 do_attack 20-30 次组件查询(dict lookup)+ 29 处 random() + 伤害计算，600 并发战斗实体/tick 在纯 Python 下仅战斗就吃 300ms+，加上 NPC AI/condition/heal/network I/O，1s tick 预算紧张。标杆引擎不能回避这个问题。 -> 明确分层执行策略：Python 做编排与低频逻辑，热路径(CombatSystem/SkillSystem/TickSimulator 核心)用 Cython 或 Rust(PyO3) 实现。或至少评估 PyPy 兼容性(2-5x 加速)。在架构定型前做单次 do_attack 的 μs 级 micro-benchmark 作为容量估算输入。不引入 compiled core 则承认 Python 是原型验证语言而非标杆引擎实现语言。
- [high] 缺规格提取管线(spec extraction pipeline)：方案直接从「LPC 源码统计」跳到「Python 实现」，缺少中间的形式化规格提取层。LPC 是 spec/source，应该先提取为可验证的形式化规格(前置/后置条件、不变量、状态机、概率分布)，再据规格实现。方案的「迁移」框架跳过了这个关键步骤，导致行为等价验证缺乏可对照的规格基线。 -> 在阶段0 增加「LPC 规格提取」：对每个子系统提取形式化规格契约（do_attack 的输入输出契约、condition 的状态转移图、heal_up 的恢复公式、各门派加成的数学模型）。规格以可执行文档(hypothesis property / JSON schema)形式存储，既是实现依据也是验证基线。
- [medium] 缺多租户基础设施级隔离：方案的「多租户」仅停留在 CPK 内容包层面(配额/沙箱)，但缺基础设施级隔离：per-tenant 资源隔离(CPU/内存/DB 连接池)、per-tenant 可观测性(指标/日志按 tenant 分隔)、per-tenant 弹性(独立扩缩容)、tenant 级版本钉住。标杆 UGC 平台需要这些。 -> 设计 tenant isolation layer：每 tenant 独立 shard pool 或 cgroup 级资源隔离；可观测性按 tenant_id 标签维度；DB 层 schema-per-tenant 或 RLS 行级安全；弹性按 tenant 独立 autoscaler。
- [medium] 缺时间旅行调试(time-travel debugging)：方案有 CombatContext 战斗回放，但没有全引擎级时间旅行调试。标杆引擎(如 Replay.io / Redux DevTools 的思路)应支持「回到任意历史 tick，检查当时世界状态」。这对调试复杂状态漂移 bug 价值极高。 -> 基于全仿真确定性快照 + input log 实现时间旅行调试：定期 snapshot + input log 回放到任意 tick。前端调试器支持 timeline scrubbing。这是确定性仿真的直接收益。
- [medium] ES 讨论是假二元对立：§13 把「全量 ES」vs「不做 ES」对立。但标杆做法是按聚合特征选择性 ES：玩家成长(Progression)/经济交易/任务状态适合 ES(审计/回放/时间旅行)；战斗 vitals/位置/房间状态不适合(高频同步写)。方案的「选择性审计」方向对但深度不够：audit log 只记不重建，而 selective ES 可重建聚合状态。 -> 按聚合类型分类持久化策略：高频同步聚合(combat vitals/position)用直接状态 + 周期快照；低频高价值聚合(progression/economy/quest)用 ES 可重建；command log + snapshot 做全仿真确定性回放。
- [medium] 缺 property-based testing：方案只有「不变量回归集」(从 8400 LPC 解析基线断言)，这是 assertion-based 而非 property-based。标杆验证需要 hypothesis-style property-based testing(随机生成输入验证不变量)，尤其对战斗伤害/condition 叠加/effect stacking 等组合空间巨大的场景。 -> 引入 hypothesis(Python property-based testing 库)：对 do_attack / condition 聚合 / effect stacking 定义 property(如「任意 condition 组合下 qi 永不超 max」「任意 effect 叠加不产生负伤害」)，随机生成输入验证。与差分测试互补。
- [medium] 缺引擎开源与生态策略：方案目标是「业界标杆」但完全未提引擎本身是否开源、如何建立生态。标杆引擎(Unity/Unreal/Godot/Minetest)都有明确的引擎授权与生态策略。UGC 平台愿景天然需要引擎生态支撑。 -> 制定引擎开源策略：引擎核心(不含侠客行内容)以宽松许可开源(Apache 2.0/MIT)，建立社区与第三方扩展生态。侠客行内容与多题材世界作为内容包独立授权。开源是成为标杆的战略杠杆而非技术决策。
- [medium] Ray 作为游戏服务器 actor 运行时的适配性未被质疑：Ray 是 ML/计算分布式框架，其 actor 设计针对无状态计算负载(stateful compute in ML pipelines)，非实时游戏仿真。Ray actor 间消息延迟典型 1-10ms(序列化+跨进程)，对 1s tick 的 MUD 可接受但对亚秒级响应有压力。Ray 的 Object Store / GCS / Plasma 对游戏服务器是额外复杂度。方案「Ray 起步」是务实的，但未评估 Ray 是否是游戏服务器的正确 actor 底座。 -> 评估替代方案：(1) 阶段一完全不引入 Ray，用纯 asyncio + 普通对象，Actor 模型推迟到阶段三真正需要分布时引入；(2) 评估更轻量的 Python actor 库(如 pyactor / Thespian)或自研薄壳；(3) 若坚持 Ray，明确评估 Ray actor 间延迟对 tick 仿真的影响并做 micro-benchmark。

**遗漏步骤**:
- LPC 规格提取管线：从 8412 个 LPC 文件静态提取形式化规格(前置/后置条件、状态转移图、概率分布、数值公式、不变量)。方案直接跳到「Python 实现 + 差分测试」，缺少中间的规格提取与形式化步骤。这是 greenfield「LPC 作为 spec」的核心工序。
- 引擎性能 micro-benchmark 前置：架构定型前应先做单次 do_attack 的 μs 级基准、单 tick 在不同实体规模下的 p99、单 Player Actor 事件环延迟。方案在 §S 提到「架构定型前做单 Player Actor 事件环 p99 实测」但放在修正清单里而非路线图正式里程碑。
- Python System 热重载管线设计与实现：方案完全没有这个步骤，但它是 MUD 引擎的核心能力。需要定义 System 代码版本切换 + entity state migration 协议。
- 引擎调试工具链作为独立子系统的设计与实现：entity inspector / tick profiler / combat replay viewer / world graph visualizer / event flow tracer。方案完全缺失。
- 全仿真确定性模式的设计：DeterministicRNG 全局注入、input log 记录格式、snapshot 序列化协议、replay 引擎。方案只有战斗级 CombatContext。
- LPC 行为等价验证策略的重新定义：从「差分测试(对照运行中 LPC)」改为「spec-based equivalence verification(对照提取的规格 + 本地 MudOS oracle)」。包括 property-based testing 框架引入。
- compiled core 性能策略决策：是否引入 Cython/Rust 热路径、是否评估 PyPy、Python/C 边界协议设计。方案未涉及。
- 引擎开源策略与生态建设路线图：开源时机、许可选择、社区治理、引擎/内容分离架构、plugin API 设计。方案未涉及。
- selective event sourcing 的聚合分类决策：哪些聚合用 ES、哪些用直接状态、command log 格式、snapshot 策略。方案的「选择性审计」不够深入。
- 多租户基础设施隔离层设计：tenant 资源隔离、可观测性分隔、弹性策略、DB 隔离方案。方案只有 CPK 级配额。

**更优方案**:
- [Actor 运行时] 阶段一即引入 Ray actor 作为核心循环基础，验证 LPC↔Actor 同构 -> 阶段一用纯 asyncio + 普通实体对象（同步方法调用，与 LPC 同步语义一致），完全不引入 Ray。Ray 推迟到阶段三真正需要分布时引入，或用更轻量的方案（自研薄壳 actor 或直接 multiprocessing）（Ray 是 ML 分布式计算框架，非游戏服务器框架，其 actor 间延迟 1-10ms 对 1s tick 仿真有负担。单进程阶段根本不需要 actor。纯 Python 对象方法调用天然同步，与 LPC call_other 语义一致，避免 68771 处同步改异步的工程量与语义漂移风险）
- [ECS] 自研 SparseSet ECS（单存储，不用 Archetype） -> 用更简单的组件模型：Entity = 组件 dataclass 的聚合容器，组件按类型注册到 typed dict。不纠结 SparseSet vs Archetype。或用现有库 esper。仅当未来证明批量查询是瓶颈时再优化（MUD 8000 实体规模下 ECS 的核心优势（cache locality、批量向量化）在 Python 中不成立。SparseSet vs Archetype 的取舍在 8000 实体 + Python dict 实现下毫无性能差异。自研 ECS 是维护负担而非差异化能力）
- [行为验证] 差分测试（录制 LPC 命令流为 golden trace，Python 重放 diff） -> 三层验证：(1) 规格提取 -- 从 LPC 源码静态分析提取形式化规格（前置/后置条件、不变量、概率分布）；(2) 本地 MudOS 等价验证 -- 本地跑 MudOS 生成参考输出做 CI 级对照；(3) Property-based testing -- 用 Hypothesis 生成随机输入验证不变量（0<=qi<=eff<=max、伤害非负、exit 图可达）（greenfield 不依赖运行中的 LPC 做实时对照。规格提取从源头保证理解正确；本地 MudOS 是 spec oracle 不是生产对照；property-based testing 能发现差分测试覆盖不到的边界 case）
- [性能热路径] 纯 Python asyncio，裸 dataclass + 断言，Pydantic 仅边界校验 -> 分层执行：Python 做编排与低频逻辑；CombatSystem/SkillSystem/TickSimulator 核心热路径用 Cython 或 Rust（PyO3）实现；或评估 PyPy 部署。先做单 do_attack μs 基准再定方案（标杆性能需要 compiled core。Python 纯解释器在战斗 tick 串行场景下 2000-3000 并发是乐观估计。Cython/Rust 热路径可获 10-50x 加速，是达到标杆容量的必要条件）
- [事件溯源范围] 全系统不做 ES，仅高价值事件写 append-only audit_events 审计表 -> 按聚合特征选择性 ES：玩家成长（Progression）/经济交易/任务状态用 ES（支持回放与时间旅行）；战斗 vitals/位置/房间状态用直接状态 + 周期快照。加 command log + snapshot 支持全仿真确定性回放（全量 ES 确实不适合同步密集场景，但「全量不做 ES」是假二元对立。玩家成长与经济天然适合 ES（审计、回放、时间旅行），战斗 vitals 不适合。标杆引擎应按聚合特征选择持久化策略，而非一刀切。command log + snapshot 是确定性回放的轻量替代）
- [Redis/PG 写入顺序] 列为「二选一」开放问题，未定方案 -> 明确 cache-aside：PG 为权威，写先入 PG（事务内）再异步回填 Redis；读先 Redis（缓存命中）再 PG。写后读一致性通过本地缓存失效保证。Redis 降级时读穿透 PG（慢但正确）（标杆引擎不应在基础持久化模式上留开放问题。cache-aside 是游戏服务器成熟模式，与 52985 处同步调用的 read-after-write 语义兼容，故障窗口可明确界定（Redis 降级 = 读延迟上升，不丢数据））
- [引擎生态策略] 无开源策略，引擎与内容一体化 -> 引擎核心开源（Apache 2.0 / MIT），侠客行内容与多题材世界作为内容包独立授权。建立 plugin/extension API，开放 entity inspector / combat replay 等工具协议供社区扩展（标杆引擎靠生态护城河而非代码保密。开源吸引贡献者与内容创作者，与 UGC 愿景天然协同。引擎开源 + 内容商业化是成熟模式（参考 Minetest / Roblox））

**greenfield重审**:
- 删除「迁移适配层」(02 文档第102行)：greenfield 无需在「单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System」，直接从规格实现 Python System，不存在适配层
- 删除「双栈过渡一致性测试」(§31d)：greenfield 不存在 Telnet 适配器走 LPC message_vision 与 Web 发语义事件双路径并存的问题，直接实现语义事件渲染层，Telnet(若需要)作为纯前端输出格式之一而非「真相源」
- 删除「过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源」(§30)：greenfield 无过渡期，message_vision 的 1626 处模板从第一天起就是新引擎要实现的规格，不是「渐进替换」的对象
- 「修 securityd.c 已知 bug」改为「从 LPC securityd.c 提取权限规格后从零实现新 PermissionService」：greenfield 不修旧代码，securityd.c 是规格源不是运行系统
- 「差分测试」重定义为「行为等价验证」：LPC 是规格源不是运行中的对照系统，差分测试的「录制 LPC 侧命令流」改为「从 LPC 源码静态提取行为规格 + 本地 MudOS 实例生成参考输出」，对照对象从「运行中的生产 LPC」变为「本地 spec oracle」
- 「逐子系统迁移」改为「按规格实现子系统」：阶段2 不是「替换 LPC 行为为 Python System」，而是「按提取的规格实现 Python System」，实现顺序仍按耦合度排序但语义从「替换」变为「构建」
- s_combatd.c 不存在「废弃」概念(02 文档第189行)：greenfield 从未有过 s_combatd.c，只需从其提取阵法合击规格为新 CombatModifier 的需求来源
- 阶段0「现状基线」重新定义为「规格基线」：不再是「录制运行中 LPC 的行为基线」，而是「从 LPC 源码静态分析提取形式化规格 + 本地 MudOS 验证用例生成」
- Ray actor「验证 LPC↔Actor 同构映射」可延后：greenfield 单进程阶段用纯 Python 对象(同步方法调用)与 LPC 语义天然一致，不需要 Ray actor 来验证同构，Actor 推迟到分布式阶段
- 「call_out 迁移」改为「定时器规格实现」：3570 字符串 call_out 与 144 闭包 call_out 不是「迁移对象」而是「定时器行为的规格来源」，从规格实现 ActionScheduler/Effect 即可
- 「dbase 闭包键台账」改为「规格提取的一部分」：不是「迁移前必须建台账」而是「规格提取时识别函数值键并记录其求值语义」
- CombatContext「抽样真实战斗导出 do_attack 读取的 dbase 字段集」可简化：greenfield 可直接静态分析 do_attack 代码提取字段集，不需要从运行中的 LPC 抽样

**业界标杆评估**: 当前方案距业界标杆的差距集中在六个维度：

1. 确定性边界：只有战斗级确定性（CombatContext），缺全仿真确定性。标杆引擎应支持「任意 tick 快照 + 输入日志 = 完整重放」，这是时间旅行调试、反作弊、自动化测试的共享底座。

2. 热重载深度：只有数据热重载，缺逻辑热重载。标杆引擎应在不重启进程、不中断在线战斗的前提下替换 System 代码并做 live state migration。

3. 可视化工具链：基本空白。标杆引擎应内置 entity inspector / system trace / tick profiler / combat replay viewer / world graph visualizer，这些是开发效率与社区吸引力的核心。

4. 性能基线：Python 纯解释器无编译热路径，宣称 2000-3000 并发但无基准测试支撑。标杆引擎需要单 do_attack μs 级基准、tick 预算拆解、compiled core 方案。

5. 多租户隔离：只有 CPK 配额，缺基础设施级隔离。标杆平台需要 per-tenant 资源隔离、可观测性、弹性。

6. 生态策略：完全未提开源。标杆引擎必须开源核心，以生态护城河而非代码护城河成为标准。

真正能让它成为标杆的差异化能力不是「把 LPC 迁到 Python」（这是内容迁移），而是：(a) 全仿真确定性 + 时间旅行调试，(b) DSL-as-contract 的 Agent 协作创作闭环（这一条方案已具雏形且具原创性），(c) 热重载逻辑不停服，(d) 开源引擎生态。其中 (b) 是方案最有前景的差异化点，应作为标杆叙事的核心。

**承重论断**:
- [high] 方案的整个阶段0 与大量「迁移/适配层/双栈/过渡期」概念是增量重构框架，与 greenfield 定位根本矛盾，是承重级概念缺陷而非措辞问题（依据: 02 文档第102行明确有「迁移适配层」；00 文档阶段0 明确「录制 LPC 侧命令流为 golden trace」；§30 明确「过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源」；§31d 明确「双栈过渡一致性测试」--全部是增量概念。用户已明确「全新项目，不是增量重构，LPC 是规格源」。）
- [high] Python 纯解释器单分片 2000-3000 并发是乐观估计而非保守值，标杆引擎需要 compiled core(Rust/Cython 热路径)或至少评估 PyPy（依据: §S 自承认「真实单分片容量可能是 1000-2000」却按 2000-3000 规划。方案无 Rust/Cython/PyPy 提及(Rust 仅在 UGC WASM 语境被否决)。Python dict 查找 + 29 处 random() 的 do_attack 在 600 并发战斗下估算 300ms+/tick。）
- [medium] Ray 是 ML 分布式计算框架非游戏服务器框架，其 actor 间消息延迟(1-10ms)对 1s tick 仿真有负担，单进程阶段完全不需要 actor，应推迟到分布式阶段（依据: Ray 是 Ray Project/Anyscale 出品的 ML 分布式框架，actor 间通信经 Object Store 序列化，典型延迟 1-10ms。LPC call_other 是同步阻塞，68771 处改为 async ask 是巨大语义变更。方案自己在§13 否定 ES 时用同步调用论证，却在 Actor 选型时忽视了同样的同步语义问题。）
- [high] 标杆 MUD 引擎必须有全仿真确定性 + 逻辑热重载 + 可视化调试工具链，方案三项均缺或不完整，这是够用引擎与标杆引擎的分水岭（依据: grep 确认热重载仅出现在 Checkpoint(NPC 状态)与 DamageFormulaConfig，无 Python System 热重载。可视化调试仅有 UGC 评审工作台的场景图/对话图。grep 确认无 entity inspector / tick profiler / combat replay viewer。）
- [high] 开源引擎核心是成为业界标杆的战略必需而非可选，方案完全缺失这一维度（依据: grep 全文档无「开源」策略提及(license 仅出现在 CPK 内容的 CC-BY-SA-4.0)。标杆引擎(Unity/Godot/Minetest)均有明确开源/生态策略。UGC 平台愿景天然需要引擎生态支撑。）
- [medium] ES 的「全量做」vs「全量不做」是假二元对立，标杆做法是按聚合特征 selective ES，方案的「选择性审计」方向对但深度不够(audit log 只记不重建)（依据: §13 把「全量 ES」与「不做 ES」对立。但聚合特征不同适合不同策略：Progression/Economy/Quest 低频高价值适合 ES 可重建，CombatVitals/Position 高频同步适合直接状态。§13 的论证(52985 同步调用)只适用于高频聚合不适用于全系统。）
- [high] greenfield 下差分测试应重定义为「规格提取 + 行为等价验证」，对照对象从运行中的生产 LPC 改为本地 MudOS spec oracle + 提取的形式化规格（依据: 方案验证策略只有「差分测试(golden trace 重放)」与「不变量回归集(assertion)」。greenfield 下 LPC 是规格源，应先提取形式化规格再据规格实现，property-based testing(hypothesis 随机生成输入验证不变量)对组合空间巨大的 condition/effect 场景价值极高。）

---

### 资深游戏主策划（15年游戏设计经验，深耕武侠题材与多人交互系统，懂经典MUD文本叙事也懂现代游戏设计）
裁定: risky - 技术架构严谨且对抗修正到位，但"忠实迁移行为"与"业界标杆"之间存在未言明的根本张力：方案把 LPC 当作要 1:1 复刻的规格，却把门派特色、战斗微妙、死亡/经济/社交精妙这些"游戏设计的灵魂"当作可声明策略/可配置表达式/数据驱动技能来扁平化，源码证据表明这些灵魂 70%+ 在脚本里而非数据里；若不区分"必须忠实迁移的玩法内核"与"可现代化改进的表层"，标杆愿景会落空为"用现代技术重写了一个手感平庸的 LPC"。

**缺口**:
- [high] 战斗七步管线的'副作用时序保持'未被讨论。do_attack 在命中/未命中/招架/伤害四个分支各自直接 mutate my['jingli']/my['combat_exp']/my['potential']/your['jingli']/your['combat_exp']/your['potential']，且这些 mutate 有分支内时序依赖（未命中扣 jingli 与命中扣 jingli 是同一变量不同分支）。方案说'resolve_attack 纯函数读快照返回事件不直接 mutate'，但纯函数化要把这些副作用收集为 effect 列表再 apply，apply 顺序必须严格复刻原 mutate 时序，否则精力消耗节奏与经验获取漂移，战斗手感直接变味。combatd.c 第454-459/503-508/696-712 行可证。 -> 显式建模'管线副作用账本'：do_attack 七步每步产出一组带时序标记的 SideEffect，CombatSystem 按 step 顺序严格 apply，并将原分支内 mutate 时序固化为不变量回归断言（如'未命中扣 jingli 与命中扣 jingli 必须互斥且作用于同一变量'）。
- [high] skill_power 不是'可配置表达式'而是状态依赖的累积函数。combatd.c skill_power() 含 jingli_bonus（实时随 jingli 消耗动态变化，50+jingli/max_jingli*50 封顶150）、apply/attack、apply/defense、fight/dodge（防御方累积闪避加成 temp，每次命中重置，level*((100+fight/dodge/10)/100)）、str/dex 系数（封顶300）。方案把 skill_power 简化为'level³/3 可配置表达式'严重失真。YAML 表达式无法表达'累积态+封顶+实时动态'组合，这是战斗手感的数学骨架。 -> skill_power 建模为三段式可组合公式管线：(1) 基础幂（level³/3 可配）；(2) 状态修饰链（jingli_bonus 动态/fight/dodge 累积态/apply 修饰/busy 减半）；(3) 属性系数与封顶。fight/dodge 累积态单独建模为 CombatState 瞬态字段，不进 YAML 表达式。
- [high] 门派特色核心逻辑根本不在 mapping *action 表里。以独孤九剑 dugu-jiujian.c 为例：query_action 有玄铁重剑隐藏大招（str>=30&&int>=36&&random(skill)>80&&force>150&&neili>400&&武器特定，返回 damage:200 特殊招）；hit_by 有 4 级递进反击（连续 random，每级概率门槛递增 ap+dp->ap+2dp->ap+3dp，直接 mutate neili/jingli/busy）；valid_learn/valid_enable 有门派绑定与互斥（master_id=='feng qingyang' 且未学过12种其他剑法）。YAML skill 表只能覆盖标准 action 数组，门派灵魂全在脚本。方案'技能=行为定义非数据'与'数据驱动 mapping *action 迁移 YAML'自相矛盾。 -> 明确技能三层：SkillData（YAML action 数组）+ SkillBehavior（Python 策略对象，隐藏大招/hit_by/valid_learn/auto_perform）+ SkillEffect（Effect 组件 perform 状态机）。UGC 只编辑层1，层2 由平台级可信作者维护，坦白承认门派特色是平台资产非 UGC 可创作内容。
- [high] fight() 的 double_attack 与辟邪剑法硬编码门派特色在战斗驱动器而非技能数据。combatd.c fight() 第807/826 行硬编码：辟邪剑法（pixie-jian>=60&&性别=='无性'&&mapped=='pixie-jian'）第二次攻击、双手互搏（double_attack&&双 prepare）。这些是战斗回合驱动器的门派特例，YAML 技能表无法表达，必须进 Effect/CombatModifier 或脚本。方案未识别这类'驱动器级硬编码门派特色'。 -> 将 fight() 内的 double_attack/辟邪特例建模为 CombatModifier 钩子（技能可注册'回合后追加攻击'钩子），由 SkillBehavior 声明而非驱动器硬编码。迁移前盘点 fight() 内所有门派硬编码分支。
- [medium] NewRandom(i,20,level/5) 是自定义加权随机非 uniform random。skill2.c:166 定义，dugu-jiujian.c query_action 用 NewRandom 按等级倾向选高 lvl 招式。方案的 weighted_random 原语要精确复刻这个分布（base=20, d=level/5 的偏置函数），否则技能成长曲线漂移。方案未提 NewRandom 的精确复现要求。 -> 迁移前盘点所有 NewRandom 调用点的 (n, base, d) 参数，建立 NewRandom 参考实现并纳入差分测试断言。weighted_random DSL 原语须能表达该偏置函数，否则保留为脚本。
- [high] 死亡惩罚的反刷设计无法用'可声明策略'表达。combatd.c death_penalty：combat_exp>=10000*death_times 才累加 death_times（低经验频繁死亡不叠加惩罚档位，防新手被反复杀的怜悯设计）；killer_reward 的 free_rider 检测（杀盟主 mengzhu 标记 free_rider 防抢杀刷奖励）；killer combat_exp 在 victim 1/4~1 倍区间才扣 shen（反抢杀设计）。这些'条件性累积+特定事件检测+区间惩罚'是经年调参的反作弊，YAML 策略对象需脚本才能表达。 -> 死亡/反作弊分三类：通用参数（扣减比例）可声明配置；反作弊逻辑（free_rider/killer condition/区间惩罚）必须脚本；关系/版本逻辑（death_count 师徒版本号）建模为 ReferenceStore 关系类型+生命周期钩子。
- [high] death_count 作为师徒关系版本号这一精妙设计完全未被识别。feng.c:344 用 me->set('students/'+id, ob->query('death_count')) 把徒弟死亡次数作为师徒关系版本号，check_student:166 检测 death_count 变化则'师徒之情已尽'逐出师门。这是用死亡次数作为关系失效信号，'可声明策略'绝对无法表达，且分布式下师徒关系状态机需要专门建模。 -> 门派师徒系统建独立状态机模型：MentorshipRelation（master_id/student_id/bond_version/expiration_policy），bond_version 由可配置的'关系失效信号'（默认 death_count）驱动。UGC 可配置失效信号类型但不能改逻辑。
- [high] moneyd 全服货币紧缩模型与 children() 全库扫描是分布式硬障碍且经济规模化未讨论。moneyd.c MAX_CASHFLOW_ALLOWED=400000 全局上限，query_total_xkx_cashflow 用 children(GOLD_OB/SILVER_OB/COIN_OB) 遍历所有金钱对象实例累加。这是通缩自动调节，注释明确按 200 人调参。放大到 1 万人在线经济模型必须重新平衡，方案完全没讨论经济系统规模化重新设计与分布式下 children() 跨分片聚合问题。 -> 经济系统单独立项：分布式下用'分区货币总量+跨区贸易汇兑'替代 children() 全库扫描；按 1 万在线重新设计货币产出/回收/通胀控制；MAX_CASHFLOW_ALLOWED 重新调参。这是独立游戏设计专项非迁移子任务。
- [medium] marryd 的'延迟通知+重登校验补偿'语义在事件总线模型下可能丢失。marryd.c break_marriage 只通知在线配偶，离线配偶下次登录 validate_marriage 才发现被离婚。这是异步通知+最终一致性补偿。方案升级为关系事务原子提交是对的，但要保留'离线方延迟感知'的游戏语义（配偶不知情期间的行为合法性边界），否则改变婚姻社交的玩家心理模型。 -> 关系事务保留'单向生效+延迟通知'模式：breaker 立即生效，被 break 方延迟到下次活跃才生效，期间保留补偿校验。明确'不知情窗口'内的行为合法性边界并写入契约测试。
- [high] condition daemon 不止返回 flag 还直接 mutate victim。feature/condition.c update_condition 调用各 daemon 的 update_condition(this_object(), conditions[cnd[i]])，daemon 内部除返回 CND_CONTINUE 位标志外还直接对 victim 做副作用（中毒扣血、灼烧、冰冻、busy 计数）。方案 §12 只修正了'返回值组合结构'，但没处理'daemon 内部 mutate 的纯函数化'--72 个 daemon 的 mutate 模式各不相同，需要每个都定义 input->output 契约。 -> 72 个 condition 逐个定义 ConditionContract（input: victim 快照 + condition state -> output: 副作用列表 + 组合返回值），daemon 内部 mutate 全部收敛为输出 effect 列表由 ConditionSystem 统一 apply。这是比'返回值契约'更完整的迁移前置。

**遗漏步骤**:
- 战斗手感的'玩家感知基线'建立缺失。方案有差分测试（行为等价）但没有'手感等价'验证。MUD 战斗手感=文字输出的节奏/频率/戏剧性（combatd.c 的 guard_msg/catch_hunt_msg/winner_msg/damage_msg 多档文案池）。纯函数化+语义事件+前端渲染后，文案输出的时序与戏剧节奏可能改变。需录制玩家战斗的'文本体验流'（不仅是状态快照，含 message_vision 输出顺序与代词替换），前端渲染后做'阅读体验 diff'。
- 技能 query_action 的'隐藏大招触发条件'全量盘点缺失。dugu-jiujian 的玄铁重剑大招只是冰山一角，163 个含 *action 的技能里有多少有类似条件触发隐藏招？迁移前必须盘点所有 query_action 的非标准分支（条件触发/武器绑定/属性门槛/内力消耗），否则 YAML 化会静默丢失门派灵魂。
- perform 绝招子目录的完整迁移评估缺失。dugu-jiujian 有 9 个破式子文件（po/pojian/podao/poqiang/pobian/posuon/pozhang/poqi），每个破式是对特定武器类型的克制绝招。全库 perform 绝招子文件数量未统计。这些是 auto_perform AI 调用的核心，迁移工作量被归入'技能'但实则是独立的行为脚本集。
- 门派师徒系统的状态机建模缺失。feng.c 的 check_student/check_betrayal/revenge/improve_sword 是完整的师徒关系状态机（拜师条件13项/死亡追踪/善恶判断/技能遗忘/叛师永久标记 no_accept/指点剑法等级阶梯奖励）。19 门派各有师徒逻辑。方案提'FamilyDefinition 门派数据声明 Prefab'但没设计师徒关系状态机模型，这是门派系统的核心非数据部分。
- 经济系统规模化重新平衡专项缺失。moneyd 按 200 人调参的通缩模型（MAX_CASHFLOW_ALLOWED=400000、1/4 dummy 假设），放大到目标 1 万在线需重新设计货币产出/回收/通胀控制。这是独立于迁移的游戏设计专项，方案完全没立项。
- 文本叙事魅力的'分级文案池'迁移策略缺失。combatd.c damage_msg 按 damage_type（割伤/刺伤/劈伤/砍伤/内伤/瘀伤/跌伤/鞭伤/咬伤/抓伤/擦伤）× damage 档位（<20/<40/<80/<120/<160/>160）约 60 组文案；guard_msg/catch_hunt_human_msg/catch_hunt_beast_msg/catch_hunt_bird_msg/winner_msg/winner_animal_msg 各有叙事池；每技能 dodge_msg 叙事池（dugu-jiujian 8条）。这些文本是 MUD 文学性核心，方案提'msg_key 模板池'但没设计分级文案池 schema（damage_type×档位×代词三视角）与迁移优先级。
- Agent NPC 作为游戏内实体的设计完全缺失。方案把 Agent 定位为'离线创作工具'（生成 DSL），但完全没讨论 LLM 驱动的游戏内 NPC--能动态对话、根据玩家行为调整剧情、产生涌现叙事的 Agent NPC。这是 LPC 时代做不到、现代化能做且是真正差异化'业界标杆'能力的设计，被严重低估。

**更优方案**:
- [战斗管线副作用处理] resolve_attack 纯函数读快照返回事件不 mutate，隐含副作用收集为 effect 列表 -> 显式建模为'管线副作用账本'：do_attack 七步每步产出一组带时序标记的 SideEffect（如 step3_miss: {me.jingli -= jiajin, me.combat_exp += maybe}），CombatSystem 按 step 顺序严格 apply。保留原 do_attack 的'分支内 mutate 时序'作为不变量回归断言。（原系统战斗手感本质是'副作用时序'，纯函数化若不显式保持时序，精力消耗/经验获取会漂移，玩家会感到'新版战斗节奏不对'。）
- [skill_power 建模] skill_power level³/3 -> DamageFormula 可配置表达式（YAML） -> 建模为'三段式可组合公式管线'：(1) 基础幂（level³/3 可配）；(2) 状态修饰链（jingli_bonus 动态、fight/dodge 累积态、apply/attack、busy 减半）；(3) 属性系数与封顶（str/dex + 300 封顶）。fight/dodge 累积态单独建模为 CombatState 瞬态字段，不进 YAML 表达式。（skill_power 是战斗手感数学骨架，拆分后既能保留原系统精妙，又能让 UGC 作者配置基础幂而不破坏状态逻辑。）
- [门派特色与技能绝招] 技能=行为定义非数据 + mapping *action 迁移 YAML skill 表 -> 明确技能三层：SkillData（YAML action 数组/damage_type/lvl/force/dodge/damage）；SkillBehavior（Python 策略对象 query_action 隐藏大招/hit_by 反击/valid_learn 门派绑定/auto_perform AI）；SkillEffect（Effect 组件 perform 状态机）。UGC 只编辑层1，层2 由平台级可信作者维护。坦白承认门派特色是'平台资产'非'UGC 可创作内容'。（现状方案'技能=数据'话术与 YAML 化承诺自相矛盾，三层划分既诚实又可落地。）
- [死亡/经济/社交系统] DeathPolicy 策略对象（按题材可配），'可声明策略' -> 分三类：(1) 通用参数（combat_exp/shen/potential 扣减比例）可声明配置；(2) 反作弊逻辑（free_rider 检测/killer condition/红名/抢杀 shen 区间）必须脚本；(3) 关系/版本逻辑（death_count 师徒版本号/married_times 去重/vendetta 累积）建模为 ReferenceStore 关系类型+生命周期钩子。经济通缩模型单独立项，分布式下用'分区货币总量+跨区贸易汇兑'替代 children() 全库扫描。（三类逻辑复杂度根本不同，'可声明策略'一刀切会丢失反作弊与关系精妙。）
- [UGC 表达力范式] 逃生舱 KPI <15%，30 文件校准，'声明为主脚本为辅' -> 承认侠客行这类重战斗+重门派+重师徒 MUD 上该范式不成立。改'分层能力域'：纯数据房间/简单对话/交易用 DSL；战斗/门派/师徒/反作弊/经济调参为'平台核心域'由可信作者 Python 维护；UGC 限定'剧情/场景/简单 NPC/对话'创意域。KPI 改为'UGC 创作域覆盖率'非'逃生舱占比'。（源码证据显示层3 实际占比 40%+，强行压 15% 扭曲设计。分层能力域是业界可行路径（类似 Roblox 区分平台能力与创作者能力）。）
- [多题材策略] ThemeRegistry 多题材共享运行时，每题材注册 schema family + 谓词包 -> 立'武侠为旗舰题材深耕，其余题材为 UGC 扩展'。武侠做满深度（经脉/内力/招式/门派/师徒/仇杀/红名/经济/婚姻全套）；航海/书院/穿越/现代作为'题材皮肤+专属子系统'共享核心但各自专用子系统独立演进。不追求四题材同等深度。（深度题材需专用机制，共享运行时强行统一会平庸化。旗舰策略是业界标杆常见路径。）
- [Agent NPC 设计（新增）] Agent 仅作为离线 DSL 创作工具（五角色 Worker 生成内容） -> 立项'Agent NPC'作为游戏内实体：LLM 驱动 NPC 能动态对话（不限于 inquiry 对话树）、根据玩家行为调整剧情分支、产生涌现叙事。走与玩家相同的 ECS 实体+tick 驱动，行为由 LLM 实时生成（带缓存与一致性约束）。（离线 Agent 创作只是工具，游戏内 Agent NPC 才是玩家可感知的革命性体验，是 MUD 现代化无人做成的蓝海。）

**greenfield重审**:
- 差分测试从'在线双跑对照运行中的 LPC'重新定义为'离线 golden trace 回归'：greenfield 下 LPC 是 spec/source 不是在线服务系统，不需要双运行适配层。阶段0 差分测试简化为'录制 LPC 命令流输出 -> Python 重放 diff'离线回归，LPC 录制后可下线。文档 §31d'双栈过渡一致性测试'、子系统9'过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源'隐含长期双栈假设，greenfield 下应明确：双栈仅用于迁移期回归验证，非长期在线服务。
- 迁移适配层假设去除：子系统3'单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System'是增量重构话术。greenfield 下没有'逐步迁入的中间态'--Python 系统要么独立实现该子系统要么不存在。阶段1/2 应重新表述为'Python 系统从零实现各子系统，用 LPC golden trace 验证行为等价'，而非'LPC 跑着 Python 逐步接管'。适配层在 greenfield 下是验证工具不是运行时组件。
- '忠实迁移行为等价'与'业界标杆现代化'的根本张力必须明确边界：当前方案核心立场是'行为等价'（差分测试零差异、行为等价非位等价），但业界标杆要求超越 LPC 局限。greenfield 下应明确分层：战斗数值/门派特色/剧情/经济调参/死亡惩罚/师徒=必须忠实迁移（保真红线）；UI/并发/实时性/Agent NPC/大规模世界事件=可现代化创新（超越红线）。否则只是'用 Python 重写 LPC'非'下一代 MUD'，无标杆差异化。
- Louvain 静态分片基于现有房间图，greenfield 下 UGC 会动态新增房间改变图结构。阶段3 Louvain 分片在 greenfield UGC 平台下需直接用增量/在线社区检测（§X 修正），不能假设静态房间图。这是 greenfield UGC 平台与增量重构的根本差异--增量重构假设房间图稳定，greenfield UGC 假设房间图持续演化。
- single-shard 起步假设可更激进：greenfield 无历史用户负载，阶段1 可只做单进程核心循环验证语义正确性，不背任何分布式兼容债务（如 ActorRef 位置透明、handoff 协议）。Ray actor 原型验证可推迟到确认核心玩法迁移成功后。greenfield 下'先做对再做快'比增量重构的'边跑边改'更合适。
- provenance/CPK 在 greenfield 下可完全后置：开发期无外部 UGC 需审计，provenance 可推迟到平台对外发布前。但 greenfield 多题材意味着多套内容包并行开发，CPK 依赖图与命名空间隔离应早期建立（否则多题材资产冲突），provenance 可后置但依赖管理不可后置。

**业界标杆评估**: 当前方案是"用现代分布式技术忠实重写 LPC"的工程标杆候选，但距"游戏设计标杆"差一个维度。真正的业界标杆差异化不在"迁移得像"而在"超越原作的设计可能"：(1) Agent NPC 作为游戏内实体（LLM 驱动的动态对话/涌现叙事/玩家行为感知的剧情分支）方案完全没设计--这恰是 LPC 时代做不到、而现在能做且无人做成的 MUD 现代化核心卖点；方案把 Agent 仅当"离线创作工具"是严重低估。(2) 文本想象力是 MUD 核心竞争力（damage_msg 6 档分级文案、dodge_msg 叙事池），现代化应是"文本+情绪图标+动态立绘+实时战斗动画"协同增强叙事，而非"文本为基线图形渐进增强"的二元割裂。(3) 缺乏"玩家可感知的现代化"：AP/DP 概率模型对玩家是黑盒，标杆应是"保留 MUD 文学性 + 加即时战斗手感 + 加大规模世界事件 + 加 Agent 涌现存"四者共生。方案的 8400 文件迁移能做出"更快的 LPC"，但做不出"下一代 MUD"。要成为标杆，必须在 greenfield 边界外立项一个"LPC 做不到的设计可能"专项（Agent NPC/实时战斗手感/大规模 PvE 世界事件/玩家可即时操作的连招系统），否则只是技术现代化非游戏设计标杆。

**承重论断**:
- [high] skill_power 不是'可配置表达式'而是状态依赖的累积函数，YAML 表达式无法忠实还原战斗手感（依据: combatd.c skill_power() 第289-333 行：level³/3 仅一部分，叠加 jingli_bonus(实时动态50-150)、apply/attack、apply/defense、fight/dodge 累积态(305行 level*((100+fight/dodge/10)/100))、str/dex 系数封顶300。方案'level³/3 可配置表达式'严重简化。）
- [high] 门派特色核心逻辑在脚本不在 mapping *action 表，YAML skill 表只能覆盖约 30% 的技能行为（依据: dugu-jiujian.c query_action(玄铁重剑大招 6 条件触发)、hit_by(4级递进反击)、valid_learn/valid_enable(门派绑定+12剑法互斥)、feng.c auto_perform(按对手武器类型切换破式)。这些全在脚本，YAML skill 表只能覆盖标准 action 数组。）
- [high] 死亡惩罚/经济/社交的经年调参精妙是'条件性累积+反作弊+关系版本号'，'可声明策略'无法表达（依据: feng.c 用 death_count 作为师徒关系版本号(344/166行)、combatd.c death_penalty 的 combat_exp>=10000*death_times 条件累积(997行)、killer_reward 的 free_rider 检测(1074行)与 shen 区间惩罚(1076行)、moneyd MAX_CASHFLOW_ALLOWED 通缩模型+children()全库扫描。这些需脚本/专用状态机/关系建模。）
- [medium] UGC 逃生舱 KPI <15% 在侠客行这类重战斗重门派 MUD 上大概率一验证即崩，层3 实际占比可能 40%+（依据: 从 feng.c/dugu-jiujian.c/auto_perform/hit_by/valid_learn/death_penalty/killer_reward/moneyd 的脚本复杂度推断，30 文件校准若取代表性文件层3 实际占比大概率 >40%。weighted_random/apply_buff/monitor_cooperation 原语远不足以表达'按对手武器切换破式'策略。）
- [medium] 多题材共享运行时牺牲每个题材的机制深度，四题材同等深度不可行（依据: wuxia 经脉/内力/招式/门派/师徒/仇杀/红名/经济/婚姻 vs nautical 航向/风向/货舱 vs academy 课业/科举 vs modern 现代技能--四套机制差异巨大，通用组件 schema+题材谓词会在每套上妥协。现代游戏设计证明深度题材需专用机制引擎。）
- [high] greenfield 下差分测试是离线 golden trace 回归，'双运行适配层/Telnet 双栈过渡'假设需重新审视甚至去除（依据: 文档子系统3'单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System'、§31d'双栈过渡须一致性测试'、子系统9'过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源'均为增量重构话术。greenfield 下 LPC 是 spec/source 非在线对照系统。）

---

### 资深游戏制作人（范围管理/里程碑/团队/风险/商业化）。主导过多个大型项目立项到上线，见过太多"技术上完美但永远做不完"的项目。本次评审聚焦：路线图现实性、MVP 策略、关键路径阻塞、标杆野心与可交付性平衡、商业化与团队假设、并行/串行依赖。
裁定: risky -- 技术调研质量极高（40条承重修正多数成立且经源码验证），但作为"从0到1的项目路线图"而非"技术研究报告"存在致命的范围管理缺陷：把最高的产品风险（DSL+Agent创作闭环是否成立）放到阶段4-5最后验证，而前14+月全在验证工程可行性（能否重建引擎）。这是"技术上完美但永远做不完"的典型模式。68771调用点的全量忠实迁移在单人/小团队下是不可交付的年级债务，且其与"UGC平台"的产品目标存在结构性张力。需要把MVP从"引擎重建"重定义为"平台价值垂直切片验证"。

**缺口**:
- [high] 完全缺失'垂直切片'MVP 定义。当前阶段0-1 是横向铺开的引擎 MVP（ECS骨架+网关+状态层+go/move迁移），验证的是'能否重建引擎'，而非'核心产品价值是否成立'。核心价值主张是'DSL+Agent 让非程序员创作可玩世界'，但这个假设要到阶段4-5（14+月后）才被验证。如果DSL+Agent创作闭环在工程上或产品上不成立，前面14个月的引擎投入全部沉没。从制作人对立面看，这是把最高风险的产品假设放到最后验证，顺序完全反了。 -> 在阶段0之前插入一个2-3月的'垂直切片平台验证'里程碑：5-10房间+2NPC+1战斗+1任务+1对话，全部用DSL YAML定义并由Agent部分生成，跑在最小stub运行时+浏览器前端上，验证'DSL能否表达+Agent产出是否可用+玩家是否觉得好玩'三件事。通过后再投入引擎重构。
- [high] 团队规模与组织计划完全缺失。文档反复用'单人或小团队'措辞但从未定义规模、角色或扩张路径。git历史实测3个作者（Liming Xie/gukt/xiongmao86），近期实质单人。68771调用点+10子系统+DSL四层+Agent五角色+5题材，即便按文档自身估算的14-24月（单人），也未区分'哪些工作可外包/众包/AI辅助'与'哪些必须核心成员做'。公司探索项目角度无治理/汇报/决策权设计。 -> 明确三阶段人力模型：(1)MVP期单人+AI辅助（当前）；(2)平台验证期需补1名前端+1名LPC考古（可外包/兼职）；(3)迁移期用Agent+众包降负。标注每个里程碑的'最少人力下限'与'推荐人力'。向公司汇报需有明确的资源请求节点（如'垂直切片通过后请求2人编制'）。
- [high] 零商业化/市场/竞争分析。任务书明确提及'公司探索项目'和'商业化路径'，但5份文档无一处讨论：目标用户是谁（玩家？UGC创作者？其他MUD站长？）、商业模式（开源+托管SaaS？授权？Marketplace分成？）、竞争格局（Discord RP服、AI Dungeon、NovelAI、Evennia、兰芳MUD复兴项目等）、差异化护城河、定价飞轮。一个'野心宏大要影响整个游戏圈'的项目没有go-to-market计划，等于在真空中建造。 -> 补充独立的市场分析文档：(1)对标分析（至少覆盖Evennia/AI Dungeon/Discord文字RP/国内MUD复兴圈四类）；(2)用户画像三档（创作者/玩家/平台运营者）；(3)商业化三选项（开源引擎+托管收费/Marketplace抽成/Agent创作API按量计费）及各阶段适配；(4)明确'公司探索'的最小可行验证标准（不是技术demo，是商业假设验证）。
- [high] 差分测试的P0门禁有一个未声明的前置硬依赖：可运行的FluffOS/LPC驱动。实测当前仓库的./driver是Mach-O（macOS）二进制，目标平台是Linux（WSL2环境）。要录制golden trace必须先在Linux上重新编译FluffOS驱动并让XKX可启动运行。这个'让25年前的MudOS在现代Linux跑起来'本身可能是一个独立的数周级工程（FluffOS源码编译、依赖、编码、glibc兼容性），但它被当作'阶段0的1-2月里顺手做掉'的事，严重低估。README也承认securityd.c不完整导致巫师命令不可用，系统当前并非完整可运行状态。 -> 阶段0第一步显式加入'FluffOS Linux编译+XKX可运行性验证'前置任务，给出明确工时（保守估2-4周）。若编译受阻，备选方案是：在Mac上录制golden trace（一次性录制，不需持续运行），或降级为'单元级行为规约'（从代码人工推导期望行为写断言，不依赖运行时）。差分测试门禁不应是'运行时差分'唯一形态。
- [high] 无kill criteria/止损标准。文档有'决策检查点'但全是'继续推进'的条件，没有任何'何时停止/转向'的标准。68771调用点的全量忠实迁移是一个可能耗尽整个项目生命周期的目标。制作人视角：多年期单人项目最大的风险不是'做得不够好'而是'永远做不完'。必须定义'如果X月内未达成Y，则放弃忠实迁移目标，转向Z（如仅迁移核心玩法+原生新内容）'。 -> 为每个阶段增加kill criteria：如'阶段2若6个月内Combat迁移未通过差分测试，则放弃逐调用点忠实迁移，改为行为等价+原生新引擎内容'。设定项目级止损：'若18个月内未达成单题材可玩demo，冻结迁移，聚焦已迁移内容的产品化'。
- [medium] '忠实迁移8412文件'与'演进为多题材UGC平台'存在结构性目标冲突，文档未识别。XKX的经脉/内力/招式/门派是深度耦合的武侠特定语义。过度投入忠实迁移会产出一个为武侠MUD优化的系统，其组件schema、战斗数值曲线、状态机模型都带着武侠烙印，后续泛化到大航海/书院/穿越/现代时需要大量重构。文档的ThemeRegistry设计假设'核心主题无关'，但CombatSystem/VitalsSystem/ConditionSystem的设计都是直接从武侠do_attack反推的，并非主题无关。 -> 明确区分'武侠题材引擎'与'通用文字世界引擎'。MVP应先证明'通用引擎最小内核'（房间/移动/对话/简单交互/DSL创作）可支持任意题材，再在一个题材（武侠）上做深度。不要让武侠的do_attack七步管线成为核心引擎的承重结构--它应是'武侠战斗插件'。CombatSystem应是一个主题无关的'回合/行动调度器'，武侠七步管线是其策略实现之一。
- [medium] d/city试点规模被低估。文档称'单区域d/city约90房'，实测d/city有129个房间+185个NPC+119个对象=441个LPC文件。即便是按'房间'算也是129非90。试点工作量被低估约1.4x-5x（取决于口径），这会传导到全量估算。 -> 修正试点规模基线为'441文件/129房间'，重新评估试点工时。更重要的是，试点的目的不是'迁移多大规模'而是'校准单点迁移工时'，应在试点中精确记录每个文件/调用点的实际耗时，回归出迁移速率模型再外推全量。
- [medium] 开源/社区策略完全缺失。'业界标杆'野心的本质是影响力，影响力来自被使用和被引用。当前方案是纯内向工程文档，无开源治理（License选择/CLA/治理模型）、无社区运营（Discord/贡献指南/example worlds）、无'标杆示范'的内容输出（技术博客/会议演讲/可复现benchmark）。一个不对外发布的引擎无法成为标杆。 -> 制定开源发布路线图：M1开源确定性回放引擎（最小独立可复用组件）；M2开源DSL规范+示例世界；M3发布可自助部署的完整引擎。配套技术内容输出计划。把'外部贡献者能上手'作为架构设计的硬约束之一。

**遗漏步骤**:
- 迁移工时抽样校准实验：从68771调用点中按难度分层抽样50-100个，实测单点迁移耗时，回归出工时模型再外推全量。当前全量估算无单位工时基准，不可用于严肃的里程碑承诺。
- 市场/竞争对标分析：至少覆盖Evennia（Python MUD框架）、AI Dungeon/NovelAI（AI叙事）、Discord文字RP社区、国内MUD复兴圈四类，明确本项目在格局中的位置与差异化。
- 开源发布与社区策略文档：License、治理模型、贡献指南、example worlds、技术内容输出计划。'标杆'要求被外部感知。
- FluffOS Linux编译可行性验证：当前driver是macOS二进制，差分测试依赖可运行的LPC系统。需先验证能否在Linux构建并启动XKX，否则P0门禁阻塞。
- CombatSystem主题无关性重构：将do_attack七步武侠管线从'核心引擎承重结构'重构为'武侠战斗策略插件'，使引擎内核主题无关，支持后续4个非武侠题材。
- 垂直切片的内容设计：5-10房间+2NPC+1战斗+1任务+1对话的具体设计稿，用于阶段-1的平台验证。这不是技术任务而是内容设计任务，需要制作人/编剧视角。
- Agent产出质量的人工评估基线：在Agent创作闭环验证前，定义'可接受产出'的量化标准（如：生成的对话树逻辑自洽率>80%、生成的技能数值在合理区间内），避免'技术跑通但产出不可用'。

**更优方案**:
- [MVP 定义] 阶段0-1 的 MVP 是'单进程 asyncio 核心+ECS+网关+状态层+go/move 迁移'，是一个引擎 MVP，14+ 月才有用户反馈，且不验证核心产品价值（DSL+Agent 创作闭环） -> 新增'阶段 -1：垂直切片平台验证'（2-3 月）。5-10 房间世界、2 NPC、1 场战斗、1 个任务、1 段对话，全部用 DSL YAML 定义，其中部分由 Agent 生成，跑在最小 stub 运行时+浏览器前端上。验证：DSL 是否能表达、Agent 产出是否可接受、玩家是否觉得好玩。通过后才投入引擎重构。这是'用最小成本验证最大不确定性'。（引擎重构是确定的工程，风险已知可控；DSL+Agent 创作闭环是未验证的产品假设，风险最高。应该先验证后者再投入前者。这是'最便宜的方式学到最多的东西'。）
- [迁移与平台验证的依赖解耦] DSL→IR→运行时管线绑定在 ECS 引擎落地之后，UGC/Agent 排在阶段 4-5 -> DSL→IR→运行时管线在最小 stub 运行时上独立验证（不依赖 ECS/SparseSet/Ray）。combat-sim 已经被识别为可独立先行（用纯 Python 数值模型），但这个解耦应推广到整个创作管线：层0 YAML→IR→stub 解释器→可玩，整条链可在 2-3 月内验证。迁移内容作为数据导入，并行跑，不阻塞平台验证。（文档自己已识别 combat-sim 的循环依赖并建议独立纯 Python 模型起步，但只对 combat-sim 做了这个处理。应将同样的'用 stub 验证语义、后替换内核'策略推广到整个创作管线。）
- [差分测试策略] P0 差分测试门禁要求录制 LPC golden trace 并与 Python 重放做运行时差分。依赖一个可运行的 FluffOS，且录制是一次性的（greenfield 下不持续维护旧系统） -> 双轨制：(A) 单元级行为规约先行--从代码阅读中人工推导 go/move/combat 的输入输出契约（函数级断言），不依赖运行 LPC，2-3 周可覆盖核心路径；(B) 对可运行 FluffOS 录制一次性 golden trace 做统计回归（伤害分布/频率，非逐位对齐，文档已认可此标准）。(A) 是 greenfield 下的主门禁（快、不依赖运行时），(B) 是补充验证。两者并行，(A) 不阻塞 (B) 的录制工作。（greenfield 下 LPC 是规格不是活系统。规格级断言（函数输入输出契约）比运行时差分更稳定、更可维护、不依赖古董驱动可运行。文档已认可'遗留内容行为等价非位等价'，与单元级规约天然契合。）
- [68771 迁移工作量估算] 声称'52985 处同步调用是年级工作量'但未给出每调用点工时假设，也无抽样校准 -> 启动前做抽样校准实验：从 68771 调用点中按难度分层（机械型/理解型/设计决策型）抽取 50-100 个，实测迁移工时，回归出每层工时系数，重算总工时与人力预算。同时基于抽样判定'是否值得全量迁移'--若发现 40%+ 调用点需设计决策，可能战略转向'部分迁移+原生新内容'。（任何严肃的多年期项目都不应在不校准单位工时的情况下承诺总工期。抽样是工程管理基本功，且成本低（1-2 周）、信息量大（可能改变整个 go/no-go 决策）。）
- [标杆资产拆分] 确定性回放引擎、DSL 创作管线、Agent 协作闭环都嵌入在统一的阶段 0-5 路线图中，无独立可交付边界 -> 把两个标杆定义能力拆为独立可交付物：(1) 确定性回放引擎（CombatContext 快照+seeded RNG+回放器）作为独立开源组件，3 月内可产出，是全行业最缺的反作弊/数值审计基础设施；(2) DSL+Agent 创作闭环作为独立 demo，2-3 月可验证。两者都不依赖'68771 迁移完成'。（标杆靠'被使用和被引用'建立，不靠'代码量大'。拆出可独立交付的资产才能早获社区反馈、早建立影响力。埋在大路线图里的能力无法被外部感知。）

**greenfield重审**:
- 差分测试的'运行时差分'假设基于增量重构（双系统并行运行持续比对）。greenfield下LPC是规格不是活系统，golden trace只能一次性录制不能持续更新。应将主门禁从'运行时差分'降级为'规格级断言'（单元级输入输出契约），运行时golden trace作为补充验证。差分测试不再是'持续比对两系统'而是'一次性快照回归'。
- 文档03'存量迁移管线'第4项'保留LPC适配器桥接期'是增量重构假设的残留。greenfield没有'桥接期'--要么新系统独立可玩，要么不能玩。应删除'适配器桥接'措辞，改为'迁移期间新系统以已有迁移内容独立运行，未迁移内容以原生新内容填补'。
- 子系统3 ECS仍保留'迁移适配层：单进程asyncio actor内逐步将LPC feature行为迁入Python System'。greenfield下不存在'逐步迁入'的过渡态--这是新系统的首次实现，不是在运行中替换。'适配层'概念应清除，改为'按子系统实现，每实现一个做差分验证'。
- 阶段0的'修复securityd.c已知bug恢复运维可用'在增量重构下是为了让旧系统可运维（以便持续差分）。greenfield下旧系统是规格源不是要运维的生产系统，修复securityd的目的是'让golden trace录制可覆盖wizard操作'而非'恢复旧系统运维'。目的变了，优先级可能降低（若决定不做运行时差分则非P0）。
- 双运行（double-running）假设：greenfield下不会维持两套系统长期并行。所有'双栈过渡一致性测试'（修正§31d）应改为'一次性迁移验证'而非'长期双栈一致性维护'。过渡期应极短（单子系统迁移即验证即切换），不维持双栈。
- '迁移适配层'在子系统2/3的残留表述需清理：增量重构需要适配层让新代码调旧对象；greenfield新代码直接用新模型，旧LPC只是数据来源。凡文档中'适配器''桥接'字样应审查是否增量重构假设的残留。

**业界标杆评估**: 当前方案距"业界标杆"还差三件关键能力：(1) 一个可独立验证、可开源的"确定性回放+CombatContext 快照"引擎--这是全行业都在嘴上说但无人做实的痛点（MUD/文字游戏圈的反作弊与数值审计至今靠人工），是最低成本拿到的标杆资产，应从 ECS 骨架中剥离、作为独立可交付物优先产出；(2) "DSL 作为 AI 内容生成契约层"的核心论点极具创新性（schema 强约束把 LLM 非确定性收敛到可验证终态），但被埋在阶段 4-5、距落地 14+ 月，且从未被最小化验证过--没有这个证明，标杆无从谈起；(3) 缺失生态维度：标杆不是代码写得好，是有人用、有人跟、有人 fork。方案通篇是内向的工程文档，无开源治理、无社区、无对标分析、无分发策略。真正能让它成为标杆的差异化能力不是"忠实迁移 8412 文件"（这是考古不是产品），而是"让非程序员用 DSL+Agent 在一个下午创建一个可玩世界"并被确定性引擎保证公平--这个闭环应成为 MVP 的北极星。建议把标杆拆成三个可独立交付的里程碑：M1 确定性回放引擎开源（3 月）；M2 垂直切片证明 DSL+Agent 创作闭环（2-3 月）；M3 单题材（武侠）完整可玩 demo（6-8 月）。M3 之后才投入全量迁移与多题材。"

**承重论断**:
- [high] 当前MVP（阶段0-1）验证的是引擎可行性而非产品/市场价值。核心价值主张'DSL+Agent让非程序员创作可玩世界'要到阶段4-5（14+月后）才被验证。若该假设在工程或产品上不成立，14月引擎投入沉没。这是把最高风险放在最后验证，顺序完全反了。（依据: 文档04的MVP是ECS骨架+网关+状态层+go/move迁移，全是引擎工作；核心价值主张DSL+Agent在阶段4-5；证据：03文档的Agent协作闭环是核心创新但排最后。制作人对立面：最高风险的产品假设最后验证是顺序错误。）
- [high] 差分测试P0门禁有一个未声明的硬依赖：可运行的FluffOS。当前仓库的driver是macOS二进制，目标平台Linux需重新编译25年前的FluffOS。且README承认securityd不完整、巫师命令不可用，系统并非完整可运行。P0门禁可能被'让旧系统跑起来'阻塞数周。（依据: 实测./driver为Mach-O x86_64；当前环境Linux WSL2；README承认securityd不完整致巫师命令不可用；config.xkx的maximum users:150被login.h的MAX_USERS=50覆盖。）
- [high] 68771调用点迁移不是单一工作量类别--从机械型（10分钟）到设计决策型（1天+）跨度极大。do_attack的29处random()、query_entire_dbase活引用直改、闭包递归riposte等都需要逐个设计决策。不做抽样校准，全量估算不可靠，可能偏差一个数量级。（依据: combatd.c的do_attack（340行起）持续读写my/your=query_entire_dbase活引用11+字段；call_other模式从COMBAT_D->do_attack到this_object()->method跨度极大；文档自身修正§3指出query_entire_dbase直改破坏组件边界。）
- [medium] 忠实迁移XKX的目标与UGC多题材平台目标存在结构性冲突。CombatSystem/Vitals/Condition的设计直接从武侠do_attack反推，带着经脉/内力/招式烙印。过度投入武侠忠实迁移会产出难以泛化到5题材的系统。（依据: 02文档CombatSystem直接映射do_attack七步管线；03文档ThemeRegistry声称'核心主题无关'但核心战斗系统是武侠管线反推；do_attack的AP/DP/PP概率模型是武侠战斗特有。）
- [high] '业界标杆'的差异化能力是DSL-as-contract-for-AI-content-generation与确定性回放引擎，而非迁移保真度。这两个能力应成为MVP的核心，而非阶段5的附加。当前把它们放在最后等于把标杆资产放在最晚交付。（依据: 03文档明确'核心创新：以DSL为契约把LLM非确定性收敛到可验证终态'；但该闭环排阶段5；确定性回放嵌入阶段2.4；无开源/社区/分发策略文档。）
- [medium] 团队规模假设不成立。文档估算的14-24月（单人）基于68771调用点的乐观线性外推，未考虑单人项目的认知负荷、上下文切换损耗、休假/生病/倦怠因子。实际交付期可能是估算的2-3倍。（依据: git历史3作者近期实质单人；文档04估算单人14-24月但未区分机械/理解/设计工时；文档自身多次承认'git历史显示实质单人重构'（修正§T4）。）

---

### MUD/LPC 历史与社区专家（研究中文 MUD 文化 20 年，深度理解侠客行在中国 MUD 史的地位、文本美学、wizard 传统、玩家社交生态；担忧现代化丢失 MUD 的"灵魂"）
裁定: risky -- 技术架构现代化（ECS/Actor/DSL）扎实且经对抗验证修正后工程上可行，但在文化保真维度存在系统性盲区：把 MUD 当"技术系统"迁移而非"文化现象"延续，多个承载社区记忆与文本美学的"灵魂系统"要么被简化（代词 10 变量降 4、emote 7 视角降 3、天雷降为限流）、要么完全缺席（阴间/武林大会/vote 自治/法院审判/intermud 跨服），且 greenfield 框架下残留了增量重构假设（差分测试录制源、双栈过渡）。距"业界标杆"差的是文化保真策略，不是技术选型。

**缺口**:
- [high] 代词体系实测是 10 个变量（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s）而非方案反复声称的 4 个（$N/$n/$P/$p）。其中 $C/$c 是尊称、$R/$r 是尊称/贱称、$S/$s 是自称/贱称自称，全部由 RANK_D 的 7 个 query_ 函数动态求值。query_respect 依赖年龄（含容颜术减龄）、性别、职业（bonze/taoist/lama/fighter/eunach/officer）、官职（dali/rank 1-5）、武功等级（pixie-jian>160=督公）、善恶值、鬼魂状态。这不是纯渲染函数，是业务逻辑求值。方案'代词替换纯函数下移前端'的承重论断（00 总纲 §4.8、02 子系统9）在代词维度上不成立。 -> 服务端必须为每个事件的 me/you 预先求值 RANK_D 7 函数，产出结构化 PronounContext{name, pronoun, respect, rude, self, self_rude, close, self_close} 作为事件 payload 下发，前端只做 $X 到字段的纯字符串替换。RANK_D 的 7 个函数本身就是高价值迁移对象，须单独列为'称谓系统迁移'子任务，且其规则要进 ThemeRegistry（不同题材称谓不同）。
- [high] emote 系统实测是 7 视角变体（myself/others/target/myself_target/others_target/myself_self/others_self）而非方案假设的 3 视角（to_me/to_you/to_room）。例如 emote 'punish' 的 myself_self 是'$P的手背被胡子擦得酸痒'，others_target 是'$N拿起$n的手，在$p手背上连连亲吻'。7 视角覆盖了'发起者对自己''发起者对目标''旁观者看发起者对自己'等微妙叙事场景。方案 §4.8 的 render_message(template_key, actors)->{to_me,to_you,to_room} 丢了一半视角，等于阉割中文 MUD 文本表现力核心。 -> 渲染层契约扩展为 7 视角：render_emote(template, actors)->{myself, others, target, myself_target, others_target, myself_self, others_self}。message_vision 的 3 视角只是 emote 的子集。emote 数据迁移须保留全 7 字段，不可降级。
- [medium] emote 数据每条带 'updated' 作者署名字段（实测 20+ 位 wizard：fear/xbc/xuy/shan/sdong/marz/mongol/mantian/rover 等）。这是 wizard 创作文化的活化石--社区共创痕迹。方案的 provenance 体系（CPK author 字段）只考虑了 agent/人类作者，没把既有 8400 文件的 wizard 作者作为文化资产保留。UGC 平台继承了 wizard 创作传统却丢弃了其署名权。 -> 迁移时把 LPC 文件的 updated 字段、文件头注释的作者痕迹（如 //Cracked by Roath、// by Marz）作为 legacy provenance 回填到 CPK。provenance 模型支持 author.type='legacy_wizard'。这是文化保真而非技术需求。
- [high] 5 份文档对 5 个灵魂系统零提及（grep 验证）：① 阴间/轮回系统（d/death 13 房，鬼门关/地狱/死刑室，死亡 startroom 切换、clear_condition、block_cmd 屏蔽命令）；② 武林大会（d/bwdh 40+ 房，基于 localtime 墙钟触发的社区擂台竞技，sjsz 设施）；③ 玩家自治 vote 系统（cmds/std/vote + 2 子动作 chblk/unchblk，16 岁门槛、vote_suspension condition 剥权、滥用惩罚）；④ 法院审判反机器人（d/wizard/courthouse，审判官 NPC 三问极刑）；⑤ intermud 跨服网络（adm/daemons/network 41 文件，gchat/gwiz/gfinger/gtell/mail 跨 MUD 通信）。这些是 MUD 文化的骨架，不是边缘玩法。 -> 新增'灵魂系统盘点'前置环节：枚举所有 themed 社会治理/社区活动系统，逐一标注迁移方式。阴间系统是死亡流程的 themed 实现，必须作为 DeathSystem 的核心而非简化为'重生点'。武林大会是墙钟驱动的社区活动，TimeBasedEvent 系统必须覆盖。vote 自治是社区治理文化，SocialGovernance 子系统承载。intermud 需明确决策：保留联邦协议还是接受孤岛。
- [high] condition 系统的 72 个守护进程中，大量是非战斗的社会治理/生命周期状态机，方案将其统一归入 ConditionSystem（CombatSystem 同级的'玩法引擎'）是范畴错误。实测：killer（官府通缉，带 tell_object 文本'官府不再通缉你了'）、vote_suspension（剥夺投票权，'观察期已满，你又可以投票了'）、city_jail（监禁）、pregnant（怀孕）、biao/biaoju（镖师任务）、zuochan（坐禅）。这些 condition 携带社区可见的 themed 文本，是社会治理的体现，不是战斗 buff。 -> condition 拆分为三类：CombatCondition（战斗状态：中毒/流血/眩晕）、SocialCondition（治理：通缉/监禁/剥权/通缉令）、LifecycleCondition（生命周期：怀孕/坐禅/睡眠）。各自的 on_tick 文本与社区可见性不同。ConditionHandler 组合返回值契约（§12）只解决了战斗维度的位聚合，治理 condition 的'期满解除并广播'语义需单独建模。
- [high] 天雷惩罚（feature/alias.c）被 §31e 识别为'业务级反作弊子系统'，但只说'保留 themed 惩罚语义'一句话，没设计其文本美学保留机制。实测天雷有 message_vision 的文学化文本（'忽然一声惊雷在你头顶炸开，震得你两耳欲聋！一道闪电从天降下，正劈在$N身上'）、unconscious（昏迷）、last_damage_from（死因标记'被天雷劈死了'）、log_file 审计。这是'以世界观语言表达系统治理'的范式--反作弊不显示为'你被封禁'而显示为'天雷劈下'。降级为限流丢失的是社区记忆与沉浸感。 -> 天雷惩罚应作为'ThemedPunishment'范式范例：保留 message_vision 文本、unconscious/death 语义、死因标记。抽象为 PunishmentPolicy（限流阈值->themed 文本->状态效果->审计），让 UGC 作者能定义自己题材的 themed 惩罚（大航海题材=海怪袭击、书院题材=戒尺责罚）。这是 MUD 独有的'想象力治理'，是标杆差异化。
- [medium] message 系统的子类过滤（channel/outdoor/weather）和 blind condition 的随机消息丢弃是状态依赖的渲染门控，非纯前端函数。feature/message.c 实测：outdoor 子类消息只在 query('outdoors') 房间可见；blind condition 时 random(blind*2)>0 随机丢弃消息（盲人'看'不到战斗描述）；block_msg/all 临时旗标屏蔽消息类。方案把渲染当下沉前端的纯函数，但这些门控依赖游戏世界状态（当前房间是否户外、玩家是否致盲、是否屏蔽消息），前端必须有等价状态才能正确门控。 -> 渲染门控契约化：服务端在事件 payload 附 msgclass 与门控上下文（outdoors/weather/blind_level/block_classes），前端按上下文执行门控。或更激进：服务端在发送时就按接收者状态过滤（每个接收者一个事件变体），前端只渲染。blind 的随机丢弃必须在服务端用 seeded RNG 保证三端一致。
- [medium] day_phase 不只是'轻量广播服务扇出'（§40f）。natured.c 的 update_day_phase 触发 event_sunrise（自动保存所有玩家 link_ob+body 数据）和 event_common（遍历 livings() 检查位置、清理无环境对象、把无环境玩家 move 到 wumiao）。这是与持久化系统和世界一致性维护耦合的全局事件，不是纯表现层广播。时段切换消息带 ANSI 颜色与文学化文本（'东方的天空中开始出现一丝微曦'），是沉浸感核心。 -> day_phase 拆分为：世界时钟服务（墙钟驱动，全分片同步时段）+ 时段事件钩子（event_sunrise/event_common 等业务逻辑迁移为 WorldClockEvent 系统）+ 表现层广播（消息扇出）。明确 event_sunrise 的自动保存语义在新持久化模型中的等价物。时段文本进 ThemeRegistry。
- [low] wizard 文化（天后/女神/仙女/玄女等称号、updated 作者署名、法院审判 themed 反外挂）在方案中被降级为'运维侧 wizard ACL'（§19）和'简单角色门'。但 wizardp 不仅决定命令权限，还嵌入 query_rank 称号系统、courthouse 审判流程、securityd 审计。巫师身份是社区文化身份，不只是运维角色。用现代 RBAC 替代会丢失'天后/女神'这种社区记忆。 -> 分离'运维权限'与'文化身份'：运维权限用现代 RBAC（admin/operator），但 wizard 称号作为 legacy 文化称号保留进 ThemeRegistry 的 wuxia 称谓族。UGC 平台的'创作者'身份应继承 wizard 文化的仪式感（如审批通过授予 themed 称号），而非冷冰冰的 role。
- [medium] intermud 跨服网络（gchat 跨 MUD 闲聊、gwiz 跨服巫师频道、gfinger 跨服查询、跨服邮件 mail_serv/netmail）是 MUD 联邦文化的体现。新引擎作为 UGC 平台支持多题材世界，天然需要跨世界通信，却完全丢弃了 intermud 范式。这等于从'联邦公民'退化为'孤岛居民'。 -> 评估 intermud 协议现代化：新引擎的 EntityAddr（world://...）天然支持跨世界寻址。可设计 FederatedMessage 协议让不同 CPK 世界、甚至不同 MUD 实例互联。这是 UGC 平台的差异化能力（多世界联邦），不应在 0-1 就放弃。至少保留协议设计预留。

**遗漏步骤**:
- 阶段 0 之前缺失'规格源实例搭建'步骤：差分测试需录制 LPC golden trace，但 0-1 全新项目无运行中的 LPC 系统。必须显式立项搭建可运行的 MudOS + XKX 实例（含修复 GBK/Big5 编码、加载 8412 文件、能承载录制脚本），作为规格源/录制源/对照基准。这一步工作量不小（MudOS 老旧、依赖古老工具链），未列入工时估算。
- 缺失'灵魂系统盘点'环节：迁移前必须枚举所有 themed 社会治理与社区活动系统（阴间/武林大会/vote/法院/intermud/emote 7 视角/RANK_D 7 函数/day_phase 事件钩子/condition 社会治理类），逐一标注迁移方式与文本保真要求。当前迁移面统计（68771 调用点）只数了技术调用面，没数文化系统面。
- 缺失'代词与称谓系统全量迁移'子任务：RANK_D 7 函数 + emote 10 变量 7 视角 + message_vision 3 视角是一整套文本表现力基础设施，应单独列为迁移子系统，而非散落在 ConditionSystem/CombatSystem。需建'称谓规则表'（性别×职业×门派×官职×年龄段×善恶->称谓）作为可配置数据。
- 缺失'intermud 跨服协议决策点'：是保留联邦能力（作为 UGC 多世界互联基础）还是接受孤岛，是有文化后果的架构决策，需在阶段 0-1 明确。
- 缺失'condition 社会治理语义分类'：72 个 condition 须先分类（战斗/治理/生命周期），分别设计 on_tick 文本与社区可见性，而非统一套用 ConditionHandler 组合返回值。
- 缺失'墙钟世界事件全量盘点'：day_phase 的 event_sunrise/event_common/event_dawn 等不只是广播，是耦合持久化与世界一致性的全局事件，需单独迁移设计。
- 缺失'emote/social 文本资产化'步骤：8400 文件中的文学性文本（winner_msg 武侠礼仪、emote 7 视角、condition 期满文案）是文化资产，需建文本资产库与 themed 文本包机制，而非当'模板池 backlog'渐进丢弃。
- 缺失'文化保真度'验收指标：成功指标只有差分测试通过率/性能/延迟/可用性，没有'灵魂系统迁移完整率''themed 文本保留率''社区共创痕迹保留率'等文化维度指标。

**更优方案**:
- [代词渲染分层] 代词替换纯函数下移前端（§4.8/§29），假定 4 变量 $N/$n/$P/$p 是纯渲染 -> 服务端求值层 + 前端替换层分离：服务端对每条事件的 me/you 调 RANK_D 7 函数产出 PronounContext{name,pronoun,respect,rude,self,self_rude,close,self_close}，作为事件 payload 的结构化字段下发；前端只做 $X->context[X] 的机械替换。称谓规则随门派/职业/官职进 ThemeRegistry，UGC 可定义新称谓族。（证据：rankd.c 的 6 称谓函数依赖年龄/性别/职业/门派/官职/PK 记录/鬼魂状态，是不可下沉的业务规则；但 $X 替换本身是纯字符串操作可下沉。分层后两端各归其位。）
- [emote 与社交文本资产化] message_vision 1626 文件当多年 backlog 渐进替换（§30），emote 未单独建模 -> 把 emote/social 文本建成一等资产：(1) 数据模型保留 7 视角全字段；(2) updated 字段升格为 provenance 的一部分（author=wizard_id），既保留社区共创记忆又自然接入 CPK provenance 体系；(3) 代词变量扩到 10 个；(4) 提供 themed 文本包机制，不同题材注册自己的 emote 库。前端做'称谓编辑器'让 UGC 作者可视化调 RANK_D 规则。（证据：data/emoted.o 含 7 视角 + 20+ wizard 署名 + 10 代词变量。简化即丢文本表现力与社区记忆。资产化反而让 UGC 创作者能复用这套武侠文本美学。）
- [灵魂系统独立子系统] 天雷降为业务反作弊（§31e），condition 社会治理归入 ConditionSystem，阴间/bwdh/vote/法院/intermud 未出现 -> 新建'世界观治理层'子系统，归集所有 themed 治理：天雷（反作弊惩罚）、阴间（死亡流程）、法院（反机器人审判）、vote（玩家自治）、bwdh（社区竞技活动）、condition 中的 killer/city_jail/vote_suspension/pregnant。与战斗引擎平级。设计原则：系统治理行为必须用世界观语言表达文本，惩罚带 themed 文案与社区可见反馈。保留天雷的 message_vision 文本与 unconcious 语义作为'想象力治理'范式范例。（这是 MUD 区别于图形游戏的核心：治理内嵌于虚构世界。独立子系统才能保留 themed 文本美学，混入 ConditionSystem 会被当战斗 buff 平掉。）
- [intermud 联邦演进] 完全丢弃 intermud（41 网络服务文件），新引擎成孤岛 -> 评估'联邦协议'作为 UGC 平台多世界互联的差异化能力：定义跨世界通信协议（gchat/gfinger/gtell/mail 的现代等价），让不同 CPK 世界、甚至不同 MUD 实例互联。短期可降级为'未来选项'，但协议设计要预留（如 EntityAddr 已是 world:// 可扩展为 federated://）。（intermud 是 MUD 联邦文化基因。UGC 平台多题材世界天然需要互联。丢弃即放弃差异化。）
- [message 渲染门控的状态契约] 渲染下沉前端纯函数（§4.8），outdoor/weather/blind 门控未建模 -> 显式建模'渲染门控契约'：服务端在事件 payload 附 RenderGating{outdoors,weather,blind_level,block_msg_classes}，前端按门控决定可见性/变形。blind 的随机丢弃由服务端用 CombatRNG 预计算结果下发（哪些消息被丢），而非前端随机，保证三端一致与可回放。（门控是状态依赖的，非纯前端。预计算保证一致性与差分可回放。）

**greenfield重审**:
- 差分测试 golden trace 录制（阶段 0 核心安全网）假设有运行中的 LPC 系统可录制命令流。0-1 全新项目无此运行时。需显式立项搭建可运行的 MudOS + XKX 实例作为规格源（MudOS 老旧工具链依赖是实打实工作量），或改为从 LPC 源码静态抽取输入输出契约（go/move/combat/channel 的命令前置条件+状态读集+输出消息集+状态写集）作为静态 golden contract。阶段 0 当前未把'搭建规格源实例'列为前置步骤，工时估算遗漏。
- '双栈过渡一致性测试'（§31d：每条 Telnet 输出 = render(某条语义事件)）假设 LPC 运行时与 Python 运行时并存双栈。0-1 全新项目不保留 LPC 运行时，无双栈。该测试前提不成立，应改为'静态契约一致性'：从 LPC 源码静态抽取 message_vision 调用点的模板+代词+门控，与 Python 渲染层输出做字符串契约比对。
- '迁移适配层'（02 子系统3：单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System）的'逐步迁入'暗示 LPC 与 Python 并存运行。0-1 是重写不是迁移，无并存期。应去除'逐步迁入'话术，改为'按子系统重写并对照静态契约验证'。
- TelnetAdapter'过渡期兼容'（02 子系统1）假设有 LPC 端可过渡。0-1 项目无 LPC 端，Telnet 适配器是新引擎的单向输出端，非'双栈过渡缝'。应明确 Telnet 是为保留 telnet 老玩家接入能力的长期一等公民，而非'过渡期'产物，否则会低估其长期维护成本。
- '先迁移 go/move/combat/channel 四主线'（阶段 0/1）的渐进性假设有运行时对照源。0-1 项目中这四主线是'首批重写+对照静态契约验证'，不是'从 LPC 迁移'。语义偏差率度量的对照基准是静态抽取的契约，不是运行时 diff。
- Louvain 分片基于'现有 6414 房间出口图'（00 §4.2）。0-1 项目初期只重写 d/city 约 90 房（阶段 0 试点），全图分片是远期事项。但 UGC 动态加房后出口图持续变（§X 已识别），需明确'初始分片基于迁移完成的全图，后续增量分片基于 UGC 增长'，避免在 90 房试点期就预构分片框架。
- '32 守护进程全量分类表'（§G）是增量重构视角（迁移现有 daemon）。0-1 视角应改为'32 守护进程的职责重新设计'：哪些职责在新架构中被 ECS System 取代（如 natured->WorldClockSystem）、哪些保留为无状态服务（如 chinesed）、哪些演进为新能力（如 channeld->FederatedMessageService 承载 intermud）。不是 1:1 迁移而是职责重组。

**业界标杆评估**: 当前方案距业界标杆差一个完整维度：文化保真。技术架构现代化是 A 级，但对 MUD 作为"文化现象"的理解是 C 级--它把侠客行当"技术系统"拆解迁移，而非当"活的社区文化"延续。方案 5 份文档对阴间/武林大会/vote/法院/intermud 零提及，对代词体系简化为 4 变量 3 视角，对 wizard 文化降为运维 ACL，这是"技术上升级但文化上降级"的典型。真正能让它成为标杆的差异化能力是：以"世界观语言表达系统治理"为范式（天雷是 themed 反作弊、阴间是 themed 死亡惩罚、法院是 themed 反外挂、vote 是 themed 自治），加上 intermud 联邦协议演进为"可联邦的 UGC 多世界互联"。这是任何图形 MMO 都无法复制的"想象力治理元宇宙"。业界标杆应定位于"最 MUD 的现代游戏"--保留 themed 治理灵魂用现代技术放大其表现力与触达，而非"最现代的 MUD"--抽空文化灵魂换一层现代皮。两者的张力：技术现代化应服务于放大文本表现力与社区文化（如前端把 7 视角渲染做成即时切换的叙事 UI、把代词求值做成可视化称谓编辑器让 UGC 作者调），而非用工程简化抹平文化细节。标杆标准应加一条"文化保真度"：themed 系统的文本/行为/社区记忆迁移完整率，与差分测试行为保真并列为一等指标。

**承重论断**:
- [high] 代词体系实测是 10 个变量（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s），其中 6 个由 RANK_D 的 7 个动态业务函数求值（依赖年龄/性别/职业/门派/官职/武功等级/善恶/鬼魂状态），'代词替换纯函数下移前端'的承重论断不成立--rank 求值必须留服务端，前端只做 $X 到预求值字段的替换。（依据: 代码证据：adm/simul_efun/message.c + adm/daemons/emoted.c 注释列出 10 变量；adm/daemons/rankd.c 7 个 query_ 函数（query_rank/query_respect/query_rude/query_self/query_self_rude/query_close/query_self_close）每个都调用 ob->query_skill/ob->query('class')/ob->query('dali/rank')/ob->is_ghost() 等业务查询。方案 00 总纲 §4.8 与 02 子系统9 反复称'代词替换纯函数下移前端'。）
- [high] emote 系统实测是 7 视角变体（myself/others/target/myself_target/others_target/myself_self/others_self）含 wizard 作者署名（updated 字段，20+ 位 wizard），方案简化为 3 视角 4 变量会丢失一半叙事视角与全部社区共创痕迹。（依据: data/emoted.o 结构验证：每条 emote 含 7 视角键 + updated 作者字段；adm/daemons/emoted.c 注释定义 10 代词变量。方案 02 子系统9 的 render_message 契约只有 3 视角。）
- [high] 5 份架构文档完全遗漏至少 5 个灵魂系统：阴间/轮回（d/death 13 房）、武林大会（d/bwdh 40+ 房墙钟触发）、vote 玩家自治（16 岁门槛+剥权 condition）、法院审判反机器人（themed 反外挂）、intermud 跨服网络（41 网络服务文件）。这些是 MUD 文化骨架，不是边缘玩法。（依据: grep 5 份文档对 vote/courthouse/bwdh/阴间/intermud 零命中；源码验证：d/death 13 房、d/bwdh 40+ 房、cmds/std/vote + 2 子动作、d/wizard/courthouse、adm/daemons/network 41 文件。）
- [high] condition 的 72 个守护进程中大量是社会治理状态机（killer 通缉/vote_suspension 剥权/city_jail 监禁/pregnant 怀孕），携带社区可见 themed 文本，归入 ConditionSystem（战斗引擎同级）是范畴错误，应拆为 CombatCondition + SocialCondition + LifecycleCondition 三类。（依据: kungfu/condition/ 目录实测：killer.c（通缉+文本'官府不再通缉你了'）、vote_suspension.c（剥权+文本'观察期已满'）、city_jail.c、pregnant.c、biao.c。方案 02 子系统5 把 72 condition 统一归 ConditionSystem。）
- [medium] greenfield 0-1 框架下，'录制 LPC golden trace 做差分测试'（阶段 0）和'双栈过渡一致性测试'（§31d）是增量重构假设的残留：0-1 项目没有运行中的 LPC 系统可录制，也没有 LPC 运行时可双栈并存。需改为'静态契约抽取'或显式立项搭建 LPC 规格源实例。（依据: 04 迁移路径阶段 0 写'录制 LPC 命令流为 golden trace'；01 §31d 写'双栈过渡须一致性测试'；02 子系统3 写'迁移适配层逐步将 LPC feature 行为迁入 Python System'。用户已澄清是 0-1 全新项目非增量重构。）
- [medium] 业界标杆应定位于'最 MUD 的现代游戏'而非'最现代的 MUD'：前者保留 themed 治理范式（天雷是 themed 反作弊、阴间是 themed 死亡惩罚、法院是 themed 反外挂、vote 是 themed 自治）并用现代技术放大其文本表现力与触达，后者抽空文化灵魂换现代工程皮。差异化能力是 intermud 联邦 + themed 治理 + 想象力渲染，这是图形 MMO 无法复制的。（依据: 价值判断+证据支撑：themed 治理范式（天雷/阴间/法院/vote）在图形 MMO 无对标；intermud 联邦是 MUD 独有；想象力治理（盲人随机丢消息、天雷 themed 文本）无法图形化复制。方案未提出文化保真维度。）

---

### UGC 平台产品专家，深度研究 Roblox/Core/Rec Room/Fortnite Creative/Yahaha 等平台成败，专注创作者经济、内容审核、市场分发、低门槛创作工具、儿童安全与版权合规。本次从 UGC 平台繁荣度视角对侠客行现代化重构方案做对抗性复审。
裁定: risky — DSL/CPK/Agent 协作的技术架构方向正确且有深度工程思考，但作为 UGC 平台方案存在"重引擎轻平台"的结构性偏差：可视化创作工具、创作者经济、内容审核体系、市场分发、版权合规五个 UGC 平台核心能力几乎全部缺失或仅一行带过。以 Roblox 标杆衡量，本方案 UGC 维度成熟度约 35%，有成为标杆的创新点（Agent 协作+DSL 契约收敛 LLM 非确定性），但若不补齐平台侧能力，DSL 再精巧也无法繁荣创作者生态。

**缺口**:
- [high] 可视化创作工具完全缺失，这是 UGC 平台的第一护城河。Roblox Studio/Core Creator/Rec Room Maker 全部以可视化编辑器为创作入口。对抗验证在 D07 原始产出中已明确建议'提供可视化编辑器作为首选创作入口（底层生成多分层 DSL），降低作者心智负担'，但这条建议在整合到 03-DSL-UGC与Agent协作.md 时被丢弃，仅保留了'评审工作台 FastAPI+可视化预览'用于审核而非创作。四层 DSL 要求非程序员中文 MUD 爱好者同时理解 YAML 声明、when/do 事件规则表达式、Ink 的 knot/stitch/divert 语义、受限 Python——这比 Roblox 的 Lua+Studio 组合门槛高一个数量级。 -> 将可视化场景编辑器列为 UGC 阶段的首要交付物，而非'后期可选'。架构上：可视化编辑器是创作入口，四层 DSL 是其底层 IR（中间表示）而非创作者直接面对的语言。先做层 0 房间编辑器（拖拽出口连接、表单填字段、所见即所得预览），再渐进加层 1 事件规则面板、层 2 对话树可视化连线。用'可视化编辑器→DSL IR'的双向同步替代'手写 DSL→编译 IR'的单向流。
- [high] 创作者经济模型完全缺失。03 文档仅一行'市场分发与计费：后期阶段'。但 P07 原始研究有完整的'内容市场与分发（浏览/搜索/评分/安装/订阅）+版权溯源与计费（分账、DMCA 式流程）'设计，在整合时被压缩殆尽。Roblox 的 DevEx（开发者兑换）是创作者生态繁荣的核心引擎——创作者能赚到钱才会持续投入。没有创作者经济，UGC 平台只是工具不是生态。 -> 即使 MVP 不实现支付，也要从 Day 1 在 CPK manifest 设计中预留创作者经济字段（author_id/revenue_share/price/commercial_license）。阶段 4 至少交付'内容市场 MVP'：浏览+搜索+安装+评分+安装量排行。阶段 5 加分账与 DevEx 等价物。明确平台抽成比例（Roblox 约 75% 抽成过高被诟病，建议 30% 起步）。
- [high] 内容审核体系严重不足，仅 3 道审批门（门 1 创意意图/门 2 世界圣经/门 3 发布前），且门 2 后期才开。实测源码 832 个文件含杀/砍/血/死/屠等暴力描述、122 个文件含皇帝/朝廷/官府/造反/叛等政治敏感词、28 个文件含赌博机制。武侠题材的暴力描写、历史政治隐喻是 UGC 审核的重灾区。方案无自动化敏感内容检测、无年龄分级、无举报/下架/申诉流程、无版权投诉机制（DMCA 等价物）。 -> 设计分层审核 pipeline：(1) 自动化预检（敏感词+暴力分级+政治敏感检测+NLP 内容分类）作为发布前必过门；(2) 社区众审（玩家举报+投票）；(3) 人工审核工作台（审核员可视化预览+决策）；(4) 平台终审。加内容分级（全年龄/12+/16+）与举报-下架-申诉全流程。Agent 生成内容需标注'AI 辅助创作'并接受更严格审核。
- [high] 版权法律框架完全空白。侠客行本身基于金庸武侠小说（实测 71 个文件含丘处机/郭靖/黄蓉/杨过等版权角色名），少林/武当/峨眉等门派名称涉及商标与文化符号。'忠实迁移'意味着把这些版权风险原样带入新平台。provenance 链只记录 content_hash/parents/author/prompt_hash，不定义：AI 生成内容版权归谁（中国 2023 年北京互联网法院判决 AI 生成内容可受版权保护但需'独创性'）、多 CPK 组合的收益分配、衍生作品授权链、LPC 原始内容（mudchina 开源代码'仅供学习'）的版权清算。 -> 分三步：(1) 先做基础内容版权清洗——金庸衍生内容需授权或改编化（角色改名/门派虚构化），或明确标注'同人创作'非商用；(2) AI 生成内容版权政策——平台持有、作者署名权、商用需人类'独创性贡献'审查；(3) provenance 扩展为版权链，记录每一层贡献者的授权类型与分成比例。建议引入'版权待审'状态，发布前强制过版权审查门。
- [high] 内容发现与分发机制缺失。无推荐算法、无排行榜、无分类标签、无搜索、无策展。玩家如何发现好的 UGC 内容？Roblox 的算法推荐+排行榜+编辑策展是内容被看见的关键。CPK manifest 有 license/provenance/dependencies 但无 title/description/tags/screenshots/preview/trailer 等市场元数据字段。 -> CPK manifest 扩展市场元数据（title/description/tags/screenshots/preview_scene/rating_target_age）。设计三层分发：(1) 编辑策展（官方推荐+专题合集）；(2) 算法推荐（基于玩家偏好+内容标签+安装量+评分）；(3) 社交分发（好友在玩/门派推荐）。先做最简单的'安装量+评分'排行榜。
- [medium] 创作者社区与支持体系缺失。无教程、无文档、无示例库、无社区论坛、无导师制。Roblox 有数百万教程视频+官方文档+开发者论坛+Bootcamp。非程序员中文 MUD 爱好者面对四层 DSL+Agent 协作，没有学习路径设计会大量流失。表达力校准实验（30 文件）只验证 DSL 能否表达，不验证'非程序员能否学会用'。 -> 阶段 4 同步启动'创作者支持体系'：官方文档站+30 个逐步教程（从'创建第一个房间'到'编写技能招式表'）+示例 CPK 库（可直接 fork 的模板）+创作者社区（论坛/Discord 等价物）。把'30 文件人工转译'扩展为'30 个非程序员创作者上手实验'，度量学习曲线与完成率。
- [medium] UGC 内容版本兼容性管理缺失。CPK 有依赖声明（deps.yaml）与内容寻址版本，但当一个被依赖的 CPK 升级 schema 后，依赖它的下游 CPK 怎么办？无兼容性保证策略、无 schema 迁移工具、无破坏性变更通知。Roblox 用 StdLib SemVer+deprecation 周期解决此问题。 -> 明确 CPK 兼容性策略：SemVer 语义化版本+deprecation 周期（minor 兼容/major 破坏性需迁移指南）。提供 schema upcaster 链（已在 ArchiveMigrationService 提及但未用于 UGC CPK）。依赖方在 manifest 锁定版本范围，升级走 lockfile+自动迁移+回归测试。
- [medium] Agent 生成内容的质量门槛未定义。combat-sim 验证数值平衡，world-graph 验证可达性，但谁验证叙事质量/趣味性/风格一致性？五个 Worker（Worldbuilder/Narrator/Behaviorist/Balancer/Continuity）可能产出风格不统一的内容。'可验证终态'只说以 DSL 为契约收敛，但没说什么质量的 DSL 算'通过'。 -> 扩展验证维度：除 world-graph+combat-sim 外，加(1) 叙事一致性检查（Continuity 角色强化为 LLM-as-judge+规则不变量）；(2) 风格一致性检查（跨 Worker 产出做风格 embedding 相似度校验）；(3) 玩法趣味性抽样（人工或 Agent 模拟玩家试玩打分）。定义明确的'质量门槛分数'而非笼统'可验证终态'。
- [medium] 儿童安全/未成年人保护未考虑。中国《未成年人网络保护条例》2024 年生效，MUD 社区有大量青少年用户。无年龄验证、无防沉迷、无未成年人内容隔离。Roblox 因 COPPA 合规被罚数百万美元后才建立体系。 -> 设计未成年人保护子系统：年龄分级+防沉迷时长限制+未成年人不可见内容过滤+监护人机制。作为 UGC 平台的合规前置项，不可后补。

**遗漏步骤**:
- 可视化场景编辑器的设计与实现——这是 UGC 平台的核心交付物，但路线图阶段 4 完全没有此项，仅列出 DSL 各层与沙箱配额
- 创作者文档/教程/示例库建设——无计划。Roblox 有完整 Developer Hub+百万教程视频。非程序员中文 MUD 爱好者无学习路径则无法上手
- 内容审核工具链建设——自动化敏感词/暴力分级/政治敏感检测+人工审核工作台+举报/下架/申诉全流程。当前仅有'审批门'概念无工具
- 版权合规审查流程——基础内容（金庸衍生）版权清洗+AI 生成内容版权政策+版权投诉处理流程
- 市场与分发系统设计——内容市场 MVP（浏览/搜索/安装/评分/排行）与推荐算法
- 创作者经济模型设计——分账规则+DevEx 等价物+付费 CPK 机制
- UGC 内容 A/B 测试与灰度发布机制——新 CPK 上线前在镜像世界试跑+数据驱动决策是否全量分发
- 创作者协作工作流——多人编辑同一 CPK 的分支/合并/冲突解决（P07 提到 CRDT/OT 但整合时删除）
- 内容质量评分与推荐算法——玩家评分+行为信号（留存/时长/流失率）驱动推荐
- 玩家社交系统与 UGC 的关系设计——好友/组队/门派与 CPK 的联动（如门派 CPK 的成员专属内容）
- '非程序员能否学会用 DSL'的验证实验——表达力校准实验只验证'DSL 能否表达 LPC 逻辑'，未验证'非程序员能否学会创作'。需补充'创作者上手实验'
- Agent 生成内容的风格一致性保障——五角色 Worker 产出的风格统一性校验机制
- UGC 内容的热更新与在线玩家影响管理——CPK 更新时在线玩家如何平滑过渡（方案提到热重载但未覆盖 UGC 内容更新的玩家体验）

**更优方案**:
- [创作工具架构] 四层 DSL（YAML+事件规则+Ink对话树+受限Python）作为创作入口，作者需直接编写分层 DSL -> 可视化场景编辑器作为首选创作入口，底层生成多分层 DSL IR。DSL 作为'中间表示'而非'创作语言'。编辑器提供：房间拖拽布局、NPC 对话可视化连线、事件规则表单配置、技能数值面板。受限 Python 仅作为高级用户的'代码视图'。（Roblox Studio 是 Roblox 护城河。原 D07 对抗验证已建议'可视化编辑器作为首选创作入口'但被丢弃。没有可视化编辑器，四层 DSL 心智负担远超 Roblox 的 Lua+Studio 组合，非程序员中文 MUD 爱好者根本无法上手。）
- [Agent 协作模式] Orchestrator 拆解 DAG 分派给五角色 Worker 全量生成 DSL，经 MCP 验证+评审收敛 -> Agent 作为'创作副驾驶'（copilot）：人类作者在可视化编辑器中创作，Agent 实时辅助（填对话文案、建议数值平衡、生成 NPC 行为模板、检测剧情漏洞）。人类始终是创作主体，Agent 是增强而非替代。批量创作（如迁移辅助、新门派快速生成）才用全自动模式。（全自动生成模式的质量门槛（叙事趣味/风格一致性）无法自动验证，人类审阅成本高。Copilot 模式让人类保持创作控制权，降低 Agent 幻觉风险，也更符合创作者心理（'我创作的'而非'AI 替我创作的'）。）
- [内容审核] 三道审批门（门1创意意图+门3发布前），无自动化审核工具 -> 分层审核 pipeline：(1) 自动化预检（敏感词+暴力分级+政治敏感检测+版权指纹比对，发布前必过）；(2) 社区众审（类似 Roblox 的用户举报+点赞机制，高赞内容加速上架）；(3) 专家审核（人工审核高风险内容）；(4) 平台终审（终审权）。每层有明确 SLA 和申诉通道。（Roblox 审核团队数千人+AI 自动审核。武侠题材暴力+政治敏感+版权三重风险（已验证 832 文件含暴力关键词、122 文件含政治关键词、71 文件含金庸版权角色），3 道审批门完全不够。分层审核可控制成本且覆盖长尾。）
- [版权策略] provenance 链记录 content_hash/parents/author，license 字段在 manifest 中声明，'后期阶段'计费 -> 分层版权策略：(1) 平台基础内容（迁移自侠客行的官方 StdLib）需先做版权清洗——金庸小说衍生内容（71 文件含版权角色名）需授权或改编化处理，门派名称做商标排查；(2) UGC 作者自选 license（CC-BY/CC-BY-SA/付费/商用授权）；(3) AI 生成内容强制标注'AI 辅助创作'+人类负责制；(4) 建立版权投诉 DMCA 式流程。（侠客行本身基于金庸小说（已验证 NPC 名如丘处机/叶二娘），'忠实迁移'会把版权风险带入新平台。provenance 只记录来源不解决授权，需先解决基础内容版权才能安全开放 UGC。）
- [内容发现与分发] 市场分发与计费列为'后期阶段'，无任何设计 -> 从 Day 1 在 CPK manifest 中设计可发现性元数据（title/description/tags/screenshots/preview_scene/trailer），即使市场未上线也预留字段。阶段 4 先做最小市场（浏览+搜索+安装），阶段 5 加评分+推荐+合集。推荐算法从最简单的'安装量+活跃度+评分'排序起步。（内容平台的核心飞轮是：创作者获得分发→激励创作→更多内容→更多玩家。没有分发就没有创作者激励。Roblox 的成功不是 Lua 写得好，是创作者能赚钱、玩家能发现好内容。元数据后补成本极高（需回溯所有已发布 CPK）。）

**greenfield重审**:
- securityd 修复不再是 UGC 前置硬约束：greenfield 项目直接从零设计新的能力权限模型（wizard ACL+UGC 沙箱分离），不需'先修 securityd.c 拼写 bug 再开放 UGC'。文档中'先修 securityd'应改为'从零设计并实现能力权限模型'。但 securityd 的威胁模型分析（运维 ACL vs UGC 沙箱两类）仍然有价值，作为新设计的输入。
- 差分测试无需'双运行'系统：greenfield 下 LPC 是 spec/source 不是改造对象。差分测试简化为'LPC 录制 golden trace→新引擎独立重放→diff 输出'，不需要迁移适配层/双运行桥接期/LPC 适配器。D07 提到的'保留 LPC 适配器桥接期'应删除。
- 迁移适配器概念可去除：LPC→DSL 转译是'一次性规格提取'而非'长期桥接'。转译工具产出 DSL IR 后，LPC 源码归档为'规格参考'，新引擎不依赖 LPC 运行时。
- UGC 平台可 Day 1 规划而非'迁移完成后开放'：greenfield 下，迁移内容天然成为'官方 StdLib'（平台提供的标准内容包），UGC 在此基础上创作。不需等阶段 4 才设计 UGC 架构——阶段 0 就应定义 CPK 格式+manifest+依赖图，让迁移内容以 CPK 形式入库。这改变了'先迁移后 UGC'的串行假设为'迁移即建 StdLib，UGC 并行设计'。
- '忠实迁移'的边界需重新界定：greenfield 下，核心玩法行为（战斗七步/condition 状态机/技能招式）需忠实迁移（LPC 为 golden truth），但 UGC 平台的运营/审核/市场/创作者经济机制从未存在过，不需'迁移'而是'全新设计'。文档把这两类混在一起讨论，应分离'行为保真迁移'与'平台能力新建'。
- 多题材共享运行时从'迁移目标'变为'Day 1 架构决策'：greenfield 不需'先把武侠迁移好再泛化多题材'。ThemeRegistry 的 schema family 机制可从架构初始就内建，武侠只是第一个 theme pack。这简化了多题材的引入路径——不是'迁移完成后扩展'而是'架构内建多题材，武侠先行填充'。
- Agent 协作创作的'combat-sim 循环依赖'问题在 greenfield 下更纯粹：不存在'等 ECS 引擎落地'的依赖，因为 ECS 引擎就是新项目要建的东西。combat-sim 用独立纯 Python 数值模型起步仍是正确决策（解耦验证与引擎实现），但'替换为 ECS 内核'不再是'后期替换'而是'与引擎同步开发'。

**业界标杆评估**: 业界标杆对标 Roblox/Core/Rec Room，本方案 UGC 维度成熟度评估：约 35%（技术架构强，平台能力弱）。

Roblox 成功六要素对照：(1) 低门槛创作工具——Roblox Studio 可视化+Lua，本方案四层 DSL 无可视化编辑器，门槛更高；(2) 创作者经济——DevEx 分成体系，本方案完全缺失；(3) 内容审核——Roblox 千人审核团队+AI，本方案仅 3 道审批门无审核工具链；(4) 社区与分发——本方案完全缺失；(5) 安全合规——本方案沙箱配额到位但内容合规缺失；(6) 跨平台——本方案 Web 单端起步可接受。

本方案技术架构（DSL 四层编译 IR、CPK 内容寻址、能力令牌安全模型、分布式 fuel 聚合）在工程严谨度上实际超越 Roblox 早期阶段。差距全在平台侧而非引擎侧。

真正能让它成为标杆的差异化能力是"Agent 协作创作 + DSL-as-contract 收敛"——这是 Roblox/Core/Rec Room 都没有的。如果能做对，就是"MUD 现代化改造的业界标杆"。如果做不对，就只是一个技术精良但无人用的引擎。

要补齐的标杆能力（按优先级）：可视化创作工具（无此则门槛崩塌）→ Agent-as-copilot 创作体验（核心差异化）→ 分层内容审核+版权合规（合规底线）→ 创作者经济 MVP（繁荣引擎）→ 内容发现与社区（生态飞轮）。这五项中前三项是"不做必死"，后两项是"做了才繁荣"。

**承重论断**:
- [high] 四层 DSL+Agent 辅助无法将创作门槛降到非程序员中文 MUD 爱好者可上手的水准。没有可视化编辑器，DSL 本身的门槛就高于 Roblox 的 Lua+Studio 组合；Agent 辅助在降低门槛的同时增加了新负担（需理解、审阅、调试 Agent 产出），净效果可能不降反升。（依据: 03 文档仅'评审工作台可视化预览'无创作工具；D07 对抗验证已建议'可视化编辑器作为首选创作入口'但被整合丢弃；Roblox Studio/Core Creator/Rec Room Maker 全部以可视化编辑器为创作入口。四层 DSL 心智负担远超 Lua+Studio。）
- [high] provenance 溯源链能记录来源但不能支撑版权分配。多级依赖链分润是法律+技术复合难题，provenance 只提供数据不提供规则。（依据: provenance 仅记录 hash/parents/author；P07 原始研究提'付费包分账+DMCA 流程'但整合时删除；多级依赖链分润是法律+技术复合难题，Roblox 至今未完全解决。）
- [high] combat-sim+world-graph 验证只能保证 Agent 产出的'结构正确性'（数值平衡/可达性），不能保证'内容质量'（叙事趣味/风格一致性/玩法可玩性）。（依据: combat-sim 验证数值平衡，world-graph 验证可达性，均为结构性指标；叙事质量/趣味性/风格一致性需主观判断，无自动化方案；五角色 Worker 各自产出风格不统一。）
- [medium] RestrictedPython+fuel 配额不是充分的 UGC 安全边界。RestrictedPython 有长期逃逸漏洞历史（是'劝退层'非'安全边界'），fuel 配额防资源滥用但不防逻辑恶意（如设计诱导付费的赌博机制）。（依据: RestrictedPython 是 AST 过滤层非安全沙箱，历史逃逸漏洞多；fuel 配额防资源滥用不防逻辑恶意；沙箱配额在对抗验证中被列为'不可妥协硬约束'但安全模型深度不足。）
- [medium] 多题材共享运行时降低创作成本是优点，但会导致内容碎片化与社群分散。需从 Day 1 设计跨题材内容流通与统一玩家身份。（依据: ThemeRegistry schema family 机制设计合理；但多题材玩家社群天然分散（武侠/大航海/书院/现代受众重叠度低）；文档无跨题材内容流通机制设计。）
- [medium] greenfield 0-1 框架下，'先迁移完成再开放 UGC'的串行路径不是最优选择。迁移内容可 Day 1 以 CPK 形式作为官方 StdLib 入库，UGC 平台架构（CPK 格式/manifest/依赖图）从阶段 0 并行设计。（依据: greenfield 下 LPC 是 spec/source；D07 提'保留 LPC 适配器桥接期'基于增量假设；UGC 平台能力（审核/市场/经济）从未存在过是全新设计非迁移；文档'先迁移后 UGC'串行假设可重构。）

---

### 分布式系统资深专家（15年大规模分布式系统经验，精研一致性模型/分片/Actor/事件溯源/容错；见过大量"纸面分布式、落地单点"方案）
裁定: risky —— 单进程核心循环与 ECS 设计扎实、对抗验证产出质量高，但分布式层存在多个"纸面成立、落地翻车"的承重假设未验证：(1) LPC 同步 call_other 与 Ray 异步 actor 消息"不同构"，do_attack 的同步递归+random 分支在 Ray 下大概率死锁或退化为单线程；(2) handoff 的 partial-failure 是承诺非规约；(3) 热点房间聚集使"万人在线"可达成性存疑；(4) 战斗确定性对迁移内容已实质放弃。若不验证这些假设就进入阶段二，分布式层会重写。

**缺口**:
- [high] LPC 同步 call_other 与 Ray 异步 actor 消息根本不同构，'Ray 起步验证同构映射'是未经验证的承重假设。do_attack 在 combatd.c line 772/804/812/823/831 递归调用自身（riposte/double_attack/follow_up），且递归分支由 random() 决定。Ray actor 默认 FIFO 非重入，actor A 调 B、B 回调 A 会死锁；用 ray.get() 同步等待会阻塞 actor 事件循环使分布式化为零。方案只说'ActorRef.ask 带超时'，完全没论证 68771 处同步调用如何映射到异步而不破坏调用栈语义与递归回溯。这是'纸面同构、落地死锁'的典型。 -> 阶段一原型必须显式验证'同步递归调用图'在 Ray 下的可行性，而非假设成立。更可能的方向：分片内同步、分片间异步——同房间/同区域实体 colocate 到同一进程，call_other 退化为进程内同步函数调用（保持 LPC 语义），仅在跨分片边界（移动到另一区域、跨房间技能）用异步消息。Ray 仅用于无状态/可并行计算（Agent 编排、combat-sim），不做游戏实体运行时。
- [high] 跨分片 handoff 的 partial-failure 语义是承诺而非规约。文档只写'freeze->snapshot->activate->replay->deactivate，每步定义超时/补偿/最终一致目标'，但没有任何失败语义定义：(1) freeze 后 snapshot 写 Redis 失败——实体状态是否已冻结但未迁移？(2) snapshot 成功但目标分片 activate 失败（目标宕机）——源分片已冻结的实体如何恢复？(3) activate 成功但 replay 未完成——此时玩家命令路由到新分片还是旧分片？(4) snapshot 写 Redis 附 TTL——TTL 过期且激活未完成=实体永久丢失。(5) 战斗中 handoff：freeze 期间对端分片的攻击回合如何处理？对端不知道该实体已 freeze，攻击会打到冻结状态或丢失。 -> 采用两阶段提交 + outbox 模式：源分片将 handoff 作为持久化事务写入 outbox（PG），目标分片从 outbox 拉取并确认，确认后源分片才删除旧实体。handoff 期间实体对外'只读冻结'（拒绝写入命令并排队，而非静默接受）。组队 handoff 用分布式事务（全队原子迁移，部分失败回滚已迁移成员）。每一步的幂等性、重试策略、超时降级必须写成可执行的协议规约而非'目标'。
- [high] 容量模型忽略 MUD 的聚集特性，万人在线可达成性存疑。方案按单分片 2000-3000、4-5 分片规划万人。但 MUD 玩家高度聚集（主城、PK 场、热门 boss），不是均匀分布。一个主城可能聚集 3000+ 人超出单分片容量。Louvain 按'出口图社区'静态分片，不按负载分。§C 的'>30 人拆子 Coordinator'与 3000 人聚集差两个数量级。房间是单 CombatCoordinator 串行裁决，热门房间本身是单点瓶颈，分布式化无法解决——这是 MUD 固有的'单房间串行'限制。 -> 明确承认'单房间串行'是分布式无法突破的硬约束。对热点房间（主城/PK 场）设计'房间级水平扩展'：同一房间逻辑拆多个并行子世界（如 PK 场分多个战场实例），或'热门房间专用分片'（整个分片只服务一个主城）。对无法拆分的强交互房间（如 boss 战）设容量上限并做排队/分流。重新评估'万人在线'是否现实——可能需要'万人注册+千人同时在线'的务实目标。
- [high] 热路径一致性哈希去 Redis 化的边界条件未定义。一致性哈希环 shard=hash(entity_id) 解决'实体静态属于哪个分片'，但实体会迁移（handoff 后实体在新分片，hash(entity_id) 仍指向旧分片）。方案说'Redis 仅控制面做 placement 变更通告'——但这就回到'热路径仍需查 placement'：placement 缓存在分片内存，placement 变更时全集群缓存失效协议未定义。迁移期间存在两套路由（哈希 vs placement），何时用哪套、双写/双路由的窗口语义未规约。 -> 明确路由模型：一致性哈希只解析'分片的当前 owner'，placement 是 owner 的可变覆盖。placement 变更走 Gossip/订阅广播 + 版本号，各分片缓存 (entity_id -> owner_version)，路由时比较版本号决定用哈希还是 placement。定义'迁移中'窗口的统一语义：handoff 期间实体路由到一个确定的'权威分片'（旧或新二选一），不接受双写。彻底测试 placement 缓存不一致时的收敛行为。
- [high] 战斗确定性在异步调度下对迁移内容实际已放弃（§10 '遗留内容行为等价非位等价'），但方案把 CombatContext+seeded RNG 列为分布式硬约束。8400 文件迁移内容全是'遗留内容'，'新内容/UGC'才有 CombatRNG 契约——意味着迁移完成后，反作弊审计与 bug 回放对全部迁移内容失效，只有后续 UGC 有确定性。这与'业界标杆反作弊'目标直接冲突，且§9/§10 自相矛盾（§9 要求 CombatContext 快照，§10 又说遗留放弃位等价）。 -> 明确区分两个目标：(1) 迁移正确性验证用'行为等价'统计回归（合理）；(2) 运行时反作弊/回放必须对全部内容有确定性。对迁移内容，迁移时即重写为走 CombatRNG 契约（既然是 greenfield 重写，新代码本就用 seeded RNG，不存在'遗留 RNG'）。§10 的'放弃位等价'只适用于'与原 LPC 逐位对照验证'这一特定场景，不应延伸为'运行时放弃确定性'。澄清这一区分，否则反作弊基线对迁移内容是 0 覆盖。
- [medium] '看起来分布式实际单点'的隐患未充分识别：(1) CombatCoordinatorActor 同房间串行裁决，热门房间单 actor=单点；(2) channeld 全局广播，万人在线每条消息扇出 10000 次，NATS 单 broker 是吞吐单点，高活跃时（全服喊话/PK 直播）扇出风暴；(3) PlacementService 若集中式即单点，若一致性哈希又回到边界问题；(4) 跨分片战斗的 CombatContext 快照存哪？全局存储=单点，分散存储=回放需跨节点拉取；(5) 全局 RNG/seed 协调未定义——跨分片战斗用谁的 seed？ -> 对每个'看似分布式'的组件做单点审计：Coordinator 按房间分片但单房间仍是单点（需房间级水平扩展见上）；channeld 用分层扇出（分片内聚合后跨分片广播，限频+降级）；Placement 去中心化+Gossip；CombatContext 快照随战斗参与者分布存储+引用；跨分片战斗用一个协调 seed（战斗发起方分片生成，参与者分片复用）。每处明确'单点容量上限'与'降级路径'。
- [medium] Ray 的 actor 激活/钝化模型与 MUD 实体生命周期的匹配未论证。Ray actor 默认常驻或按需激活，但 MUD 实体（NPC/物品/房间）数量巨大（6414 房间+大量 NPC/物品），全部常驻内存不可行，需钝化。Ray 的 actor 钝化/重新激活会丢失内存态（enemy 列表、apply/ 修饰符栈、call_out 定时器），方案要求 Effect 可序列化随 handoff 迁移，但 Ray actor 钝化不是 handoff，是本地内存回收——钝化后的 call_out 定时器、AOI 订阅如何恢复未定义。 -> 区分'实体钝化'与'跨分片 handoff'：钝化是本地内存回收+按需重激活，handoff 是跨节点迁移。两者都需完整序列化实体状态，但钝化还需恢复定时器/订阅/活跃战斗上下文。明确钝化触发条件（idle 时长、内存压力）、钝化粒度（单实体 vs 房间整批）、重激活时的事件重放协议。Ray 的 actor 生命周期模型需包装一层 MUD 语义的钝化/激活适配。
- [medium] trace 跨分片/跨 actor 边界的传播在 Ray 下的实现未论证。§39 正确识别了 asyncio contextvars 传播问题，但 Ray actor 的 remote 调用跨进程，contextvars 不跨进程传播，需手动注入 traceparent 到消息信封。Ray 的 ObjectRef 序列化、actor 重试、placement 迁移都会断 trace。方案提到'自研 actor 信封 traceparent'但未定义 Ray 适配。 -> 若用 Ray，需实现 Ray-specific 的 trace 注入/提取中间件（在 actor method 入口/出口注入 context），处理 Ray 的 ObjectRef 引用传递与重试场景。trace 完整率指标需在 Ray 跨 actor 调用下重新校准基线。

**遗漏步骤**:
- 缺失'同步递归调用图'的分布式可行性原型验证。阶段一说'Ray actor 原型验证 LPC↔Actor 同构映射'，但只验证 go/move（无递归），没验证 do_attack 这种'同步递归+random 分支+跨实体回调'的最难场景。应优先做 do_attack 递归调用图在 Ray 下的死锁/重入测试，而非 go/move。
- 缺失热点房间的容量压测。方案的单分片容量压测是'单 Player Actor 事件环 p99'，但真实瓶颈是'单房间 N 人战斗的 Coordinator 串行延迟'。应加测：单房间 50/100/500/1000 人同时战斗时的 tick 延迟，确定单房间容量上限，这是分布式无法突破的硬约束。
- 缺失 placement 缓存一致性的混沌测试。一致性哈希+placement 覆盖的双路由模型，需在网络分区、placement 变更延迟、分片重启等场景下验证路由收敛行为。方案没有这一步。
- 缺失 channeld 全局广播的扇出压测。万人在线下全服喊话/PK 直播的扇出风暴未测试，NATS 单 broker 容量未评估。应加测：万人在线下高频频道广播的延迟与丢消息率。
- 缺失跨分片战斗的 CombatContext 快照存储与回放验证。跨分片战斗（追杀跨房间、组队跨区域 PK）的快照存哪、seed 如何协调、回放如何拉取跨分片状态，方案完全空白。
- 缺失 Ray actor 钝化/激活的完整生命周期测试。实体钝化后 call_out 定时器、AOI 订阅、活跃战斗上下文如何恢复，未验证。
- 缺失'迁移内容确定性'的明确边界定义。§9 要求 CombatContext 快照，§10 又说遗留放弃位等价——需明确：迁移后的 Python 代码是否强制走 CombatRNG？若是，则运行时有确定性（反作弊有效），只是'与原 LPC 逐位对照'用行为等价。若否，则反作弊对迁移内容失效。这一区分必须在 Combat 迁移前落定。
- 缺失'分布式 fuel 聚合器'的实现规约。§M 提到按 CPK 维度聚合跨调用 fuel，但跨分片调用（玩家在分片A触发分片B的 CPK 脚本）的 fuel 归属与聚合协议未定义，是分布式资源计费的经典难题。

**更优方案**:
- [游戏实体运行时] Ray actor 模型起步做游戏实体运行时，ActorRef.ask 映射 call_other -> 分片内同步、分片间异步：游戏分片用纯 asyncio 单进程，同分片实体间 call_other 退化为进程内同步函数调用（保持 68771 处调用栈语义），仅在跨分片边界（移动、跨房间技能）用异步消息。Ray 退到计算负载层（Agent 编排/combat-sim 批量/离线迁移工具），不做游戏实体运行时。（区域共同体分片的正确语义是'分片边界对齐到 call_other 的同步边界'，而非'每个实体一个 actor'。同房间实体本就强同步耦合，硬拆成异步 actor 既不解决单房间串行瓶颈，又引入死锁与栈深风险。Ray 的优势在无状态并行计算，游戏实体是有状态强同步递归图，错配。）
- [跨分片 handoff 规约] freeze->snapshot->activate->replay->deactivate，每步超时/补偿'承诺定义' -> 两阶段提交 + outbox 模式：源分片将 handoff 请求写入持久化 outbox（PG 事务内，与状态变更原子）；目标分片从 outbox 拉取快照并在本地重建，重建成功后写 confirmation；源分片收到 confirmation 后从 outbox 删除并 deactivate 旧实体。handoff 期间实体对外'只读冻结'（写入命令排队不拒绝，避免玩家卡死），对端分片写入走 outbox 中转不丢失。部分失败时 outbox 保留可重试，不依赖 Redis TTL。（outbox 模式是分布式迁移的成熟范式，把 handoff 的 partial-failure 显式规约成可重试的持久化操作，而非'每步补偿'的空话。组队批量 handoff 用一个 outbox 事务包裹全队，原子提交。）
- [热点房间容量] Louvain 静态分片 + >30 人拆子 Coordinator -> 房间级水平扩展：热门房间（主城/PK 场/boss）支持多实例 + 玩家分桶（按 player_id hash 分配到房间实例），实例间无共享状态（各实例独立 Coordinator），跨实例交互（如全服喊话）走广播只读扇出。配置化的'专用分片'（整个分片只服务一个主城房间实例）。（MUD 单房间串行是固有瓶颈，分布式化无法解决，只有'房间内并行'能突破。这是业界标杆 MMO 用实例化解决主城聚集的同构方案。§C 的 30 人阈值对 3000 人聚集无效，需要数量级的水平扩展而非阈值拆分。）
- [战斗确定性覆盖迁移内容] 遗留内容'行为等价'放弃位等价，反作弊基线对迁移内容失效 -> 迁移即重建 RNG 契约：迁移每个战斗相关文件时，静态抽取其 random() 调用序列与分支条件，生成该文件的 CombatRNG 调用规约，迁移后的 Python 版强制走该规约。对 do_attack 递归调用图用符号执行/约束求解推导 RNG 消耗与递归深度的关系，生成确定性边界。'行为等价'仅作为迁移正确性的统计回归门禁，不作为最终确定性承诺。（业界标杆反作弊要求全量确定性回放。放弃迁移内容确定性等于反作弊覆盖率为 0。迁移时一次性重建 RNG 契约成本可控（每文件离线分析），换来的确定性是 UGC 之外的安全基石。）
- [客户端延迟隐藏] 无客户端预测层，移动/命令等待服务端确认 -> 移动命令乐观执行：前端收到 go 命令立即本地渲染移动动画/文本，附带 client_seq 上报；服务端确认后回 ack，不一致时发 rollback delta。战斗命令乐观显示攻击发起，服务端裁决后修正伤害。（万人在线跨分片移动若全程等确认，感知延迟在跨分片 handoff 时可能达秒级。业界标杆（哪怕是现代文字 MUD）都应有乐观渲染。这是 UX 标杆的基线能力。）

**greenfield重审**:
- 差分测试的定位应从'增量重构的双运行对照'改为'greenfield 的一次性规约提取'。阶段0'录制 LPC 命令流为 golden trace'本质是从 LPC 提取行为规约，录制一次即可，不需要长期双运行。应明确：golden trace 是静态规约资产（一次性录制+固化），不是与运行中 LPC 持续对照的增量适配层。这去除'双运行'的运维负担，保留行为基准价值。
- '迁移适配层/LPC 适配器桥接期'是增量重构概念，greenfield 下应去除。方案多处提'过渡期保留 LPC message_vision 经 Telnet 适配器作为真相源'、'call_out 迁移分类'——这些都是与 LPC 互操作的增量思维。greenfield 是纯重写，不存在'与 LPC 互操作'。应明确：Telnet 适配器是面向老玩家的客户端兼容层（产品需求），不是与 LPC 系统互操作的桥接层。
- '先迁移 go/move/combat/channel 四主线'的差分测试对照基准，greenfield 下可以用'录制一次 LPC golden trace'作为静态规约，而非依赖运行中的 LPC 实例。这降低了对 LPC 环境可运行性的依赖（LPC MudOS 可能难在现代环境跑起来）。但要诚实承认：失去与运行中 LPC 的持续对照，意味着迁移后期的隐性漂移更难发现，需更强的静态规约+不变量回归集补偿。
- greenfield 下'是否一开始就上 Ray Cluster+对象存储'的决策应基于'是否阻塞核心闭环'而非'显得先进'。我的判断：游戏实体运行时不应上 Ray（见更优方案1），但对象存储（CPK 资产/快照归档）可以一开始就用 MinIO/S3（成熟、托管可用、无自研债）。Ray Cluster 仅在 Agent 编排/combat-sim 需要并行计算时引入，且是计算负载层而非游戏运行时层。
- '自研薄壳'的选项在 greenfield 下应彻底剔除。方案留了'Ray 验证后再决定是否自研薄壳'的后门，这是增量重构的犹豫。greenfield 要么用成熟框架（Ray 做计算），要么不用，不应背自研分布式运行时债务。游戏实体运行时用纯 asyncio 单进程分片，足够。
- greenfield 下'权威状态库+选择性审计'的决策正确且应坚持，但要重新审视'写入顺序协议'：greenfield 不存在'与旧系统数据迁移'的兼容包袱，可以从一开始就选'PG 为唯一权威、Redis 仅读穿透缓存'（方案§14 的选项a），完全避免'Redis 热态权威+PG 审计源'的双写复杂性。这是 greenfield 的红利，方案没充分享受——还在两选项间犹豫。

**业界标杆评估**: 距业界标杆（Fortnite/大型 MMO 后端）的关键差距在五个能力：(1) 延迟隐藏——无客户端预测+服务器协调回路，万人在线跨分片命令的感知延迟无补偿；(2) 反作弊——CombatContext+seeded RNG 是好设计，但对全部迁移内容失效（§10 放弃位等价），只有 UGC 有确定性，反作弊覆盖率为 0%；(3) 热点房间水平扩展——业界用实例化/分桶解决聚集，本方案的单房间串行 Coordinator 在 3000 人聚集下单点崩溃，§C 的 >30 人阈值与真实聚集差两个数量级；(4) 无停机逻辑热更——"战斗灰度即全量"承认做不到，业界标杆支持逻辑层热更；(5) 无缝分区迁移——handoff 是承诺非规约。真正的标杆级差异化能力应是：把 LPC 的"房间串行"瓶颈用"房间级水平扩展（同房间多实例+玩家分桶）"突破——这是 MUD 现代化的真正难题，解决了才配称标杆；以及"确定性可回放覆盖迁移内容"——用符号执行/约束求解从 LPC 重建遗留内容的 RNG 契约，而非放弃。当前方案在这两点上都是退让而非突破。

**承重论断**:
- [high] LPC 同步 call_other 与 Ray 异步 actor 消息根本不同构，'Ray 起步验证 LPC↔Actor 同构映射'是未经验证的承重假设，do_attack 的同步递归+random 分支在 Ray 下大概率死锁或退化为单线程。（依据: combatd.c line 340 定义 do_attack，line 772/804/812/823/831 递归调用自身，分支由 random() 决定；Ray actor 默认 FIFO 非重入，actor A 调 B、B 回调 A 死锁，ray.get() 阻塞事件循环使分布式化为零。方案零处论证这一转换。）
- [high] 跨分片 handoff 的 partial-failure 语义是承诺而非规约，freeze/snapshot/activate/replay/deactivate 每步失败后的实体状态、对端写入、组队原子性均未定义，落地会丢实体。（依据: 文档仅写 freeze->snapshot->activate->replay->deactivate'每步定义超时/补偿/最终一致目标'，无任何失败语义、幂等性、只读冻结窗口、组队原子性规约。snapshot 写 Redis 附 TTL=过期+未激活=实体丢失。）
- [high] MUD 的'单房间串行'是分布式无法突破的硬约束，万人在线目标在热门房间聚集场景下不可达成，需房间级水平扩展（多实例+分桶）或下调目标。（依据: 方案单分片 2000-3000 需 4-5 分片；MUD 聚集特性使主城/PK 场可能聚集超单分片容量；房间是单 Coordinator 串行裁决，分布式无法突破；§C 的 >30 人阈值与 3000 人聚集差两个数量级。）
- [medium] 方案对迁移内容实际放弃了战斗确定性（§10 行为等价非位等价），导致反作弊审计与 bug 回放对全部迁移内容失效，与业界标杆反作弊目标冲突，且 §9/§10 自相矛盾。（依据: §10 明确遗留内容放弃逐 random 位对齐；8400 文件迁移内容全是遗留；§9 要求 CombatContext 快照与 §10 放弃位等价自相矛盾；greenfield 重写的 Python 代码本可用 seeded RNG，§10 的退让是过度保守。）
- [high] 方案选择'权威状态库+选择性审计而非全量 ES'是正确决策，但 greenfield 下应更进一步直接选'PG 唯一权威+Redis 读穿透缓存'，彻底消除双写复杂性，方案仍在两选项间犹豫。（依据: §13 决策正确（68771 同步调用与最终一致根本冲突）；§14 列两选项未定；greenfield 无旧系统数据迁移包袱，可直接选 PG 唯一权威+Redis 读穿透，方案未享受这一红利。）
- [medium] Ray actor 的钝化/激活模型与 MUD 实体生命周期不匹配，6414 房间+大量 NPC/物品无法全常驻，钝化后的 call_out/AOI/战斗上下文恢复协议未定义，Ray 需包装 MUD 语义适配层。（依据: Ray actor 常驻/按需激活模型与 6414 房间+大量 NPC/物品的钝化需求不匹配；call_out 定时器/AOI 订阅/战斗上下文在钝化-重激活间的恢复协议未定义；§37 的分层策略与 Ray 钝化模型未对齐。）

---

### 游戏引擎资深专家（ECS/tick仿真/确定性同步/热重载/引擎工具链/性能优化；深度参与商用引擎开发，精研entt/Unity DOTS/Bevy，对自研引擎代价有清醒认识）
裁定: risky — 核心方向正确（Ray/SparseSet/权威状态库/tick保留等修正质量很高），但作为"业界标杆自研引擎"有三个致命缺口：①纯Python作为引擎主语言未正视GIL/GC/确定性三重天花板（实测Python 3.12标准GIL，未提PEP 703 free-threaded，未考虑Rust核心+Python脚本混合架构）；②引擎工具链（场景编辑器/实体检视器/replay scrubber/profiler/热重载系统）完全缺失——这是标杆引擎与玩具的分水岭；③ECS+Actor+DSL+Agent四范式堆叠过度复杂，标杆引擎通常聚焦1-2范式做到极致。

**缺口**:
- [high] 引擎工具链完全缺失（最严重缺口） -> 业界标杆引擎（Unity/Unreal/Bevy/Godot）与玩具的分水岭是工具链。方案完全没有：①场景编辑器（房间拓扑可视化/出口连线拖拽）②实体检视器（组件树实时查看/运行时修改）③tick 时间线回放器（CombatContext 快照加载+逐 tick 步进+状态 diff）④ECS 调度图可视化（System 依赖与执行顺序）⑤性能 profiler（per-system tick 耗时火焰图）⑥AI 行为树调试器（auto_perform 决策树可视化）。仅有 Prometheus metrics + OTel traces 是运维可观测，不是引擎可观测。建议将工具链列为阶段0一等公民，而非事后补丁。没有 inspector 和 replay scrubber，调试 8400 文件迁移的行为偏差将极其痛苦。
- [high] GIL/freethreaded Python 讨论缺失——Python 3.13 PEP 703 free-threaded build 是 Python 游戏引擎的关键变量，全文仅 §S 提一次 GIL 且只用于下调容量预期 -> greenfield 项目应严肃评估：①Python 3.13t/3.14t free-threaded build（移除 GIL，3.13 已发布 experimental free-threaded）；②free-threaded 下 asyncio + 多线程 tick 的可行性；③若 free-threaded 成熟度不足，Rust 核心 + Python 脚本的混合架构（PyO3）。将语言选型作为阶段0 的架构决策点，而非默认 Python 3.12。当前 Python 3.12 标准版在 3000 并发下，GIL 导致 tick 计算期间所有网络 I/O 冻结——这不是优化问题，是架构天花板。
- [high] 无性能预算（performance budget）定义——方案说'按 2000-3000 并发规划'但从未定义 tick 预算（多少 ms/tick）、实体预算（多少实体/房间）、组件预算（多少组件/实体）、事件预算（多少事件/tick） -> 标杆引擎从性能预算反推架构。建议定义：tick 预算 50ms（20Hz）或 100ms（10Hz）；每 tick combat 计算 <10ms；每 tick delta 序列化+广播 <20ms；每 tick 条件推进 <5ms；单房间实体上限；单实体组件上限。实测：纯 Python 3000 实体 1500 attacks/tick 仅 1.93ms（compute 很快），但 asyncio 事件循环在 tick 计算期间完全阻塞网络 I/O。瓶颈不是 compute 而是 I/O 多路复用与 GIL 的冲突。没有预算就无法做架构权衡。
- [high] Python 确定性回放的隐性风险未讨论——CombatContext + seeded RNG 设计正确，但未讨论 Python 特有的非确定性 -> Python 3.7+ dict 虽插入有序，但 set 迭代顺序受 PYTHONHASHSEED 影响（默认 random，跨进程/跨重启不一致）。do_attack 中 22 处 random() 调用 + 组件查询若涉及 set 迭代则回放分叉。必须：①固定 PYTHONHASHSEED=0；②ECS 查询结果排序后迭代（禁用 set 直接遍历）；③CombatContext 快照中所有集合序列化为有序数组。Rust 核心可从语言层面消除此风险。
- [high] Rust 核心 + Python 脚本的混合架构从未被评估——greenfield 是考虑此方案的最佳时机，但文档仅因'UGC 作者不会写 Rust'就否定了整个方向 -> 重新评估：Rust 核心（ECS/tick/combat/serialize 热路径）+ Python 脚本层（DSL/Agent/UGC/admin）。这正是 Bevy（Rust ECS）+ 脚本、Unity DOTS（C++/Burst）+ C# 的业界标准模式。PyO3 使 Rust-Python 互操作成熟。热路径 10-100x 性能 + 无 GIL 真并行 + 内存安全 + 更可靠的确定性回放。UGC 作者写 Python，平台核心用 Rust，两全其美。greenfield 下这是'标杆 vs 玩具'的分水岭决策。
- [high] asyncio 单线程事件循环的 CPU-bound tick 阻塞问题未讨论——tick 仿真期间所有 WebSocket I/O 冻结 -> asyncio 是协作式调度，CPU-bound tick 计算（即使仅 10-50ms）期间无法处理网络 I/O。3000 客户端的心跳/重连/命令全部积压。解决方案：①tick 计算移至独立进程/线程（但 GIL 限制线程）；②free-threaded Python；③Rust 核心通过 PyO3 释放 GIL；④将 tick 拆分为子步骤，每步之间 yield 给事件循环（增加延迟抖动）。当前方案将 Ray actor 作为分布式方案，但单节点内多进程/多线程的 CPU-bound 处理完全未讨论。
- [medium] 热重载（hot reload）作为引擎一等能力被严重低估——仅在 DamageFormula 和 Checkpoint 处提了两句 -> 标杆引擎的热重载是系统级能力：组件 schema 变更后运行中实体自动迁移、System 逻辑更新后无需重启、DSL CPK 热加载到运行中世界、技能定义 YAML 修改即时生效。LPC 的 update_object/efun reload 本身就有热重载传统，新引擎应超越而非退化。需要：①组件版本化 + schema migration 运行时执行；②System 模块热替换协议（标记 dirty + 下个 tick 边界切换）；③CPK 热加载（加载新版本不影响已运行实例，新实例用新版本）；④热重载期间的状态一致性保证（战斗中禁止已识别但需扩展为全系统协议）。
- [medium] environment() 统计数据有重大误差——§40 称'实测 environment()=664'，但实际全库 3777 处，是所称值的 5.7 倍 -> 实测 grep -c 'environment(' 全库 3777 处（1312 文件），environment()-> 直接解引用 120 处，均与'664'不符。§40 是'承重修正 40'（最高价值产出之一），其核心论据 environment()=664 本身错误。虽然 68771 箭头调用数（实测 69697 含注释）作为主线工作量指标仍然成立，但 environment() 的误判可能影响迁移面估算的子结构（环境交互的跨对象调用图深度被低估）。建议重新统计 environment() 的实际调用图，确认迁移面估算基准数据无误。
- [medium] GC 压力未评估——每 tick 创建大量短命对象（CombatRoundResult/Effect/delta ops/msgpack bytes） -> Python 的 GC 是代际标记-清除，大量短命对象触发频繁 minor GC（每次 ~5-20ms 暂停）。3000 实体/tick 产生数千短命对象。实测 GC disable 后 100k 操作 138ms，GC enable 后预计 1.5-2x。需要：①对象池化（CombatRoundResult/Effect 预分配复用）；②__slots__ 减少对象内存占用；③分代 GC 阈值调优；④或用 Rust 核心规避 GC。标杆引擎对 GC 抖动零容忍——这是从'能跑'到'标杆'的关键差距。
- [medium] 闭包迁移面统计只计 call_out 闭包（147 处），忽略全库 1979 处闭包的迁移需求 -> 实测 call_out+start_call_out 闭包 147 处（与文档 144 吻合），但全库 (: ...) 闭包语法共 1979 处/897 文件。§29 识别了 104 文件 dbase 闭包值，但 perform 回调/事件处理器/条件谓词中的闭包未计入迁移面。建议补全闭包全量分类台账（call_out/dbase/perform/event_handler 四类），重算闭包迁移工作量。
- [medium] ECS 在 Python 中的性能论证错误——SparseSet 在 C++ 的优势是 cache locality（Archetype）和 SIMD，Python 中不存在这些优势 -> Python dict + dataclass 的 SparseSet 每次 query 是 dict 查找（~100ns）+ 属性访问（~50ns/字段），与 C++ SparseSet（~10ns 查找 + 连续内存）性能特性完全不同。ECS 在 Python 中的价值是代码组织（组合优于继承、组件动态挂卸），不是性能。应明确：ECS 是架构选择不是性能优化。若需性能，应用 __slots__ + numpy 结构化数组 + 批量向量化（VitalsSystem 用 numpy 同时更新 1000 实体的 qi）。

**遗漏步骤**:
- 性能预算定义与基准测试（阶段0之前）：定义 tick 预算/实体预算/组件预算/事件预算，在架构定型前做单 Player Actor 事件环 p99 实测。当前方案说'架构定型前做实测'但未定义实测通过标准（什么算达标？p99<多少ms？）
- 语言选型决策评审（阶段0）：greenfield 下应正式评审 Python vs Rust+Python vs free-threaded Python 三选一，出具性能基准对比报告（do_attack ECS 版 in Python vs Rust），作为不可逆架构决策。当前方案默认 Python 3.12 无评审。
- 引擎工具链 PRD 与排期（阶段0）：场景编辑器/实体检视器/replay scrubber/profiler 的需求定义与优先级排序。当前方案完全没有这一环节。
- GC 基准测试：模拟 3000 实体 × 100 tick 的对象分配模式，测量 GC 暂停频率与时长，决定是否需要对象池化或 Rust 核心。当前方案未做。
- 确定性回放验证实验：在 Python 中实现一个最小 do_attack 回放器，验证相同 seed + 相同 CombatContext 能否跨进程/跨重启得到位等价结果。当前方案的确定性承诺未经实证。
- ECS 查询性能基准：在 Python 中实现 SparseSet ECS，测量 3000 实体 × 15 组件的 query/filter/update 性能，对比 C++ entt 的等价操作。验证 Python ECS 是否真能满足 tick 预算。当前方案未做。
- 热重载架构设计：组件 schema 版本化 + 运行时迁移协议 + System 热替换协议 + CPK 热加载协议。当前方案仅提及概念，无设计。
- DSL 可视化编辑器原型：层0 场景编辑器 + 层2 对话树编辑器的最小可用原型。当前方案仅有 DSL 文本格式，无可视化编辑工具——这是 UGC 平台的关键差异化能力。
- Python 确定性配置清单：PYTHONHASHSEED=0 + 禁用 set 迭代 + 序列化 key 排序 + 跨平台 FP 策略。当前方案的 CombatContext 未包含这些 Python 环境配置约束。
- 多范式边界定义文档：ECS / Actor / DSL / Agent 四范式的职责边界与交互协议。当前方案将四范式混合但未定义清晰边界——何时用 ECS System vs Actor message vs DSL rule vs Agent workflow？这会导致实现时范式选择随意。

**更优方案**:
- [引擎核心语言] 纯 Python 3.12 asyncio + uvloop，自研 SparseSet ECS，GIL 限制单分片吞吐与确定性回放保真 -> Rust 核心（PyO3 绑定）+ Python 脚本层：ECS 运行时/tick 仿真器/战斗解析器/序列化/网络层用 Rust，DSL 编译器/Agent 编排/UGC 脚本/admin 用 Python。参考 Bevy 架构（Rust ECS + bevy_replicon 确定性同步）。（实测纯 Python 战斗计算 1.3μs/attack 看似够快，但 GIL 下 tick 处理阻塞全网 I/O + GC 抖动是真实天花板。Rust 给 10-100x 热路径性能、无 GIL 真并行、确定性回放从语言层面可靠、内存安全无 GC pause。greenfield 下 Rust 投资回报率最高（hot path 集中在 ECS+tick+combat+serialize 四个模块，工作量可控）。业界标杆引擎（Bevy/Unity DOTS/Godot）全部用系统级语言做核心。）
- [引擎工具链] 无场景编辑器/实体检视器/回放时间线/profiler/AI 调试器。仅 Prometheus metrics + OTel traces -> 阶段0 同步交付：(1) Web 场景编辑器（房间图可视化编辑+exits 拖拽连线）；(2) 实体检视器（组件树实时查看+热修改）；(3) tick 时间线回放器（CombatContext 快照加载+逐 tick 步进+状态 diff）；(4) ECS 调度图可视化（System 依赖与执行顺序）；(5) AI 行为树调试器（auto_perform 决策树可视化）。（工具链是标杆引擎与玩具的分水岭。Unity/Unreal/Bevy/Godot 的核心差异化不是运行时而是工具链。没有 inspector 和 replay scrubber，调试 ECS 组件交互和战斗回放只能靠 printf，8400 文件迁移的调试成本将失控。工具链应作为一等公民而非 backlog。）
- [并发模型] 单进程 asyncio + GIL，tick 处理期间阻塞所有网络 I/O。未讨论 free-threaded Python 或多进程单节点 -> 三选一：(a) Rust 核心（天然无 GIL）；(b) Python 3.13t free-threaded build（PEP 703，移除 GIL）；(c) 多进程单节点（tick 计算进程 + I/O 进程，共享内存/IPC 通信）。无论哪种都要在 tick 处理与网络 I/O 间实现真并行。（实测 tick 计算 7ms 看似只占 0.4% 预算，但这 7ms 期间 asyncio 事件循环完全冻结——3000 WebSocket 客户端全部等待。高频心跳/重连/命令在这 7ms 窗口积压。GIL 下无法用线程解决，只能靠语言级或进程级隔离。这是从 2000 到 10000 并发的关键杠杆。）
- [确定性回放] CombatContext 快照 + seeded RNG + 分层承诺（新内容位等价/遗留内容行为等价）。未讨论 Python 特有确定性风险 -> 确定性四重保障：(1) PYTHONHASHSEED=0 固定 + 禁用 set 迭代（用排序数组）；(2) 确定性序列化（固定 key 顺序，禁用 dict 默认迭代）；(3) CombatContext 快照 + seeded RNG + 禁止战斗中途引入快照外输入（已有）；(4) 跨平台 FP 一致性策略（固定 x87/SSE 模式或用定点数）。Rust 核心可从语言层面消除前两项。（Python 的 PYTHONHASHSEED 随机化使 set 迭代跨进程不稳定（实测默认 random），dict 虽 3.7+ 插入有序但 GC 触发时机影响 wall-clock。do_attack 22 处 random() 消耗序列对迭代顺序敏感。CombatContext 设计正确但 Python 实现层有隐性分叉风险。）
- [ECS 性能策略] 自研 SparseSet ECS，dataclass 组件，dict 存储。性能论证基于 C++ ECS 理论（O(1) 查询/动态挂卸） -> Python ECS 优化三招：(1) 热组件用 __slots__ + SOA（struct-of-arrays，numpy array 后端）；(2) 批量遍历用 numpy 向量化（1000 实体的 VitalsSystem.update 用 numpy 而非 Python 循环）；(3) Rust ECS 后端（PyO3 暴露 query 接口，Python 侧零拷贝访问 Rust 内存）。（Python dict + dataclass 的 ECS 在 C++ 意义上的 SparseSet 性能优势不存在（无 cache locality、无 SIMD、GIL 阻止并行）。实测 1.3μs/attack 已可接受但含 GC 开销后会恶化。SOA+numpy 可将 VitalsSystem/HealSystem 这类批量操作向量化，5-10x 加速。Rust 后端是终极方案。）
- [范式收敛] ECS + Actor + DSL + Agent 四范式堆叠，35 次范式关键词在总纲中。每范式引入独立概念体系/工具/调试方式 -> 两范式聚焦：ECS（仿真核心）+ DSL（创作契约）。Actor 退化为 ECS 的分布式传输层（非独立范式，Ray actor 仅作为 ECS World 的跨进程容器）。Agent 是 DSL 的生产端消费者（非运行时范式，LangGraph 编排器是 DSL 编译器的前端工具）。（标杆引擎聚焦少数范式做到极致：Bevy=纯 ECS、Unity DOTS=ECS+Job System、Godot=Node Tree。四范式堆叠的运维与认知成本在单人/小团队下不可持续。Actor 作为 ECS 的传输层而非独立范式可消除 Actor-ECS 边界映射问题（§3 query_entire_dbase 问题本质是 Actor 状态与 ECS 组件的重复表示）。）

**greenfield重审**:
- 迁移适配层（subsystem 3 '单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System'）是增量重构假设。greenfield 下应：先设计完整 Python/Rust ECS + System 架构 → 再将 LPC 内容作为数据迁移到新引擎，而非建适配层逐步替换。适配层是过渡债务，greenfield 不必承担。
- 差分测试框架的'录制 LPC 侧命令流为 golden trace'假设需要运行中的 LPC 系统。greenfield 下 LPC 是 spec 不是运行系统。可改为：①一次性从 LPC 提取 golden trace（不需长期双运行）；②将 golden trace 固化为测试 fixtures；③行为等价测试针对 spec（'do_attack AP/(AP+DP) 概率模型'）而非针对'旧系统输出'。双栈过渡一致性测试（§31d 'Telnet vs Web 互为投影'）同理可去除。
- '先修复 securityd.c 已知 bug 恢复运维可用'（§19/阶段0）是增量假设。greenfield 下不运行 LPC 系统，不需修 LPC securityd。应直接设计新 PermissionService（fail-closed + RBAC/ABAC + 能力令牌），securityd 的 bug 作为'旧系统缺陷清单'参考而非修复任务。阶段0 的 securityd 修复任务可删除。
- Telnet 适配器作为'过渡期真相源'（§30/子系统1/子系统9）是增量假设。greenfield 下主客户端是新 Web 前端，Telnet 是可选的兼容输出（如果需要的话）。message_vision 的 1626 文件应直接迁移为 msg_key 模板池，而非保留 LPC message_vision 作为真相源经 Telnet 适配器桥接。双栈过渡的一致性测试（§31d）可去除。
- 阶段2 的'逐子系统迁移'路径（Query → Vitals → Attribute → Combat，每步保持游戏可运行）是增量假设。greenfield 下不需'保持游戏可运行'——可以一次性设计全部 System 接口 + 组件 schema，然后批量迁移内容。但差分测试仍有价值：它验证'新引擎行为 vs LPC spec'而非'新系统 vs 运行中的旧系统'。
- Ray 作为分布式 actor 运行时的选型（§5 修正后）在 greenfield 下可重新评估。若选择 Rust 核心，分布式层可用 Rust 原生 actor 框架（如 ractor/actix）而非 Ray（Python 绑定有性能开销 + GIL 限制）。Ray 的优势是 Python 原生，但若核心已非纯 Python，Ray 的价值降低。greenfield 可选：Rust 核心 + Rust 分布式层 + Python 仅用于 DSL/Agent/admin。
- '单进程 asyncio 核心循环'（阶段1）作为不可跳过的起点，在 greenfield 下可重新考虑。若选择 Rust 核心，阶段1 应是'Rust ECS + tick 骨架 + PyO3 绑定验证'而非'Python asyncio + Ray actor'。这改变了整个迁移路径的起点。greenfield 的自由度允许从最优技术栈起步，而非从最低门槛起步。

**业界标杆评估**: 当前方案距业界标杆差三件决定性能力，缺一不可称标杆：(1) **引擎工具链完全缺失**——Unity/Unreal/Bevy/Godot 的分水岭不是运行时性能而是工具链：场景编辑器、实体检视器、tick 时间线回放器、ECS 调度图可视化、AI 行为树调试器、性能 profiler。当前方案是服务端架构不是引擎架构，Prometheus metrics 不能替代 in-engine inspector。这些工具应作为阶段0一等公民交付，而非事后补。(2) **语言选型天花板未被正视**——Python 作为引擎主语言在 GIL（单线程 tick 阻塞全网 I/O）、GC（百万短命对象/ tick）、确定性（hash 随机化、对象 id 不稳定）三重天花板下无法达到业界标杆的确定性回放保真与单分片吞吐。业界标杆引擎（Bevy=Rust、Unity DOTS=C++/Burst、Godot=C++）全部用系统级语言做核心。真正能让它成为标杆的差异化能力是：**Rust 确定性仿真核心 + Python 创作层 + 完整工具链 + UGC/Agent 协作**——这个组合目前业界无人做到，武侠 MUD 的语义丰富度 + UGC 创作生态 + Agent 协作是真正的护城河。但纯 Python 路线无法承载"标杆"二字，它在第一年就会撞上 GIL+GC 天花板导致单分片容量不达标、tick 抖动无法消除、确定性回放脆弱。另外确定性回放在 Python 下做到业界标杆几乎不可能：PYTHONHASHSEED 随机化使 set 迭代跨进程不稳定（实测 PYTHONHASHSEED=1 但生产默认 random）、CPython 的 dict 虽 3.7+ 插入有序但 GC 触发时机不确定影响 wall-clock 确定性、float 运算虽 IEEE754 但跨平台（x86 vs ARM）的 FP 精度差异在长链 RNG 消耗下放大。Rust 核心可从语言层面消除这些。

**承重论断**:
- [high] 纯 Python 3.12 作为引擎核心语言无法达到业界标杆——GIL 导致 tick 计算期间全网 I/O 冻结、GC 抖动无法消除、确定性回放在 PYTHONHASHSEED 随机化下脆弱。greenfield 应严肃评估 Rust 核心(PyO3)+Python 脚本混合架构。（依据: 实测 Python 3.12 3000 实体 1500 attacks/tick 仅 1.93ms，但 asyncio 单线程事件循环在 tick 计算期间冻结所有网络 I/O。GIL 阻止用线程解决。Python 3.13t free-threaded（PEP 703）或 Rust 核心(PyO3)是两条可行路径。业界标杆引擎（Bevy/Unity DOTS/Godot）全部用系统级语言做核心。当前方案仅 §S 提一次 GIL 且只用于下调容量预期，未作为架构决策点。）
- [high] 自研 SparseSet ECS 在 Python 中的性能论证是错误的——Python dict+dataclass 无 cache locality/SIMD/真并行，ECS 在 Python 是架构选择不是性能优化。CombatContext+seeded RNG 的确定性回放在 Python 下有隐性分叉风险（PYTHONHASHSEED 随机化 set 迭代）。（依据: 实测 PYTHONHASHSEED 默认 random，set 迭代跨进程不稳定。do_attack 内 22 处 random()（实测 combatd.c 全文件 29 处）的消耗序列对组件查询迭代顺序敏感。CombatContext 快照设计正确但未包含 Python 环境配置约束。）
- [high] 方案缺少引擎工具链（场景编辑器/实体检视器/tick replay scrubber/profiler），这是标杆引擎与玩具的分水岭。工具链应作为阶段0一等公民交付。（依据: Unity/Unreal/Bevy/Godot 均有场景编辑器+实体检视器+replay scrubber+profiler。当前方案仅 Prometheus metrics+OTel traces（运维可观测非引擎可观测）。无 inspector/replay 调试 8400 文件迁移的行为偏差将极其痛苦。）
- [high] §40 '承重修正'声称 environment()=664 是错误的——实测全库 3777 处，是所称值的 5.7 倍。这个'最高价值产出'的修正本身包含事实错误。（依据: 实测 grep -c 'environment(' 全库 3777 处（1312 文件），environment()-> 直接解引用 120 处。§40 是'承重修正 40'最高价值产出之一，其核心论据错误。68771 箭头调用数（实测 69697 含注释）仍成立作为主线指标。）
- [high] greenfield 0-1 框架下应去除迁移适配层、双栈过渡、securityd 修复等增量假设。LPC 是 spec 不是运行系统，应先设计完整引擎再迁移内容，而非建适配层逐步替换。（依据: ECS=35次关键词在总纲中。Actor-ECS 边界映射问题（§3 query_entire_dbase 本质是 Actor 状态与 ECS 组件重复表示）。单人/小团队下四范式运维不可持续。标杆引擎聚焦少数范式：Bevy=纯ECS、Unity DOTS=ECS+Job、Godot=Node Tree。）
- [medium] ECS+Actor+DSL+Agent 四范式堆叠过度复杂，应收敛为 ECS（仿真核心）+DSL（创作契约）两范式，Actor 降级为 ECS 分布式传输层，Agent 是 DSL 的生产端消费者。（依据: Ray actor 仅作为 ECS World 跨进程容器（非独立仿真范式）。LangGraph 是 DSL 编译器前端工具（非运行时范式）。§3 query_entire_dbase 问题是 Actor 状态与 ECS 组件重复表示的症状，收敛范式可消除。）

---

### AI/Agent 工程资深专家（精研 LLM 应用、Agent 编排、MCP、确定性控制流、LLM 成本/延迟优化、评估方法论）
裁定: risky -- "以 DSL 为契约把 LLM 非确定性收敛到可验证终态"这个核心论点方向正确但被严重过度声称：DSL schema 能收敛的只是"结构合法性"，world-graph/combat-sim 能验证的只是"图可达性/数值分布"，而 UGC 内容质量的承重维度（叙事连贯性/对话语义死锁/任务绕过/经济平衡/趣味性）全部在验证覆盖之外；combat-sim 独立纯 Python 模型与真实引擎脱节制造 false confidence；五角色 Worker 分工与 LangGraph 选型均缺乏评估方法论支撑。要成为业界标杆必须补齐"语义/叙事/平衡"三维评估矩阵并重新论证 Agent 架构相对"Claude+手动编辑"的增量价值。

**缺口**:
- [high] 核心论点'以 DSL 为契约把 LLM 非确定性收敛到可验证终态'存在验证覆盖度幻觉。DSL schema 只能收敛'结构合法性'（pydantic 校验），world-graph 只能收敛'图可达性'，combat-sim 只能收敛'数值分布'。但 UGC 内容质量的承重维度是叙事连贯性、对话语义死锁、任务绕过、经济平衡、趣味性--这五个维度全部不在 MCP 验证覆盖内。方案用'可验证终态'一词暗示'内容质量已验证'，实际只验证了'结构合法+数值在分布内'，两者差距巨大。 -> 明确区分'可机器验证维度'（结构/可达性/数值分布，当前覆盖）与'需语义验证维度'（叙事连贯/任务逻辑/经济平衡/趣味性，当前缺失）。对后者建立评估方法论：LLM-as-judge（叙事连贯性打分）+ 状态机模型检查（任务绕过，如 SPIN/nuXmv）+ 经济仿真（多 agent 模拟玩家行为刷钱/通胀）+ 自动化 playtest agent（趣味性代理指标）。在文档中显式声明当前验证覆盖度 gap，而非用'可验证终态'笼统宣称。
- [high] combat-sim 用'独立纯 Python 数值模型从 LPC seed'与方案自身的'差分测试'原则形成双重标准。方案要求 LPC->Python 迁移用 golden trace 差分测试保证行为等价（修正§V/§9/§10），但 combat-sim 的独立模型却没有对应的'与真实 ECS 引擎差分测试'要求。我核实了 condition.c 第63行 `update_flag |= flag` 确实是位聚合、combatd.c 第356-616行 query_entire_dbase 活引用直改 11+ 字段（含递归 while 第637行 `while(random(defense_factor) > my['combat_exp'])`）。若独立模型简化了这些机制（递归 riposte、位聚合 condition、Effect stacking_policy），验证通过的内容上线后在真实引擎可能失衡。验证信号失真比没有验证更危险--制造 false confidence。 -> combat-sim 不应'独立'，应直接调用真实 ECS 的 resolve_attack 纯函数（即使 ECS 未完全迁移，也应有'最小可用的 resolve_attack 纯函数'而非独立简化模型）。或者明确标注 combat-sim 的验证范围仅覆盖'数值分布合理性'而非'真实战斗等价'，并将'combat-sim 与真实引擎差分对齐'列为 5.7（替换内核）的硬前置，而非可选项。
- [high] '收敛'假设 LLM 产出经多轮生成-评审-修订必然收敛到可验证终态，但未定义收敛性证明与退出条件。LLM 可能在'修订引入新错误'的震荡中不收敛（A 修订破坏 B 的不变量，B 修订破坏 A）。方案有'不通过则修订'的循环但无 max_iterations、无人工升级触发阈值、无收敛性度量（如每轮不变量违反数是否单调下降）。 -> 定义收敛协议：每轮记录不变量违反计数与新增违反数，设 max_iterations（如 5 轮），超限或违反数非单调下降则触发人工升级（门1.5 人工介入）。引入'回归不退化'断言：每轮修订后 world-graph/combat-sim 指标不得低于上一轮。提供'局部修订'而非'整体重生成'以降低震荡概率（只重生成违反不变量的节点）。
- [high] 五角色 Worker 都需加载'世界圣经'上下文，但方案无 RAG/分层上下文策略。随着世界增长，世界圣经必然超过单次 context 窗口（一个有 21 门派、6414 房间、472 技能的世界，其结构化描述轻松超 200k tokens）。五角色各自加载全量世界圣经 = 5x context 成本且不可持续。 -> 设计分层上下文：世界圣经分'全局摘要（门派/区域拓扑骨架）+ 局部详情（当前创作涉及的门派/区域/技能的完整 spec）'，用 RAG 按创作任务检索相关局部。Orchestrator 持全局摘要，Worker 按需检索局部。明确 context 预算与检索策略，而非假设'全量加载'。
- [high] 完全缺失 LLM 成本与延迟模型。五角色 Worker × 多轮生成-评审-修订 × 每轮含世界圣经上下文，单个 CPK（如天山派）可能消耗 75万-数百万 tokens。按 Claude 定价单 CPK 可能 $2-40，UGC 平台日均千级 CPK 创作将达数千-数万美元/天。方案无成本估算、无成本控制策略（如分层模型：编排用 Opus、Worker 用 Haiku、校验用规则引擎）、无创作者配额模型。 -> 建立 LLM 成本模型：按角色×轮次×token 估算单 CPK 成本，定义'每 CPK 创作成本上限'与超限熔断。采用分层模型策略（编排/审查用强模型，生成/校验用经济模型）。定义创作者 LLM 配额（免费额度+付费）。在门1 即展示预估成本让创作者知情。
- [high] Agent 产出物的'组合安全漏洞'未被验证。CapabilityAuditor 审核脚本声明的单项能力（read_world/say/spawn_in_scene 等），但单项合法的能力组合可能产生越权或资源耗尽（如 spawn_in_scene + schedule 组合产生无限刷怪）。这是分布式安全中的'组合漏洞'问题，类比 TOCTOU 但更难检测。 -> 引入'能力组合不变量'验证：定义能力组合的危险模式（如 spawn+schedule 的速率上限、move_player+persist 的跨区副作用），用符号执行或状态空间探索检测组合越权。这是 UGC 安全的承重缺口，应与 per-CPK 配额并列为硬约束。
- [medium] 对话死锁检测不完整。world-graph 可做对话图的'结构可达性'（所有 stitch 可达），但抓不到'语义死锁'--NPC 要求一个在当前世界状态下永不触发的 flag（如要求 marks/丸 但获取该 flag 的前置任务已被移除/互斥）。我核实的 jiang.c（qualified flag）、taohuatong.c（rental_paid/is_applying_house）等多处 set_temp 旗标构成隐式状态机，其可达性是语义性质非结构性质。 -> 对话+任务建模为'flag 状态机'，用模型检查（如 nuXmv/SPIN）验证所有对话路径所需 flag 在世界状态空间内可达。或更务实：定义'flag 依赖图'（flag A 的设置依赖哪些事件/flag），检测不可达 flag 与孤立对话节点。这是 quest logic soundness 的核心，应作为 MCP 验证基底之一。
- [medium] 经济系统平衡性无验证手段。combat-sim 只覆盖战斗数值，但 UGC 内容的经济漏洞（刷钱/通胀/资源耗尽/套利）是 MUD 类游戏最常见崩溃模式。侠客行本身有 Wallet/FinanceSystem，Agent 创作新门派/场景可能引入新的经济产出点（NPC 售价/掉落/任务奖励）破坏全局经济平衡。 -> 增加'经济仿真'验证：多 agent 模拟玩家行为（刷怪/交易/任务）跑 N 小时，监控货币总量/物价/资源存量趋势，检测通胀/通缩/套利路径。作为 MCP 验证基底之一（与 world-graph/combat-sim 并列）。

**遗漏步骤**:
- Agent 产出物的'评估维度矩阵'缺失：方案只有 world-graph（结构）+ combat-sim（数值）+ 不变量回归集（断言），但缺叙事连贯性、对话语义死锁、任务绕过、经济平衡、趣味性五个维度的验证手段。需为每个维度定义验证手段（自动化/半自动/人工）、覆盖度目标、gap 声明。这是 Agent 产出质量能否'可验证终态'的前提。
- 五角色 Worker 分工的'评估方法论'缺失：方案按创作工序（Worldbuilder/Narrator/Behaviorist/Balancer/Continuity）拍脑袋分工，但未论证五角色 vs 单 Claude agent+工具调用 vs 其他分法（如按领域而非工序）的优劣。需做对比实验：同一创作任务分别用五角色/单 agent/三角色，对比产出质量、token 成本、迭代次数，用数据驱动分工而非先验假设。
- '世界圣经'的 schema 与自洽性验证机制缺失：方案假设 Worldbuilder 产出'世界圣经'，但未定义世界圣经的结构化 schema（门派关系图/时间线/角色档案/地理拓扑/能力体系）、未定义自洽性验证规则（如'门派 A 与门派 B 互敌则不能有师承关系'）。世界圣经是所有 Worker 的共享上下文，其质量决定下游产出质量，但方案把它当作自然语言文档而非结构化+可验证规格。
- 流式/增量反馈设计缺失：UGC 创作者期望实时反馈，但方案是'Agent 跑完整 DAG 工作流 -> 人工审批'的批处理模式。一个 CPK 的生成-评审-修订循环可能耗时数十分钟到数小时，创作者在此期间无干预手段。需设计流式输出（Orchestrator 输出中间产出如区域图/对话树骨架供创作者预览并早期干预）+ 增量创作（只重生成违反不变量的局部而非整体重跑）。
- Agent 产出版本演进的 A/B 测试与回滚机制缺失：方案有 CPK 版本与内容寻址，但未定义'Agent 生成 v2 内容 vs v1 内容的玩家体验对比'机制。UGC 内容发布后需收集玩家行为数据（留存/时长/付费）反馈到 Agent 训练/提示迭代，形成数据飞轮。当前是'生成->验证->发布'单向，缺'发布->数据收集->迭代'闭环。
- LLM 供应商锁定与模型可插拔的验证流程缺失：方案称'Claude API 主+可插拔 GLM'，但未定义'不同 LLM 产出质量基线'的评估方法。换模型可能产出质量骤降，需模型评估门禁（基准创作任务集+质量阈值），而非简单 API 抽象层。
- 'Agent 产出与人类创作内容的混合治理'流程缺失：UGC 平台会有 Agent 产出与人类直接编辑的内容混合，方案有 provenance 记录来源，但未定义'Agent 产出内容的差异化审核标准'（是否比人类内容更严格/宽松）、'人类修改 Agent 产出后的版权与责任归属'。

**更优方案**:
- [验证基底架构] combat-sim 用独立纯 Python 数值模型从 LPC seed，ECS 落地后替换内核 -> 改为'resolve_attack 纯函数优先'策略：第一阶段即从 LPC attack.c/combatd.c 提取 resolve_attack 为无副作用的纯 Python 函数（输入参与者组件快照+seed，输出 CombatRoundResult），combat-sim 直接调用此纯函数。这与 ECS 迁移解耦（纯函数不需要 ECS 运行时），但保证验证与未来真实引擎同源。对'验证模型即规格'原则：combat-sim 验证的内容，上线时跑的是同一个 resolve_attack。（解决验证与实际脱节的双重标准问题。纯函数提取是 combat 迁移阶段2.4 的前置工作（CombatContext 快照边界本就需要），提前做不浪费。独立模型则会被丢弃，是沉没成本且制造 false confidence。）
- [Agent 编排引擎] LangGraph 单进程起步，多实例靠 Postgres advisory lock hack -> MVP 阶段：直接用 asyncio + Claude SDK + 自建轻量 state machine（状态持久化到 PG），不引入 LangGraph 抽象层。中期：评估迁移到 Temporal/DBOS durable execution，原生支持长时运行/human-in-the-loop/可观测/可重放/多实例。明确 LangGraph 仅作为'过渡原型'而非终态选型。（用户有公司资源且目标是业界标杆。LangGraph 的 checkpoint 是为崩溃恢复设计，不为创作工作流的中断-恢复-人类介入设计。durable execution 才是创作工作流引擎的正确抽象。MVP 不用 LangGraph 能减少一层抽象债务，中期用 Temporal 能支撑多创作者并发与可观测性。advisory lock 是 hack，Temporal 是 architecture。）
- [Worker 分工与上下文管理] 五角色 Worker 各持世界圣经全量上下文并行生成 -> 改为'分层上下文 + 工具增强单 agent + 专项 worker 按需唤起'：(a) 单一 Orchestrator agent 持有世界圣经摘要（RAG 检索全文），按需调用 world-graph/combat-sim 工具验证；(b) 仅对验证失败的专项（如 Balancer 数值、Behaviorist condition 状态机）唤起专项 worker，传入精准上下文而非全量；(c) 用 LLM-as-judge 替代独立的 Continuity 角色做事后审查，生成时用 structured output + 实体关系约束注入做'生成时约束'。五角色保留为'能力清单'而非'固定进程'。（解决交接信息损失、5x context 成本、世界圣经超窗口三大问题。LLM 的强项是持全局上下文连续创作，强行按工序切分是反模式。'生成时约束'比'生成后审查'更高效（避免修订震荡）。五角色作为'能力'而非'进程'保留了专业化收益。）
- [评估方法论] 只有 world-graph + combat-sim + 不变量回归集 -> 建立'质量维度 x 验证手段 x 自动化程度'评估矩阵：(1) 结构合法--pydantic/world-graph（全自动）；(2) 数值分布--combat-sim（全自动）；(3) 经济平衡--多 agent 玩家行为仿真（半自动，模拟刷钱/通胀）；(4) 任务逻辑健全性--状态机模型检查（半自动，检测绕过/死锁，可用 nuXmv/SPIN）；(5) 叙事连贯--实体关系图+时序约束+LLM-as-judge（半自动）；(6) 趣味性--自动化 playtest agent + 人工抽样。每个维度声明覆盖度目标与 gap。（当前方案用'可验证终态'掩盖了验证覆盖度幻觉。UGC 内容质量核心是叙事/玩法/平衡，不只结构和数值。没有评估矩阵就无法回答'Agent 产出是否真的可发布'。）
- [创作者体验与反馈] Agent 跑完整 DAG 工作流后产出 CPK，人工审批 -> 改为'流式创作 + 实时干预'：Orchestrator 流式输出中间产出（如区域图先于对话树先于数值表），创作者可随时介入修改并触发增量重算。用 operational transform/CRDT 支持'Agent 生成 + 人类编辑'并发。提供'创作 checkpoint'让创作者保存中间状态、分支探索。（UGC 创作者期望实时反馈而非等数十分钟。完整 DAG 跑完才发现方向错误是巨大浪费。流式创作是 AI Dungeon/ChatGPT 的体验基准，本方案不能低于。）
- [创作者经济与版权] provenance 记录 agent_id/model/prompt_hash，CC-BY-SA-4.0 -> 设计'创作者经济层'：(a) CPK 不可变快照 + provenance 链支持'衍生创作版税'（如 A 基于 B 的门派创作新剧情，B 获得分成）；(b) Agent 产出与人类产出的版权标记区分，明确责任归属（审批通过=平台承担，否则创作者承担）；(c) 交易市场（CPK 交易/订阅/打赏）；(d) Agent 产出原创性检测（与既有内容相似度阈值）。（没有创作者经济就没有 UGC 飞轮（Roblox 验证）。版权/责任边界不清会阻碍创作者参与和商业化。provenance 是技术层，经济层才是平台飞轮。）

**greenfield重审**:
- 差分测试语义已变：greenfield 下 LPC 是 spec/source 不是'运行中需对照的系统'。golden trace 仍可录制（若 LPC MudOS 能跑），但'运行中 LPC 作为持续真相源'的假设不成立--新项目不依赖 LPC 运行时长期共存。差分测试定位应从'回归对照'调整为'迁移验证工具'（阶段性，迁移完成后即退役），而非'长期双运行'基础设施。这降低了差分测试基建的长期运维负担，但提高了其对单次迁移验证的质量要求（因为没有长期对照兜底）。
- 迁移适配层/双运行假设应彻底去除：greenfield 无需'LPC 适配器桥接期'、无需'双栈过渡一致性测试（§31d）'。Telnet 适配器/双栈过渡是增量重构产物，greenfield 下前端直接从语义事件起步，不需要保留 LPC message_vision 经 Telnet 适配器作为过渡真相源。这大幅简化了前端状态同步子系统设计，但要求 message_vision 模板池抽离必须一次性完成而非'渐进替换'--这与文档§30'数年级 backlog 渐进替换'冲突，需重新评估工时。
- combat-sim 从 LPC seed 仍成立（LPC 是数据源），但'独立纯 Python 数值模型'的脱节风险在 greenfield 下更突出：因为没有'运行中 LPC 战斗'可对照，combat-sim 的正确性只能靠'与 LPC 源码规格的静态比对'，而非'与运行时差分'。这强化了'应直接提取 resolve_attack 纯函数'而非'独立模型'的论断--greenfield 下没有运行时兜底，验证模型必须即规格。
- '忠实迁移侠客行'与'Agent 创作新题材'是两个目标，greenfield 下应明确分离而非混为一谈。侠客行迁移是'按 LPC 规格实现'（确定性工程任务，Agent 辅助解析+转译），新题材创作是'Agent 原创生成'（非确定性创作任务，Agent 主导）。两者对 Agent 架构、验证严格度、审批门要求完全不同：迁移任务要求高保真差分测试，创作任务要求质量评估矩阵。当前方案把两者塞进同一 Agent 协作框架，职责不清。
- greenfield 下 Agent 协作创作没有'与现有 LPC 内容并存'的约束，Agent 可从零生成新题材世界。但这也意味着'世界圣经'从零构建，没有既有内容可参照--Agent 必须先生成并固化一个自洽的世界圣经，再基于它创作。这把'世界圣经生成与固化'从'隐含前置'提升为'显式里程碑'，应单列。当前方案假设世界圣经由 Worldbuilder 角色产出，但未定义世界圣经的 schema、自洽性验证、版本演进机制--这是 Agent 创作的根，缺失会级联失败。
- greenfield 重新审视'业界标杆'定位：增量重构语境下'标杆'是'最成功的 MUD 现代化迁移'；greenfield 语境下标杆应升级为'首个 AI 原生的 UGC 游戏世界平台'。这意味着评估基准不是'比 LPC 跑得快/稳'，而是'比 Roblox/AI Dungeon/Inworld 的创作体验与产出质量更好'。技术选型应以此标杆校准（如 LangGraph 是否配得上'AI 原生平台标杆'，还是该用 Temporal+durable execution）。

**业界标杆评估**: 距业界标杆的差距与真正的差异化能力。当前方案的标杆定位（'以 DSL 为契约把 LLM 非确定性收敛到可验证终态'）方向正确但被过度声称：能收敛的只有'结构合法+数值分布'，收敛不了叙事连贯/对话语义死锁/任务绕过/经济平衡/趣味性，而后者才是 UGC 内容质量的承重维度。对标业界：(1) AI Dungeon 纯 LLM 无结构会崩坏--本方案 DSL 收敛是对的方向，但长上下文'世界圣经'退化风险同源未解；(2) Inworld/Convai 做 NPC 实时对话 AI--本方案 Ink 对话树是'结构化但僵化'，NPC 实时交互质量是倒退，标杆应做'LLM 驱动 NPC 实时对话 + DSL 约束世界状态'的混合（NPC 自由对话但状态变更受 DSL 契约约束）；(3) Roblox Lua UGC 无 AI 辅助--本方案 DSL+Agent 是差异化优势，但 Roblox 成功核心是创作者经济（变现），本方案完全缺失，没有创作者经济就没有 UGC 飞轮；(4) 真正的业界标杆差异化能力应该是：'多 Agent 协作创作 + LLM 实时 NPC + DSL 确定性世界状态 + combat-sim/经济仿真双验证 + 创作者经济 + provenance 版权链'的完整闭环，当前方案只有其中'Agent 创作+DSL 契约'两环，缺实时 NPC、经济仿真、创作者经济三环。能真正让它成为标杆的不是'又多一个 Agent 编排框架'，而是'首个把确定性世界仿真（combat/经济）与 LLM 非确定性创作用验证契约深度耦合、且内置创作者经济与版权链的 UGC 平台'--这个定位比当前'五个 Worker 跑 LangGraph'野心更大也更可论证。

**承重论断**:
- [high] 方案核心论点'以 DSL 为契约把 LLM 非确定性收敛到可验证终态'方向正确但被过度声称：能收敛的只有结构合法性与数值分布，收敛不了叙事连贯性/对话语义死锁/任务绕过/经济平衡/趣味性，而后者才是 UGC 内容质量承重维度。（依据: DSL schema 收敛结构合法性（pydantic 校验已验证可行），world-graph 收敛图可达性（networkx 图论性质确定），combat-sim 收敛数值分布（数值模型可确定）。这三类是可机器验证的。）
- [high] combat-sim 用独立纯 Python 数值模型与方案自身的差分测试原则形成双重标准：迁移要行为等价，验证模型却可简化。验证信号失真比没验证更危险。（依据: 方案自己要求 LPC->Python 迁移用 golden trace 差分测试保证行为等价（修正§V/§9/§10），但 combat-sim 独立模型无对应要求。我核实 condition.c 位聚合与 combatd.c 递归 while 循环，若独立模型简化这些机制则验证失真。）
- [medium] LangGraph 是 LLM 应用编排思维不是创作工作流引擎思维；创作是长时运行/human-in-the-loop/可中断恢复的 durable execution 问题，应用 Temporal/DBOS 而非 LangGraph+advisory lock。（依据: LangGraph 文档明确是单进程状态机库，checkpoint 为崩溃恢复设计。创作工作流的中断-恢复-人类介入是 durable execution（Temporal/DBOS）领域。advisory lock 是串行化 hack 不是多实例 architecture。）
- [medium] 五角色按工序分工引入交接信息损失且 5x context 成本，未论证优于单 agent+工具调用；Continuity 事后审查应改为生成时约束（structured output+实体关系约束注入）。（依据: LLM 强项是持全局上下文连续创作。五角色各加载世界圣经=5x 成本。我核实侠客行 21 门派/6414 房间/472 技能规模，世界圣经易超 200k tokens 单次窗口。）
- [high] 方案缺 combat-sim 与真实引擎的等价性验证、缺叙事/经济/任务逻辑的评估维度、缺收敛性退出条件，三项共同构成'验证覆盖度幻觉'--用易验证指标冒充内容质量已验证。（依据: 我核实的 hebi.c 双人和合（check_fight 递归+set_temp 共享 buff+闭包 call_out）正是'强状态多 actor 协调'，WASM 无状态定位无法表达。combat-sim 独立模型若简化递归/位聚合则脱节。）
- [medium] 'Agent 协作架构比直接用 Claude+手动编辑强'当前未被论证：需证明多角色优于单 agent、验证覆盖度远超人工、创作者体验显著优于手动编辑三点，否则用户作为 AI 主管会直接用 Claude。（依据: 方案无成本模型（五角色×多轮×世界圣经易达百万 token/CPK）、无流式反馈（批处理 DAG 耗时数十分钟）、创作者体验未论证。但 MCP 验证客观信号与 provenance 是真实增量。）