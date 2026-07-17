# Done 归档 - 阶段 1（核心循环 Wave 1-4, T1-T10）

> 从 PROGRESS.md 归档于 2026-07-14。阶段 1 已完成条目的历史记录，按需检索。
> 当前活状态见 [PROGRESS.md](../../PROGRESS.md)。

## Done

- [x] **分支合并 + 阶段 1 实施计划产出**（[12-阶段1-核心循环实施计划.md](docs/xkx-arch/12-阶段1-核心循环实施计划.md)）：
  - feat/s5-playtest 合并到 master（`--no-ff` merge commit `1419d120`，118 files +28882 lines），push origin master；从 master 开新分支 `feat/stage-1-core-loop`（feat/s5-playtest 保留作阶段 -1~0 历史标记）
  - 阶段 1 实施计划文档：10 个里程碑（M1-1~M1-10，对应 04 §三）分解为 T1-T10 任务 + 依赖图 + 4 个 Wave（Wave 1 串行 T1-T3 基础层 / Wave 2 并行 T4-T6 / Wave 3 并行 T7-T9 / Wave 4 串行 T10 门禁）+ 8 个待写 ADR（ADR-0017~0024，关联 05 §五 dissent）+ 05 §五 10 条 dissent 全映射到任务 + kill criteria 3/6/8 触发条件 + 性能优化备选 6 步
  - 现状盘点：阶段 -1/0 产出 16979 行可复用（combat/dsl/runtime/spec 四模块 + 680 tests），阶段 1 是"从 stub 到真实引擎"跃迁而非从零开始
  - 启动前置：ADR-0017/0018（Wave 1 前置）+ 用户确认启动编码

- [x] **阶段 1 Wave 1 T1：ECS 骨架升级完成**（[ADR-0017](docs/adr/ADR-0017-ecs-sparse-set-effect-component.md) + [ADR-0018](docs/adr/ADR-0018-conditionhandler-on-tick-contract.md)）：
  - ADR-0017 SparseSet 选型 + Effect 一等公民：SparseSet（非 Archetype，1000 实体规模足够，dict -> SparseSet 平滑升级 API 兼容）；Effect 一等公民（即时 Effect combat-only + 持续 Effect EffectComp，可序列化/可中断/可崩溃恢复 04 §三硬约束）
  - ADR-0018 ConditionHandler.on_tick 契约：ConditionTickResult（effects/messages/condition_deltas/completed/flags/ledger 交织）；on_tick 纯函数不 mutate；非均匀 tick（对齐 LPC 5+random(10)）；dissent 7 派生变更审计轨迹
  - T1 实现：SparseSet 升级 [ecs.py](engine/src/xkx/runtime/ecs.py)（swap-remove + 交集查询）+ Progression 组件（combat_exp/potential/max_potential 从 Vitals 迁移，[components.py](engine/src/xkx/runtime/components.py) + [world.py](engine/src/xkx/runtime/world.py) + [commands.py](engine/src/xkx/runtime/commands.py) + 4 tests 调整）+ EffectComp 组件（持续 Effect，独立实体 attach 支持多 condition）+ [systems.py](engine/src/xkx/runtime/systems.py) System 基类 + [conditions.py](engine/src/xkx/runtime/conditions.py) ConditionHandler/ConditionSystem
  - 测试：[test_ecs.py](engine/tests/test_ecs.py) 7 tests（SparseSet swap-remove/覆盖/交集 + hypothesis 属性测试）+ [test_conditions.py](engine/tests/test_conditions.py) 14 tests（on_tick 纯函数/衰减/completed/flags/多 condition/非均匀 tick）
  - **701 tests 全绿（+21），ruff 全过**

