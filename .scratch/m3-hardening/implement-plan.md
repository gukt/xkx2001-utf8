# M3 停机加固实现计划：Wave 拆分 + `/implement` → `/code-review` → fix 循环

> 本文件是 11 张票（[issues/](issues/)）的执行手册，供你在**新 session** 里按 wave 逐批推进。拆票逻辑与设计决策见 [to-tickets-notes.md](to-tickets-notes.md)；spec 原文见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：延用当前工作分支 `feat/m3-ugc-loop-creation-surface`（M3 UGC 闭环已在此分支落地并全绿，本次加固是同一里程碑的收口窗口，不需要另开分支；若用户在新 session 里决定切一个专门的加固分支，先跟用户确认再动手，不要默认假设）。
>
> **核心校准**：每个 wave 开工前，重新对照 [spec.md](spec.md) 开头的「范围边界」段——**Wave P0（票 `01`–`07`）全部关闭，才是"M3 停机加固"可对外宣布完成的唯一标准**；**Wave B3（票 `08`–`11`）各项各自关闭即可勾掉，不要求全部关闭才能改写 PROGRESS.md**（这条"两个 wave 关闭方式不同"的规则来自 spec Further Notes 与 CONTEXT.md「M3 停机加固」词条，本计划的 Wave 划分与之对齐：Wave 0/1 = spec Wave P0，Wave 2/3 = spec Wave B3）。若某个 wave 的工作量远超预估（单票超 3 倍，对齐 [07 号治理票](../mvp-scope/issues/07-governance-cost-tracking.md) 止损线），先停下来核对是不是不小心做进了「未纳入本次拆票范围」（见 to-tickets-notes.md 末节）列出的 Out of Scope 项，而不是继续往前赶。

## Wave 总览

| Wave | 票据 | 主题 | 对应 spec wave | 并行度 |
|---|---|---|---|---|
| 0 | `01`, `02`, `03`, `04`, `05` | P0 五张互相独立的实现票：昏迷苏醒 / 持刃门禁 / combat.py 消灭全局态 / wire_runtime / --validate --strict | Wave P0 | 五票互不阻塞，可并行或任意顺序 |
| 1 | `06`, `07` | P0 收尾两张：创作者契约 v0（阻塞于 `05`）/ 票 Status 刷新 + 战斗事件契约测（阻塞于 `03`） | Wave P0 | 两票彼此独立，可并行；**Wave 0+1 全部完成 = Wave P0 门闩关闭** |
| 2 | `08`, `10`, `11` | B3 三张：messaging.py 抽取 / 三条交叉测试（阻塞于 `03`）/ GAP 台账 | Wave B3 | 三票互不阻塞，可并行 |
| 3 | `09` | B3 收尾：官方/示例双轨范本文档（阻塞于 `06`） | Wave B3 | 单票 |

依赖图（→ 表示"被…阻塞"）：

```
01 ─┐
02 ─┤
03 ─┼─→ 07
04 ─┤   03 ─→ 10
05 ─┴─→ 06 ─→ 09

08（独立，可与任意 wave 并行）
11（独立，可与任意 wave 并行）
```

（`01`/`02`/`04` 全程无阻塞；`03` 是 `07`/`10` 的前置；`05` 是 `06` 的前置；`06` 是 `09` 的前置；`08`/`11` 全程无阻塞。）

## 每个 Wave 结束后的 `/code-review` 循环

1. **Wave 开工前**打一个标记：`git tag m3-hardening-wave{N}-start`（如 `m3-hardening-wave0-start`）。这是 `/code-review` 的"fixed point"。**注意**：本 effort 的 tag 前缀是 `m3-hardening-wave{N}-start`，与已存在的 `m3-wave{N}-start`（属于 `m3-ugc-loop-creation-surface` effort）区分,不要混用。
2. 在**新 session** 里用下方"Wave 提示词模板"跑 `/implement`，实现该 wave 全部票（每票单独 commit，便于 `/code-review` 报告能对应到具体票）。
3. 实现完成后跑：`/code-review`，fixed point 填 `m3-hardening-wave{N}-start`，spec 来源填 `.scratch/m3-hardening/spec.md`（以及本 wave 涉及的具体 issue 文件路径，`/code-review` 技能会自己去读）。
4. 根据 `/code-review` 的 Standards 轴与 Spec 轴报告修 fix；fix 完成后跑一次 `just test`（engine 全量测试套件）确认绿，再进入下一个 wave（重新打 `m3-hardening-wave{N+1}-start` tag）。
5. **Wave 1 结束时的额外动作**：Wave P0（票 `01`–`07`）全部关闭，此时才能把 [PROGRESS.md](../../PROGRESS.md) 的当前状态从"M3 停机加固窗口"改写为"可诚实停机"（对照 spec Further Notes 与 CONTEXT.md「M3 停机加固」词条的措辞要求，不要在 Wave P0 未全关时提前改写）。
6. **止损线**（对齐 [07 号治理票](../mvp-scope/issues/07-governance-cost-tracking.md)）：若某一票实际工作量超预估 3 倍，停下来重估范围，先怀疑是不是做进了 Out of Scope 的东西（本计划范围已经很收敛），再考虑真的拆票。若单 session 接近 smart zone（~120K token）还没做完且无进展信号，`/handoff`（记录到 PROGRESS.md 的 In Progress，下一 session 接续）。

