# 第四轮专家复审 · UGC 平台/插件架构专家

> 评审重点：CPK / ThemeRegistry / UGC 三层边界、module_pack vs ugc、题材包静态加载、受信任开发者扩展、沙箱与配额、内容市场预留。
> 评审日期：2026-07-15
> 依据上下文：context_engine.md / context_original_A.md / context_original_B.md / context_third.md / context_ugc.md，以及 engine/src/xkx/ 相关源码与 ADR。

## 总体裁定

**verdict：risky**

CPK 骨架、ThemeRegistry 静态加载与主题无关性切割已经落地，M3 阶段只做官方 `module_pack` 的策略正确；但 `module_pack` 与 `ugc` 的边界目前只是字段约定，RestrictedPython 沙箱、资源配额、能力声明校验、受信任开发者白名单均未实现，任何提前开放外部 CPK 的行为都会把“静态加载的 StdLib”直接变成“可执行任意 Python 的插件系统”，风险不可接受。

## 当前实现与侠客行核心系统的缺口

| 相关系统 | 状态 | 风险等级 | 证据（文件路径） | 建议 |
|---|---|---|---|---|
| **ThemeRegistry 静态加载** | partial | 中 | `engine/src/xkx/runtime/theme_registry.py`、`engine/src/xkx/themes/wuxia.py`、`engine/src/xkx/themes/default.py` | 注册表机制已就位，M3 注册 `wuxia` + `default` 两个题材；但 `condition_predicates`、`action_verbs`、`class_tables`、`governance_policies` 字段目前为空或默认值，未与层1 规则求值、校验器、称号系统真正挂接。建议 M3-2 补齐武侠/非武侠两套词汇表与 class 表，并加回归测试断言“未注册谓词/动词在 CPK 中使用时校验失败”。 |
| **CPK manifest 与加载器** | partial | 中 | `engine/src/xkx/dsl/cpk.py`、`engine/src/xkx/dsl/cpk_loader.py`、`engine/scenes/*/manifest.yaml` | `CpkManifest` 与 `load_cpk` 已对齐 03 §四 M3 简化版，5 个微场景已加 manifest；但依赖解析仅支持线性空列表，`resource_quota`、`provenance` 全为 `None`，`entry_points` 只有 `main_scene`。建议 UGC 开放前实现 networkx 拓扑排序+环检测，并补齐 manifest 唯一性校验。 |
| **module_pack vs ugc 边界** | at_risk | 高 | `engine/src/xkx/dsl/cpk.py` 第 36-37 行、`engine/src/xkx/orchestrator/loop.py` 第 187 行 | `pack_type` 只是字符串字段，Orchestrator 硬编码输出 `module_pack`，加载器对两种类型不做任何区分处理。没有沙箱、没有配额、没有能力门控之前，该字段不构成安全边界。建议把“开放 UGC 脚本”设为独立门禁，前置条件：沙箱+配额+能力校验全部就位。 |
| **RestrictedPython 层3 沙箱** | missing | 高 | `context_engine.md` 第 1 条、`docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md` | ADR-0053 明确 M2 MVP 延后 layer2/layer3。当前 DSL 只到层1 + 最小层2 `InquiryNode`，任何图灵完备逻辑仍需进程级 Python。建议 layer3 设计必须在 8400 文件批量转换前完成 30 文件表达力校准，层3 占比 >15% 时优先扩层1/层2。 |
| **能力声明与资源配额校验** | missing | 高 | `engine/src/xkx/dsl/cpk_loader.py` `_validate_manifest`、`engine/src/xkx/dsl/validator.py` | `capabilities_required` 与 `ResourceQuota` 已建模，但 `load_cpk` 仅校验 `theme` 注册与 `entry_points`，`SceneValidator` 四道校验只有 schema/capability/resource/dependency 最小实现，且 capability 只检查 NPC `attack_skill` 是否在 `skills` 中。建议建立 `CapabilityRegistry`，在 CPK 加载阶段校验 `capabilities_required` 与实际使用的能力集合匹配。 |
| **受信任开发者扩展机制** | missing | 高 | `engine/src/xkx/dsl/cpk.py` `PackType` | `module_pack` 被定义为“受信任开发者 / 官方 StdLib，无沙箱”，但没有任何签名、白名单或发布者校验。外部作者完全可以把 `pack_type` 写成 `module_pack` 以绕过沙箱。建议在引入外部 CPK 前增加受信任发布者列表或最小签名机制。 |
| **内容审核 pipeline** | partial | 中 | `engine/src/xkx/content_review/precheck.py`、`engine/src/xkx/content_review/rules.py`、`engine/src/xkx/content_review/review_status.py` | 自动化预检、`_review.json` 与 manifest `review_status` 分离已落地，4 类词表结构正确；但 `SENSITIVE` 为空表、`license` 只检查非空、版权命中仅 `needs_review` 不 `block`、社区众审/平台终审未实现。建议外部玩家测试前接入合规敏感词库，并把 71 文件金庸衍生内容的 M3-4 清洗计划写进 PROGRESS。 |
| **Provenance 与内容市场预留** | partial | 中 | `engine/src/xkx/dsl/cpk.py` `Provenance` / `MarketFields`、`engine/src/xkx/orchestrator/loop.py` 第 197-201 行 | `MarketFields` Day1 预留符合决策，但 `Provenance` 在 Orchestrator 中已写入 `author_type`/`model`，`content_hash`、`parents`、`prompt_hash` 均为空。建议在门3 前实现 `blake3` 内容哈希与 prompt 哈希，否则无法证明“哪个 prompt 产生了哪份资产”。 |
| **题材包数据填充** | partial | 中 | `engine/src/xkx/themes/wuxia.py`、`engine/src/xkx/themes/default.py` | 仅填充武当派与“海盗帮”两条 `FamilyBonus`，21 门派、97 技能、class 称号分支表、阵法数据均未迁移。M3 单题材 demo 可接受，但需在 M3-1 Wave 2 制定官方 StdLib CPK 填充清单，避免临时数据在 demo 中固化。 |
| **主题无关性硬门禁** | partial | 中 | `docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md`、`engine/src/xkx/runtime/race.py`、`engine/src/xkx/runtime/family.py`、`engine/src/xkx/runtime/theme.py` | race/family/theme_config 已成功外提，`test_theme_neutrality` 范围扩展到 `runtime/` 与 `dsl/`；但 `TitleComp.dali_rank`、`dbase_map.py` 的 LPC key 仍作为保真让步保留。建议持续运行 `test_theme_neutrality`，并在 ADR 中明确这些豁免项的清单与 rationale，防止后续扩散。 |
| **M2 创作闭环/Orchestrator** | partial | 中 | `engine/src/xkx/orchestrator/loop.py`、`docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md` | 生成->校验->修订->预检闭环已落地，CLI workbench 替代 Web UI 符合 MVP；但 L4 校验依赖外部 `measure_revision`，修订量 >40% 的 kill criterion 暂无自动化追踪。建议把 `revision_trace.json` 与人工修订率指标接入 PROGRESS 每周检查。 |
| **层2 Ink 对话树** | partial | 低 | `engine/src/xkx/dsl/layer2.py` | 仅实现 `InquiryNode` 原子节点，无完整 Ink 运行时。M3 用现有 `ask` 路径足够，但需在 M3 后评估是否需要真正 Ink 解释器。 |

