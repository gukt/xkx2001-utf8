# 第三轮专家复审 · dissent 与未消除风险摘要

> 来源：[05-第三轮专家对抗复审报告](../../05-第三轮专家对抗复审报告.md) + `_archive/_第三轮专家复审原始产出/`（digest/verdict.json/6 份 review.json/3 份 debate.json）。
> 本文件为第四轮专家复审提供上下文，聚焦 10 条关键 dissent、当前 engine 缓解状态与仍需关注的风险。

---

## 一、10 条关键 dissent / 未消除风险

### 1. CombatKernel 抽象时机张力（Q1）

- **dissent 内容**：CombatKernel 需同时满足“从武侠 do_attack 七步提取（保深度）”与“用非武侠微场景验证主题无关性（保可移植）”。在武侠深度尚未完整实现时提取接口，可能过窄（锁死武侠语义）或过宽（平庸化）。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/combat/resolve_attack.py`、`engine/src/xkx/combat/context.py`、`engine/src/xkx/combat/system.py` 已按七步管线实现；`engine/src/xkx/themes/wuxia.py` 为唯一题材包；非武侠微场景验证未见独立测试套件。
- **仍需关注的风险**：阶段 -1 非武侠微场景硬门禁是否真正落地； CombatKernel 接口在迁移更多武侠招式时是否会回渗武侠语义。

### 2. “第二个题材真实存在”触发条件未定义（Q1）

- **dissent 内容**：运行时热插拔被后置，但“何时重新引入”的触发条件（第二个题材真实存在且需不停服切换）未量化定义，容易滑成“永不考虑”，低估迁移成本。
- **当前 engine 缓解状态**：open
- **证据文件**：`engine/src/xkx/runtime/theme_registry.py` 为启动时静态加载；`docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md` 未涉及多题材触发条件；`engine/src/xkx/themes/` 仅含 `default.py` / `wuxia.py`。
- **仍需关注的风险**：门派灵魂（SkillBehavior）从核心引擎/race 层剥离为题材包资产的切割方案未文档化；human.c 19 门派 if-else 加成迁移路径未在阶段 2 明确。

### 3. 层1 原语蠕变（Q2）

- **dissent 内容**：为覆盖更多 LPC 触发器行为，可能反复扩充 DSL 层1 条件/动作原语，使层1 逐步长成事实上的规则引擎，违反“否决独立规则引擎”的裁决。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/dsl/layer1.py` 持续扩展（ADR-0040 新增 ask/clearflag/spawnitems 等）；`engine/src/xkx/dsl/layer2.py` 为新增层；`docs/adr/ADR-0046-sampling-calibration-methodology.md` 提出 30 文件校准但尚未完成。
- **仍需关注的风险**：层1 与层2/层3 边界是否严格执行“可声明式且跨规则复用才扩层1，需图灵完备则下沉层3”；KPI < 15% 逃生舱使用率尚无实测数据。

### 4. 规则冲突语义漂移（Q2）

- **dissent 内容**：LPC 依赖注册顺序隐式覆盖触发器命中，层1 若 priority / deny-wins / 首匹配语义未严格对齐，533 valid_leave 等触发器迁移后行为会漂移。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/dsl/layer1.py` 含规则求值；`engine/src/xkx/runtime/commands.py` 中 `go` 命令触发 valid_leave；verdict.json 明确要求“写进基线测试断言原 LPC 命中行为”。
- **仍需关注的风险**：valid_leave、accept_object、add_action 等事件的冲突解决基线测试尚未见完整覆盖；notify_fail 语义与 deny-wins 对齐需逐事件验证。

### 5. call_out 归属未交叉验证（Q2）

- **dissent 内容**：DSL/规则引擎专家独家将 call_out（694 文件/3109 处）归入 ActionScheduler，其他专家未充分确认；call_out 与 ConditionSystem / EventBus 的边界需实现时明确。
- **当前 engine 缓解状态**：open
- **证据文件**：`engine/src/xkx/runtime/engine.py` 与 `engine/src/xkx/runtime/systems.py` 尚未显式区分 ActionScheduler 与 ConditionSystem 对 call_out 的归属；`engine/src/xkx/conditions.py` 含周期 condition 逻辑。
- **仍需关注的风险**：call_out 若被错误地统一进规则求值，会重蹈“事件驱动替代 heart_beat”覆辙；延迟/自递归调度与周期 condition 的语义四分可能实现不一致。

### 6. force_me 边界侵蚀（Q3）

- **dissent 内容**：force_me 被映射为 PrivilegedAction（Command 变体），明确是“仅外部意图”规则的保真让步；若未来 NPC AI 或触发器大量使用，会侵蚀 Command / System 边界。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/runtime/privileged.py` 实现 PrivilegedAction；`engine/src/xkx/runtime/middleware/s7_execute_audit.py` 提供执行审计；`feature/command.c:89-95` 实证 4 个调用点（updated.c/cost.c/to.c×2）。
- **仍需关注的风险**：PrivilegedAction 调用点是否被严格限制为 ROOT 门控 + 强制审计；NPC AI / 触发器是否被约束为走 System.update 而非 PrivilegedAction。

### 7. 派生变更审计覆盖缺口（Q3）

