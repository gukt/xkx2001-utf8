# DSL、UGC 平台与 Agent 协作创作（v3 收缩版）

> 本文档是 v3 创作层方案。相对 v2（见 `_archive/03-v2-DSL-UGC与Agent协作.md`），重点收缩：层3 沙箱统一为 RestrictedPython（砍 WASM）、否决独立规则引擎（层1 是唯一规则表示层）、题材包三层边界 + 静态加载、Agent 编排内存状态机、砍分布式燃料聚合器与多创作者 CRDT/OT、内容市场仅预留字段。三个开放问题的裁决详见 [02-三个开放架构问题裁决](02-三个开放架构问题裁决.md)。

---

## 一、为什么需要 DSL

XKX 现状统计（实测）：

- 8412 个 LPC 文件中，2482 个是 replace_program 纯声明式房间（38.7%）。
- 1113 个房间带自定义 add_action（17.3%，需事件规则或脚本）。
- 424-434 个 inquiry 对话（含 101 个同时耦合 inquiry+accept_object+set_temp 的交易 NPC）。
- 472 个技能文件，其中 163 个含 `mapping *action`、165 个用 query_action、131 个用 NewRandom、128 个用 auto_perform。
- 72 个 condition 状态机守护进程。
- 1626 个文件用 message_vision。

结论：约 30% 是纯数据可直接转声明式，70% 含事件/对话/定时/战斗逻辑需要规则 DSL 或脚本逃生舱。**纯声明式无法表达所有逻辑，纯脚本对 30% 纯数据房间是浪费**--故采用分层混合 DSL。

---

## 二、四层 DSL 架构

```text
┌─────────────────────────────────────────────────────┐
│ 层3 RestrictedPython 脚本逃生舱（统一两层，砍 WASM） │  <15% KPI
├─────────────────────────────────────────────────────┤
│ 层2 Ink 对话树 + 交易原子节点（对话/交易流程）        │
├─────────────────────────────────────────────────────┤
│ 层1 事件规则 condition->action（唯一规则表示层）       │
├─────────────────────────────────────────────────────┤
│ 层0 YAML 声明式场景数据（房间/NPC/技能/条件数据）     │  覆盖 60%+
└─────────────────────────────────────────────────────┘
         │ 全部编译为
         ▼
   JSON IR（唯一真相源）── 运行时只消费 IR，与创作语法解耦
```

### 层0：YAML 声明式数据

