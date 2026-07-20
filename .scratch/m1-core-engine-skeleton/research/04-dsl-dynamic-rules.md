> 本文是 2026-07-19 M1 扩展调研的**原始 subagent 输出**（DSL 动态规则调研员），完整保留，未做二次精简。汇总与 scope 决策见 [../research-m1-extension-items-npc-nature.md](../research-m1-extension-items-npc-nature.md)。
>
> 立场：LPC 与旧方案是设计灵感与术语参考，不是规格源（ADR-0001）。

---

完全清楚了。现在确认几个关键事实用于报告：

- `World` 是纯数据容器，**没有任何事件总线/钩子注册机制**。`should_quit` 是唯一的"全局引擎态"。
- `TickLoop` 只挂 `save_fn`，`advance()` 里没有"分发 tick 事件给订阅者"的接缝。
- `commands.execute` 是 `handler(world, player_id, intent)` 直接调用，**没有任何 before/after 钩子环绕**。
- 命令处理函数**直接 mutate 组件**（`door.state = ...`、`position.room = ...`、`container.items.add/discard`），没有任何"前置校验可否决"或"后置通知"的接缝。

这意味着 ADR-0004 的"声明式 policy + Protocol 钩子 + 注册表注入"手法要推广到非战斗系统，**当前 M1 代码缺一个核心基础设施：事件分发/钩子环绕层**。这正是报告要建议 M1 预留的核心。

信息已经足够。现在产出报告。

# M1 阶段 DSL 动态规则与自定义逻辑表达--调研决策输入报告

> 调研对象：新引擎 M1 内部过渡 DSL（`engine/data/m1_default_scene.yaml` + `engine/src/mud_engine/scene_loader.py`）如何在 M1 打磨扎实，重点是"如何表达运行时动态规则与自定义逻辑"。
> 输入文档：mvp-scope 03/02 号票、ADR-0004、旧 DSL 四层方案、01 避坑清单、M1 spec、当前 M1 实现代码。外部引擎参考基于既有知识（WebSearch 在本环境未返回实质结果），已标注。

---

## 一、旧方案与避坑清单的核心结论提炼

### 1.1 旧方案四层结构是什么、为什么放弃、什么仍值得吸收

**旧四层结构**（`docs/archive/xkx-arch/_archive/03-DSL-UGC与Agent协作.md`）：

| 层 | 内容 | 覆盖面目标 |
|---|---|---|
| 层0 | YAML 声明式场景数据（房间/NPC/技能/条件） | 60%+，LPC 2482 个 replace_program 纯声明房 |
| 层1 | 事件规则 `condition -> action`（when/do 表达式） | init/add_action/valid_leave/accept_object 钩子 |
| 层2 | Ink 对话树 + 交易原子节点 | inquiry（424-434 个）的"询问->设旗->收物->交付"流程 |
| 层3 | WASM / 受限 Python 脚本逃生舱 | 双人和合、perform 状态机等复杂逻辑，KPI <15% |

全部编译为 JSON IR，经四道校验（Schema / Capability / ResourceBudget / Dependency）后注册运行。

**放弃沿用的理由**（03 号票）：旧四层是为"全量复刻《侠客行》8412 文件"量身设计的目标，新目标是题材无关引擎 + 轻量题材包 MVP，不复刻、不做行为等价（ADR-0001），旧四层的"层2 Ink 对话树 + 层3 WASM 逃生舱 + CPK provenance 溯源链 + MCP world-graph/combat-sim 双验证 server + LangGraph 五角色 Agent 编排"这一整套是服务于"大规模存量迁移 + Agent 协作创作"的，MVP 不需要。强行沿用会把整个旧方案的技术栈（Lark+pydantic+Ink+wasmtime+LangGraph+LangChain+Celery+Redis+FastAPI+MinIO+MCP，§T4 已点名的 14+ 组件）背进新项目。

**仍值得吸收的设计思想**（这些是"与具体目标无关的工程判断"）：

1. **分层混合 DSL**（旧方案二节开头的统计论据）：约 30% 是纯数据可声明式，70% 含事件/对话/定时/战斗逻辑。**纯声明式无法表达所有逻辑，纯脚本对 30% 纯数据是浪费**--这条统计结论虽来自旧 LPC 库，但其"声明为主、脚本为辅"的分层动机在新题材下依然成立（任何题材都有大量纯数据房间 + 少量动态逻辑）。**新方案应保留"声明为主 + 脚本逃生舱"的分层思路，但层数与每层职责从零定。**
2. **层0 必须穷举语义字段为显式 schema**（旧方案二节末 + §B4）：LPC `set("任意键")` 是反模式（语义塞进 string bag），新 DSL 字段必须显式命名（`outdoors`/`cost`/`objects`/`resource/*` 等），不能开"任意键"口子。**当前 M1 的 YAML 已经遵循这条**（`rooms`/`items`/`npcs`/`exits`/`door`/`key` 都是显式键），值得保持。
3. **层1 规则 DSL 的原语必须够用，否则逃生舱滥用**（§22）：旧方案列出 `apply_buff_to_actors`/`weighted_random`/`monitor_cooperation` 等原语缺口。**这条不是"旧方案的具体原语清单要照搬"，而是"声明式规则的表达力边界要预先评估、预留扩充点"的方法论**--新方案在引入任何动态规则层时也要做同样的表达力校准。
4. **IR 与运行时解耦**（旧方案二节图）：创作语法编译成 IR，运行时只消费 IR。**这条在新方案下表现为"DSL 解析与执行解耦"**，M1 spec 用户故事 25 已经把"解析->意图->执行"两阶段定下来，`intent.py` 的 `Intent` 就是这个稳定中间表示。旧方案的"IR 是唯一真相源"思想已被吸收成 M1 的 `Intent`。
5. **能力令牌安全模型**（旧方案三节 + §19）：`read_world`/`say`/`move_self`/`spawn_in_scene`/`schedule` 常规，`move_player`/`destroy`/`persist`/`log_file`/`privileged_force` 危险需提升。**这套能力分级清单是 UGC 沙箱设计的直接输入**，新方案 M3 落地受限 Python 钩子时可直接参考（M1 不实现沙箱，但要为"将来钩子函数受能力令牌约束"留形状）。
6. **资源配额硬约束先行**（旧方案三节 + §M + §16/§37）：`fuel`/`wall_time`/`memory`/`call_out_quota`，分布式 fuel 聚合按 CPK 滑动窗口。**新方案虽单机不分布式，但"UGC 钩子必须有 fuel 计量 + 超时 + 递归深度上限"这条硬约束不变**--单机下没有"跨节点聚合"，但单钩子调用的 fuel/wall_time 配额依然是必须的（防恶意/病态表达式拖垮 tick，§F）。
7. **call_out 字符串方法名天然可序列化**（§16）：3700 处 call_out 里 3570 是字符串方法名（`(object, method, delay, args)` 四元组），机械可序列化；仅 144 处是闭包。**这条对"延迟效果/定时触发"的 DSL 设计是直接输入**：动态规则的"延迟动作"应该用声明式 `(target, action, delay)` 而非闭包，闭包是 Effect 的一等公民问题（§4/§T）。

