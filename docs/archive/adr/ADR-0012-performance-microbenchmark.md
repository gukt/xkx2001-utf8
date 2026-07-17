# ADR-0012：性能 micro-benchmark 方法论与 go/no-go 阈值

- 状态：已采纳（阶段 0 任务 4）
- 日期：2026-07-11
- 阶段：0 任务 4（性能 micro-benchmark，go/no-go 硬门禁）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三任务 4 / §四 kill criteria 3 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 性能基准硬门禁 dissent / [ADR-0002](ADR-0002-resolve-attack-extraction.md)（resolve_attack S1 实现）/ [ADR-0009](ADR-0009-original-driver-runnable.md)（driver 可运行）/ [ADR-0010](ADR-0010-lpc-spec-extraction-methodology.md)（层 E 规格）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 0 任务 4 验收标准：

> | **性能 micro-benchmark（go/no-go 硬门禁）** | 单 do_attack μs 报告 + 1s tick 预算 + 1000+100 负载压测 + GC 基准 + PYTHONHASHSEED=0 | 有数据支持继续推进；不达标触发 kill criteria |

kill criteria 3：

> micro-benchmark 单 do_attack 超阈值 -> 先优化热路径（对象池/避免分配/缓存）；1000 实体 tick 超预算 -> 降 tick 频率或裁剪 System；1000+100 经优化仍不达标且无 Rust 退路 -> **降级目标到 500 在线+50 并发**（仍是当前 10 倍）并重新评估 Rust/Go 热路径

任务 1 层 E 已产出 do_attack 七步规格（[ADR-0010](ADR-0010-lpc-spec-extraction-methodology.md)，26 函数 / 49 副作用 / 31 处 random），S1 已提取 `resolve_attack` 纯函数（[ADR-0002](ADR-0002-resolve-attack-extraction.md)）。本 ADR 定义任务 4 的方法论、阈值与范围边界。

[05](../xkx-arch/05-第三轮专家对抗复审报告.md) 性能基准硬门禁 dissent：性能基准从"决策 compiled core"改为"go/no-go 硬门禁"（[04](../xkx-arch/04-迁移路径与避坑清单.md) §一核心立场 5）。本 ADR 落地该裁决的阶段 0 部分。

## 范围：阶段 0 可做 vs 后置阶段 1

| 项 | 阶段 0 | 阶段 1 | 理由 |
|---|---|---|---|
| 单 resolve_attack μs 基准 | ✅ 可做 | - | 纯函数已存在，无需框架 |
| GC 基准（分配计数 + gc.get_stats） | ✅ 可做 | - | 纯函数可隔离测量 |
| PYTHONHASHSEED=0 确定性验证 | ✅ 可做 | - | 跨进程重放验证 |
| 1s tick 预算实测 | 概念性推算 | ✅ 实测 | 需阶段 1 tick 框架 + 非 uniform tick 调度 |
| 1000+100 负载压测 | - | ✅ | 需阶段 1 ECS + WS 服务器框架（[08](../xkx-arch/08-阶段-0-实施计划.md) §五：1000+100 负载需阶段 1 框架） |

**阶段 0 聚焦"单 resolve_attack μs 基准 + GC 基准 + PYTHONHASHSEED 验证"三件**，作为 kill criteria 3 的前置数据点。完整 go/no-go 判定需阶段 1 的 1000+100 负载实测；本 ADR 的 μs 阈值是"单点不超标"的必要条件，非充分条件。

## 方法

### 1. resolve_attack μs 基准

- **工具**：标准库 `timeit`（不引入 pytest-benchmark 新依赖，符合 [04](../xkx-arch/04-迁移路径与避坑清单.md) §一核心立场 7 收敛原则）
- **取样**：N=10000 次 resolve_attack 调用，统计 min/median/p99/max
- **场景覆盖**：三分支各取样（hit/dodge/parry），用不同 seed 触发各分支
- **fixture**：复用 [test_resolve_attack.py](../../engine/tests/test_resolve_attack.py) 的 `_attacker`/`_victim`/`_ctx` 模式（中等属性 CombatantSnapshot）
- **隔离**：GC disabled 模式 vs enabled 模式各测一次（分离 GC 噪声）

### 2. GC 基准

- **指标**：单次 resolve_attack 的内存分配量（`tracemalloc`）+ `gc.get_stats()` 代际回收频率
- **场景**：连续 10000 次调用，统计 gen0 回收次数
- **目的**：识别分配热点（`CombatRoundResult` / `Effect` / `LedgerEntry` 对象分配），为阶段 1 对象池决策提供数据（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做：对象池化用 tick profiler 实测后再决定）

