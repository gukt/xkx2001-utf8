# 战略复审文档集

> 本文档集是对侠客行 LPC MUD 现代化重构项目的综合战略复审，由 5 视角两轮红队对抗产出 + 完整性批判交叉验证综合裁决而成。
>
> 产出日期：2026-07-16 ｜ 当前分支：feat/sampling-pilot ｜ 当前阶段：阶段 2 按规格实现子系统（M3 已归档，实质性迁移期）

---

## 一、复审背景

项目核心假设是"用 DSL+Agent 让非程序员创作可玩世界"，以经典 LPC MUD（8412 文件、6414 房间、21 门派）为规格源，greenfield Python 重写并做行为等价验证。当前 [M3（单题材武侠可玩 demo）已通过归档](docs/progress-archive/stage-m3-done.md)（2026-07-14），进入阶段 2 实质性迁移期。

推进方式经历史调整：用户曾用工时估算推进（[ADR-0048](docs/adr/ADR-0048-workload-estimation-by-call-point-enumeration.md)），后放弃改 AI agent 按架构依赖分批迁移（[ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)）。当前已迁移碎片：bboard 子系统、job_data 子系统、门派武器 149 条数据层 CPK、wield/unwield/wear 命令批。

5 个视角分别从不同维度审视项目，各经两轮红队对抗质证。综合裁决在此基础上叠加完整性批判（7 个缺席维度、5 个被遮蔽的跨视角分歧、9 条未验证主张），并直接深读 5 视角均未读取的关键文件核实后产出。

---

## 二、用户 5 个元问题如何映射到文档

| 元问题 | 对应文档 | 核心结论摘要 |
|---|---|---|
| 还差多远？ | [01-进度与剩余规模.md](docs/strategy-review/01-进度与剩余规模.md) | 引擎骨架已完成（runtime 14602 行，2416 tests），但 6414 房间 0 实质迁移、472 阵法/技能脚本未启动；全量迁移无里程碑/无活跃止损线（置信度 high） |
| 是否偏离架构基线？发现更好想法怎么安全介入？ | [02-架构偏离与纠偏机制.md](docs/strategy-review/02-架构偏离与纠偏机制.md) | 六条收缩硬边界无回潮，但 04 基线文档存在 4 处与实现/裁决不同步；AI 迁移偏离方向不可预测（N=2 方向相反），守门有效但被动（置信度 medium-high） |
| 复刻是否抓到核心？取舍怎么做？ | [03-复刻意义与取舍战略.md](docs/strategy-review/03-复刻意义与取舍战略.md) | 引擎行为保真抓到了核心（七步管线/themed 治理/combat 确定性），但存在保真分层缺失导致"铁律被 stub、可改编内容被当铁律完整复刻且验证绕过"的优先级倒置（置信度 high） |
| 推进方式是否仍适配？ | 01 + 02 | ADR-0056 分批迁移适配当前阶段，但缺 AI 成本记录回路 + 缺全量迁移里程碑 + 缺活跃止损线，三重治理盲区需补齐（置信度 high） |
| 基线该不该修订？ | [04-对抗评审记录与综合裁决.md](docs/strategy-review/04-对抗评审记录与综合裁决.md) | 应修订：9 条提案，其中 3 条 Impact:High（保真分层 ADR / 全量迁移路径分解 / 运行时验证扩展评估），需用户复审拍板（置信度 medium-high） |

---

## 三、如何使用本复审

1. **先读本文档**了解全局映射与提案总览。
2. **决策优先级**：关注 [04](docs/strategy-review/04-对抗评审记录与综合裁决.md) 的基线修订提案清单，每条标 Impact/Effort/Risk。
3. **落地行动**：[01](docs/strategy-review/01-进度与剩余规模.md) 的"必做/可砍分级"和 [02](docs/strategy-review/02-架构偏离与纠偏机制.md) 的"架构偏离检测检查点"可直接操作。
4. **保真决策**：[03](docs/strategy-review/03-复刻意义与取舍战略.md) 的"保真度分级表"是 grind 是否调整、哪些内容可改编的决策锚点。
5. **每条结论标置信度**（high/medium/low），提案标 Impact/Effort/Risk。

---

## 四、基线修订提案总览

以下 9 条提案需用户复审拍板，详细论证见 [04](docs/strategy-review/04-对抗评审记录与综合裁决.md) §四。

