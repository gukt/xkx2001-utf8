Status: ready-for-agent

# M3 停机加固：Wave P0（停机门闩 S0）+ Wave B3（排期，非门闩）

> 依据：[CLAUDE.md 架构不变量](../../CLAUDE.md) 第 8 条（推进治理，M3 与 M4 之间插入"M3 停机加固"）；[CONTEXT.md](../../CONTEXT.md)「M3 停机加固」词条（退出标准仅评审 P0/S0；B3 是同 spec 的排期 wave，不定义"可宣布停机"）；[评审 Final 报告](../m3-engine-architecture-review/final/m3-engine-architecture-review-report.md) 第 6 节统一 P0/P1/P2 清单 + [Phase 2 交叉对抗裁决](../m3-engine-architecture-review/adversarial/cross-review.md)（每条决策的分歧矩阵 D1–D20 与最终裁决，本 spec 的 Implementation Decisions 直接对应这些裁决）；[ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)（Effect 生命周期延期）/[ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)（频道/登录单机降级）/[ADR-0009](../../docs/adr/0009-single-process-single-world.md)（单进程单 World）——三份均已 accepted，本 spec **只引用，不重开决策**；[PROGRESS.md](../../PROGRESS.md)「M3 停机加固拍板」「P1 排期拍板」两条 Done 摘要（2026-07-21）是本 spec 两个 wave 范围的直接来源。
>
> **范围边界（写在此处供 `/to-tickets` 核对，不可扩大）**：
> - **Wave P0** = 评审报告 P0-1～P0-9 全部 9 项，对应评审报告"停机门闩"表；退出标准 = 本 wave 全部关闭后才可诚实宣布"M3 停机加固完成"。
> - **Wave B3** = 评审报告 P1-2/P1-3/P1-4/P1-6/P1-7 共 5 项（对应 PROGRESS "P1 排期拍板"里的 R1/M1/C1/T1/G1 五个决策代号），是同一 spec 下续排的非门闩 wave——B3 全关不是必须，但已排入本 spec 范围，不再需要二次拍板。
> - **OOS（本 spec 明确不做）**：评审报告 P1-1/P1-5/P1-8/P1-9；评审报告 P2 全部 11 项；M4（账本/分成/埋点实现、Web 创作者平台）。理由与出处见下文 Out of Scope。
> - P0-1（Effect/ADR-0004）与 P0-9（频道/登录范围降级）已分别由 ADR-0007、ADR-0008 完成决策落盘，CLAUDE.md 摘要已同步引用；B3 的 P1-2（单进程单 World 文档化）已由 ADR-0009 完成并被 CLAUDE.md 引用。这三项在本 spec 里**不产生新的实现票**，只在停机叙事文档里确认引用链完整（见 Implementation Decisions P0-1/P0-9/B3-1）。

## Problem Statement

M3 里程碑（包外声明式内容包 → `load_pack` → `--validate` → 可玩 → 存档重挂）已经兑现，649 测试绿，`just verify-m3` 锁死回归。但四份独立专家评审 + Phase 2 交叉对抗裁决一致指出：如果现在直接宣布"停机"并进入 M4，对外叙事会与工程事实脱节——具体表现为九类"文档谎言"风险点（Effect 生命周期悬空却被默认认为已实现、昏迷卡死却被测试用"再打一次"掩盖、少林山门"持刃"条件挂在没有 wield 命令的背包标签上、`combat.py` 里一个模块级全局列表破坏"纯函数结算"叙事、restore 路径与 fresh-load 路径各自维护一份 `attach_*` 清单容易漂移、UGC 创作者面对的字段契约从未正式冻结、`--validate` 对未消费字段完全静默、5 张 M2 票已实现却仍标 `ready-for-agent`、频道/登录范围降级只停留在口头共识没有落到 CLAUDE 摘要）。这些不处理，团队与外部读者都无法信任"M3 已停机"这句话。

同时，评审还识别出一批"强烈建议、但不构成停机失败条件"的 P1 项（拆分上帝模块、内容加厚、表情瘦身等共 9 项）。用户已经用 `/grill-with-docs` 续过一轮，从 9 项里选出 5 项（P1-2/3/4/6/7）排入本次加固窗口的续 wave，避免和 P0 一起做导致范围失控，又避免遗漏后被 M4 的开工节奏冲掉、变成无人认领的技术债。

## Solution

同一个 spec，两个顺序 wave（不是两个平行 spec）：

