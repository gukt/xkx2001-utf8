# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-22：Pre-M4 频道/spawn/任务 **已拆票**（[issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`）；下一步按票 `/implement`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固 Wave P0（票 `01`–`07`）已关闭 → 可诚实停机**；**Wave B3（票 `08`–`11`）全关 → 加固整体完成**。**暂缓 M4**。开 M4 **之前**插入两段 Pre-M4：**① 频道/spawn/任务**（建议先）→ **② 引擎房间保真**（均已记笔记，待 grill）。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（加固 Wave 3 fixed point：`m3-hardening-wave3-start`）。
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

### 1. Pre-M4 频道/spawn/任务：按 Wave 执行（分支 `feat/pre-m4-channels-spawn-quest`）

已 `/to-tickets`，[issues/](.scratch/pre-m4-channels-spawn-quest/issues/) `01`–`07`。按依赖关系分 3 个 Wave，**本阶段全部实现票都在新分支 `feat/pre-m4-channels-spawn-quest` 上做，不直接改 `master`**。每个 Wave 开工前把下面对应的提示词整段粘给一个新 session 执行，Wave 之间按顺序来（Wave 2 依赖 Wave 1 落地，Wave 3 依赖 Wave 2 落地）。

| Wave | 票 | 依赖 | 状态 |
|---|---|---|---|
| 1 | `01` give 命令 / `02` 房间中心 `objects` 放置迁移 / `03` 假多人 seam 按会话收件箱 | 无（frontier） | 待执行 |
| 2 | `04` 物品/NPC 槏位补刷 / `05` Channel `chat`+`system` / `06` Quest 状态机+官方闭环 | Wave 1 | 待执行 |
| 3 | `07` 收口：GAP 台账 + CONTEXT/PROGRESS 回写 | Wave 2 | 待执行 |

<details>
<summary>Wave 1 提示词（票 01/02/03，可复制整段执行）</summary>

```
开工先读 PROGRESS.md + CLAUDE.md + CONTEXT.md。

任务：实现 Pre-M4 频道/spawn/任务 effort 的 Wave 1，对应三张票（互相无阻塞）：
- .scratch/pre-m4-channels-spawn-quest/issues/01-give-command.md
- .scratch/pre-m4-channels-spawn-quest/issues/02-room-objects-placement.md
- .scratch/pre-m4-channels-spawn-quest/issues/03-per-session-mailbox.md

分支与 tag：
1. 若本地没有 feat/pre-m4-channels-spawn-quest 分支，先 git fetch，再 git checkout -b feat/pre-m4-channels-spawn-quest origin/feat/pre-m4-channels-spawn-quest；若本地已有则 git checkout feat/pre-m4-channels-spawn-quest 并确保是最新。全程不要在 master 上改代码。
2. 在开始实现前打一个 fixed point：git tag pre-m4-channels-spawn-quest-wave1-start（已存在则跳过）。

对 01 → 02 → 03 逐票实现（每张票完整做完再进入下一张，不要并行改同一批文件）：
1. 用 /implement 完成该票 issue 文件里的验收项（TDD 优先，跑相关单测；每票做完跑一次 just test 全量回归）。
2. 用 /code-review review 本票的改动并修复发现的问题。
3. 单独 commit，message 格式 "pre-m4-channels-spawn-quest-01: give 命令" 这种"票号+摘要"风格（参照 git log 里 M3-hardening-08 这类提交）。
4. 把该票 issue 文件顶部 Status 从 ready-for-agent 改成 resolved，并在文件末尾 ## Comments 里补一句实现摘要（做了什么、关键决策、遗留点）。

三张票都做完、just test 全绿后：
- 更新 PROGRESS.md：Wave 1 三张票的实现记录加进 Done（滑动窗口只留最近 5 条，超出的移进 .scratch/progress-archive.md）；本节表格里 Wave 1 状态改成"已完成"，Wave 2 改成"可开始"。
- git push（把分支推上去；不需要推 tag 除非你想留痕）。

不要动 Wave 2/3 的票（04/05/06/07），不要扩大本 effort 范围（参照 spec.md 的 Out of Scope）。
```

</details>

