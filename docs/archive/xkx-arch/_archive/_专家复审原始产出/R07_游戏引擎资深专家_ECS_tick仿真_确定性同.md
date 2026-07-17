# 专家复审·游戏引擎资深专家（ECS/tick仿真/确定性同步/热重载/引擎工具链/性能优化；深度参与商用引擎开发，精研entt/Unity DOTS/Bevy，对自研引擎代价有清醒认识）

## 裁定
risky — 核心方向正确（Ray/SparseSet/权威状态库/tick保留等修正质量很高），但作为"业界标杆自研引擎"有三个致命缺口：①纯Python作为引擎主语言未正视GIL/GC/确定性三重天花板（实测Python 3.12标准GIL，未提PEP 703 free-threaded，未考虑Rust核心+Python脚本混合架构）；②引擎工具链（场景编辑器/实体检视器/replay scrubber/profiler/热重载系统）完全缺失——这是标杆引擎与玩具的分水岭；③ECS+Actor+DSL+Agent四范式堆叠过度复杂，标杆引擎通常聚焦1-2范式做到极致。

## 业界标杆评估
当前方案距业界标杆差三件决定性能力，缺一不可称标杆：(1) **引擎工具链完全缺失**——Unity/Unreal/Bevy/Godot 的分水岭不是运行时性能而是工具链：场景编辑器、实体检视器、tick 时间线回放器、ECS 调度图可视化、AI 行为树调试器、性能 profiler。当前方案是服务端架构不是引擎架构，Prometheus metrics 不能替代 in-engine inspector。这些工具应作为阶段0一等公民交付，而非事后补。(2) **语言选型天花板未被正视**——Python 作为引擎主语言在 GIL（单线程 tick 阻塞全网 I/O）、GC（百万短命对象/ tick）、确定性（hash 随机化、对象 id 不稳定）三重天花板下无法达到业界标杆的确定性回放保真与单分片吞吐。业界标杆引擎（Bevy=Rust、Unity DOTS=C++/Burst、Godot=C++）全部用系统级语言做核心。真正能让它成为标杆的差异化能力是：**Rust 确定性仿真核心 + Python 创作层 + 完整工具链 + UGC/Agent 协作**——这个组合目前业界无人做到，武侠 MUD 的语义丰富度 + UGC 创作生态 + Agent 协作是真正的护城河。但纯 Python 路线无法承载"标杆"二字，它在第一年就会撞上 GIL+GC 天花板导致单分片容量不达标、tick 抖动无法消除、确定性回放脆弱。另外确定性回放在 Python 下做到业界标杆几乎不可能：PYTHONHASHSEED 随机化使 set 迭代跨进程不稳定（实测 PYTHONHASHSEED=1 但生产默认 random）、CPython 的 dict 虽 3.7+ 插入有序但 GC 触发时机不确定影响 wall-clock 确定性、float 运算虽 IEEE754 但跨平台（x86 vs ARM）的 FP 精度差异在长链 RNG 消耗下放大。Rust 核心可从语言层面消除这些。

## 缺口
- **[high]** 引擎工具链完全缺失（最严重缺口）
  -> 修复：业界标杆引擎（Unity/Unreal/Bevy/Godot）与玩具的分水岭是工具链。方案完全没有：①场景编辑器（房间拓扑可视化/出口连线拖拽）②实体检视器（组件树实时查看/运行时修改）③tick 时间线回放器（CombatContext 快照加载+逐 tick 步进+状态 diff）④ECS 调度图可视化（System 依赖与执行顺序）⑤性能 profiler（per-system tick 耗时火焰图）⑥AI 行为树调试器（auto_perform 决策树可视化）。仅有 Prometheus metrics + OTel traces 是运维可观测，不是引擎可观测。建议将工具链列为阶段0一等公民，而非事后补丁。没有 inspector 和 replay scrubber，调试 8400 文件迁移的行为偏差将极其痛苦。
- **[high]** GIL/freethreaded Python 讨论缺失——Python 3.13 PEP 703 free-threaded build 是 Python 游戏引擎的关键变量，全文仅 §S 提一次 GIL 且只用于下调容量预期
  -> 修复：greenfield 项目应严肃评估：①Python 3.13t/3.14t free-threaded build（移除 GIL，3.13 已发布 experimental free-threaded）；②free-threaded 下 asyncio + 多线程 tick 的可行性；③若 free-threaded 成熟度不足，Rust 核心 + Python 脚本的混合架构（PyO3）。将语言选型作为阶段0 的架构决策点，而非默认 Python 3.12。当前 Python 3.12 标准版在 3000 并发下，GIL 导致 tick 计算期间所有网络 I/O 冻结——这不是优化问题，是架构天花板。
