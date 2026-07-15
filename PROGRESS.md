# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-15

## 当前状态速览

- **阶段**：M3 收官后产品化收尾窗口（demo 打磨 9 项完成）
- **分支**：feat/stage-3-techdebt-r3
- **tests**：1814 全绿，ruff 全过
- **关键 ADR**：[ADR-0043](docs/adr/ADR-0043-drink-command-initial-items-tea-block.md)（drink+初始物品+持茶挡路）/ [ADR-0044](docs/adr/ADR-0044-door-open-close-locked.md)（门 open/close+LOCKED）/ [ADR-0045](docs/adr/ADR-0045-hatred-vendetta-triggers.md)（hatred+vendetta）/ [ADR-0040](docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md)~[ADR-0042](docs/adr/ADR-0042-door-state-machine.md)（第 2 轮）/ [ADR-0047](docs/adr/ADR-0047-greenfield-effort-semantics.md)（抽样校准 greenfield 工时语义）/ [ADR-0048](docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)（阶段 B 方案修正：降级区间承诺）/ [ADR-0049](docs/adr/ADR-0049-multi-opponent-select-and-key-system.md)（多对手+钥匙系统，B-2/C5 收尾）/ [ADR-0050](docs/adr/ADR-0050-du-command-and-schema-extension.md)（du 研读命令+ItemDef/QuestReward schema 扩展，demo 打磨）/ [ADR-0051](docs/adr/ADR-0051-berserk-semantic-flavor-only.md)（berserk 语义裁决=忠实 LPC flavor）/ [ADR-0052](docs/adr/ADR-0052-c5-residual-smashed-skip-dynamic-exit-postpone.md)（C5 残留裁决：SMASHED 跳过+动态 exit 后置交通系统）
- **下一步**：M3->后置决策检查点（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md) 三问，用户已选产品化收尾窗口方向）；demo 打磨 9 项完成（A1/B1/B2/B3/B5/C1/C2/C3/B4）；抽样校准 pilot 实测待启动（[ADR-0048](docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)，人工工时红线，被测环节留人工）；berserk 语义已裁决=忠实 LPC flavor（[ADR-0051](docs/adr/ADR-0051-berserk-semantic-flavor-only.md)，look 邪派 NPC flavor 不战斗）
- **工具链**：仓库根新增 [justfile](justfile) task runner（24 recipe 自带 `cd engine && uv run`，agent 在仓库根 `just <recipe>` 即可，`just --list` 自举）；CLAUDE.md/本文件命令行已同步改 `uv run`。ruff format 有 85 文件历史漂移，可单独 `just format` 全量格式化。
- **可玩 demo**：CLI `python -m xkx.cli` 闭环（起始 dshanlu 免卡门 + 供奉/拜师/kneel/learn/du 研读经书链 + drink 闭环 + aggressive/hatred/vendetta NPC + open/close/knock/unlock 门 + 钥匙开锁 + 藏经阁取经 + 密室雪莲丹 + kill 野狼 quest；战斗逐条节奏 + 死亡还阳）+ `python -m xkx.content_review` 审核 pipeline

## Done

> 当前阶段（M3）滚动窗口（Wave 2 收尾 + Wave 3 + Wave 4 收官）。M3 Wave 1/2 早期子任务见 [stage-m3-done.md](docs/progress-archive/stage-m3-done.md)；阶段 -1/0/1/2 见 [归档](docs/progress-archive/)。

