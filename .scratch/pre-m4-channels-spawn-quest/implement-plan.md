# Pre-M4 频道/spawn/任务实现计划：Wave 拆分 + `/implement` → `/code-review` → fix 循环

> 本文件是 7 张票（[issues/](issues/)）的执行手册，供你在**新 session** 里按 wave 逐批推进。spec 原文见 [spec.md](spec.md)；grill 底稿见 [session-notes-2026-07-22.md](session-notes-2026-07-22.md)/[grill-paused-2026-07-22.md](grill-paused-2026-07-22.md)；放置模型决策见 [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：全部工作在 `feat/pre-m4-channels-spawn-quest`（已从 `master` 切出并推到远端）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前，重新对照 [CLAUDE.md](../../CLAUDE.md) 的架构不变量第 4 条（子系统四档归类）与本 spec 开头的「范围边界」段——本 effort 是**严格切片**：假多人 seam + Channel（仅 `chat`/`system`）、房间中心 `objects` 放置 + 槏位补刷、声明式 Quest（仅交物+旗标），三条都做但不做成完整多人网游/通用任务引擎。任何票据实现时发现要扩展到 spec「Out of Scope」列出的项，先停下来核对是不是不小心越界，而不是顺手做了。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 1 | `01`, `02`, `03` | 地基三张互相独立的能力：`give` 命令 / 房间中心 `objects` 放置迁移 / 假多人按会话收件箱 | 三票互不阻塞，可并行或任意顺序 |
| 2 | `04`, `05`, `06` | 在 Wave 1 之上的三条能力：物品/NPC 槏位补刷（阻塞于 `02`）/ Channel `chat`+`system`（阻塞于 `03`）/ Quest 状态机+官方闭环（阻塞于 `01`、`02`） | 三票彼此不互相阻塞，只依赖 Wave 1，可并行 |
| 3 | `07` | 收口：GAP 台账 + `CONTEXT.md`/`PROGRESS.md` 回写 | 单票，阻塞于 `04`、`05`、`06` |

依赖图（→ 表示"被…阻塞"）：

```
01 ──────────→ 06
02 ──┬───────→ 06
     └───────→ 04
03 ───────────→ 05

04, 05, 06 ───→ 07
```

（`01`/`02`/`03` 全程无阻塞，是本 effort 的 frontier；`07` 是唯一的收口票，必须等 `04`/`05`/`06` 都落地才能改判 GAP 台账。）

## 每个 Wave 结束后的 `/code-review` 循环

1. **Wave 开工前**打一个标记：`git tag pre-m4-channels-spawn-quest-wave{N}-start`（如 `pre-m4-channels-spawn-quest-wave1-start`）。这是 `/code-review` 的"fixed point"。
2. 在**新 session** 里用下方"Wave 提示词模板"跑 `/implement`，实现该 wave 全部票（每票单独 commit，便于 `/code-review` 报告能对应到具体票）。
3. 实现完成后跑：`/code-review`，fixed point 填 `pre-m4-channels-spawn-quest-wave{N}-start`，spec 来源填 [spec.md](spec.md)（以及本 wave 涉及的具体 issue 文件路径，`/code-review` 技能会自己去读）。
4. 根据 `/code-review` 的 Standards 轴与 Spec 轴报告修 fix；fix 完成后跑一次 `just test`（engine 全量测试套件）确认绿，再进入下一个 wave（重新打 `pre-m4-channels-spawn-quest-wave{N+1}-start` tag）。
5. **止损线**（对齐 [07 号治理票](../mvp-scope/issues/07-governance-cost-tracking.md)）：若某一票实际工作量超预估 3 倍，停下来重估范围——先怀疑是不是做进了 spec「Out of Scope」的东西，再考虑真的拆票（拆出的新票记进该票 Comments，不要私自扩大本 effort 范围）。若单 session 接近 smart zone（~120K token）还没做完且无进展信号，`/handoff`（记录到 PROGRESS.md 的 In Progress，下一 session 接续）。

## Wave 提示词模板（复制进新 session）

> 所有模板都假设新 session 已经 `cd` 到仓库根目录。第一步统一是切到/新建工作分支（本效唯一分支，全程复用，不要为每个 wave 新开分支）。

### Wave 1

```
先 git fetch，若本地没有 feat/pre-m4-channels-spawn-quest 分支，git checkout -b feat/pre-m4-channels-spawn-quest origin/feat/pre-m4-channels-spawn-quest；
若本地已有则 git checkout feat/pre-m4-channels-spawn-quest 并确保是最新。全程不要在 master 上改代码。

打 fixed point：git tag pre-m4-channels-spawn-quest-wave1-start（已存在则跳过）。

用 /implement 技能实现以下三张票（互不阻塞，可任意顺序或并行处理）：
.scratch/pre-m4-channels-spawn-quest/issues/01-give-command.md
.scratch/pre-m4-channels-spawn-quest/issues/02-room-objects-placement.md
.scratch/pre-m4-channels-spawn-quest/issues/03-per-session-mailbox.md

开工前请先读 .scratch/pre-m4-channels-spawn-quest/spec.md 的 Implementation Decisions 全文（不长，三段：
Channel 与假多人 / 房间 objects 与槏位补刷 / Quest）与 docs/adr/0010-room-centric-objects-placement.md
（02 号票的放置模型决策已经拍板，不要在实现时重开）。

02 号票是 04/06 两张后续票的前置依赖（房间 objects 的写法与加载器改动会被下游直接复用）；
03 号票是 05 号票的前置依赖（按会话收件箱是 Channel 跨会话投递的地基）。请确保这两票的对外行为
（scene_loader 报错文案、World 消息投递 API 形状）稳定下来、测试全绿后再收尾。

每票单独 commit（commit message 引用票号，如 "pre-m4-channels-spawn-quest-01: give 命令"）。
每票完成后把该票 issue 文件顶部 Status 改成 resolved，并在文件末尾 ## Comments 补一句实现摘要。
全部完成后跑一次 engine 全量测试套件（just test）确认绿，不要跑 /code-review（等这个 wave 走完
code-review 环节再继续）。
```

### Wave 2

```
在分支 feat/pre-m4-channels-spawn-quest 上（确认已经完成 Wave 1 并通过 code-review fix），
打 fixed point：git tag pre-m4-channels-spawn-quest-wave2-start（已存在则跳过）。

用 /implement 技能实现以下三张票：
.scratch/pre-m4-channels-spawn-quest/issues/04-item-npc-slot-respawn.md（阻塞于 02，已在 Wave 1 落地）
.scratch/pre-m4-channels-spawn-quest/issues/05-channel-chat-system.md（阻塞于 03，已在 Wave 1 落地）
.scratch/pre-m4-channels-spawn-quest/issues/06-quest-state-machine.md（阻塞于 01、02，均已在 Wave 1 落地）

这三张票彼此不互相阻塞，只依赖 Wave 1 产出，可并行或任意顺序处理。06 号票的完成结算钩子直接挂在
01 号票的 give 命令上，实现前确认 give 命令的成功/失败路径签名没有被 04 号票的槏位补刷改动波及
（两票理论上不touch同一段代码，但都会改 scene_loader/ai.py，建议先做完 04 再做 06，减少合并冲突）。

每票单独 commit。每票完成后把该票 issue 文件 Status 改 resolved，## Comments 补实现摘要。
全部完成后跑一次全量测试套件确认绿。
```

### Wave 3（收口）

```
在分支 feat/pre-m4-channels-spawn-quest 上（Wave 1/2 均已 code-review fix 完成），
打 fixed point：git tag pre-m4-channels-spawn-quest-wave3-start（已存在则跳过）。

用 /implement 技能实现 .scratch/pre-m4-channels-spawn-quest/issues/07-closeout-gap-ledger.md
（阻塞于 04、05、06，均应已落地）。

这是本 effort 的最后一张票，以文档改动为主：docs/gap-ledger.md 改判"多人频道/物品 respawn/任务"为
已支持（措辞不越界，不宣称完整多人网游/通用任务引擎）；核对 CONTEXT.md 的 Channel / 房间 objects
放置 / Quest 三条词条与最终实现是否一致，有出入直接回写词条（不新开决策票；若发现偏差大到需要
重新拍板，停下来做一次短 grill 再继续）；核对 .scratch/pre-m4-engine-room-fidelity/ 现有文档未把
放置模型当未决项重开。

完成后：
1. 跑一次全量测试套件（just test）确认没有被文档改动波及；
2. 更新根目录 PROGRESS.md：Done 滑动窗口追加本次 effort 收口条目（超出 5 条的旧条目移进
   .scratch/progress-archive.md）、Next Up 把"Pre-M4 频道/spawn/任务"这条历史条目划掉，
   参照 spec.md「Further Notes」与根 PROGRESS.md「Next Up」现有第 2/3 条，决定下一步是推进
   Pre-M4 引擎房间保真还是评估开 M4；
3. 不要合并回 master（除非用户明确要求），完成后停在这里等待用户 review。
```

## 参考文档索引

- 规格源：[spec.md](spec.md)（本次拆票的直接依据）
- grill 底稿：[session-notes-2026-07-22.md](session-notes-2026-07-22.md)、[grill-paused-2026-07-22.md](grill-paused-2026-07-22.md)
- 频道调研：[research-channels-lpc-2026-07-22.md](research-channels-lpc-2026-07-22.md)
- 放置模型决策：[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)；停机门闩澄清：[ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)
- 项目宪法：[CLAUDE.md](../../CLAUDE.md)
- 治理止损线：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- `implement-plan` 格式 precedent：[m2-mvp-scene-playable/implement-plan.md](../m2-mvp-scene-playable/implement-plan.md)、[m3-hardening/implement-plan.md](../m3-hardening/implement-plan.md)
- 跨 session 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 完成后），在 PROGRESS.md 的 Done 滑动窗口追加一条（格式对照现有条目：`**标题**（日期）：简述 + 链接`），标题建议用 `Pre-M4 频道/spawn/任务 Wave{N} 落地：<该 wave 主题一句话>`。
- **In Progress** 在每个 wave 开工时更新为当前 wave 编号与票号范围；wave 结束清空。
- **Next Up** 始终保持"下一个待做的 wave 编号"，只做简单引用（当前 Wave 编号 + 指回本文件），不要把整段提示词搬回 PROGRESS.md。
- 只有 Wave 3（`07` 号票）完成时才把"Pre-M4 频道/spawn/任务"这条 Next Up 历史条目划掉，换成房间保真或 M4 评估相关待办——且换之前需要用户对照 [06](../mvp-scope/issues/06-scaling-commercialization-support-points.md)/[07](../mvp-scope/issues/07-governance-cost-tracking.md) 号治理票明确拍板，不能因为本效做完就自动滑入 M4。
- 若某 wave 中途因为止损线触发被迫拆票/重估范围，在 PROGRESS.md 的 Blocked 区块记录一行，说明具体是哪张票、为什么超预估、下一步计划，不要只在票据 Comments 里记而不同步到 PROGRESS.md。
