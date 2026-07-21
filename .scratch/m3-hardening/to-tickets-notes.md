# M3 停机加固拆票分析笔记（`/to-tickets` 会话记录）

> 本文件记录本次 `/to-tickets` 会话对 [spec.md](spec.md) 的拆分逻辑、依据，以及为解决 spec 里未钉死到可直接拆票程度的实现歧义所做的具体决策。11 张票已发布在 [issues/](issues/) 下（`01`–`11`，编号即依赖顺序）。配套的执行计划见 [implement-plan.md](implement-plan.md)。
>
> **核心目标校准**：spec 开头「范围边界」段已经把这次拆票的边界钉得很死——**Wave P0**（评审 P0-1～P0-9 全 9 项，停机门闩 S0）+ **Wave B3**（评审 P1-2/3/4/6/7，排期非门闩）。这条边界本身就是一条反膨胀护栏：本次加固不是"把评审报告里所有 P1/P2 建议都做掉"，是"把停机门闩关上，再顺手把已经拍板要做的 5 项 B3 排进同一个 effort"。拆票时反复核对的问题始终是"这一项属于 P0-1～9/P1-2/3/4/6/7 里的哪一条，还是属于 spec 明确划掉的 Out of Scope"——凡是后者，即使看起来顺手就能做（比如 `commands.py` 拆分、扬州地标加厚），也不开票，理由在下面「未纳入本次拆票范围」一节逐条对齐 spec 的 Out of Scope。

## 勘察方法

在动手拆票前，完整读了以下材料，确保票据引用的模块/函数/字段名与代码库当前真实状态一致（不是凭 spec 文字脑补）：

- **spec 本身**：[spec.md](spec.md) 全文——Problem Statement、User Stories 全部 34 条（Wave P0 24 条 + Wave B3 10 条）、Implementation Decisions（P0-1～P0-9 + B3-1～B3-5，逐条给了具体文件路径/函数签名/字段名）、Testing Decisions、Out of Scope、Further Notes（三条跨票提醒：P0-4 应在 P0-8/B3-4 之前落地；P0-2 的存档兼容性缺字段回退默认值；P0-5 的 `commands.py` 遗留 attach 调用需要 `/to-tickets` 复核而非直接裁定）。
- **上游决策文档**：[CLAUDE.md](../../CLAUDE.md) 架构不变量第 8 条（推进治理，M3 与 M4 之间插入本次加固窗口）；[评审 Final 报告](../m3-engine-architecture-review/final/m3-engine-architecture-review-report.md) 第 6 节统一 P0/P1/P2 清单；[ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)/[ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)/[ADR-0009](../../docs/adr/0009-single-process-single-world.md)（P0-1/P0-9/B3-1 均已由这三份 ADR 落盘，只需确认引用链没漂移）；[PROGRESS.md](../../PROGRESS.md)「M3 停机加固拍板」「P1 排期拍板」两条 Done 摘要（本 spec 两个 wave 范围的直接拍板来源）。
- **本仓库 `/to-tickets` 惯例 precedent**：[m3-ugc-loop-creation-surface/to-tickets-notes.md](../m3-ugc-loop-creation-surface/to-tickets-notes.md)（票据粒度惯例、"算法层先行、组合层跟进、接口层收口"的拆分手法、"内容票与机制票严格解耦"原则）与其 [implement-plan.md](../m3-ugc-loop-creation-surface/implement-plan.md)（wave/`/code-review` 循环/fixed point tag 的具体格式，本次直接复用同一套结构）；[docs/agents/issue-tracker.md](../../docs/agents/issue-tracker.md)（一票一文件、`.scratch/<effort>/issues/NN-<slug>.md` 命名约定）与 [triage-labels.md](../../docs/agents/triage-labels.md)（`ready-for-agent` 标签映射）。
- **代码库现状（逐文件确认，不是抽样）**：`engine/src/mud_engine/` 下全部 31 个模块的文件清单（确认 `combat.py`/`death_flow.py`/`scene_loader.py`/`entity_gate.py`/`skills.py`/`world.py`/`__main__.py`/`commands.py`/`ai.py` 等 spec 引用的路径全部真实存在，不是 spec 撰写时的笔误或已重命名）；`engine/tests/` 下全部 43 个测试文件清单（确认 `test_entry_guard.py`/`test_scene_shaolin.py`/`test_skill_behavior_hooks.py`/`test_combat_engagement.py`/`test_mount.py`/`test_ferry.py`/`test_load_pack.py`/`test_m3_pack_loop.py`/`test_main_cli.py` 等票据要扩展的既有测试文件全部存在，不需要新建平行测试文件——除非 spec 明确说"新建"，如 07 号票可选的 `test_combat_events_contract.py`）。
- **`.scratch/` 目录现状**：确认 `.scratch/m3-hardening/` 只有 `spec.md`，`issues/` 目录尚未创建；确认 `.scratch/m2-mvp-scene-playable/issues/16-20` 五个文件确实存在（07 号票要刷新的 Status 行目标）。

