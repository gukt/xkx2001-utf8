# 第四轮专家复审 · 游戏服务器架构师评审

评审重点：单机分层、1000+100 可行性、JSON 存档崩溃安全、存储策略、tick 预算、命令管线与 WS 服务器。

---

## 总体裁定

**verdict: solid**

阶段 1 单进程 asyncio 核心循环已跑通，tick 预算、JSON 存档崩溃安全、命令 8 段管线、WS 会话骨架均已有工程证据且当前实测达标；主要缺口是 100 并发命令路径尚未纳入 tick 预算实测、部分 System 仍为 ad-hoc 桥接、以及 UGC/WS 生产边界需继续收紧。

---

## 当前实现与侠客行核心系统的缺口

### 1. 单机分层与 ECS / System 注册表

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| 统一 tick 循环 `Engine` | implemented | low | `engine/src/xkx/runtime/engine.py` | 已按 1s tick + compute<100ms 实现，per-System profiler 插桩就位 |
| System 注册表与鸭子类型接入 | partial | medium | `engine/src/xkx/runtime/engine.py` `SystemLike` / `systems.py` `System` 基类仍为 `NotImplementedError` | `System` 基类应尽快提供默认 `update` 骨架或统一 Effect 账本接口，避免新 System 复制 ad-hoc 桥接模式 |
| ECS SparseSet 存储 | implemented | low | `engine/src/xkx/runtime/ecs.py` | 1000 实体查询性能已验证，Archetype 后置策略合理 |
| SchemaRegistry 类型校验 | partial | medium | `engine/src/xkx/runtime/schema.py` / `world.py` | 生产路径已启用，但测试 World 仍有 `schema=None` 路径，建议逐步收紧 |

`Engine.systems` 采用 `SystemLike` 协议（鸭子类型），`CombatSystem`/`ConnectionSystem` 不继承 `System` 基类，这符合“避免循环依赖/会话表非 ECS 组件”的局部理由，但也导致 `runtime/systems.py` 的 `System` 基类至今仍是 `raise NotImplementedError` 的 stub。从架构一致性看，`System` 应至少提供默认 `update` 契约与可选的 Effect 账本钩子，避免后续 System 继续以 ad-hoc 方式接入。

### 2. 1000+100 可行性与 tick 预算

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| 单 `resolve_attack` μs 基准 | implemented | low | `engine/tools/benchmark.py` / `tests/test_benchmark.py` | median 10-15μs，p99 <18μs，PYTHONHASHSEED 跨进程一致，GO |
| 1000 实体 tick 预算压测 | implemented | low | `engine/tools/load_test.py` / `tests/test_load_test.py` | tick p99 9.8ms（预算 100ms），判定 GO |
| 100 并发命令对 tick 的影响 | missing | **high** | `load_test.py` 只测 System tick，不注入命令执行 | 应尽快在 load_test 中加入并发命令 dispatch（如每 tick 100 条随机命令），确认命令处理是否挤压 tick 预算 |
| GC 与对象分配基准 | partial | medium | `benchmark.py` GC 数据 | gen0 0 次/20k 调用良好，但应增加 1000 实体长时间运行 GC 压力测试 |
| 非均匀 tick / 跳 tick 恢复 | partial | medium | `engine.py` `tick_interval=1.0` | 当前压测是连续调用 `tick()`，未模拟事件循环因负载导致的跳 tick；建议增加跳 tick 场景验证 ConditionSystem/Effect 对齐 |

实测数据（本轮在 WSL2 环境运行）：

- `just bench`：所有分支 median <16μs，p99 <18μs，PYTHONHASHSEED 一致，GO。
- `just loadtest --ticks 300`：tick p50 3.4ms / p99 9.8ms / max 10.8ms，远低于 100ms 预算，GO。

