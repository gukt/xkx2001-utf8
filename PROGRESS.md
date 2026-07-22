# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 频道/spawn/任务 **Wave 3 收口（effort 关闭）**；下一步 Pre-M4 引擎房间保真 grill（不自动开 M4）。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固 Wave P0（票 `01`–`07`）已关闭 → 可诚实停机**；**Wave B3（票 `08`–`11`）全关 → 加固整体完成**。**暂缓 M4**。开 M4 **之前**插入两段 Pre-M4：**① 频道/spawn/任务（已关闭）** → **② 引擎房间保真**（笔记已有，待 grill）。
- **工作分支**：`feat/pre-m4-channels-spawn-quest`（effort 已关，未合并 master；是否合入由用户决定）。`feat/m3-ugc-loop-creation-surface` 是上一里程碑遗留分支，已落后于 `master`，本阶段不再使用。
- **engine/**：测试绿（718）；创作者契约见 [docs/creator-contract-v0.md](docs/creator-contract-v0.md)；GAP 台账见 [docs/gap-ledger.md](docs/gap-ledger.md)（频道 / 槽位补刷 / 声明式 Quest 已改判为严格切片已支持）；双轨说明见 [docs/scene-authoring-guide.md](docs/scene-authoring-guide.md)；本 effort 已关：[pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0010](docs/adr/0010-room-centric-objects-placement.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 频道/spawn/任务 Wave 3 收口（effort 关闭）**（2026-07-22）：票 `07` GAP 台账改判（多人频道 / 物品·NPC 槽位补刷 / 声明式 Quest 为严格切片已支持）+ CONTEXT 词条与实现对齐 + 房间保真文档核对未重开放置；fixed point `pre-m4-channels-spawn-quest-wave3-start`。票 `01`–`07` 全关。
- [x] **Pre-M4 频道/spawn/任务 Wave 2 落地**（2026-07-22）：票 `04` 物品/NPC 槽位补刷 / `05` Channel `chat`+`system` / `06` Quest + 官方 `escort_delivery`；fixed point `pre-m4-channels-spawn-quest-wave2-start`。Review fix：`ItemTemplateKey` 使非槽位物品也能按模板完成任务；补刷 `_refill_slots` 去重。718 绿。
- [x] **Pre-M4 频道/spawn/任务 Wave 1 落地**（2026-07-22）：票 `01` give / `02` 房间 `objects`（ADR-0010）/ `03` 按会话收件箱；fixed point `pre-m4-channels-spawn-quest-wave1-start`。Review fix：BDD `When*` 重组 give/mailbox 测；give 背包未持有→「你没有」；物品可跨房 `objects`、NPC 仍单房；补 `count`/`startroom` 错配测；mailbox 占位改 `_pending_before_primary`。690 绿。
- [x] **Pre-M4 频道/spawn/任务：`/to-tickets` 拆票**（2026-07-22）：[issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`，依赖顺序编号。Frontier 已由 Wave 1 吃掉；后续：`04` 槽位补刷（阻塞于 `02`）→ `05` Channel（阻塞于 `03`）→ `06` Quest（阻塞于 `01`、`02`）→ `07` 收口（阻塞于 `04`、`05`、`06`）。
- [x] **Pre-M4 频道/spawn/任务：grill + spec**（2026-07-22）：shared understanding 确认；[spec.md](.scratch/pre-m4-channels-spawn-quest/spec.md)（S1/S2/S3）；[ADR-0010](docs/adr/0010-room-centric-objects-placement.md) 房间 `objects`；ADR-0008 澄清；CONTEXT 增 Channel / 房间 objects / Quest。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Pre-M4 引擎房间保真

笔记与缺口清单见 [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。**放置模型不在本批**（ADR-0010 已由频道/spawn/任务 effort 落地）。下一步：`/grill-with-docs` → to-spec → to-tickets → implement。

### 2. M4 评估

上述 Pre-M4 房间保真关完（或 grill 明确缩 scope / 延期）后再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。**不因频道/spawn/任务关完或 B3 做完自动滑入 M4。**

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。
