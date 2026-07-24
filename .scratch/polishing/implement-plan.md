# Polishing：Wave 拆分 + `/implement` → `/code-review` → fix 循环

> 本文件是 13 张票（[issues/](issues/)）的执行手册，供你在**新 session** 里按 wave 逐批推进。拆票逻辑见 [to-tickets-notes.md](to-tickets-notes.md)；spec 见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：全部工作在 `feat/polishing`（自已合入 master 的 `feat/pre-m4-room-hooks-xingxiu` tip 开出）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前对照 [spec.md](spec.md) 开头「候选 ID 对照表」与「Out of Scope」——13 项**纳入即做**，不得以体量为由后置出本阶段；不做 LPC 行为等价（ADR-0001）；C12 只走官方 hooks `params`、不扩条件 DSL 原语（ADR-0012 边界不变）；C14 先 ADR 再实现；关完**不**自动开 M4。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 1 | `01`, `02` | 出口导航别名 + YAML 简写规范化 | `02` 阻塞于 `01`，同 wave 顺序做 |
| 2 | `03` | 房间风景 details 升级（K2+U+S1+N1） | 单票，体量大独立成 wave |
| 3 | `04`, `05` | `block_exits` 拒走文案 + 步行 `cost` 精力 | 两票互不阻塞 |
| 4 | `06` | 客店三件套（sleep + hotel + pay + 睡房拦练功） | 单票，新命令面较多独立成 wave |
| 5 | `07`, `08` | 条件 DSL 文档化 + 液体/eat/drink | 两票互不阻塞（文档 + 代码配对） |
| 6 | `09`, `10` | 随机 objects 表 + 刷怪条件扩展 | 两票互不阻塞（均落在 spawn/钩子侧） |
| 7 | `11` | 多文件路径引用 `includes` | 单票，加载器改动体量大独立成 wave |
| 8 | `12` | 局部天气继承 ADR | 单票，仅文档，无阻塞——**可提前插队**（见下方并行机会） |
| 9 | `13` | 局部天气继承实现 | 阻塞于 `12`；具体模块以 ADR 结论为准 |

依赖图（→ 表示「被…阻塞」）：

```
01 → 02
03（无阻塞）
04（无阻塞）
05（无阻塞）
06（无阻塞）
07（无阻塞）
08（无阻塞）
09（无阻塞）
10（无阻塞）
11（无阻塞）
12 → 13
```

（除 `02` 阻塞于 `01`、`13` 阻塞于 `12` 外，其余 9 票彼此互不阻塞。Wave 分组是为了控制单 session 体量与 `/code-review` 粒度，不代表票据间真实阻塞——见下方「提前开工的并行机会」。）

## 每个 Wave 结束后的 `/code-review` 循环

1. **Wave 开工前**打标记：`git tag polishing-wave{N}-start`（如 `polishing-wave1-start`）。这是 `/code-review` 的 fixed point。
2. 在**新 session**用下方提示词跑 `/implement`（建议每票单独 commit）。
3. 完成后跑 `/code-review`，fixed point 填上表 tag，spec 填 [spec.md](spec.md) + 本 wave 的 issue 路径。
4. 按 Standards / Spec 两轴修 fix；再跑 `just test` 确认绿，然后进入下一 wave。
5. **止损线**（对齐 [mvp-scope 07](../mvp-scope/issues/07-governance-cost-tracking.md)）：单票工作量超预估 3 倍 → 重估；13 项**纳入即做**，止损只能改工作量估计/拆更细票，不能把票踢出本阶段。单 session 近 smart zone（~120K）无进展 → `/handoff` 写回 PROGRESS In Progress。

## Wave 提示词模板（复制进新 session）

> 假设已 `cd` 到仓库根。全程复用本 effort 分支，不要为每个 wave 新开分支。

### Wave 1

