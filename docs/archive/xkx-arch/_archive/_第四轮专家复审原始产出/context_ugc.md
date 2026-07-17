# UGC 分层与核心指标归属基线

> 整理来源：[03-DSL-UGC 与 Agent 协作](../03-DSL-UGC与Agent协作.md)、ADR-0030、ADR-0031、ADR-0032、ADR-0033、ADR-0053。
> 用途：第四轮专家复审前上下文速查，明确 UGC 架构分层、职责边界与指标 owner。

---

## 一、DSL 四层职责

| 层级 | 语法/载体 | 覆盖范围 | 信任级 | 目标覆盖率 |
|---|---|---|---|---|
| 层0 | YAML 声明式场景数据 | 房间、NPC、物品、技能静态数据、条件数据 | 引擎可信 / CPK 资产 | 60%+ |
| 层1 | condition->action 事件规则 | init / add_action / valid_leave / accept_object / chat_msg 等事件钩子 | CPK 资产，受 ThemeRegistry 词汇表约束 | 25% 左右 |
| 层2 | Ink 语义对话树 + 交易原子节点 | 带分支的对话、inquiry、交易流程 | CPK 资产 | 按需 |
| 层3 | RestrictedPython 脚本逃生舱 | 图灵完备逻辑、无法声明式表达的世界行为 | UGC 沙箱受限 / module_pack 受信任 | <15%（KPI） |

### 关键约束

- 层1 是**唯一规则表示层**，否决独立规则引擎；薄求值子模块只做事件触发即时求值 + dirty-flag 缓存 + 主题注册动词派发。
- 层3 使用率超标（>15%）时，先扩层1/层2 表达力，而非放松 KPI。
- 明确禁止在层1 与层3 之间再建“规则脚本”中间层。
- heart_beat 1s tick 不被规则引擎吸收；调度语义四分：事件触发器归层1、call_out 归 ActionScheduler、周期 condition 归 ConditionSystem、连续仿真归 Combat/Heal/NPCAI。

---

## 二、CPK pack_type 区别

CPK（Content Pack）= manifest + 资产集合，是 UGC 平台的内容单元。

| 维度 | `module_pack` | `ugc` |
|---|---|---|
| 作者身份 | 受信任开发者 / 官方 StdLib | 普通创作者 |
| 执行环境 | 进程级 Python（StdLib 级，无沙箱） | RestrictedPython 沙箱 |
| `capabilities_required` | 建议声明，不强制 | 强制声明 |
| `resource_quota` | 不强制 | 强制（fuel/wall_time/memory/call_out） |
| M3 状态 | 全部官方 CPK 为 module_pack | 后置 Wave 3 / M3 后 |
| 典型内容 | 武侠题材包、门派、区域、官方武学 | 玩家/第三方创作者内容 |

### manifest 关键字段（M3 简化版）

- `cpk_id`、`schema_version`、`theme`、`pack_type`、`version`、`license`、`author`
- `dependencies`、`capabilities_required`、`entry_points`
- `market`：Day1 预留（title/description/tags/author_id/revenue_share/price），M3 不实现功能
- `provenance`：门3 前强制回填，M3 开发期用简单 version + author
- `resource_quota`：UGC 后置

---

## 三、ThemeRegistry 静态加载

### 三层粒度

| 层 | 粒度 | 作者 | 执行权限 |
|---|---|---|---|
| 核心 | 引擎（ECS + tick + CombatKernel + DSL 编译器 + 沙箱） | 平台核心开发者 | 不可插拔 |
| 题材包 | Theme（schema family + 谓词/动词词汇表 + themed 治理策略）+ Module Pack（门派/区域 CPK） | 受信任开发者 | 进程级无沙箱 Python |
| UGC | CPK（层0 + 层1 + 层2） | 创作者 | 沙箱受限 RestrictedPython |

### ThemeRegistry 机制

- `ThemeRegistry = dict[str, ThemeDescriptor]`，**启动时静态加载**，无运行时 unload / 版本协商 / 隔离。
- 每个 `ThemeDescriptor` 注册：
  - `race_profile`
  - `family_bonuses`
  - `theme_config`（start_room / death_room / revive_room / jail_rooms）
  - `class_tables`
  - `condition_predicates`（层1 谓词词汇表）
  - `action_verbs`（层1 动词词汇表）
  - `governance_policies`
- M3 注册 2 个题材：`wuxia`（武侠旗舰）与 `default`（非武侠测试题材）。
- 新增题材 = 注册新 schema family + 谓词包，不改核心。
- 运行时热插拔等第二个题材真实存在且需不停服切换时再议。

---

## 四、themed 治理 fail-closed