### 1.2 01-避坑清单逐条提炼（DSL/脚本/动态逻辑/沙箱相关）

这是"已用真实代码验证过的坑"，权重最高。逐条提炼与本项目相关性：

| 条目 | 核心教训 | 对 M1 DSL 动态规则的启示 |
|---|---|---|
| **§4 Effect 必须是一等公民组件** | perform 用 `start_call_out(闭包)` 实现持续效果，闭包捕获 `this_object()` 无法序列化/跨进程/断线重放。修正：`EffectList(skill_id, effect_type, remaining_ticks, payload, source_id)` 可序列化组件 + tick 衰减。 | **动态规则的"持续效果"绝不能用闭包/call_out 表达，必须落成可序列化 Effect 组件**。M1 虽不做 Effect，但 DSL 的"延迟/持续"类规则要预留 Effect 数据形状（duration/payload/source）。ADR-0004 已确认 Effect 归引擎。 |
| **§8 heart_beat 是 tick 驱动器，不可被事件驱动替代** | 战斗回合、busy、condition 的 update_condition 都由 heart_beat 驱动。若"事件驱动替代全局心跳"，核心模拟失去驱动机制。 | **动态规则的"随时间推进"类（回血、NPC 巡逻、毒素衰减）必须挂在 tick 上，不能纯靠事件**。M1 的 `TickLoop` 已是统一驱动点（spec 用户故事 18），DSL 的周期规则挂它。 |
| **§12 ConditionHandler.on_tick 不能用互斥枚举** | `CND_CONTINUE`/`CND_NO_HEAL_UP` 是可组合位标志，跨 condition 做 OR 聚合（中毒抑制恢复）。互斥枚举会破坏"多个 condition 任意一个抑制恢复"。 | **动态规则的多规则聚合要支持组合语义（any/all），不能"先到先得"或"互斥覆盖"**。多个 `on_tick` 规则同时作用于一个实体时，要定义聚合规则（如 `suppress_heal = any(rule.suppress_heal)`）。ADR-0004 的 `StackingPolicy` 是同源手法。 |
| **§E EffectSystem 需声明 stacking_policy** | perform 用 set_temp 旗标控制效果互斥。Effect 缺"同类型唯一"约束会导致重复施加（parry buff 翻倍）。修正：`stacking_policy(unique|refresh|stack|independent)`。 | **动态规则的"施加效果/设置状态"要声明 stacking 语义**。ADR-0004 已采纳四枚举 + INDEPENDENT 逃生口。这条手法要推广到非战斗效果（buff/旗帜/计时器）。 |
| **§T Effect 需时间模式字段与崩溃恢复策略** | `duration_ticks` 以 tick 为单位，宕机不推进 tick；原 call_out 基于墙钟，宕机扣减剩余 delay。跨战斗延续效果用已结束战斗的种子产生审计歧义。修正：`mode: tick|wallclock`，wallclock 按真实经过时间衰减；崩溃恢复按 downtime 上限 clamp 跳过的 tick。 | **DSL 的"持续 N tick/N 秒"规则要支持 tick 与 wallclock 两种时间模式**，且崩溃恢复有明确语义（M1 存档是"崩溃恢复级耐久"，spec 用户故事 19，这条直接相关）。M1 的存档机制已经处理"内存权威 + 周期快照"，DSL 的持续效果要能进存档、恢复后正确续算。 |
| **§F 门派/伤害公式面向 UGC 须进沙箱** | family_definition.yaml 的加成公式用"纯 Python lambda 或受限表达式 AST"，UGC 作者可注入恶意/病态表达式（`level**100` 数值溢出、无限循环）。修正：统一安全边界，公式若面向 UGC 全部进 WASM 或受限 AST（白名单运算符、无循环、深度上限），Python lambda 仅限可信内部配置。 | **DSL 里任何"表达式"字段（条件、公式、阈值）面向 UGC 时必须进受限 AST，不能用裸 Python lambda**。这条是"条件表达式 DSL"设计的硬约束--M1 即使不实现沙箱，DSL 的条件表达式形状要按"受限 AST 可解析"设计（运算符白名单、无副作用、无循环、深度上限）。 |
| **§16 call_out 迁移要分类** | 3700 处 call_out 中 3570 是字符串方法名（天然可序列化），仅 144 是闭包。闭包真正难点不是序列化而是对象生命周期（触发时目标可能已 destruct）。修正：字符串型自动化批量；闭包型逐一人工；Effect 必须内置 target 存活校验。 | **DSL 的"延迟/定时"规则用声明式 `(target, action, delay)` 而非闭包**，且触发时要校验目标存活（目标可能已被销毁/移出场景）。这条直接影响"定时触发器"类 DSL 的设计。 |
| **§17 PermissionService 必须 fail-closed** | 授权缓存不可达时 fail-open（放行，安全漏洞）还是 fail-closed（拒绝，拒绝服务）未规定。 | **UGC 钩子的能力校验默认 fail-closed**：能力令牌校验失败或沙箱不可达时拒绝执行而非放行。M1 不实现，但是设计原则。 |
| **§19 分离 wizard ACL 与 UGC 能力沙箱** | 把损坏的 wizard ACL（运维命令权限）与 UGC 不可信代码沙箱合并是两类不同威胁模型。修正：分离两个安全域。 | **新方案天然避免了这条坑**--新引擎从零设计，没有 securityd 历史包袱。但"运维命令权限"与"UGC 钩子能力"仍是两个独立安全域，DSL 设计时不要把它们混进同一个权限模型。 |
| **§21 inquiry 是交易状态机非对话树** | inquiry 本质是"询问->设旗标->收物->校验->交付"原子交易流程（101 个 NPC 同时耦合 inquiry+accept_object+set_temp）。Ink 的 knot/stitch/divert 是叙事分支模型，不天然表达原子交易。强行套 Ink 会丢失交易原子性。修正：层2 引入"交易原子节点"语义，或简单字符串响应转层0、带交易的转"对话+交易"混合节点。 | **NPC 对话触发的 DSL 要区分"纯叙事分支"与"带原子交易的对话"**。`NPC 被问特定词触发剧情`若涉及"给物品/扣钱/改库存"，必须作为原子交易（全部成功或全部回滚），不能拆成多个独立 do 动作。这条是"NPC 对话触发"类 DSL 的硬约束。 |
| **§22 逃生舱使用率 KPI + 表达力校准实验** | 复杂面比自评更大（189 auto_perform、101 inquiry+accept_object、75 call_out 闭包、172 perform 状态机、40 CND_CONTINUE）。层1 规则 DSL 动词集缺多 actor buff/监控共同战斗/加权随机原语。修正：加大层1 表达力投入，设 KPI（<15% 走脚本），超标触发 DSL 迭代；先做 30 文件表达力校准实验。 | **新方案引入动态规则层时也要设"逃生舱使用率 KPI"**--声明式规则覆盖面不足时是"规则 DSL 表达力不够"的信号，而不是"多写脚本"的信号。M1 不做迁移所以不做 30 文件实验，但 M2/M3 引入动态规则后要观测"多少规则落声明式 vs 多少落脚本"。 |
| **§23 UGC 脚本用受限 Python 非 WASM** | 层3 WASM 要求作者写 Rust/AssemblyScript/WAT，但 UGC 作者是非程序员中文 MUD 爱好者。修正：层0-2 声明式覆盖 80%；层3 用受限 Python 子集（RestrictedPython 或 Pyodide）；WASM 仅给平台级已审计扩展。RestrictedPython 非安全边界，需叠加 fuel + 能力令牌纵深防御。 | **UGC 钩子逃生舱用受限 Python，不是 WASM**。这条已写进 CLAUDE.md 架构不变量第 5 条。M1 不实现钩子沙箱，但 DSL 设计要为"受限 Python 钩子"留平滑过渡（表达式 DSL 扩展点，旧方案 §23 末句）。 |
| **§H WASM 沙箱与 perform 多 actor 有状态协调** | WASM"天然无状态可水平扩展"与 perform 状态机自相矛盾。hebi.c 双刀和璧是深度有状态多 actor 协调（共享 buff、递归 check_fight、跨对象消息）。修正：WASM 定位为无状态计算单元（pure function），所有状态外部化为可序列化 Effect/QuestState；或扩展层1 规则 DSL 的 Effect 原语承认它是规则而非脚本。 | **多 actor 协调的有状态逻辑不能塞进"无状态钩子函数"**，要么外部化为 Effect/QuestState 实体，要么作为声明式规则原语。这条影响"双人和合/共同战斗/共享 buff"类 DSL 的设计边界。 |
| **§L Checkpoint 纳入 NPC 本地持久态** | Checkpoint 只覆盖玩家临时旗标与对话游标，未纳入 NPC 本地 dbase 持久字段（如库存计数）。热重载后 NPC 库存重置，玩家可重复刷物品。修正：扩展 Checkpoint 为 `{scene_id, temp_flags, npc_local_state, dialogue_cursor, quest_states, active_effects, version}`。战斗中禁止热重载。 | **NPC 的本地可变状态（库存、对话进度、旗标）必须进存档**。M1 的存档是按 entity 全量存（spec 用户故事 19 + save.py），NPC 若有可变状态要能序列化。DSL 的 NPC 动态规则不能依赖"不可序列化的运行时对象"。 |
| **§28 tmp_dbase≠delta（概念错误）** | dbase 与 tmp_dbase 是两个并行命名空间（分别经 query()/query_temp() 访问），tmp_dbase 不持有针对 dbase 的差分补丁，而是独立瞬时键。 | **DSL 的"临时状态"与"持久状态"是两个命名空间，不要混**。DSL 字段要明确标注"运行时可变且进存档"vs"运行时可变但不进存档（瞬时）"。当前 M1 组件字段没有这层区分，未来动态规则引入时要补。 |
| **§29 dbase 函数值/闭包键击穿 snapshot** | dbase.c query() 返回 `evaluate(data, this_object())`，104+ 文件 set 了闭包值。snapshot 序列化会在闭包键上静默丢弃或崩溃。修正：dbase 键分类台账 data-valued（可快照）vs function-valued（服务端求值后下发）；战斗 actions 等闭包必须 resolve 成动作描述符再进事件，绝不进 snapshot。 | **DSL 字段值不能是闭包/函数**，必须纯数据；任何"动态计算"的字段（如"长描述随天气变"）要在服务端求值后下发，不进存档。这条直接关系到"房间文案随 Nature 拼接"类 DSL--文案模板可声明式，但渲染结果是运行时求值，不存档。 |
| **§31b apply/ 修饰符两类语义** | apply/ 是重载的：`apply/name`/`short`/`long` 是数组栈（last-wins 覆盖），`apply/attack`/`damage`/`armor` 是标量累加槽。用单一 ModifierStack 会混淆。修正：统一建模为 Component：presentation 型（覆盖，last-wins）、stat 型（累加，add 语义）、transform 型（数组栈）。 | **DSL 的"修饰符/覆盖"规则要区分三种语义**：覆盖型（last-wins，如"夜里房间名变成 XX"）、累加型（add，如"中毒叠加伤害"）、变换栈型（数组，如"多个 buff 按序应用"）。这条是"动态修饰"类 DSL 的分类框架。 |
| **§37 call_out 不应统一持久化（分层）** | 大量 call_out 是单对象内亚秒~秒级延迟，全部持久化产生每秒数千小任务写入。修正：分层--短延迟（<30s）对象内定时器留运行时内存（崩溃丢失可接受）；仅跨重启/全局/长周期定时器走持久化。 | **DSL 的"定时触发器"要区分"短延迟内存态"与"跨重启持久态"**。M1 存档是周期快照，短延迟规则（如"喝水后 10 秒回血"）崩溃丢失可接受，但"24 小时后门自动开"这类要持久化。DSL 要能声明 time mode。 |

