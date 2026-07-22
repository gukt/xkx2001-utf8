# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 频道/spawn/任务 **已拆票**（[issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`）；下一步按票 `/implement`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固 Wave P0（票 `01`–`07`）已关闭 → 可诚实停机**；**Wave B3（票 `08`–`11`）全关 → 加固整体完成**。**暂缓 M4**。开 M4 **之前**插入两段 Pre-M4：**① 频道/spawn/任务**（建议先）→ **② 引擎房间保真**（均已记笔记，待 grill）。
- **工作分支**：`feat/pre-m4-channels-spawn-quest`（从 `master` 切出并已推远端；`feat/m3-ugc-loop-creation-surface` 是上一里程碑遗留分支，已落后于 `master`，本阶段不再使用）。
- **engine/**：测试绿（673）；创作者契约见 [docs/creator-contract-v0.md](docs/creator-contract-v0.md)；GAP 台账见 [docs/gap-ledger.md](docs/gap-ledger.md)；双轨说明见 [docs/scene-authoring-guide.md](docs/scene-authoring-guide.md)；spec 见 [m3-hardening/spec.md](.scratch/m3-hardening/spec.md)，票见 [m3-hardening/issues/](.scratch/m3-hardening/issues/)，执行计划见 [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Pre-M4 频道/spawn/任务：`/to-tickets` 拆票**（2026-07-22）：[issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`，依赖顺序编号。Frontier（无阻塞，可并行开始）：`01` give 命令 / `02` 房间中心 `objects` 放置迁移 / `03` 假多人 seam 按会话收件箱。后续：`04` 物品/NPC 槏位补刷（阻塞于 `02`）→ `05` Channel `chat`+`system`（阻塞于 `03`）→ `06` Quest 状态机+官方闭环（阻塞于 `01`、`02`）→ `07` 收口 GAP 台账/CONTEXT/PROGRESS 回写（阻塞于 `04`、`05`、`06`）。未实现，下一步按票 `/implement`。
- [x] **Pre-M4 频道/spawn/任务：grill + spec**（2026-07-22）：shared understanding 确认；[spec.md](.scratch/pre-m4-channels-spawn-quest/spec.md)（S1/S2/S3）；[ADR-0010](docs/adr/0010-room-centric-objects-placement.md) 房间 `objects`；ADR-0008 澄清；CONTEXT 增 Channel / 房间 objects / Quest。
- [x] **Pre-M4 频道旁路：research + 窄域 grill**（2026-07-22）：[research-channels-lpc](.scratch/pre-m4-channels-spawn-quest/research-channels-lpc-2026-07-22.md)；频道支线已决 `chat`+`system`；并入主 grill/spec。
- [x] **M3 停机加固 Wave 3 落地：B3 收口（双轨范本文档）**（2026-07-22）：票 `09` [场景创作双轨说明](docs/scene-authoring-guide.md)（官方轨 `m2_mvp_scene.yaml` ↔ 内容包轨 `example-pack/`，共用契约 v0；诚实记录不做官方场景包化）+ 契约/GAP 反向链接；fixed point `m3-hardening-wave3-start`。**Wave B3（`08`–`11`）全关**；加固整体（P0+B3）完成。673 绿。
- [x] **M3 停机加固 Wave 2 落地：B3 三张（messaging / 交叉测 / GAP）**（2026-07-21）：票 `08` 抽出 `messaging.py` 解开 `ai↔commands` 循环 / `10` 三条交叉测（pack×交战 restore、SkillBehavior×tick、骑乘×渡船）/ `11` [GAP 台账](docs/gap-ledger.md) + 创作者契约反向链接；fixed point `m3-hardening-wave2-start`。Review fix：骑乘×渡船断言锁 `Terrain.cost` 与渡船在场。673 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. Pre-M4 频道/spawn/任务

已 `/to-tickets`，票见 [issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`，**执行计划（Wave 拆分 + 可复制的提示词模板）见 [implement-plan.md](.scratch/pre-m4-channels-spawn-quest/implement-plan.md)**。分支 `feat/pre-m4-channels-spawn-quest`（已从 `master` 切出并推远端，本阶段全部实现票在这个分支上做，不直接改 `master`）。

**当前 Wave：1**（票 `01`/`02`/`03`，frontier，无阻塞）→ Wave 2（`04`/`05`/`06`）→ Wave 3（`07` 收口）。每个 Wave 结束更新本节这行 + Done/In Progress，具体提示词直接去 implement-plan.md 复制。

### 2. Pre-M4 引擎房间保真

**放置不在本批**（ADR-0010 归上项）；上项关完或明确可并行后再 `/grill-with-docs`（[.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)）。

### 3. M4 评估

上述 Pre-M4 effort 关完（或 grill 明确缩 scope / 延期）后再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。**不因 B3 做完自动滑入 M4。**

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（建议先）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。
