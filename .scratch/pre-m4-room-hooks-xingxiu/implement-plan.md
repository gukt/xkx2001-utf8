# Pre-M4 房间钩子 / 星宿机制：Wave 拆分 + `/implement` → `/code-review` → fix 循环

> 本文件是 11 张票（[issues/](issues/)）的执行手册，供你在**新 session** 里按 wave 逐批推进。拆票逻辑见 [to-tickets-notes.md](to-tickets-notes.md)；spec 见 [spec.md](spec.md)；跨 session 状态见 [PROGRESS.md](../../PROGRESS.md)。
>
> **分支**：全部工作建议在 `feat/pre-m4-room-hooks-xingxiu` 上进行（自已合入 master 的引擎房间保真 tip 开出）。**不要**在 `master` 上直接实现。
>
> **核心校准**：每个 wave 开工前对照 [spec.md](spec.md) 开头「范围边界」与 [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)——T1 仅官方/题材包可信 Python；R1 窄 `ctx`；UGC 禁钩子（fail-closed）；不整区移植星宿；不做 LPC 行为等价（ADR-0001）；关完**不**自动开 M4。

## Wave 总览

| Wave | 票据 | 主题 | 并行度 |
|---|---|---|---|
| 1 | `01` | 地基：房间钩子协议 + 注册表 + 窄 `ctx` + 房间自由状态 | 单票，后续全部依赖它 |
| 2 | `02` | 机关 #1 动态出口+时限崩塌 + 机关 #2 `random_of`（创建 `xingxiu_mechanics.yaml`） | 单票 |
| 3 | `03`, `04`, `05` | 多步状态机 / `valid_leave` 迷途 / jump·climb 技能门槛 | 三票互不阻塞，可并行或任意顺序 |
| 4 | `06`, `07` | 时段耦合秘道 / 入室磁力吸铁 | 两票互不阻塞 |
| 5 | `08`, `09` | 劫匪刷拦 / 杀令介入（简化） | 两票互不阻塞 |
| 6 | `10` | 柔丝索跨玩家捕获（`SkillBehavior`，依赖 `01` 的受限移动方法本体） | 单票 |
| 7 | `11` | 收口：UGC 边界复核 + 十类整合 + 契约/GAP/CONTEXT/PROGRESS | 单票，阻塞于 `02`–`10` 全部 |

依赖图（→ 表示「被…阻塞」）：

```
01 ──┬→ 02 ──┐
     ├→ 03 ──┤
     ├→ 04 ──┤
     ├→ 05 ──┤
     ├→ 06 ──┼→ 11
     ├→ 07 ──┤
     ├→ 08 ──┤
     ├→ 09 ──┤
     └→ 10 ──┘
```

（`02`–`10` 全部只阻塞于 `01`，彼此互不阻塞；Wave 分组是为了控制单 session 体量与 `/code-review` 粒度，不代表票据间真实阻塞。）

## 每个 Wave 结束后的 `/code-review` 循环

1. **Wave 开工前**打标记：`git tag pre-m4-room-hooks-xingxiu-wave{N}-start`（如 `pre-m4-room-hooks-xingxiu-wave1-start`）。这是 `/code-review` 的 fixed point。
2. 在**新 session**用下方提示词跑 `/implement`（建议每票单独 commit）。
3. 完成后跑 `/code-review`，fixed point 填上表 tag，spec 填 [spec.md](spec.md) + 本 wave 的 issue 路径。
4. 按 Standards / Spec 两轴修 fix；再跑 `just test` 确认绿，然后进入下一 wave。
5. **止损线**（对齐 [mvp-scope 07](../mvp-scope/issues/07-governance-cost-tracking.md)）：单票工作量超预估 3 倍 → 重估；先怀疑是否该机关的代表切片选择过重，按 spec Further Notes 处理，不默默降级验收标准。单 session 近 smart zone（~120K）无进展 → `/handoff` 写回 PROGRESS In Progress。

## Wave 提示词模板（复制进新 session）

