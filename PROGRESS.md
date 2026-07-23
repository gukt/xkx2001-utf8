# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-23：`feat/pre-m4-room-hooks-xingxiu` 已合并 master 并推送；新开 `feat/polishing` 分支。Polishing `/to-tickets` 完成，产出 [.scratch/polishing/issues/](.scratch/polishing/issues/)（`01`–`13`）；Next Up 转 `/implement`。**不自动开 M4**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4 三批已关。**Polishing 已拆 13 票**（`01`–`13`；未开实现）。
- **工作分支**：`feat/polishing`（从 master 新开；`feat/pre-m4-room-hooks-xingxiu` 已合并 master 关闭）。
- **engine/**：测试绿（861；本 session 未改代码）。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)；Polishing 规格见 [.scratch/polishing/spec.md](.scratch/polishing/spec.md)；拆票分析见 [.scratch/polishing/to-tickets-notes.md](.scratch/polishing/to-tickets-notes.md)（权威拍板底稿仍是 [.scratch/polishing-candidate-review/session-notes-2026-07-23.md](.scratch/polishing-candidate-review/session-notes-2026-07-23.md)）。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Polishing `/to-tickets`**（2026-07-23）：把 [.scratch/polishing/spec.md](.scratch/polishing/spec.md) 13 项按候选 ID 顺序拆成 [.scratch/polishing/issues/](.scratch/polishing/issues/) `01`–`13`（A1+A2→`01`，A3→`02`(blocked by `01`)，A4→`03`，A5→`04`，B6→`05`，B8→`06`，B9→`07`，C10→`08`，C11→`09`，C12→`10`，C13→`11`，C14 ADR→`12`，C14 实现→`13`(blocked by `12`)）；B8 三项开放子决策已由架构师拍板钉死（`sleep_room` 沿用现有 `no_sleep_room`；付费用新 `pay` 命令；睡房拦练功独立实现不共用 `LibraryRoom`），写入票 `06` 与 [to-tickets-notes.md](.scratch/polishing/to-tickets-notes.md)。**未**开实现。同 session 先把 `feat/pre-m4-room-hooks-xingxiu` 合并进 master 并推送，新开 `feat/polishing` 分支承载本 effort 实现。
- [x] **Polishing `/to-spec`**（2026-07-23）：按序读 PROGRESS/CLAUDE+CONTEXT/session-notes/provenance/gap-ledger 后，把 grill 拍板的 13 项（A1+A2、A3、A4、A5、B6、B8、B9、C10、C11、C12、C13、C14）转成 [.scratch/polishing/spec.md](.scratch/polishing/spec.md)：逐项 Problem/User Stories/Implementation Decisions（含开放子决策标注）/Testing Decisions（复用既有 `execute_line`/`load_scene`/`--pack --validate`/`spawn_scan` seam，不新增 seam）；C14 标「先出 ADR 再实现」两票拆分要求；C12 标「只走官方 hooks params，不扩条件 DSL」。**未**开实现、**未**改契约/加载器、**未**把已纳入项踢出 scope。效力目录定名 `.scratch/polishing/`。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 7 收口（effort 关闭）**（2026-07-22）：票 `11`；UGC `hooks` 边界复核；契约「官方轨专属 hooks」+ GAP「运行时改世界机关」+ CONTEXT 回写；`test_xingxiu_mechanics_closeout` S3 清单；fixed point `pre-m4-room-hooks-xingxiu-wave7-start`；code-review fix：补 PROGRESS/archive 与票/README 对齐。861 绿。**不自动开 M4**。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 6 落地：柔丝索跨玩家捕获**（2026-07-22）：票 `10`；`SilkRopeCaptureBehavior`/`silk_rope`；`CombatContext` 可选 `world`/`defender_id`；`hit_ob` 直调 `relocate_entity`；切片 `silk_yard`/`silk_prison`；fixed point `pre-m4-room-hooks-xingxiu-wave6-start`；code-review fix：纯函数契约文档对齐、未 relocate 不播报捕获、双会话测挂 `PlayerSession`、去掉未用 `attacker_id`。859 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 5 落地：劫匪刷拦 + 杀令介入**（2026-07-22）：票 `08`/`09`；`bandit_ambush`/`kill_order`；`objects: 0` 蓝图登记；`ensure_npc`/`actor_faction_id`/`try_engage`；fixed point `pre-m4-room-hooks-xingxiu-wave5-start`；code-review fix：切片 `player.faction`、劫匪解除路径、`on_leave` 只清 `triggered`、解析器去重。852 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Polishing `/implement`（新 session 主线）

**目标**：按依赖顺序认领 [.scratch/polishing/issues/](.scratch/polishing/issues/) `01`–`13`，逐票落地。工作分支 `feat/polishing`。

**可立即开工（无阻塞，可并行）**：`01`（出口导航别名）、`03`（房间风景 details 升级）、`04`（block_exits 拒走文案）、`05`（步行 cost 精力）、`06`（客店三件套）、`07`（条件 DSL 文档化）、`08`（液体/eat/drink）、`09`（随机 objects 表）、`10`（刷怪条件扩展）、`11`（多文件 includes）、`12`（局部天气 ADR）。
**有阻塞**：`02`（A3，blocked by `01`）；`13`（C14 实现，blocked by `12`）。

**开工读**（按序）：
1. [PROGRESS.md](PROGRESS.md)（本文件）
2. [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)
3. [.scratch/polishing/spec.md](.scratch/polishing/spec.md)（**权威规格**）+ [.scratch/polishing/to-tickets-notes.md](.scratch/polishing/to-tickets-notes.md)（拆票依据 + 已钉死的开放子决策）
4. 认领的具体票 [.scratch/polishing/issues/NN-*.md](.scratch/polishing/issues/)
5. 需要出处背景时再翻 [.scratch/polishing-candidate-review/](.scratch/polishing-candidate-review/)（session-notes 拍板 + provenance LPC 出处）

**新 session 建议第一句**：
`@PROGRESS.md /implement .scratch/polishing/issues/01-exit-navigation-aliases.md`（或其它无阻塞票号）

**约束**：
- **纳入即做**（13 票全部本阶段必须落地，不得以「太大」为由后置）
- **每票关闭回写**：`docs/gap-ledger.md` / `docs/creator-contract-v0.md` / `CONTEXT.md`（清单见 spec.md「Further Notes」收尾回写清单）；effort 整体关闭时建议产出 `scripts/verify_polishing.py` + `test_verify_polishing_matrix.py`（S5，参考兄弟批手法）
- **不自动开 M4**

### 2. M4 评估（可并行拍板，勿与 polishing 混 scope）

独立决定是否开 M4（商业化数据模型）。**不自动滑入 M4**。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（**已关**）。
- Polishing grill（已确认）：[.scratch/polishing-candidate-review/](.scratch/polishing-candidate-review/)。实现 effort：[.scratch/polishing/](.scratch/polishing/)（`spec.md` 已写；票 `01`–`13` 已拆，待 `/implement`；工作分支 `feat/polishing`）。