```
先确认分支：git checkout feat/polishing（没有则从当前 master tip 创建并跟踪）。
不要在 master 上改代码。

打 fixed point：git tag polishing-wave1-start（已存在则跳过）。

用 /implement 依次实现（02 阻塞于 01，按顺序做，不要并行）：
.scratch/polishing/issues/01-exit-navigation-aliases.md
.scratch/polishing/issues/02-yaml-shorthand-normalization.md

开工前读：
- .scratch/polishing/spec.md 的 Implementation Decisions「A1+A2」「A3」
- CONTEXT.md「出口导航别名」词条（权威规格摘要）
- engine/src/openmud/parsing.py（现有 DIRECTION_SHORTCUTS）

注意：
- 出口 token 解析必须走「① 出口 aliases → ② 目标房 name/aliases → ③ 方向键内置同义词」三层顺序，_cmd_go 与 look 展示复用同一套候选解析，不要各写一套判定逻辑。
- 裸中文方位/裸中文地名必须拒绝（须带 go），区分「不认识」与「须带 go」两种拒绝原因。
- 01 落地并 just test 全绿后才开 02（02 依赖 01 的内置同义词表清理范本，顺序不能反）。

每票单独 commit（message 引用票号，如 "polishing-01: 出口导航别名"）。
每票完成后把 issue Status 改 resolved，## Comments 补实现摘要（内置同义词表结构、去重策略选定方案）。
全部完成后 just test 全绿；不要跑 /code-review（等本 wave 统一 review）。
```

### Wave 2

```
在分支 feat/polishing 上（Wave 1 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave2-start（已存在则跳过）。

用 /implement 实现：
.scratch/polishing/issues/03-room-scenery-details-upgrade.md

开工前读：
- .scratch/polishing/spec.md 的 Implementation Decisions「A4」
- CONTEXT.md「房间风景」词条（权威规格：K2+U+S1+N1）
- engine/tests/test_room_details.py（现有 details 测试范式）

注意：
- RoomDetails 从 dict[str, str] 升级为 dict[str, DetailEntry] 时，旧「键→纯字符串」写法要有明确兼容/迁移路径（本票钉死：自动转换为 {text: 值, aliases: [键]}）。
- 归一 N1（空格/_/-/全粘连同一骨架）与 S1 安全阀（仅命中已登记 details 才判定可 look）都要落地测试矩阵，不能只测 happy path。
- 不引入 <d:…> 等标签；不从 long 里自动解析并登记 aliases（真·括号语法解析，本波明确不做）。

完成后 commit；Status→resolved；Comments 钉死 DetailEntry 字段名、扫描辅助函数签名（供后续客户端消费参考）。
just test 全绿。
```

### Wave 3

```
在分支 feat/polishing 上（Wave 2 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave3-start（已存在则跳过）。

用 /implement 实现（两票互不阻塞，可任意顺序；建议分别 commit）：
.scratch/polishing/issues/04-block-exits-deny-message.md
.scratch/polishing/issues/05-walking-terrain-cost-stamina.md

注意：
- 04 的 BlockExits.by_direction 升级为 BlockEntry 时，纯字符串旧写法要保留兼容（等价于 deny_message: null）。
- 05 的步行精力扣减规则只在非骑乘分支生效（Riding 组件存在时完全跳过），不要与既有坐骑精力扣减规则叠加或互相干扰。
- 05 精力恰好等于所需消耗时放行（扣至 0），不足才拒绝——对齐骑乘分支既有对称性。

每票单独 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 4

```
在分支 feat/polishing 上（Wave 3 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave4-start（已存在则跳过）。

用 /implement 实现：
.scratch/polishing/issues/06-hotel-sleep-rent.md

开工前读票正文「已钉死的开放子决策」三条（不要重新讨论，直接按钉死方案实现）：
1. sleep_room 极性沿用现有 RoomFlags.no_sleep_room（默认允许睡，显式关闭）。
2. 付费用新增专门 pay 命令，不复用 buy/give。
3. 睡房拦练功独立实现（_cmd_practice 新增判定分支），不复用 LibraryRoom 组件。