## 二、ADR-0004 手法向非战斗系统的推广分析

ADR-0004 拍板的战斗边界手法是：

> **引擎内嵌不变量**（七步顺序 + AP/DP 概率判定结构 + Effect 调度/衰减/移除机制）+ **题材包经注册表/Protocol 注入**（每步数值/文案的 `SkillData` + 钩子行为的 `SkillBehavior` Protocol + `PowerModel` 策略公式 + `EffectHandlerFn` 一个函数 + 声明式 `StackingPolicy`/`EffectMode`）。

这套手法的三个核心要素：①**声明式 policy 枚举**（`StackingPolicy`/`EffectMode`）描述"策略选择"而非"流程逻辑"；②**Protocol 钩子**（`SkillBehavior.hit_ob`/`hit_by`/`post_action`）描述"可选的行为插桩点"，多数实现只填数据不实现钩子；③**注册表注入**（`register_condition(name, handler)`）让题材包把自己的策略/钩子挂进引擎，引擎不知具体实现。

**推广到非战斗系统**：

| 系统 | 引擎内嵌不变量（不可改） | 题材包经注册表/Protocol 注入 | 声明式 policy |
|---|---|---|---|
| **门/锁**（M1 已有） | 门三态（open/closed/locked）枚举 + `go` 遇非开则拒 + `unlock` 需匹配钥匙 | （当前硬编码"锁需钥匙"，未来可注入"锁需密码/需解谜/需 NPC 在场"） | `LockPolicy: key_item|password|quest_flag|custom_handler` |
| **出口动态增删**（M1 已有机制） | `Exits.by_direction` 运行时可增删 + `go` 查不到则拒 | 题材包注入"何时增删哪条出口"的规则 | `ExitChangePolicy: once|reversible|timed` |
| **物品使用效果** | `use` 命令骨架 + Effect 施加/移除机制（归引擎，ADR-0004） | `ItemUseHandler` Protocol（`on_use`/`on_consume` 钩子）+ 具体效果文案/数值 | `UsePolicy: consumable|reusable|cooldown` + `StackingPolicy` |
| **NPC 对话触发** | 对话节点导航骨架 + 原子交易（§21）的回滚机制 | `DialogueHandler` Protocol（`on_topic`/`on_give` 钩子）+ 对话树数据 | `DialogueNodePolicy: narrative|transaction|quest` |
| **Nature（天气/昼夜）** | Nature 状态机 tick 推进 + 广播机制 | `NaturePhaseHandler` Protocol + 具体相位文案/效果 | `NatureEffectPolicy: cosmetic|mechanical`（纯展示 vs 影响机制如"下雨门锈住"） |
| **房间文案拼接** | 文案模板的 `$N`/`$weather`/`$time` 占位符替换骨架 | 题材包注入占位符取值函数 | （纯声明式，无 policy） |
| **状态恢复（回血等）** | tick 推进 + `suppress_heal` 聚合机制（§12） | `RegenHandler` Protocol + 具体恢复速率/条件 | `RegenPolicy: always|suppressed_when|conditional` |