- [x] M3-1 子任务 4 完整内容扩展（[ADR-0032](docs/adr/ADR-0032-family-core-loop-design.md) / [ADR-0036](docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)）- 3 师傅 + 8 武学 + 3 任务链 + ~12 房间 + 测试 bug 修复收尾 - 1744 tests
- [x] kill criteria 5 达标（第 4 轮 semantic_ratio 30.3% < 40% 走弱线）- 方向 A：rooms 注入 known ids（20 房间+11 NPC）消除幻觉引用 + quests 改人工；第 3 轮 prompt 强化 4 点使结构错误 70->0；累积 4 轮 37.0%/56.9%/44.6%/30.3% - 1744 tests
- [x] M3-3 内容审核 pipeline MVP（[ADR-0033](docs/adr/ADR-0033-content-review-pipeline-mvp.md)）- content_review 模块（4 类词表 + 递归扫描 + license 校验 + 状态推导 + `_review.json` + checklist MVP）+ CpkManifest review_status 字段；雪山派 4 金庸角色命中验证 - 1768 tests
- [x] M3-5 全仿真确定性评估收官（[ADR-0035](docs/adr/ADR-0035-full-simulation-determinism-decision-point.md)）- **否决全仿真实施，保持 combat-only**；实测 tick 驱动 System 几乎无 random（HealSystem/ConditionSystem/GovernanceSystem/auto_fight 全无），范围外随机源仅 command 路径 5 文件 8 处一次性随机（角色创建/死亡/练功/称谓）；扩展成本主要是全量快照 + dissent 7 审计统一 + PYTHONHASHSEED 全局化（架构税高），收益边际递减；专家 2 承重论断 2 仍成立；保留逐 System 按需纳入演进路径 - 1768 tests
- [x] M3 收官后技术债补缺口（[ADR-0039](docs/adr/ADR-0039-combat-path-unification.md)）- E 3 处过时注释（impl_map riposte / combat system 接入 / 全仿真确定性引用 ADR-0035）+ B 战斗路径统一（kill/fight 命令建立 CombatState + advance_combat 只调 CombatBridge 驱动，启用 ADR-0023 确定性重放，is_fighting 正确，flee 中断；对齐 LPC heart_beat）+ C1 CLI shlex 引号 tokenizer + C2 drop 命令 + C6 kneel message PronounContext 渲染 - 1771 tests
- [x] 技术债补缺口第 2 轮（[ADR-0040](docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md) / [ADR-0041](docs/adr/ADR-0041-auto-fight-aggressive-wiring.md) / [ADR-0042](docs/adr/ADR-0042-door-state-machine.md)）- C4 xlama2 交互闭环（ask set_flag + give clear_flag + spawn_items 物品生成）+ B-2 auto_fight 接入（MVP aggressive 触发 + go room-enter + CombatBridge 驱动）+ C5 门状态机（标准 doors + knock + call_out 定时关 + 双向同步 + DoorSystem）- 1782 tests
- [x] 技术债补缺口第 3 轮（[ADR-0043](docs/adr/ADR-0043-drink-command-initial-items-tea-block.md) / [ADR-0044](docs/adr/ADR-0044-door-open-close-locked.md) / [ADR-0045](docs/adr/ADR-0045-hatred-vendetta-triggers.md)）- C4 drink 命令+厨房初始物品+持茶挡路闭环 + C5 open/close 命令+LOCKED 位 + B-2 hatred(killer_ids 重入重触)+vendetta(标记式追杀，非门派世仇) - 1795 tests
- [x] CLI 试玩三 bug 修复（合并 worktree-fix-combat-death-respawn）- 战斗节奏（`_print_paced` 接入 kill/fight + 死亡对话逐条停顿）/ 死亡还阳 `KeyError: city/wumiao`（rooms.yaml 内置 death/gate+city/wumiao + commands.py 4 处 `room_entities[...]` 改 `.get()` 防御）/ demo 潜能（`load_game` 给 potential=100+force=30 测通 learn 链；help 澄清 `practice <技能种类>`）+4 回归测试 - 1799 tests
- [x] 抽样校准实验阶段 A（[ADR-0046](docs/adr/ADR-0046-sampling-calibration-methodology.md)）- 59270 调用点枚举（对账粗略 68771）+ 分布（dbase 56%/d+kungfu 82%）+ 抽样方案 80 样本 + 迁移单位建议（函数级）- 1799 tests
- [x] 抽样校准实验阶段 B 设计定稿（[ADR-0047](docs/adr/ADR-0047-greenfield-effort-semantics.md)）- 函数级分布（7991 函数）+ greenfield 工时语义（已实现 82.4%/待迁移 17.6%=10422 调用点/1159 函数）+ 修正抽样面 + 80 样本候选清单 + 实测方法论定稿 - 1799 tests
- [x] 抽样校准阶段 B 方案修正（[ADR-0048](docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)）- 评审团 4 方案+3 评委三方收敛：80 样本窄 CI 降级为 pilot 13+类比基准区间承诺（14-20h 省 75-85%）+误分类定量纠偏+回归按需后置+LLM 否决（工时语义污染）；pilot 脚手架+manifest 就绪 - 1799 tests
- [x] 技术债补缺口第 4 轮（[ADR-0049](docs/adr/ADR-0049-multi-opponent-select-and-key-system.md)）- B-2 多对手 select_opponent（修正每 tick 全打 bug，combat seed+combat_selects 跨层）+ C5 钥匙系统（key_id+unlock+铁钥匙场景）；berserk/动态 exit/SMASHED 仍后置 - 1807 tests
- [x] Demo 打磨（产品化收尾窗口，9 项）- A1 fight 提示引号 + B1 起始 dshanlu+卡门引导 + B5 quest 只列进行中 + B2 NPC 中文短 alias + B3 combat_exp 便利+learn 引导 + C3 du 研读（对照 LPC lx-jing.c，ItemDef read_skill）+ C1 藏经阁般若经+取经 quest + C2 密室雪莲丹+drink qi（ItemDef qi_recover）+ B4 kill 野狼 quest（QuestReward potential）- 1812 tests
- [x] berserk 语义裁决=忠实 LPC flavor（[ADR-0051](docs/adr/ADR-0051-berserk-semantic-flavor-only.md)）- `look <target>` NPC 详情 + 邪派 NPC（金轮法王 shen-300）被看输出"瞪眼+扫视"flavor 不战斗（忠实 !userp 早退）；NpcDef.shen 字段 - 1814 tests
- [x] C5 残留裁决关闭（[ADR-0052](docs/adr/ADR-0052-c5-residual-smashed-skip-dynamic-exit-postpone.md)）- SMASHED 全仓库死代码跳过 + 动态 exit 后置交通系统（真实需求=FERRY/SHIP 渡船海船，当前 greenfield 无交通场景，全量迁移场景驱动连带实施；修正 ADR-0049 理由）- 1814 tests