- **[high]** 无性能预算（performance budget）定义——方案说'按 2000-3000 并发规划'但从未定义 tick 预算（多少 ms/tick）、实体预算（多少实体/房间）、组件预算（多少组件/实体）、事件预算（多少事件/tick）
  -> 修复：标杆引擎从性能预算反推架构。建议定义：tick 预算 50ms（20Hz）或 100ms（10Hz）；每 tick combat 计算 <10ms；每 tick delta 序列化+广播 <20ms；每 tick 条件推进 <5ms；单房间实体上限；单实体组件上限。实测：纯 Python 3000 实体 1500 attacks/tick 仅 1.93ms（compute 很快），但 asyncio 事件循环在 tick 计算期间完全阻塞网络 I/O。瓶颈不是 compute 而是 I/O 多路复用与 GIL 的冲突。没有预算就无法做架构权衡。
- **[high]** Python 确定性回放的隐性风险未讨论——CombatContext + seeded RNG 设计正确，但未讨论 Python 特有的非确定性
  -> 修复：Python 3.7+ dict 虽插入有序，但 set 迭代顺序受 PYTHONHASHSEED 影响（默认 random，跨进程/跨重启不一致）。do_attack 中 22 处 random() 调用 + 组件查询若涉及 set 迭代则回放分叉。必须：①固定 PYTHONHASHSEED=0；②ECS 查询结果排序后迭代（禁用 set 直接遍历）；③CombatContext 快照中所有集合序列化为有序数组。Rust 核心可从语言层面消除此风险。
- **[high]** Rust 核心 + Python 脚本的混合架构从未被评估——greenfield 是考虑此方案的最佳时机，但文档仅因'UGC 作者不会写 Rust'就否定了整个方向
  -> 修复：重新评估：Rust 核心（ECS/tick/combat/serialize 热路径）+ Python 脚本层（DSL/Agent/UGC/admin）。这正是 Bevy（Rust ECS）+ 脚本、Unity DOTS（C++/Burst）+ C# 的业界标准模式。PyO3 使 Rust-Python 互操作成熟。热路径 10-100x 性能 + 无 GIL 真并行 + 内存安全 + 更可靠的确定性回放。UGC 作者写 Python，平台核心用 Rust，两全其美。greenfield 下这是'标杆 vs 玩具'的分水岭决策。
- **[high]** asyncio 单线程事件循环的 CPU-bound tick 阻塞问题未讨论——tick 仿真期间所有 WebSocket I/O 冻结
  -> 修复：asyncio 是协作式调度，CPU-bound tick 计算（即使仅 10-50ms）期间无法处理网络 I/O。3000 客户端的心跳/重连/命令全部积压。解决方案：①tick 计算移至独立进程/线程（但 GIL 限制线程）；②free-threaded Python；③Rust 核心通过 PyO3 释放 GIL；④将 tick 拆分为子步骤，每步之间 yield 给事件循环（增加延迟抖动）。当前方案将 Ray actor 作为分布式方案，但单节点内多进程/多线程的 CPU-bound 处理完全未讨论。
- **[medium]** 热重载（hot reload）作为引擎一等能力被严重低估——仅在 DamageFormula 和 Checkpoint 处提了两句
  -> 修复：标杆引擎的热重载是系统级能力：组件 schema 变更后运行中实体自动迁移、System 逻辑更新后无需重启、DSL CPK 热加载到运行中世界、技能定义 YAML 修改即时生效。LPC 的 update_object/efun reload 本身就有热重载传统，新引擎应超越而非退化。需要：①组件版本化 + schema migration 运行时执行；②System 模块热替换协议（标记 dirty + 下个 tick 边界切换）；③CPK 热加载（加载新版本不影响已运行实例，新实例用新版本）；④热重载期间的状态一致性保证（战斗中禁止已识别但需扩展为全系统协议）。
