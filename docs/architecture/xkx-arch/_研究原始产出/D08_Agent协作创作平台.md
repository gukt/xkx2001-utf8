# 方案设计·Agent协作创作平台

## 设计概述
核心理念: 以 DSL 为唯一契约层, 将 LLM 非确定性收敛到可验证终态。XKX 现有声明式内容模式(房间 exits 出口图、NPC dbase 键值属性、武功 mapping *action 招式表、condition 状态机 update_condition->CND_CONTINUE、inquiry 对话映射+set_temp marks 旗标)直接抽象为 wuxia DSL schema family, 作为所有 Agent 产出的统一出口; schema 强约束使多 Agent 交接零歧义。资产以内容寻址(blake3) + 不变量回归集保证可验证性, 形成"DSL 生成 -> WASM 沙箱执行 -> MCP 结构化指标反馈 -> 修订精炼"的闭环。协作采用编排者-工作者分工 + 生成-评审-修订循环, MVP 先跑通这两条主干, 红蓝对抗验证作为后期质量放大器。人机协作设三道审批门(创意意图/世界圣经/发布前), 早期只开意图与发布两道避免拖慢迭代。多题材通过主题清单插件化复用协作骨架, 仅新增 DSL schema family。落地关键顺序约束: (1)CPK+manifest+provenance溯源从第一个包就内建, 不可后补; (2)运行时沙箱与 per-CPK 配额治理先行且不可妥协, 直接对齐 config.xkx 的 eval-cost/reset/clean-up 语义; (3)先重建替代损坏的 securityd 能力权限模型再开放协作, 否则安全边界无法成立。该子系统是整个重构的"内容工厂", 上游对接人类创意意图与 Agent 编排, 下游产出可挂载到分布式 Actor/ECS 运行时的题材世界。