## 已知技术债（后置，不阻塞阶段 0）

- **B-2 残留后置**（[ADR-0045](docs/adr/ADR-0045-hatred-vendetta-triggers.md)）：多对手 select_opponent 已实施（[ADR-0049](docs/adr/ADR-0049-multi-opponent-select-and-key-system.md)）/ berserk 已裁决=忠实 LPC flavor（[ADR-0051](docs/adr/ADR-0051-berserk-semantic-flavor-only.md)，look 邪派 NPC flavor 不战斗；NPC 第四触发偏离不采纳）
- **C5 残留已裁决关闭**（[ADR-0052](docs/adr/ADR-0052-c5-residual-smashed-skip-dynamic-exit-postpone.md)）：钥匙系统已实施（[ADR-0049](docs/adr/ADR-0049-multi-opponent-select-and-key-system.md)）/ 动态 exit 后置交通系统（真实需求=FERRY/SHIP，当前 greenfield 无交通场景，全量迁移连带实施）/ SMASHED 跳过（全仓库死代码）
- **LPC 规格提取跳过部分**：本次 9 层覆盖核心循环约 7000 行，跳过 condition 具体类型 / 第二梯队守护进程 / 后置系统 / kungfu+d/ 内容。补充计划见 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md)（3 类分阶段补充，"实现到时才补"原则，不提前批量提取）
- **M3-4 版权清洗后置**（用户决策 2026-07-14，未商业化阶段过早清洗是过度工程）：雪山派 CPK 含 4 金庸角色（金轮法王/鸠摩智/灵智上人/达尔巴）+ 雪山派门派名本身（[ADR-0033](docs/adr/ADR-0033-content-review-pipeline-mvp.md) 关键发现）。M3-3 预检标记 `needs_review` 待办，商业化前清洗时预检就位。全量改编化/标注/授权 + provenance 版权链回填后置门3。

## In Progress

**Demo 打磨（产品化收尾窗口）完成**（9 项，详见 Done）：A1/B1/B2/B3/B5/C1/C2/C3/B4。1812 tests 全绿。方向=用户选产品化收尾窗口（Q2 暂否，聚焦已迁移内容产品化；pilot 被测环节受人工工时红线约束留人工；berserk 已裁决=忠实 LPC flavor [ADR-0051]）。

**M3->后置决策检查点已裁决**（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md) 三问，2026-07-15）：Q1 单进程容量实测 80%--否（合成压测余量 8x，无真实在线）；Q3 第二题材--否（仅武侠）；Q2 外部玩家测试--**暂否**（用户选产品化收尾窗口，不启动 PG 迁移/网络层产品化）。三问均不触发后置阶段，聚焦已迁移内容产品化 + 后置技术债/抽样 pilot 按需推进。

**可穿插推进**（非主线前置，待主线方向确认后启动）：

- 任务 6 抽样校准实验：**阶段 B 方案修正完成**（[ADR-0048](docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)，评审团 4 方案+3 评委三方收敛）。80 样本窄 CI 降级为 pilot 13 样本+类比基准区间承诺（[manifest](engine/tools/sampling/pilot/samples_manifest.json)）。pilot 脚手架（[schema](engine/tools/sampling/pilot/schema.py)/[estimate](engine/tools/sampling/pilot/estimate.py)/stubs）就绪。**pilot 实测待启动**（下 session 从 manifest id=1 xue.c:main 起步，建共享桩+测 1-2 high-tier；被测环节人工工时红线，留人工计时）
- golden trace 定点辅助（driver PID 22753 运行中）-- do_attack 七步基线已录制，扩展绑定 2.4（当前过早）

## Blocked

**当前无阻塞项。**

driver UE 问题已于 2026-07-11 解除（用户重启电脑，PID 22753 监听 8888）。[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md) 记录的风险仍有效：未来 kill -9 driver 可能再触发 UE，建议 SIGTERM 优雅退出。golden trace 定位为辅助验证手段（ADR-0009），不阻塞主线。

## Next Up

**M3 收官 -> 后置阶段**（M3 5 任务全部裁决完毕：M3-1/2/3/5 完成，M3-4 后置；§八 三问 2026-07-15 裁决=产品化收尾窗口）：

- **M3->后置决策检查点已裁决**（[04 §八](docs/xkx-arch/04-迁移路径与避坑清单.md)）：Q1/Q3 否，Q2 暂否（产品化收尾窗口）。后置阶段（分布式/PG 迁移/热插拔）均不触发，待未来条件满足再评估。
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