注意：
- engine/data/m2_mvp_scene.yaml 的 yangzhou_kedian 房已有 kedian_waiter NPC，直接复用作 pay 目标，不新建场景。
- 离开客店房间清 rent_paid 复用既有 on_leave_room 事件点，不新增 hook 协议方法。
- 房钱固定数值、睡觉具体效果范围作为可调参数自行钉死，写进 Comments。

完成后 commit；Status→resolved；Comments 钉死组件名/命令形状/房钱数值。
just test 全绿。
```

### Wave 5

```
在分支 feat/polishing 上（Wave 4 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave5-start（已存在则跳过）。

用 /implement 实现（两票互不阻塞）：
.scratch/polishing/issues/07-condition-dsl-docs.md
.scratch/polishing/issues/08-liquid-eat-drink.md

注意：
- 07 仅产出文档（docs/condition-dsl.md），无代码变更；每个接入点至少一段取自现有官方范本的真实 YAML 片段，不虚构示例；「现在不支持」清单要与 docs/gap-ledger.md 措辞对齐。
- 08 的一次性效果不接入 Effect 持续生命周期（ADR-0007 停机范围不变）；fill 只在房间 resource.water 为真时成功；eat 复用既有 Consumable.uses 耗尽销毁路径，不新建平行销毁逻辑。

每票单独 commit；Status→resolved；Comments 钉死字段/命令形状（08 需钉死容器数据形状、恢复数值）。
just test 全绿。
```

### Wave 6

```
在分支 feat/polishing 上（Wave 5 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave6-start（已存在则跳过）。

用 /implement 实现（两票互不阻塞）：
.scratch/polishing/issues/09-random-objects-pool.md
.scratch/polishing/issues/10-spawn-condition-hook-params.md

注意：
- 09 的补刷期抽签不得与出口 random_of（加载期一次性选定）共用同一段求值代码路径，实现时用代码注释或测试双重锚定这一边界。
- 09 需评估 spawn_scan 是否要新增 rng 注入参数（只做加法，不改既有调用方默认行为）。
- 10 只在 room_hooks.py 内部实现条件判定，不改动 ai.py 条件求值器或 conditions.py；UGC 包声明 hooks 仍必须失败，需补 S3 回归确认本次扩展未打开 UGC 缺口。

每票单独 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 7

```
在分支 feat/polishing 上（Wave 6 已 code-review fix 完成）。
打 fixed point：git tag polishing-wave7-start（已存在则跳过）。

用 /implement 实现：
.scratch/polishing/issues/11-scene-includes.md

注意：
- 本票已钉死：不支持嵌套 include；内容包轨允许 includes 但路径不得穿出包目录；--validate --strict 下 include 文件同样走已知字段校验。
- 路径解析基准目录为当前场景文件所在目录，越界/缺失/重复 id 三类失败都要有独立测试用例。
- 合并后模板 id 全局唯一校验对齐 ADR-0010「同文件扁平模板键」唯一性精神（放宽为「同一次合并后的命名空间」），不要误解为放开唯一性约束。

完成后 commit；Status→resolved；Comments 钉死 includes 段字段形状、路径校验规则。
just test 全绿。
```

### Wave 8

```
在分支 feat/polishing 上（Wave 7 已 code-review fix 完成；若已提前插队完成本 wave 可跳过重复劳动）。
打 fixed point：git tag polishing-wave8-start（已存在则跳过）。

用 /implement 实现：
.scratch/polishing/issues/12-local-weather-adr.md

本票只产出 ADR 文档（docs/adr/0013-*.md，编号写作时确认无冲突后确定），不写任何实现代码。
正面回答四点（见票正文清单）：与 ADR-0009 单进程单 World 的关系、与 nature.py NatureState 单例设计的关系、影响范围边界、回退语义。
ADR 状态先写 Proposed；/implement 阶段落地后（票 13 完成）再回写 Accepted。

完成后 commit；Status→resolved；不需要 just test（无代码变更）。
```

### Wave 9

