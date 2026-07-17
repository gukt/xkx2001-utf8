# 引擎工具链 PRD：Tick Profiler

> 创建日期：2026-07-11
>
> 本文档是引擎工具链最小三件之一 Tick Profiler 的产品设计文档。关联 [04](04-迁移路径与避坑清单.md) §一原则 5 性能基准硬门禁 / §三阶段 1 tick 预算 / §五范围检查点 5+10 / §六不做清单（50ms/20Hz 砍、6 件工具链砍为 3 件、对象池后置），以及 [ADR-0012](../adr/ADR-0012-performance-microbenchmark.md) 性能 micro-benchmark 成果。

---

## 一、定位与目标

### 定位

Tick Profiler 是引擎 tick 循环的性能分析工具，测量 1s tick 内各 System 的 compute 时间，识别热路径，是 **"tick compute<100ms"和"1000+100 负载"的测量工具**，定位为 **"阶段 1 性能门禁工具"**。

### 目标

| 目标 | 对应验收标准 |
|---|---|
| 测量 per-System compute 时间 | [04](04-迁移路径与避坑清单.md) §三阶段 1：tick compute<100ms 非均匀 tick |
| 验证 tick 无回归 | [04](04-迁移路径与避坑清单.md) §五范围检查点 10：tick profiler 验证无回归 |
| 支持 1000+100 负载压测可观测 | [04](04-迁移路径与避坑清单.md) §五范围检查点 5：1000 在线+100 并发集成测试 |
| 为对象池决策提供数据 | [04](04-迁移路径与避坑清单.md) §六不做：对象池化用 tick profiler 实测后再决定 |

### 与 ADR-0012 benchmark 的分工

| 维度 | ADR-0012 micro-benchmark | Tick Profiler |
|---|---|---|
| 粒度 | 单函数 μs 级（resolve_attack 25.9μs） | tick 级宏观（1s tick 内多 System 聚合） |
| 场景 | 隔离纯函数，无框架依赖 | 真实 tick 循环，含 ECS 查询 + System 调度 |
| 时机 | 阶段 0 已完成 | 阶段 1 tick 框架就绪后 |
| 用途 | 单点不超标的必要条件 | tick 预算分配 + 热路径定位 + 回归监控 |

ADR-0012 benchmark 回答"单次 resolve_attack 是否够快"，Tick Profiler 回答"整个 tick 周期内各 System 的 compute 分配是否合理、是否 <100ms"。两者互补，共同构成 kill criteria 3 的完整 go/no-go 判定依据。

### 不做（收敛边界）

- 不做分布式 tracing（后置 OTel+Grafana，[04](04-迁移路径与避坑清单.md) §六不做）
- 不做 50ms/20Hz 框架适配（LPC heart_beat 实测 1s，[04](04-迁移路径与避坑清单.md) §六不做）
- 不做生产环境常驻采集（生产关闭，调试/压测开启）
- 不做火焰图 / 历史趋势（后置能力，见 §七）

---

## 二、核心功能

### 2.1 per-System compute 时间统计

按 System 聚合每个 tick 内的 compute 时间，输出统计摘要：

| 指标 | 说明 |
|---|---|
| mean | 平均 compute 时间（μs），反映常态开销 |
| p99 | 第 99 百分位（μs），反映尾延迟（GC 抖动 / 分配尖峰） |
| max | 最大 compute 时间（μs），反映最差 tick |
| total | 累计 compute 时间（μs），反映 tick 预算占比 |
| ticks | 采样 tick 数，反映统计置信度 |

示例输出：

```
System          mean(us)    p99(us)    max(us)    total(ms)  ticks  %tick
─────────────────────────────────────────────────────────────────────────
CombatSystem       820        1,450      2,100      41.0     500    41%
NPCAISystem        340          680      1,020      17.0     500    17%
ConditionSystem    180          320        480       9.0     500     9%
HealSystem         120          250        390       6.0     500     6%
TickDecaySystem     80          160        280       4.0     500     4%
─────────────────────────────────────────────────────────────────────────
Total                                                        77.0    77%
Budget                                                       100.0   100ms
```

### 2.2 per-entity tick 开销

