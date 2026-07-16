# AI 迁移批次成本台账

> [ADR-0056](../adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 5 执行回路：AI 成本边跑边记，替代退役的人工工时估算作为迁移规模参考。
> token 从 Claude Code session transcript 自动采集（[tools/batch_cost.py](../engine/tools/batch_cost.py)），避免 agent 自报不准（重蹈 ADR-0056 弃用工时估算的"估算而非实测"覆辙）。
> 运行时间从 transcript 首/末 timestamp 算。session 进行中数值会持续增长，批次收尾时重跑 `record` 更新最终值。
>
> 来源：[strategy-review](../strategy-review/04-对抗评审记录与综合裁决.md) 提案 8（恢复边跑边记 AI 成本执行回路，2026-07-16 落地）。

## 记录口径

- **input / output**：新输入/输出 token（成本主项，output 单价最高）。
- **cache_read**：缓存读 token（单价低，体现 prompt-cache 命中）。
- **total**：input + output + cache_read + cache_creation（throughput 总量）。
- **运行 min**：首条到末条 timestamp 的墙钟跨度（含 agent 思考/工具等待，非纯计算）。
- **产出**：tests 数 / 代码行 / 文档等（人工填）。
- 采集命令：`cd engine && uv run python tools/batch_cost.py tokens`（最新 session）或 `record --batch <名> --adr <ADR-NNNN>` 追加台账。

## 历史批次（ADR-0057~0064，成本未记）

ADR-0056 决策 5 承诺"边跑边记"但后续 5 批迁移（bboard/job_data/武器填表/wield/wear）零成本记录（[strategy-review](../strategy-review/04-对抗评审记录与综合裁决.md) 裁决 5 治理盲区）。本台账自 2026-07-16 起建立，历史批次无 transcript 采集条件，仅留此说明。

| 批次 | 日期 | ADR | input | output | cache_read | total | 运行min | 产出 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 清战略债(strategy-review 提案1/3/5/8) | 2026-07-16 | ADR-0056(决策5) | 1046948 | 340468 | 10728832 | 12116248 | 27.5 | 2416 | 同步04 4处不同步+性能核查归档+rng口径修正+AI成本回路建立 |