- **Wave P0（停机门闩 S0）**：评审报告 P0-1～P0-9 共 9 项。P0-1、P0-9 已通过 ADR 落盘，本 wave 内只需在停机叙事文档里确认引用；其余 7 项（P0-2～P0-8）需要实际实现或文档产出。**Wave P0 全部关闭，才是"M3 停机加固"可对外宣布完成的唯一标准**（CONTEXT.md「M3 停机加固」词条已锁定这一点）。
- **Wave B3（排期，非门闩）**：P0 关完后接着做的 5 项（P1-2/3/4/6/7）。B3-1（对应 P1-2）已通过 ADR-0009 落盘，本 wave 内同样只需确认引用；其余 4 项需要产出。B3 未关闭不影响"M3 停机加固"的对外宣布，但已经是本 spec 承诺的范围，不是可选愿望清单。
- **明确排除**：评审报告 P1-1/P1-5/P1-8/P1-9、全部评审 P2、M4，见 Out of Scope（这些不是"以后可能做"的模糊表述，而是本 spec 主动划的线，重新纳入需要新的拍板，不能靠 `/implement` 阶段临时加做）。

## User Stories

### Wave P0 — 停机门闩

**P0-1（Effect / ADR-0004，已落，只引用）**

1. 作为项目架构师，我想停机加固窗口不重新论证 Effect 生命周期该不该实现，因为 [ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md) 已经选定"延期兑现、归属不变"，以便加固窗口的精力花在真正悬而未决的项上。
2. 作为对外阅读 CLAUDE.md/PROGRESS.md 的人，我想看到的表述是"Effect 生命周期延期至加固窗口之后"而不是"ADR-0004 字面已齐"，以便不产生规格与实现脱节的误解——这条 CLAUDE.md 摘要已经在写，本 spec 只需确认它没有漂移。

**P0-2（昏迷 tick 自动苏醒）**

3. 作为终端玩家，我想气血耗尽陷入昏迷后，即使没有人再打我一下，经过一段时间也会自然醒来恢复行动能力，以便免死区教学、野外遭遇后没有队友的情况下不会被卡死在"只能等被杀"的软锁里。
4. 作为引擎开发者，我想昏迷的自动苏醒是 tick 驱动（复用 `TickLoop`/`on_tick`，不新起一套驱动机制，也不新增 `rest` 命令），以便这条恢复路径与死亡状态机现有的"事件驱动 + tick 驱动"分工保持一致。
5. 作为引擎开发者，我想苏醒阈值（多少 tick 后醒、醒来后气血恢复到多少）是数据驱动参数（挂在现有的 `DeathPolicy` 上，不是硬编码常量），以便题材包能调整这条数值而不用改引擎代码，与死亡惩罚比例/复活点的现有做法同构。
6. 作为引擎开发者，我想苏醒判定与既有的 `UNCONSCIOUS_BLOCKED_VERBS` 阻塞列表、`Engaged`/`NoDeathZone` 现有语义无冲突（苏醒只清除 `Unconscious`，不重新触发交战），以便这条新机制不需要改动死亡状态机已经验证过的转移规则。

**P0-3（持刃门禁与装备语义对齐）**

7. 作为终端玩家，我想少林山门的进入条件不再暗中要求"背包里没有 `edged` 标签物品"，因为角色目前没有任何命令能把武器"收起来"，这条条件在体验上等价于一个玩家永远猜不出规则的隐藏门槏。
8. 作为主策划，我想少林山门只保留"性别 + 门派归属"两项确实可操作的门槏（且更新拒绝文案），把"持刃"这条从场景条件里移除，以便 `EntryGuard` 门禁语义与题材包实际提供的命令面对齐，不承诺一个装备系统还没落地的体验。
9. 作为引擎开发者，我想 `EntityGateContext.is_wielding_edged_weapon` 这条求值能力本身**保留在引擎层**（不删代码、不改条件求值器语法），只是本次停机不再有任何官方场景内容消费它，以便未来真的落地 wield/unwield 命令时，门禁条件可以直接复用而不用重新设计接缝。

**P0-4（消灭 `combat.py` 战斗回合全局态）**

10. 作为引擎开发者，我想 `resolve_attack` 真正做到"给定同一份输入两次求值结果一致、不依赖任何进程级可变态"，因为当前 `_ROUND_EXTRA_FRAGMENTS` 模块级全局列表意味着两次并发或嵌套调用会互相污染文案片段，这与 spec A1 已经承诺的纯函数叙事矛盾。
11. 作为引擎开发者，我想 `SkillBehavior.hit_by`/`post_action` 通过**返回值**（而不是调用一个全局 `append_round_fragment` 副作用函数）向 `resolve_attack` 传回本回合追加文案，以便"招式钩子只读快照、把结果显式返回给调用方"这条约束覆盖到播报文案，不留一个副作用后门。
12. 作为引擎开发者，我想这条清理不影响 `hit_ob` 已有的"返回值可修改伤害数值"约定（`hit_ob` 签名不变），只统一 `hit_by`/`post_action` 的返回值形状，以便改动范围收敛到确实有问题的那两个钩子。

**P0-5（`wire_runtime` 统一 restore/load 接线）**