识别高开销实体（如高负载 NPC、大量 Effect 堆积的战斗者），定位"哪个实体拖慢了哪个 System"。

| 维度 | 说明 |
|---|---|
| entity_id | 实体 ID |
| system_name | 该实体在哪个 System 被处理 |
| compute_us | 该实体的单次处理耗时（μs） |
| reason | 开销标注（如 "12 active effects" / "8 enemies" / "heavy chat evaluate"） |

CLI 输出示例（`profile tick --top 10`）：

```
Top 10 entities by tick compute (CombatSystem, last 500 ticks)
────────────────────────────────────────────────────────────────
Rank  entity_id  mean(us)  max(us)  reason
  1      #1042     185       420    12 active effects, 3 enemies
  2      #1087     160       380    8 active effects, 4 enemies
  3      #1033     145       350    10 active effects, 2 enemies
  ...
```

### 2.3 非均匀 tick 可视化

对照 LPC heart_beat 的非均匀 tick 机制（[层 G 规格](../engine/src/xkx/spec/layer_g_npc_ai.py) `tick = 5 + random(10)` 衰减周期），展示哪些实体在哪个 tick 激活、哪些被跳过。

| 维度 | 说明 |
|---|---|
| tick_id | tick 序号 |
| entity_id | 实体 ID |
| activated | 是否在本 tick 激活（True/False） |
| decay_remaining | 衰减剩余 tick 数（对应 LPC `tick--`） |
| system_name | 激活时执行的 System |

CLI 输出示例（`profile tick --non-uniform`）：

```
Non-uniform tick pattern (entity #1042, ticks 1-20)
──────────────────────────────────────────────────
Tick  activated  decay  systems
  1     Y         7     CombatSystem, NPCAISystem
  2     Y         6     CombatSystem, NPCAISystem
  3     Y         5     CombatSystem, NPCAISystem, ConditionSystem, HealSystem
  4     Y         4     CombatSystem, NPCAISystem
  5     Y         3     CombatSystem, NPCAISystem
  6     Y         2     CombatSystem, NPCAISystem
  7     Y         1     CombatSystem, NPCAISystem
  8     Y         0     CombatSystem, NPCAISystem, ConditionSystem, HealSystem
  9     Y         9     CombatSystem, NPCAISystem  (decay reset: 5+random(10)=9)
 ...
```

此功能验证引擎的非均匀 tick 实现是否与 LPC `set_heart_beat(1)` + `tick = 5 + random(10)` 语义一致：每 1s 执行 heart_beat，但 ConditionSystem/HealSystem 仅在 tick 衰减到 0 时执行。

### 2.4 热路径定位

System 内函数级耗时分解，识别 System 内部哪个环节是瓶颈。例如 CombatSystem 内 `resolve_attack` 占比、`select_opponent` 占比、`effect_apply` 占比。

| 维度 | 说明 |
|---|---|
| system_name | 所属 System |
| function_name | 函数名（如 `resolve_attack` / `select_opponent`） |
| compute_us | 函数级耗时（μs） |
| call_count | 调用次数 |
| %system | 占该 System compute 的百分比 |

CLI 输出示例（`profile tick --system combat --hotpath`）：

```
Hotpath analysis (CombatSystem, last 500 ticks)
────────────────────────────────────────────────────────────
Function              calls   mean(us)  total(ms)  %system
resolve_attack          1200      25.9     31.1       76%
select_opponent         1200       3.2      3.8        9%
clean_up_enemy          1200       2.1      2.5        6%
effect_apply            2400       1.5      3.6        9%
────────────────────────────────────────────────────────────
Total                                      41.0      100%
```

---

## 三、接口设计

### 3.1 CLI 命令

```
profile tick                          # 基础报告：per-System 统计摘要
profile tick --top 10                 # 高开销实体 Top 10
profile tick --system combat          # 聚焦特定 System
profile tick --system combat --hotpath  # System 内热路径分解
profile tick --non-uniform            # 非均匀 tick 可视化
profile tick --ticks 1000             # 采集 1000 tick 后报告（默认 500）
profile tick --json                   # JSON 输出（供脚本消费）
```

