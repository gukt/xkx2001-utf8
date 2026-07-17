# 第四轮专家评审：游戏引擎/ECS 专家

## 总体裁定

**verdict：risky**

ECS 骨架与 combat-only 确定性边界已正确落地，SparseSet、System tick 注册、Effect 账本、主题无关性硬门禁均符合 ADR-0017/0023/0030/0031 的裁决；但 1000+100 性能门禁尚未实测，`call_out` 的调度归属、`ActionScheduler` 抽象、`System` 注册顺序等关键边界仍处 ad-hoc 桥接状态，存在运行时语义漂移与性能不可知风险。

---

## 当前实现与侠客行核心系统的缺口

| 系统 | 状态 | 风险等级 | 证据 | 建议 |
|------|------|----------|------|------|
| **单进程 ECS/SparseSet** | implemented | 低 | `engine/src/xkx/runtime/ecs.py` | `_SparseSet` 按组件类型分 store，O(count) 遍历 + O(1) 单实体查询，`entities_with` 已按最小 store 优化。建议为 `entities_with` 增加缓存或预排序版本，供高频 archetype 查询使用。 |
| **Schema 注册与组件校验** | implemented | 低 | `engine/src/xkx/runtime/schema.py`、`runtime/ecs.py:94` | ADR-0019 已落地，未注册组件类型 raise `SchemaError`。建议将 `World._stores` 等内部字段改为受保护命名，避免 `storage.py/governance.py` 直接访问 `world._stores`。 |
| **System 基类与注册表** | partial | 中 | `engine/src/xkx/runtime/systems.py`、`runtime/engine.py` | `System` 仅为空抽象；`Engine` 用 duck-typed `SystemLike` 注册，`CombatBridge`、`world.storage_system` 等为 ad-hoc 注入。建议补 `System` 抽象优先级/阶段位（如 `update_phase`），并将动态属性收敛到 `World` 显式字段或 `EngineContext`。 |
| **tick 调度与非均匀 tick** | partial | 中 | `engine/src/xkx/runtime/engine.py` | `tick=1s` + `compute<100ms` 已测量，但**未在调度器内实施硬性预算截断**（超预算仅报告不降级）。建议增加 `tick_budget_ms` 参数与慢 System 告警/跳 tick 策略。 |
| **combat-only 确定性** | implemented | 低 | `engine/src/xkx/combat/replay.py`、`combat/resolve_attack.py`、`combat/rng.py` | `CombatSnapshot` + `InputEntry` + `DeterministicRNG` + `replay` 纯函数链路完整，`test_theme_neutrality.py` 硬门禁持续通过。 |
| **战斗 System 边界** | partial | 中 | `engine/src/xkx/combat/system.py`、`runtime/engine.py:147` | `CombatSystem` 在 `combat/` 包自包含，通过 `CombatBridge` 桥接，避免 combat->runtime 依赖；但 `CombatBridge` 直接写 `world.combat_selects` 与 `world.pending_messages` 等动态属性，未走 System 返回值。建议把跨层临时状态收敛到 `EffectComp` 或显式的 tick 上下文对象。 |
| **condition System** | partial | 中 | `engine/src/xkx/runtime/conditions.py` | `ConditionSystem` 继承 `System`，handler 注册表机制完整，`ConditionTickResult` 提供审计账本。但 `death_stage` 与 `door_close` 通过 `effect_id` 过滤被 `ConditionSystem` 跳过，实际由 `GovernanceSystem`/`DoorSystem` 处理，该约定未在类型系统/注册表中显式表达，易新增 handler 时遗漏。 |
| **heal/exp 等非战斗 System** | partial | 高 | `engine/src/xkx/runtime/heal.py` | `HealSystem` 已实现但**未继承 `System`**（源码第 37 行 `class HealSystem(System)` 已继承，OK），但 `heal_up` 直接 mutate Vitals 无 Effect 账本。 dissent 7 指出 System 派生变更缺少 Command 级审计；`HealSystem` 应记录变更到统一 mutation log 或 ledger。 |
| **GovernanceSystem（阴间/法院）** | partial | 中 | `engine/src/xkx/runtime/governance.py` | 平台级 fail-closed 语义正确，死亡阶段、通缉、审判、监狱释放均走 `ThemeConfig` 注入。但 `death_stage` EffectComp 与通用 condition 混用同一 `EffectComp` schema，仅靠 `effect_id` 字符串区分；建议加 `system_owner` 字段显式标注所属 System，防止过滤遗漏。 |
| **StorageSystem/JSON 崩溃恢复** | partial | 中 | `engine/src/xkx/runtime/storage.py` | write-temp + fsync + os.replace、offload 线程、dirty-flag、Effect next_tick 对齐均实现。但 `DEFAULT_PERSIST_INTERVAL=30`、`DEFAULT_CHECKPOINT_INTERVAL=10` 偏小，1000 实体全量 checkpoint 时单次 IO 可能冲击 100ms 预算；建议做 IO 压力基准并允许配置。 |
| **call_out / ActionScheduler** | at_risk | 高 | `engine/src/xkx/runtime/engine.py` 注释提及 `ActionScheduler`、但未找到独立实现 | `call_out` 被分散到 `EffectComp.next_tick`、`ConditionSystem`、`GovernanceSystem`、`DoorSystem`。 dissent 5 风险未消除：延迟/自递归调度与周期 condition 的语义四分尚未交叉验证。建议补一个 `ActionScheduler` System 原型，把非周期、一次性、可自递归的 call_out 从 `EffectComp` 中剥离。 |
| **对象生命周期（swap/clean_up/autoload）** | missing | 中 | 无对应实现 | LPC 的 `swap`、`clean_up`、`autoload`、对象引用管理均未迁移。当前 ECS 中实体只增不删（除非 `world.remove` 组件），长期运行下 `_next_id` 单调递增。建议阶段 2 评估 entity id 回收或 64-bit id。 |
| **性能门禁（1000+100）** | at_risk | 高 | `engine/src/xkx/runtime/profiler.py` | `TickProfiler` 就位，但缺少 1000 实体/100 并发/单 do_attack 的 go/no-go 报告。这是约束 3/4 的唯一承重验证，必须尽快产出。 |
| **ThemeRegistry 与题材包加载** | partial | 中 | `engine/src/xkx/runtime/theme_registry.py`、`themes/wuxia.py`、`themes/default.py` | 静态注册表、`wuxia` + `default` 题材、`FamilyBonus` 注入均落地。但 `class_tables`、`condition_predicates`、`action_verbs` 仍为空或部分填充，M3-1 需补全门派与词汇表。 |
| **层3 RestrictedPython 沙箱** | missing | 高 | 无对应实现 | ADR-0053 明确 M2 MVP 延后 layer3，但 UGC 开放前沙箱是硬依赖。建议在 M3 收尾前给出 layer3 设计草案与 capability->沙箱 API 映射。 |