13. 作为引擎开发者，我想"一份场景加载完成后需要挂哪些运行时子系统"（nature/AI/渡口/交战/门禁）只在一处定义，无论是 fresh load（`load_scene`）还是崩溃恢复（`__main__._reattach_runtime`）都调用同一个函数，以便新增一个 `attach_xxx` 子系统时只改一处，不会出现"restore 路径忘了挂新子系统"这类静默漂移。
14. 作为引擎开发者，我想统一后的接线函数不依赖"fresh load 时 nature 配置还留在 `world.extension_data` 里、restore 后已经空了"这条隐藏的时序假设，而是每次都显式从 `scene_path` 重新读取 nature 配置，以便两条路径在同一份代码前提下行为一致，不用记住两条路径的历史差异。
15. 作为引擎开发者，我想这条统一不引入依赖注入容器或改变 `World` 挂件的现有形状（评审已裁决"务实面"，只要求单一入口，不做 `World` 反模式大重构），以便改动范围收敛在"接线顺序"这一件事上。

**P0-6（创作者契约 v0 一页纸）**

16. 作为 UGC 创作者，我想有一份明确写着"这些字段现在可以用、语义已冻结、只会新增不会改义"的文档，而不是要去读引擎源码里的 `_ROOM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS` 等常量才知道能写什么，以便我写场景 YAML 时有一份可信赖的参照。
17. 作为项目架构师，我想 `scene_loader.py` 顶部注释不再自称"M1 内部过渡格式，不是 M3 要交给创作者的正式 DSL"，而是改口"现行创作契约 v0"，以便代码内文档与对外承诺的措辞一致，不让读代码的人和读文档的人得到两个矛盾的印象。
18. 作为 UGC 创作者，我想这份契约明确写出"透传字段（`extension_data`）不算冻结契约的一部分，随时可能变化"，以便我不会误把一个还没被引擎消费的自定义字段当成稳定 API 依赖。

**P0-7（`--validate` 未消费字段 warn）**

19. 作为 UGC 创作者，我想跑 `openmud --pack <dir> --validate` 时，如果我的场景 YAML 里有字段被引擎透传进 `extension_data` 而没有被任何能力消费，能看到一条明确的警告列出具体是哪些字段、在哪个实体上，以便及时发现拼写错误或过时字段，而不是加载"成功"却发现游戏里毫无效果。
20. 作为 UGC 创作者，我想默认行为是 warn（不阻断校验通过），但可以加 `--strict` 让未消费字段变成校验失败，以便日常创作时不被这条检查打断，但在正式发布前可以选择更严格的把关。
21. 作为引擎开发者，我想这条检查复用已经存在的已知字段集机制（`_ROOM_KNOWN_FIELDS` 等 + `world.extension_data`/`entity_extension_data()`），不新建一套平行的字段登记表，以便"哪些字段是已知的"只有一份事实来源。

**P0-8（票 Status 刷新 + 战斗事件点最小契约测）**

22. 作为项目治理责任人，我想 M2 的 16～20 号票（`SkillBehavior` 钩子接线、死亡流程接线、NPC 死亡重生、aggro 行为、同名序号消歧）状态从 `ready-for-agent` 刷新为 `resolved`，因为它们对应的实现与测试（`death_flow.py`、`test_skill_behavior_hooks.py`、`test_aggro.py`、`test_disambiguation.py` 等）早已存在，票面状态与工程事实不符本身就是一种"文档谎言"。
23. 作为引擎开发者，我想 `on_before_combat_round`/`on_combat_round`/`on_combat_end` 三个已经存在的战斗事件点补上最小契约测试（否决 `on_before_combat_round` 能中止本回合结算、`on_combat_round`/`on_combat_end` 在预期时机被分发且携带正确的上下文字段），以便这批事件点不是"挂了但没人验证过真的会触发"的隐性契约。

**P0-9（频道/登录单机降级，已落，只引用）**

24. 作为项目架构师，我想停机加固窗口不重新讨论频道/登录该不该在单机阶段实现，因为 [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) 已经拍板"单机阶段不作为停机门闩"，CLAUDE.md 也已经引用，以便这条不占用本次加固的实现精力。

### Wave B3 — 排期（非门闩）

**B3-1（P1-2 / R1：单进程单 World 文档化，已落，只引用）**

25. 作为项目架构师，我想 B3 wave 不重新写一份"单进程单 World"的说明文档，因为 [ADR-0009](../../docs/adr/0009-single-process-single-world.md) 已经把这条决策落盘，CLAUDE.md 架构不变量第 1 条也已经引用它，以便这一项在本 spec 里只是"确认已完成"而不产生新的产出物。

**B3-2（P1-3 / M1：抽出 `messaging.py`，解开 `ai ↔ commands` 循环依赖）**

