# DSL、UGC 平台与 Agent 协作创作（v2）

> 本文档是 v2 创作层方案。与 v1（[[03-DSL-UGC与Agent协作]]）相比，重点修正：Agent NPC 严格分层、五角色 Worker 降级为能力清单、combat-sim 改真实 `resolve_attack` 纯函数、验证覆盖度六维矩阵、版权清洗与创作者经济 Day1 预留。

---

## 一、为什么需要 DSL

XKX 现状统计（实测）：

- 8412 个 LPC 文件中，2482 个是 replace_program 纯声明式房间（38.7%）。
- 1113 个房间带自定义 add_action（17.3%，需事件规则或脚本）。
- 424-434 个 inquiry 对话（含 101 个同时耦合 inquiry+accept_object+set_temp 的交易 NPC）。
- 472 个技能文件，其中 163 个含 `mapping *action`、165 个用 query_action、131 个用 NewRandom、128 个用 auto_perform。
- 72 个 condition 状态机守护进程。
- 1626 个文件用 message_vision。

结论：约 30% 是纯数据可直接转声明式，70% 含事件/对话/定时/战斗逻辑需要规则 DSL 或脚本逃生舱。**纯声明式无法表达所有逻辑，纯脚本对 30% 纯数据房间是浪费**——故采用分层混合 DSL。

---

## 二、四层 DSL 架构

```
┌─────────────────────────────────────────────────────┐
│ 层3 RestrictedPython / WASM 脚本逃生舱              │  <15% KPI
├─────────────────────────────────────────────────────┤
│ 层2 Ink 对话树 + 交易原子节点（对话/交易流程）        │
├─────────────────────────────────────────────────────┤
│ 层1 事件规则 condition->action（触发器/副作用）       │
├─────────────────────────────────────────────────────┤
│ 层0 YAML 声明式场景数据（房间/NPC/技能/条件数据）     │  覆盖 60%+
└─────────────────────────────────────────────────────┘
         │ 全部编译为
         ▼
   JSON IR（唯一真相源）── 运行时只消费 IR，与创作语法解耦
```

### 层0：YAML 声明式数据