## 拆分原则

1. **P0-1/P0-9/B3-1 三项不开票，只在 Done 记录里做"确认引用链完整"的核对**——spec Implementation Decisions 对这三项的措辞是"`/to-tickets` 不为此开实现票"，这不是含糊表述，是明确指令。这三项已经通过 ADR-0007/ADR-0008/ADR-0009 完成决策落盘，且 [CLAUDE.md](../../CLAUDE.md) 架构不变量摘要已经引用（本次拆票逐条核对过，没有发现漂移）。如果为它们开票，会制造"9+5 张票才能关闭 Wave P0/B3"这种假象,与 spec 明确的"7 张 P0 实现票 + 4 张 B3 实现票"范围不符。
2. **编号即依赖顺序，阻塞边只在真实存在代码/文档引用依赖时才画**——11 张票里只有 4 条阻塞边（`05→06`、`03→07`、`03→10`、`06→09`），其余 7 张（`01`/`02`/`03`/`04`/`05`/`08`/`11`）互相独立，构成拆票后的 frontier。这条原则背后是刻意抵抗"把所有 P0 票串成一条链"的偷懒做法——spec 的 Implementation Decisions 里每一项都给了具体到文件/函数的实现方案，互相之间除了 Further Notes 明确指出的那三处关联，并没有真实的代码耦合（例如 P0-2 昏迷苏醒改 `death_flow.py`/`components.py`，P0-3 门禁改 `entity_gate.py`/YAML，两者互不touch，没有理由假装它们互相阻塞）。
3. **"消灭全局态"（03 号票）作为一张独立的机制票，前置于 07/10 两张会 touch 同一段调用路径的票**——这是 Further Notes 第一条的直接落地：`resolve_attack`/`SkillBehavior.hit_by`/`post_action` 这条调用路径会被三张票依次touch（03 改签名与去全局态、07 加事件契约测试、10 加 tick 驱动的钩子交叉测试）。如果不定阻塞边，07/10 的实现者可能在 03 号票落地前就基于旧签名写断言，03 号票落地后又要回头改一遍——这正是 vertical-slice 拆票要避免的"同一批代码被两张票分别改两次"。
4. **P0-4（03 号票）与 B3-2（08 号票）虽然都是"结构性重构"，但不套用 expand-contract 宽重构模式，因为blast radius 很小且可控**——03 号票改的是 `SkillBehavior` Protocol 两个方法的签名，调用点集中在 `combat.py`/`skills.py` 两个文件 + 对应测试，不是"改一个跨越几十个文件的共享类型"；08 号票搬 `room_say` 一个函数 + 三个调用点（`commands.py` 一处、`ai.py` 一处、可能的测试 import 若干处），同样是有限的、一次性可完成的迁移。两者都够小,可以在单张票内直接完成"改代码 + 改调用点 + 改测试"的完整闭环，不需要"先加新形式共存、再分批迁移、最后删旧形式"的三段式。
5. **创作者向文档三件套（06/09/11）按"谁引用谁"的自然顺序排阻塞边，不是按"谁先想到"排序**——06 号票（创作者契约 v0）需要引用 05 号票确定的 `--validate`/`--strict` 行为作为"机器可检查侧"，所以 `05→06`；09 号票（双轨范本文档）需要引用 06 号票冻结的 v0 契约作为"双轨共用基础"，所以 `06→09`；11 号票（GAP 台账）虽然 spec 提示"建议补一条反向链接到创作者契约"，但这只是锦上添花的交叉引用，不是内容产出的前提（GAP 台账列的是"表达力缺口"，跟契约文档是否已经写好完全无关），因此不设 `06→11` 阻塞边,只在 11 号票里留一条"若 06 已完成，补链接"的软提示。
6. **战斗事件契约测试（07 号票的第二部分）与票 Status 刷新（07 号票的第一部分）合并成一张票,不拆成两张**——两者都是 spec P0-8 的同一条决策产出,且工作量都很小（前者是改 5 个文件的一行 `Status:`,后者是新增一个测试文件的三个测试用例）,拆成两张票会制造不必要的协调开销（两张票都"无阻塞"，实现顺序完全无所谓，不如合并省一次 `/code-review` 往返）。这与 [m3-ugc-loop-creation-surface 的 05 号票](../m3-ugc-loop-creation-surface/issues/05-e2e-verification-and-docs.md)"端到端证据 + 里程碑收口文档"合并成一张票的先例是同一条原则的再次应用。