- 天雷、阴间、vote、法院等 themed 治理是**平台级 fail-closed Python System**，不落入 UGC 可编辑规则层（层1）。
- 权限策略是**启动时加载的可信配置/代码**（非可变存档），进程内求值。
- Fail-closed 语义：策略加载失败则拒绝启动。
- 门派内容（FamilyBonus / RaceProfile / SkillData / FormationData）是**题材包 CPK 资产**，不是治理逻辑；门派灵魂归属武侠题材包资产。

---

## 五、审核 pipeline 分层

| 层级 | 名称 | 自动化程度 | M3 范围 |
|---|---|---|---|
| 第 1 层 | 自动化预检 | 全自动 | 做 |
| 第 2 层 | 社区众审 | 半自动 | 后置 |
| 第 3 层 | 专家审核 | 人工 | 做 MVP（checklist） |
| 第 4 层 | 平台终审 | 人工 | 后置 |

### 自动化预检规则

- 4 类词表：
  - VIOLENCE（过度血腥）-> `needs_review`
  - SENSITIVE -> MVP 空表（合规词库需法务确认）
  - GAMBLING -> `needs_review`
  - COPYRIGHT（金庸角色名 + 门派名 + 出处小说）-> `needs_review`
- license 校验：空 license -> `block`；非空 -> 放行（M3 宽松，门3 前严格化白名单）。
- 扫描方式：通用递归遍历 CPK 内所有字符串，不依赖 layer0 Def 字段枚举。

### 审核状态

- `CpkManifest.review_status`：pending / passed / needs_review / rejected。
- 详细 findings 落 `<cpk_dir>/_review.json`，manifest 只存状态，资产与审核元数据分离。
- `passed = True` 当且仅当无 block 且 license 合规；`needs_review` 不阻塞 passed。
- M3-4 版权清洗后置：金庸命中只标记 `needs_review`，不 block。

---

## 六、Agent 创作闭环

### 核心理念

以 DSL 为唯一契约层，将 LLM 非确定性收敛到可验证终态；schema 强约束使多 Agent 交接零歧义。

### 专项能力（v1 五角色降级）

| 能力 | 职责 | 产出 |
|---|---|---|
| Worldbuilder | 世界圣经、场景拓扑 | 层0 场景 + 区域图 |
| Narrator | 对话树、剧情事件 | 层2 对话 + 层1 剧情 |
| Behaviorist | condition 状态机、chat_msg | 层1 事件规则 + condition |
| Balancer | 武功 action 数值 | 层0 技能 + 数值表（skill_power 平台级 Python 实现） |
| Continuity | 生成时约束注入 | structured output + 实体关系约束（替代事后审查） |

### 人机协作三道审批门

1. 门1 创意意图：创作启动前人类确认方向（早期开启）。
2. 门2 世界圣经：规模扩大后确认世界观一致性（后期开启）。
3. 门3 发布前：对外发布前最终审批（早期开启）。

provenance 强制点后移到门3 前。

### MCP 验证基底

1. **world-graph**：纯 stdlib BFS 图分析，出口可达性。
2. **combat-sim**：直接调用从 LPC 提取的 `resolve_attack` 纯函数。
3. **不变量回归集**：从 8400 LPC 解析入库形成基线断言。

### 六维评估矩阵

| 维度 | 方法 | 自动化程度 |
|---|---|---|
| 结构 | jsonschema / 图可达性 | 全自动 |
| 数值 | combat-sim 分布 / hypothesis property-based | 全自动 |
| 经济 | 多 agent 玩家行为仿真 | 半自动 |
| 任务逻辑 | 状态空间探索 / 模型检查 | 半自动 |
| 叙事 | LLM-as-judge | 人工抽样 |
| 趣味 | playtest agent + 人工 playtest | 人工抽样 |

### M2 MVP 范围（ADR-0053）

- 先用 layer0/1 闭合 loop，延后 layer2 Ink / layer3 RestrictedPython。
- CLI 评审工作台 `just orchestrate review <cpk>` 替代 FastAPI/WebSocket Web UI。
- Langfuse 追踪保持后置，用本地 `semantic_ratio` + `revision_trace.json`。
- 火山方舟为主 LLM 基线，`LLMClient` Protocol 保留可插拔 adapter。
- 不做 networkx，world-graph 用 stdlib BFS。

### kill criterion（Agent 创作）

- 单 CPK token 预算上限。
- 3 轮迭代后人工修订率 >40% -> 先扩层1-2 表达力。
- 扩后仍 >30% -> Agent 降级为辅助（人工为主，Agent 建议为辅）。
- LLM token 预算耗尽且未产出通过闭环的 CPK -> 停止 Agent 投入，回退人工创作 DSL。

