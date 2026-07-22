# Pre-M4 引擎房间保真：Wave 拆分 + `/implement` → `/code-review` → fix 循环

> 本文件是 7 张票（[issues/](issues/)）的执行手册，供你在**新 session**里按 wave 逐批推进。拆票逻辑见 [to-tickets-notes.md](to-tickets-notes.md)；spec 见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：全部工作在 `feat/pre-m4-engine-room-fidelity`（自已合入 master 的频道/spawn/任务 tip 开出）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前对照 [spec.md](spec.md) 开头「范围边界」与 [ADR-0011](../../docs/adr/0011-semantic-color-tokens.md)——硬门闩 = `details` + 语义色 + 完整藏书；`day_shop`/剧情门可止损；**禁止**重开放置（ADR-0010）；关完**不**自动开 M4。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 1 | `01`, `02`, `03` | 地基：风景 `look` / 语义色 / 房间旗标+禁练能力 | 三票互不阻塞，可并行或任意顺序 |
| 2 | `04`, `05`, `06` | 能力闭环：藏书阁（硬门闩）/ 日间店 / 剧情门翰林 | `04` 阻塞于 01+03；`05`/`06` 无阻塞；三票彼此不互相阻塞 |
| 3 | `07` | 收口：契约加法 + GAP + CONTEXT/PROGRESS；核对 S3；不自动开 M4 | 单票，阻塞于 04/05/06（或后二者明文止损） |

依赖图（→ 表示「被…阻塞」）：

```
01 ──┐
03 ──┼→ 04 ──┐
02    │       ├→ 07
05 ───┤       │
06 ───┘       │
```

（`01`/`02`/`03` 是 frontier；`05`/`06` 技术上可与 Wave 1 并行，默认仍放 Wave 2 控 session 体量——见下方「提前开工」。）

## 每个 Wave 结束后的 `/code-review` 循环

1. **Wave 开工前**打标记：`git tag pre-m4-engine-room-fidelity-wave{N}-start`（如 `pre-m4-engine-room-fidelity-wave1-start`）。这是 `/code-review` 的 fixed point。
2. 在**新 session**用下方提示词跑 `/implement`（建议每票单独 commit）。
3. 完成后跑 `/code-review`，fixed point 填上表 tag，spec 填 [spec.md](spec.md) + 本 wave 的 issue 路径。
4. 按 Standards / Spec 两轴修 fix；再跑 `just test` 确认绿，然后进入下一 wave。
5. **止损线**（对齐 [mvp-scope 07](../mvp-scope/issues/07-governance-cost-tracking.md)）：单票工作量超预估 3 倍 → 重估；先怀疑是否做进 OOS。`05`/`06` 允许明文止损（记票 Comments + PROGRESS Blocked）。单 session 近 smart zone（~120K）无进展 → `/handoff` 写回 PROGRESS In Progress。

## Wave 提示词模板（复制进新 session）

> 假设已 `cd` 到仓库根。全程复用本 effort 分支，不要为每个 wave 新开分支。

### Wave 1

```
先确认分支：git checkout feat/pre-m4-engine-room-fidelity（没有则从当前 master/频道 tip 创建并跟踪）。
不要在 master 上改代码。

打 fixed point：git tag pre-m4-engine-room-fidelity-wave1-start（已存在则跳过）。

用 /implement 实现以下三张票（互不阻塞，可任意顺序）：
.scratch/pre-m4-engine-room-fidelity/issues/01-room-details-look.md
.scratch/pre-m4-engine-room-fidelity/issues/02-semantic-color-tokens.md
.scratch/pre-m4-engine-room-fidelity/issues/03-room-flags-no-practice.md

开工前读：
- .scratch/pre-m4-engine-room-fidelity/spec.md 的 Implementation Decisions（房间风景 / 语义色 / 房间旗标）
- .scratch/pre-m4-engine-room-fidelity/to-tickets-notes.md「关键设计决策」（尤其 3、4、5）
- docs/adr/0011-semantic-color-tokens.md

注意：01 要把 look 扩到同房 NPC 再查 details；02 核心回文保留 <c:…>，渲染只在 CLI；03 禁练是通用能力，官方藏书阁挂载留给 04。不要重开放置模型。

每票单独 commit（message 引用票号，如 "pre-m4-room-fidelity-01: details + look"）。
每票完成后把 issue Status 改 resolved，## Comments 补实现摘要（字段名/命令形状务必写下，供 07 回写契约）。
全部完成后跑 just test 确认绿；不要跑 /code-review（等本 wave 统一 review）。
```

