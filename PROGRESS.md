# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-14

## 当前状态速览

- **阶段**：M3 收官后技术债补缺口第 2 轮完成（C4/B-2/C5 全部落地）
- **分支**：feat/stage-3-m3
- **tests**：1782 全绿，ruff 全过
- **关键 ADR**：[ADR-0040](docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md)（层1 ask/clear_flag/spawn_items）/ [ADR-0041](docs/adr/ADR-0041-auto-fight-aggressive-wiring.md)（auto_fight aggressive 接入）/ [ADR-0042](docs/adr/ADR-0042-door-state-machine.md)（门状态机）/ [ADR-0039](docs/adr/ADR-0039-combat-path-unification.md)（战斗路径统一）
- **下一步**：M3->后置决策检查点（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md) 三问：单进程容量 80% / 外部玩家测试触发 PG / 第二题材）；B-2 hatred/vendetta/berserk + C5 open/close/锁 + C4 drink 残留后置
- **工具链**：仓库根新增 [justfile](justfile) task runner（24 recipe 自带 `cd engine && uv run`，agent 在仓库根 `just <recipe>` 即可，`just --list` 自举）；CLAUDE.md/本文件命令行已同步改 `uv run`。ruff format 有 85 文件历史漂移，可单独 `just format` 全量格式化。
- **可玩 demo**：CLI `python -m xkx.cli` 闭环（xlama2 交互 + aggressive NPC + 门）+ `python -m xkx.content_review` 审核 pipeline

## Done

> 当前阶段（M3）滚动窗口（Wave 2 收尾 + Wave 3 + Wave 4 收官）。M3 Wave 1/2 早期子任务见 [stage-m3-done.md](docs/progress-archive/stage-m3-done.md)；阶段 -1/0/1/2 见 [归档](docs/progress-archive/)。

- [x] M3-1 子任务 4 完整内容扩展（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) / [ADR-0036](docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)）- 3 师傅 + 8 武学 + 3 任务链 + ~12 房间 + 测试 bug 修复收尾 - 1744 tests
- [x] kill criteria 5 达标（第 4 轮 semantic_ratio 30.3% < 40% 走弱线）- 方向 A：rooms 注入 known ids（20 房间+11 NPC）消除幻觉引用 + quests 改人工；第 3 轮 prompt 强化 4 点使结构错误 70->0；累积 4 轮 37.0%/56.9%/44.6%/30.3% - 1744 tests
- [x] M3-3 内容审核 pipeline MVP（[ADR-0033](docs/adr/ADR-0033-content-review-pipeline-mvp.md)）- content_review 模块（4 类词表 + 递归扫描 + license 校验 + 状态推导 + `_review.json` + checklist MVP）+ CpkManifest review_status 字段；雪山派 4 金庸角色命中验证 - 1768 tests
- [x] M3-5 全仿真确定性评估收官（[ADR-0035](docs/adr/ADR-0035-full-simulation-determinism-decision-point.md)）- **否决全仿真实施，保持 combat-only**；实测 tick 驱动 System 几乎无 random（HealSystem/ConditionSystem/GovernanceSystem/auto_fight 全无），范围外随机源仅 command 路径 5 文件 8 处一次性随机（角色创建/死亡/练功/称谓）；扩展成本主要是全量快照 + dissent 7 审计统一 + PYTHONHASHSEED 全局化（架构税高），收益边际递减；专家 2 承重论断 2 仍成立；保留逐 System 按需纳入演进路径 - 1768 tests
- [x] M3 收官后技术债补缺口（[ADR-0039](docs/adr/ADR-0039-combat-path-unification.md)）- E 3 处过时注释（impl_map riposte / combat system 接入 / 全仿真确定性引用 ADR-0035）+ B 战斗路径统一（kill/fight 命令建立 CombatState + advance_combat 只调 CombatBridge 驱动，启用 ADR-0023 确定性重放，is_fighting 正确，flee 中断；对齐 LPC heart_beat）+ C1 CLI shlex 引号 tokenizer + C2 drop 命令 + C6 kneel message PronounContext 渲染 - 1771 tests
- [x] 技术债补缺口第 2 轮（[ADR-0040](docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md) / [ADR-0041](docs/adr/ADR-0041-auto-fight-aggressive-wiring.md) / [ADR-0042](docs/adr/ADR-0042-door-state-machine.md)）- C4 xlama2 交互闭环（ask set_flag + give clear_flag + spawn_items 物品生成）+ B-2 auto_fight 接入（MVP aggressive 触发 + go room-enter + CombatBridge 驱动）+ C5 门状态机（标准 doors + knock + call_out 定时关 + 双向同步 + DoorSystem）- 1782 tests

## 已知技术债（后置，不阻塞阶段 0）