---

## 七、核心指标 / 系统归属基线

| 指标 / 系统 | 默认 owner | 理由 | 主题无关性影响 |
|---|---|---|---|
| heart_beat tick 周期（1s，compute<100ms） | framework | 引擎核心调度不变量，所有题材共享 | 强主题无关，不允许题材包覆盖 |
| ECS 组件生命周期（创建/销毁/序列化） | framework | 核心运行时基础设施 | 强主题无关 |
| Command 管线（意图 -> ActionContext -> Capability 校验） | framework | 命令是外部意图抽象 | 强主题无关；具体命令实现可下沉题材包 |
| `do_attack` 七步管线 | framework | CombatKernel 抽象，主题无关 | 强主题无关；招式数据走 SkillData |
| PronounContext（speaker/viewer/target 三元组） | framework | 文本渲染核心，rankd.c 实证 | 强主题无关 |
| JSON 存档原子写（write-temp + os.replace） | framework | 持久化边界抽象 | 强主题无关 |
| 层1 规则求值器 | framework | 唯一规则表示层，引擎内求值 | 主题无关；谓词/动词词汇表由题材包注册 |
| layer0 schema（房间/NPC/物品字段） | framework | schema 由 ThemeRegistry 注册，核心提供验证框架 | 框架主题无关；具体 schema family 题材相关 |
| ThemeRegistry 静态加载 | framework | 启动时注册表，引擎层机制 | 强主题无关；内容题材相关 |
| CPK 加载器（manifest -> IR） | framework | DSL 编译与依赖校验基础设施 | 强主题无关 |
| 四道校验（Schema/Capability/Resource/Dependency） | framework | IR 安全与完整性 | 强主题无关 |
| RestrictedPython 沙箱 | framework | UGC 脚本执行环境 | 强主题无关；具体 capability 由题材包声明 |
| 自动化预检（暴力/赌博/版权/license） | framework | 内容审核基础设施 | 强主题无关；词表可配置 |
| 专家审核 checklist 模板 | framework | 六维矩阵与人工 review 框架 | 强主题无关 |
| 武侠门派加成（FamilyBonus 数据） | official_cpk | `wuxia` 题材包 StdLib 资产 | 主题相关；必须走 ThemeRegistry 注入 |
| 武侠 race_profile（人类/limbs/年龄公式参数） | official_cpk | `wuxia` 题材包注入；引擎只提供 setup_race 框架 | 主题相关；default 题材包可注入非武侠 profile |
| 武侠房间路径（start/death/jail rooms） | official_cpk | `wuxia` 题材包 ThemeConfig | 主题相关；核心通过 ThemeConfig 抽象 |
| 武侠 class 称号分支表 | official_cpk | `wuxia` 题材包 ThemeDescriptor.class_tables | 主题相关 |
| 武侠技能招式表（SkillData） | official_cpk | `wuxia` 题材包 CPK 资产 | 主题相关；不进 combat 内核 |
| 门派任务链数据（NPC/对话/objective） | official_cpk / user_cpk | 内容生产产出；M3 官方，后期可 UGC | 主题相关 |
| 原创第三方门派/区域 CPK | user_cpk | UGC 创作者产出，受沙箱与审核约束 | 主题相关；需声明 theme 与 capabilities |
| 玩家自建房间/NPC 事件规则 | user_cpk | UGC layer0/1 资产 | 主题相关；受 ThemeRegistry 词汇表限制 |
| 市场分发（浏览/搜索/安装/评分/分账） | framework | 平台级能力，market 字段 Day1 预留 | 强主题无关；M3 不做 |
| 版权清洗状态与 provenance 链 | framework | 平台级合规与内容追踪 | 强主题无关；命中内容由题材包产生 |
| Langfuse / 修订量追踪 | framework | M2 创作闭环度量基础设施 | 强主题无关 |

---

## 八、关键不可妥协约束

1. 开放 UGC 脚本前 per-CPK 资源配额必须就位。
2. UGC 协作开放前必须先重建 securityd 能力权限模型，不修旧代码。
3. 8400 文件批量转换前必须先做 30 文件表达力校准，层3 占比 >20% 则先扩充层1-2。
4. provenance 后移：开发期用简单版本号，门3 前强制回填。
5. combat-sim 必须调用真实 `resolve_attack` 纯函数，不依赖简化模型。
6. Agent NPC 硬隔离：LLM 只出对话文本，DSL 状态机守所有状态变更。
7. 金庸衍生 71 文件必须处理后方可对外发布。
8. themed 治理不进层1：天雷/阴间/vote/法院是平台级 fail-closed Python System。

---

*整理日期：2026-07-15*
