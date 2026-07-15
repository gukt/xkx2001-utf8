# 阶段 B pilot 实测脚手架

> 抽样校准实验阶段 B 修正后（[ADR-0048](../../../../docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)）的 pilot 实测工作目录。**一次性测量代码，测完即丢，不污染 `src/xkx`**（ADR-0048 决策 8）。

## 用途

pilot 12-16 样本迁移工时实测 + 分项记录 + 区间承诺推算。方法论见 [ADR-0048](../../../../docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md) + [17 §六](../../../../docs/xkx-arch/17-抽样校准实验实施计划.md)。

## 文件

| 文件 | 用途 |
|---|---|
| `schema.py` | 工时记录 `EffortRecord` 结构 + 校验 |
| `stubs.py` | 共享桩（`SKILL_D`/`recognize_apprentice` 等，多 logic 样本共用，pilot 前一次性补建） |
| `estimate.py` | 区间承诺推算（读 `effort_records.jsonl` -> 分层均值 × 层规模 + 类比基准） |
| `effort_records.jsonl` | 每样本一条工时记录（实测时填） |
| `samples/` | pilot 样本的 Python 等价代码 + 单元测试（按样本分子文件） |

## 工时记录规范

每样本一条 JSONL，schema 见 `schema.py`。分项：`read_spec` / `write_code` / `write_test` / `debug` / `subtotal`（分钟）。强制记 `corrected_status` / `corrected_kind`（纠偏分类，ADR-0048 决策 3 定量审计）。

## 运行

```bash
cd engine && uv run python -m tools.sampling.pilot.estimate   # 推算区间承诺（pilot 数据齐后）
```
