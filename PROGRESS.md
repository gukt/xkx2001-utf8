# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 引擎房间保真 **Wave 3 收口（effort 关闭）**；不自动开 M4。下一步：房间钩子 `/to-spec`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4：**① 频道/spawn/任务（已关闭）** → **② 引擎房间保真（已关闭）** → **③ 房间钩子 / 星宿机制**（骨架已落；实现未开；`/to-spec` 门闩已满足）。
- **工作分支**：`feat/pre-m4-engine-room-fidelity`（本 effort 已关；合并前仍可在此分支做 review fix）。
- **engine/**：测试绿（767）；后继 [pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 引擎房间保真 Wave 3 收口（effort 关闭）**（2026-07-22）：票 `07`；契约加法 + GAP 改判 + CONTEXT/PROGRESS；S3 户外旗杆语义色测；M2 旅程进打铁铺前强制白天（消 `day_shop` 墙钟 flaky）；fixed point `pre-m4-engine-room-fidelity-wave3-start`。767 绿。**不自动开 M4**。
- [x] **Pre-M4 引擎房间保真 Wave 2 落地：藏书 / day_shop / 剧情门翰林**（2026-07-22）：票 `04`–`06`；fixed point `pre-m4-engine-room-fidelity-wave2-start`；code-review fix：官方 `details.书架`、TOC 分页测、拆复合断言、删未用 `clear_reading`。766 绿。
- [x] **Pre-M4 房间钩子 / 星宿机制：grill + 骨架 + ADR-0012**（2026-07-22）：档 B + 硬门闩 γ；兄弟 effort；验收 `xingxiu_mechanics`；T1+R1 可信模块窄 `ctx`；S3 骨架 / S1 实现门闩。底稿 [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)。
- [x] **Pre-M4 引擎房间保真 Wave 1 落地：details / 语义色 / 房间旗标**（2026-07-22）：票 `01`–`03`；fixed point `pre-m4-engine-room-fidelity-wave1-start`；code-review fix：NPC `short`/`long` 走语义色校验、`_look_item` 未命中返回 `None`。745 绿。
- [x] **Pre-M4 引擎房间保真：`/to-tickets`**（2026-07-22）：[issues/](.scratch/pre-m4-engine-room-fidelity/issues/) `01`–`07`；[to-tickets-notes.md](.scratch/pre-m4-engine-room-fidelity/to-tickets-notes.md)；[implement-plan.md](.scratch/pre-m4-engine-room-fidelity/implement-plan.md)（Wave 1–3）。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Pre-M4 房间钩子 / 星宿机制：`/to-spec`

[.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)；依据 [session-notes](.scratch/pre-m4-room-hooks-xingxiu/session-notes-2026-07-22.md) + [ADR-0012](docs/adr/0012-trusted-room-hooks-narrow-ctx.md)。房间保真已关，实现门闩满足。

### 2. M4 评估

房间钩子批关完（或明确缩 scope / 延期）后再决定是否开 M4。**不自动滑入 M4。**

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿（现为 [pre-m4-room-hooks-xingxiu](.scratch/pre-m4-room-hooks-xingxiu/)）。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（骨架；待 `/to-spec`）。
