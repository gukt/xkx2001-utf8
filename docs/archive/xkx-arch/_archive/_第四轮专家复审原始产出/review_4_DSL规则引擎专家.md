# 第四轮专家复审：DSL / 规则引擎专家

## 总体裁定

**verdict：risky**

DSL 层0 / 层1 / 层2 已按 M2/M3 节奏落地，层3 RestrictedPython 沙箱因 MVP 范围明确延后；但层1 谓词 / 动作集缺乏 ThemeRegistry 词汇表硬门禁，`capabilities_required` 与词汇表未绑定，规则冲突检测与 LPC 基线覆盖不足，`command` 事件尚未接入命令管线，存在"层1 原语蠕变"与"隐性规则引擎化"的明确风险，需在 M3 收官前补全护栏。

## 当前实现与侠客行核心系统的缺口

| 相关系统 | 状态 | 风险等级 | 证据 | 建议 |
|---------|------|---------|------|------|
| **DSL 层0 声明式数据** | partial | medium | `engine/src/xkx/dsl/layer0.py`；已覆盖 RoomDef / NpcDef / ItemDef / QuestDef / SkillDef / ApprenticeDef / KneelDef；`ADR-0032` 将拜师 / 任务链 / 技能数据归入层0 | 补全 `SkillDef` 与 `combat.context.SkillData` 的招式表映射；将 `item_category`（weapon / armor / key 等）注册到 `ThemeDescriptor`，供 `has_item` 谓词主题化校验 |
| **DSL 层1 condition-action 求值** | partial | high | `engine/src/xkx/dsl/layer1.py`；已实现 `valid_leave`（deny-wins）、`accept_object`（首匹配）、`ask`（首匹配 + set_flag）、`command`（deny-wins）；`runtime/commands.py` 中 `go()` / `ask()` / `give()` 已调用 | 将 `evaluate_command` 接入 8 段命令管线（当前仅单元测试调用）；为 `valid_leave` / `accept_object` 增加 LPC 抽样基线回归测试；修复 `status_eq` 用集合字符串编码 `flag=value` 的脆弱约定；增加规则冲突检测（同方向同 priority 多条 deny / 同 npc_id+item_id 多条 accept_object） |
| **DSL 层2 Ink 对话树** | partial | medium | `engine/src/xkx/dsl/layer2.py`；`InquiryNode` 已落地并接入 `NpcDef.inquiry`；`compile_ink_to_inquiries` 仅支持线性 knot | 保持 M3 最小闭环；后续扩展选择支 / 循环时，所有状态变更仍须走层1 规则或 `InquiryNode` 显式字段，禁止在层2 解释器中引入任意 Python 表达式 |
| **DSL 层3 RestrictedPython 沙箱** | missing | medium-high | 目录无 `dsl/layer3.py`；`ADR-0053` 明确本 Wave 不做 | 在 M3 后 Wave 3 启动设计：沙箱 AST 白名单、`resource_quota`（fuel / wall_time / memory / call_out）计费、`capabilities_required` 到运行时权限的映射 |
| **`capabilities_required` 与词汇表** | partial | high | `engine/src/xkx/dsl/cpk.py` 有字段但仅空列表；`engine/src/xkx/runtime/theme_registry.py` 有 `condition_predicates` / `action_verbs` 字段但 `themes/wuxia.py`、`themes/default.py` 未填充；`engine/src/xkx/orchestrator/capabilities.py` 仅做生成任务调度，不做运行时校验 | 为每个题材包填充已注册谓词 / 动作 / 事件类型集合；CPK 加载器校验规则仅使用注册词汇；将 `capabilities_required` 映射为"所需谓词 + 动作 + 事件 + 系统能力"的并集 |
| **CPK 加载器与四道校验** | partial | medium | `engine/src/xkx/dsl/cpk_loader.py` 实现 manifest -> IR / 规则 / 技能加载；`engine/src/xkx/dsl/validator.py` 为最小实现，仅覆盖 schema / 攻击技能 / 非负数值 / 引用完整性 | 扩展校验器：规则 `npc_id` / `item_id` / `topic` 引用完整性、`spawn_items` 目标房间存在性、规则冲突、`capabilities_required` 审计；M3 后补 networkx 依赖图与环检测 |
| **内容审核 pipeline** | partial | medium | `engine/src/xkx/content_review/rules.py` / `precheck.py` / `review_status.py` / `checklist.py` 已实现 4 类词表 + license + 六维 checklist；`ADR-0033` 将版权命中标记为 `needs_review` | 将"规则冲突 / 能力声明违规"作为预检或校验器的一类 finding；敏感词库接入前保持空表；license 白名单与 provenance 链按门3 计划回填 |
| **是否蠕变成事实规则引擎** | at_risk | high | 层1 谓词从 S1 4 个增至当前 15 个叶子 + 组合；动作从 deny/allow 扩展出 set_flag / clear_flag / spawn_items；`command` 事件已引入；每次扩展均有 ADR，但无运行时词汇表硬门禁 | 建立并发布《层1 谓词 / 动作 / 事件类型目录》；新增原语必须通过"可声明式且跨规则复用"测试；维持 <15% 层3 逃生舱 KPI，并在 `measure_revision` 中统计规则中未收录谓词的比例 |

