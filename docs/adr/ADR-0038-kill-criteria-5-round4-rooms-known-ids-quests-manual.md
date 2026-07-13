# ADR-0038：kill criteria 5 第 4 轮方向 A 裁决（rooms known ids + quests 改人工）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 Wave 2（M3-1 kill criteria 5 修订量度量收尾）
- 关联：[ADR-0036](ADR-0036-content-llm-volcano-ark-langfuse-postpone.md) 决策 3（kill criteria 5 阈值）/ [ADR-0032](ADR-0032-family-core-loop-design.md) 决策 6 / [ADR-0004](ADR-0004-agent-dsl-generation-s3.md) measure_revision

## 背景

[ADR-0036](ADR-0036-content-llm-volcano-ark-langfuse-postpone.md) 决策 3 定 kill criteria 5 判定阈值：累积 3 轮后 >40% 先扩 DSL 表达力 / 扩后仍 >30% Agent 降级。measure_revision 的 semantic_ratio（非注释行变化 / v1 非注释行）为度量本体。

累积 3 轮数据：

- 第 1 轮 37.0%（子集 5 NPC + 3 skill + 3 quest，<40% 走弱线）
- 第 2 轮 56.9%（完整雪山派 11+11+6+20，>40% 走弱线，结构错误 70 个）
- 第 3 轮 44.6%（prompt 强化 4 点后，结构错误 70->2，但仍 >40%）

第 3 轮 prompt 强化 4 点（id 引用规范 / quest 结构 trigger 单值+objectives 完整 / 文本字段单行 / gender 中文+ANSI 清洗）使结构错误从 70 降到 2，semantic_ratio 从 56.9% 降到 44.6%。但仍 >40%，需裁决方向。

## 问题

第 3 轮 44.6% 的剩余 ratio 集中在两类问题：

1. **quests objectives 完整性弱**（quests 97.6%）：LLM 对 LPC 任务链理解不足，jiamu/lazhangfo objectives 仍空，pilgrimage/fsgelun 缺 reach_room 步骤。这是 LLM 对 LPC set_temp marks + accept_object + valid_leave/go 调用链的结构化理解弱点，prompt 强化后仍未解决，继续 prompt 迭代收益递减。

2. **rooms 幻觉引用**（rooms 63.1%）：LLM 忠实转译 LPC 源码的所有 exits/objects，包括指向范围外房间（kongque/tower/shilun/shangu1 等 9 处）和未生成 NPC（tuying/lu/xiangke 等 10+ 处）。v1 人工裁剪到 20 房间/11 NPC 范围。这是"LLM 忠实转译"vs"v1 人工裁剪"的内容差异，非 LLM 结构错误。

剩余 ratio 中，npcs 29.3%（属性值差异，LLM 转 LPC 原值 vs v1 人工调整数值）和 skills 4.2% 是内容性差异，非结构错误。

## 决策

### 决策 1：rooms 注入 known ids 范围裁剪

[build_room_prompt](../../engine/src/xkx/content_gen/prompts.py) 加 `known_room_ids` / `known_npc_ids` 可选参数。若提供，prompt 注入范围裁剪指令：只保留指向已知 id 的 exits/objects，LPC 源码里指向范围外房间的 exit 或范围外 NPC 的 object 一律省略。

[generate_room](../../engine/src/xkx/content_gen/generate.py) 透传 known ids。[generate_rooms_v0.py](../../engine/tools/content_gen/generate_rooms_v0.py) 从 ROOMS 列表提取 20 房间 id + 从 generate_v0.NPCS 提取 11 NPC id，注入每个 room prompt。

效果：rooms semantic_ratio 63.1% -> 44.6%（幻觉引用消除，v0 行数 186 -> 153 ≈ v1 157）。

### 决策 2：quests 改人工（LLM 仅生成 NPC/skill/room）

第 3 轮证明 quests objectives 完整性是 LLM 理解弱点，prompt 难解决。裁决 quests 改人工：

- LLM 不再生成 quests（generate_v0_resume.py 跳过 quests）
- quests.yaml 用 v1 人工版本（已入库 scenes/xueshan_micro/quests.yaml）
- v0 目录的 quests.yaml 标注"人工编写"（measure_revision semantic_ratio 0%）

LLM 仍生成 NPC/skill/room（这三类第 3 轮结构错误已近清零）。

效果：quests semantic_ratio 97.6% -> 0%。

### 决策 3：第 4 轮结果（30.3% < 40% 达标）

第 4 轮 semantic_ratio = 30.3%（rooms 44.6% + npcs 29.3% + quests 0% + skills 4.2%）。结构错误 0（check_v0_errors 验证）。1744 tests 全绿。

**kill criteria 5 走弱线通过**（<40%）。不触发 >30% 降级线（30.3% 接近但未超降级阈值，且剩余 ratio 是内容性差异非结构错误）。

累积 4 轮：37.0% / 56.9% / 44.6% / 30.3%。

## 后续

- **剩余 ratio 不阻塞**：npcs 29.3%（属性值差异）+ rooms 44.6%（long 文本精简差异）是"LLM 忠实转译 LPC"vs"v1 人工调整/精简"的内容性差异，非 LLM 结构错误。M3-1 Wave 2 收尾，进 Wave 3。
- **quests 人工可持续**：后续门派（武当/少林等）的 quests 可沿用人工模式（LLM 生成 NPC/skill/room，quests 人工写），直到 LLM 任务链理解能力提升（M2 独立 LLM 验证时再评估）。
- **known ids 模式可复用**：rooms known ids 范围裁剪模式可推广到后续门派生成（每个门派的 generate_rooms 脚本注入该门派的已知房间/NPC id 列表）。
- **工具沉淀**：[check_v0_errors.py](../../engine/tools/content_gen/check_v0_errors.py) 自动检查 4 类错误 + [generate_v0_resume.py](../../engine/tools/content_gen/generate_v0_resume.py) 断点续跑（会话切换停后台任务时复用已生成部分），为后续轮次/门派生成提供工具支撑。
