# M2 实现计划：Wave 拆分 + /implement → /code-review → fix 循环

> 本文件是 26 张票（[issues/](issues/)）的执行手册，供你在**新 session**里按 wave 逐批推进。拆票逻辑与设计决策见 [to-tickets-notes.md](to-tickets-notes.md)；spec 原文见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：全部工作在 `feat/m2-mvp-scene-playable`（已从 `master` 切出）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前，重新对照 [CLAUDE.md](../../CLAUDE.md) 的"项目一句话"（题材无关核心引擎 + UGC 创作层 + 官方轻量武侠题材包）与 ADR-0004（骨架固定 + 钩子策略注入）——尤其是 Wave 0–3（机制层）的每个新组件/命令，验收时都要能回答"这条机制如果换一个题材包（非武侠）还成立吗，具体数值/文案是不是都在题材包侧（YAML/纯数据参数）而不是硬编码在引擎侧"。Wave 4（场景内容）才是武侠题材包本身，允许硬编码武侠具体设定。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 0 | `01`,`02`,`03`,`04` | 地基：注册表 prefactor + 战斗算法核心 + 技能数据地基 + spawner 修复 | 4 票互相独立，全并行 |
| 1 | `05`,`06`,`07`,`08`,`09` | 核心组件与机制：角色成长 / 死亡状态机 / 货币商店 / 门派框架 / 渡船 | 5 票只依赖 Wave 0，全并行 |
| 2 | `10`,`11`,`12`,`13`,`14` | 组合与接线：坐骑购买 / 门槏校验 / 战斗真实接线 / practice / learn | 5 票依赖关系见下方依赖图，部分可并行 |
| 3 | `15`,`16`,`17`,`18`,`19`,`20` | 收尾机制：地形限制 / 技能钩子 / 死亡流程 / NPC 死亡重生 / aggro / 同名消歧 | 6 票均只依赖 Wave 2 产出，全并行 |
| 4 | `21`,`22`,`23`,`24`,`25` | 题材包内容：六个场景分区 | 依赖已闭合的可提前开工（见下方"提前开工"提示），否则全并行 |
| 5 | `26` | 收口：六分区互联 + 端到端剧本测试 + 更新 PROGRESS.md | 依赖 Wave 4 全部完成，单票 |

依赖图（→ 表示"被…阻塞"）：

```
01 ─┬→ 05 ─┬→ 12 ─┬→ 13
    ├→ 06 ─┼→ 17  ├→ 14
    ├→ 07 ─┼→ 10 ─┼→ 15
    ├→ 08 ─┼→ 11  ├→ 16
    └→ 09 ─┘       ├→ 18
02 ────────→ 12     ├→ 19
03 ────────→ 12,13,14,16   └→ 20
04 ────────────────────────→ 18

15,16,17,18,19,20 → 21,22,23,24,25 → 26
```

（`02`/`03`/`04` 是 Wave 0 的另外三票，箭头指向它们各自解锁的下游；完整逐票 Blocked-by 请直接读对应 issue 文件，此图仅示意宏观结构。）

## 每个 Wave 结束后的 /code-review 循环

1. **Wave 开工前**打一个标记：`git tag m2-wave{N}-start`（如 `m2-wave0-start`）。这是 `/code-review` 的"fixed point"（skill 要求"the user supplies"，用 wave 起点 tag 最省心，不需要每次手动找 commit SHA）。
2. 在**新 session** 里用下方"Wave 提示词模板"跑 `/implement`，实现该 wave 全部票（可对每票单独 commit，也可以整个 wave 一次性 commit——建议每票一个 commit，便于 `/code-review` 报告能对应到具体票）。
3. 实现完成后跑：`/code-review`，fixed point 填 `m2-wave{N}-start`，spec 来源填 `.scratch/m2-mvp-scene-playable/spec.md`（以及本 wave 涉及的具体 issue 文件路径，`/code-review` 技能会自己去读）。
4. 根据 `/code-review` 的 Standards 轴与 Spec 轴报告修 fix；fix 完成后再跑一次 `just` 测试矩阵确认绿，然后进入下一个 wave（重新打 `m2-wave{N+1}-start` tag）。
5. **止损线**（对齐 [07 号票治理](../mvp-scope/issues/07-governance-cost-tracking.md)）：若某一票实际工作量超预估 3 倍，停下来重估范围，不要硬撑做完——可以把票拆成两张（原票 + 一张"遗留收尾"新票），记录在该票的 Comments 里。若单 session 接近 smart zone（~120K token）还没做完且无进展信号，`/handoff`（记录到 PROGRESS.md 的 In Progress，下一 session 接续）。