## Wave 提示词模板（复制进新 session）

> 所有模板都假设新 session 已经 `cd` 到仓库根目录且已经 `git checkout` 到工作分支。

### Wave 0

```
在 M3 停机加固工作分支上，用 /implement 技能实现以下五张票（互不阻塞，可任意顺序或并行处理）：
.scratch/m3-hardening/issues/01-unconscious-tick-recovery.md
.scratch/m3-hardening/issues/02-shaolin-gate-drop-edged-condition.md
.scratch/m3-hardening/issues/03-combat-round-pure-function.md
.scratch/m3-hardening/issues/04-wire-runtime-unify-attach.md
.scratch/m3-hardening/issues/05-validate-strict-unconsumed-fields.md

开工前请先读 .scratch/m3-hardening/spec.md 的 Implementation Decisions「P0-2/P0-3/P0-4/P0-5/P0-7」段
与 .scratch/m3-hardening/to-tickets-notes.md「关键设计决策」第 1、2 条（04 号票里 wire_runtime 放哪个文件、
commands.py 那处防御性调用怎么处置，都是留给你在实现时读代码后再拍板的,不是遗漏)。

03 号票是 07/10 两张后续票的前置依赖（会 touch 同一段 resolve_attack/SkillBehavior 调用路径），
请确保 03 号票的 SkillBehavior 签名变更与全局态清理完全落地、测试全绿后再收尾这一票。

每票单独 commit（commit message 引用票号，如 "M3-hardening-01: 昏迷 tick 自动苏醒"）。
全部完成后跑一次 engine 全量测试套件（just test）确认绿，不要跑 /code-review（等这个 wave 走完
code-review 环节再继续）。
```

### Wave 1

```
在 M3 停机加固工作分支上（确认已经完成 Wave 0 并通过 code-review fix），用 /implement 技能实现
以下两张票（彼此独立，可并行）：
.scratch/m3-hardening/issues/06-creator-contract-v0.md（阻塞于 05，确认 05 已落地）
.scratch/m3-hardening/issues/07-issue-status-refresh-and-combat-event-contract-tests.md（阻塞于 03，确认 03 已落地）

06 号票开工前请先读 spec.md 的 Implementation Decisions「P0-6」段；07 号票开工前请先读「P0-8」段
与 to-tickets-notes.md「关键设计决策」第 3 条（事件契约测试放哪个文件，看 test_combat_engagement.py
现有长度再决定，不要提前假设）。

这两票完成、code-review fix 通过后，Wave P0（票 01-07）全部关闭——此时请更新 PROGRESS.md 把当前状态
从"M3 停机加固窗口"改写为"可诚实停机"（不要在这之前提前改写这条状态）。

每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 2

```
在 M3 停机加固工作分支上（Wave 0/1 均已 code-review fix 完成，Wave P0 已关闭），用 /implement 技能
实现以下三张票（互不阻塞，可任意顺序或并行处理）：
.scratch/m3-hardening/issues/08-extract-messaging-module.md
.scratch/m3-hardening/issues/10-cross-cutting-integration-tests.md（阻塞于 03，已在 Wave 0 落地）
.scratch/m3-hardening/issues/11-gap-ledger.md

08 号票开工前请先读 spec.md 的 Implementation Decisions「B3-2」段——纯结构性搬家,不改变 room_say
行为或签名。10 号票开工前请先读「B3-4」段,三条交叉测试可以分别独立提交（不要求同一个 commit）。
11 号票是纯文档产出,若此时 06 号票已经落地,请在 docs/creator-contract-v0.md 里补一条反向链接
（to-tickets-notes.md「关键设计决策」第 4 条——这是软提示，不是硬性前提）。

每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 3（收口）