- [x] **阶段 1 Wave 1 T2：SchemaRegistry 类型化组件完成**（[ADR-0019](docs/adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)）：
  - ADR-0019 SchemaRegistry 与 DSL SchemaValidator 边界：runtime 组件层（启动期/运行期，类型注册+字段名存在性）vs DSL IR 层（创作期/加载期，结构+语义+引用）；dissent 3 护栏--SchemaRegistry 只做拼写检查不做语义校验（名字存在性 ≠ 值合法性），语义留给 DSL SchemaValidator + System 不变量
  - T2 实现：[schema.py](engine/src/xkx/runtime/schema.py) SchemaRegistry（register/resolve/resolve_name/has_field/field_names，从 dataclasses.fields 自动提取字段集，with_builtins 注册 13 内置组件）+ [ecs.py](engine/src/xkx/runtime/ecs.py) World 可选注入 schema（schema=None 向后兼容测试；有 schema 时 get/add/has/remove/entities_with 调 resolve，未注册类型 raise SchemaError 非静默 None）+ [world.py](engine/src/xkx/runtime/world.py) build_world 用 World(SchemaRegistry.with_builtins()) 生产路径强制校验
  - 测试：[test_schema.py](engine/tests/test_schema.py) 17 tests（注册/解析/字段查询/重复注册幂等/类型名冲突/非 dataclass 拒绝/未注册 raise/with_builtins 全覆盖/World 校验集成/build_world 带 schema/hypothesis 字段集一致性）
  - **718 tests 全绿（+17），ruff 全过**

- [x] **阶段 1 Wave 1 T3：字段->组件映射表完成**（[13-dbase-key-map.md](docs/xkx-arch/13-dbase-key-map.md) / ADR-0019 覆盖）：
  - [dbase_map.py](engine/src/xkx/runtime/dbase_map.py)：DBASE_KEY_MAP（37 已映射简单 key -> 13 组件字段，覆盖 Identity/Attributes/Vitals/Progression/Skills/NpcBehavior/RoomComp）+ PATH_PREFIX_MAP（skill/xxx -> Skills.levels，marks/xxx -> Marks.flags，LPC dbase 路径访问语义）+ POSTPONED_KEYS（55 后置 key，分 5 类：战斗行为/角色长期/PK法院/频道消息/登录重连/对象房间扩展）+ validate_dbase_map（T2 has_field 启动期校验映射目标合法）+ resolve_dbase_key（简单 key + 路径前缀解析，未映射返回 None）
  - [world.py](engine/src/xkx/runtime/world.py)：build_world 调 validate_dbase_map，映射目标非法 raise SchemaError（T2-T3 衔接）
  - [13-dbase-key-map.md](docs/xkx-arch/13-dbase-key-map.md)：完整 key 枚举文档（spec 82 key 全归类：37 已映射 + 2 路径前缀 + 55 后置 + 动态拼接 eff_/max_ type 维度）
  - 测试：[test_dbase_map.py](engine/tests/test_dbase_map.py) 9 tests（validate 正常+空 schema 全报/resolve 简单+路径+未映射/POSTPONED 不污染已映射/hypothesis 映射目标合法）
  - **727 tests 全绿（+9），ruff 全过**
  - **Wave 1 全部完成（T1+T2+T3）**

- [x] **阶段 1 Wave 2 前置 ADR 全部产出**（[ADR-0020](docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) / [ADR-0021](docs/adr/ADR-0021-previous-object-explicit-mapping.md) / [ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) / [ADR-0023](docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md)）：
  - ADR-0020 命令 8 段中间件管线（对照 LPC command_hook 四分支 + process_input）+ ActionContext 三元组（actor/viewer/target，PronounContext viewer 不变量）+ CapabilityToken（HS256 + 内存吊销）+ force_me=PrivilegedAction（ROOT 门控 + 强制审计 + 调用点白名单）；关联 dissent 6
  - ADR-0021 previous_object 155 处显式化映射表（this_player()->actor / previous_object()->source）+ A/B/C 三类处置 + 调用点审计策略（source 显式传参 + 白名单 + ROOT 签发审计 + 两类审计分离）；关联 dissent 6
  - ADR-0022 持久化边界抽象（persist=崩溃恢复级耐久，非 save=权威写，为迁 PG 留策略切换）+ 原子写三步（write-temp + fsync + os.replace）+ 事件循环外 offload + dirty-flag 分摊 + 丢失语义台账 5 项（kill criteria 8 止损线）+ Effect 崩溃恢复 + 冷重启协议；关联 dissent 8
  - ADR-0023 combat-only 确定性边界（范围内/范围外 + 边界红线）+ CombatSystem（tick 驱动 + 快照边界 + input log + replay 入口 + 不套 Command）+ 简化台账 6 项补全（hit_ob/hit_by mapping / riposte 递归 / 武器类型 / skill_power / combat_exp 防御折减 / 技能 action）+ test_theme_neutrality 硬门禁兜底；关联 dissent 1
  - agent teams 3 路并行写 ADR（T4 一个 agent 写 0020+0021 / T5 一个写 0022 / T6 一个写 0023），审查收敛后修复 1 处交叉引用链接
  - **727 tests 全绿（无回归），ruff 全过**

