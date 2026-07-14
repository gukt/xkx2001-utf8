# ADR-0036：内容生产 LLM 选型（火山方舟 + deepseek-v4-flash，Langfuse 后置）

- 状态：已通过（2026-07-13）
- 日期：2026-07-13
- 阶段：M3 Wave 2（M3-1 子任务 4 内容生产落地）
- 关联 dissent：[03](../xkx-arch/03-DSL-UGC与Agent协作.md) §六 技术选型（LLM：Claude API 主 + 可插拔 GLM）/ [ADR-0032](ADR-0032-family-core-loop-design.md) 决策 6 + 开放问题 4 / [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) measure_revision 修订量度量

## 背景

[ADR-0032](ADR-0032-family-core-loop-design.md) 决策 6 + 开放问题 4 原定内容生产方式为「Claude API + Langfuse 追踪」。[03 §六](../xkx-arch/03-DSL-UGC与Agent协作.md) 技术选型基线为「LLM = Claude API 主 + 可插拔 GLM（符合部署环境）」。M3-1 子任务 4 内容生产落地时，用户决策改用火山方舟（Volcano Ark）Endpoint + deepseek-v4-flash 模型，且 Langfuse 后置。

## 问题

1. **LLM 选型偏离 03 §六 基线**：基线主 LLM 是 Claude API。改用火山方舟 + deepseek-v4-flash 是对基线的偏离，需 ADR 记录（CLAUDE.md：偏离 00-04 基线须写 ADR）。
2. **Langfuse 后置**：决策 6 原定 Langfuse 追踪修订量。后置后 kill criteria 5（修订量度量）数据源需明确。
3. **可插拔架构**：03 §六 已留「可插拔 GLM」口子，本 ADR 落地首个非 Claude adapter，需确定 LLMClient 抽象边界。
4. **部署环境**：03 §六 rationale「符合部署环境」-- 火山方舟是国内可访问的模型推理平台，deepseek 系列中文/代码能力强，契合国内部署环境。

## 决策

### 决策 1：LLMClient 抽象 + 火山方舟 adapter

新建 `engine/src/xkx/content_gen/llm_client.py`：

- `LLMClient` Protocol（`chat(messages, *, model=None, **kw) -> str`），创作期工具不进 runtime 导入图。
- `VolcanoArkClient`：火山方舟 OpenAI 兼容 `/api/v3/chat/completions`，stdlib `urllib.request`（POST JSON + JSON 响应），**无新运行时依赖**。
- 可插拔架构：未来可加 ClaudeClient / GlmClient adapter，本 ADR 只落地火山方舟首个 adapter。