## UGC 核心指标/系统分层建议

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|---|---|---|---|
| tick 周期、ECS 生命周期、Command 管线、`do_attack` 七步、PronounContext、JSON 原子写 | framework | 引擎核心不变量，所有题材共享 | 强主题无关，题材包不可覆盖 |
| ThemeRegistry 静态加载机制、CPK 加载器、四道校验框架、RestrictedPython 沙箱 | framework | 平台级基础设施，决定 UGC 能否安全运行 | 强主题无关；具体词汇/能力由题材包注册 |
| 层1 规则求值器 | framework | 唯一规则表示层，求值语义必须统一 | 主题无关；谓词/动词词汇表走 ThemeRegistry |
| 自动化预检、专家 checklist、审核状态与 `_review.json`、版权 provenance 链 | framework | 内容合规与追踪是平台能力 | 强主题无关；命中内容由题材包产生 |
| 市场分发字段/基础设施（浏览/搜索/安装/评分/分账） | framework | Day1 预留，M3 不做；未来由平台统一实现 | 强主题无关 |
| `RaceProfile` / `ThemeConfig` 接口与 `setup_race` / `apply_family_bonuses` 分发 | framework | 引擎提供参数化框架 | 强主题无关；具体参数由题材包注入 |
| 武侠 `RaceProfile`、门派 `FamilyBonus`、class 称号分支表、技能/招式/阵法数据 | official_cpk | 武侠题材包 StdLib 资产 | 主题相关；必须通过 ThemeRegistry 注入 |
| 非武侠测试题材（academy / age_of_sail）的 race/family/class 数据 | official_cpk | 用于主题无关性验证的官方测试资产 | 主题相关；验证 framework 的抽象能力 |
| 原创第三方门派/区域/任务 CPK | user_cpk | 普通创作者产出 | 主题相关；必须声明 theme 与 capabilities，受沙箱与配额约束 |
| 玩家自建房间/NPC/层1 规则 | user_cpk | UGC layer0/1 资产 | 主题相关；受 ThemeRegistry 谓词/动词词汇表限制 |
| 天雷/阴间/vote/法院等 themed 治理 | framework | 平台级 fail-closed Python System，不可落入 UGC 可编辑层 | 强主题无关；策略是启动时加载的可信配置/代码 |
| 能力词汇表（capabilities）注册表 | framework | 定义 UGC 可请求的能力集合 | 强主题无关；具体能力实现可由 official_cpk 提供 |
| 每 CPK 资源配额（fuel/wall_time/memory/call_out） | framework | 沙箱执行前提 | 强主题无关；`ugc` 强制，`module_pack` 可豁免但建议审计 |
| 修订量 / token 预算 / Langfuse 追踪 | framework | M2 创作闭环度量基础设施 | 强主题无关 |