**推广的关键观察**：ADR-0004 手法的本质是"**流程/机制归引擎，内容/数值/具体行为归题材包**"。这条边界在非战斗系统同样成立--门的三态机制、出口的增删机制、对话的导航机制、Nature 的 tick 推进机制都是"机制"，归引擎；"什么条件下哪扇门锈住""NPC 被问什么词触发什么剧情""下雨时房间文案怎么变"都是"内容"，归题材包（经 DSL 声明 + 钩子注入）。

**推广到非战斗系统时，当前 M1 代码缺一个核心基础设施**：事件分发/钩子环绕层。具体看现有代码：
- `commands.execute` 是 `handler(world, player_id, intent)` 直接调用，**没有 before/after 钩子环绕**。命令处理函数直接 mutate 组件（`door.state = ...`、`position.room = ...`）。要支持"夜里 NPC 不卖酒"这类"命令前置条件可否决"的规则，需要在 `execute` 外包一层"前置规则校验 -> 执行 -> 后置规则通知"。
- `TickLoop.advance` 只调 `save_fn`，**没有"分发 tick 事件给订阅者"的接缝**。要支持"喝水后 10 秒回血"这类周期规则，需要 tick 能通知订阅者。
- `World` 是纯数据容器，**没有任何事件总线/钩子注册表**。

**这正是报告要建议 M1 预留的核心基础设施**（详见第五节）。

## 三、动态规则表达范式对比

| 范式 | 形态 | 优点 | 缺点 | 适用场景 | UGC 友好度 |
|---|---|---|---|---|---|
| **①纯声明式条件表** | `when <cond> then <state>`（如 `when night and raining then door.locked`） | 可静态分析、可可视化、可校验、无副作用、可序列化、AI 生成准确率高 | 表达力有限，复杂分支/副作用/多步流程表达不了；条件谓词与状态动作词汇表要先穷举 | 状态切换、阈值触发、门/出口开关、文案拼接 | 极高（非程序员可写） |
| **②事件/触发器** | `on <event> when <cond> do <actions>`（`on_tick`/`on_enter`/`on_get`/`on_say`） | 接近自然语言心智模型、解耦（规则不关心谁触发）、可叠加多规则 | 多规则冲突/顺序需聚合策略（§12）；事件点必须引擎先预留；副作用编排弱 | 反应式行为、NPC 对话、物品使用反馈 | 高（结构清晰） |
| **③受限 Python 钩子函数** | `def on_use(ctx): ...`（RestrictedPython + fuel + 能力令牌） | 表达力强、能写复杂流程、逃生舱；作者熟悉 Python 语法 | 安全边界需多层纵深（§23 非安全边界）；性能需配额；不可静态分析；难可视化 | 复杂状态机、多 actor 协调、算法逻辑 | 中（需懂 Python） |
| **④规则 DSL/表达式语言** | 自研 mini-language（`actor.has_flag("x") && scene.time == "night"`） | 比 Python 受控（白名单运算符、无循环、深度上限，§F）、可静态分析、可序列化 | 需自研解析器（Lark）、词汇表设计成本、学习成本介于①与③ | 条件表达式、公式、阈值（作为①②的子语言） | 中高（受限但安全） |
| **⑤状态机** | `states: {A, B, C}, transitions: A->B on event` | 复杂状态流转清晰、可可视化、可证明性质（可达性/死锁） | 简单逻辑用状态机过重；状态爆炸；与①有重叠 | NPC AI、condition、quest 流程、门禁 | 中高（结构化） |