- **C4 残留后置**：buttertea drink 效果（无 drink 命令）/ 厨房 valid_leave 持茶挡路 / 厨房初始 buttertea -- 后置
- **B-2 残留后置**（[ADR-0041](docs/adr/ADR-0041-auto-fight-aggressive-wiring.md)）：hatred（killer 数据结构）/ vendetta（门派世仇）/ berserk（look 触发）/ 多对手 select_opponent -- 后置
- **C5 残留后置**（[ADR-0042](docs/adr/ADR-0042-door-state-machine.md)）：LOCKED/SMASHED 位 / open/close 命令 / 锁钥匙系统 / 动态 exit 模式 -- 后置
- **LPC 规格提取跳过部分**：本次 9 层覆盖核心循环约 7000 行，跳过 condition 具体类型 / 第二梯队守护进程 / 后置系统 / kungfu+d/ 内容。补充计划见 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md)（3 类分阶段补充，"实现到时才补"原则，不提前批量提取）
- **M3-4 版权清洗后置**（用户决策 2026-07-14，未商业化阶段过早清洗是过度工程）：雪山派 CPK 含 4 金庸角色（金轮法王/鸠摩智/灵智上人/达尔巴）+ 雪山派门派名本身（[ADR-0033](docs/adr/ADR-0033-content-review-pipeline-mvp.md) 关键发现）。M3-3 预检标记 `needs_review` 待办，商业化前清洗时预检就位。全量改编化/标注/授权 + provenance 版权链回填后置门3。

## In Progress

**M3 收官后技术债补缺口（第 2 轮）完成**（[ADR-0040](docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md) / [ADR-0041](docs/adr/ADR-0041-auto-fight-aggressive-wiring.md) / [ADR-0042](docs/adr/ADR-0042-door-state-machine.md)）。C4 xlama2 交互闭环（ask set_flag + give clear_flag + spawn_items）+ B-2 auto_fight 接入（MVP aggressive，go room-enter + handler 注册 + CombatBridge 驱动）+ C5 门状态机（标准 doors + knock + call_out 定时关 + 双向同步 + DoorSystem）全部落地。1782 tests 全绿。技术债补缺口（第 1 轮 E/B/C1/C2/C6 + 第 2 轮 C4/B-2/C5）全部完成。

**M3->后置决策检查点待用户裁决**（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md) 三问）：单进程容量是否实测达 80% / 是否需要外部玩家测试（触发 PG 迁移，kill criteria 8）/ 第二题材是否真实存在（触发热插拔评估）。M3 内部 demo 已达成，下一步方向需用户决策。

**可穿插推进**（非主线前置，待主线方向确认后启动）：

- 任务 6：抽样校准实验（68771 调用点抽 50-100 个实测工时）-- 为全量迁移工时承诺提供数据支撑
- golden trace 定点辅助（driver PID 22753 运行中）-- do_attack 七步基线已录制，可扩展更多场景

## Blocked

**当前无阻塞项。**

driver UE 问题已于 2026-07-11 解除（用户重启电脑，PID 22753 监听 8888）。[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md) 记录的风险仍有效：未来 kill -9 driver 可能再触发 UE，建议 SIGTERM 优雅退出。golden trace 定位为辅助验证手段（ADR-0009），不阻塞主线。

## Next Up

**M3 收官 -> 后置阶段**（M3 5 任务全部裁决完毕：M3-1/2/3/5 完成，M3-4 后置）：

- **M3->后置决策检查点**（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md)，待用户裁决下一步方向）：
  - 单进程容量是否实测达 80%（触发分布式评估）
  - 是否需要外部玩家测试（触发 PG 迁移，kill criteria 8 硬止损线）
  - 第二题材是否真实存在（触发热插拔评估）
- **全仿真确定性**：M3-5 已决策否决实施（[ADR-0035](docs/adr/ADR-0035-full-simulation-determinism-decision-point.md)），保持 combat-only，触发条件后置（分布式回放 / 反作弊强需求 / 观战产品需求）

**规格补充建议**：层 H 第二梯队（CHANNEL_D/fingerd/rankd PKS）/ 层 C（vote）/ 层 I（human.c 属性公式）/ 层 F（阴间流程）-- 按 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md) "实现到时才补"。S2-S4f 简化项按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md)~[ADR-0008](docs/adr/ADR-0008-schema-validator-four-checks.md) 在 S4+ 补全。

## kill criteria 状态（开工必读）

**阶段 -1 / 0 / 1 / 2**（全通过）：DSL+Agent 闭环 / 非武侠微场景 / micro-benchmark（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md)）/ 表达力校准 6.4%（[ADR-0015](docs/adr/ADR-0015-layer-calibration-methodology.md)）/ 1000+100 tick p99 12.6ms（[14 压测报告](docs/xkx-arch/14-T10-压测报告.md)）/ Combat 行为等价（golden trace + ConformanceChecker 8 项）/ 门派边界 test_theme_neutrality（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)）。

**M3**（完成；M3-1/M3-2/M3-3/M3-5 完成，M3-4 版权清洗后置）：

- kill criteria 5 Agent 修订量 ✅（第 4 轮 semantic_ratio 30.3% < 40%；方向 A：rooms 注入 known ids + quests 改人工；结构错误 70->0）
- kill criteria 7 项目级 18 个月未达 M3 ✅（M3 可玩 demo 已达成，2026-07-14 收官）
- M3-5 全仿真确定性决策点 ✅（[ADR-0035](docs/adr/ADR-0035-full-simulation-determinism-decision-point.md) 否决实施，保持 combat-only）

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三/§四。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR。每开新阶段归档 Done 到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`。
- 偏离 00-04 基线写 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent。
- 跑测试：`just test`（或 `cd engine && uv run pytest`）；lint：`just lint`（或 `cd engine && uv run ruff check src tests`）。统一用 `uv run`（.venv 未装 dev 依赖，裸 pytest/ruff 不可用）。全部命令见仓库根 [justfile](justfile)，`just --list` 自举。