26. 作为引擎开发者，我想 `room_say`（及其依赖的 `ON_HEAR_SAY`/`HearSayContext`/玩家判定辅助函数）搬到一个新的 `messaging.py` 模块，以便 `ai.py` 的 Chatter 行为可以在模块顶部直接 `from openmud.messaging import room_say`，不用再在函数体内做一次延迟 import 来绕开循环依赖。
27. 作为引擎开发者，我想这次搬家只是"移动 + 改 import"，不改变 `room_say` 的行为或签名，以便这是一次纯粹的结构性清理，不需要更新任何依赖其行为的测试断言。

**B3-3（P1-4 / C1：官方/示例双轨范本文档）**

28. 作为 UGC 创作者，我想有一份文档解释清楚"默认场景 `engine/data/m2_mvp_scene.yaml`"与"内容包 `manifest.yaml + scene.yaml`"这两条轨道之间的关系——它们共用同一套场景 YAML 语法（P0-6 冻结的 v0 契约），差异只在"是否被一份 `manifest.yaml` 包裹、是否通过 `--pack` 加载"，以便我不会误以为这是两套互相不兼容的格式,需要分别学习。
29. 作为项目架构师，我想这份文档明确说明"本窗口不做官方场景包化"（不强制把默认场景改造成一个带 `manifest.yaml` 的内容包目录），只做说明性文档，以便双轨共存的现状被诚实记录，而不是被悄悄"文档掉"成看起来已经统一。

**B3-4（P1-6 / T1：三条交叉测试）**

30. 作为规格/QA，我想有一条测试覆盖"内容包模式下，建立 `Engaged` 交战关系后 save→restore，交战状态与 `pack_manifest` 都能正确恢复"，因为现有 `test_load_pack.py`/`test_m3_pack_loop.py` 只覆盖移动与物品，没有覆盖"存档发生在战斗过程中"这一现实场景。
31. 作为规格/QA，我想有一条测试覆盖"一个声明了 `SkillBehavior` 钩子的招式，通过完整的 tick 驱动自动交战回合（而不是直接构造 `CombatContext` 调用 `resolve_attack`）触发钩子"，因为现有 `test_skill_behavior_hooks.py` 完全绕过了 `Engaged`/tick 路径,没有证明钩子在真实调度链路里也生效。
32. 作为规格/QA，我想有一条测试覆盖"玩家骑乘坐骑沿官道走到渡口，渡船在场时骑乘状态 `go` 过河"，断言坐骑与骑手同步换房间、且这条组合不会被 `Terrain.cost` 校验意外拒绝，因为现有 `test_mount.py`/`test_ferry.py` 是分开测试的，两个子系统的组合路径此前没有被验证过。

**B3-5（P1-7 / G1：GAP 台账）**

33. 作为 UGC 创作者，我想有一份持续维护的清单，列出"当前声明式场景 YAML 表达不了什么、遇到时推荐怎么降级/绕过"（持续 Effect、脚本化剧情分支、多人频道广播、装备槏位与真实 wield、坐骑驯服/被抢等），以便我在设计内容时能提前知道边界在哪，而不是写到一半撞墙才发现。
34. 作为项目架构师，我想这份清单明确不是一个"能力橱窗包"（不新建一个专门用来展示引擎全部能力的示例内容包），以便与 CONTEXT.md 已经写明的"GAP 台账 ≠ 能力橱窗包"区分保持一致，不产生范围蔓延。

## Implementation Decisions

### Wave P0

**P0-1（引用，无代码改动）**：确认 [ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md) 与 [CLAUDE.md](../../CLAUDE.md) 摘要（第 4 条）已经正确引用，`/to-tickets` 不为此开实现票；若发现摘要有漂移，只修文档措辞，不重新决策。

**P0-2（昏迷 tick 自动苏醒）**

- 给 `Unconscious`（`engine/src/openmud/components.py`）新增字段 `ticks_remaining: int`（陷入昏迷时按 `DeathPolicy` 参数写入初值，不再是空 marker）。
- `DeathPolicy`（`death_flow.py`）新增两个数据字段：`unconscious_recovery_ticks: int`（默认给一个 MVP 数值，如 5）与 `recovery_vitals_ratio: float`（苏醒时气血恢复到 `qi_max` 的比例，默认如 0.2，避免醒来即刻 0 血又被环境判定打回昏迷）。两者与现有 `penalty_ratio`/`revive_room_key` 同构，场景可声明覆盖。
- 新增一个挂在 `world.events` 的 `on_tick` 订阅者（与 `attach_ai_system`/`attach_ferries` 同构的 `attach_xxx` 函数，放在 `death_flow.py`）：遍历 `entities_with(Unconscious)`，每 tick 递减 `ticks_remaining`，归零时移除 `Unconscious`、把 `Vitals.qi_current` 设为 `max(1, int(qi_max * recovery_vitals_ratio))`、推一条 `world.pending_messages` 提示"你悠悠转醒"。不触碰 `Engaged`（昏迷时已经在 `_handle_player_depleted` 里清过交战关系，苏醒不重新建立）。
- 存档：`Unconscious` 已经是"运行时可变进存档"的组件，新增字段走现有 `save.py` codec 扩展流程（与其他组件加字段同样处理，不需要新的版本机制——本项目当前无存档格式版本号，`/to-tickets` 若发现需要为老存档缺字段兜底，按"缺失字段回退默认值"处理，不新增迁移框架）。
- 是否需要新命令：不需要。此设计属于"tick 自动苏醒"路径（评审 D12 主席倾向选项），不做 `rest` 命令，也不改 US23 文案。