### Wave 2

```
在分支 feat/pre-m4-engine-room-fidelity 上（Wave 1 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-engine-room-fidelity-wave2-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-engine-room-fidelity/issues/04-library-and-cangshuge.md（阻塞于 01、03，应已落地）
.scratch/pre-m4-engine-room-fidelity/issues/05-day-shop.md
.scratch/pre-m4-engine-room-fidelity/issues/06-story-doors-hanlin.md

三票彼此不互相阻塞。建议顺序：先 04（硬门闩），再 05/06；若单 session 吃不消，可先完整做完 04 并 review fix，再开 session 做 05/06。

开工前读 to-tickets-notes 决策 1（付费用银两 Currency）、决策 2（day_shop 与手写 entry_guard 并存则加载失败）。
04 必须在官方 m2_mvp_scene 挂扬州藏书阁完整主路径；05 挂打铁铺；06 挂翰林三件套。不新建橱窗包。
05/06 为非硬门闩：若撞上未预见大洞可止损，Comments + PROGRESS Blocked 写明，不要硬撑进 OOS。

每票单独 commit；Status→resolved；Comments 钉死 schema/命令形状。
全部完成后 just test 全绿。
```

### Wave 3（收口）

```
在分支 feat/pre-m4-engine-room-fidelity 上（Wave 1/2 均已 code-review fix；05/06 若止损须已在 PROGRESS/票 Comments 明文记录）。
打 fixed point：git tag pre-m4-engine-room-fidelity-wave3-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-engine-room-fidelity/issues/07-closeout-contract-gap.md

收口清单：
1. docs/creator-contract-v0.md + 加载器已知字段 / --validate 只做加法；
2. docs/gap-ledger.md 改判本波已支持项（措辞不越界）；
3. 核对 CONTEXT.md 房间风景/语义色/旗标/藏书/日间店/剧情门/effort 词条；
4. 核对 S3：藏书阁、打铁铺日夜、翰林三件套、至少一处带色+details 户外——缺则最小补齐 m2_mvp_scene；
5. 更新 PROGRESS.md：Done 增补收口；Next Up 改为 M4 评估；明确不自动开 M4；
6. 本 effort README 状态改为已关闭。

完成后 just test；不要合并回 master（除非用户明确要求）；停住等待 review。
```

## 提前开工的并行机会（可选）

- `05`（日间店）、`06`（剧情门）**无票级阻塞**，可在 Wave 1 期间另开 session 认领；注意与 `01`/`02` 同时改 `m2_mvp_scene.yaml` / `scene_loader` 时减少冲突（建议约定房间键：`yangzhou_cangshuge` / 打铁铺已有键 / `yangzhou_hanlin_*`）。
- 若并行：`/code-review` 仍建议按 wave 边界打 tag，提前完成的票并入下一波 review，避免 review 切得比票还碎。

## 参考文档索引

- 规格：[spec.md](spec.md)
- 拆票笔记：[to-tickets-notes.md](to-tickets-notes.md)
- grill 底稿：[session-notes-2026-07-21.md](session-notes-2026-07-21.md)
- ADR：[0010](../../docs/adr/0010-room-centric-objects-placement.md)、[0011](../../docs/adr/0011-semantic-color-tokens.md)、[0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)
- 契约 / GAP：[docs/creator-contract-v0.md](../../docs/creator-contract-v0.md)、[docs/gap-ledger.md](../../docs/gap-ledger.md)
- 治理止损：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- implement-plan 格式 precedent：[pre-m4-channels-spawn-quest/implement-plan.md](../pre-m4-channels-spawn-quest/implement-plan.md)、[m2-mvp-scene-playable/implement-plan.md](../m2-mvp-scene-playable/implement-plan.md)
- 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 后）：Done 滑动窗口追加一条，标题建议 `Pre-M4 引擎房间保真 Wave{N} 落地：<一句话>`；超出 5 条移入 `.scratch/progress-archive.md`。
- **In Progress**：wave 开工时写当前 wave + 票号范围；wave 结束清空。
- **Next Up**：始终指向「下一个待做 wave」+ 链回本文件；不要把整段提示词贴进 PROGRESS。
- **仅 Wave 3（`07`）完成**后：划掉本 effort 的 Next Up，换成「M4 评估」——**不得**因本效做完自动开 M4。
- 止损/拆票：同步写 PROGRESS Blocked（不只写票 Comments）。
