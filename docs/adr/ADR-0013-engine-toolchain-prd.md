# ADR-0013：引擎工具链 PRD（最小三件）

> 阶段 0 任务 5 产出。定义引擎工具链最小三件（Entity Inspector / Tick Profiler / Combat Replay Viewer）的 PRD，满足阶段 0 -> 1 决策检查点"引擎工具链 PRD 评审通过"。
>
> 创建：2026-07-11
> 关联：[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 不做清单（6 件砍为 3 件）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3/4/7 / [ADR-0011](ADR-0011-spec-conformance-checker.md) CombatRoundResult ledger / [ADR-0012](ADR-0012-performance-microbenchmark.md) 性能基准

## 背景

04 §六不做清单将原 6 件工具链砍为最小三件（理由"单机+1000 在线下过重"）：
- Entity Inspector（实体检视器）
- Tick Profiler（tick 性能分析器）
- Combat Replay Viewer（战斗回放查看器）

阶段 1 验收要求"引擎工具链同步可用"（04 §三阶段 1）+ 范围检查点 10"每阶段 tick profiler + combat replay viewer 验证无回归"。

阶段 0 -> 1 决策检查点要求"引擎工具链 PRD 评审通过"。

## 决策

三件工具的 PRD 已产出（3 个独立文档），统一**定位为阶段 1 开发期工具**（非"生产运维工具"），进程内模块，不引入分布式/K8s/Redis。

### PRD 文档

1. [10-引擎工具链PRD-entity-inspector.md](../xkx-arch/10-引擎工具链PRD-entity-inspector.md)
2. [10-引擎工具链PRD-tick-profiler.md](../xkx-arch/10-引擎工具链PRD-tick-profiler.md)
3. [10-引擎工具链PRD-combat-replay-viewer.md](../xkx-arch/10-引擎工具链PRD-combat-replay-viewer.md)

### 三件工具定位

| 工具 | 定位 | 核心数据源 | 阶段 1 最小范围 |
|---|---|---|---|
| Entity Inspector | 开发期只读调试 | ECS 实体 + 组件 | 查询 + 组件检视 + CLI + LPC F_DBASE 语义映射 |
| Tick Profiler | 阶段 1 性能门禁 | System.update 耗时 | per-System 统计 + CLI 报告 + 开关 |
| Combat Replay Viewer | combat 确定性验证 + M1 前身 | CombatRoundResult ledger | 逐回合回放 + 确定性 diff + ConformanceChecker 集成 |

### 关键设计点

**Entity Inspector**：
- 只读快照（阶段 1 严格只读，修改后置），< 0.1ms/查询
- LPC F_DBASE 语义映射表：`query("skill/axe")` -> `Skills.levels["axe"]`，`query_temp("marks/酥")` -> `Marks.flags`，覆盖 dbase/temp 两类作用域
- 程序化 API 供 Tick Profiler / Replay Viewer 调用

**Tick Profiler**：
- per-System compute 统计（mean/p99/max），性能开销 < 1ms/tick（< 1% tick 预算）
- `enabled=False` 零开销 contextmanager + `__slots__` 采样对象 + ring buffer 滑动窗口
- 与 [ADR-0012](ADR-0012-performance-microbenchmark.md) benchmark 分工：benchmark 是 μs 级微基准（单 resolve_attack 25.9μs），profiler 是 tick 级宏观（1s tick 内多 System 聚合），两者互补构成 kill criteria 3 完整 go/no-go 判定

**Combat Replay Viewer**：
- 非侵入消费 resolve_attack 的 ledger（不修改 combat 内核）
- 可离线回放（脱离引擎运行，仅依赖 `xkx.combat` 模块）
- 确定性 diff：同 seed 同 input -> 同输出，diff 两次回放定位首次分歧回合
- 与 [ADR-0011](ADR-0011-spec-conformance-checker.md) ConformanceChecker 联动（回放时自动跑 8 项检查）
- 战报归档格式（CombatLog JSON = context + input_log + output_frames）直接衔接 M1 开源交付物，阶段 1 实现即为 M1 开源仓库核心组件前身

## 关联 dissent

- **dissent 3（性能基线）**：Tick Profiler 是阶段 1 "tick compute<100ms"的测量工具，提供宏观级数据；ADR-0012 benchmark 已提供 μs 级前置数据点。两者互补回应"性能基线是否达标"的 go/no-go 判定。
- **dissent 4（规则冲突语义漂移）**：Combat Replay Viewer 的确定性 diff 能力可用于验证 valid_leave 命中行为（规则冲突）的回归，补充 golden trace（被 driver UE 状态阻塞）的辅助验证路径。
- **dissent 7（派生变更审计覆盖）**：Tick Profiler 的 per-System 统计可识别 heart_beat/chat 的派生变更开销（层 G 规格），补充派生变更审计的运行时覆盖。

## 不做（后置）

- Entity Inspector：实时修改 / 历史回溯 / 远程检视（WS）/ 与 tick profiler 联动 -> 后置
- Tick Profiler：per-entity / 火焰图 / 历史趋势 / Langfuse 对接 -> 后置
- Combat Replay Viewer：TUI 交互式回放 / Web 可视化 / 与 tick profiler 集成 -> 后置
- 原 6 件工具链的其余 3 件（04 §六不做清单已砍）-> 不做

## 验收

阶段 0 -> 1 决策检查点"引擎工具链 PRD 评审通过"满足：3 件工具 PRD 已产出，定位明确（阶段 1 开发期工具），最小实现范围收敛，与已有 ADR-0011/0012 衔接，关联 dissent 3/4/7。

阶段 1 实施时三件工具同步开发，范围检查点 10"tick profiler + combat replay viewer 验证无回归"在每阶段执行。