**P0-3（持刃门禁与装备语义对齐）**

- 编辑 `engine/data/m2_mvp_scene.yaml` 里少林山门房间（约 273–285 行）的 `entry_guard.condition`：删除 `not: {predicate: is_wielding_edged_weapon}` 这一支，只保留性别 + 门派归属两支；同步改写 `deny_message`（去掉"且不得持刃器入内"）。
- `entity_gate.py` 的 `EntityGateContext.is_wielding_edged_weapon` 求值能力**不删除**（保留供未来 wield 系统复用），只是本次没有任何官方场景内容引用它。
- 同步更新受影响测试：`test_entry_guard.py`、`test_scene_shaolin.py` 里断言"持刃/edged 物品被拒"的用例改为断言新的两条件门槏（性别 + 门派），不再构造/携带 edged 物品作为拒绝案例。
- 不做最小 `wield`/`unwield`/`stash` 命令（评审 D13 给了"改条件或最小装备命令"二选一，PROGRESS 已拍板选"改条件"）。

**P0-4（消灭 `combat.py` 战斗回合全局态）**

- `skills.py` 的 `SkillBehavior` Protocol：`hit_by(self, ctx: CombatContext) -> None` 改为 `hit_by(self, ctx: CombatContext) -> str | None`；`post_action(self, ctx: CombatContext) -> None` 改为 `post_action(self, ctx: CombatContext) -> str | None`。返回的字符串即为本次调用要追加的播报片段；`None` 表示无追加。`hit_ob` 签名不变（已经能返回 `int | str | None`）。
- `combat.py`：删除 `_ROUND_EXTRA_FRAGMENTS` 模块级列表与 `append_round_fragment` 函数（含 `__all__` 里的导出）。`resolve_attack` 改为在本次调用作用域内用局部变量收集 `hit_by`/`post_action` 的返回值，拼进 `fragments` 元组，不再 `.clear()` 一个全局态。
- `skills.py` 里现有的示范钩子 `DemoPoisonStrikeBehavior.hit_by`（当前调用 `append_round_fragment("毒素渗入伤口！")`）改为 `return "毒素渗入伤口！"`。
- 受影响测试：`test_skill_behavior_hooks.py` 里对 `hit_by`/`post_action` 返回值的断言方式需要同步更新（从"检查全局列表内容"改为"检查 `resolve_attack` 返回的 `CombatRoundResult.fragments` 是否包含预期片段"——若测试此前就是通过 `resolve_attack` 返回值断言的，改动更小）。

**P0-5（`wire_runtime` 统一接线）**

- 新增一个函数（建议放 `world.py` 或新建一个不产生循环 import 的小模块，`/to-tickets` 阶段确定，暂定 `wire_runtime(world: World, scene_path: Path) -> None`）：固定顺序调用 `attach_nature(world, config_from_yaml=read_nature_config(scene_path))` → `attach_ai_system(world)` → `attach_ferries(world)` → `attach_combat_system(world)`（内部已调用 `attach_power_model`）→ `attach_entry_guards(world)`。两条调用路径统一显式传入 `scene_path` 重新读取 nature 配置，不再依赖"fresh load 时配置还留在 `extension_data` 里"这条隐藏时序。
- `scene_loader.py` 的 `load_scene`（约 94–103 行现有 5 行 `attach_*` 序列）改为调用 `wire_runtime(world, scene_path)`。
- `__main__.py` 的 `_reattach_runtime`（约 151–160 行）删除，两处调用点（`_load_or_restore_default`、`_load_or_restore_pack`）改为直接调用 `wire_runtime(world, world.scene_path or DEFAULT_SCENE_PATH)`。
- `commands.py` 内约 1194–1200 行处存在一处对 `attach_combat_system` 的延迟 import + 条件调用（命令执行时的防御性重挂）：`/to-tickets` 阶段需要复核这处调用的用途，若属于同一类"接线分散"问题应改为路由到 `wire_runtime` 或有明确注释说明为何不能统一（可能是"命令执行期间发现 `world.combat is None` 的防御性兜底"，不一定要合并，但需要明示决策，不能留成新的第三份隐藏清单）。
- `load_pack`（`pack.py`）本身只负责 manifest + `load_scene` 组合，不需要改动——它已经通过委托 `load_scene` 间接获得统一后的 `wire_runtime`。