- **[medium]** environment() 统计数据有重大误差——§40 称'实测 environment()=664'，但实际全库 3777 处，是所称值的 5.7 倍
  -> 修复：实测 grep -c 'environment(' 全库 3777 处（1312 文件），environment()-> 直接解引用 120 处，均与'664'不符。§40 是'承重修正 40'（最高价值产出之一），其核心论据 environment()=664 本身错误。虽然 68771 箭头调用数（实测 69697 含注释）作为主线工作量指标仍然成立，但 environment() 的误判可能影响迁移面估算的子结构（环境交互的跨对象调用图深度被低估）。建议重新统计 environment() 的实际调用图，确认迁移面估算基准数据无误。
- **[medium]** GC 压力未评估——每 tick 创建大量短命对象（CombatRoundResult/Effect/delta ops/msgpack bytes）
  -> 修复：Python 的 GC 是代际标记-清除，大量短命对象触发频繁 minor GC（每次 ~5-20ms 暂停）。3000 实体/tick 产生数千短命对象。实测 GC disable 后 100k 操作 138ms，GC enable 后预计 1.5-2x。需要：①对象池化（CombatRoundResult/Effect 预分配复用）；②__slots__ 减少对象内存占用；③分代 GC 阈值调优；④或用 Rust 核心规避 GC。标杆引擎对 GC 抖动零容忍——这是从'能跑'到'标杆'的关键差距。
- **[medium]** 闭包迁移面统计只计 call_out 闭包（147 处），忽略全库 1979 处闭包的迁移需求
  -> 修复：实测 call_out+start_call_out 闭包 147 处（与文档 144 吻合），但全库 (: ...) 闭包语法共 1979 处/897 文件。§29 识别了 104 文件 dbase 闭包值，但 perform 回调/事件处理器/条件谓词中的闭包未计入迁移面。建议补全闭包全量分类台账（call_out/dbase/perform/event_handler 四类），重算闭包迁移工作量。
- **[medium]** ECS 在 Python 中的性能论证错误——SparseSet 在 C++ 的优势是 cache locality（Archetype）和 SIMD，Python 中不存在这些优势
  -> 修复：Python dict + dataclass 的 SparseSet 每次 query 是 dict 查找（~100ns）+ 属性访问（~50ns/字段），与 C++ SparseSet（~10ns 查找 + 连续内存）性能特性完全不同。ECS 在 Python 中的价值是代码组织（组合优于继承、组件动态挂卸），不是性能。应明确：ECS 是架构选择不是性能优化。若需性能，应用 __slots__ + numpy 结构化数组 + 批量向量化（VitalsSystem 用 numpy 同时更新 1000 实体的 qi）。

## 遗漏步骤
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

## 更优方案
- **[引擎核心语言]** 纯 Python 3.12 asyncio + uvloop，自研 SparseSet ECS，GIL 限制单分片吞吐与确定性回放保真 -> **Rust 核心（PyO3 绑定）+ Python 脚本层：ECS 运行时/tick 仿真器/战斗解析器/序列化/网络层用 Rust，DSL 编译器/Agent 编排/UGC 脚本/admin 用 Python。参考 Bevy 架构（Rust ECS + bevy_replicon 确定性同步）。**
  理由：实测纯 Python 战斗计算 1.3μs/attack 看似够快，但 GIL 下 tick 处理阻塞全网 I/O + GC 抖动是真实天花板。Rust 给 10-100x 热路径性能、无 GIL 真并行、确定性回放从语言层面可靠、内存安全无 GC pause。greenfield 下 Rust 投资回报率最高（hot path 集中在 ECS+tick+combat+serialize 四个模块，工作量可控）。业界标杆引擎（Bevy/Unity DOTS/Godot）全部用系统级语言做核心。
- **[引擎工具链]** 无场景编辑器/实体检视器/回放时间线/profiler/AI 调试器。仅 Prometheus metrics + OTel traces -> **阶段0 同步交付：(1) Web 场景编辑器（房间图可视化编辑+exits 拖拽连线）；(2) 实体检视器（组件树实时查看+热修改）；(3) tick 时间线回放器（CombatContext 快照加载+逐 tick 步进+状态 diff）；(4) ECS 调度图可视化（System 依赖与执行顺序）；(5) AI 行为树调试器（auto_perform 决策树可视化）。**
  理由：工具链是标杆引擎与玩具的分水岭。Unity/Unreal/Bevy/Godot 的核心差异化不是运行时而是工具链。没有 inspector 和 replay scrubber，调试 ECS 组件交互和战斗回放只能靠 printf，8400 文件迁移的调试成本将失控。工具链应作为一等公民而非 backlog。