## 关键设计决策 / 已解决的歧义

spec Further Notes 里有一处明确留给 `/to-tickets` 阶段核对而非直接裁定的决策，以及几处 spec 文字本身给了"暂定，`/to-tickets` 阶段确定"空间的具体选择，记在这里供 `/implement` 阶段直接采纳：

1. **04 号票（`wire_runtime`）里 `commands.py` 那处防御性 `attach_combat_system` 调用的处置方式——spec 明确说"`/to-tickets` 阶段需要复核，不是本 spec 直接裁定"**：本次拆票没有在 notes 阶段贸然下结论（没有读到 `commands.py` 那一段的完整上下文，不足以判断它是"接线分散"还是"命令期防御性兜底"），而是把这条复核动作原样保留在 04 号票的验收标准里（"判断是否属于同一类接线分散问题；若是，改为路由到 `wire_runtime`；若不是，保留但补充明确注释"）。这是刻意的延迟决策——`/implement` 阶段实现者会先读到那段代码的完整上下文，比 `/to-tickets` 阶段凭函数名猜测更可靠，强行在这里拍板反而可能拍错。
2. **`wire_runtime` 放哪个文件——spec 给了"`world.py` 或新建一个不产生循环 import 的小模块，`/to-tickets` 阶段确定"的选择空间**：本次拆票没有进一步收窄这个选择，原样把两个选项都写进 04 号票（"放 `world.py` 或新建一个不产生循环 import 的小模块"）。理由是这条选择依赖于 `/implement` 阶段实际尝试 `world.py` 是否会产生循环 import（`attach_ai_system`/`attach_ferries`/`attach_combat_system`/`attach_entry_guards` 分别定义在 `ai.py`/`ferry.py`/`combat_system.py`/`entity_gate.py`，`wire_runtime` 需要 import 全部四个——如果 `world.py` 本身被这几个模块反向 import，放进去会循环；这个事实只有跑一次 import 才能确认,没有必要在 notes 阶段用静态阅读去猜）,提前收窄反而可能锁死一个实际会循环 import 的选项。
3. **07 号票的事件契约测试放哪个文件——spec 给了"`test_combat_engagement.py` 或新建 `test_combat_events_contract.py`，`/to-tickets` 定"的选择空间**：本次拆票同样原样保留两个选项，不提前收窄，理由与上一条一致——实际选择取决于 `test_combat_engagement.py` 现有的测试量与组织方式（如果这个文件已经很长，新建文件更合适；如果很短，加进去更省事），这是一个"看了文件内容才能拍板"的细节,`/to-tickets` 阶段没有必要为了"看起来拆得更细"而强行拍死。
4. **B3-5（11 号票 GAP 台账）与 06 号票（创作者契约）之间只设软提示、不设硬阻塞边**：spec 用词是"应该在 Wave P0/B3 收尾时反过来在 PROGRESS.md 里留一条引用"——这是关于 PROGRESS.md 收尾更新的提醒,不是"GAP 台账内容依赖创作者契约先写好"。本次拆票把这条提醒原样落进 11 号票的 What to build（"建议在 06 号票落地后补一条反向链接"），但没有让 11 号票的 `Blocked by` 写 `06`，因为 11 号票本身的核心产出（列出表达力缺口清单）不需要读 06 号票的内容就能独立完成——如果设了硬阻塞边,会人为推迟一张本可以立即开工的票。
5. **B3-2（08 号票）不设 `Blocked by: 04`，即使两者都是"结构性重构"且属于同一批"接线相关"清理**：spec Further Notes 明确写"P0-5（`wire_runtime`）与 B3-2（抽 `messaging.py`）都是纯结构性重构，互相独立，可以并行"——这是 spec 自己给的结论，本次拆票直接采纳，没有因为"看起来都是重构"就人为画一条不存在的依赖。