**范式间的真实关系**：这五类不是互斥选择，而是**分层组合**。旧方案四层本质就是 ①(层0) + ②(层1) + ⑤(层2 对话状态机) + ③(层3 脚本)。④是①②的"条件子语言"。

**Inform 7 的启示**（基于既有知识）：Inform 7 的规则系统把每个动作拆成 `instead of`（拦截替代）、`check`（前置校验可否决）、`carry out`（执行）、`report`（后置展示）四段式 rulebook。这是"②事件触发器"的精炼--**把一个动作的生命周期显式切成"前置校验->执行->后置通知"三段，每段都可挂规则**。这套四段式恰好是当前 M1 `commands.execute` 缺的钩子环绕层。

**Evennia 的启示**（基于既有知识）：Evennia 的 Typeclass 提供 `at_object_creation`/`at_after_move`/`at_traverse`/`at_ticker` 等 hook 方法，是"③受限 Python 钩子"的范式--钩子直接是 Python 方法，靠 Typeclass 继承复用。问题是钩子与方法绑定，跨实体规则难表达（要 mixin 或全局脚本）。

**TADS Adv3 的启示**（基于既有知识）：TADS 3 的 `doActionFor` 与 `preCond`/`actionDobj`/`verifyDobj` 是"⑤状态机 + ②事件"混合--每个动词有 verify（前置校验）/action（执行）钩子，物品按类型挂不同实现。接近 ADR-0004 的 Protocol 钩子手法。

**对本项目的结论**：以 ②事件/触发器 + ①声明式条件 为骨架（覆盖 80%），④受限表达式作为条件子语言（避免裸 Python lambda，§F），③受限 Python 钩子作为逃生舱（<15%，§22/§23），⑤状态机用于 NPC AI/quest（M2+）。**这与旧方案分层精神一致，但层数与职责从零定，不照搬旧四层。**

## 四、声明式与命令式的边界

**适合声明式**（条件、阈值、状态切换）：
- 门/出口的状态切换（`when night then door.locked`）
- 文案拼接（`long: "天{weather}了，{time}时分"`）
- 数值阈值（`when hp < 30% then regen suppressed`）
- 简单触发响应（`on_get herb then give hp+10`）
- stacking 策略（`stacking: unique`/`mode: tick`）

**必须命令式**（复杂流程、副作用编排、算法）：
- 多 actor 协调（双人和合、共同战斗监控，§H）
- 复杂状态机（auto_perform AI 循环，189 个）
- 算法逻辑（加权随机、路径计算）
- 跨实体副作用编排（"给全体队友施加 buff"）
- 闭包式延迟回调（§4/§16，但要翻译成 Effect）

**两者协作的接缝**：声明式规则在"表达不了"时降级到命令式钩子，但**钩子的"状态外部化"是硬约束**--钩子不能持有不可序列化的运行时对象（闭包捕获、this_object 引用，§4/§29），所有跨调用状态必须落成 Effect/QuestState 组件。这条是声明式与命令式协作的"合约"。

**判定流程**（给未来 M2/M3 创作者/AI Agent 用）：先试声明式条件表 -> 表达不了用事件触发器+受限表达式 -> 仍表达不了用受限 Python 钩子（状态外部化）-> 钩子也写不了的（如全新战斗模型）考虑扩展引擎。每一步降级都触发"是不是引擎该新增声明式原语"的反思（§22 KPI）。

## 五、推荐方案

### 5.1 总方向：声明式条件/触发器 + 受限 Python 钩子 + 注册表注入（ADR-0004 手法推广）

**三层结构**（从零设计，不照搬旧四层，但精神延续）：

```
┌──────────────────────────────────────────────────────┐
│ 层3 受限 Python 钩子逃生舱（<15% KPI，§22/§23）        │
│   Protocol 钩子函数 + RestrictedPython + fuel + 能力令牌 │
├──────────────────────────────────────────────────────┤
│ 层2 事件触发器 on<event> when<cond> do<actions>        │
│   引擎事件点订阅 + 声明式 stacking/聚合（§12/§E）       │
├──────────────────────────────────────────────────────┤
│ 层1 声明式条件表（字段值/状态切换/文案拼接/stacking policy）│
│   YAML 字段 + 枚举 policy + 模板占位符                  │
├──────────────────────────────────────────────────────┤
│ 层0 静态场景数据（房间/物品/NPC/出口/门，M1 已有）        │
└──────────────────────────────────────────────────────┘
```

**层1 是 M1 要打磨的核心**，层2 是 M1 要"预留事件点但不实现规则引擎"的，层3 是 M3 的事。

### 5.2 边界与理由

1. **层0 静态数据**：M1 已落地，保持显式字段（§B4 反"任意键"口子），不引入动态逻辑。
2. **层1 声明式条件**：M1 引入，但只做"字段值/模板/枚举 policy"三类--不做"when/do 规则引擎"。理由：when/do 规则引擎需要事件点 + 聚合策略 + 表达式语言，是层2 的职责，M1 引入会过度设计（spec 反复强调"M1 不预支 M3 设计"）。
3. **层2 事件触发器**：M1 **预留事件点（空挂不实现规则引擎）**，理由见第七节。这是"为动态规则留演进空间而不锁死"的关键。
4. **层3 受限 Python 钩子**：M3 做。M1 只在 DSL 形状上预留"钩子引用"字段（如 `on_use: !hook item_use_healing_potion`），但不实现钩子执行。
5. **受限表达式（④）作为层1/层2 的条件子语言**：M1 可暂用 Python 表达式字面量（受限 AST 校验留 M3），但 DSL 形状按"受限 AST 可解析"设计（白名单运算符、无循环、无副作用，§F）。

### 5.3 推荐手法（直接复用 ADR-0004 三要素）