| # | 提案 | target_doc | Impact | Effort | Risk | 置信度 |
|---|---|---|---|---|---|---|
| 1 | 同步 04 基线文档（工时验收/检查点 7/kill criteria 7/driver 可运行性 4 处不同步） | 04-迁移路径与避坑清单.md | High | Low | Low | high |
| 2 | 写保真分层 ADR（机制铁律 vs 内容可改编，裁决 grind 归属） | 新 ADR | High | Medium | Medium | medium-high |
| 3 | 核查并归档性能验证实际状态（test_benchmark + test_load_test） | PROGRESS.md | High | Low | Low | high |
| 4 | 定义全量内容迁移里程碑与路径分解（M3 后 gate 前置条件） | 04 / PROGRESS.md | High | Medium | Low | high |
| 5 | 修正 rng 收口口径漂移（rng.py "18 处" → 精确口径） | rng.py / 04 | Medium | Low | Low | high |
| 6 | 评估 receive_damage 即时性保真缺口（golden trace 前置） | 新 ADR 或 ADR-0023 补充 | High | Medium | Medium | high |
| 7 | 建立留 M3 技术债统一台账 | 新文档 | Medium | Low | Low | medium-high |
| 8 | 恢复边跑边记 AI 成本执行回路（ADR-0056 决策 5 断档） | PROGRESS.md / 工具 | Medium | Low | Low | high |
| 9 | 评估运行时验证扩展（扩大 golden trace 覆盖面） | 新 ADR 或 04 补充 | High | High | High | medium |

---

## 五、专家团与对抗过程说明

### 5 个视角

| 视角 | 审查焦点 | 修订主张数 | 红队两轮后存活/削弱/驳回 |
|---|---|---|---|
| 架构守护 (architecture) | 收缩约束/不变量/偏离/过渡层 | 16 | 存活 9 / 削弱 6 / 驳回 1 |
| 游戏设计与复刻意义 (game-design) | 灵魂/糟粕/grind/好玩度验证/自参照 | 12 | 存活 7 / 削弱 4 / 驳回 1 |
| 进度与剩余规模 (progress) | 剩余规模/推进方式/golden trace/口径漂移 | 12 | 存活 9 / 削弱 3 / 驳回 0 |
| 纠偏与实时介入机制 (process) | 决策阈值/微观决策模式/止损/spike | 8 | 存活 3 / 削弱 5 / 驳回 0 |
| LPC 保真与取舍边界 (lpc-fidelity) | receive_damage/rng 收口/保真分层/文档漂移 | 16 | 存活 12 / 削弱 4 / 驳回 0 |

### 对抗过程

每个视角经"修订主张 → 红队第 1 轮质证（survives/weakened/refuted）→ 修订 → 红队第 2 轮质证"两轮。综合裁决在此基础上叠加：

- **完整性批判**：识别 5 个被遮蔽的跨视角分歧（如 architecture 称"不变量已落地"与 lpc-fidelity 揭示"字面落地但语义有缺口"）、7 个完全缺席的维度（性能验证/安全模型/测试质量审计/产品愿景验证/存档一致性/铁律挑战/golden trace 扩展）。
- **直接取证**：综合裁决深读了 5 视角均未读取的 9 个关键文件（[test_benchmark.py](engine/tests/test_benchmark.py)、[test_load_test.py](engine/tests/test_load_test.py)、golden trace baseline 6 文件、[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md)、[ADR-0038](docs/adr/ADR-0038-kill-criteria-5-round4-rooms-known-ids-quests-manual.md)、[governance.py](engine/src/xkx/runtime/governance.py)、[layer_e_combat.py](engine/src/xkx/spec/layer_e_combat.py)、[death.py](engine/src/xkx/runtime/death.py) 实现段、[resolve_attack.py](engine/src/xkx/combat/resolve_attack.py) wound/damage 段），纠正了 3 处事实错误（prog-c10 kill criteria 5 轮次、prog-c5 golden trace 覆盖面、combatd.c random 口径）。

### 关键纠错记录

1. **prog-c10 事实错误**：称"kill criteria 5 仅 1 轮数据点距 3 轮阈值仍有 2 轮缺口"。实测 [ADR-0038](docs/adr/ADR-0038-kill-criteria-5-round4-rooms-known-ids-quests-manual.md) 决策 3 明确累积 4 轮（37.0%/56.9%/44.6%/30.3%），第 4 轮 30.3% < 40% 已判定通过。
2. **prog-c5 不准确**：称"golden trace 仅 combat 14 回合一个场景，对非 combat 路径完全无运行时验证"。实测 [baseline/meta.json](engine/tools/golden_trace/baseline/meta.json) + [login_session.txt](engine/tools/golden_trace/baseline/login_session.txt)（21 条目完整登录会话）= 非 combat 路径运行时验证存在。
3. **wound 简化确认**：[resolve_attack.py](engine/src/xkx/combat/resolve_attack.py) L229 `rng.chance(4)` 是固定 1/4 概率，而 [golden trace](engine/tools/golden_trace/baseline/meta.json) lpc_formula_map 显示 LPC wound 有 4 种概率（空手 kill 1/4、武器 kill 1/2、空手非 kill 1/7、武器非 kill 1/4）。