但是，`load_test.py` 中的“100 并发”只体现在 1000 个 `ConnectionSession` 存在内存中，并未在 tick 内实际执行 100 条命令。命令管线（8 段中间件 + 世界查询）是纯 CPU 热路径，100 并发命令的真实开销是当前数据未覆盖的。建议在 load_test 中增加命令注入阶段，并作为 kill criteria 3 完整判定的一部分。

### 3. JSON 存档崩溃安全与存储策略

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| 原子写（write-temp + os.replace） | implemented | low | `engine/src/xkx/runtime/storage.py` `JsonFileBackend._write_entity_atomic` / `tests/test_storage.py` | 崩溃测试覆盖 tmp 损坏不污染 target |
| offload 到线程不阻塞 tick | implemented | low | `storage.py` `_async_persist` + `asyncio.to_thread` / `test_storage.py` | tick p99 不受 persist 耗时影响（全量 persist 1.4s 在后台） |
| dirty-flag 分摊 | implemented | low | `storage.py` `_dirty` set / `tests/test_storage.py` | 只写脏实体；checkpoint 周期重置 |
| Effect 崩溃恢复 | implemented | low | `storage.py` `restore_world` / `serialization.py` / `tests/test_storage.py` | duration/next_tick 恢复、悬空引用跳过、不补执行 |
| 持久化边界抽象 `StorageBackend` | implemented | low | `storage.py` `StorageBackend` ABC | 为迁 PG 留了策略接口 |
| 丢失语义台账与 kill criteria 8 | implemented | low | `ADR-0022` §5 / `04 §四` kill criteria 8 | 已明确外部玩家测试前必须迁 PG |
| PG 后端实现 | missing | low | 无 `PostgresBackend` | 按 kill criteria 8 触发条件实施即可，当前无需提前 |
| 存档 schema 版本迁移 | missing | medium | `serialization.py` `SAVE_VERSION = 1` | 预留 version 字段，但无迁移代码；M3 前应补最小版本兼容层 |
| 多实体事务原子性 | missing | **high** | `ADR-0022` §5 台账 #1 | JSON 跨文件无事务，崩溃可能部分实体新、部分旧；迁 PG 前应在文档中明确这是已知限制 |

JSON 存档三要素（原子写、offload、dirty-flag）均已落地并有测试背书，`StorageBackend` 的“持久化边界”抽象也正确区分了“崩溃恢复级耐久”与“save=权威写”。当前最大风险不是实现缺失，而是**多实体跨文件无事务原子性**：一次 checkpoint 涉及大量 entity 文件，进程崩溃时可能部分文件已 replace、部分尚未写入，导致世界状态不一致。这在单进程阶段 1 可被接受（kill criteria 8 触发前无外部玩家），但必须在迁 PG 前完成台账 #1 的补齐。

### 4. 命令管线

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| 8 段中间件管线 | implemented | low | `engine/src/xkx/runtime/commands.py` `run_pipeline` / `tests/test_command_pipeline.py` | 段顺序、Abort 短路、行为等价测试覆盖 |
| 命令注册表 | implemented | low | `commands.py` `COMMAND_REGISTRY` | 30+ 命令已注册，适配器模式保留原函数签名 |
| 权限校验 fail-closed | partial | medium | `middleware/s2_permission.py` | 无 `PermissionService` 时测试路径默认放行，生产路径必须注入 |
| PrivilegedAction 边界 | partial | **high** | `engine/src/xkx/runtime/privileged.py` / `middleware/s7_execute_audit.py` | 需持续监控调用点是否 ROOT 门控 + 强制审计；NPC AI 落地后是关键侵蚀点 |
| 刷屏/天雷惩罚 | partial | medium | `middleware/s0_flood_check.py` | 仅 Abort 命令，扣气/精与天雷后置 |
| 方向快捷与全局别名 | implemented | low | `middleware/s1_alias.py` / `s4_direction.py` | 18 方向别名 + 方向快捷回退已覆盖 |
| 参数解析 tokenizer | implemented | low | `middleware/s5_parse_args.py` | 引号感知，但完整 LPC parse_command 后置 |
| previous_object / PronounContext | partial | medium | `middleware/s6_inject_context.py` / `engine/src/xkx/runtime/pronoun.py` | 三元组已就位，但 System tick 消息中的 viewer 回退需继续验证 |

