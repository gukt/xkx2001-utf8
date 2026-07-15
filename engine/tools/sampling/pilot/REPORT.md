# pilot 实测报告（ADR-0048 阶段 B 降级区间承诺）

> 13 样本迁移工时实测 + 区间承诺推算。方法论 [ADR-0048](../../../../docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md) + [17 §六](../../../../docs/xkx-arch/17-抽样校准实验实施计划.md)。
> 生成日期：2026-07-15。工时明细见 [effort_records.jsonl](effort_records.jsonl)。

## 概况

- 样本：13（pending/logic/high 6 + mid 3 + data/low 2 + implemented/logic/high 2）
- 总工时：1065min（17.75h），全部 `tests_pass=True`
- 全量测试：2189 passed（+176 pilot 单测），ruff 全过
- 误分类率：7.7%（1/13，id=10 `snake.c:init` data->logic）
- 执行方式：两阶段并行（阶段一预建 7 组共享桩；阶段二 Workflow 11 agent 并行迁移）

## 区间承诺（全量迁移工时）

| 指标 | 值 |
|---|---|
| 点估 | 1252.9h（75172min） |
| 区间 | [781.6h, 1724.1h] |
| 展幅 | 38%（high-tier 极值偏移推导） |
| pilot high-tier 均值 | 91min |
| 类比基准 high-tier 均值 | 147min（ADR-0048 决策 4） |
| implemented drift | 140min（不外推） |

## 退路校验（ADR-0048 决策 5）

- 误分类率 7.7% < 30% ✓ 不触发接力补测
- high-tier CV ≈ 0.24 < 1.0 ✓ 不触发接力补测
- **两退路均未触发，pilot 数据可用**

## 分层数据

| 层 | n | mean(min) | size | total(min) |
|---|---|---|---|---|
| pending/logic/high | 6 | 90.8 | 21 | 1908 |
| pending/logic/mid | 3 | 78.3 | 186 | 14570 |
| pending/logic/low | 1 | 60.0 | 872 | 52320 |
| pending/data/low | 1 | 85.0 | 75 | 6375 |
| pending/data/mid | 0 | - | 5 | 0 |
| implemented/logic/high | 2 | 70.0 | 0（不外推） | drift 140 |

high-tier 6 样本工时：xue 125 / center 70 / tieyanling 65 / murong 80 / next_sword 95 / die 110。

## 数据质量问题（重要，影响区间承诺可靠性）

### 1. pending/logic/low 层（872 函数）仅 1 个纠偏样本外推，主导点估 70%

id=10 `snake.c:init`（60min，原 data 纠偏为 logic）单独代表 872 个 low-tier logic 函数。
id=10 含战斗触发+概率分支+新命令 `bian`，相对复杂（60min），但 low-tier 函数大多更简单。
60min × 872 = 52320min **占点估 70%**，严重不可靠--真实 low-tier 均值可能 20-30min，
点估可能高估 2-3 倍（若按 25min 计，点估降至约 675h）。

### 2. pending/data/low 层（75 函数）仅 1 个样本

id=11 `char.c:setup`（85min，架构替代）偏高，data/low 通常更简单。1 个样本外推 75 个。

### 3. implemented drift 140min 是"完整迁移"工时，非"补后置分支"工时

id=12 `death_penalty`（45min）+ id=13 `bai.c:main`（95min）按"独立完整迁移"计工时
（迁移 prompt 指示独立等价实现），非 manifest 预期的"补后置分支"（~7min / ≈0）。
drift 140min 应解读为"完整重做成本"而非"后置分支偏差"。不外推，仅作提示。

## 结论与建议

- 区间承诺 [781, 1724]h（约 7.8-21.6 人月，1 人）量级合理，全量迁移需分批/接力（[ADR-0047](../../../../docs/adr/ADR-0047-batch-migration-path.md)）。
- 退路未触发，pilot 数据可用；但 low tier 外推不确定性大，**下界 781h 可能仍偏高**。
- 类比基准 high-tier 147min > pilot 91min，pilot 实测低于预期（agent 迁移或偏快于人工锚点）。
- 建议：low tier（872+75 函数）补测典型样本校准均值，或用类比基准下修后再承诺。

## 产出文件

- 迁移代码：[samples/](samples/)（13 个 `.py`，id=1/3 原 + id=2,4-13 新）
- 单元测试：`engine/tests/test_*.py`（13 个，176 测试）
- 工时记录：[effort_records.jsonl](effort_records.jsonl)（13 条）
- 共享桩：[stubs.py](stubs.py)（10 原桩 + 7 组阶段一预建共享桩）
- 推算脚本：[estimate.py](estimate.py)