- **[并发模型]** 单进程 asyncio + GIL，tick 处理期间阻塞所有网络 I/O。未讨论 free-threaded Python 或多进程单节点 -> **三选一：(a) Rust 核心（天然无 GIL）；(b) Python 3.13t free-threaded build（PEP 703，移除 GIL）；(c) 多进程单节点（tick 计算进程 + I/O 进程，共享内存/IPC 通信）。无论哪种都要在 tick 处理与网络 I/O 间实现真并行。**
  理由：实测 tick 计算 7ms 看似只占 0.4% 预算，但这 7ms 期间 asyncio 事件循环完全冻结——3000 WebSocket 客户端全部等待。高频心跳/重连/命令在这 7ms 窗口积压。GIL 下无法用线程解决，只能靠语言级或进程级隔离。这是从 2000 到 10000 并发的关键杠杆。
- **[确定性回放]** CombatContext 快照 + seeded RNG + 分层承诺（新内容位等价/遗留内容行为等价）。未讨论 Python 特有确定性风险 -> **确定性四重保障：(1) PYTHONHASHSEED=0 固定 + 禁用 set 迭代（用排序数组）；(2) 确定性序列化（固定 key 顺序，禁用 dict 默认迭代）；(3) CombatContext 快照 + seeded RNG + 禁止战斗中途引入快照外输入（已有）；(4) 跨平台 FP 一致性策略（固定 x87/SSE 模式或用定点数）。Rust 核心可从语言层面消除前两项。**
  理由：Python 的 PYTHONHASHSEED 随机化使 set 迭代跨进程不稳定（实测默认 random），dict 虽 3.7+ 插入有序但 GC 触发时机影响 wall-clock。do_attack 22 处 random() 消耗序列对迭代顺序敏感。CombatContext 设计正确但 Python 实现层有隐性分叉风险。
- **[ECS 性能策略]** 自研 SparseSet ECS，dataclass 组件，dict 存储。性能论证基于 C++ ECS 理论（O(1) 查询/动态挂卸） -> **Python ECS 优化三招：(1) 热组件用 __slots__ + SOA（struct-of-arrays，numpy array 后端）；(2) 批量遍历用 numpy 向量化（1000 实体的 VitalsSystem.update 用 numpy 而非 Python 循环）；(3) Rust ECS 后端（PyO3 暴露 query 接口，Python 侧零拷贝访问 Rust 内存）。**
  理由：Python dict + dataclass 的 ECS 在 C++ 意义上的 SparseSet 性能优势不存在（无 cache locality、无 SIMD、GIL 阻止并行）。实测 1.3μs/attack 已可接受但含 GC 开销后会恶化。SOA+numpy 可将 VitalsSystem/HealSystem 这类批量操作向量化，5-10x 加速。Rust 后端是终极方案。
- **[范式收敛]** ECS + Actor + DSL + Agent 四范式堆叠，35 次范式关键词在总纲中。每范式引入独立概念体系/工具/调试方式 -> **两范式聚焦：ECS（仿真核心）+ DSL（创作契约）。Actor 退化为 ECS 的分布式传输层（非独立范式，Ray actor 仅作为 ECS World 的跨进程容器）。Agent 是 DSL 的生产端消费者（非运行时范式，LangGraph 编排器是 DSL 编译器的前端工具）。**
  理由：标杆引擎聚焦少数范式做到极致：Bevy=纯 ECS、Unity DOTS=ECS+Job System、Godot=Node Tree。四范式堆叠的运维与认知成本在单人/小团队下不可持续。Actor 作为 ECS 的传输层而非独立范式可消除 Actor-ECS 边界映射问题（§3 query_entire_dbase 问题本质是 Actor 状态与 ECS 组件的重复表示）。