命令管线是本轮最扎实的部分之一。8 段中间件结构清晰，测试覆盖行为等价与短路语义。需要关注的是 `permission_check` 在无 `PermissionService` 时“测试/开发期默认放行”，生产部署时容易因注入遗漏变成隐式放行。建议增加一个启动期检查：若 `Game` 处于生产模式（如 `debug=False`）且无 `PermissionService`，则拒绝启动。

### 5. WS 服务器与会话管理

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| WS 核心逻辑（可单元测试） | implemented | low | `engine/src/xkx/runtime/ws_server.py` `handle_frame` / `tests/test_workbench.py` | 网络层与核心逻辑分离 |
| 会话状态机 + 超时 | implemented | low | `engine/src/xkx/runtime/connection.py` | LOGIN/ACTIVE/NET_DEAD/CLOSED 四态 + 三类超时 |
| 断线重连 ring buffer | implemented | low | `connection.py` `replay_since` / `ws_server.py` `_handle_resume` | 100 条 / 30 秒默认值 |
| 1000 连接真实容量测试 | missing | **high** | 无专项 WS 压力测试 | 应补 1000 并发 WS 连接 + 登录 + 命令收发测试，验证 `websockets` 库在单进程下的 FD/内存/GC 表现 |
| 生产级 WS 网关特性 | missing | medium | 无 rate-limit、无连接数硬上限 | 单机 1000+100 目标下，需确认 ulimit、asyncio 默认策略是否足够 |

`WSServer` 的核心逻辑（`handle_frame`）与网络层（`serve`）已分离，便于单元测试。但当前**没有针对 1000 并发 WS 连接的专项测试**。`load_test.py` 只构造了内存中的 `ConnectionSession`，并未真的打开 1000 个 WebSocket 连接。`websockets` 库在单进程、1000 长连接下的 FD 消耗、内存占用、`asyncio` 事件循环调度延迟，都是需要实测才能确认的。建议在 kill criteria 3/5 的完整判定中加入 WS 层压测。

### 6. System 派生变更审计

| 项目 | 状态 | 风险 | 证据 | 建议 |
|------|------|------|------|------|
| Command 路径审计 | implemented | low | `middleware/s7_execute_audit.py` `AuditLog` | 内存 ring buffer，阶段 1 不持久化 |
| System 派生变更审计 | at_risk | **high** | `runtime/heal.py`、`conditions.py`、`death.py`、`governance.py` 直接 mutate 组件 | 除 combat 有副作用账本外，其他 System 变更缺少统一审计轨迹；建议为 `SystemContext` 增加轻量 mutation 钩子 |
| 审计持久化 | missing | medium | `AuditLog` 内存 buffer | 外部玩家测试前需持久化，与 PG 迁移同步 |

这是 dissent 7 的直接体现。`CombatBridge` 有 `CombatSystem.flatten_effects` 和 `pending_messages` 作为副作用账本，但 `HealSystem`、`ConditionSystem`、`GovernanceSystem` 等仍是直接 mutate 组件。当前 `SystemContext` 存在但较薄，建议在 `System.update` 与组件 mutation 之间增加可选的 mutation 钩子（或要求 System 通过 `world.apply_mutation(eid, delta)`），使非 combat System 也能留下可审计、可回放的变更轨迹。

---

## UGC 核心指标/系统分层建议