## 与 spec 决策块的映射（供回溯）

| spec 决策项 | 覆盖票据 | 备注 |
|---|---|---|
| P0-1（Effect，已落） | — | 无票，只引用 ADR-0007，已核对 CLAUDE.md 摘要无漂移 |
| P0-2（昏迷 tick 自动苏醒） | `01` | 独立票，无阻塞 |
| P0-3（持刃门禁与装备语义对齐） | `02` | 独立票，无阻塞 |
| P0-4（消灭 `combat.py` 全局态） | `03` | 独立票，无阻塞；是 `07`/`10` 的前置依赖 |
| P0-5（`wire_runtime` 统一接线） | `04` | 独立票，无阻塞；与 `08` 可并行 |
| P0-6（创作者契约 v0） | `06` | 阻塞于 `05` |
| P0-7（`--validate` 未消费字段 warn） | `05` | 独立票，无阻塞；是 `06` 的前置依赖 |
| P0-8（票 Status 刷新 + 战斗事件契约测） | `07` | 阻塞于 `03` |
| P0-9（频道/登录降级，已落） | — | 无票，只引用 ADR-0008 |
| B3-1（单进程单 World，已落） | — | 无票，只引用 ADR-0009 |
| B3-2（抽出 `messaging.py`） | `08` | 独立票，无阻塞；与 `04` 可并行 |
| B3-3（官方/示例双轨范本文档） | `09` | 阻塞于 `06` |
| B3-4（三条交叉测试） | `10` | 阻塞于 `03` |
| B3-5（GAP 台账） | `11` | 独立票，无阻塞（软提示指向 `06`，非硬阻塞） |

## 未纳入本次拆票范围（明确排除，对齐 spec Out of Scope）

以下不对应任何票据，理由已在 spec Out of Scope 逐条说明，本次拆票不重复展开，只做清单式确认，避免遗漏后续被误当作"漏拆的票"：

- **P1-1**（拆分 `commands.py`/分区 `capabilities.py`）：交叉对抗裁决"停机窗口玩法/规格诚实 > 上帝模块拆分"，用户排期拍板排除，留给后续独立重构 effort。
- **P1-5**（扬州地标加厚、`use` 消耗品命令、坐骑休整机制）：主策玩法内容加厚，不阻塞停机，排期拍板排除。
- **P1-8**（可选 `power_model` 场景/manifest 声明）：已降级为软风险，不构成 M3 失败，排期拍板排除。
- **P1-9**（`$N`/`$n` 表情模板瘦身）：主策/实现向内容瘦身，非停机相关，排期拍板排除。
- **评审 P2 全部 11 项**（目录分层大搬家、默认 CLI 进 M2、双玩家广播契约、全命令消歧加码、e2e 断言收紧与拆分、`extension_data` 语义终裁、多文件场景、脚本层、Web 平台、账本、阴间、PvP、覆盖率门禁）：评审与交叉对抗均明确"有余力再做"，不进本次加固范围。
- **M4**（账本/分成/消费埋点实现、Web 创作者一站式平台、游戏内编辑器、留言板）：用户已明确"暂缓 M4"，任何看起来像 M4 的产出都不属于本次拆票，即使某张票的实现过程中"顺手就能做一点"。
- **RestrictedPython/WASM 脚本沙箱、Ink 对话树、LLM Orchestrator**：ADR-0005 M3 范围已排除；11 号票（GAP 台账）只记录"这里表达不了"，不预留空 Protocol 接缝。
- **LPC 行为等价 / golden trace**：ADR-0001 永久排除，与本次加固无关。
- **分布式、K8s、PG/Redis、多进程世界隔离**：mvp-scope 05 号票已定的通用工程判断，不因本次加固重新讨论。