## Wave 提示词模板（复制进新 session）

> 每个模板里的 `{N}`/票号范围按实际 wave 替换。所有模板都假设新 session 已经 `cd` 到仓库根目录且已经 `git checkout feat/m2-mvp-scene-playable`。

### Wave 0

```
在分支 feat/m2-mvp-scene-playable 上，用 /implement 技能实现 .scratch/m2-mvp-scene-playable/issues/01-room-npc-capability-registries.md、
02-combat-resolution-core.md、03-skill-data-registry-and-behavior-protocol.md、04-spawner-registry-fix.md 这四张票。
这四张票彼此独立无依赖，可以按任意顺序实现。开工前请先读 .scratch/m2-mvp-scene-playable/spec.md 的 Implementation Decisions
「H1/A1/A2/A3/B1/C2」相关段落与 .scratch/m2-mvp-scene-playable/to-tickets-notes.md 的「关键设计决策」部分（尤其第 1、2 条）。
每张票请优先用 /tdd 在票据标注的纯函数/命令层 seam 上做红绿重构；实现完成后每票单独 commit，
commit message 引用票号（如 "M2-02: 战斗结算核心 CombatContext+resolve_attack+PowerModel"）。
全部完成后跑一次 engine 全量测试套件确认绿，不要跑 /code-review（等我在这个 wave 走完 code-review 环节再继续）。
```

### Wave 1

```
在分支 feat/m2-mvp-scene-playable 上（确认已经完成 Wave 0 并通过 code-review fix），用 /implement 技能实现
.scratch/m2-mvp-scene-playable/issues/05-character-growth-components.md、06-death-state-machine-core.md、
07-currency-and-shop.md、08-faction-framework-and-join.md、09-ferry-dynamic-exits.md 这五张票。
这五张票都只依赖 01 号票（已完成），彼此独立、可并行/任意顺序实现。注意 08 号票"是否允许换门派"这类没钉死细节的地方，
按票据要求"决定一个明确策略并写进代码注释"，不要留成未定义行为。每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 2

```
在分支 feat/m2-mvp-scene-playable 上（Wave 0/1 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m2-mvp-scene-playable/issues/10-mount-and-riding-with-purchase.md、11-entry-guard-and-gate-context.md、
12-combat-engagement-commands.md、13-skill-practice-command.md、14-faction-skill-learning.md 这五张票。
建议实现顺序：先 12（战斗真实接线，13/14 的验证更方便有真实战斗环境，但 13/14 本身不强制依赖 12）；
10 依赖 07（已完成）；11 依赖 08（已完成）。12 号票是本 wave 复杂度最高的票（战斗 tick 调度 + attack/flee 命令 + 三个事件点），
如果单 session 处理不完，可以先完整实现 12 号票并 code-review fix 一轮，再单独开一个 session 做 10/11/13/14。
每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 3

```
在分支 feat/m2-mvp-scene-playable 上（Wave 0/1/2 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m2-mvp-scene-playable/issues/15-terrain-and-mount-limits.md、16-skill-behavior-hook-wiring.md、
17-death-flow-wiring.md、18-npc-death-and-respawn-flow.md、19-aggro-behavior.md、20-same-name-target-disambiguation.md 这六张票。
六票均只依赖 Wave 2 产出（已完成），彼此独立可并行。特别注意 17 号票：请同时处理
.scratch/m2-mvp-scene-playable/to-tickets-notes.md「关键设计决策」第 4 条点名的"昏迷态命令行为限制"缺口
（06 号票刻意没做，17 号票是补上的正确位置）。20 号票涉及 Intent/matching 的架构性改动，实现前先确认不会破坏
现有 test_matching.py/test_parsing.py 的无序号场景测试。每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 4

```
在分支 feat/m2-mvp-scene-playable 上（Wave 0-3 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m2-mvp-scene-playable/issues/21-scene-huashan-village.md、22-scene-yangzhou-hub-and-gates.md、
23-scene-yangzhou-commerce-and-stable.md、24-scene-shaolin-temple.md、25-scene-wild-road-and-ferry.md 这五张场景内容票。
这批是"题材包内容"（武侠具体设定），不是引擎机制——可以放心硬编码武侠具体数值/文案。开工前读一遍
.scratch/mvp-scope/issues/10-mvp-scenes-selection.md（场景清单原始拍板文本，各票的验收清单直接对照它，不要自己另起一套房间清单）。
22 号票与 23 号票共用 yangzhou_* 房间键命名空间，实现顺序不重要但要互相检查键不冲突（建议先扫一遍两张票各自
要新建的房间键清单，写进一个共享的临时笔记）。每票单独 commit。全部完成后跑一次全量测试套件 + just verify-* 全套确认绿。
```

### Wave 5（收口）

```
在分支 feat/m2-mvp-scene-playable 上（Wave 4 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m2-mvp-scene-playable/issues/26-scene-integration-and-e2e-script.md（六分区互联 + 端到端剧本测试）。
这是 M2 里程碑的收口票，完成后请：
1. 确认 .scratch/mvp-scope/issues/07-governance-cost-tracking.md 定义的 M2 里程碑（"一个 MVP 场景端到端可玩"）达成；
2. 更新根目录 PROGRESS.md：Done 滑动窗口追加本次 M2 收口条目（超出 5 条的旧条目移进 .scratch/progress-archive.md）、
   Next Up 更新为 M3 相关待办（对照 CLAUDE.md 待办清单"M3 前核对 03-ugc-dsl-design-inheritance 编辑器系统归类"）、
   当前状态速览一行更新为 M2 完成；