## greenfield 重审
- 迁移适配层（subsystem 3 '单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System'）是增量重构假设。greenfield 下应：先设计完整 Python/Rust ECS + System 架构 → 再将 LPC 内容作为数据迁移到新引擎，而非建适配层逐步替换。适配层是过渡债务，greenfield 不必承担。
- 差分测试框架的'录制 LPC 侧命令流为 golden trace'假设需要运行中的 LPC 系统。greenfield 下 LPC 是 spec 不是运行系统。可改为：①一次性从 LPC 提取 golden trace（不需长期双运行）；②将 golden trace 固化为测试 fixtures；③行为等价测试针对 spec（'do_attack AP/(AP+DP) 概率模型'）而非针对'旧系统输出'。双栈过渡一致性测试（§31d 'Telnet vs Web 互为投影'）同理可去除。
- '先修复 securityd.c 已知 bug 恢复运维可用'（§19/阶段0）是增量假设。greenfield 下不运行 LPC 系统，不需修 LPC securityd。应直接设计新 PermissionService（fail-closed + RBAC/ABAC + 能力令牌），securityd 的 bug 作为'旧系统缺陷清单'参考而非修复任务。阶段0 的 securityd 修复任务可删除。
- Telnet 适配器作为'过渡期真相源'（§30/子系统1/子系统9）是增量假设。greenfield 下主客户端是新 Web 前端，Telnet 是可选的兼容输出（如果需要的话）。message_vision 的 1626 文件应直接迁移为 msg_key 模板池，而非保留 LPC message_vision 作为真相源经 Telnet 适配器桥接。双栈过渡的一致性测试（§31d）可去除。
- 阶段2 的'逐子系统迁移'路径（Query → Vitals → Attribute → Combat，每步保持游戏可运行）是增量假设。greenfield 下不需'保持游戏可运行'——可以一次性设计全部 System 接口 + 组件 schema，然后批量迁移内容。但差分测试仍有价值：它验证'新引擎行为 vs LPC spec'而非'新系统 vs 运行中的旧系统'。
- Ray 作为分布式 actor 运行时的选型（§5 修正后）在 greenfield 下可重新评估。若选择 Rust 核心，分布式层可用 Rust 原生 actor 框架（如 ractor/actix）而非 Ray（Python 绑定有性能开销 + GIL 限制）。Ray 的优势是 Python 原生，但若核心已非纯 Python，Ray 的价值降低。greenfield 可选：Rust 核心 + Rust 分布式层 + Python 仅用于 DSL/Agent/admin。
- '单进程 asyncio 核心循环'（阶段1）作为不可跳过的起点，在 greenfield 下可重新考虑。若选择 Rust 核心，阶段1 应是'Rust ECS + tick 骨架 + PyO3 绑定验证'而非'Python asyncio + Ray actor'。这改变了整个迁移路径的起点。greenfield 的自由度允许从最优技术栈起步，而非从最低门槛起步。

## 承重论断（供质证）
- **[high]** 纯 Python 3.12 作为引擎核心语言无法达到业界标杆——GIL 导致 tick 计算期间全网 I/O 冻结、GC 抖动无法消除、确定性回放在 PYTHONHASHSEED 随机化下脆弱。greenfield 应严肃评估 Rust 核心(PyO3)+Python 脚本混合架构。
  依据：实测 Python 3.12 3000 实体 1500 attacks/tick 仅 1.93ms，但 asyncio 单线程事件循环在 tick 计算期间冻结所有网络 I/O。GIL 阻止用线程解决。Python 3.13t free-threaded（PEP 703）或 Rust 核心(PyO3)是两条可行路径。业界标杆引擎（Bevy/Unity DOTS/Godot）全部用系统级语言做核心。当前方案仅 §S 提一次 GIL 且只用于下调容量预期，未作为架构决策点。
- **[high]** 自研 SparseSet ECS 在 Python 中的性能论证是错误的——Python dict+dataclass 无 cache locality/SIMD/真并行，ECS 在 Python 是架构选择不是性能优化。CombatContext+seeded RNG 的确定性回放在 Python 下有隐性分叉风险（PYTHONHASHSEED 随机化 set 迭代）。
  依据：实测 PYTHONHASHSEED 默认 random，set 迭代跨进程不稳定。do_attack 内 22 处 random()（实测 combatd.c 全文件 29 处）的消耗序列对组件查询迭代顺序敏感。CombatContext 快照设计正确但未包含 Python 环境配置约束。
- **[high]** 方案缺少引擎工具链（场景编辑器/实体检视器/tick replay scrubber/profiler），这是标杆引擎与玩具的分水岭。工具链应作为阶段0一等公民交付。
  依据：Unity/Unreal/Bevy/Godot 均有场景编辑器+实体检视器+replay scrubber+profiler。当前方案仅 Prometheus metrics+OTel traces（运维可观测非引擎可观测）。无 inspector/replay 调试 8400 文件迁移的行为偏差将极其痛苦。