依赖选型 stdlib urllib（非 openai SDK / httpx）遵循 [04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 收敛原则 + [ADR-0012](ADR-0012-performance-microbenchmark.md) 先例（stdlib timeit 替代 pytest-benchmark）。content_gen 仅依赖 stdlib + 已有 pyyaml，不污染 runtime 依赖清单。

### 决策 2：主 LLM = 火山方舟 + deepseek-v4-flash

- `ARK_BASE_URL` = `https://ark.cn-beijing.volces.com/api/v3`（OpenAI 兼容 chat/completions 端点）
- `ARK_API_KEY` = 用户在火山方舟控制台的 API key
- `ARK_MODEL` = `deepseek-v4-flash-260425`（火山方舟 model ID 含日期后缀；用户指定的 deepseek-v4-flash 实际 ID，默认，可被 env/CLI 覆盖）

配置经 `engine/.env`（不入库，见决策 4 安全）。`.env` 加载用极简内联解析器（KEY=VALUE，跳过注释，仅当 os.environ 未设时填入），不引入 python-dotenv 依赖（同决策 1 收缩原则）。

### 决策 3：Langfuse 后置

- **kill criteria 5 修订量度量不依赖 Langfuse**：[measure_revision.py](../../engine/tools/measure_revision.py) 的 `semantic_ratio`（非注释行变化 / v1 非注释行，排除注释重组噪声）本地即可度量。Langfuse 只是跨迭代趋势的可观测层，非度量本体。
- 本轮用 measure_revision 本地度量产出首个 kill criteria 5 数据点。Langfuse 接入后置（独立 LLM 验证趋势稳定后再接，避免观测层引入与内容生产无关的复杂度）。
- kill criteria 5 判定阈值不变（[ADR-0032](ADR-0032-family-core-loop-design.md)）：3 轮迭代后 >40% 先扩 DSL 表达力 / 扩后仍 >30% Agent 降级。本轮 1 轮产首个数据点，不判定，累积 3 轮后判。

### 决策 4：安全约束（硬性）

- `ARK_API_KEY` 只准写入 `engine/.env`，绝不硬编码进源码、绝不提交 git。
- 创建 `engine/.env` 前必须先把 `.env` 加入 `engine/.gitignore`。
- 测试中不发起真实 API 调用（mock LLMClient / monkeypatch urllib）。
- 文档/日志不出现 API key 明文，只引用 `ARK_API_KEY` 环境变量名。

### 决策 5：本轮范围（子集先行）

完整雪山派内容量大（~25 房间 + 6 师傅/门槛 + 11 武学 + 4 任务链），单 session 难一次推完且需 prompt 迭代。本轮子集先行验证管线：

- 2 师傅 NPC（gongcang + samu，含 ApprenticeDef rich 条件）
- 3 武学 SkillData（longxiang-banruo / lamaism / xueshan-jian）
- 1 新任务链（darba fight_win）
- 支撑房间/物品

验证 LLM -> 人工修订 -> measure 全链路，产出首个 kill criteria 5 修订量数据点。完整内容下一 session 扩展。

## 不做（后置）

- 完整雪山派内容（剩余 3 师傅 + 8 武学 + 3 任务链 + ~20 房间）-- 下一 session
- Langfuse 接入 -- 独立 LLM 验证趋势稳定后
- SkillData rich 字段（valid_learn/practice_skill 结构化条件 + query_action 招式表）-- 需扩练功命令 + combat action 选择，后置；本轮保持 [ADR-0032](ADR-0032-family-core-loop-design.md) 决策 2 的 bool stub，rich LPC 条件记 GAP
- 多轮生成-修订迭代（3 轮 kill criteria 5 判定）-- 本轮 1 轮首个数据点，后续轮次累积

## kill criteria

- **kill criteria 5**（Agent 修订量）：本轮产出首个 semantic_ratio 数据点（measure_revision 本地度量）。判定阈值不变（3 轮 >40% 走弱 / >30% 降级），本轮 1 轮不判定。
- **test_theme_neutrality**：门派武学走 SkillData 声明不进内核，content_gen 是创作期工具不进 runtime 热路径，硬门禁持续通过。
- **test_load_test**：tick p99 < 100ms 不退化（content_gen 不进 runtime 热路径）。

## 验收标准（本轮子集）

- [ ] LLMClient 抽象 + VolcanoArkClient（stdlib urllib，.env 配置，无新依赖）
- [ ] content_gen 生成管线（prompts + generate + cli，grounded in 07 映射）
- [ ] SkillData CPK 加载管线（skills.yaml + cpk_loader 扩展 + register_skill_data 接线）
- [ ] 子集内容生成（2 师傅 + 3 武学 + 1 任务链 + 房间物品）经 LLM v0 -> 人工 v1 修订入 CPK
- [ ] measure_revision 扩展（items.yaml/skills.yaml）+ 首个 semantic_ratio 数据点
- [ ] 测试（mock LLM，无真实 API）：test_llm_client + test_content_gen + test_skill_data_cpk
- [ ] 全量 tests 绿 + ruff 全过；test_theme_neutrality + test_load_test 硬门禁持续通过

## 关联

- [03](../xkx-arch/03-DSL-UGC与Agent协作.md) §六 技术选型（LLM：Claude API 主 + 可插拔 GLM，符合部署环境）-- 本 ADR 偏离此基线，落地首个非 Claude adapter
- [ADR-0032](ADR-0032-family-core-loop-design.md) 决策 6（内容生产方式）+ 开放问题 4（独立 LLM 选型）-- 本 ADR 实施期细化
- [ADR-0004](ADR-0004-agent-dsl-generation-s3.md)（measure_revision 修订量度量，kill criteria 5 数据源）
- [ADR-0031](ADR-0031-cpk-format-and-themeregistry-static-loading.md)（CPK 格式，skills.yaml 入库载体）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §六 收敛原则 + [ADR-0012](ADR-0012-performance-microbenchmark.md) stdlib 优先先例

> **ADR 编号说明**：[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) ADR 映射预留 ADR-0033（审核）/0034（版权）/0035（确定性）。本 ADR 是 M3-1 Wave 2 内容生产落地期的 LLM 选型决策，用 ADR-0036（下一个空闲编号，不占用预留）。16-M3 ADR 映射表同步追加 ADR-0036。