**P0-6（创作者契约 v0 一页纸）**

- 新增 `docs/creator-contract-v0.md`：冻结当前 `scene_loader.py` 的顶层段已知集合（`rooms:`/`items:`/`npcs:`/`player:`/`skills:`/`factions:`/`death_policy:` 等）与各层级已知字段集合（`_ROOM_KNOWN_FIELDS`/`_ITEM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS`/`_PLAYER_KNOWN_FIELDS`），以及 `manifest.yaml` 的已知字段（`id`/`version`/`creator`/`title`）。承诺条款：v0 只做加法（新增字段/新增顶层段），不做破坏性语义变更；已知字段之外的透传（`extension_data`）不在冻结范围内，随时可能被未来版本收编为正式字段或改变行为。文档需引用 P0-7 的 `--validate`/`--strict` 作为契约的机器可检查侧、引用 B3-5 的 GAP 台账作为"契约表达不到的地方"的对照。
- 同步改写 `scene_loader.py` 顶部模块 docstring（现文案"M1 内部过渡格式...不是 M3 要交给创作者的正式 UGC DSL"）为指向"现行创作契约 v0"的措辞，避免代码内注释与对外文档矛盾（不需要改变任何解析逻辑，纯文案）。

**P0-7（`--validate` 未消费字段 warn）**

- `__main__.py` 新增 `--strict` 参数（须搭配 `--validate`，否则报参数错误，与现有 `--validate` 须搭配 `--pack` 的校验方式一致）。
- `_validate_pack` 扩展：加载成功后遍历 `world.extension_data`（顶层未知段）与 `world.all_entities()` 上非空的 `entity_extension_data(entity)`（实体级未消费字段），汇总成一份"字段 → 出现位置"的报告。默认（无 `--strict`）打印为警告（stdout 或 stderr，`/to-tickets` 定具体格式），退出码仍为 0；有 `--strict` 且报告非空时，退出码改为非 0（复用现有 `_format_pack_or_scene_error` 附近的错误路径风格，给出汇总而不是逐字段刷屏）。
- 不新建平行的字段登记表：已知字段集合直接复用 `scene_loader.py` 现有的 `_ROOM_KNOWN_FIELDS` 等常量与 `world.extension_data`/`entity_extension_data()` 现有透传机制，本票只是"读出已经在被透传收集的数据并汇总展示"。

**P0-8（票 Status 刷新 + 战斗事件点契约测）**

- 刷新 `.scratch/m2-mvp-scene-playable/issues/16-skill-behavior-hook-wiring.md`、`17-death-flow-wiring.md`、`18-npc-death-and-respawn-flow.md`、`19-aggro-behavior.md`、`20-same-name-target-disambiguation.md` 五个文件的 `**Status:**` 行，从 `ready-for-agent` 改为 `resolved`（对照现有实现：`death_flow.py`、`test_skill_behavior_hooks.py`、`test_death_flow.py`、`test_aggro.py`、`test_disambiguation.py` 均已存在且通过）。
- 新增战斗事件点契约测试（可放在 `test_combat_engagement.py` 或新建 `test_combat_events_contract.py`，`/to-tickets` 定）：
  - `on_before_combat_round`：注册一个否决 handler，断言本回合被跳过（不扣血/不产生结算），且能正常在下一 tick 恢复非否决状态。
  - `on_combat_round`：断言每次自动交战回合结算后确实分发一次，携带的上下文字段（交战双方、本回合结果）与实际结算一致。
  - `on_combat_end`：断言交战关系解除（死亡/脱离）时分发一次，不多分发也不漏分发。

**P0-9（引用，无代码改动）**：确认 [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) 与 CLAUDE.md 摘要（第 4 条）已正确引用，`/to-tickets` 不为此开实现票。

### Wave B3

**B3-1（引用，无代码改动）**：确认 [ADR-0009](../../docs/adr/0009-single-process-single-world.md) 与 CLAUDE.md 架构不变量第 1 条已正确引用，`/to-tickets` 不为此开实现票。

**B3-2（抽出 `messaging.py`）**

- 新建 `engine/src/openmud/messaging.py`：迁入 `room_say`、`_is_player_entity`（可考虑改名去掉下划线前缀，因为将被 `ai.py` 跨模块使用，具体命名 `/to-tickets` 定）、`ON_HEAR_SAY`、`HearSayContext`（若这些常量/类型当前定义在 `commands.py` 别处，一并迁移到 `messaging.py`）。
- `commands.py` 的 `say` 命令改为 `from openmud.messaging import room_say`（模块顶部 import，不再是本地定义）。
- `ai.py` 第 174 行的延迟 import（`from openmud.commands import room_say`，在函数体内）改为模块顶部 `from openmud.messaging import room_say`，移除函数体内的延迟 import。
- 纯结构性搬家，不改变 `room_say` 行为；现有测试（若有直接 `from openmud.commands import room_say` 的测试用例）需要同步改 import 路径。