<details>
<summary>Wave 2 提示词（票 04/05/06，依赖 Wave 1 已落地，可复制整段执行）</summary>

```
开工先读 PROGRESS.md + CLAUDE.md + CONTEXT.md，确认 Wave 1（票 01/02/03）已在 Done 里、feat/pre-m4-channels-spawn-quest 分支已有对应提交。

任务：实现 Pre-M4 频道/spawn/任务 effort 的 Wave 2，对应三张票：
- .scratch/pre-m4-channels-spawn-quest/issues/04-item-npc-slot-respawn.md（阻塞于票 02，Wave 1 应已落地）
- .scratch/pre-m4-channels-spawn-quest/issues/05-channel-chat-system.md（阻塞于票 03，Wave 1 应已落地）
- .scratch/pre-m4-channels-spawn-quest/issues/06-quest-state-machine.md（阻塞于票 01、02，Wave 1 应已落地）

这三张票彼此无阻塞，可按 04 → 05 → 06 顺序逐票做（或你判断更省事的顺序，但仍逐票完整落地）。

分支与 tag：
1. git checkout feat/pre-m4-channels-spawn-quest 并确保是最新（本地没有则 git fetch 后 checkout）。全程不要在 master 上改代码。
2. 打 fixed point：git tag pre-m4-channels-spawn-quest-wave2-start（已存在则跳过）。

对每张票：
1. /implement 完成验收项（TDD 优先；单测 + 每票做完跑一次 just test 全量）。
2. /code-review review 本票改动并修复。
3. 单独 commit，message 如 "pre-m4-channels-spawn-quest-04: 物品/NPC 槏位补刷"。
4. 该票 issue 文件 Status 改 resolved，## Comments 补实现摘要。

三张票都做完、just test 全绿后：
- 更新 PROGRESS.md：Wave 2 记录进 Done（滑动窗口规则同上）；表格 Wave 2 改"已完成"，Wave 3 改"可开始"。
- git push。

不要动票 07（收口票留给 Wave 3，因为它要求 04/05/06 都落地后才回写 GAP 台账）。
```

</details>

<details>
<summary>Wave 3 提示词（票 07，依赖 Wave 2 已落地，可复制整段执行）</summary>

```
开工先读 PROGRESS.md + CLAUDE.md + CONTEXT.md，确认 Wave 2（票 04/05/06）已在 Done 里。

任务：实现 Pre-M4 频道/spawn/任务 effort 的 Wave 3（收口），对应票：
- .scratch/pre-m4-channels-spawn-quest/issues/07-closeout-gap-ledger.md

分支：git checkout feat/pre-m4-channels-spawn-quest 并确保是最新。

1. 打 fixed point：git tag pre-m4-channels-spawn-quest-wave3-start（已存在则跳过）。
2. /implement 完成票 07 的验收项：docs/gap-ledger.md 改判、CONTEXT.md 三个词条核对回写、PROGRESS.md Done/Next Up 更新、核对 pre-m4-engine-room-fidelity 文档未被重开放置模型讨论。本票以文档改动为主，若过程中发现前面 Wave 1/2 的实现细节与 spec/词条描述有出入，直接回写词条本身，不新开决策票；若发现偏差大到需要重新拍板，停下来做一次短 grill 再继续。
3. /code-review review 改动。
4. commit，message 如 "pre-m4-channels-spawn-quest-07: 收口 GAP 台账 + CONTEXT/PROGRESS 回写"。
5. 票 07 Status 改 resolved，## Comments 补摘要。

跑一次 just test 全量确认没有被文档改动波及。更新 PROGRESS.md：把整个 Pre-M4 频道/spawn/任务 effort 标记为已完成，移出 Next Up；本 effort 的完整收尾记录进 Done。git push。

本票做完后，本 effort（.scratch/pre-m4-channels-spawn-quest/）全部关闭。是否把 feat/pre-m4-channels-spawn-quest 合并回 master、要不要开 PR，等人工确认，不要自动合并。合并后再决定是否推进 Pre-M4 引擎房间保真（.scratch/pre-m4-engine-room-fidelity/）或评估开 M4。
```

</details>

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