## 其他全局关注点

1. **层1 原语蠕变风险（05 §五 dissent 3）**。`dsl/layer1.py` 已支持 13 类谓词与 4 类事件，新增谓词必须走 ADR 与 30 文件校准。建议设立“层1 原语委员会”式硬门：任何新谓词/动词必须同时提供（a）跨 3 个以上 LPC 文件的用例；（b）无法被现有原语组合表达的证据；（c）主题无关性测试。KPI“层3 使用率 <15%”在沙箱缺失前无法测量，应延后考核但保留字段。

2. **规则冲突语义漂移（05 §五 dissent 4）**。`valid_leave` 采用 deny-wins，`accept_object` 采用首匹配，`ask` 也采用首匹配，目前由代码分别实现；但 533 个 `valid_leave` 的 LPC 基线命中行为尚未形成可回归断言。建议抽取 20-30 个典型 LPC 触发器用例，写入 `tests/test_layer1_conflict.py`，确保 `notify_fail` 语义与 deny-wins 对齐。

3. **call_out 归属仍未交叉验证（05 §五 dissent 5）**。`ActionScheduler` 与 `ConditionSystem` 对 694 文件/3109 处 `call_out` 的归属在 `runtime/engine.py`、`runtime/systems.py` 中尚未显式区分。建议把延迟调度拆分为独立模块，并在 ADR 中明确：事件触发器归层1、`call_out` 归 ActionScheduler、周期 condition 归 ConditionSystem、连续仿真归 Combat/Heal/NPCAI。

4. **force_me / PrivilegedAction 边界（05 §五 dissent 6）**。`runtime/privileged.py` 与 `middleware/s7_execute_audit.py` 已提供机制，但未来 NPC AI 或触发器可能倾向于用 `PrivilegedAction` 绕过 Command 管线。建议增加设计约束：NPC AI 与 System tick 派生变更必须走 `System.update`，只有 ROOT 级运维/调试脚本可走 `PrivilegedAction`，且强制审计。

5. **System 派生变更审计覆盖缺口（05 §五 dissent 7）**。`middleware/s7_execute_audit.py` 主要覆盖 Command 路径；heal、condition、governance 等 System 派生变更尚无统一审计。建议在 `SystemContext` 中强制携带 `capability` 与 `audit_hook`，关键状态变更写审计日志。

6. **Agent/LLM 投入对核心循环的挤占（05 §五 dissent 10）**。M2 Orchestrator 已落地，但阶段 0 的 tick profiler、1000+100 负载测试、非武侠微场景验证仍在进行中。建议把“单 CPK 3 轮迭代人工修订率 >40%”和“1000 实体 tick p99 <100ms”同时写入 PROGRESS 的每周 check，防止平台特性过度挤占核心循环。

7. **版权与合规债务**。雪山派 CPK 已命中 4 个金庸角色 +“雪山派”门派名，M3-4 清洗后置是用户决策，但 71 文件清单与清洗方案尚未产出。建议在外部玩家测试前至少完成：71 文件盘点脚本、改编化/同人标注标准、门3 provenance 回填流程。

8. **存储迁移止损线**。JSON 原子写已实现，但“任何外部玩家测试开始前必须迁 PG”是硬止损线。建议把该检查点写进 M3 exit criteria，并在当前 JSON 实现中补齐 write-temp + os.replace、事件循环外 offload、dirty-flag 分摊的回归测试。

## Top 3-5 风险

1. **`module_pack` / `ugc` 边界名存实亡：沙箱、配额、能力校验全部缺失，外部 CPK 可借 `module_pack` 执行任意进程级 Python。** 严重性：high；证据：`engine/src/xkx/dsl/cpk.py`、`engine/src/xkx/orchestrator/loop.py`、context_engine.md。

2. **层3 RestrictedPython 沙箱未实现，导致图灵完备逻辑无法安全下沉，层1 原语蠕变压力将持续增大。** 严重性：high；证据：`docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md`、`engine/src/xkx/dsl/layer2.py`。

3. **受信任开发者模型空白：`module_pack` 没有签名/白名单，仅凭 `pack_type` 字段无法区分官方 StdLib 与外部插件。** 严重性：high；证据：`engine/src/xkx/dsl/cpk.py`。

4. **ThemeRegistry 词汇表（`condition_predicates` / `action_verbs`）未真正启用，CPK 可能引用未注册谓词/动词而静默失败或产生未定义行为。** 严重性：medium；证据：`engine/src/xkx/runtime/theme_registry.py`、`engine/src/xkx/dsl/cpk_loader.py`。

5. **Provenance 与版权追踪不完整：`content_hash`/`prompt_hash` 为空，71 文件金庸衍生内容未清洗，门3 合规回填存在大量债务。** 严重性：medium；证据：`engine/src/xkx/dsl/cpk.py`、`docs/adr/ADR-0033-content-review-pipeline-mvp.md`。
