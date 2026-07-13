# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-14

## 当前状态速览

- **阶段**：M3 Wave 2（M3-1 门派核心循环）
- **分支**：feat/stage-3-m3
- **tests**：1744 全绿，ruff 全过
- **关键 ADR**：[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md)（核心循环）/ [ADR-0036](docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)（LLM 内容）/ [ADR-0037](docs/adr/ADR-0037-m3-1-subtask5-playtest-demo-integration.md)（demo 集成）
- **下一步**：kill criteria 5 第 3 轮（改进 prompt 后再跑，看 ratio 是否 <40%）
- **可玩 demo**：CLI `python -m xkx.cli` 闭环已打通

## Done

> 当前阶段（M3）已完成条目。更早的阶段 -1/0/1/2 见 [归档](docs/progress-archive/)。

- [x] M3 启动前置（[ADR-0031](docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) + [16-M3](docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md)）- 5 Wave 分解 + ADR 编号映射 + 8-12 周预估
- [x] M3-2 CPK 格式化 + StdLib CPK 骨架（[ADR-0031](docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) Wave 1）- CpkManifest + ThemeRegistry 静态加载 + 5 微场景重整 StdLib CPK - 1628 tests
- [x] M3-1 拜师机制（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) 决策 1，子任务 1）- FamilyComp + bai/kneel/recruit/betrayer + ApprenticeDef 声明式配置 - 1651 tests
- [x] M3-1 练功机制（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) 决策 2，子任务 2）- improve_skill + learn/practice/dazuo/tuna/enable + busy condition（EffectComp）- 1680 tests
- [x] M3-1 任务链扩展（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) 决策 3，子任务 3）- 多步 chain + fight 命令 + time-gate 可重复 + kill_npc/reach_room/fight_win - 1692 tests
- [x] M3-1 内容生产子集（[ADR-0036](docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)，子任务 4）- 火山方舟 LLM 客户端 + 生成管线 + SkillData CPK 加载 + kill criteria 5 前 2 轮数据（37.0% / 56.9%）- 1724 tests
- [x] M3-1 子任务 5 可玩 demo 整合（[ADR-0037](docs/adr/ADR-0037-m3-1-subtask5-playtest-demo-integration.md)）- CLI 接 Engine 自动推进 + 消息缓冲 + 死亡轮回 die() + ConditionSystem 跳过 death_stage - 1733 tests
- [x] M3-1 子任务 4 完整内容扩展（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) / [ADR-0036](docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)）- 3 师傅 + 8 武学 + 3 任务链 + ~12 房间 + 测试 bug 修复收尾 - 1744 tests

## 已知技术债（后置，不阻塞阶段 0）

- **CLI 命令解析缺陷**：`cli.py` 用 `line.strip().split()` 解析，NPC/物品名含空格时拆错（如"小 喇嘛"）。需改用引号感知的 tokenizer 或 LPC 风格的 `parse_command`（阶段 0 命令管线 8 段中间件时一并处理）
- **`drop` 命令未实现**：`commands.py` 有 take/give 无 drop。阶段 0 物品系统规格提取时补全
- **xlama2 交互闭环未完成**（S4e GAP）：ask_tea 的 set_flag 茶 + accept_object 酥油的 clear_flag + 物品生成需 ask->action 机制 / clear_flag action / 物品系统（阶段 0）
- **门状态机运行时未实装**（S3 GAP）：do_knock / call_out 定时关 / 跨房间 exits 同步（阶段 0）
- **LPC 规格提取跳过部分**：本次 9 层覆盖核心循环约 7000 行，跳过 condition 具体类型 / 第二梯队守护进程 / 后置系统 / kungfu+d/ 内容。补充计划见 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md)（3 类分阶段补充，"实现到时才补"原则，不提前批量提取）
- **kneel/拜师 message PronounContext 渲染未接入**（M3-1 子任务 1 GAP，子任务 5 闭环暴露）：gongcang kneel message 含 `$N`/`$n` 占位符，[kneel 命令](engine/src/xkx/runtime/commands.py)直接返回原文未过 `PronounService.render`（bai `success_message` 无占位符不受影响）。功能正确（剃度设 `class=lama` + 清 pending），占位符渲染体验打磨后置（需 PronounContext speaker=玩家/viewer=玩家/target=师傅 集成）。

## In Progress