- **声明式 policy 枚举**：每个动态行为字段配一个枚举 policy（如 `LockPolicy`/`UsePolicy`/`StackingPolicy`/`EffectMode`），policy 取值固定可枚举，题材包选不写代码。
- **Protocol 钩子**：每个事件点定义一个 Protocol（如 `OnEnterRoom`/`OnTake`/`OnUse`/`OnTick`），题材包按需实现，不实现就走默认。
- **注册表注入**：钩子/策略经 `register_xxx(name, handler)` 挂进引擎（与 `commands.register` 同构，ADR-0004 的 `register_condition` 同源）。

### 5.4 与引擎不变量的兜底关系

| 引擎不变量 | DSL 动态规则如何兜住 |
|---|---|
| 存档可恢复（spec 19） | 动态规则产生的可变状态必须落可序列化组件（Effect/旗标/计数器），不能是闭包/运行时对象（§4/§29）；时间模式声明 tick/wallclock（§T） |
| tick 可驱动（spec 18） | 周期类规则挂 `TickLoop`，不靠命令触发（§8）；短延迟内存态 vs 长周期持久态分层（§37） |
| 组件纯数据（spec 15/27） | DSL 字段值纯数据，动态计算字段运行时求值不进存档（§29）；钩子状态外部化为 Effect（§4/§H） |
| 命令解析两阶段（spec 25） | 动态规则不破坏 Intent 形状；规则挂在"执行"阶段的 before/after 环绕，不进解析阶段 |
| 命令不经 tick / tick 不经命令（spec 17） | 规则按"事件源"挂对应路径：玩家输入触发挂命令环绕，时间推进挂 tick，两者不交叉触发同一状态 |
| 多规则聚合（§12） | 同事件多规则按聚合策略组合（any/all/first-wins），不互斥覆盖 |

## 六、M1 值得预留的引擎事件点/钩子点清单

按系统分组。**M1 只"空挂"事件点（定义 Protocol + 注册表 + 调用点），不实现规则引擎与 DSL 解析**。空挂的成本极低（一个 Protocol + 一个 `dict[str, list[handler]]` 注册表 + 几处调用点），但锁死了"未来 DSL 规则能挂哪里"。

### 6.1 命令生命周期（挂在 `commands.execute` 外环绕，Inform 7 四段式）

| 事件点 | 触发时机 | 签名示意 | 用途示例 |
|---|---|---|---|
| `on_command_before` | 解析成功、执行处理函数前 | `(world, player, intent) -> Allow|Deny|Replace` | "夜里 NPC 不卖酒"前置否决；权限校验占位（spec 已预留） |
| `on_command_after` | 处理函数返回后 | `(world, player, intent, messages) -> messages` | 后置文案修饰、埋点 |

### 6.2 移动/房间（挂在 `_cmd_go` 前后）

| 事件点 | 触发时机 | 用途示例 |
|---|---|---|
| `on_before_enter_room` | 玩家将进入目标房间前（可否决） | "门锈住打不开"否决；疲劳检查 |
| `on_enter_room` | 玩家已进入房间后 | 触发房间内 NPC 反应、埋点、首次进入剧情 |
| `on_leave_room` | 玩家离开房间后 | 清理临时状态、通知房间 NPC |
| `on_traverse_blocked` | 出口存在但被门/规则挡住时 | 自定义挡路文案 |

### 6.3 物品（挂在 `take`/`drop`/未来 `use` 前后）

| 事件点 | 触发时机 | 用途示例 |
|---|---|---|
| `on_get` | 物品从地面移到玩家栏前（可否决） | "诅咒物品拿不起"；任务物品检查 |
| `on_drop` | 物品从栏移到地面前 | "任务物品不能丢" |
| `on_use`（M2 引入 use 命令时） | 物品被使用时 | "喝水后 10 秒回血"挂 Effect |
| `on_item_state_change` | 物品组件状态变化时 | 耐久度变化通知 |

### 6.4 门/出口（挂在门命令 + go 门检查处）

| 事件点 | 触发时机 | 用途示例 |
|---|---|---|
| `on_door_state_change` | 门状态 open/closed/locked 切换时 | "门被打开触发机关"；联动出口增删 |
| `on_exit_change` | `Exits.by_direction` 增删时 | 渡船到岸动态出口缝合（08 号票坐骑交通） |

### 6.5 Nature/环境（M2 引入 Nature 时，M1 只预留 tick 钩子）

| 事件点 | 触发时机 | 用途示例 |
|---|---|---|
| `on_tick` | 每次 `TickLoop.advance` | 回血、Effect 衰减、NPC AI、周期触发器 |
| `on_nature_change`（M2） | 天气/昼夜相位切换时 | "下雨时门锈住"；"夜里房间文案变" |
| `on_time_phase`（M2） | 昼夜周期推进时 | NPC 行为切换（白天卖货/夜里睡觉） |

### 6.6 NPC/对话（M2 引入 NPC 行为时）

| 事件点 | 触发时机 | 用途示例 |
|---|---|---|
| `on_say` / `on_topic`（M2） | 玩家对 NPC 说话/问特定词时 | "NPC 被问特定词触发剧情" |
| `on_give_to_npc`（M2） | 玩家给 NPC 物品时 | inquiry 原子交易（§21） |
| `on_npc_tick`（M2） | NPC 周期决策时 | NPC 巡逻、auto_perform AI |

### 6.7 M1 必须预留 vs 可推迟

**M1 必须预留（空挂）**：
- `on_tick`（`TickLoop.advance` 加订阅者分发，最核心，所有周期规则的地基）
- 命令生命周期 `on_command_before`/`on_command_after`（`execute` 外环绕，所有前置否决规则的地基）
- 移动 `on_before_enter_room`/`on_enter_room`/`on_leave_room`（`_cmd_go` 前后，"门锈住""进房触发"的最小集）
- 物品 `on_get`/`on_drop`（`_cmd_take`/`_cmd_drop` 前后）
- 门 `on_door_state_change`（门命令处）

**M1 可推迟到 M2**（Nature/NPC/对话/use 相关）：`on_nature_change`/`on_time_phase`/`on_say`/`on_give_to_npc`/`on_use`/`on_npc_tick`。但**M1 的 `on_tick` 钩子点要设计得能承载这些 M2 事件**（即 tick 分发要支持"按订阅 key 路由"，M2 的 Nature 相位切换本质也是 tick 驱动）。

