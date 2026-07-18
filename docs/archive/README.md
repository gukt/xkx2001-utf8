# 归档说明

> 归档日期：2026-07-17。原因：项目发现原定目标/取舍战略存在问题，决定重新设定目标（比 [strategy-review](strategy-review/README.md) 提出的 9 条基线修订更大幅度——不是修订，是重设）。

本目录下的一切**不再是当前目标**，但依然是**真实发生过的历史**：决策为什么当时那样做、探索过什么、踩过什么坑，这些事实不会因为目标改变而失效。新 session/新 agent 需要参考历史背景、查旧 ADR 的论证过程、或理解 engine 代码里某段实现的来龙去脉时，来这里找。

**不要**把这里的内容当作当前应该遵循的架构基线或应该继续推进的计划——那些判断已被撤回。

## 目录内容

| 路径 | 归档前是什么 | 用途 |
|---|---|---|
| [xkx-arch/](xkx-arch/) | 架构基线文档（00-17 + README），含 `_archive/` 内更早的 v1→v2 重设记录——**这是本项目第二次做这种整体重设** | 查旧目标架构的设计与论证 |
| [adr/](adr/) | `ADR-0001` ～ `ADR-0064` 决策日志 | 查某个实现决策当时的背景与取舍；新 ADR 见根目录 [docs/adr/](../adr/)（重新从头编号，格式见 [domain-modeling ADR-FORMAT](../../.claude/skills/domain-modeling/ADR-FORMAT.md)，不带 `ADR-` 前缀） |
| [strategy-review/](strategy-review/) | 2026-07-16 的 5 视角红队战略复审，9 条基线修订提案 | 本次重设的直接导火索之一；里面对"进度/偏离/取舍/推进方式"的分析在重新定目标时仍有参考价值 |
| [progress-archive/](progress-archive/) | 按阶段（-1/0/1/2/M2/M3）归档的 Done 历史 | 查某个阶段具体做了什么、测试数、关联 ADR |
| [batch-cost.md](batch-cost.md) | AI agent 迁移的 token/时长成本台账 | 估算未来工作量时的历史基准数据 |
| [PROGRESS.md](PROGRESS.md) | 重设前最后一次的活状态快照 | 查重设发生时项目卡在哪、下一步原计划是什么 |
| [CLAUDE.md](CLAUDE.md) | 重设前的操作手册（六条收缩约束、关键架构不变量、开发规范） | 查旧约束/不变量当时是怎么定义和论证的；新约束如果要延续某一条，从这里抄，不要凭记忆重写 |

## 内部链接可能已失效

以上文档之间大量互相引用（如 ADR 引用 strategy-review、strategy-review 引用 progress-archive），链接路径都是归档前的相对路径（`docs/adr/...`、`docs/xkx-arch/...`），归档后**未逐条修复**——这批文档已冻结，批量修复几百条链接的成本不划算。找不到目标时，去掉链接里的 `docs/archive/` 之外的路径前缀，在本目录下用文件名搜索即可定位。

同理，旧 `engine/` 源码里一些注释/docstring 引用了旧的 `docs/adr/ADR-NNNN.md` 路径（仅文档链接，非运行时依赖）——同样未批量修复。

## 旧引擎源码在哪

工作区 `engine/` 已于 M1 第 0 步绿场清空（[ADR-0002](../adr/0002-engine-workspace-greenfield-reset.md)）。约 45k 行旧实现**不在本 archive 目录**，而在 git tag：

```bash
git show archive/engine-pre-m1-rewrite:engine/src/xkx/runtime/ecs.py
```