### 3.2 程序化 API

```python
# 采集器
class TickProfiler:
    """Tick 级性能采集器，通过 contextmanager 在 System.update 前后插桩。"""

    def __init__(self, *, enabled: bool = False, window: int = 500) -> None:
        """enabled=False 时为空操作，开销为零。window 指定滑动窗口大小。"""

    @contextmanager
    def measure_system(self, system_name: str) -> Iterator[None]:
        """System.update 前后插桩，记录 compute 时间。"""

    @contextmanager
    def measure_entity(self, system_name: str, entity_id: int) -> Iterator[None]:
        """per-entity 级插桩，记录单实体处理耗时。"""

    @contextmanager
    def measure_function(self, system_name: str, func_name: str) -> Iterator[None]:
        """函数级插桩，记录热路径函数耗时。"""

    def record_tick(self, tick_id: int, active_entities: set[int],
                    decay_map: dict[int, int]) -> None:
        """记录非均匀 tick 信息：哪些实体激活、衰减剩余。"""

    def report(self) -> TickReport:
        """生成报告对象。"""

    def reset(self) -> None:
        """清空滑动窗口，重新采集。"""

# 报告器
class TickReport:
    """Tick 性能报告，支持格式化输出。"""

    def system_summary(self) -> list[SystemStats]:
        """per-System 统计摘要。"""

    def top_entities(self, system_name: str, n: int = 10) -> list[EntityStats]:
        """高开销实体 Top N。"""

    def hotpath(self, system_name: str) -> list[FunctionStats]:
        """System 内热路径分解。"""

    def non_uniform_pattern(self, entity_id: int, ticks: int = 20) -> list[TickPattern]:
        """非均匀 tick 模式。"""

    def to_json(self) -> str:
        """JSON 序列化。"""

    def to_table(self) -> str:
        """CLI 表格格式。"""
```

---

## 四、数据模型

### 4.1 TickSample

```python
@dataclass(slots=True)
class TickSample:
    """单次 tick 内一个 System 的采样记录。"""
    tick_id: int               # tick 序号
    system_name: str           # System 名称
    entity_count: int          # 本 tick 处理的实体数
    compute_us: int            # 总 compute 时间（μs）
    samples: list[EntitySample]  # per-entity 子采样（可为空，采样模式下按比例采集）

@dataclass(slots=True)
class EntitySample:
    """单实体的处理采样。"""
    entity_id: int             # 实体 ID
    compute_us: int            # 该实体处理耗时（μs）
    reason: str                # 开销标注（可选）

@dataclass(slots=True)
class FunctionSample:
    """函数级采样。"""
    system_name: str           # 所属 System
    function_name: str         # 函数名
    compute_us: int            # 函数耗时（μs）
    tick_id: int               # 所属 tick

@dataclass(slots=True)
class TickPattern:
    """非均匀 tick 模式记录。"""
    tick_id: int               # tick 序号
    entity_id: int             # 实体 ID
    activated: bool            # 是否激活
    decay_remaining: int       # 衰减剩余（对应 LPC tick--）
    systems_executed: list[str]  # 激活时执行的 System 列表
```

### 4.2 聚合统计

```python
@dataclass(slots=True)
class SystemStats:
    """System 级聚合统计。"""
    system_name: str
    mean_us: float             # 平均 compute（μs）
    p99_us: float              # P99（μs）
    max_us: int                # 最大 compute（μs）
    total_us: int              # 累计 compute（μs）
    ticks: int                 # 采样 tick 数
    pct_tick: float            # 占 tick 预算的百分比（预算=100ms）

@dataclass(slots=True)
class EntityStats:
    """实体级聚合统计。"""
    entity_id: int
    system_name: str
    mean_us: float
    max_us: int
    reason: str
```

### 4.3 采集策略

| 策略 | 说明 | 开销 | 适用场景 |
|---|---|---|---|
| **全量采集** | 每 tick 每 System 每 entity 全量记录 | 较高（见 §五开销控制） | 压测 / 调试 |
| **采样采集** | 每 N tick 采样一次，per-entity 按 1/K 比例采样 | 低 | 长时间运行监控 |
| **关闭** | enabled=False，所有方法为空操作 | 零 | 生产环境 |