## 七、DSL 草稿示意

基于现有 `m1_default_scene.yaml` 扩展。**每段标注用到的引擎事件点**。这些是"讨论用草稿"，不是 M1 要落地的格式--M1 落地范围见第八节。

### 草稿①房间文案随 Nature 拼接（层1 声明式模板）

```yaml
rooms:
  market_square:
    name: 集市广场
    long_template:        # 模板占位符，运行时求值，不进存档（§29）
      "天{weather}了，{time_phase}时分，广场上{crowd_level}。"
    long_fallback: "一片空旷的广场。"   # 模板求值失败时的静态回退
    exits:
      north: { to: inn }
```

**用到的引擎事件点**：无（纯声明式，`look` 渲染时求值占位符）。需要引擎提供"占位符取值函数注册表"（`register_placeholder("weather", fn)`）。

### 草稿②门条件规则（层1 声明式 policy + 层2 触发器）

```yaml
rooms:
  cellar:
    exits:
      north:
        to: secret_room
        door: locked
        key: iron_key
        lock_policy: custom_handler   # 声明式 policy，替代默认 key_item 检查
        lock_handler: cellar_riddle   # 题材包注入的钩子名（层3）
        # 触发器：下雨时门锈住打不开
        rules:
          - on: door_state_change      # 层2 事件触发器
            when: "nature.weather == 'raining'"
            do:
              - set_door_state: jammed   # 扩展门状态（或用 closed + flag）
              - say: "雨水让门轴锈死了，一时推不开。"
```

**用到的引擎事件点**：`on_door_state_change`（门状态变化时触发规则）、`on_command_before`（`open`/`go` 前置校验时调 `lock_policy` 钩子）。声明式 `lock_policy` 是 ADR-0004 的 `StackingPolicy` 同构。

### 草稿③NPC 对话触发（层2 事件触发器 + 层2 对话状态机，§21 原子交易）

```yaml
npcs:
  innkeeper:
    name: 酒馆老板
    in_room: inn
    dialogue: innkeeper_dialogue   # 引用对话树
    rules:
      - on: topic                   # 玩家对 NPC 说话/问特定词
        when: "verb == 'ask' && topic in ['酒','卖酒'] && nature.time_phase == 'night'"
        do:
          - say: "夜里不卖酒，明儿再来吧。"
          - deny: true              # 否决交易
    # 对话树（带原子交易的节点，§21）
    dialogue_trees:
      innkeeper_dialogue:
        start:
          text: "客官要点什么？"
          options: [买酒, 闲聊, 告辞]
        buy_wine:
          text: "一两银子一壶。"
          transaction:              # 原子交易，全部成功或全部回滚
            preconditions:
              - "actor.gold >= 1"
              - "npc.stock.wine > 0"
              - "nature.time_phase != 'night'"   # 夜里拒绝
            actions:
              - take_money: 1
              - decrement_stock: [wine, 1]
              - give_item: wine_jug
            on_success: { text: "老板递过一壶酒。" }
            on_failure: { text: "要么钱不够，要么没货。" }
```

**用到的引擎事件点**：`on_say`/`on_topic`（玩家对 NPC 说话时）、`on_command_before`（`ask`/`buy` 前置校验）。`transaction` 是 §21 原子交易节点（旧方案层2 思想，但本项目从零定，不引入 Ink）。

### 草稿④物品使用效果（层2 触发器 + Effect，§4/§E/§T）

```yaml
items:
  healing_herb:
    name: 疗伤草
    placed_in: storage_room
    use_policy: consumable           # 声明式 policy：消耗品
    on_use: healing_herb_handler     # 层3 钩子名（或内联声明式效果）
    effect:                          # 声明式 Effect（ADR-0004 同构）
      type: regen_hp
      magnitude: 10
      duration: 10                   # 10 tick
      mode: tick                      # §T 时间模式
      stacking_policy: refresh       # §E 重复使用刷新而非叠加
      suppress_heal: false            # §12 组合标志
    rules:
      - on: use                       # 玩家 use 此物品时
        do:
          - apply_effect: regen_hp
          - consume: true             # use_policy: consumable 的具体动作
          - say: "你嚼了嚼疗伤草，伤口慢慢愈合。"
```

**用到的引擎事件点**：`on_use`（M2 引入 use 命令时）、`on_tick`（Effect 衰减挂 tick，§4/§8）。`effect` 块是 ADR-0004 的 `StackingPolicy`/`EffectMode` 直接复用。

### 草稿⑤自定义事件触发器（层2 纯触发器，跨系统联动）

```yaml
# 全局规则段（不在具体房间/物品下，挂在世界级事件点）
world_rules:
  - id: bridge_collapse_on_storm
    on: nature_change                 # 天气变化时
    when: "nature.weather == 'storm' && nature.duration > 3"
    do:
      - remove_exit: { room: river_bank, direction: east }   # 桥被冲垮
      - add_exit: { room: river_bank, direction: down, to: riverbed }  # 露出河床新路
      - say_room: [river_bank, "轰隆一声，木桥被山洪冲垮了！"]
      - schedule:                     # §16 声明式延迟，非闭包
          delay: 100
          mode: tick
          action: { add_exit: { room: river_bank, direction: east, to: east_bank } }
          target: world               # target 存活校验（§16）
  - id: night_lock_gate
    on: time_phase
    when: "time_phase == 'night'"
    do:
      - set_door_state: { room: city_gate, direction: out, state: locked }
```

**用到的引擎事件点**：`on_nature_change`/`on_time_phase`（M2 Nature 引入时）、`on_tick`（`schedule` 延迟动作挂 tick，§16/§37）。`schedule` 是 §16 的声明式 `(target, action, delay)` 四元组，非闭包。

## 八、M1 scope 建议（DSL 这块做到哪）

### 8.1 M1 必须做（为动态规则留演进空间，不锁死）