> 假设已 `cd` 到仓库根。全程复用本 effort 分支，不要为每个 wave 新开分支。

### Wave 1

```
先确认分支：git checkout feat/pre-m4-room-hooks-xingxiu（没有则从当前 master/房间保真 tip 创建并跟踪）。
不要在 master 上改代码。

打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave1-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-room-hooks-xingxiu/issues/01-room-hook-protocol-registry-ctx.md

开工前读：
- .scratch/pre-m4-room-hooks-xingxiu/spec.md 的 Implementation Decisions（房间钩子协议与注册表 / 窄 ctx API）
- .scratch/pre-m4-room-hooks-xingxiu/to-tickets-notes.md「关键设计决策」1、2
- docs/adr/0012-trusted-room-hooks-narrow-ctx.md
- engine/src/openmud/skills.py（仿照对象：SkillBehavior 协议 + 注册表 + CombatContext 窄只读 ctx 形状）

注意：
- 受限实体移动方法要实现为独立可复用方法本体（供未来票 10 的 SkillBehavior 直调），不要只挂在 ctx 对象上。
- UGC 拒绝规则随字段一起落地，不留窗口期。
- 用测试专用哑钩子验证挂载全链路，不要提前创建 xingxiu_mechanics.yaml（留给票 02）。

完成后单独 commit（message 引用票号，如 "pre-m4-room-hooks-xingxiu-01: 房间钩子协议+注册表+窄ctx"）。
Status 改 resolved，## Comments 补实现摘要（协议方法签名、ctx 方法名、房间自由状态组件名，供后续票与票 11 回写契约）。
just test 全绿；不要跑 /code-review（等本 wave 统一 review）。
```

### Wave 2

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 1 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave2-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-room-hooks-xingxiu/issues/02-dynamic-exit-collapse-random-of.md

开工前读票 01 的 Comments（ctx 方法名与房间自由状态组件形状）。
本票创建 engine/data/xingxiu_mechanics.yaml（官方单文件轨道，不带 manifest.yaml）。

完成后 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 3

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 2 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave3-start（已存在则跳过）。

用 /implement 实现（三票互不阻塞，可任意顺序；建议分别 commit）：
.scratch/pre-m4-room-hooks-xingxiu/issues/03-multi-step-room-state-machine.md
.scratch/pre-m4-room-hooks-xingxiu/issues/04-valid-leave-lost-in-maze.md
.scratch/pre-m4-room-hooks-xingxiu/issues/05-jump-climb-skill-gate.md

注意：
- 04 需要新增引擎事件总线的 ON_BEFORE_LEAVE_ROOM（可否决），镜像既有 ON_BEFORE_ENTER_ROOM；只服务本机关，不做成钩子协议通用方法族。
- 三票都会追加房间到 xingxiu_mechanics.yaml，若并行开发注意房间键不冲突。
- 05 的技能等级判定直接复用既有 SkillLevels，不新造判断逻辑。

若单 session 吃不消，可分次做完并各自 code-review fix。
每票单独 commit；Status→resolved；Comments 钉死字段/命令形状。
全部完成后 just test 全绿。
```

### Wave 4

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 3 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave4-start（已存在则跳过）。

用 /implement 实现（两票互不阻塞）：
.scratch/pre-m4-room-hooks-xingxiu/issues/06-time-of-day-secret-passage.md
.scratch/pre-m4-room-hooks-xingxiu/issues/07-magnetic-iron-attraction.md

注意：06 复用既有 is_day/is_night + HiddenExits 揭示机制；07 复用既有 ItemTags，本票只做播报级效果，不强制卸除物品。

每票单独 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 5

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 4 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave5-start（已存在则跳过）。

用 /implement 实现（两票互不阻塞）：
.scratch/pre-m4-room-hooks-xingxiu/issues/08-bandit-ambush-spawn.md
.scratch/pre-m4-room-hooks-xingxiu/issues/09-kill-order-intervention.md

注意：08 优先复用房间保真已交付的 block_exits（NPC 在场挡向），钩子只负责生成/解除编排，不新建阻挡字段；09 不建通缉/声望持久状态，只用房间自由状态记一个"本次是否已触发"标记位。

每票单独 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 6

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 5 已 code-review fix 完成）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave6-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-room-hooks-xingxiu/issues/10-silk-rope-cross-player-capture.md

注意：本机关是 SkillBehavior（招式命中回调），不是 RoomHook；直调票 01 的受限实体移动方法本体。
测试用同一 World 内 spawn_player_session 出两个会话（参考 engine/tests/test_per_session_mailbox.py 的写法）。
不新建通用远程传送命令面。

完成后 commit；Status→resolved；Comments 钉死字段/命令形状。
just test 全绿。
```

