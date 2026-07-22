# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 房间钩子 / 星宿机制 **Wave 7 收口（effort 关闭）**（票 `11`）；fixed point `pre-m4-room-hooks-xingxiu-wave7-start`；861 绿。下一步：M4 评估。**不自动开 M4**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4：**① 频道/spawn/任务（已关闭）** → **② 引擎房间保真（已关闭）** → **③ 房间钩子 / 星宿机制（已关闭）**。
- **工作分支**：`feat/pre-m4-room-hooks-xingxiu`（收口完成；未要求前不合并 master）。
- **engine/**：测试绿（861）。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 7 收口（effort 关闭）**（2026-07-22）：票 `11`；UGC `hooks` 边界复核；契约「官方轨专属 hooks」+ GAP「运行时改世界机关」+ CONTEXT 回写；`test_xingxiu_mechanics_closeout` S3 清单；fixed point `pre-m4-room-hooks-xingxiu-wave7-start`；code-review fix：补 PROGRESS/archive 与票/README 对齐。861 绿。**不自动开 M4**。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 6 落地：柔丝索跨玩家捕获**（2026-07-22）：票 `10`；`SilkRopeCaptureBehavior`/`silk_rope`；`CombatContext` 可选 `world`/`defender_id`；`hit_ob` 直调 `relocate_entity`；切片 `silk_yard`/`silk_prison`；fixed point `pre-m4-room-hooks-xingxiu-wave6-start`；code-review fix：纯函数契约文档对齐、未 relocate 不播报捕获、双会话测挂 `PlayerSession`、去掉未用 `attacker_id`。859 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 5 落地：劫匪刷拦 + 杀令介入**（2026-07-22）：票 `08`/`09`；`bandit_ambush`/`kill_order`；`objects: 0` 蓝图登记；`ensure_npc`/`actor_faction_id`/`try_engage`；fixed point `pre-m4-room-hooks-xingxiu-wave5-start`；code-review fix：切片 `player.faction`、劫匪解除路径、`on_leave` 只清 `triggered`、解析器去重。852 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 4 落地：时段秘道 + 磁力吸铁**（2026-07-22）：票 `06`/`07`；`time_of_day_passage`/`magnetic_iron`；`actor_has_item_tag`；fixed point `pre-m4-room-hooks-xingxiu-wave4-start`；code-review fix：首 sync 经 HiddenExits、挂载冷启动 `on_tick`、`when` 校验、磁力文案跟 tag。837 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 3 落地：多步状态机 + 迷途 + jump/climb**（2026-07-22）：票 `03`/`04`/`05`；`multi_step_gate`/`lost_in_maze`/`skill_gate`；`ON_BEFORE_LEAVE_ROOM`；fixed point `pre-m4-room-hooks-xingxiu-wave3-start`；code-review fix：协议文档补 jump/climb、迷途 `escape_target`、技能门槛播报用 `direction`。820 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. M4 评估

房间钩子 / 星宿机制批已关闭。决定是否开 M4 前独立拍板。**不自动滑入 M4**。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（**已关**）。
