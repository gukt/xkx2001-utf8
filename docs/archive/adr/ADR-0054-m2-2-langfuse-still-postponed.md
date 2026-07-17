# ADR-0054: M2-2 仍不接入 Langfuse

## 状态

- 日期：2026-07-15
- 决策：接受
- 影响范围：M2/UGC 创作闭环、可观测性、依赖管理

## 上下文

M2/UGC 创作闭环 MVP（ADR-0053）已落地：自定义 Orchestrator + 4 个 MCP 校验器 +
最小 RAG + 自动修订闭环 + CLI workbench。M2-2 增强轮在本分支
`feat/m2-ugc-loop-r2` 继续推进 layer2 Ink 对话树 / FastAPI+WebSocket 评审工作台 /
ClaudeClient adapter。

ADR-0036 已决定"Langfuse 后置"，理由是 kill criteria 5（修订量 <40%）的度量
依赖本地 `tools/measure_revision.py` 的 `semantic_ratio`，不依赖 Langfuse。

## 问题

M2-2 是否应当引入 Langfuse SDK 做 trace/observability？

## 决策

**M2-2 仍不接入 Langfuse。** 仅做文档记录与代码暗示清理。

## 理由

1. **当前 kill criteria 已满足**：M2 MVP 第 4 轮 semantic_ratio 降至 30.3%，低于
   40% 走弱线；度量完全基于本地 diff + 独立 LLM 语义判断，无需 Langfuse。
2. **依赖收敛原则**：04 §六明确约束"纯 Python""无新运行时依赖除非必要"。
   Langfuse SDK 及其依赖（postgresql/s3 等）与当前"内存数据+本地 JSON"架构冲突。
3. **可观测性收益边际递减**：当前痛点是修订量与可跑通性，不是跨迭代 trace
   查询。评审工作台（M2-2）已提供 WebSocket 实时事件流，覆盖即时观察需求。
4. **商业化前再评估**：Langfuse 适合外部作者规模化后的审计与 provenance 追踪，
   该阶段在阶段 0 之后，与 M3-4 版权清洗同步考虑更合理。

## 后果

- 正面：保持依赖树精简；避免为可观测性引入额外基础设施。
- 负面：跨 session 的 LLM 调用历史无法通过 Langfuse 检索；后续若需大规模
  人工审计，需重新打开本 ADR。

## 相关

- ADR-0036-content-llm-volcano-ark-langfuse-postpone.md
- ADR-0053-m2-ugc-loop-mvp-scope.md