以下基于 `context_ugc.md` 的基线，结合游戏服务器架构视角补充说明。

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|-------------|-----------|------|----------------|
| heart_beat tick 周期（1s，compute<100ms） | framework | 引擎核心调度不变量，所有题材共享 | 强主题无关，不允许题材包覆盖 |
| ECS 组件生命周期 | framework | 核心运行时基础设施 | 强主题无关 |
| Command 8 段管线 | framework | 外部意图抽象；具体命令实现可下沉题材包 | 强主题无关；动词注册表由题材包扩展 |
| `do_attack` 七步管线 | framework | CombatKernel 抽象 | 强主题无关；招式数据走 SkillData |
| PronounContext | framework | 文本渲染核心 | 强主题无关 |
| JSON 存档原子写 / dirty-flag | framework | 持久化边界抽象 | 强主题无关 |
| StorageBackend 策略切换 | framework | 崩溃恢复级耐久接口 | 强主题无关 |
| 层1 规则求值器 | framework | 唯一规则表示层 | 主题无关；谓词/动词词汇表由题材包注册 |
| ThemeRegistry 静态加载 | framework | 启动时注册表机制 | 强主题无关 |
| CPK 加载器与四道校验 | framework | DSL 编译与依赖校验基础设施 | 强主题无关 |
| RestrictedPython 沙箱 | framework | UGC 脚本执行环境 | 强主题无关；capability 由题材包声明 |
| 自动化预检（暴力/赌博/版权/license） | framework | 内容审核基础设施 | 强主题无关；词表可配置 |
| 专家审核 checklist 模板 | framework | 六维矩阵与人工 review 框架 | 强主题无关 |
| WS 服务器 / 会话管理 / 断线重连 | framework | 平台级网络基础设施 | 强主题无关 |
| tick profiler / 负载测试框架 | framework | 性能基准基础设施 | 强主题无关 |
| 武侠门派加成 / race_profile / class 称号 | official_cpk | `wuxia` 题材包 StdLib 资产 | 主题相关；必须走 ThemeRegistry 注入 |
| 武侠技能招式表 SkillData | official_cpk | `wuxia` 题材包 CPK 资产 | 主题相关；不进 combat 内核 |
| 门派任务链数据 | official_cpk / user_cpk | M3 官方，后期可 UGC | 主题相关 |
| 原创第三方门派/区域 CPK | user_cpk | UGC 创作者产出 | 主题相关；受沙箱与审核约束 |
| 玩家自建房间/NPC 事件规则 | user_cpk | UGC layer0/1 资产 | 主题相关；受 ThemeRegistry 词汇表限制 |
| 市场分发 / 版权 provenance | framework | 平台级能力，字段 Day1 预留 | 强主题无关；M3 不做功能 |
| Langfuse / 修订量追踪 | framework | M2 创作闭环度量基础设施 | 强主题无关；当前按 ADR-0053 后置 |

**架构师补充观点**：

1. **性能与 UGC 的交叉点**：CPK 加载器（framework）必须保证在 1000+100 场景下，CPK 编译与热更新不阻塞 tick。当前 `dsl/layer0.py`/`layer1.py` 是静态加载，UGC 运行时加载能力尚未实现，建议 M3 前明确 CPK 加载是否允许运行时增量注册。
2. **沙箱资源配额**：RestrictedPython 沙箱（framework）的 `resource_quota`（fuel/wall_time/memory/call_out）必须在开放 UGC 脚本前就位。当前 layer3 沙箱尚未实现，这是 UGC 安全硬门禁。
3. **审核 pipeline 与 tick 无关**：自动化预检（framework）应在 CPK 加载/发布前离线完成，不应进入 tick 热路径。

---

## 其他全局关注点

### 1. 命令执行与 tick 的耦合
当前 `dispatch` 是同步调用，命令执行结果直接返回给 WS。这在单玩家 CLI demo 中工作良好，但 100 并发命令同时进入事件循环时，每条命令的 8 段管线 + 世界查询 + 可能的战斗推进都会占用事件循环时间。如果命令处理未与 tick 解耦，可能出现“命令风暴”导致 tick 延迟。建议评估是否需要命令队列或限流（`s0_flood_check` 已有每 actor 限流，但全局并发命令数无上限）。