阶段 1 默认使用全量采集（压测场景），生产环境关闭。采样采集为后置能力。

---

## 五、与引擎集成点

### 5.1 System.update 前后插桩

Tick Profiler 通过 `contextmanager` 在 System.update 调用前后插桩，不侵入 System 代码：

```python
# 引擎 tick 循环中的集成方式（示意，非实现）
for system in systems:
    with profiler.measure_system(system.name):
        for entity in world.entities_with(*system.required_components):
            with profiler.measure_entity(system.name, entity):
                system.update(world, entity)
```

profiler 在 `enabled=False` 时，`measure_system` / `measure_entity` 为空 contextmanager（`contextlib.nullcontext`），无函数调用开销。

### 5.2 性能开销控制

**硬约束：profiler 自身开销 < 1% tick 预算，即 < 1ms/tick（100ms 预算的 1%）。**

| 措施 | 说明 |
|---|---|
| 时间测量用 `time.perf_counter_ns()` | 单调时钟纳秒精度，无系统调用开销 |
| `@dataclass(slots=True)` | 采样对象用 `__slots__`，减少分配开销 |
| 滑动窗口 ring buffer | 固定大小窗口（默认 500 tick），无动态扩容 |
| `enabled=False` 时零开销 | 空操作 contextmanager，编译期可消除 |
| per-entity 采样可关 | `measure_entity` 可通过配置关闭，只保留 per-System |
| 函数级插桩按需启用 | `measure_function` 仅在 `--hotpath` 时启用，常态关闭 |

开销预算分解（全量采集模式，1000 实体 + 5 System）：

```
per-System contextmanager enter+exit:  5 × 2 × 100ns  = 1μs
per-entity contextmanager enter+exit:  5000 × 2 × 100ns = 1ms  (上限)
TickSample 构造 + ring buffer 写入:    5 × 500ns = 2.5μs
────────────────────────────────────────────────────────
总计: ~1ms（正好 1% 预算）
```

注：per-entity 插桩是开销大头。若 1000 实体 × 5 System = 5000 次 contextmanager 进出，约 1ms。若需进一步降低，可启用采样模式（1/K 比例采集 per-entity）。

### 5.3 可开关机制

| 模式 | enabled | 说明 |
|---|---|---|
| 生产 | False | 零开销，所有方法为空操作 |
| 调试 | True，全量 | per-System + per-entity 全采集 |
| 压测 | True，全量 + hotpath | 叠加函数级插桩 |
| 监控 | True，采样 | 1/N tick 采样，低开销长时间运行 |

开关通过引擎配置控制，不需要重启引擎（运行时切换 `profiler.enabled`）。

### 5.4 与 ADR-0012 benchmark 的衔接

| ADR-0012 阶段 0 成果 | Tick Profiler 阶段 1 衔接 |
|---|---|
| resolve_attack 中位数 25.9μs | Tick Profiler 验证 1000 实体 CombatSystem 总 compute 是否 <50ms（1000 × 25.9μs ≈ 25.9ms） |
| GC 基准：分配热点（CombatRoundResult/Effect/LedgerEntry） | Tick Profiler per-entity 识别 GC 抖动导致的尾延迟（p99 远超 mean） |
| PYTHONHASHSEED=0 确定性验证 | Tick Profiler 不涉及确定性（性能观测工具，非重放工具） |
| 阈值：单 resolve_attack 中位数 <50μs / p99 <200μs | Tick Profiler 验证 tick 级阈值：total compute <100ms / per-System p99 <50ms |

---

## 六、最小实现范围（阶段 1）

### 阶段 1 必做

| 功能 | 说明 |
|---|---|
| per-System compute 统计 | mean/p99/max/total/ticks，按 System 聚合 |
| CLI `profile tick` 基础报告 | 表格格式输出 System 统计摘要 + tick 预算占比 |
| 开关机制 | `enabled=False` 零开销 / `enabled=True` 全量采集 |
| 滑动窗口 ring buffer | 固定 500 tick 窗口，无动态扩容 |
| `--json` 输出 | 供脚本消费的 JSON 格式 |
| `--system <name>` 过滤 | 聚焦特定 System |

