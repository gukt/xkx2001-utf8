# M3 实现计划：Wave 拆分 + /implement → /code-review → fix 循环

> 本文件是 5 张票（[issues/](issues/)）的执行手册，供你在**新 session** 里按 wave 逐批推进。拆票逻辑与设计决策见 [to-tickets-notes.md](to-tickets-notes.md)；spec 原文见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：建议新开 `feat/m3-ugc-loop-creation-surface`（从当前 `master`/`feat/m2-mvp-scene-playable` 视你上次会话决定合并与否而定——若 M2 分支尚未合并 `master`，先跟用户确认 M3 从哪个分支切出，不要默认假设）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前，重新对照 [spec.md](spec.md) 开头的"范围校准"段与 [.scratch/mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md) 的 M3 里程碑定义——"打通一次"，不是"搭一套平台"。本计划规模明显小于 [M2 implement-plan.md](../m2-mvp-scene-playable/implement-plan.md)（5 票 vs 26 票），这是里程碑定义本身决定的，**不是**遗漏遗漏后需要在实现阶段"顺手补全"的信号；实现时如果发现某个 wave 的工作量远超预期，先停下来对照 [07 号票](../mvp-scope/issues/07-governance-cost-tracking.md) 的止损线（单票超预估 3 倍强制重估），大概率是不小心把 Out of Scope 里明确排除的东西又做进去了，回去核对 [spec.md](spec.md) 的 Out of Scope 一节与 [to-tickets-notes.md](to-tickets-notes.md) 的"未纳入本次拆票范围"一节，而不是继续往前赶。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 0 | `01` | manifest 纯函数地基：`PackManifest` + `load_manifest` + `PackManifestError` | 单票，无并行 |
| 1 | `02` | `load_pack` 组合入口 + `World.pack_manifest` + restore 后重挂 | 单票，依赖 Wave 0 |
| 2 | `03`, `04` | CLI `--pack`/`--validate` 接口 + 非武侠示例包内容 | 两票均只依赖 Wave 1，可并行 |
| 3 | `05` | 收口：端到端剧本测试 + `verify-m3` 转录 + 里程碑文档更新 | 依赖 Wave 2 全部完成，单票 |

依赖图（→ 表示"被…阻塞"）：

```
01 → 02 → 03 ─┐
         └→ 04 ┴→ 05
```

（`03`/`04` 都只依赖 `02`，彼此不互相依赖，`05` 依赖两者都完成。）

## 每个 Wave 结束后的 /code-review 循环

1. **Wave 开工前**打一个标记：`git tag m3-wave{N}-start`（如 `m3-wave0-start`）。这是 `/code-review` 的"fixed point"。
2. 在**新 session** 里用下方"Wave 提示词模板"跑 `/implement`，实现该 wave 全部票（每票单独 commit，便于 `/code-review` 报告能对应到具体票）。
3. 实现完成后跑：`/code-review`，fixed point 填 `m3-wave{N}-start`，spec 来源填 `.scratch/m3-ugc-loop-creation-surface/spec.md`（以及本 wave 涉及的具体 issue 文件路径，`/code-review` 技能会自己去读）。
4. 根据 `/code-review` 的 Standards 轴与 Spec 轴报告修 fix；fix 完成后再跑一次 `just` 测试矩阵确认绿，然后进入下一个 wave（重新打 `m3-wave{N+1}-start` tag）。
5. **止损线**（对齐 [07 号票治理](../mvp-scope/issues/07-governance-cost-tracking.md)）：若某一票实际工作量超预估 3 倍，停下来重估范围，不要硬撑做完——先怀疑是不是做进了 Out of Scope 的东西（本计划的规模本身就该很小），再考虑真的拆票。若单 session 接近 smart zone（~120K token）还没做完且无进展信号，`/handoff`（记录到 PROGRESS.md 的 In Progress，下一 session 接续）。

## Wave 提示词模板（复制进新 session）

> 所有模板都假设新 session 已经 `cd` 到仓库根目录且已经 `git checkout` 到 M3 工作分支。

### Wave 0

```
在 M3 工作分支上，用 /implement 技能实现 .scratch/m3-ugc-loop-creation-surface/issues/01-pack-manifest-loading.md 这一张票。
开工前请先读 .scratch/m3-ugc-loop-creation-surface/spec.md 的 Implementation Decisions「A1/A2/A3」段
与 .scratch/m3-ugc-loop-creation-surface/to-tickets-notes.md「拆分原则」第 2 条。
这是一张纯数据/纯函数票，不涉及 World/scene_loader/CLI，建议用 /tdd 直接对 load_manifest 做红绿重构。
完成后单独 commit（commit message 引用票号，如 "M3-01: 内容包 manifest 加载与校验"）。
跑一次 engine 全量测试套件确认绿，不要跑 /code-review（等我在这个 wave 走完 code-review 环节再继续）。
```

### Wave 1

```
在 M3 工作分支上（确认已经完成 Wave 0 并通过 code-review fix），用 /implement 技能实现
.scratch/m3-ugc-loop-creation-surface/issues/02-load-pack-and-world-wiring.md 这一张票。
开工前请先读 spec.md 的 Implementation Decisions「B1/B2」段与 to-tickets-notes.md「关键设计决策」第 1、2 条
（尤其第 1 条："pack_manifest 不进存档、restore 后从 scene_path 旁边重读"这条决策的依据，不要在实现时又反过来扩展
save.py 的持久化格式——这条决策已经确认过是有意为之的简化，不是遗漏）。
本票验收标准里有一条"save.py 未被本票改动"，实现完成后请自行核对一遍再提交。
commit 单独一条。跑一次全量测试套件确认绿。
```