```
在分支 feat/polishing 上（Wave 8 的 ADR 已写完并经你确认——ADR 是架构决策，建议在开 Wave 9 前单独过一遍 review，不必等 /code-review 循环）。
打 fixed point：git tag polishing-wave9-start（已存在则跳过）。

用 /implement 实现：
.scratch/polishing/issues/13-local-weather-implementation.md

开工前读票 12 产出的 ADR 全文——具体数据模型、字段形状、回退语义、模块命名全部以该 ADR 结论为准，本票不预先指定实现模块。
影响范围只到户外 look 描述文案与条件 DSL 里 is_raining/is_night 类谓词该房间取值；不新增天气→数值的玩法影响。

完成后 commit；Status→resolved；把票 12 的 ADR 状态从 Proposed 回写 Accepted。
just test 全绿。
```

## 提前开工的并行机会（可选）

- `12`（C14 ADR）**无票级阻塞、无代码变更**，可在任意早期 wave 期间另开 session 提前写完——越早写完，`13` 就能越早解锁，不必卡到 Wave 8 才动笔。若提前完成，Wave 8 直接跳过（只需确认 ADR 已 `resolved`）。
- `03`（A4 details 升级）、`06`（B8 客店三件套）、`11`（C13 includes）体量较大，若某个 wave 因止损线推迟，可优先把体量较小的 `04`/`05`/`07`/`10` 提前挪到更早的 wave 填空档，不必严格按 Wave 编号顺序推进——前提是同一份 PROGRESS/票 Comments 里记录实际推进顺序，避免下个 session 对不上号。
- 若并行：`/code-review` 仍建议按 wave 边界打 tag，提前完成的票并入下一波 review，避免 review 切得比票还碎。

## 参考文档索引

- 规格：[spec.md](spec.md)
- 拆票笔记：[to-tickets-notes.md](to-tickets-notes.md)
- grill 底稿：[../polishing-candidate-review/session-notes-2026-07-23.md](../polishing-candidate-review/session-notes-2026-07-23.md)、[../polishing-candidate-review/session-qa-provenance-2026-07-23.md](../polishing-candidate-review/session-qa-provenance-2026-07-23.md)
- ADR：[0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)、[0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)、[0009](../../docs/adr/0009-single-process-single-world.md)、[0010](../../docs/adr/0010-room-centric-objects-placement.md)、[0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)
- 契约 / GAP：[docs/creator-contract-v0.md](../../docs/creator-contract-v0.md)、[docs/gap-ledger.md](../../docs/gap-ledger.md)
- 治理止损：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- implement-plan 格式 precedent：[pre-m4-room-hooks-xingxiu/implement-plan.md](../pre-m4-room-hooks-xingxiu/implement-plan.md)、[pre-m4-engine-room-fidelity/implement-plan.md](../pre-m4-engine-room-fidelity/implement-plan.md)
- 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 后）：Done 滑动窗口追加一条，标题建议 `Polishing Wave{N} 落地：<一句话>`；超出 5 条移入 `.scratch/progress-archive.md`。
- **In Progress**：wave 开工时写当前 wave + 票号范围；wave 结束清空。
- **Next Up**：始终指向「下一个待做 wave」+ 链回本文件；不要把整段提示词贴进 PROGRESS。
- **仅 Wave 9（`13`）完成**后：effort 整体关闭——按 spec.md「Further Notes」收尾回写清单核对 `docs/gap-ledger.md`/`docs/creator-contract-v0.md`/`CONTEXT.md`/`PROGRESS.md`；建议补一份 `scripts/verify_polishing.py` + `test_verify_polishing_matrix.py`（S5，参考 [pre-m4-room-hooks-xingxiu](../pre-m4-room-hooks-xingxiu/) 收口手法），覆盖 13 项每项至少一条端到端场景步骤；本 effort README 状态改为已关闭。Next Up 换成「M4 评估」——**不得**因本 effort 做完自动开 M4。
- 止损/拆票：同步写 PROGRESS Blocked（不只写票 Comments）。