直接吸收 LPC 的 set() 调用。schema 固化前必须穷举环境/语义字段（objects spawn、resource、cost、outdoors、no_clean_up、resource/* 等）。

### 层1：事件规则 condition→action

覆盖 init/add_action/valid_leave/accept_object/chat_msg 等事件钩子。

**须扩充的原语**：`apply_buff_to_actors`、`weighted_random`（精确复刻 `NewRandom(i,20,level/5)`）、`monitor_cooperation`、`spawn_coordinated_effect`。

### 层2：对话树 + 交易原子节点

采用 Ink 语义模型。简单字符串响应转层0；带交易的 inquiry 转"对话+交易"混合节点。

### 层3：脚本逃生舱

- **UGC 作者用受限 Python 子集**（RestrictedPython 或 Pyodide 沙箱执行）。
- **WASM 仅保留给平台级已审计扩展**（可信编辑者）。
- 设**逃生舱使用率 KPI <15%**，超标触发层1-2 表达力迭代。

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
- (a) 运维侧 wizard ACL（admin/arch/wiz/player 命令权限）——从 securityd.c 提取规格后从零实现。
- (b) UGC 沙箱能力令牌——仅作用于 UGC 脚本。

### 资源配额（不可妥协硬约束）

- 每脚本每心跳指令上限（fuel）
- 墙钟超时
- 内存上限
- 递归深度
- call_out 配额
- **分布式燃料聚合器**：按 CPK 维度聚合跨调用 fuel，设滑动窗口配额，超限熔断。

---

## 四、UGC 内容包（CPK）

```yaml
内容包(CPK) = manifest + 资产集合
manifest:
  cpk_id: wuxia_shaolin_v3
  schema_version: 1
  theme: wuxia
  version: 3.1.0
  license: CC-BY-SA-4.0
  provenance:
    content_hash: blake3:...
    parents: [wuxia_shaolin_v2]
    author: {type: agent, id: worldbuilder-7, model: claude}
    prompt_hash: sha256:...
    # updated 作者署名作为 legacy provenance 回填
    legacy_authors: ["wiz_feng", "wiz_yun"]
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
```

### 内容生命周期

创作 -> 测试 -> 审核 -> 发布 -> 版本 -> 下架

- **内容寻址**：blake3 哈希，不可变快照。
- **依赖图**：networkx 拓扑排序，检测循环与缺失引用。
- **命名空间隔离**：每 CPK 独立命名空间，跨包引用经依赖声明。
- **市场分发与计费**：Day1 在 CPK manifest 预留 author_id / revenue_share / price 字段。
- **provenance 强制点**：开发期用简单版本号快速迭代，**首次对外发布前（审批门3开启前）**强制回填全量溯源并固化 CPK 格式。

---

## 五、多题材机制（ThemeRegistry）

泛化现有 19 门派模式为题材包：

| 题材 | schema family | 特色谓词/动词 |
|---|---|---|
| wuxia（武侠） | 经脉/内力/招式 | 经脉运行、内力运转、招式连击 |
| nautical（大航海时代） | 航向/风向/货舱 | 起航、贸易、海战 |
| academy（书院） | 课业/师承/科举 | 读书、考试、论道 |
| modern（现代剧情） | 现代属性/职业 | 现代技能、社交、职业 |

**机制**：DSL 核心主题无关，每主题注册自己的条件谓词/动作动词/组件 schema family/默认资产。新增题材 = 注册新 schema family + 谓词包，不改核心。

---

## 六、Agent 协作创作架构（v2 重大修正）

### 核心理念

以 DSL 为唯一契约层，将 LLM 非确定性收敛到可验证终态。schema 强约束使多 Agent 交接零歧义。

### 五角色降级为"能力清单"

v1 的固定五角色 Worker 在 v2 中降级为 Orchestrator 可调用的专项能力：

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
- MVP 用 PG-backed 状态机；LangGraph 仅过渡原型，中期迁 Temporal/DBOS durable execution。

### 人机协作三道审批门

1. **门1 创意意图**（创作启动前人类确认方向）——早期开启。
2. **门2 世界圣经**（规模扩大后确认世界观一致性）——后期开启。
3. **门3 发布前**（对外发布前最终审批）——早期开启。

早期只设门1+门3，避免门过多拖慢迭代。provenance 强制点后移到门3前。

### MCP 验证基底

1. **world-graph**（出口可达性）：纯 networkx 图分析，独立先行。
2. **combat-sim**（伤害/胜率）：**直接调用从 LPC 提取的 `resolve_attack` 纯函数**，不依赖完整 ECS 运行时但保证与未来真实引擎同源。
3. **不变量回归集**：从 8400 LPC 解析入库形成基线断言。

### 验证覆盖度六维矩阵（v2 新增）

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

```
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

### 技术选型（MVP 最小集）

| 组件 | 选型 | 说明 |
|---|---|---|
| DSL 解析 | Lark + PyYAML + pydantic v2 | 外部 DSL |
| 对话树 | Ink 语义子集 | 避免外部二进制依赖 |
| 沙箱 | RestrictedPython（UGC）/ wasmtime-py（平台级） | 燃料计量 |
| Agent 编排 | PG-backed 状态机（MVP） | LangGraph 仅过渡原型 |
| LLM | Claude API 主 + 可插拔 GLM | 符合部署环境 |
| MCP 验证 | Model Context Protocol + networkx | 图可达性 + combat-sim |
| 资产存储 | blake3 + PostgreSQL + MinIO/S3 | 内容寻址 |
| 任务队列 | MVP 不用 Celery，单进程 asyncio | 验证收敛后再引入 |
| 评审工作台 | FastAPI + WebSocket + 可视化预览 | 场景图/对话图 |

**LLM 成本模型（v2 新增）**：
- 建立单 CPK tokens 估算模型（可能 75 万-数百万 tokens）。
- 分层模型策略：编排/审查用强模型，生成/校验用经济模型。
- 创作者配额。

---

## 七、Agent NPC 严格分层（v2 新增）

**定位**：立项但先判定 tractable 再排期；是 research problem 不是普通 feature。

### 分层

1. **tick 仿真内 NPC AI**：用确定性行为树/状态机（快、确定、可回放）。不在 tick 内调用 LLM。
2. **实时深度对话服务**：独立"对话服务"，LLM 推理结果异步注入游戏世界。
3. **硬隔离 guardrail**：**LLM 只出对话文本，DSL 状态机守所有状态变更**。NPC 幻觉不能 mutate 游戏世界（不能刷金币、破坏任务逻辑）。

### 接口

- `DialogueService.generate(npc_id, player_context, world_bible_snippet) -> {text, suggested_emotion}`
- 状态变更只能由 DSL 状态机或可信 System 触发，对话服务返回值不直接写世界状态。

---

## 八、内容合规与经济系统（v2 新增）

### 版权与法律框架

- **金庸衍生内容 71 文件**：需授权、改编化（角色改名/门派虚构化）或标注同人非商用。
- **AI 生成内容版权政策**：明确训练数据、生成产物归属。
- **provenance 扩展为版权链**：记录作者、模型、prompt、父版本。

### 分层内容审核 pipeline

1. 自动化预检（暴力/敏感词/赌博/版权关键词）。
2. 社区众审。
3. 专家审核。
4. 平台终审。

加内容分级 + 举报下架申诉。

### 创作者经济 Day1 预留

即使 MVP 不实现支付，CPK manifest 也预留：

```yaml
market:
  title: 少林派扩展包
  description: ...
  tags: [wuxia, shaolin, kungfu]
  screenshots: [...]
  author_id: creator_42
  revenue_share: 0.70
  price: 0  # MVP 免费
```

阶段 4 交付内容市场 MVP（浏览/搜索/安装/评分/分账）。

---

## 九、存量迁移管线（greenfield 口径）

**不是"迁移"而是"规格提取 → 按规格实现"**：

1. **层0 schema 固化**（穷举环境/语义字段）。
2. **2482 纯数据房间转层0**，建立基线回归集。
3. **inquiry 子分类**（纯字符串 vs 带交易）分别进入层0/层2。
4. **技能**：提取 SkillData YAML + SkillBehavior Python 策略规格。
5. ** securityd**：提取权限规格后从零实现，不修旧代码。

### 表达力校准实验（不可跳过）

启动批量转换前，取 30 个代表性文件人工转译为 DSL，统计落入各层分布。**若层3占比 >20%**，先扩充层1-2 原语。

---

## 十、落地顺序与硬约束

```
1. 阶段 -1 垂直切片平台验证（验证 DSL+Agent 闭环是否成立）
2. 层0 schema 固化（穷举环境/语义字段）
3. 2482 纯数据房间转层0（建立基线回归集）
4. 表达力校准实验（30 文件）
5. 层1-2 规则 DSL + 对话树（含交易原子节点）
6. RestrictedPython/WASM 沙箱 + per-CPK 配额
7. CPK 格式固化 + 创作者经济字段预留
8. PG-backed 状态机编排 + world-graph MCP 验证
9. combat-sim 调用 resolve_attack 纯函数
10. 多题材 ThemeRegistry
11. Agent NPC 严格分层（先判定 tractable）
```

### 不可妥协的硬约束

1. **沙箱配额先行**：开放 UGC 脚本前 per-CPK 资源配额必须就位。
2. **securityd 规格提取**：UGC 协作开放前必须先重建能力权限模型，不修旧代码。
3. **表达力校准**：8400 文件批量转换前必须先做 30 文件验证，层3占比 >20% 则先扩充层1-2。
4. **provenance 后移**：开发期用简单版本号，门3前才强制回填。
5. **combat-sim 调真实 resolve_attack**：不依赖简化独立模型。
6. **Agent NPC 硬隔离**：LLM 只出文本，DSL 状态机守状态变更。
7. **版权清洗**：金庸衍生 71 文件必须处理后方可对外发布。

---

*最后更新：2026年7月9日*