---

## UGC 核心指标/系统分层建议

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|------------|-----------|------|----------------|
| ECS SparseSet / World 生命周期 | framework | 运行时基础设施，所有题材共享 | 强主题无关 |
| tick 调度器 / 非均匀 tick | framework | 引擎核心不变量 | 强主题无关；题材包不可覆盖 tick 周期 |
| System 注册表与执行顺序 | framework | 平台级调度机制 | 强主题无关；具体 System 实现可下沉题材包 |
| CombatKernel（do_attack 七步管线） | framework | 主题无关内核，已用非武侠验证 | 强主题无关；招式数据走 SkillData |
| `resolve_attack` / `DeterministicRNG` / `replay` | framework | 纯函数重放基础设施 | 强主题无关 |
| Effect 账本与 apply_effects | framework | 跨 System 的副作用抽象 | 强主题无关；具体 effect kind 可扩展 |
| ConditionSystem 与 handler 注册表 | framework | 周期 condition 的平台级求值框架 | 强主题无关；具体 condition handler 可由题材包注册 |
| ActionScheduler（call_out） | framework | 延迟/自递归调度的平台级机制 | 强主题无关；具体 call_out 内容由题材包/CPK 产生 |
| HealSystem / 自然恢复公式 | framework | 通用资源恢复框架 | 强主题无关；题材包可注册种族/环境修正 |
| GovernanceSystem（阴间/法院） | framework | 平台级 fail-closed Python，不进 UGC | 强主题无关；房间路径由 ThemeConfig 注入 |
| ThemeRegistry 静态加载 | framework | 启动时注册机制 | 强主题无关；内容题材相关 |
| CPK 加载器 / manifest 校验 | framework | DSL 编译与依赖校验基础设施 | 强主题无关 |
| RestrictedPython 沙箱 | framework | UGC 脚本执行环境 | 强主题无关；capability 由题材包声明 |
| 层1 规则求值器 | framework | 唯一规则表示层 | 强主题无关；谓词/动词词汇表由题材包注册 |
| 层2 Ink 对话树编译器 | framework | 将 InkStory 编译为运行时原子 | 强主题无关；具体对话内容由 CPK 提供 |
| 武侠 FamilyBonus / RaceProfile / class 表 | official_cpk | `wuxia` 题材包 StdLib 资产 | 主题相关 |
| 非武侠 FamilyBonus / RaceProfile（default） | official_cpk | `default` 题材包验证用 | 主题相关 |
| 武侠技能招式表 SkillData | official_cpk | `wuxia` 题材包资产，不进内核 | 主题相关 |
| 具体 condition handler（snake_poison/drunk 等） | official_cpk | 武侠题材具体行为，可注册到 framework handler 表 | 主题相关；handler 接口主题无关 |
| 玩家/第三方 CPK（房间/NPC/任务/规则） | user_cpk | UGC 产出，受沙箱与审核约束 | 主题相关；必须声明 theme 与 capabilities |
| 市场分发 / provenance / 版权清洗 | framework | 平台级能力 | 强主题无关；命中内容由题材包产生 |