### 阶段 1 不做（后置）

| 功能 | 后置到 | 理由 |
|---|---|---|
| per-entity tick 开销 | 阶段 1 后半 | 1000+100 压测发现瓶颈后再细化 |
| 非均匀 tick 可视化 | 阶段 1 后半 | 需非均匀 tick 调度器先就绪 |
| 热路径函数级分解 | 阶段 2 | CombatSystem 实现后才有意义 |
| 采样采集模式 | 阶段 2 | 全量采集在 1000 实体下开销可控 |
| 历史趋势 / 回归基线 | 阶段 2 | 需多次压测数据积累 |
| 火焰图 | 后置 | 需 py-spy / austin 等外部工具，非自研 |

### 验收标准

- [ ] `profile tick` 能输出 per-System 统计摘要（mean/p99/max/total/%tick）
- [ ] `enabled=False` 时 profiler 开销可忽略（微基准验证：空操作 contextmanager 开销 <0.1ms/tick）
- [ ] `enabled=True` 全量采集时 profiler 开销 <1ms/tick（1000 实体 + 5 System 场景）
- [ ] `--json` 输出可被 `json.loads` 解析
- [ ] 代码不引入已砍复杂度（无分布式 / K8s / Redis / 50ms tick）
- [ ] ruff lint/format 全过

---

## 七、后置能力

| 能力 | 触发条件 | 说明 |
|---|---|---|
| 火焰图 | 阶段 2 热路径优化需求 | 对接 py-spy / austin 采样 profiler，生成 SVG 火焰图；自研 profiler 不做火焰图 |
| 历史趋势 | 多次 1000+100 压测后 | tick compute 时间序列存储 + 回归基线对比（基线 snapshot + diff 报告） |
| 1000+100 负载压测集成 | 阶段 1 后半 | profiler 内嵌压测脚本，自动跑 1000 实体 + 100 并发 + N tick 采集 + 报告 |
| Langfuse 对接 | Agent 侧（M2） | Agent 编排的 tick 开销追踪，非引擎 tick profiler 范围 |
| 采样采集模式 | 长时间运行监控需求 | 1/N tick 采样 + per-entity 1/K 比例采样，降低持续运行开销 |
| 对象池决策支持 | tick profiler 实测数据显示 GC 是瓶颈 | [04](04-迁移路径与避坑清单.md) §六不做：CombatRoundResult/Effect 对象池化用 tick profiler 实测后再决定 |
| OTel 导出 | 运维观测后置阶段 | profiler 采样数据导出为 OTel metric（后置基础设施，当前不引入） |

---

## 八、约束对照

| 约束 | 本设计如何遵守 |
|---|---|
| [04](04-迁移路径与避坑清单.md) §六不做：不引入分布式/K8s/Redis | 纯进程内工具，无外部依赖 |
| [04](04-迁移路径与避坑清单.md) §六不做：不引入 50ms/20Hz 框架 | profiler 测量 1s tick，不改变 tick 频率 |
| [04](04-迁移路径与避坑清单.md) §六不做：对象池后置 | profiler 为对象池决策提供数据，不预判实现 |
| [04](04-迁移路径与避坑清单.md) §六不做：6 件工具链砍为 3 件 | profiler 是最小三件之一，不做超出范围的功能 |
| CLAUDE.md 不变量：tick=1s + compute<100ms + 非均匀 tick | profiler 是该不变量的测量工具，自身不改变 tick 语义 |
| 性能开销 <1% tick 预算 | §5.2 开销控制：全量 <1ms/tick，关闭时零开销 |
| 收敛优先于完备 | 阶段 1 只做 per-System 统计 + CLI 报告 + 开关，其余后置 |

---

*本文档是引擎工具链最小三件 PRD 之二（Tick Profiler）。关联文档：[04-迁移路径与避坑清单](04-迁移路径与避坑清单.md) / [ADR-0012](../adr/ADR-0012-performance-microbenchmark.md) / [层 G NPC AI 规格](../engine/src/xkx/spec/layer_g_npc_ai.py)。*