## UGC 核心指标 / 系统分层建议

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|------------|-----------|------|----------------|
| heart_beat tick 周期（1 s，compute < 100 ms） | framework | 引擎核心调度不变量，所有题材共享 | 强主题无关，题材包不可覆盖 |
| ECS 组件生命周期 | framework | 核心运行时基础设施 | 强主题无关 |
| Command 管线与 ActionContext | framework | 外部意图抽象；具体命令实现可下沉题材包 | 强主题无关；动词表可由题材包扩展 |
| `do_attack` 七步管线 | framework | CombatKernel 抽象，招式数据走 SkillData | 强主题无关 |
| PronounContext（speaker/viewer/target） | framework | 文本渲染核心，`rankd.c` 实证 | 强主题无关 |
| JSON 存档原子写 | framework | 持久化边界抽象 | 强主题无关 |
| DSL 层0 schema 框架 | framework | ThemeRegistry 注册具体 schema family | 框架主题无关；具体字段题材相关 |
| DSL 层1 规则求值器 | framework | 唯一规则表示层，引擎内求值 | 主题无关；谓词 / 动词词汇表由题材包注册 |
| DSL 层2 对话树运行时 | framework | 解释器框架；具体对话内容由 CPK 提供 | 主题无关；文本题材相关 |
| DSL 层3 RestrictedPython 沙箱 | framework | UGC 脚本执行环境 | 强主题无关；具体 capability 由题材包声明 |
| ThemeRegistry 静态加载机制 | framework | 启动时注册表，引擎层机制 | 强主题无关；注册内容题材相关 |
| CPK 加载器与四道校验框架 | framework | DSL 编译、依赖与完整性基础设施 | 强主题无关 |
| `capabilities_required` 审计 | framework | 安全边界，衔接词汇表与运行时权限 | 强主题无关 |
| 自动化预检（暴力 / 赌博 / 版权 / license） | framework | 内容审核基础设施；词表可配置 | 强主题无关 |
| 专家审核 checklist 模板 | framework | 六维矩阵与人工 review 框架 | 强主题无关 |
| 武侠门派加成（FamilyBonus） | official_cpk | `wuxia` 题材包 StdLib 资产 | 主题相关；须经 ThemeRegistry 注入 |
| 武侠 race_profile / class 称号表 | official_cpk | 题材包注入；引擎只提供框架 | 主题相关；default 题材包注入非武侠 profile |
| 武侠技能招式表（SkillData） | official_cpk | 题材包 CPK 资产 | 主题相关；不进 combat 内核 |
| 门派任务链数据 | official_cpk / user_cpk | M3 官方，后期可开放 UGC | 主题相关 |
| 玩家自建房间 / NPC 事件规则 | user_cpk | UGC 层0 / 层1 资产 | 主题相关；受 ThemeRegistry 词汇表限制 |
| 原创第三方门派 / 区域 CPK | user_cpk | UGC 创作者产出，受沙箱与审核约束 | 主题相关；需声明 theme 与 capabilities |
| 版权清洗状态与 provenance 链 | framework | 平台级合规与内容追踪 | 强主题无关；命中内容由题材包产生 |
| Langfuse / 修订量追踪 | framework | M2 创作闭环度量基础设施 | 强主题无关 |
| 市场分发（浏览 / 搜索 / 安装 / 评分 / 分账） | framework | 平台级能力，`market` 字段 Day1 预留 | 强主题无关；M3 不做 |