3. 不要合并回 master（除非用户明确要求），完成后停在这里等待用户 review。
```

## 提前开工的并行机会（可选，不强制）

若你想在多个 session 里同时推进（而不是严格按 wave 串行），以下票据的**真实**依赖闭合得比其 wave 分组更早，可以提前认领（见 [to-tickets-notes.md](to-tickets-notes.md) 决策 7 的说明）：

- `23`（扬州商业+马厩）真实只依赖 `07`+`10`（Wave 1/2），Wave 2 收尾即可开工，不必等 Wave 3。
- `21`（华山村）真实只依赖 `06`+`12`（Wave 1/2），同理可提前。
- `24`（少林寺）真实只依赖 `08`+`11`+`14`（Wave 1/2），同理可提前。

只有 `22`（依赖 `20`，Wave 3）与 `25`（依赖 `09`/`15`/`18`/`19`，Wave 1/3）严格需要等到 Wave 3 收尾。如果并行开工，注意 `/code-review` 的 fixed point tag 策略需要相应调整（建议仍按 wave 打 tag，提前完成的票在下一个 wave 边界一起 review，不要为了追求极限并行而把 review 切得比票还碎）。

## 参考文档索引

- 规格源：[spec.md](spec.md)（本次拆票的直接依据）
- 拆票分析记录：[to-tickets-notes.md](to-tickets-notes.md)
- 项目宪法：[CLAUDE.md](../../CLAUDE.md)（架构不变量全 8 条）
- 战斗/效果边界：[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md)
- 场景清单原始拍板：[mvp-scope/issues/10-mvp-scenes-selection.md](../mvp-scope/issues/10-mvp-scenes-selection.md)
- 子系统四档归类：[mvp-scope/issues/08-subsystem-classification-research.md](../mvp-scope/issues/08-subsystem-classification-research.md)
- 治理止损线：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- M1 技术地基：[m1-core-engine-skeleton/spec.md](../m1-core-engine-skeleton/spec.md)、[m1-core-engine-skeleton/issues/](../m1-core-engine-skeleton/issues/)（票据写法 precedent）
- 跨 session 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 完成后），在 PROGRESS.md 的 Done 滑动窗口追加一条（格式对照现有条目：`**标题**（日期）：简述 + 链接`），标题建议用 `M2 Wave{N} 落地：<该 wave 主题一句话>`。
- **In Progress** 在每个 wave 开工时更新为当前 wave 编号与票号范围；wave 结束清空。
- **Next Up** 始终保持"下一个待做的 wave 编号"在第一条。
- 只有 `26` 号票（Wave 5）完成时才把"M2 `/to-tickets`"这条 Next Up 历史条目彻底划掉，换成 M3 相关待办（对照 CLAUDE.md 文末的 M3 前核对待办）。
- 若某 wave 中途因为止损线触发被迫拆票/重估范围，在 PROGRESS.md 的 Blocked 区块记录一行，说明具体是哪张票、为什么超预估、下一步计划，不要只在票据 Comments 里记而不同步到 PROGRESS.md（PROGRESS.md 是"跨 session 唯一交接信源"，票据 Comments 是细节，两者不是二选一）。