**B3-3（官方/示例双轨范本文档）**

- 新增文档（建议 `docs/scene-authoring-guide.md`，`/to-tickets` 可调整命名）：说明"官方默认场景"（`engine/data/m2_mvp_scene.yaml`，走无 `--pack` 的默认 CLI 入口，无 manifest 包裹）与"内容包"（`manifest.yaml` + `scene.yaml`，走 `--pack`/`--validate`）共用同一份 P0-6 冻结的场景 YAML v0 契约,唯一差异是是否被 manifest 包裹、走哪条 CLI 入口。引用 `.scratch/m3-ugc-loop-creation-surface/example-pack/` 作为内容包轨的具体样例，引用 `engine/data/m2_mvp_scene.yaml` 作为官方轨的具体样例。
- 明确声明本文档**不伴随任何代码改动**（不做官方场景包化），纯说明性产出。

**B3-4（三条交叉测试）**

- 新增（或扩展现有 `test_load_pack.py`/`test_m3_pack_loop.py`）一条测试：`--pack` 模式下建立 `Engaged` 后 `save_world`→`restore_world`，断言双方 `Engaged.opponent` 正确恢复、`pack_manifest` 正确恢复（走 `reattach_pack_manifest`）。
- 新增（或扩展现有 `test_skill_behavior_hooks.py`）一条测试：通过 `attach_combat_system` + `TickLoop.advance()` 的真实 tick 路径（而非直接构造 `CombatContext` 调 `resolve_attack`）触发一个声明了 `SkillBehavior` 钩子的招式，断言钩子确实生效、播报文案出现在真实的战斗播报里。
- 新增（或扩展 `test_mount.py`/`test_ferry.py`）一条测试：玩家骑乘状态沿官道走到渡口房间，渡船在场时 `go` 过河，断言坐骑 `Position` 与骑手同步更新，且 `Terrain.cost` 校验不会因为渡口房间本身声明的地形代价而误拒绝这次移动。

**B3-5（GAP 台账）**

- 新增 `docs/gap-ledger.md`：条目式列出至少覆盖——持续 Effect（buff/debuff，链接 ADR-0007）、脚本化任务/剧情分支（无沙箱，链接 ADR-0005 OOS）、多人频道/双玩家广播（链接 ADR-0008）、装备槏位与真实 wield/unwield（链接 P0-3）、坐骑驯服/被抢、多文件/大世界树场景。每条给"现状"+"推荐降级方式"两栏。
- 明确不新建能力橱窗内容包（与 CONTEXT.md「GAP 台账」词条的 `_Avoid_` 一致）。

## Testing Decisions

- 延续 M1/M2/M3 已确立的测试 seam 分层，不新增测试基础设施：
  - **纯函数直测**：P0-4 改动后的 `resolve_attack`（断言 `hit_by`/`post_action` 返回值正确拼进结果，且两次独立调用互不污染——这正是本票要恢复的纯函数属性,应该有一条测试专门断言"连续两次调用不共享状态"）。
  - **tick 层 seam**：P0-2 的自动苏醒（反复调用 `TickLoop.advance()`/`dispatch(ON_TICK, ...)` 断言 `ticks_remaining` 递减与归零后的状态恢复）、B3-4 的 SkillBehavior×tick 交叉测、B3-4 的骑乘×渡船交叉测。
  - **命令层 seam**：P0-3 改动后 `test_entry_guard.py`/`test_scene_shaolin.py` 的门槏断言更新；P0-7 的 `--validate`/`--strict` 走 CLI 参数解析 + `_validate_pack` 返回码断言（与现有 `test_main_cli.py` 模式一致）。
  - **存档 restore 综合测**：B3-4 的 Pack×交战 restore（与现有 `test_load_pack.py`/`test_save.py` 的 restore 断言模式一致：save → 新 `World` 实例 restore → 断言组件状态）。
  - **事件契约测**：P0-8 新增的战斗三事件点契约测试，模式参照现有 `test_domain_events.py`/`test_command_hooks.py`（否决/分发/上下文字段断言）。
  - **纯文档产出无自动化测试**：P0-1/P0-6/P0-9/B3-1/B3-3/B3-5——这些项的"验收"是人工核对文档内容与引用链完整，不写自动化断言（与 ADR 文档本身不需要测试的性质一致）。
- P0-8 的票 Status 刷新本身不是代码改动，不需要新测试；它的"验收标准"是刷新后五个文件的 `**Status:**` 行与其对应测试文件的存在/通过状态一致。
- 已有回归不得破坏：`just verify-m2`/`just verify-m3`（若存在对应脚本）与全量 `pytest` 649 基线在本 spec 全部改动后必须继续绿——P0-4/P0-5 都是对已测过路径的重构而非新增行为,尤其需要在改动后重跑一次门禁全绿再收尾。