---

## 其他全局关注点

1. **System 间隐式顺序依赖**
   `Engine.systems` 按 `add_system` 顺序执行。当前 `CombatBridge` 在 `ConditionSystem` 之后、`StorageSystem` 之前注册（依赖 build_world/CLI 初始化顺序），但无文档或机制保证。若 `ConditionSystem` 与 `CombatSystem` 同一 tick 都产生 damage effect，应用顺序会影响最终数值。建议在 ADR 中明确 System update phase（如 `pre_combat`、`combat`、`post_combat`、`persist`）。

2. **动态属性的可维护性**
   `world.storage_system`、`world.theme_config`、`world.current_tick`、`world.pending_messages`、`world.combat_selects` 均为运行时动态附加属性。虽然收敛了 LPC `this_object()` 风格，但削弱了类型安全。建议将这些常用字段提升为 `World` 的显式可选字段，或使用 `EngineContext` 对象传递给 System.update。

3. **消息系统的 M3 风险**
   `world.pending_messages` 作为全局列表缓冲 System/Command 消息，当前 CLI 自动推进时全量打印。100 并发时该列表会快速膨胀，且缺乏按 viewer 分发的路由。M3 必须引入 `ConnectionSystem`/`ws_server` 的消息 ring buffer 与 PronounContext 三元组渲染。

4. **`EffectComp` 被多 System 共用的过滤风险**
   `EffectComp` 同时承载 condition、death_stage、door_close、exercise/respirate 等语义。`ConditionSystem` 通过 `effect_id` 黑名单跳过非其所属的条目，这是一种保守做法，但扩展新 System 时容易遗漏过滤条件。建议为 `EffectComp` 增加 `owner_system: str` 字段，使各 System 只遍历自己拥有的 effect。

5. **UGC 沙箱与 System 边界**
   当前 `module_pack` 官方 CPK 是进程级 Python，可直接注册 condition handler 或自定义 System。一旦开放 `user_cpk` 的 layer3 脚本，必须限制其只能：
   - 注册层1 谓词/动词；
   - 生成 `EffectComp` 或调用 capability 白名单内的 framework API；
   - 不能创建新的 System 或修改 tick 调度顺序。
   该约束尚未在 capability 模型中显式定义。

6. **性能基准的缺失**
   `ADR-0012` 只验证了单 `resolve_attack` 的 μs 级耗时；`TickProfiler` 只提供采样框架。阶段 0 kill criteria 要求的"1000 实体 tick 超预算"与"1000+100 不达标"尚无实测数据。应在 CI 中加入 `tests/test_load_*.py` 门禁。

---

## Top 3-5 风险

1. **性能门禁未验证（高）**
   约束 3（单机 1000 在线 + 100 并发）与约束 4（纯 Python）共同构成未验证赌注。当前仅有单函数微基准，缺少 1000 实体并发 tick、JSON checkpoint IO、WS 连接与命令吞吐的端到端压测。

2. **call_out / ActionScheduler 归属未收敛（高）**
   dissent 5 指出 call_out 与 ConditionSystem / EventBus 边界需实现时明确。当前 `call_out` 被拆解为 `EffectComp.next_tick` + 各 System 自行过滤，无统一的 ActionScheduler 抽象；自递归 call_out、延迟触发与周期 condition 的语义四分尚未交叉验证。

3. **System 变更审计不完整（中-高）**
   dissent 7 关于 System.update 直接 mutation 缺少 Command 级审计轨迹的问题，`CombatSystem` 已有 ledger，`ConditionSystem` 已有 `ConditionTickResult`，但 `HealSystem` 直接修改 Vitals 未记录变更日志，`GovernanceSystem` 也未统一产出 effect 账本。全 System 审计一致性未落地。

4. **Layer3 沙箱缺失阻塞 UGC 开放（高）**
   ADR-0053 将 RestrictedPython 沙箱延后到 M2 之后，但 UGC 核心指标要求"开放 UGC 脚本前 per-CPK 资源配额必须就位"。沙箱设计、capability 映射、fuel/wall_time/memory/call_out 配额尚未开始，可能成为 M3 后第一波用户创作的阻塞点。

5. **System 注册顺序与隐式时序依赖（中）**
   `Engine` 按列表顺序调 System，但顺序由初始化代码决定，无显式 phase 或优先级。Combat、condition、heal、governance、storage 的时序交互（如同一 tick 内 combat damage 与 heal 的先后顺序）会改变运行结果，需文档化或机制化。
