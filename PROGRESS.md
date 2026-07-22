# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 引擎房间保真 **Wave 1 落地**（票 `01`–`03` + code-review fix；745 绿）。下一步 Wave 2；不自动开 M4。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4：**① 频道/spawn/任务（已关闭）** → **② 引擎房间保真**（Wave 1 已关；[implement-plan.md](.scratch/pre-m4-engine-room-fidelity/implement-plan.md) → **Next = Wave 2**）。
- **工作分支**：`feat/pre-m4-engine-room-fidelity`。
- **engine/**：测试绿（745）；本批：[pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0011](docs/adr/0011-semantic-color-tokens.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 引擎房间保真 Wave 1 落地：details / 语义色 / 房间旗标**（2026-07-22）：票 `01`–`03`；fixed point `pre-m4-engine-room-fidelity-wave1-start`；code-review fix：NPC `short`/`long` 走语义色校验、`_look_item` 未命中返回 `None`。745 绿。
- [x] **Pre-M4 引擎房间保真：`/to-tickets`**（2026-07-22）：[issues/](.scratch/pre-m4-engine-room-fidelity/issues/) `01`–`07`；[to-tickets-notes.md](.scratch/pre-m4-engine-room-fidelity/to-tickets-notes.md)；[implement-plan.md](.scratch/pre-m4-engine-room-fidelity/implement-plan.md)（Wave 1–3）。
- [x] **Pre-M4 引擎房间保真：`/to-spec`**（2026-07-22）：[spec.md](.scratch/pre-m4-engine-room-fidelity/spec.md)（`ready-for-agent`；S1/S2/S3）；硬门闩三 + 日间店/剧情门非门闩 + 契约回写 + 扬州 MVP 验收。
- [x] **Pre-M4 引擎房间保真：grill + shared understanding**（2026-07-22）：硬门闩 = `details` + 语义色（ADR-0011）+ 完整藏书；本波必做非门闩 = `day_shop` + 剧情门 + 契约；液体/防拐带后置；不重开放置。
- [x] **Pre-M4 频道/spawn/任务 Wave 3 收口（effort 关闭）**（2026-07-22）：票 `07` GAP 台账改判 + CONTEXT 收紧；票 `01`–`07` 全关。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Pre-M4 引擎房间保真：Wave 2 `/implement`

[implement-plan.md](.scratch/pre-m4-engine-room-fidelity/implement-plan.md) Wave 2：票 `04`（藏书+藏书阁硬门闩）、`05`（`day_shop`）、`06`（剧情门翰林）。复制该文件「Wave 2」提示词；fixed point：`pre-m4-engine-room-fidelity-wave2-start`。

### 2. M4 评估

房间保真关完（或明确缩 scope / 延期）后再决定是否开 M4。**不自动滑入 M4。**

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 的 [implement-plan.md](.scratch/pre-m4-engine-room-fidelity/implement-plan.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（Wave 1 已关，待 Wave 2）。