直接吸收 LPC 的 `set()` 调用。schema 固化前必须穷举环境/语义字段（objects spawn、resource、cost、outdoors、no_clean_up、resource/* 等）。

### 层1：事件规则 condition->action（唯一规则表示层）

覆盖 init/add_action/valid_leave/accept_object/chat_msg 等事件钩子。

> **v3 裁决**（[02](02-三个开放架构问题裁决.md) Q2）：层1 是**唯一规则表示层**，否决独立规则引擎。层1 的薄求值子模块（不命名为"引擎"、不建独立框架）管事件触发即时求值 + dirty-flag 缓存 + 主题注册动词派发。UGC 触发器只能声明式层1，从题材包注册表查询受限谓词/动词，不能注册新词。

**须扩充的原语**：`apply_buff_to_actors`、`weighted_random`（精确复刻 `NewRandom(i,20,level/5)`）、`monitor_cooperation`、`spawn_coordinated_effect`。

**规则冲突解决**：显式 priority + deny-wins（对齐 `notify_fail`）+ 同 action-tag 首匹配，按事件类型固定策略，写进基线测试断言原 LPC 命中行为（533 valid_leave 及 12 个 imm/wiz 同名动词）。

**调度语义四分**（避免双真相源）：

| 调度类型 | 归属 |
|---|---|
| 事件触发器 | 层1 求值 |
| call_out（694 文件/3109 处） | 进程内 ActionScheduler（timer wheel） |
| 周期 condition | ConditionSystem tick（CND_CONTINUE/CND_NO_HEAL_UP 位标志） |
| 连续仿真 | Combat/Heal/NPCAI System |

**heart_beat 1s tick 绝不被规则引擎吸收**。

### 层2：对话树 + 交易原子节点

采用 Ink 语义模型。简单字符串响应转层0；带交易的 inquiry 转"对话+交易"混合节点。

### 层3：脚本逃生舱（统一为 RestrictedPython）

- **UGC 作者用受限 Python 子集**（RestrictedPython）。
- **v3 收缩：砍 WASM**--单进程纯 Python 下无多租户进程隔离需求，引入 Rust/AssemblyScript 编译为 wasm32-wasi 的工具链负担不抵收益。改用 RestrictedPython 统一两层，靠**审查门 + 能力令牌 + 配额**区分信任级而非语言隔离。WASM 留作多租户生产阶段重新评估。
- 设**逃生舱使用率 KPI <15%**，超标触发层1-2 表达力迭代（非放松 KPI）。
- **明确禁止层1 与层3 之间的"规则脚本"中间层**。
- 判定标准：可声明式描述且跨多条规则复用则扩层1；需图灵完备逻辑则层3。

---

## 三、IR 校验与安全模型

所有层编译为 JSON IR，经四道校验：

1. **SchemaValidator**：jsonschema 结构校验。
2. **CapabilityAuditor**：审核脚本引用能力是否在 CPK manifest 声明范围内。
3. **ResourceBudgetChecker**：fuel/wall_time/memory/call_out_quota 是否超限。
4. **DependencyResolver**：networkx 依赖图拓扑排序与环检测。

### 能力令牌安全模型

显式能力清单：read_world / say / move_self / spawn_in_scene / schedule / move_player / destroy / persist / log_file / privileged_force。

**安全模型分两个独立域**：

- (a) 运维侧 wizard ACL（admin/arch/wiz/player 命令权限）--从 `securityd.c` 提取规格后从零实现。**权限策略是启动时加载的可信配置/代码**（非可变存档），进程内求值，fail-closed = "策略加载失败则拒绝启动"。
- (b) UGC 沙箱能力令牌--仅作用于 UGC 脚本（RestrictedPython）。

### 资源配额（不可妥协硬约束）

- 每脚本每心跳指令上限（fuel）
- 墙钟超时
- 内存上限
- 递归深度
- call_out 配额
- **v3 收缩：砍分布式燃料聚合器**（按 CPK 维度聚合跨调用 fuel 的滑动窗口配额）。单进程内 per-CPK fuel 即进程内计数器，无需 Redis 计数器/分布式限流/熔断协议。

---

## 四、UGC 内容包（CPK）

```yaml
内容包(CPK) = manifest + 资产集合
manifest:
  cpk_id: wuxia_shaolin_v3
  schema_version: 1
  theme: wuxia              # 所属题材包
  pack_type: module_pack    # module_pack(受信任开发者) | ugc(创作者)
  version: 3.1.0
  license: CC-BY-SA-4.0
  provenance:
    content_hash: blake3:...
    parents: [wuxia_shaolin_v2]
    author: {type: agent, id: worldbuilder-7, model: claude}
    prompt_hash: sha256:...
    legacy_authors: ["wiz_feng", "wiz_yun"]   # updated 作者署名回填
  dependencies:
    - wuxia_core: ^2.0
    - common_dialogue: ^1.0
  capabilities_required: [read_world, say, spawn_in_scene]
  resource_quota:
    fuel_per_tick: 50000
    wall_time_ms: 50
    memory_mb: 64
    call_out_quota: 100
  entry_points:
    main_scene: shaolin/shanmen
  # 创作者经济 Day1 预留字段（不实现功能）
  market:
    title: 少林派扩展包
    description: ...
    tags: [wuxia, shaolin, kungfu]
    author_id: creator_42
    revenue_share: 0.70
    price: 0
```

### 内容生命周期

创作 -> 测试 -> 审核 -> 发布 -> 版本 -> 下架

- **内容寻址**：blake3 哈希，不可变快照。JSON 可序列化，存储后端解耦，后期可经存储接口策略模式无痛迁 PG/MongoDB。
- **依赖图**：networkx 拓扑排序，检测循环与缺失引用。
- **命名空间隔离**：每 CPK 独立命名空间，跨包引用经依赖声明。
- **provenance 强制点**：开发期用简单版本号快速迭代，**首次对外发布前（审批门3开启前）**强制回填全量溯源并固化 CPK 格式。
- **市场分发与计费**：Day1 在 CPK manifest 预留 author_id / revenue_share / price / title / tags 字段，**阶段 -1~2 不实现浏览/搜索/安装/评分/分账**（后置）。
- **v3 收缩：砍 CRDT/OT 结构化合并的多创作者 CPK 协作工作流**--砍到单作者 CPK + 简单 fork-merge（人工 merge 冲突），多创作者并发是后置能力。

---

## 五、题材与扩展机制（ThemeRegistry）

> v3 裁决（[02](02-三个开放架构问题裁决.md) Q1）：三层边界 + 静态加载。砍运行时热插拔。

### 三层粒度

| 层 | 粒度 | 谁来写 | 执行权限 |
|---|---|---|---|
| 核心 | 引擎（ECS+tick+CombatKernel+DSL 编译器+沙箱） | 平台核心开发者 | 不可插拔 |
| 题材包 | Theme（schema family+谓词/动词词汇表+themed 治理策略）+ Module Pack（门派/区域 CPK） | 受信任开发者 | 进程级无沙箱 Python（StdLib 级） |
| UGC | CPK（层0+层1+层2） | 创作者 | 沙箱受限 RestrictedPython |

> 源码实证：`adm/daemons/race/human.c` 第 92-185 行对 19 门派硬编码 if-else 加成，证明门派是 wuxia 题材下内容包（Module Pack）非独立题材。

### 机制

- **ThemeRegistry** = 启动时加载的静态注册表（Python dict: `theme_id -> ThemeDescriptor`），无运行时 unload/版本协商/隔离。
- 每题材注册：component_schemas / condition_predicates / action_verbs / combat_resolver_impl / default_assets / themed_governance_policies。
- 新增题材 = 注册新 schema family + 谓词包，不改核心。
- **门派灵魂**（SkillBehavior Python 策略）归属武侠题材包资产；`human.c` 19 门派加成迁移时从 race/核心层剥离为题材包内容。
- **CombatKernel 抽象从武侠 `do_attack` 七步提取**（不从 4 题材预先设计），阶段 -1 用非武侠微场景验证主题无关性。
- 受信任开发者扩展 = 带代码题材包，审查 + 签名 + SemVer + CPK provenance。
- **运行时热插拔等第二个题材真实存在且需不停服切换时再议**。

| 题材（未来） | schema family | 特色谓词/动词 |
|---|---|---|
| wuxia（武侠，旗舰） | 经脉/内力/招式 | 经脉运行、内力运转、招式连击 |
| academy（学院） | 课业/师承/科举 | 读书、考试、论道 |
| scifi（科幻） | 科技/势力/装备 | 探索、研究、对战 |
| simulation（模拟经营） | 资源/生产/贸易 | 经营、生产、交易 |

---

## 六、Agent 协作创作架构

### 核心理念

以 DSL 为唯一契约层，将 LLM 非确定性收敛到可验证终态。schema 强约束使多 Agent 交接零歧义。

### 五角色降级为"能力清单"

v1 的固定五角色 Worker 降级为 Orchestrator 可调用的专项能力：

| 能力 | 职责 | 产出 |
|---|---|---|
| Worldbuilder | 世界圣经、场景拓扑 | 层0 场景 + 区域图 |
| Narrator | 对话树、剧情事件 | 层2 对话 + 层1 剧情 |
| Behaviorist | condition 状态机、chat_msg | 层1 事件规则 + condition |
| Balancer | 武功 action 数值 | 层0 技能 + 数值表（**对 skill_power 无产出能力，平台级 Python 实现**） |
| Continuity | 生成时约束注入 | structured output + 实体关系约束（**替代事后审查**） |

**Orchestrator 架构**：

- 单 Orchestrator 持世界圣经摘要。
- 用 RAG 检索解决 200k+ token 超窗口问题。
- 按需唤起上述能力，而非固定进程。
- **v3 收缩：MVP 用内存状态机**（砍 PG-backed 状态机的 PG 依赖，状态随进程内存）。LangGraph 仅过渡原型，中期迁 durable execution 后置。

### 人机协作三道审批门

1. **门1 创意意图**（创作启动前人类确认方向）--早期开启。
2. **门2 世界圣经**（规模扩大后确认世界观一致性）--后期开启。
3. **门3 发布前**（对外发布前最终审批）--早期开启。

早期只设门1+门3，避免门过多拖慢迭代。provenance 强制点后移到门3前。

### MCP 验证基底

1. **world-graph**（出口可达性）：纯 networkx 图分析，独立先行。
2. **combat-sim**（伤害/胜率）：**直接调用从 LPC 提取的 `resolve_attack` 纯函数**，不依赖完整 ECS 运行时但保证与未来真实引擎同源。
3. **不变量回归集**：从 8400 LPC 解析入库形成基线断言。

### 验证覆盖度六维矩阵

| 维度 | 方法 | 自动化程度 |
|---|---|---|
| 结构 | jsonschema / 图可达性 | 全自动 |
| 数值 | combat-sim 分布 / hypothesis property-based | 全自动 |
| 经济 | 多 agent 玩家行为仿真 | 半自动 |
| 任务逻辑 | 状态空间探索 / 模型检查 | 半自动 |
| 叙事 | LLM-as-judge | 人工抽样 |
| 趣味 | playtest agent + 人工 playtest | 人工抽样 |

**必须显式声明 gap**：前三维可机器自动验证，后三维需半自动或人工。不掩盖覆盖度幻觉。

### 闭环

```text
人类创意意图(门1)
    │
    ▼
Orchestrator(RAG 世界圣经) 拆解 DAG ──> 按需唤起专项能力生成 DSL
    │                         │
    │                         ▼
    │                    MCP 验证(world-graph / resolve_attack combat-sim)
    │                         │
    │                    六维评估矩阵
    │                         │
    │                    生成时约束注入(Continuity)
    │                         │
    ▼ <─── 不通过则修订 ──────┘
资产入库(CPK + provenance)
    │
    ▼
人工审批(门3 发布前)
    │
    ▼
发布到题材世界
```

### v3 新增：LLM token 预算 + kill criterion

- 单 CPK token 预算上限（可能 75 万-数百万 tokens，建立估算模型）。
- 分层模型策略：编排/审查用强模型，生成/校验用经济模型。
- 创作者 LLM 配额（免费额度+付费）。
- **Langfuse 追踪人工修订量趋势**：3 轮迭代后修订率 >40% 则先扩层1-2 表达力再继续 Agent；扩后仍 >30% 则 Agent 降级为辅助（人工为主 Agent 建议为辅）；LLM token 预算耗尽且未产出通过闭环的 CPK -> 停止 Agent 投入回退人工创作 DSL。

### 技术选型（MVP 最小集）

| 组件 | 选型 | 说明 |
|---|---|---|
| DSL 解析 | Lark + PyYAML + pydantic v2 | 外部 DSL |
| 对话树 | Ink 语义子集 | 避免外部二进制依赖 |
| 沙箱 | RestrictedPython（UGC + 平台级统一两层） | 砍 WASM；燃料计量 |
| Agent 编排 | 内存状态机（MVP） | LangGraph 仅过渡原型 |
| LLM | Claude API 主 + 可插拔 GLM | 符合部署环境 |
| MCP 验证 | Model Context Protocol + networkx | 图可达性 + combat-sim |
| 资产存储 | blake3 + 本地 JSON（经 StorageBackend 接口） | 内容寻址，后期策略切换 PG |
| 任务队列 | MVP 不用 Celery，单进程 asyncio | 验证收敛后再引入 |
| 评审工作台 | FastAPI + WebSocket + 可视化预览 | 场景图/对话图 |

---

## 七、Agent NPC 严格分层

**定位**：立项但先判定 tractable 再排期；是 research problem 不是普通 feature。

### 分层

1. **tick 仿真内 NPC AI**：用确定性行为树/状态机（快、确定、可回放）。不在 tick 内调用 LLM。
2. **实时深度对话服务**：独立"对话服务"，LLM 推理结果异步注入游戏世界。
3. **硬隔离 guardrail**：**LLM 只出对话文本，DSL 状态机守所有状态变更**。NPC 幻觉不能 mutate 游戏世界（不能刷金币、破坏任务逻辑）。

### 接口

- `DialogueService.generate(npc_id, player_context, world_bible_snippet) -> {text, suggested_emotion}`
- 状态变更只能由 DSL 状态机或可信 System 触发，对话服务返回值不直接写世界状态。

---

## 八、内容合规与版权

### 版权与法律框架

- **金庸衍生内容 71 文件**：需授权、改编化（角色改名/门派虚构化）或标注同人非商用。对外发布前必须处理。
- **AI 生成内容版权政策**：明确训练数据、生成产物归属。
- **provenance 扩展为版权链**：记录作者、模型、prompt、父版本。

### 分层内容审核 pipeline

1. 自动化预检（暴力/敏感词/赌博/版权关键词）。
2. 社区众审。
3. 专家审核。
4. 平台终审。

加内容分级 + 举报下架申诉。

### 创作者经济 Day1 预留

即使 MVP 不实现支付，CPK manifest 也预留 `market` 字段（title/description/tags/author_id/revenue_share/price）。阶段 4 交付内容市场 MVP（浏览/搜索/安装/评分/分账）。

---

## 九、存量迁移管线（greenfield 口径）

**不是"迁移"而是"规格提取 -> 按规格实现"**：

1. **层0 schema 固化**（穷举环境/语义字段）。
2. **2482 纯数据房间转层0**，建立基线回归集。
3. **inquiry 子分类**（纯字符串 vs 带交易）分别进入层0/层2。
4. **技能**：提取 SkillData YAML + SkillBehavior Python 策略规格。
5. **securityd**：提取权限规格后从零实现，不修旧代码。
6. **门派**：`human.c` 19 门派加成从 race/核心层剥离为武侠题材包 Module Pack。

### 表达力校准实验（不可跳过）

启动批量转换前，取 30 个代表性文件人工转译为 DSL，统计落入各层分布。**若层3 占比 >20%**，先扩充层1-2 原语。逃生舱使用率 KPI <15%。

---

## 十、落地顺序与硬约束

```text
1. 阶段 -1 垂直切片平台验证（验证 DSL+Agent 闭环是否成立）
2. 层0 schema 固化（穷举环境/语义字段）
3. 2482 纯数据房间转层0（建立基线回归集）
4. 表达力校准实验（30 文件）
5. 层1-2 规则 DSL + 对话树（含交易原子节点）
6. RestrictedPython 沙箱 + per-CPK 配额（砍 WASM）
7. CPK 格式固化 + 创作者经济字段预留
8. 内存状态机编排 + world-graph MCP 验证
9. combat-sim 调用 resolve_attack 纯函数
10. 题材包三层边界 + ThemeRegistry 静态加载
11. Agent NPC 严格分层（先判定 tractable）
```

### 不可妥协的硬约束

1. **沙箱配额先行**：开放 UGC 脚本前 per-CPK 资源配额必须就位。
2. **securityd 规格提取**：UGC 协作开放前必须先重建能力权限模型，不修旧代码。
3. **表达力校准**：8400 文件批量转换前必须先做 30 文件验证，层3 占比 >20% 则先扩充层1-2。
4. **provenance 后移**：开发期用简单版本号，门3 前才强制回填。
5. **combat-sim 调真实 resolve_attack**：不依赖简化独立模型。
6. **Agent NPC 硬隔离**：LLM 只出文本，DSL 状态机守状态变更。
7. **版权清洗**：金庸衍生 71 文件必须处理后方可对外发布。
8. **themed 治理不进层1**：天雷/阴间/vote/法院是平台级 fail-closed Python System，不对 UGC 开放。

---

*最后更新：2026年7月10日*