**M3-1 门派核心循环**（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) / [16-M3](docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) Wave 2 主线）。子任务 1-5 + 子任务 4 内容扩展 + kill criteria 5 前 2 轮数据全部落地（1744 tests 全绿）。

**当前子任务**：kill criteria 5 第 3 轮。累积 2 轮数据：第 1 轮 37.0%（<40% 走弱线）、第 2 轮 56.9%（>40% 走弱线）。

**卡点/下一步动作**：第 3 轮需改进 prompt（强调 id 规范 `xueshan/npc/xxx` + quest 结构 trigger/objectives + exits 引用规范 + 单行文本）再跑看 ratio 是否 <40%。主要错误是 LLM 不遵守 id 规范（giver/exit 用 name/缺前缀）+ quest 结构化生成弱点，**非 DSL 表达力不足**，改进 prompt 优先。若仍 >40%，按 kill criteria 5 裁决"先扩 DSL 层1-2 表达力"或"quests 改人工 LLM 仅生成 NPC/skill/room"。

**可穿插推进**（非 M3 前置）：
- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）-- 为工时承诺提供数据支撑
- golden trace 定点辅助（driver PID 22753 运行中）-- do_attack 七步基线已录制，M3 可扩展更多场景

## Blocked

**当前无阻塞项。**

driver UE 问题已于 2026-07-11 解除（用户重启电脑，PID 22753 监听 8888）。[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md) 记录的风险仍有效：未来 kill -9 driver 可能再触发 UE，建议 SIGTERM 优雅退出。golden trace 定位为辅助验证手段（ADR-0009），不阻塞主线。

## Next Up

**kill criteria 5 第 3 轮后的分支**：
- 若 ratio <40%（3 轮累积达标）：M3-1 Wave 2 收尾，进 Wave 3
- 若仍 >40%：裁决方向（扩 DSL 层1-2 表达力 / quests 改人工 LLM 仅生成 NPC/skill/room）

**M3 剩余里程碑**（[16-M3](docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md)）：
- Wave 3：M3-3 内容审核 pipeline MVP + M3-4 版权清洗（金庸衍生 71 文件，并行）
- Wave 4：M3-5 全仿真确定性评估收官（M3 后评估）

**规格补充建议**（任务 7 盘点产出，按 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md) "实现到时才补"原则）：
- 层 H 第二梯队：CHANNEL_D chblk 检查 / fingerd.c get_killer() / rankd.c PKS 称号
- 层 C：vote 命令规格
- 层 I：human.c 属性计算公式（武林大会用）
- 层 F：阴间世界流程规格（黑白无常剧情/还阳路径/gate.c 物品销毁）

S2-S4f 简化项按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md)~[ADR-0008](docs/adr/ADR-0008-schema-validator-four-checks.md) 表在 S4+ 或阶段 0 补全。

## kill criteria 状态（开工必读）

**阶段 -1**（已完成，全通过）：
- DSL+Agent 创作闭环验证 ✅
- 非武侠微场景验证 CombatKernel 主题无关性 ✅

**阶段 0**（已完成，全通过）：
- 性能 micro-benchmark 达标 ✅（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md)，1000+100 后置阶段 1）
- 30 文件表达力校准层3 <15% ✅（[ADR-0015](docs/adr/ADR-0015-layer-calibration-methodology.md)，修正 KPI 6.4%）

**阶段 1**（已完成，全通过）：
- 1000+100 集成测试达标 ✅（[14 压测报告](docs/xkx-arch/14-T10-压测报告.md)，tick p99 12.6ms < 100ms，kill criteria 3 GO）

**阶段 2**（已完成，全通过）：
- Combat 迁移行为等价验证 ✅（2.4 golden trace diff 三层全 PASS + ConformanceChecker 8 项全通过）
- 门派内容包边界干净切割 ✅（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)，test_theme_neutrality 收官硬门禁全通过，核心引擎无武侠烙印，kill criteria 2 GO）

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- **Done 维护规范**：单条 ≤2 行（一行摘要 + 关键产出名词 + ADR 链接 + tests 数），子任务细节进 ADR 不在 PROGRESS 重复。每开新阶段，把当前 Done 整体归档到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`，主文件 Done 从空开始。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`cd engine && .venv/bin/python -m pytest`（venv 在 `engine/.venv`；系统 Python 受 PEP 668 限制需 venv）；lint：`cd engine && .venv/bin/ruff check src tests`。