### Wave 7（收口）

```
在分支 feat/pre-m4-room-hooks-xingxiu 上（Wave 1–6 均已 code-review fix；若任一票按治理止损线重估/止损，须已在 PROGRESS/票 Comments 明文记录）。
打 fixed point：git tag pre-m4-room-hooks-xingxiu-wave7-start（已存在则跳过）。

用 /implement 实现：
.scratch/pre-m4-room-hooks-xingxiu/issues/11-closeout-ugc-boundary-contract-gap.md

收口清单：
1. 复核 UGC 拒绝规则（--validate/--strict/非严格路径一致失败判定），本票不补代码，只复核；
2. 核对 xingxiu_mechanics.yaml 十类机关全部到位、S3 端到端跑通、与 m2_mvp_scene 互不干扰；
3. docs/creator-contract-v0.md 新增钩子字段官方轨专属说明节；
4. docs/gap-ledger.md 新增「运行时改世界机关」行；核对既有「剧情门」行措辞一致；
5. 核对 CONTEXT.md 房间钩子/xingxiu_mechanics/窄 ctx/房间自由状态/ON_BEFORE_LEAVE_ROOM 词条；
6. 更新 PROGRESS.md：Done 增补收口；Next Up 改为 M4 评估；明确不自动开 M4；
7. 本 effort README 状态改为已关闭。

完成后 just test 全量回归；不要合并回 master（除非用户明确要求）；停住等待 review。
```

## 参考文档索引

- 规格：[spec.md](spec.md)
- 拆票笔记：[to-tickets-notes.md](to-tickets-notes.md)
- grill 底稿：[session-notes-2026-07-22.md](session-notes-2026-07-22.md)
- ADR：[0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)、[0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)、[0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)、[0009](../../docs/adr/0009-single-process-single-world.md)、[0010](../../docs/adr/0010-room-centric-objects-placement.md)
- 契约 / GAP：[docs/creator-contract-v0.md](../../docs/creator-contract-v0.md)、[docs/gap-ledger.md](../../docs/gap-ledger.md)
- 治理止损：[mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)
- implement-plan 格式 precedent：[pre-m4-engine-room-fidelity/implement-plan.md](../pre-m4-engine-room-fidelity/implement-plan.md)
- 双 `PlayerSession` seam precedent：`engine/tests/test_per_session_mailbox.py`
- 活状态：[PROGRESS.md](../../PROGRESS.md)

## 与 PROGRESS.md 的对接约定

- **每个 wave 结束**（code-review fix 后）：Done 滑动窗口追加一条，标题建议 `Pre-M4 房间钩子/星宿机制 Wave{N} 落地：<一句话>`；超出 5 条移入 `.scratch/progress-archive.md`。
- **In Progress**：wave 开工时写当前 wave + 票号范围；wave 结束清空。
- **Next Up**：始终指向「下一个待做 wave」+ 链回本文件；不要把整段提示词贴进 PROGRESS。
- **仅 Wave 7（`11`）完成**后：划掉本 effort 的 Next Up，换成「M4 评估」——**不得**因本 effort 做完自动开 M4。
- 止损/拆票：同步写 PROGRESS Blocked（不只写票 Comments）。