1. **预留 `on_tick` 事件点**：`TickLoop.advance` 增加"订阅者分发"机制（一个 `dict[subscriber_key, handler]` + 遍历调用），M1 唯一订阅者仍是 `save_fn`。这是所有周期规则的地基，不预留则 M2 要改 `TickLoop` 接口。
2. **预留命令生命周期钩子环绕**：`commands.execute` 外包一层 `on_command_before`/`on_command_after`（空实现，直接放行）。这是所有"前置否决"规则的地基，不预留则 M2 要改 `execute` 签名。
3. **预留移动/物品/门的事件点**（第六节 6.1-6.4 列的 M1 必须项），空挂调用。
4. **YAML 过渡格式允许"未知段透传"**：`scene_loader` 遇到 `rules`/`on_use`/`effect`/`dialogue` 等未识别段时，不报错而是透传到一个"扩展数据"容器（挂在 world 或 entity 上的 `dict`），M1 不解析不执行，只是"留着不丢"。这样 M2/M3 引入动态规则解析时，旧 YAML 不必重写。**这条是"不锁死未来"的关键**--M1 不实现规则，但规则数据能留在场景文件里。
5. **组件字段标注"运行时可变且进存档" vs "启动固定" vs "运行时可变不进存档（瞬时）"**：当前 `components.py` 注释已标了"运行时可变 vs 启动固定"（见 `Door.state` 注释），补上第三类"瞬时"（§28）。这条成本极低（注释），但为 §37 短延迟内存态 vs 持久态分层铺路。

### 8.2 M1 不要做（避免过度设计，spec 反复强调）

1. **不做 when/do 规则引擎**（层2 规则解析执行）：M2/M3 的事。
2. **不做受限 Python 钩子沙箱**（层3）：M3 的事，依赖 RestrictedPython/fuel/能力令牌（§23）。
3. **不做对话树/原子交易**（草稿③）：M2 NPC 行为引入时。
4. **不做 Effect 系统**（草稿④的 `effect` 块）：ADR-0004 已确认 Effect 归引擎，但落地在 M2 战斗/状态子系统时，M1 不做。
5. **不做 Nature/时间相位**（草稿⑤的 `on_nature_change`）：M2 的事。
6. **不做表达式语言解析器**（④受限 AST）：M3 的事。M1 的 YAML 条件表达式暂用 Python 字面量或字符串占位，但**形状按"未来可换受限 AST"设计**（不引入裸 Python lambda 作为字段值，§F）。

### 8.3 M1 的 YAML 过渡格式要为动态规则扩展到什么程度

**最小但够用的程度**：
- 允许房间/物品/NPC/出口下挂 `rules:` 段（透传不解析，8.1 第 4 条）。
- 允许顶层挂 `world_rules:` 段（透传）。
- 允许字段值是"模板字符串"（占位符语法 `{xxx}`，M1 不求值，但 `look` 渲染时若遇到占位符且无取值函数则原样输出或回退 `long_fallback`）。
- **不引入** `when`/`do`/`on` 关键字的解析--这些段存在但不被 M1 解释执行。

这样 M3 正式 UGC DSL 即使整体替换格式（spec 明确允许），也可以选择"沿用 M1 的字段命名 + 扩展规则段"，而非推倒重写场景数据。**演进空间留住了，但 M1 没有预支 M3 的设计工作**（spec「场景数据与引擎能力的边界」2026-07-18 修订的核心精神）。

### 8.4 风险与止损

- **风险**：预留事件点若设计不当（如签名太具体），M2 引入真实规则时反而要改接口。**止损**：M1 预留的事件点签名尽量通用（`(world, player, intent) -> Allow|Deny|Replace` 这种），并加契约测试锁定形状（spec Testing Decisions 已要求"解析失败信号形状被测试锁定"，同思路用于事件点签名）。
- **风险**：YAML 透传段若 M3 格式整体替换，透传数据作废。**止损**：M1 的场景数据量极小（几个房间），格式替换成本可忽略；透传的目的是"不锁死"，不是"保证复用"。

## 九、关键结论速览

1. **方向**：声明式条件/触发器（层1+层2，覆盖 80%）+ 受限 Python 钩子逃生舱（层3，<15%，§22/§23）+ 注册表注入（ADR-0004 三要素推广到非战斗系统）。
2. **M1 不实现动态规则引擎，但必须预留事件点**：`on_tick`（最核心）、命令生命周期 before/after、移动/物品/门事件点。空挂成本极低，不挂则 M2 要改引擎接口。
3. **M1 YAML 过渡格式允许未识别段透传**（`rules`/`on_use`/`effect`/`world_rules` 等留着不丢不解析），这是"为 M3 UGC DSL 留演进空间而不锁死"的关键，且不违反"M1 不预支 M3 设计"（透传不是设计，只是不丢弃）。
4. **硬约束（来自避坑清单，已验证过的坑）**：动态效果必须可序列化 Effect（§4/§29，不能闭包）；条件表达式面向 UGC 进受限 AST 不用裸 Python lambda（§F）；多规则按聚合策略组合不互斥（§12）；持续效果声明 tick/wallclock 时间模式（§T）；NPC 对话带交易走原子节点（§21）；短延迟内存态 vs 长周期持久态分层（§37）。
5. **ADR-0004 手法可直接推广**：`StackingPolicy`/`EffectMode` 枚举 + Protocol 钩子 + 注册表注入这套，适用于门/物品/NPC/Nature 全部非战斗系统，边界是"机制归引擎、内容/数值/具体行为归题材包"。
6. **当前 M1 代码缺一个核心基础设施**：`commands.execute` 无 before/after 环绕、`TickLoop.advance` 无订阅者分发、`World` 无事件总线。这是预留事件点的具体落地位置。

## Sources

本项目内部文档（调研主要依据，路径均为绝对路径）：
- `/Users/gukt/github/xkx2001-utf8/.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md`
- `/Users/gukt/github/xkx2001-utf8/.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md`
- `/Users/gukt/github/xkx2001-utf8/docs/adr/0004-combat-effects-boundary-engine.md`
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/03-DSL-UGC与Agent协作.md`
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/01-关键修正与避坑清单.md`
- `/Users/gukt/github/xkx2001-utf8/.scratch/m1-core-engine-skeleton/spec.md`
- `/Users/gukt/github/xkx2001-utf8/engine/data/m1_default_scene.yaml`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/scene_loader.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/components.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/commands.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/tick.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/intent.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/world.py`
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/cli.py`

外部引擎参考（Evennia / Inform 7 / TADS Adv3 / Ranvier）：基于既有知识分析，WebSearch 在本环境未返回实质结果，相关结论已在第三节标注"基于既有知识"，未作事实性断言。如需核实可后续补充检索。
