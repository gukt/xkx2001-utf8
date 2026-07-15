# ADR-0053：M2/UGC 创作闭环 MVP 范围与 LLM 基线

- 状态：已采纳
- 日期：2026-07-15
- 阶段：M2

## 背景

M3 收官后，项目最高优先级的未闭合创新点是 M2："DSL + Agent 创作闭环"（[04 §三](../xkx-arch/04-迁移路径与避坑清单.md)）。当前已实现 DSL layer0/1、`content_gen` 单-shot 生成、`content_review` 预检、`measure_revision` L1~L4 校验；缺失 Orchestrator、MCP、RAG、评审工作台。本 ADR 裁决 M2 MVP 的最小范围与 LLM 后端基线。

## 决策

### 1. M2 MVP 先用 layer0/1 闭合 loop，延后 layer2/3

- **layer2 Ink 对话树** 与 **layer3 RestrictedPython 沙箱** 不纳入本 Wave。
- 对话需求继续用现有 `NpcDef.inquiry` 静态映射；复杂逻辑用 `# GAP:` 标注。
- 理由：闭合"生成 -> 校验 -> 修订"的循环是 M2 核心假设，layer2/3 会显著扩大范围且当前无迫切需求。

### 2. CLI 评审工作台替代 FastAPI/WebSocket Web UI

- 本 Wave 的评审入口为 `just orchestrate review <cpk>`，输出 world-graph 摘要、校验结果、预检发现、checklist。
- FastAPI + WebSocket 可视化工作台后置到 M2-2。

### 3. Langfuse 追踪保持后置

- 继续用本地 `semantic_ratio` + `revision_trace.json` 度量修订量。
- Orchestrator 内部预留可插拔 trace 位，但不引入 Langfuse 依赖。
- 与 ADR-0036 决策 3 一致：Langfuse 在独立 LLM 趋势稳定后再接入。

### 4. 火山方舟成为主 LLM 基线

- 架构文档 [03 §六](../xkx-arch/03-DSL-UGC与Agent协作.md) 原表述为"Claude API 主 + 可插拔 GLM"，与实际落地（ADR-0036 火山方舟 + `LLMClient` Protocol）不一致。
- 将 03 §六 更新为"火山方舟主 + 可插拔 adapter（Claude/GLM 可选）"。
- 保留 `LLMClient` Protocol，未来加 ClaudeClient adapter 不影响架构。

## 实现概要

- 新增 `engine/src/xkx/orchestrator/`：状态机、RAG（WorldBible）、Capability Registry、MCP Verifiers、闭环逻辑、CLI。
- MCP 校验器：world-graph 可达性（stdlib BFS）、schema 四道校验、content_review 预检、measure L4。
- 新增 `engine/scenes/bibles/xueshan.yaml` 作为 RAG 上下文示例。
- 新增 `just orchestrate` recipe。
- 扩展 `content_gen`：`generate_rule()` + `revise_asset()` + 对应 prompts。

## 不做（收敛）

- 不实现 layer2 Ink / layer3 RestrictedPython。
- 不实现 FastAPI/WebSocket 评审工作台。
- 不接入 Langfuse。
- 不引入 networkx（world-graph 用 stdlib BFS）。
- 不做 ClaudeClient adapter（保留 Protocol，按需后续添加）。

## 关联

- [03 §六](../xkx-arch/03-DSL-UGC与Agent协作.md)（Agent 架构与 LLM 选型，已同步更新）。
- [ADR-0036](ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)（火山方舟 + Langfuse 后置）。
- [04 §三](../xkx-arch/04-迁移路径与避坑清单.md)（M2 定义）。
- [05 §五](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3（层1 原语蠕变风险：本 MVP 通过延后 layer2/3 控制）。