## Out of Scope

- **P1-1（拆分 `commands.py`/分区 `capabilities.py`）**：评审给的建议改判是"停机窗口玩法/规格诚实 > 上帝模块拆分"（交叉对抗 D2），用户在 P1 排期拍板里明确排除，留给后续独立的重构 effort。
- **P1-5（扬州地标加厚、`use` 消耗品命令、坐骑休整机制）**：主策玩法内容加厚，评审判定不阻塞停机，用户排期拍板排除，留给内容向后续迭代。
- **P1-8（可选 `power_model` 场景/manifest 声明）**：评审已把"默认武侠 `PowerModel` 损害题材无关"这条指控降级为软风险（交叉对抗 D5，不构成 M3 失败），用户排期拍板排除。
- **P1-9（`$N`/`$n` 表情模板瘦身）**：主策/实现向内容瘦身，非停机相关，用户排期拍板排除。
- **评审 P2 全部 11 项**（目录分层大搬家、默认 CLI 进 M2、双玩家广播契约、全命令消歧加码、e2e 断言收紧与拆分、`extension_data` 语义终裁、多文件场景、脚本层、Web 平台、账本、阴间、PvP、覆盖率门禁）：评审报告与交叉对抗均明确这批"有余力再做"，不进本次加固范围。
- **M4（账本/分成/消费埋点实现、Web 创作者一站式平台、游戏内编辑器、留言板）**：用户已明确"暂缓 M4"，评审对抗结论 C3/D15 一致——本窗口的存在意义就是"停住 M3，不开 M4"，任何看起来像 M4 的产出（哪怕只是"留个空实现"）都不属于本 spec。
- **RestrictedPython/WASM 脚本沙箱、Ink 对话树、LLM Orchestrator**：ADR-0005 M3 范围已排除，B3-5 的 GAP 台账只记录"这里表达不了"，不预留空 Protocol 接缝（交叉对抗 D19 已裁决"不预留"）。
- **LPC 行为等价 / golden trace**：ADR-0001 永久排除，与本次加固无关，仅在此重申边界不因加固窗口而松动。
- **分布式、K8s、PG/Redis、多进程世界隔离**：mvp-scope 05 号票已定的通用工程判断，不因本次加固重新讨论。

## Further Notes

- **Wave 内部依赖顺序建议**（供 `/to-tickets` 拆票时参考，非强制）：P0-4（消灭全局态，改 `SkillBehavior` Protocol 签名）应该在 P0-8 的战斗事件点契约测试之前落地，因为两者都touch `resolve_attack`/`SkillBehavior` 调用路径，避免同一批代码被两张票分别改两次;B3-4 的"SkillBehavior×tick 交叉测"同理，建议排在 P0-4 之后。P0-5（`wire_runtime`）与 B3-2（抽 `messaging.py`）都是纯结构性重构，互相独立，可以并行。
- **P0-2 的存档兼容性**：给 `Unconscious` 加字段后，任何在改动前生成的、恰好处于昏迷态的存档，restore 时会缺 `ticks_remaining`——本项目当前没有存档版本迁移框架，`/to-tickets` 阶段需要明确"缺字段回退默认值"这一条具体怎么写（大概率是 `save.py` 对应 codec 的 `.get(key, default)` 兜底），不需要因此新增一套迁移机制。
- **P0-5 的 `commands.py` 遗留 attach 调用**：Implementation Decisions 已经标注这处需要 `/to-tickets` 复核而不是本 spec 直接裁定处置方式,因为不确定它是"接线分散"还是"命令期防御性兜底"这两种不同性质的代码,需要先看清楚再决定要不要合并进 `wire_runtime`。
- **本 spec 与既有停机叙事文档的关系**：P0-6/P0-7/B3-3/B3-5 产出的四份新文档（创作者契约 v0、`--validate`/`--strict`、双轨范本、GAP 台账）都应该在 Wave P0/B3 收尾时反过来在 PROGRESS.md 里留一条引用，避免"加固完成但没人知道去哪找这些文档"——但具体怎么更新 PROGRESS.md 是收尾动作，不是本 spec 要求实现的功能,不需要单独拆票。
- **两个 wave 的关闭方式不同**：Wave P0 全部关闭后才允许把 PROGRESS.md 的当前状态从"M3 停机加固窗口"改写为"可诚实停机"；Wave B3 各项各自关闭即可勾掉,不要求 B3 全部关闭才能改写 PROGRESS.md（这是 CONTEXT.md「M3 停机加固」词条已经写明的规则，本 spec 不改变它，只是在此重申以免 `/to-tickets`/`/implement` 阶段的人误合并两者的验收标准）。
