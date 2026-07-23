# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-23：Polishing Wave 6 落地（票 `09`/`10`）；fixed point `polishing-wave6-start`；code-review fix 已合。Next Up → Wave 7。**不自动开 M4**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4 三批已关。**Polishing Wave 1–6 已落地**（`01`–`10` resolved）；其余 `11`–`13` 待做。
- **工作分支**：`feat/polishing`。
- **engine/**：测试绿（948）。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)；Polishing 规格见 [.scratch/polishing/spec.md](.scratch/polishing/spec.md)；执行手册 [.scratch/polishing/implement-plan.md](.scratch/polishing/implement-plan.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Polishing Wave 6 落地：随机 objects 表 + 刷怪条件 hooks params**（2026-07-23）：票 `09`/`10`；`RandomObjectSlotBlueprint` / `draw_random_object_template`；`spawn_scan(rng=)`；`bandit_ambush.min_item_value` + `actor_meets_min_item_value`；`xingxiu` 铁剑 `value: 100`；与出口 `random_of` 求值路径分离；UGC hooks S3 仍拒；fixed point `polishing-wave6-start`；code-review fix：物品池对称测、混种候选拒载、item 生成复用 `spawn_item_from_blueprint`。948 绿。
- [x] **Polishing Wave 5 落地：条件 DSL 文档 + 液体/eat/drink**（2026-07-23）：票 `07`/`08`；`docs/condition-dsl.md`；`RoomResources`/`LiquidContainer`；`fill`/`drink`/`eat`；`DRINK_RESTORE_JINGLI=20` / `EAT_RESTORE_QI=15` / `EAT_RESTORE_JINGLI=10`；未知 `resource.*` 子键加载失败；grass 喂食 GAP 留白；fixed point `polishing-wave5-start`；code-review fix：CONTEXT 词条、S2 liquid 消费测、drink 仅 water。935 绿。
- [x] **Polishing Wave 4 落地：客店三件套（sleep + hotel + pay）**（2026-07-23）：票 `06`；`HotelRoom`/`RentPaid`；`HOTEL_RENT_COST=10`；睡觉拉满气血/精力；`on_leave_room` 清租；睡房拦 `practice`；`yangzhou_kedian`；fixed point `polishing-wave4-start`；code-review fix：`_parse_pay` 文档、PROGRESS 收口、契约 `details` 形状补记。926 绿。
- [x] **Polishing Wave 3 落地：block_exits deny_message + 步行 cost 精力**（2026-07-23）：票 `04`/`05`；`BlockEntry`；步行 `WALK_JINGLI_PER_TERRAIN_COST=2`；MVP 玩家 jingli 100；fixed point `polishing-wave3-start`；code-review fix：空 `deny_message` 回退默认、CONTEXT 补词条。916 绿。
- [x] **Polishing Wave 2 落地：房间风景 details 升级（K2+U+S1+N1）**（2026-07-23）：票 `03`；`DetailEntry`/`room_details.py`；旧写法自动转换；N1 六变体 look；S1 `scan_detail_mentions`；fixed point `polishing-wave2-start`；code-review fix：`_match_detail_key` 去重、裸 `(…)` 跳过。907 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Polishing Wave 7（新 session）

**目标**：按 [.scratch/polishing/implement-plan.md](.scratch/polishing/implement-plan.md) Wave 7 提示词实现票 [`11`](.scratch/polishing/issues/11-scene-includes.md)（多文件路径引用 `includes`）。分支 `feat/polishing`；打 tag `polishing-wave7-start`。

**约束**：纳入即做；Wave 结束跑 `/code-review`；**不自动开 M4**。

### 2. M4 评估（可并行拍板，勿与 polishing 混 scope）

独立决定是否开 M4（商业化数据模型）。**不自动滑入 M4**。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（**已关**）。
- Polishing：[.scratch/polishing/](.scratch/polishing/)（Wave 1–6 已落地；工作分支 `feat/polishing`）。