### Wave 2

```
在 M3 工作分支上（Wave 0/1 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m3-ugc-loop-creation-surface/issues/03-cli-pack-pointing-and-validate.md 与
04-example-pack-derelict-outpost.md 这两张票。两票均只依赖 02（已完成），彼此独立，
可以任意顺序或并行处理（如果分两个 session 并行推进，注意 04 号票的验收依赖"用 02 号票的 load_pack
手动验证一次"，不依赖 03，可以完全独立于 03 的进展）。

03 号票开工前请先读 spec.md 的 Implementation Decisions「C1」段与 to-tickets-notes.md「关键设计决策」第 3、4 条
（--pack 不支持隐式路径推断、--validate 不支持脱离 --pack 单独使用，两条都是明确排除，不是待定项）。

04 号票开工前请先读 spec.md 的 Implementation Decisions「D1」段与 to-tickets-notes.md「关键设计决策」第 5 条。
这是一张纯内容票，验收标准第一条就是"不改动 engine/src/mud_engine/ 下任何一个模块"——如果实现过程中发现不改引擎代码
写不出想要的效果，请先简化场景设计或换一个非武侠故事，而不是回头改引擎代码；若确实存在真正的表达力缺口（不是文案/命名
喜好问题），按票据要求记一条 GAP 说明在 Comments 里，不要借机新增引擎能力。

每票单独 commit。全部完成后跑一次全量测试套件确认绿。
```

### Wave 3（收口）

```
在 M3 工作分支上（Wave 0-2 均已 code-review fix 完成），用 /implement 技能实现
.scratch/m3-ugc-loop-creation-surface/issues/05-e2e-verification-and-docs.md（端到端剧本测试 +
verify-m3 转录 + 里程碑文档更新）。这是 M3 里程碑的收口票，完成后请：
1. 确认 .scratch/mvp-scope/issues/07-governance-cost-tracking.md 定义的 M3 里程碑
   （"UGC 创作闭环打通一次，走完创作→加载→可玩全流程"）达成；
2. 更新根目录 PROGRESS.md：Done 滑动窗口追加本次 M3 收口条目（超出 5 条的旧条目移进
   .scratch/progress-archive.md）、Next Up 更新为 M4 相关待办（对照 07 号票的 M4 定义：
   "商业化支撑点的数据模型落地，不要求真实计费"）、当前状态速览一行更新为 M3 完成；
3. 如实现细节与 ADR-0005 原描述有出入，在该 ADR 补一条修订记录（不改判 Status）；
4. 不要合并回 master（除非用户明确要求），完成后停在这里等待用户 review。
```

## 提前开工的并行机会（可选，不强制）

若想在两个 session 里同时推进 Wave 2，`03`（CLI）与 `04`（示例包内容）彼此没有依赖关系，可以直接拆给两个并行 session；`04` 号票的验收只需要 `02` 号票交付的 `load_pack` 函数本身，不需要等 `03` 号票的 CLI 层落地。**不建议**进一步并行 `01`/`02`——两者是严格的顺序依赖（`02` 直接调用 `01` 交付的函数），拆给两个 session 只会增加协调成本，没有真实并行收益。

## 参考文档索引

- 规格源：[spec.md](spec.md)（本次拆票的直接依据）
- 拆票分析记录：[to-tickets-notes.md](to-tickets-notes.md)
- 项目宪法：[CLAUDE.md](../../CLAUDE.md)（架构不变量全 8 条，尤其第 5 条）
- UGC 创作面边界：[ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md)、[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)
- M3 创作闭环最小切片原始决定：[mvp-scope/issues/03-ugc-dsl-design-inheritance.md](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md)
- 里程碑定义与治理止损线：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- 商业化支撑点（manifest 简化版依据）：[mvp-scope/issues/06-scaling-commercialization-support-points.md](../mvp-scope/issues/06-scaling-commercialization-support-points.md)
- M2 技术地基与票据写法 precedent：[m2-mvp-scene-playable/spec.md](../m2-mvp-scene-playable/spec.md)、[m2-mvp-scene-playable/to-tickets-notes.md](../m2-mvp-scene-playable/to-tickets-notes.md)、[m2-mvp-scene-playable/issues/](../m2-mvp-scene-playable/issues/)
- 跨 session 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 完成后），在 PROGRESS.md 的 Done 滑动窗口追加一条（格式对照现有条目：`**标题**（日期）：简述 + 链接`），标题建议用 `M3 Wave{N} 落地：<该 wave 主题一句话>`。
- **In Progress** 在每个 wave 开工时更新为当前 wave 编号与票号范围；wave 结束清空。
- **Next Up** 始终保持"下一个待做的 wave 编号"在第一条。
- 只有 `05` 号票（Wave 3）完成时才把"M3 `/to-spec` + `/to-tickets`"这条 Next Up 历史条目彻底划掉，换成 M4 相关待办。
- 若某 wave 中途因为止损线触发被迫拆票/重估范围，在 PROGRESS.md 的 Blocked 区块记录一行，说明具体是哪张票、为什么超预估、下一步计划——鉴于本里程碑刻意做小，任何一票"超预估 3 倍"大概率意味着不小心做进了 Out of Scope 的东西，记录时请顺带写明是否属于这种情况。
