# CLAUDE.md - 侠客行 MUD 现代化重构 项目指令

> 本文件每个 session 自动加载。**2026-07-17 项目重设，2026-07-18 新目标定稿**：原目标（全量复刻《侠客行》+ 行为等价验证）已放弃，重设过程用 `/wayfinder` 走了一遍 [.scratch/mvp-scope/](.scratch/mvp-scope/) 9/10 票决策，均已拍板（[02-engine-boundary-combat-effects](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 用户主动标"暂定"未拍板，不阻塞其他票，见下文"待办"）。本文件下面的"项目一句话"与"架构不变量"是这 9 票的结论摘要；完整论证/理由/边界讨论在 [.scratch/mvp-scope/map.md](.scratch/mvp-scope/map.md) 与其 `issues/` 目录，本文件与它冲突时以本文件的摘要为准（摘要是这 9 票之后的最终结论，某些条目在后续票里被追加改判过）。
>
> 开工第一件事：读本文件 + [PROGRESS.md](PROGRESS.md)（活状态）。需要旧背景（旧目标怎么论证的、踩过什么坑、某个实现决策当时为什么这么做）时去 [docs/archive/README.md](docs/archive/README.md) 找——那批文档冻结但依然是真实历史，不是当前基线；LPC 源码与旧架构文档仅作设计灵感/术语参考，不是规格源。

## 项目一句话

**题材无关的核心 MUD 引擎 + UGC 创作层 + 一个官方轻量武侠题材包（MVP）。**《侠客行》LPC 源码（8412 文件、6414 房间、21 门派）与其架构拆解文档只提供设计灵感和术语参考，新引擎服务任意题材（未来可扩展仙侠/科幻/校园等），不是《侠客行》的行为等价替代品——**不做任何形式的 LPC 行为等价验证**（[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）。商业模式上，承载靠"题材包数量横向扩展"而非单世界做大，为未来 UGC 创作者生态留架构支撑点（细节见下）。

## 架构不变量

以下摘自 [.scratch/mvp-scope/](.scratch/mvp-scope/) 9 票决策，是当前阶段的硬约束，偏离需要写 ADR（见下文"决策日志"）：

1. **单机承载，不做分布式**（[05](.scratch/mvp-scope/issues/05-six-constraints-continuation.md)）：不搞分布式架构/网关，单机 1000 在线 + 100 并发；运维观测后置（只上基础 OpenTelemetry + Grafana，不上 K8s/Helm）；纯 Python（暂不考虑 Rust/Go）；内存数据 + 本地 JSON 定时存档（不上 PG/Redis）。这五条延续自旧方案，是通用工程判断，跟"复刻不复刻"无关。
2. **不做行为等价验证**（[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）：无论是位等价、统计行为等价还是 golden trace 运行时对照，都不做，连一次性验证也不做。
3. **`engine/` 整体重写，工作区已绿场清空**（[04](.scratch/mvp-scope/issues/04-engine-code-disposition.md) + [ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)）：不逐段复用；路径名仍是 `engine/`（不建 `engine_v2`）。旧实现（约 45k 行）冻结于 git tag `archive/engine-pre-m1-rewrite`，按需 `git show` 查阅，禁止 import / 禁止当重写起点。`engine/prototypes/` 可留 throwaway 原型。
4. **子系统四档归类**（[01](.scratch/mvp-scope/issues/01-subsystem-classification-framework.md)/[08](.scratch/mvp-scope/issues/08-subsystem-classification-research.md)/[09](.scratch/mvp-scope/issues/09-subsystem-classification-confirm.md)）：36+5 个已发现子系统（详见 [00-子系统发现报告](docs/archive/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/00-子系统发现报告.md)）全部归类为 MVP 必做（18）/ 可选（4）/ 现代化改造（10）/ 丢弃（10），归类依据是"对新引擎与 MVP 题材包的设计参考价值"，不是保真度。完整清单 + 每条理由见 [08 号票](.scratch/mvp-scope/issues/08-subsystem-classification-research.md)。**遗留跨票依赖**：[02-engine-boundary-combat-effects](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 已拍板（2026-07-19）：战斗结算流程框架 + 效果生命周期机制归引擎，精确边界见 [ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md)；战斗/状态/技能/死亡轮回四子系统归类维持 MVP 必做不变；[03](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统的归类要回头核对。
5. **UGC/DSL 创作层从零设计**（[03](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md)）：不直接沿用旧方案的 DSL 四层结构，但旧方案与 [关键修正与避坑清单](docs/archive/xkx-arch/_archive/01-关键修正与避坑清单.md) 中已用真实代码验证过的教训（如"UGC 脚本用受限 Python 非 WASM"）是重要参考输入，不能忽略。
6. **商业化架构支撑点，MVP 不要求实现**（[06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md)）：玩家侧双货币+订阅+不 pay-to-win（参考 Iron Realms），创作者侧按题材包消费分成（参考 Roblox/Fortnite）；承载扩展靠题材包数量横向扩展，不是单世界做大。要留位置但不强制 MVP 实现的四个支撑点：货币/账本抽象、题材包资产元数据（创作者归属+版本溯源）、消费/参与度埋点（可打点到题材包 ID）、世界实例隔离（每个题材包独立进程）。
7. **MVP 场景清单**（[10](.scratch/mvp-scope/issues/10-mvp-scenes-selection.md)）：新手村（华山村，不绑定门派）+ 城镇（扬州丰富子集）+ 门派（少林寺）+ 野外（扬州↔少林沿途）+ 官道（跨区域连接）+ 水陆交通（渡口/渡船）+ 坐骑（官道/野外可骑乘）。坐骑与交通系统因这条要求从"现代化改造"改判为"MVP 必做"，是四档归类中唯一被二次改判的子系统。
8. **推进治理**（[07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)）：止损线两条——某 ticket 落地到 `/implement` 阶段后实际工作量超预估 3 倍，强制停下重估范围；单 session 接近 smart zone（~120K token）还没完成且无进展信号，强制 `/handoff`。里程碑节奏 M0（本地图定稿+本文件重写，已完成）→ M1（核心引擎骨架，空场景+命令-移动-存档最小闭环）→ M2（一个 MVP 场景端到端可玩）→ M3（UGC 创作闭环打通一次）→ M4（商业化支撑点数据模型落地，不要求真实计费）。AI 成本/token 台账**不建**（曾讨论过又拍板取消）。

## 仓库拓扑

- `adm/ cmds/ d/ kungfu/ ...`（仓库根）：**LPC 规格源，只读参考，禁止修改**。无论新目标如何调整，这批文件的"只读参考"性质不变。
- [engine/](engine/)：**唯一活的 Python 引擎工作区**（绿场）。`src/mud_engine/` 包（`import mud_engine`），`tests/` 测试，`prototypes/` 为 throwaway。旧实现不在工作区，见 tag `archive/engine-pre-m1-rewrite` 与 [ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)。
- [.scratch/mvp-scope/](.scratch/mvp-scope/)：**新目标定稿的完整决策记录**（`/wayfinder` 地图，10/10 票已解决）。本文件"架构不变量"是它的摘要；要看某条结论的完整论证/被否决的备选方案，去这里的 `map.md` 和 `issues/NN-*.md`。
- [.scratch/m1-core-engine-skeleton/](.scratch/m1-core-engine-skeleton/)：**M1 里程碑** spec + issues（第 0 步工作区重置已完成，见 [00](.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md)）。
- [docs/archive/](docs/archive/)：**旧目标的完整历史归档**（架构基线、64 条 ADR、进度归档、战略复审、旧 `CLAUDE.md`/`PROGRESS.md`）。只读参考，不是当前基线，见 [docs/archive/README.md](docs/archive/README.md)。同目录下的《侠客行》架构拆解说明书（`docs/archive/xkx-arch/`）虽在"旧目标"归档里，但其设计灵感/术语参考价值在新目标下依然有效，见"架构不变量"第 4 条。旧引擎**源码**不在此目录，而在 git tag `archive/engine-pre-m1-rewrite`。
- [docs/adr/](docs/adr/)：**重设后的新决策日志**，从头编号（目前 [0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)～[0004](docs/adr/0004-combat-effects-boundary-engine.md)）。格式见 [domain-modeling ADR-FORMAT](.claude/skills/domain-modeling/ADR-FORMAT.md)：`NNNN-slug.md`，不带 `ADR-` 前缀，短段落即可。
- [docs/agents/](docs/agents/)：engineering skills 的仓库级配置（issue tracker / triage 标签 / domain docs 消费规则），与目标本身无关，重设不影响。
- `todo.md` / `README`：遗留的 LPC UTF-8 转码记录，与新项目无关，忽略。

## Agent skills

### Issue tracker

本地 markdown（`.scratch/<effort>/`），未用 GitHub Issues。见 [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md)。

### Triage labels

默认五角色标签（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix）。见 [docs/agents/triage-labels.md](docs/agents/triage-labels.md)。

### Domain docs

single-context：根目录 `CONTEXT.md`（惰性创建）+ [docs/adr/](docs/adr/)（新决策，惰性创建）+ [docs/archive/](docs/archive/)（旧背景参考）。见 [docs/agents/domain.md](docs/agents/domain.md)。
- [ ] `/to-spec` / M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后，编辑器系统（子系统 9）的归类是否仍准确。