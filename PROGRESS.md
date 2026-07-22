# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 房间钩子 / 星宿机制 **Wave 1 落地**（票 `01`）；fixed point `pre-m4-room-hooks-xingxiu-wave1-start`；789 绿。下一步：`/implement` Wave 2（票 `02`）。**不自动开 M4**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4：**① 频道/spawn/任务（已关闭）** → **② 引擎房间保真（已关闭）** → **③ 房间钩子 / 星宿机制**（Wave 1 已落地；票 `02`–`11` 待做）。
- **工作分支**：`feat/pre-m4-room-hooks-xingxiu`。
- **engine/**：测试绿（789）；下一步见 [pre-m4-room-hooks-xingxiu/implement-plan.md](.scratch/pre-m4-room-hooks-xingxiu/implement-plan.md)。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 房间钩子 / 星宿机制 Wave 1 落地：钩子协议 + 注册表 + 窄 ctx**（2026-07-22）：票 `01`；`RoomHook`/`RoomHookContext`/`RoomFreeState`/`relocate_entity`；UGC `hooks` fail-closed；fixed point `pre-m4-room-hooks-xingxiu-wave1-start`；code-review fix：注册表类型、CLI `--validate`、挂载路径异常传播、restore 重挂。789 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制：`/to-tickets`**（2026-07-22）：[issues/](.scratch/pre-m4-room-hooks-xingxiu/issues/) `01`–`11`（编号即依赖顺序，与 spec US1–51 分组一一对应）；[to-tickets-notes.md](.scratch/pre-m4-room-hooks-xingxiu/to-tickets-notes.md)；[implement-plan.md](.scratch/pre-m4-room-hooks-xingxiu/implement-plan.md)（7 Wave）。`01`（钩子协议/注册表/窄 `ctx`）为唯一地基票，`02`–`10`（十类机关）只阻塞于 `01`、彼此不互阻塞；`11` 收口阻塞于全部机关票。
- [x] **Pre-M4 引擎房间保真 Wave 3 收口（effort 关闭）**（2026-07-22）：票 `07`；契约加法 + GAP 改判 + CONTEXT/PROGRESS；S3 户外旗杆语义色测；M2 旅程进打铁铺前强制白天（消 `day_shop` 墙钟 flaky）；fixed point `pre-m4-engine-room-fidelity-wave3-start`。767 绿。**不自动开 M4**。
- [x] **Pre-M4 引擎房间保真 Wave 2 落地：藏书 / day_shop / 剧情门翰林**（2026-07-22）：票 `04`–`06`；fixed point `pre-m4-engine-room-fidelity-wave2-start`；code-review fix：官方 `details.书架`、TOC 分页测、拆复合断言、删未用 `clear_reading`。766 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制：grill + 骨架 + ADR-0012**（2026-07-22）：档 B + 硬门闩 γ；兄弟 effort；验收 `xingxiu_mechanics`；T1+R1 可信模块窄 `ctx`；S3 骨架 / S1 实现门闩。底稿 [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Pre-M4 房间钩子 / 星宿机制：`/implement` Wave 2

按 [.scratch/pre-m4-room-hooks-xingxiu/implement-plan.md](.scratch/pre-m4-room-hooks-xingxiu/implement-plan.md) 做票 `02`（动态出口+时限崩塌 + `random_of`，创建 `xingxiu_mechanics.yaml`）。分支继续 `feat/pre-m4-room-hooks-xingxiu`。

### 2. M4 评估

房间钩子批关完（或明确缩 scope / 延期）后再决定是否开 M4。**不自动滑入 M4。**

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿（现为 [pre-m4-room-hooks-xingxiu](.scratch/pre-m4-room-hooks-xingxiu/)）。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（Wave 1 已落地；待 Wave 2+）。