### 2. `CombatBridge` 的扩展性
`CombatBridge` 每 tick 遍历 `is_fighting=True` 的 combatant，按 `MAX_OPPONENT=4` 选 1 个对手。当前 50 战斗对下 p99 9.5ms；若战斗对增加到 200-500，或每个 combatant 有多个敌人，`input_log` 规模线性增长，可能逼近 100ms 预算。建议增加 combat 规模扩展性压测（200/500/1000 活跃战斗对）。

### 3. 持久化 fire-and-forget 的背压
`StorageSystem.update` 在 `persist_interval` 到达时触发 `_async_persist`，若上一个任务未完成则跳过。这在“tick 不阻塞”上是正确的，但意味着高 dirty 率下可能连续跳过多个 persist 周期，导致崩溃丢失窗口超过 30s。建议在 tick profiler 中增加“persist 跳过次数”指标，并设定连续跳过 N 次后的告警/降级策略。

### 4. 测试覆盖的完整性
- `tests/test_load_test.py` 用 30 tick 快速跑，阈值 100ms，主要验证“不退化”。完整 300 tick 由本地 `tools/load_test.py` 执行，但未纳入 CI。
- `tests/test_storage.py` 已覆盖原子写、offload、dirty-flag、Effect 恢复，但缺少“高 dirty 率下 persist 跳过”的测试。
- 缺少 1000 真实 WS 连接压测。

### 5. 与 LPC 规格的差距
从 `context_original_A.md`/`context_original_B.md` 看，大量 LPC 子系统仍为 `partial` 或 `missing`：CHANNEL_D、NATURE_D、MONEY_D、组队、婚姻、InterMUD、坐骑、武林大会、完整 NPC AI 等。这些大部分已被 04 的“不做”清单或后置阶段明确砍掉，符合当前阶段范围。但**死亡与轮回系统**（`runtime/death.py` + `governance.py`）已部分实现，阴间地图/黑白无常/鬼魂视觉隔离仍需 M3 后补齐。

---

## Top 3-5 风险

1. **100 并发命令未纳入 tick 预算实测（high）**
   - 当前 `load_test.py` 只测量 System tick，不执行真实命令。100 并发命令路径（8 段管线 + 世界查询）是单进程 asyncio 的潜在瓶颈，可能使实际 tick 延迟远超 9.8ms。
   - 建议：在 `tools/load_test.py` 中增加并发命令注入阶段，作为 kill criteria 3 完整判定的必选项。

2. **System 派生变更审计覆盖缺口（high）**
   - 除 combat 外，heal/condition/death/governance 等 System 直接 mutate 组件，缺少统一审计轨迹。未来反作弊、bug 追溯、数据修复都会受限。
   - 建议：为 `SystemContext`/`World` 增加轻量 mutation 钩子，要求非 combat System 通过统一入口写变更。

3. **1000 真实 WS 连接容量未验证（high）**
   - 内存中的 1000 会话不等于真实 1000 WebSocket 长连接。`websockets` 库、asyncio 事件循环、FD 限制、GC 在真实高连接下的表现未知。
   - 建议：补做 1000 并发 WS 连接 + 登录 + 命令收发压测，确认单进程承载边界。

4. **多实体 JSON 存档无事务原子性（medium）**
   - checkpoint 跨多个 entity 文件，崩溃可能导致世界状态部分新、部分旧。虽然单进程阶段 1 可接受，且 kill criteria 8 触发前无外部玩家，但应在文档中显式标注。
   - 建议：在 `ADR-0022` 台账 #1 中增加“阶段 1 已知限制”段落，并在迁 PG 时作为首要补齐项。

5. **`System` 基类仍为 stub 导致 ad-hoc 桥接模式蔓延（medium）**
   - `runtime/systems.py` 的 `System` 未提供默认实现，新 System 容易复制 `CombatBridge` 的自定义桥接逻辑。
   - 建议：在 `System` 基类中提供 `update(world, tick)` 默认骨架（如读快照 -> 求变更 -> apply_effects/mark_dirty），统一后续 System 接入模式。

---

评审人：游戏服务器架构师
评审日期：2026-07-15