## 组件
- **dsl-contract（DSL 契约层）**：定义主题无关核心 schema 与各题材 schema family；外部 DSL(YAML 方言+规则/对话语法)经 Lark 解析、pydantic v2 校验，编译为语言无关 JSON IR 作为唯一真相源。四层结构: 层0声明式场景数据(对应2531纯数据房间)、层1事件规则 condition->action(对应 add_action/valid_leave/accept_object/chat_msg)、层2 Ink对话树 knot/stitch/divert/weave(对应434个 inquiry 映射+set_temp marks)、层3 WASM脚本逃生舱(对应 query_action NewRandom等复杂逻辑)。负责强约束 schema 使多 Agent 交接零歧义。（技术：Lark(EBNF外部DSL解析) + pydantic v2(schema校验与类型化组件) + 自研IR编译器 + Ink(knot/stitch对话模型)）
- **agent-orchestration（Agent 编排层）**：实现编排者-工作者分工与生成-评审-修订循环。编排器把'创意意图'拆解为 DAG 工作流分派给五角色 Worker: Worldbuilder(世界观设计师,产出世界圣经与场景拓扑)、Narrator(编剧,产出对话树与剧情事件)、Behaviorist(NPC行为作者,产出 condition状态机与 chat_msg)、Balancer(平衡测试,产出武功 action数值与战斗模拟调参)、Continuity(连贯性审查,交叉验证世界圣经一致性)。每条产出经 MCP验证+评审修订循环收敛到可验证终态；MVP先做编排-工作者与生成-评审-修订两主干，红蓝对抗作为后期质量放大器。（技术：LangGraph(状态机编排+checkpoint持久化可断点续跑) + LangChain(LLM调用抽象) + Claude API主、可插拔GLM等国模型）
- **asset-store（内容寻址资产库）**：以 CPK(内容包)+manifest+依赖图为单元管理创作资产生命周期。资产内容寻址(blake3)不可变,版本快照可回滚；manifest内建 license声明与 provenance溯源链(来源Agent/human、prompt hash、父资产hash),从第一个CPK即内建避免后期补登；依赖图检测循环与缺失引用。对接现有 replace_program房间/clone物品/kungfu技能经迁移脚本批量转译为初始CPK集合形成基线。（技术：blake3(内容寻址哈希) + PostgreSQL(清单/依赖图/版本/provenance) + MinIO/S3(资产对象存储,天然去重) + 自研依赖解析器）
- **mcp-verification（MCP 验证层）**：以 MCP(Model Context Protocol)暴露共享验证基底给所有Agent。优先实现两高频验证 server: world-graph(出口可达性,基于 networkx图分析,覆盖孤立房/死路/不可达区)与 combat-sim(伤害/胜率,复用重构后 ECS战斗引擎做确定性 seeded模拟器)。叠加不变量回归集(从8400 LPC解析入库形成基线断言,如'所有门派技能force值>0'、'主城互通'),任何变更须过全量回归。输出结构化指标(覆盖率/胜率分布/数值溢出)驱动精炼闭环。（技术：MCP协议(Anthropic标准) + networkx(图可达性分析) + 复用重构后ECS战斗引擎做模拟器 + 确定性seeded RNG）
- **sandbox-runtime（WASM 沙箱运行时）**：执行层3 WASM脚本与层1事件规则。安全模型用显式能力清单(read_world/say/move_self/spawn_in_scene/schedule),危险动作(move_player/destroy/persist/log_file)需提升权限；对齐XKX set_temp旗标+log_file审计但显式化。资源限制对齐 config.xkx的 eval-cost语义固化为 per-CPK配额: 每心跳指令上限、墙钟超时、内存上限、递归深度、call_out配额,燃料耗尽即中止(替代原'Too long evaluation'但可配置、按作者配额)。UGC一律走WASM,可信编辑者可用受限Python。（技术：wasmtime-py(WASM运行时+WASI) + 能力令牌注入host functions + per-CPK燃料计量）
- **review-pipeline（评审管线）**：实现人机协作三道审批门。门1创意意图(创作启动前人类确认方向)、门2世界圣经(规模扩大后引入确认世界观一致性)、门3发布前(对外发布前最终审批)。早期只设门1+门3避免门过多拖慢迭代。审批工作台支持可视化预览(场景图/对话图/事件流),人类决策与Agent验证报告并列展示；超时设默认策略防阻塞。Agent协作产出物强制走与人类相同的审核与版本流程。（技术：FastAPI(审批API) + WebSocket(实时协作通知) + 可视化预览(Twine式场景图/Ink式对话图)）
- **theme-registry（多题材注册表）**：主题包插件机制,泛化现有19门派(kungfu/class/*)模式为题材包。DSL核心主题无关,每主题注册自己的条件谓词/动作动词/Actor属性 schema family。wuxia注册经脉/内力/招式谓词,nautical注册航向/风向/货舱,academy注册课业/师承,modern注册现代属性。多题材共享运行时但各自演进,避免为每题材重建引擎；新增题材=注册新schema family+谓词包,不改核心。（技术：Python entry points(插件机制) + pydantic动态schema注册 + 主题清单(theme manifest)声明谓词/动词/属性）
- **lpc-ingest（存量迁移管线）**：把8400 LPC文件用Agent解析为DSL入仓形成基线回归集。优先级: 先转2531纯数据房间(层0工作量小收益大),再转434个inquiry为对话树(层2),最后处理技能/复杂任务逻辑(层3 WASM)。既验证DSL表达力是否完备(不能表达即schema缺陷反馈给契约层),又为后续UGC增量提供不变量保护网。处理LPC隐式行为(simul_efun覆写destruct->remove、this_object()动态分派)需静态分析与人工标注。（技术：LPC静态分析器(自研基于tree-sitter-lpc或正则+AST) + Agent辅助解析 + 人工标注集）

## 关键接口/事件
- compile(dsl_source: str, theme: str) -> CompileResult[ir, errors, warnings] - DSL源码编译为JSON IR,返回IR与编译诊断
- validate(ir: IR, schema_family: str) -> ValidationResult[ok, schema_errors, capability_violations, budget_report] - schema+能力清单+资源预算三重校验
- register_asset(ir: IR, provenance: ProvenanceRecord) -> asset_id - 内容寻址注册,内建license与溯源链
- verify(asset_id: AssetID, check_set: CheckSet) -> VerificationReport[passed, metrics, coverage] - MCP验证基底统一入口,world-graph/combat-sim等检查器按check路由
- orchestrate(intent: CreativeIntent, theme: str, workflow_type: str) -> workflow_id - 启动编排工作流,拆解DAG分派Worker
- request_human_review(workflow_id: WorkflowID, gate: GateType) -> review_token - 请求人工审批门,返回预览URL与证据报告
- resolve_asset(asset_id) -> IR - 按内容寻址取资产,跨节点可缓存
- reconcile_invariants(asset_scope) -> RegressionReport - 对资产范围跑全量不变量回归
- 事件: AssetProposed / AssetCompiled / AssetValidated / AssetRejected - 资产生命周期
- 事件: ReviewGateOpened / HumanDecisionRecorded / GateTimeoutDefaulted - 审批流转(含超时默认策略)
- 事件: InvariantRegressionDetected - 不变量回归失败触发修订循环
- 事件: WorkflowStageChanged / WorkerTaskDelegated / WorkerTaskCompleted - 编排状态机流转
- 事件: CapabilityEscalationRequested / SandboxFuelExhausted - 沙箱权限提升与配额耗尽
- 事件: ThemePackRegistered / SchemaFamilyVersionBumped - 多题材注册

## 数据模型
核心单元为 CPK(内容包),内含 manifest 声明依赖/license/author/theme/version。数据模型分层: (1)Asset资产: id=blake3(content)内容寻址不可变, type=scene/npc/skill/condition/dialogue/event_rule, ir=编译后JSON IR;(2)AssetVersion:资产版本快照支持回滚;(3)DependencyEdge:依赖图边(asset_a依赖asset_b,类型reference/spawn/inherit);(4)ProvenanceRecord:溯源链(来源agent_id/human_id、prompt_hash、parent_asset_id、license、created_at)从第一个CPK即内建;(5)WorkflowRun:编排实例(state=planning/generating/reviewing/published/rejected、stage、produced_asset_ids、langgraph checkpoint_id);(6)ReviewGate:审批门(gate_type=intent/bible/release、status、reviewer_id、decision、evidence_report_id);(7)InvariantSet:不变量回归集(assertion_expr、check_type=graph_reachability/combat_balance/schema、expected、asset_scope)从LPC基线解析入库;(8)VerificationResult:验证报告(asset_id、check、passed、metrics_json);(9)CapabilityGrant:能力授权(subject、capability、scope、expires_at);(10)ThemePack:主题包(schema_family、predicates、verbs、actor_attributes)。持久化策略:权威存储PostgreSQL(append-only events表+snapshots表+manifest/依赖图/provenance),热资产Redis Stream缓存,大资产对象MinIO/S3;LangGraph checkpoint存PG支持workflow断点续跑与回放;资产内容寻址天然去重,版本快照按需存对象存储。沿用LPC dbase持久层 vs tmp_dbase瞬态层分离思想:持久资产入PG/snapshot,运行期投影/缓存入Redis可重建。

## 旧->新映射
- d/*/*.c 房间手写 create() + set("exits",(["east":__DIR__"beidajie1"])) 硬编码绝对路径(6414房) -> **层0 YAML Scene声明式定义, exits用稳定 scene_id 引用解耦身份与路径, 编译器解析为图模型边**（2531个 replace_program纯数据房间先批量转层0, 收益最大; 室内/户外/cost保留为环境属性）
- kungfu/skill/*.c 的 mapping *action招式表 + query_action/valid_enable/valid_learn方法(359技能) -> **层0 SkillDef IR(招式表YAML化+技能类型+绑定) + 层3 WASM处理复杂 query_action如 NewRandom加权**（先用Agent解析入库形成基线回归集验证DSL表达力; 技能是行为定义非实体数据,保留策略对象多态）
- kungfu/condition/*.c 的 update_condition(me,duration)->CND_CONTINUE/CND_NO_HEAL_UP 状态机(72个) -> **层1 EventRule(condition->action)DSL, duration与CND_CONTINUE映射为状态机节点与迁移**（返回0=结束、1=继续、2=禁治疗,是简洁状态机协议,直接映射为DSL状态节点）
- set("inquiry",([topic:(:func:)])) + ask_me_N()函数 + set_temp("marks/",1)临时旗标(434处) -> **层2 Ink对话树 knot/stitch/divert/weave, set_temp marks映射为对话树状态变量**（Ink的weave比手写状态机简洁, 434处inquiry优先于技能迁移(对话结构规整)）
- accept_object(me,ob)/chat_chance+chat_msg/valid_leave(me,dir)房间与NPC事件钩子(164处accept_object) -> **层1 EventRule注册(on:give_item/on:idle_tick/on:leave_room), 钩子作为UGC剧情触发点**（valid_leave是房间级离开校验,天然UGC剧情触发点(门派规矩/任务门禁); chat_msg映射为on:idle_tick随机事件）
- globals.h宏路径常量 + CLASS_D(x)/SKILL_D(x)/CONDITION_D(x)/DRUG_D(x)数据驱动行为注册表(19门派) -> **多题材注册表(theme-registry), 泛化19门派模式为题材包(wuxia/nautical/academy/modern)**（宏路径解耦服务定位思想保留为服务发现; 门派即题材包雏形,直接泛化即可支持多题材）
- securityd.c valid_cmd ACL(含authorized_cmds拼写bug、两处硬编码默认值) + euid/wizhood路径回溯式权限 -> **能力令牌(capability tokens)显式授权 read_world/say/move_self/spawn_in_scene, 危险动作需提升权限**（本分支已损坏须先重建能力权限模型再开放协作; 对齐set_temp旗标+log_file审计但显式化）
- config.xkx的eval cost(6亿全局预算) + 931处call_out非持久定时器绑定对象生命周期 -> **per-CPK配额(指令上限/墙钟超时/内存/递归深度/call_out配额) + 持久化调度器, 燃料耗尽即中止**（eval cost作为单线程执行预算废弃, 替换为per-tenant资源隔离; 燃料机制对齐'Too long evaluation'但可配置按作者配额）
- save_object全量覆盖写.o平文件 + autoload重建引用(无版本/无并发/无审计) -> **内容寻址资产(blake3)+manifest+依赖图+provenance溯源链, PostgreSQL权威存储+快照**（沿用dbase持久层vs tmp_dbase瞬态层分离思想: 持久资产入PG, 运行期投影入Redis可重建）
- room reset()内联 make_inventory硬编码repop + clean_up破坏式对象生命周期 -> **声明式对象清单(objects映射即desired state) + 世界重生服务读取spawn配置reconcile**（reset的'声明式清单+系统收敛到期望状态'是不可变基础设施模式,值得保留为reconcile语义）

## 分布式扩展策略
编排器无状态化: LangGraph workflow状态(checkpoint)持久化到PostgreSQL,编排器实例可水平扩展多副本,任一实例崩溃可从checkpoint续跑避免单点。Worker Agent池按角色分池: Worldbuilder/Narrator/Behaviorist/Balancer/Continuity各自独立队列,用Celery+Redis分发,按题材与LLM负载路由可独立扩缩容。MCP验证服务无状态副本: world-graph(纯图计算无状态)与combat-sim(seeded确定性模拟)均可多实例并行验证同一资产,按验证负载水平扩展。资产库内容寻址天然去重与CDN友好: blake3相同内容只存一份,MinIO/S3可加CDN缓存热点IR,跨节点读取IR走对象存储而非主库。多租户隔离:每个题材世界(wuxia/nautical/academy/modern)独立supervision与资源配额,CPK边界即租户隔离边界,WASM沙箱per-CPK配额硬隔离,一个题材的Agent失控不拖垮其他题材。沙箱运行时按worker分片: WASM实例池绑定worker,燃料计量per-CPK,燃料耗尽即中止不阻塞其他CPK。存量迁移管线可并行: 8400文件按区域分片并行ingest,结果合并入基线回归集。渐进扩展:先单进程asyncio编排验证语义,再加多worker池与多MCP副本,规模达跨区域多租户时按需引入NATS subject分区隔离,不过早引入Kafka。

## 技术选型
- DSL解析: Lark(EBNF外部DSL解析器,纯Python,支持自定义语法方言)
- Schema校验: pydantic v2(类型化组件schema,运行时校验+静态类型,替代散落全库的字符串键query)
- 对话树: Ink(inkjs/py-ink,knot/stitch/divert/weave模型,替代inquiry+set_temp marks退化状态机)
- WASM沙箱: wasmtime-py(内存安全+燃料计量+能力化+近原生速度+语言无关,优于裸Lua/Python沙箱)
- Agent编排: LangGraph(状态机编排,checkpoint持久化可断点续跑,优于裸LangChain chain)
- LLM推理: Claude API主+可插拔后端(支持GLM等国模型,符合部署环境)
- MCP验证: Model Context Protocol(Anthropic标准,Agent共享验证基底)+networkx(图可达性分析)
- 任务队列: Celery+Redis(创作任务分发与结果回传,Worker按角色分池)
- 资产存储: blake3(内容寻址哈希,快于sha256)+PostgreSQL(清单/依赖图/provenance审计)+MinIO/S3(对象存储,天然去重)
- 评审工作台: FastAPI+WebSocket(审批API与实时协作通知)
- 多题材插件: Python entry points(主题包注册机制,运行时发现并加载schema family)
- LPC静态分析: tree-sitter-lpc或自研正则+AST(解析8400文件入仓,处理this_object动态分派需人工标注)
- 确定性模拟: 复用重构后ECS战斗引擎+seeded RNG(战斗回放与反作弊审计前提)

## 风险
- DSL表达力不足: 现有8400 LPC含复杂逻辑(query_action的NewRandom加权、门派专属auto_perform AI、双面门运行时协调),纯声明式无法表达,须依赖WASM逃生舱兜底,但WASM创作门槛高可能劝退UGC作者;需控制层3占比并强化层0-2覆盖面
- LLM非确定性收敛困难: 生成-评审-修订循环可能不收敛(无限修订打转)或收敛到平庸局部最优;须设最大迭代数硬上限+不变量硬约束作为终止条件+红蓝对抗防止评审者与生成者共谋
- 8400文件迁移工作量与隐式行为风险: Agent解析LPC形成基线本身是大工程,且LPC的this_object()动态分派、simul_efun隐式覆写(destruct->remove)、previous_object信任链难以静态分析,迁移可能遗漏关键钩子导致语义偏差
- WASM沙箱安全: 能力清单设计不全即等于开放拒绝服务,必须per-CPK配额(燃料/超时/内存/call_out)硬约束先行且不可妥协,且须先重建替代securityd.c(本分支已损坏含authorized_cmds拼写bug)的能力权限模型再开放协作
- MCP验证覆盖率盲区: world-graph/combat-sim覆盖数值与可达性缺陷,但剧情连贯性/对话死锁/任务绕过/逻辑时序错乱需专门检查器,覆盖不全即放过缺陷;须从'武功数值溢出'与'任务绕过'两类高频漏洞切入逐步扩展
- 多题材schema漂移: 主题包插件机制可能导致schema family分叉(各题材谓词/动词不一致),后期合并困难;须统一核心schema+受控扩展点约束,避免19门派式硬编码if-else链在多题材层重演
- provenance后补成本极高: 若第一个CPK未内建溯源,后期海量UGC资产无法追溯已发布内容,版权与审计无法成立;必须从CPK格式固化时即内建内容寻址与license声明,不后补
- 人机协作审批瓶颈: 三道门若审批者响应慢会阻塞迭代流水线;须设超时与默认策略(门1/门3人工、门2默认放行待规模扩大),且审批工作台须高效预览否则人工成本过高
- Agent编排与LLM成本: 五角色多Agent生成-评审循环token消耗大,创作规模扩大后成本显著;须缓存复用、分级模型(简单校验用小模型、复杂生成用大模型)、批处理仿真摊薄成本
- 确定性随机与分布式一致性: 战斗模拟与Agent生成的随机性在分布式多实例下需独立seeded RNG,否则回放与反作弊审计失效;须每场模拟/每个region分配独立seed并写append-only事件日志

---

## 🔍 对抗验证

**裁定**：risky（方向正确，核心论点成立，但执行风险显著，多处关键假设未经实证支撑）。核心论点——以 DSL 为唯一契约把 LLM 非确定性收敛到可验证终态、内容寻址+不变量回归保可验证性、编排者-工作者+生成-评审-修订循环——是站得住的，且 currentToNewMapping 经逐项核对与代码库高度吻合（exits 出口图、mapping *action 招式表、update_condition 返回 0/1 状态机、inquiry+set_temp marks、make_inventory+reset 声明式清单均实测确认；simul_efun 覆写 destruct->remove 在 adm/simul_efun/object.c 实测确认；securityd.c 损坏与 authorized_cmds 拼写 bug 第 757 行实测确认）。但存在若干硬伤：combat-sim 依赖一个尚不存在的 ECS 引擎形成循环依赖；LangGraph 被当作分布式编排器使用但实际是单进程库，多实例协调缺位；安全模型把运维 wizard ACL 与 UGC 沙箱能力两类不同威胁模型混为一谈；WASM 层 3 创作门槛与'非程序员 UGC 作者'目标人群直接冲突；既有 16 份架构分析文档只分析 LPC 模式、完全未涉及 ECS/DSL/Agent/UGC/能力令牌等新概念，方案的解法抽象全是 net-new 未经既有研究验证。判定为 risky 而非 flawed，因为核心思路与代码映射扎实、风险多可经具体修正缓解；不判 sound，因为关键依赖链与扩展性论断有多处被实测证伪或悬空。

**严重度**：medium

### 问题与修复
- **ECS 战斗引擎循环依赖（最严重）：mcp-verification 的 combat-sim 声称'复用重构后 ECS 战斗引擎做确定性 seeded 模拟器'，但仓库中不存在任何 ECS 实现，现有战斗是 COMBAT_D（adm/daemons/combatd.c）+ feature/attack.c 的守护进程+混入模式，16 份既有架构分析文档也未提及 ECS。这意味着整个'生成->WASM执行->MCP反馈->修订'闭环的核心验证器（combat-sim）依赖另一个子系统（分布式 Actor/ECS 运行时重构）先完成，而该子系统本身是更大的工程。**
  - 影响：闭环不收敛即整个'以验证终态收敛 LLM 非确定性'的核心论点无法落地；combat-sim 缺位时 Balancer 角色与门派技能数值不变量（方案自己列为高频验证项）无法验证，Agent 产出质量无客观信号，退化为纯人工评审。
  - 修复：将 ECS 战斗引擎重构显式列为前置里程碑并设交付标准，或先用一个独立的纯 Python 数值模型做 combat-sim（直接从 LPC *action 招式表与 feature/attack.c 的伤害公式 seed 出来），不耦合运行时子系统；待 ECS 落地后再替换模拟器内核。world-graph 可独立先行（纯 networkx 图分析，无 ECS 依赖）。
- **LangGraph 分布式扩展被夸大：LangGraph 是单进程状态机库，checkpoint 持久化到 PG 只支持崩溃后恢复，不提供多实例协调。方案声称'编排器实例可水平扩展多副本，任一实例崩溃可从 checkpoint 续跑避免单点'，但若两个编排器实例同时恢复同一 workflow，会重复分派 Worker 任务、双花 LLM token、产出冲突。方案未提分布式锁/租约（如 Redis SETNX 或 PG advisory lock）来串行化 workflow 认领。**
  - 影响：声称的水平扩展不可用，强行多副本会导致 LLM 成本翻倍与产出不一致；若实际只用单实例则 scaleStrategy 关于 Worker 池与编排器水平扩展的论述大部分落空，高并发目标受限于单编排器吞吐。
  - 修复：明确分布式协调机制：用 Postgres advisory lock 或 Redis SETNX 给 workflow 加租约（lease），任一编排器持锁后才能续跑；或务实接受'单编排器 + 故障转移（standby 从 checkpoint 接管）'而非 active-active 多副本。MVP 直接单进程 asyncio 编排，验证语义正确性后再谈水平扩展。
- **安全模型范畴错误：方案把损坏的 wizard ACL（securityd.c 的 authorized_cmds，决定谁能跑 /cmds/adm）与 UGC 不可信代码沙箱能力（WASM capability tokens）合并为'能力令牌显式授权'。这是两类不同的威胁模型：wizard ACL 是运营/管理授权（可信运维人员的命令权限），WASM capability 是不可信 UGC 代码执行隔离。混淆二者会导致运维权限管理缺失或 UGC 隔离设计错位。我已确认 securityd.c 的 authorized_cmds 拼写 bug（第 757 行 authorized_cmds["cmd"] 应为 "cmds"]）与两处硬编码默认值（725-726 行）属实。**
  - 影响：若用 UGC 能力模型替代运维 ACL，巫师命令权限丢失导致平台无法运维；若运维 ACL 渗入 UGC 沙箱则攻击面评估错位。两者绑死还会拖延'先重建 securityd 再开放协作'这个方案自己设的前置门。
  - 修复：分离两个安全域：(a) 运维侧保留一个简单的角色门（admin/arch/wiz/player 命令 ACL），先修好 authorized_cmds 拼写与硬编码默认值即可恢复巫师可用；(b) 能力令牌仅作用于 UGC WASM 沙箱（read_world/say/move_self 等）。不要用一套能力模型同时覆盖运维与 UGC，二者信任边界与审计需求不同。
- **WASM UGC 创作门槛与 UGC 目标自相矛盾：层 3 WASM 逃生舱要求作者写 Rust/AssemblyScript/WAT，而目标 UGC 作者是非程序员中文 MUD 爱好者。方案自己识别了'WASM 创作门槛高可能劝退 UGC 作者'风险，却只给'控制层 3 占比'这一无操作性的缓解。实测 165 个技能有 query_action、131 个用 NewRandom、128 个用 auto_perform——这些复杂逻辑若不能用声明式表达，UGC 作者一旦触顶即被卡死，且无退路。**
  - 影响：UGC 创作者触顶即卡死，无中间路径，平台活跃度受限于能写 WASM 的极少数人；层 3 占比失控则安全面与性能面双双恶化，与 UGC 大规模目标冲突。
  - 修复：分层创作体验：层 0-2 声明式 DSL 覆盖 80%；层 3 用受限 Python 子集（如 RestrictedPython 或 Pyodide 沙箱执行），而非裸 WASM，降低创作门槛；WASM 仅保留给平台级已审计扩展（可信编辑者）。为 UGC 作者提供层 2 到层 3 的平滑过渡（如表达式 DSL 扩展点），避免直接掉进 WASM 悬崖。
- **迁移工具成熟度押注于不存在的 grammar：方案称用'tree-sitter-lpc 或自研正则+AST'解析 8400 文件。tree-sitter-lpc 并非成熟维护的 grammar；LPC 的 heredoc 语法（set("long",@LONG...LONG)）、globals.h 自动全局包含（157 行宏）、simul_efun 的 destruct 覆写、this_object()-> 动态分派（实测 274 文件）、previous_object() 信任链（51 文件）都需要流分析而非解析。正则+AST 对这套预处理+动态分派极度脆弱。**
  - 影响：若假设 Agent 解析能达语义保真，实际迁移产物会静默丢失钩子（如某 NPC 的 previous_object 信任校验被吞），上线后表现为剧情 bug/任务绕过，且因基线回归集本身有缺陷而无法发现，缺陷被固化进不变量。
  - 修复：不押注 tree-sitter-lpc；采用'正则抽取结构化字段（exits/objects/inquiry/marks）+ 人工标注集覆盖动态分派长尾'的混合策略。先用单区域（如 d/city 约 90 房）做端到端迁移试点，度量语义偏差率，确认 DSL 表达力与标注成本后再推全量。把 this_object()/previous_object 长尾明确划为人工标注而非自动化范围。
- **'纯数据房间收益最大'低估了层 0 复杂度：实测即便'纯'replace_program 房间（如 d/city/dongjiao1.c）仍含 set("objects",[...]) 生成引用、set("resource/grass",1) 资源采集、set("cost",2) 移动消耗、set("outdoors","city") 天气语义。更关键：6414 房中仅 2482 是 replace_program（38.7%），1113 房（17.3%）带自定义 add_action（如 do_suicide/do_ask/do_check）属非声明式，需层 1 事件规则或 WASM。'先转纯数据房间'的规模被高估。**
  - 影响：'收益最大'的快胜假设落空，层 0 迁移要么低估工作量延期，要么因 schema 不全而把语义塞进 string bag，重演旧系统 set("任意键") 的反模式。
  - 修复：在层 0 schema 固化前先穷举环境/语义字段（objects spawn、resource、cost、outdoors、no_clean_up、resource/* 等）为显式 schema 字段；把 1113 个带 add_action 的房间单独列为层 1 迁移批次而非'纯数据'。迁移排期按'schema 字段完备度'而非'文件数'估算工作量。
- **provenance 从第一个 CPK 即内建对 MVP 过早：方案坚持'从第一个 CPK 即内建内容寻址与 license，不后补'，理由是后期海量 UGC 无法追溯。这在'已发布 UGC'场景下成立，但 MVP 开发期尚未开放发布（门 3 未开），没有外部 UGC 需要审计。强制每个开发迭代资产都带完整 provenance（agent_id/prompt_hash/parent_asset）增加迭代摩擦。**
  - 影响：开发期每条资产创建都付溯源开销，拖慢迭代；若开发期资产无外部消费者，溯源字段在 MVP 阶段是纯负担。若后期想补又确实无法追溯已发布内容，形成两难——但 MVP 阶段没有任何'已发布'内容，该风险被提前兑现了。
  - 修复：把 provenance 强制点从'第一个开发 CPK'后移到'首次对外发布前（门3 开启前）'。开发期用简单版本号即可快速迭代；门 3 开启前再强制全量资产回填 provenance 并固化 CPK 格式。这既保住发布后的审计/版权保证，又不拖慢 MVP。
- **技术栈广度与团队规模严重失配：方案涉及 Lark+pydantic v2+Ink+wasmtime-py+LangGraph+LangChain+Celery+Redis+FastAPI+WebSocket+PostgreSQL+MinIO/S3+networkx+MCP+tree-sitter 共 14+ 技术组件。git 历史显示当前维护者 gukt 仅 1 次提交，前分析者 xiongmao86 42 次——实质是单人重构。**
  - 影响：团队把大量精力消耗在基础设施集成与运维上，而非验证核心 DSL->Agent->验证闭环是否成立；任一组件出问题即拖累整体，故障域过大；单人难以同时运维 PG+MinIO+Celery+WASM 池+多 MCP 副本。
  - 修复：砍 MVP 到最小可验证收敛集：DSL 编译器(Lark+pydantic) + 单进程 LangGraph 编排 + SQLite/PG + 一个 MCP 检查（world-graph） + 最简评审 UI。Celery/MinIO/分布式 WASM 池/NATS 等待单进程验证语义正确后再按需引入。用'是否阻塞验证收敛闭环'为唯一引入判据。
- **技能数与层 3 工作量估算偏差显著，影响 WASM/迁移预算：方案称'359 技能有 *action 招式表'，实测 kungfu/skill 下共 472 个 .c 文件，但含 'mapping *action' 模式的仅 163 个；query_action 出现在 165 文件。误差近 2 倍，直接关系层 3 WASM 兜底工作量评估。call_out 实测 1011 处（方案称 931）、replace_program 2482（称 2531）、inquiry 424 文件（称 434）也有 5-8% 偏差。**
  - 影响：层 3 工作量被高估约 2.2 倍，可能误导资源分配（过度投入 WASM 逃生舱而忽视层 0-2 覆盖面）；或反之，若按错误的小数字排期，实际迁移时发现长尾远超预期而延期。方案自己列的风险'层 3 占比失控'的判断基线就是错的。
  - 修复：迁移前先跑一次精确基线统计（*action 映射数、query_action 数、NewRandom 数、auto_perform 数、call_out 数），用实测值重算层 3/WASM 工作量与人力预算。把'359 技能'更正为'163 个含 *action 招式表'，并据此评估 WASM 逃生舱占比。

### 改进建议
- 先在单区域（d/city 约 90 房）做端到端 MVP，跑通'声明式 DSL 房间 -> Agent 生成 -> world-graph 验证 -> 人工评审'最小闭环，用实测语义偏差率校准全量迁移可行性，再决定是否投入 8400 文件规模。
- 把 ECS 战斗引擎重构显式列为前置里程碑并设交付标准；在此之前 combat-sim 用独立纯 Python 数值模型（从 feature/attack.c 与 *action 表 seed）顶上，不要让验证闭环硬等运行时子系统。world-graph 可独立先行。
- 先修好 securityd.c（authorized_cmds 拼写 + 硬编码默认值）恢复最小运维可用，但把 wizard ACL 与 UGC 能力沙箱拆为两个安全域分别演进，不要用一套能力模型同时覆盖。
- 层 3 UGC 脚本用受限 Python 子集（RestrictedPython/Pyodide）而非裸 WASM，WASM 仅留作平台级已审计扩展；为非程序员 UGC 作者提供层 2->层 3 平滑过渡（表达式 DSL 扩展点），避免触顶即卡死。
- 分布式协调显式化：要么给 workflow 加分布式锁/租约支持多编排器，要么务实接受单编排器+故障转移；砍掉 active-active 多副本的假设。MVP 直接单进程 asyncio 编排。
- MVP 技术栈砍到最小：Lark+pydantic + 单进程 LangGraph + SQLite/PG + 一个 MCP 检查（world-graph）+ 最简评审 UI。Celery/MinIO/分布式 WASM 池/NATS 等单进程验证收敛后再按需引入。
- provenance 强制点后移到'首次对外发布前（门3 开启前）'而非'第一个开发 CPK'，开发期用简单版本号快速迭代，发布前再回填全量溯源并固化 CPK 格式。
- 迁移前跑一次精确基线统计（实测：*action 163、query_action 165、NewRandom 131、auto_perform 128、call_out 1011、replace_program 2482、带 add_action 房 1113/6414），用实测值重算层 3/WASM 工作量与人力预算，修正方案中 359 技能等偏差。