- [x] **阶段 1 Wave 2 T4 命令 8 段管线 + ActionContext + CapabilityToken 完成**（[ADR-0020](docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md) + [ADR-0021](docs/adr/ADR-0021-previous-object-explicit-mapping.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T4）：
  - 8 段中间件管线（[middleware/](engine/src/xkx/runtime/middleware/) 8 文件：s0 刷屏检测 / s1 别名 / s2 权限 / s3 命令查找 / s4 方向快捷 / s5 参数解析 / s6 previous_object 注入 / s7 执行+审计），对照 LPC command_hook 四分支 + process_input
  - [ActionContext](engine/src/xkx/runtime/action_context.py) frozen dataclass 三元组（actor/source/viewer/target + capability_token + seq + result/effects），PronounContext viewer 不变量
  - [CapabilityToken](engine/src/xkx/runtime/capability.py) HS256 签名 + 内存吊销集合 + 能力集映射 LPC 权限模型（exclude 优先 authorized）+ PermissionService 签发/验签/吊销
  - [PrivilegedAction](engine/src/xkx/runtime/privileged.py) force_me=PrivilegedAction（ROOT 门控 + 强制审计 + 调用点白名单 4 处 + 走完整 8 段管线 + NPC AI 禁用）
  - [previous_object_map.py](engine/src/xkx/runtime/previous_object_map.py) PREVIOUS_OBJECT_MAP（A/B/C 三类 11 条典型调用点）+ 启动期 MappingError 校验；[pronoun.py](engine/src/xkx/runtime/pronoun.py) PronounService（viewer/target 显式传参）；[system_context.py](engine/src/xkx/runtime/system_context.py) SystemContext（System.update 路径轻量）
  - [commands.py](engine/src/xkx/runtime/commands.py) 重构接入管线（COMMAND_REGISTRY + run_pipeline + dispatch），10 命令行为等价
  - 测试：[test_command_pipeline.py](engine/tests/test_command_pipeline.py) 26 + [test_capability_token.py](engine/tests/test_capability_token.py) 20 + [test_privileged_action.py](engine/tests/test_privileged_action.py) 13 + [test_previous_object_map.py](engine/tests/test_previous_object_map.py) 21
  - **80 新测试全绿，61 e2e 不回归，ruff 全过**；关联 dissent 6

- [x] **阶段 1 Wave 2 T5 内存权威 + JSON 存档完成**（[ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T5）：
  - [storage.py](engine/src/xkx/runtime/storage.py) StorageBackend 抽象基类（persist=崩溃恢复级耐久，非 save=权威写）+ JsonFileBackend（原子写 write-temp+fsync+os.replace + offload asyncio.to_thread + per-entity dirty-flag）+ StorageSystem（tick 驱动周期 persist + mark_dirty + 全量 checkpoint 周期重置 + persist_now + restore_world 冷重启协议）
  - [serialization.py](engine/src/xkx/runtime/serialization.py) 组件 dataclass <-> JSON 序列化（dataclasses.fields 提取 + SchemaRegistry 字段名衔接 + set 字段 sorted list 往返 + 多余/缺失字段容忍）
  - [world.py](engine/src/xkx/runtime/world.py) 最小接入 StorageSystem（build_world 加可选 storage_backend 参数，world.storage_system 动态属性，零破坏现有调用）
  - Effect 崩溃恢复：duration 不衰减（时间冻结）+ next_tick 对齐 current_tick+tick_interval（不补执行）+ 悬空 target_id 跳过 + 悬空 source_id 保留
  - 丢失语义台账 5 项（ADR §5 已记录，PG 后置 kill criteria 8）
  - 测试：[test_storage.py](engine/tests/test_storage.py) 25 tests（原子写崩溃 + offload 不阻塞 + dirty-flag + 冷重启 + Effect 崩溃恢复 + hypothesis 序列化往返 6 property）
  - **25 新测试全绿，ruff 全过**；关联 dissent 8

- [x] **阶段 1 Wave 2 T6 combat 确定性扩展 + 简化台账 6 项补全完成**（[ADR-0023](docs/adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T6）：
  - 6 项简化台账补全（[resolve_attack.py](engine/src/xkx/combat/resolve_attack.py)）：
    1. hit_ob/hit_by mapping 分支：[HitCallbackResult](engine/src/xkx/combat/context.py) 声明式载体（message/damage_delta/override，主题无关 + 可序列化），内核只做返回类型分发，按规格 order=23/25/26/32/33 交织入 ledger
    2. riposte 递归：TYPE_REGULAR + damage<1 + victim guarding 时递归调 resolve_attack，子回合经 [embed_subresult](engine/src/xkx/combat/result.py) 嵌入父回合 ledger（LEDGER_SUBRESULT，非独立账本），_RIPOSTE_MAX_DEPTH=4 防死循环
    3. 武器类型：不在内核枚举（test_theme_neutrality 源码无 sword/blade 硬门禁持续通过），attack_skill/weapon_label 由题材数据声明
    4. skill_power 完整公式：level³/3 + jingli_bonus(上限 150) + str/dex 加成 + is_fighting DEFENSE 折减 + level<1 低技能经验补偿（LPC _skill_power invariants）
    5. combat_exp 防御折减：defense_factor 折半自然终止（while 循环，每次 rng.rand），替代 S1 的固定 5 次上限
    6. 技能 action：[SkillData](engine/src/xkx/combat/context.py) 载体（action/dodge/parry/damage/force/damage_type/post_action），快照从 SkillData 取值，post_action 声明式副作用入 ledger（order=47）
  - CombatSystem（[system.py](engine/src/xkx/combat/system.py) 新建）：tick 驱动 + 快照构建 + input log 记录 + apply_effects + replay 入口 + flatten_messages/effects（展开 riposte 子回合）+ 不套 Command。独立实现（不继承 runtime.System，避免 combat->runtime 依赖），不接入 world.py System 注册（后续整合）
  - replay 纯函数（[replay.py](engine/src/xkx/combat/replay.py) 新建）：replay(snapshot, seed, input_log) -> list[CombatRoundResult]，同 snapshot+seed+input_log -> 同输出（combat-only 确定性，不依赖运行时 ECS）
  - impl_map 升级（[impl_map.py](engine/src/xkx/spec/impl_map.py)）：three_layer_resource_invariant / interleaving_order 状态 simplified -> implemented（14 implemented + 0 simplified）
  - DeterministicRNG 加 derive_seed（riposte 子回合 seed 派生，确定性）
  - 测试：[test_simplification_ledger.py](engine/tests/test_simplification_ledger.py) 20 tests（6 项补全回归 + 主题无关性断言）+ [test_combat_system.py](engine/tests/test_combat_system.py) 13 tests（tick 驱动 + 确定性重放 + apply_effects 三层不变量 + flatten 子回合展开）
  - test_conformance.py 最小适配 2 处：test_ap_dp_pp_lower_bound（完整公式 level<1 边界行为，skill_power>=0 + resolve_attack max(1,ap) 修正）+ test_implemented_count（14/0）
  - **840 tests 全绿（+33），ruff 全过**；test_theme_neutrality 5 断言全绿（硬门禁不回归）；ConformanceChecker 8 项全通过（riposte 场景验证）

- [x] **阶段 1 Wave 3 T7 单进程 WS 服务器 + 认证 + 重连完成**（[ADR-0024](docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T7）：
  - [account.py](engine/src/xkx/runtime/account.py) AccountService（argon2id 密码哈希替换 LPC crypt + check_legal_id/name + random_gift 天赋生成不变量 str+int+con+dex+end=100 + JSON 存储账号）
  - [login.py](engine/src/xkx/runtime/login.py) LoginMachine 状态机（WS 登录子协议驱动；老玩家 GET_ID->GET_PASSWD->DONE + 新玩家注册流程；阶段 1 简化跳过 CONFIRM_BIG5/wiz_lock/GET_GIFT/GET_EMAIL）
  - [connection.py](engine/src/xkx/runtime/connection.py) ConnectionSystem（ADR-0014 第 6 个 System；tick 驱动会话超时 LOGIN/NET_DEAD/IDLE + ring buffer 重连 ring/snapshot 降级 + 进程内内存非持久化 dissent 8 取舍）
  - [ws_server.py](engine/src/xkx/runtime/ws_server.py) WSServer（JSON 帧编解码 7 类帧 + 登录子协议 + command->dispatch 8 段管线 + resume 重连 + 事件推送；session token 复用 T4 CapabilityToken HS256；核心逻辑不依赖网络库可单元测试 + serve 方法用 websockets 库）
  - 依赖：argon2-cffi + websockets 加 pyproject.toml；测试 28+14+23+16
  - **81 新测试全绿，ruff 全过**；关联 dissent 8

- [x] **阶段 1 Wave 3 T8 引擎工具链三件完成**（[ADR-0013](docs/adr/ADR-0013-engine-toolchain-prd.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T8）：
  - [inspector.py](engine/src/xkx/runtime/inspector.py) EntityInspector（只读快照 + LPC F_DBASE 语义映射表 43 key 含 skill//marks/ 路径访问 + 程序化 API 6 方法 + CLI inspect --map；只读不修改 world）
  - [profiler.py](engine/src/xkx/runtime/profiler.py) TickProfiler（per-System compute 统计 mean/p99/max/total/%tick + enabled=False 零开销 contextmanager + ring buffer 滑动窗口 + CLI profile tick + --json）
  - [tools/replay.py](engine/src/xkx/tools/replay.py) Combat Replay Viewer（CombatLog JSON 归档 M1 前身 + 逐回合回放 + 交织时序展示 + ConformanceChecker 集成 + 确定性 diff 定位首次分歧 + CLI replay --step/--round/--diff/--conformance/--json；非侵入消费 ledger 仅依赖 xkx.combat）
  - 测试 [test_inspector.py](engine/tests/test_inspector.py) + [test_profiler.py](engine/tests/test_profiler.py) + [test_replay_viewer.py](engine/tests/test_replay_viewer.py)
  - **57 新测试全绿，ruff 全过**；关联 dissent 3/4/7

- [x] **阶段 1 Wave 3 T9 combat-sim 行为等价验证完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md) / [12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T9）：
  - [combat_sim.py](engine/src/xkx/combat/combat_sim.py) run_combat_sim（replay + ConformanceChecker 8 项检查 + CombatSimReport/RoundReport + JSON 序列化 + CLI python -m xkx.combat.combat_sim）
  - [replay.py](engine/src/xkx/combat/replay.py) 扩展 replay_with_context（返回 ctx+result 对供符合性检查用 ctx；replay 接口不变向后兼容）
  - 测试 [test_combat_sim.py](engine/tests/test_combat_sim.py) 端到端无 violation + 确定性 + JSON 往返 + CLI
  - **16 新测试全绿，ruff 全过**；greenfield 主门禁（不依赖运行 LPC）；impl_map 14 implemented + 0 simplified 自动区分

- [x] **阶段 1 Wave 4 T10 1000+100 集成测试完成（kill criteria 3 完整判定 GO）**（[12](docs/xkx-arch/12-阶段1-核心循环实施计划.md) T10 / [14 压测报告](docs/xkx-arch/14-T10-压测报告.md)）：
  - 整合遗留收纳：[engine.py](engine/src/xkx/runtime/engine.py) Engine 统一 tick 循环（System 注册 + TickProfiler 集成）+ CombatBridge 适配器（CombatSystem 接入，按 enemy_ids 构建 input_log O(活跃对) 非 O(n²)）+ CombatState 扩展 guarding/is_fighting/fight_dodge + to_snapshot 传递 + mark_dirty 整合（CombatBridge/ConditionSystem mutation 后标记）
  - [load_test.py](engine/tools/load_test.py) 压测脚本：1300 实体（50 房间 + 200 NPC + 1000 玩家 + 50 Effect）+ 1000 会话 + 50 战斗对 + 300 tick；async 模式 StorageSystem offload 生效
  - **tick p99 12.6ms < 100ms 预算 -> GO**；CombatSystem 5.3ms mean（占 92%），ConditionSystem 238μs，ConnectionSystem 236μs（1000 会话线性扩展），StorageSystem 6μs（persist tick 深拷贝 1.8ms）
  - 存档 offload 验证：全量 persist p99 389.8ms 在后台（asyncio.to_thread），tick p99 不含 persist（[ADR-0022](docs/adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) §3 生效）
  - 测试 [test_engine.py](engine/tests/test_engine.py) 12（Engine tick 循环 + CombatBridge + CombatState 扩展 + 完整整合）+ [test_load_test.py](engine/tests/test_load_test.py) 4（CI 回归门禁 tick p99 < 100ms + JSON 往返 + scaled 降级）
  - **kill criteria 3 完整判定通过**，不触发 kill criteria 6/降级；阶段 1 -> 2 决策检查点全部通过
  - **1035 tests 全绿（+16），ruff 全过**

