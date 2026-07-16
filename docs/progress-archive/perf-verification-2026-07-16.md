# 性能验证核查与归档（2026-07-16）

> 来源：[strategy-review](../strategy-review/04-对抗评审记录与综合裁决.md) 提案 3（核查并归档性能验证实际状态，Impact:High / Effort:Low / Risk:Low）。
> 5 视角复审均未核查性能 kill criteria，本文件补齐实测数据归档，为 kill criteria 3/9 背书。
> 环境：Linux 6.6.87.2-microsoft-standard-WSL2 ｜ Python 3.13.2 ｜ 单机本地实测。

## A. resolve_attack μs 基准（[tools/benchmark.py](../../engine/tools/benchmark.py)，ADR-0012 阈值 median≤50μs / p99≤200μs）

三分支（hit/dodge/parry）× GC on/off 实测：

| 分支 | median μs | p99 μs | 阈值判定 |
|---|---|---|---|
| hit (gc on) | 15.87 | 16.82 | [OK] |
| hit (gc off) | 15.71 | 17.00 | [OK] |
| dodge (gc on) | 11.07 | 12.48 | [OK] |
| dodge (gc off) | 11.37 | 17.03 | [OK] |
| parry (gc on) | 11.24 | 11.98 | [OK] |
| parry (gc off) | 11.20 | 11.90 | [OK] |

- median 全部 11-16μs，远低于 50μs 阈值（余量 ~3x）；p99 全部 <17.1μs，远低于 200μs（余量 ~12x）。
- GC 基准：单次调用内存峰值 5088B（<100KB 阈值，余量 ~20x）；20k 次调用 gen0 回收 **0** 次（<1000，GC 压力极小）。
- PYTHONHASHSEED 跨进程一致性：`consistent_across_processes = true`（0/1/random 三组各 3 次输出全相同），combat 确定性基础成立。
- **判定：GO**（us 基准达标 + hashseed 一致）。

## B. 1000+100 集成压测（[tools/load_test.py](../../engine/tools/load_test.py)，完整配置 300 tick）

配置：1300 实体（50 房间 + 200 NPC + 1000 玩家 + 50 Effect）+ 1000 会话 + 50 战斗对（player↔npc 互打），300 tick，persist_interval=30 / checkpoint_interval=10。

tick compute（μs）：

| 指标 | 值 |
|---|---|
| p50 | 3585 |
| p99 | 10325（10.3ms） |
| max | 11620 |
| mean | 3773 |

per-System（μs）：

| System | mean | p99 | max | %tick |
|---|---|---|---|---|
| CombatSystem | 3437 | 9895 | 11321 | 91% |
| ConditionSystem | 183 | 423 | 1469 | 5% |
| ConnectionSystem | 129 | 250 | 321 | 4% |
| StorageSystem | 4 | 2 | 1177 | <1% |

- tick p99 10.3ms < 100ms 预算（余量 ~10x），**判定：GO**。
- CombatSystem 占 tick 91%（50 战斗对 × 300 tick = 15000 次 resolve_attack，是性能热点，符合预期）。
- 存档 offload 生效：StorageSystem tick 内 mean 4μs（fire-and-forget）；**全量 persist p99 = 1506.2ms 在后台 `asyncio.to_thread`，不含在 tick p99**。

## C. 缺口与观察（需后续关注）

1. **100 并发命令路径未压测**：`LoadTestConfig` 注释明确"100 并发 = 100 同时活跃命令（tick compute 不含命令处理，不体现于此）"。kill criteria 3 的"1000+100"里 **100 并发命令处理维度无数据**，load_test 只压了 50 战斗对的 combat tick + 1000 会话。命令管线在 100 并发下的 compute 未验证（关联 [04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 5"1000+100 负载"维度）。建议后续补命令并发压测或显式声明"100 并发留 M3 后/外部玩家测试前"。
2. **persist 全量 1.5s**：全量 checkpoint persist p99 1506ms（1300 实体全量序列化写 JSON）。虽 offload 不阻塞 tick，但 1.5s 窗口内崩溃会丢增量（关联 [ADR-0022](../adr/ADR-0022-json-save-crash-recovery-dirty-flag.md) dirty-flag 分摊 + kill criteria 8 迁 PG 的 30s 崩溃窗口红线）。
3. **CI 回归门禁现状**：[test_benchmark.py](../../engine/tests/test_benchmark.py)（4 测试，median<200μs/内存<100KB/GC<1000）+ [test_load_test.py](../../engine/tests/test_load_test.py)（4 测试，CI 30 tick p99<100ms + scaled(500) 配置 + per-System 覆盖）共 **8 passed in 22.40s**。CI 阈值较本地宽松（test_benchmark 200μs vs benchmark.py 50μs；test_load_test 30 tick vs 完整 300 tick），防退化而非精确基准。

## D. 与 kill criteria 关系

- **kill criteria 3（性能基准）**：micro-benchmark（A）+ 1000+100 负载（B）双 GO，未触发"降级 500+50 或优化热路径"。
- **kill criteria 9（性能后置触发）**：双失败且 Python 优化穷尽才重评 Rust/Go。当前双 GO，未触发。
- **kill criteria 6/8**：单进程核心循环支撑 1000+100（B 验证 tick 维度）；JSON 存档迁 PG 红线见观察 2。

## 后续

- 100 并发命令压测补齐（观察 1）。
- persist 全量耗时优化或迁 PG 时重评（观察 2）。
- 性能数据随引擎演进定期重测归档（避免"全绿"无性能背书的盲区）。