## 其他全局关注点

1. **`command` 事件未接入 8 段命令管线**：`layer1.py` 已实现 `evaluate_command`，但 `runtime/commands.py` 的 `COMMAND_REGISTRY` / 中间件并未调用它；自定义命令前置 deny（如 `knock` / `enter`）目前仍由命令函数自身或层3 处理，存在绕过层1 护栏的路径。

2. **`EvalContext` 构造方式偏重**：`commands.py` 中 `_eval_ctx` 每次从 ECS 抽取 actor 属性、门派、物品、标记等全量集合，未评估 1000 在线 / 100 并发下的 tick 内求值开销。建议在 profiler 中增加"层1 规则求值次数与耗时"指标。

3. **`status_eq` 的值比较实现脆弱**：用 `actor_flags` 集合元素形如 `flag=value` 的字符串约定来支持值比较，既破坏集合语义，也容易被 UGC 内容中的等号文本误触发。应改为 `EvalContext` 显式携带 `dict[str, str]` 标记值映射。

4. **内容预检与 DSL 校验分离**：`precheck.py` 通用递归扫描字符串，无法区分叙事文本与规则字段；建议将"规则使用了未注册谓词 / 动作"作为 `SceneValidator` 或 `PrecheckReport` 的独立 finding 类别，而非仅依赖字符串命中。

5. **M2 Agent 生成规则的词汇表约束**：`orchestrator/capabilities.py` 按 asset 类型调度生成器，但未在生成阶段注入"当前题材允许使用的谓词 / 事件 / 动作列表"。应把 ThemeRegistry 词汇表作为 prompt / structured output 约束，防止 LLM 产出无法通过 CPK 校验的规则。

6. **themed 治理未落入层1**：`governance.py` 中阴间 / 法院 / PK 等逻辑仍是平台级 Python System，符合 `CLAUDE.md` 与 `ADR-0029` 裁决；需持续禁止将天雷 / 阴间 / vote / 法院规则改写为层1 规则。

## Top 3-5 风险

1. **层1 原语蠕变且无词汇表硬门禁，退化为事实规则引擎（high）**  
   当前层1 谓词 15 个、动作 5 类、事件 4 类，且每次扩展都有 ADR，但 ThemeRegistry 的 `condition_predicates` / `action_verbs` 为空，CPK 加载器不校验规则词汇。一旦为赶 M3 进度继续添加"临时"谓词 / 动作，将直接违反 02 Q2 "否决独立规则引擎"的裁决。

2. **`command` deny 与层1 副作用未接入真实命令管线，行为等价验证不足（high）**  
   `evaluate_command` 仅在单元测试中被调用，`runtime/commands.py` 未在中间件或 adapter 中集成；`spawn_items` / `set_flag` / `clear_flag` 虽在 `go` / `ask` / `give` 中生效，但缺少与 LPC 同一场景的成对基线断言，533 `valid_leave` 等触发器的冲突语义尚未被回归测试锁定。

3. **`capabilities_required` 与 ThemeRegistry 词汇表未绑定，UGC 安全边界悬空（medium-high）**  
   `CpkManifest.capabilities_required` 目前只是空列表字段，未映射到层1 谓词 / 动作 / 事件 / 运行时权限。开放 UGC 沙箱前，必须先建立"capability -> 词汇表子集 + 资源配额 + 运行时权限"的显式映射，否则沙箱策略无法落地。

4. **规则冲突检测与 LPC 基线测试缺失，语义漂移风险（medium）**  
   `SceneValidator` 不检查同方向同 priority 的多条 `valid_leave` deny 规则、不检查同 `npc_id+item_id` 的多条 `accept_object` 规则、不检查 `spawn_items` 目标房间存在性。LPC 依赖注册顺序隐式覆盖，greenfield 若未将原命中行为写入基线断言，迁移后易出现 `notify_fail` / deny-wins 语义漂移。

5. **层3 沙箱与资源配额缺失，开放 UGC 前无法执行"不可妥协约束1/2"（medium）**  
   `ADR-0053` 明确本 Wave 不做层3，但项目约束要求"开放 UGC 脚本前 per-CPK 资源配额必须就位"、"UGC 协作开放前必须先重建 securityd 能力权限模型"。M3 收官后应立刻将层3 / capability / quota 设计排入下一 Wave，否则 UGC 开放时间将被迫延后。