- **[high]** §40 '承重修正'声称 environment()=664 是错误的——实测全库 3777 处，是所称值的 5.7 倍。这个'最高价值产出'的修正本身包含事实错误。
  依据：实测 grep -c 'environment(' 全库 3777 处（1312 文件），environment()-> 直接解引用 120 处。§40 是'承重修正 40'最高价值产出之一，其核心论据错误。68771 箭头调用数（实测 69697 含注释）仍成立作为主线指标。
- **[high]** greenfield 0-1 框架下应去除迁移适配层、双栈过渡、securityd 修复等增量假设。LPC 是 spec 不是运行系统，应先设计完整引擎再迁移内容，而非建适配层逐步替换。
  依据：ECS=35次关键词在总纲中。Actor-ECS 边界映射问题（§3 query_entire_dbase 本质是 Actor 状态与 ECS 组件重复表示）。单人/小团队下四范式运维不可持续。标杆引擎聚焦少数范式：Bevy=纯ECS、Unity DOTS=ECS+Job、Godot=Node Tree。
- **[medium]** ECS+Actor+DSL+Agent 四范式堆叠过度复杂，应收敛为 ECS（仿真核心）+DSL（创作契约）两范式，Actor 降级为 ECS 分布式传输层，Agent 是 DSL 的生产端消费者。
  依据：Ray actor 仅作为 ECS World 跨进程容器（非独立仿真范式）。LangGraph 是 DSL 编译器前端工具（非运行时范式）。§3 query_entire_dbase 问题是 Actor 状态与 ECS 组件重复表示的症状，收敛范式可消除。

## 优先建议
- 【最高优先】在阶段0 做语言选型决策评审：Python 3.13t free-threaded vs Rust 核心(PyO3)+Python 脚本 vs 纯 Python 3.12。出具 do_attack ECS 版的性能基准对比（Python vs Rust）。这是不可逆架构决策，决定能否达到'业界标杆'。当前默认纯 Python 3.12 是未经评审的假设，GIL 是不可绕过的天花板。
- 【最高优先】将引擎工具链列为阶段0 一等公民：场景编辑器、实体检视器、tick replay scrubber、ECS 调度图可视化。这是标杆引擎与玩具的分水岭。没有 inspector/replay 调试 8400 文件迁移的行为偏差将失控。建议先做 replay scrubber（基于 CombatContext 快照），ROI 最高。
- 【高优先】定义性能预算（performance budget）并做基准测试：tick 预算 50-100ms、combat 计算 <10ms/tick、delta 序列化 <20ms/tick。当前'2000-3000 并发'无预算支撑。实测纯 Python 3000 实体 1500 attacks 仅 1.93ms（compute 不是瓶颈），但 asyncio tick 期间网络 I/O 冻结 + GC 抖动是真实约束。预算定义后才能判断是否需要 Rust 核心。
- 【高优先】greenfield 重新审视迁移路径：去除迁移适配层、双栈过渡、securityd 修复等增量假设。改为：先设计完整 ECS+System 架构 → 再将 LPC 内容作为数据迁移。差分测试改为'针对 spec 的行为等价测试'而非'针对运行中 LPC 的回归测试'。
- 【高优先】范式收敛到 ECS+DSL 两范式：Actor 降级为 ECS 分布式传输层（非独立范式），Agent 是 DSL 的生产端消费者（非运行时范式）。减少运维与认知成本。明确四范式边界定义文档。
- 【中优先】修复 §40 environment() 统计错误：实测 3777 处而非 664 处。重新验证迁移面估算的子结构数据准确性。
- 【中优先】补全闭包迁移台账：call_out 闭包 147 处（已计）+ dbase 闭包 104+ 文件（已计）+ perform/event/condition 回调闭包（未计，全库共 1979 处闭包）。重算闭包迁移工作量。
- 【中优先】确定性回放验证实验：在 Python 中实现最小 do_attack 回放器，验证相同 seed+CombatContext 跨进程/跨重启能否位等价。固定 PYTHONHASHSEED=0 + 禁 set 迭代。若失败则强化 Rust 核心论证。