### 3. PYTHONHASHSEED=0 确定性验证

- **方法**：同 seed + 同快照，跨进程（`PYTHONHASHSEED=0` / `=1` / 随机）各跑 100 次，比较输出
- **验证**：resolve_attack 输出完全一致（combat 确定性基础，阶段 1 里程碑前置，[04](../xkx-arch/04-迁移路径与避坑清单.md) §五范围检查点 6）
- **预期**：resolve_attack 内部用 `random.Random(seed)`（非 hash），PYTHONHASHSEED 不应影响；验证此预期成立

## 阈值

### 阶段 0 μs 阈值（本 ADR 定义）

| 指标 | 阈值 | 推导 |
|---|---|---|
| 单 resolve_attack 中位数 | < 50μs | 1000 实体 * tick<100ms；combat 占 50% 预算 -> 1000*X < 50,000μs -> X < 50μs |
| 单 resolve_attack p99 | < 200μs | 尾延迟控制（GC 抖动容忍） |
| PYTHONHASHSEED 跨进程一致性 | 完全一致 | combat 确定性基础 |

### 阈值推导依据

- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 验收：tick compute<100ms（非均匀 tick）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做：tick=1s + compute<100ms（LPC heart_beat 实测 `set_heart_beat(1)`）
- 1000 实体是目标上界（[04](../xkx-arch/04-迁移路径与避坑清单.md) §一目标务实：1000 人在线 + 100 并发）
- combat 不是 tick 内唯一 System，留 50% 给其他 System 是保守估计
- 实际 1000 在线时活跃战斗者远少于 1000，但保守上界合理（为阶段 1 1000+100 实测留余量）

### 超标应对（kill criteria 3 阶段 0 部分）

1. **中位数超标** -> 先优化热路径（对象池 / 避免分配 / 缓存 `skill_power` 结果 / `__slots__`）
2. **优化后仍超标** -> 记录为风险，不立即触发 kill criteria（完整 kill criteria 3 需 1000+100 负载双失败）
3. **阶段 1 1000+100 实测双失败且 Python 优化穷尽** -> 触发 kill criteria 3（降级目标到 500+50 或评估 Rust/Go 热路径，[04](../xkx-arch/04-迁移路径与避坑清单.md) §四 kill criteria 3/9）

## 决策

1. **不引入 pytest-benchmark**：标准库 `timeit` 足够，符合收敛原则（[04](../xkx-arch/04-迁移路径与避坑清单.md) §一核心立场 7）。pyproject dev 依赖仅 pytest+hypothesis+ruff，不新增
2. **benchmark 脚本放 [engine/tools/benchmark.py](../../engine/tools/benchmark.py)**：与 [measure_revision.py](../../engine/tools/measure_revision.py) 同目录
3. **benchmark 测试放 [engine/tests/test_benchmark.py](../../engine/tests/test_benchmark.py)**：作为回归门禁，防性能退化（阈值硬断言，但 p99 容忍 GC 抖动用软断言）
4. **三分支覆盖**：hit/dodge/parry 各 benchmark，用不同 seed 触发各分支
5. **GC disabled + enabled 双测**：分离 GC 噪声，识别分配热点
6. **benchmark 不进 CI 硬门禁**：性能受运行环境影响，CI 硬断言易误报。`test_benchmark.py` 用宽松阈值（中位数 < 200μs，留 4x 余量）防退化，精确基准由本地 `tools/benchmark.py` 跑

## 后置（阶段 1）

- 1000+100 负载压测：需阶段 1 ECS + WS 服务器框架 + 会话管理
- 1s tick 预算实测：需阶段 1 tick 框架 + 非 uniform tick 调度
- compiled core (Rust/Go) 评估：仅当 μs 基准 + 1000+100 负载双失败且 Python 优化穷尽时触发（kill criteria 3/9，[04](../xkx-arch/04-迁移路径与避坑清单.md) §四/§六不做）
- 对象池化决策：基于本 ADR GC 基准数据 + 阶段 1 tick profiler 实测后决定（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做：CombatRoundResult/Effect 对象池化用 tick profiler 实测后再决定）

## 与阶段 0 决策检查点的关系

[04](../xkx-arch/04-迁移路径与避坑清单.md) §八阶段 0 -> 1 决策检查点：

> - **性能 micro-benchmark 是否达标（go/no-go）？**

本 ADR 的阶段 0 部分（μs + GC + PYTHONHASHSEED）提供"单点不超标"的必要条件。完整 go/no-go 判定在阶段 1 1000+100 负载实测后给出。阶段 0 结束时，若 μs 基准达标，记为"go 前置数据点充分"；若超标，记为"需优化后再进阶段 1"。