```
在 M3 停机加固工作分支上（Wave 0-2 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m3-hardening/issues/09-scene-authoring-two-tracks-doc.md（阻塞于 06，确认 06 已落地）。

这是本次加固 Wave B3 的最后一张票，开工前请先读 spec.md 的 Implementation Decisions「B3-3」段。
完成后：
1. 确认 Wave B3（票 08-11）状态——B3 不要求全部关闭才能改写 PROGRESS.md（与 Wave P0 的关闭标准不同），
   若 08/10/11 也已完成，一并勾掉；
2. 更新根目录 PROGRESS.md：Done 滑动窗口追加本次加固收口条目（超出 5 条的旧条目移进
   .scratch/progress-archive.md）、Next Up 参照 spec.md「Further Notes」最后一段的提醒
   （对照 06 号票的 06/07 号 mvp-scope 治理票，决定是否开 M4）；
3. 不要合并回 master（除非用户明确要求），完成后停在这里等待用户 review。
```

## 提前开工的并行机会（可选，不强制）

- `08`（`messaging.py` 抽取）与 `04`（`wire_runtime`）在 spec Further Notes 里被明确点名"都是纯结构性重构，互相独立，可以并行"——如果想在两个 session 里同时推进，可以把 `08` 提前拉到 Wave 0 一起做,不需要等到 Wave 2。本计划把 `08` 放在 Wave 2 是为了让 Wave 0/1（Wave P0）先形成一个清晰的"停机门闩"收口节奏,不是因为存在真实阻塞。
- `11`（GAP 台账）全程无阻塞,同理可以提前到任意 wave 插空做,只要注意"若 06 已完成，补链接"这条软提示——如果 `11` 早于 `06` 完成,补链接这一步留到 `06`/`09` 落地后再补一次 commit 即可，不影响 `11` 本身的验收。
- **不建议**打乱 `03→07`、`03→10`、`05→06`、`06→09` 四条真实阻塞边——这些是 Further Notes 与 spec 明确指出的"同一段代码/同一份文档会被两张票依次 touch"关系，拆给两个并行 session 反而会增加协调成本。

## 参考文档索引

- 规格源：[spec.md](spec.md)（本次拆票的直接依据）
- 拆票分析记录：[to-tickets-notes.md](to-tickets-notes.md)
- 项目宪法：[CLAUDE.md](../../CLAUDE.md)（架构不变量全 8 条，尤其第 8 条推进治理）
- 拍板依据：[评审 Final 报告](../m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](../../docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](../../CONTEXT.md)「M3 停机加固」词条
- `/to-tickets`/`implement-plan` 格式 precedent：[m3-ugc-loop-creation-surface/to-tickets-notes.md](../m3-ugc-loop-creation-surface/to-tickets-notes.md)、[m3-ugc-loop-creation-surface/implement-plan.md](../m3-ugc-loop-creation-surface/implement-plan.md)
- M4 是否开工的判断依据：[mvp-scope/issues/06-scaling-commercialization-support-points.md](../mvp-scope/issues/06-scaling-commercialization-support-points.md)、[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- 跨 session 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 完成后），在 PROGRESS.md 的 Done 滑动窗口追加一条（格式对照现有条目：`**标题**（日期）：简述 + 链接`），标题建议用 `M3 停机加固 Wave{N} 落地：<该 wave 主题一句话>`。
- **In Progress** 在每个 wave 开工时更新为当前 wave 编号与票号范围；wave 结束清空。
- **Next Up** 始终保持"下一个待做的 wave 编号"在第一条。
- **Wave 1 结束（Wave P0 全关）**是唯一允许把 PROGRESS.md 当前状态改写为"可诚实停机"的时点；Wave 2/3（Wave B3）结束不改变这条状态措辞，只是各自勾掉对应票。
- 只有 Wave 3（`09` 号票）完成时才考虑是否要把"M3 停机加固"这条 Next Up 历史条目换成 M4 相关待办——且换之前需要用户对照 [06](../mvp-scope/issues/06-scaling-commercialization-support-points.md)/[07](../mvp-scope/issues/07-governance-cost-tracking.md) 号治理票明确拍板是否开 M4（spec 与 PROGRESS.md 均已写明这是一次独立决策，不能因为 B3 做完就自动滑入 M4）。
- 若某 wave 中途因为止损线触发被迫拆票/重估范围，在 PROGRESS.md 的 Blocked 区块记录一行，说明具体是哪张票、为什么超预估、下一步计划——鉴于本次加固范围已经跟评审报告逐条对齐，任何一票"超预估 3 倍"大概率意味着不小心做进了 Out of Scope 的东西，记录时请顺带写明是否属于这种情况。