- **dissent 内容**：System.update 直接产生的 mutation（战斗外 exp/jingli、condition 效果、heal 等）不经 Command，因此缺少 Command 级审计轨迹；战斗有副作用账本覆盖，其他 System 需逐个决定审计粒度。
- **当前 engine 缓解状态**：open
- **证据文件**：`engine/src/xkx/runtime/system_context.py` 提供轻量 SystemContext；`engine/src/xkx/runtime/middleware/s7_execute_audit.py` 主要覆盖 Command 路径；`engine/src/xkx/runtime/heal.py`、`engine/src/xkx/runtime/conditions.py` 为 System 派生变更。
- **仍需关注的风险**：关键 System（heal/condition/death/governance）的状态变更是否具备可回溯审计；SystemContext 是否携带足够能力/审计钩子。

### 8. 存储收缩丢失语义（制作人）

- **dissent 内容**：内存+JSON 存档不是简单“换存储”，而是丢失了事务原子性、崩溃恢复、并发写 CAS、关系完整性、append-only 不可篡改等语义，必须逐一标注并设止损线。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/runtime/storage.py` 实现 StorageBackend 与 JSON 原子写；`docs/adr/ADR-0038-kill-criteria-5-round4-rooms-known-ids-quests-manual.md` 等设止损线；`engine/src/xkx/runtime/serialization.py` 处理序列化。
- **仍需关注的风险**：JSON 实现是否完整覆盖 write-temp + os.replace、事件循环外 offload、dirty-flag 分摊、关键事件强制同步 persist；外部玩家测试前迁 PG 的硬止损线是否被严格执行。

### 9. 1000+100 无 Rust 退路是未验证赌注（制作人）

- **dissent 内容**：从实测 MAX_USERS=50 的 20 倍跃升到 1000 在线+100 并发，约束4 砍掉 Rust/Go 退路，若 kill criteria 不到位则是无 Plan B 的赌注。
- **当前 engine 缓解状态**：open
- **证据文件**：`docs/adr/ADR-0046-sampling-calibration-methodology.md` 开始工时校准；`engine/src/xkx/runtime/profiler.py` 提供 tick profiler；阶段 0 micro-benchmark go/no-go 门禁尚未见完整报告；1000+100 负载测试未执行。
- **仍需关注的风险**：tick compute < 100ms、非均匀 tick、GC 调优（gc.freeze / gen0 抑制）是否已在基准中验证；双失败后重新评估 Rust/Go 热路径的触发条件是否明确。

### 10. 平台特性并行范围过载（制作人）

- **dissent 内容**：4 层 DSL、Agent 编排、6 维评估、CPK+provenance、ThemeRegistry、沙箱+配额、审核 pipeline、创作者经济等平台特性远超“单机 1000+100 验证”，应与引擎+核心循环验证显式串行而非并行。
- **当前 engine 缓解状态**：partial
- **证据文件**：`engine/src/xkx/content_gen/`、`engine/src/xkx/content_review/`、`engine/src/xkx/orchestrator/loop.py`、`engine/src/xkx/workbench/` 均处于 M2 UGC 创作闭环 MVP 实现中；`docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md` 对范围做了收缩；`docs/adr/ADR-0054-m2-2-langfuse-still-postponed.md` 明确 Langfuse 不接。
- **仍需关注的风险**：M2 的 Agent/LLM/MCP/RAG 投入是否挤占阶段 0 核心循环与性能基准的人工/算力；单 CPK 人工修订量 >40% 的 kill criterion 是否被持续追踪。

---

## 二、9 条 kill criteria 中当前应重点关注的 3-5 条

完整 9 条见 [04-迁移路径与避坑清单](../../../04-迁移路径与避坑清单.md) 第四节与 `verdict.json`。结合当前阶段 0 pilot 实测与 M2 UGC 闭环 MVP 状态，应重点关注：

1. **阶段0：micro-benchmark 单 do_attack 超阈值 / 1000 实体 tick 超预算 / 1000+100 不达标**
   - 当前 profiler 已就位，但 go/no-go 门禁报告尚未产出；这是约束4（纯 Python）与约束3（单机 1000+100）的唯一承重验证。

2. **JSON 存储：任何外部玩家测试开始前必须迁 PG**
   - engine 当前 JSON 存档实现需持续验证原子写/offload/dirty-flag；该条是硬止损线，不可因 MVP 进度而模糊。

3. **Agent 创作：单 CPK 经 3 轮迭代后人工修订量仍 >40% / 扩后仍 >30%**
   - M2 UGC 闭环 MVP 正处于 Agent 创作验证期，修订量趋势决定 DSL+Agent 假设是否成立，直接影响范围过载风险。

4. **阶段-1：非武侠微场景无法验证 CombatKernel 内核主题无关性**
   - 当前 combat/ 已围绕武侠七步构建，若缺少非武侠微场景硬门禁，CombatKernel 主题无关性无法证成，第二题材扩展将背负高额重构债务。

5. **项目级：18 个月未达 M3（单题材可玩 demo）**
   - 在平台特性并行推进背景下，该条是总范围刹车；需确保 M2/M3 里程碑不被 Agent/内容生成开销过度挤占。

---

## 三、给第四轮复审的提示

- 优先验证上述 **open / partial** 项是否有新的工程证据或 ADR 更新；特别关注 `ADR-0046` 采样校准、`ADR-0053` M2 范围、`ADR-0054` Langfuse 不接的后续影响。
- 若本轮新增偏离 00-04 基线或 05 裁决的设计，必须写新 ADR 并关联上述对应 dissent 编号。
