## Destination

新目标范围收敛决策定稿:确定"题材无关核心 MUD 引擎 + UGC 创作层 + 官方轻量武侠题材包(MVP)"这一新方向下,已发现的 36 个子系统(架构拆解说明书 + 子系统发现报告)每一个的归类——**MVP 必做 / 可选 / 现代化改造 / 必须丢弃**,归类依据是"对新引擎和 MVP 题材包的设计参考价值",不做任何形式的行为等价验证(见 [ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md))。同时给出 `engine/` 现有实现(约 45k 行代码)的去留结论;并为"未来承载目标、商业化闭环"标出架构支撑点(不要求 MVP 阶段实现)。定稿产出可直接重写 `CLAUDE.md` 的"项目一句话"与架构不变量章节,并作为后续 `/to-spec` 的输入。

本地图止于**决策**,不产出实施计划或代码改动——实施留给定稿后的 `/to-spec` → `/to-tickets` → `/implement`。

## Notes

- 背景:项目是《侠客行》LPC MUD(8412 文件 / 6414 房间 / 21 门派)的现代化重构。2026-07-17 前的完整历史见 [docs/archive/](../../docs/archive/README.md),归档原因是原定"全量复刻"目标本身被推翻,不只是取舍战略修订。
- 每张 ticket 解决时应参考的技能:`/grilling`(逐票细聊)、`/domain-modeling`(术语与 ADR 维护)、`/codebase-design`(涉及模块边界/接口设计的票,例如 02)。
- 本效力标准偏好:
  - **不做行为等价验证**([ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md))——LPC 源码与旧架构文档仅作设计灵感与术语参考,不是规格源。
  - 子系统归类统一用四档:MVP 必做 / 可选 / 现代化改造 / 丢弃,不再细分"丢弃"的理由类别(设计过时 vs 工程代价不值)——图省事优先,除非实践中发现四档不够用。
  - 框架/流程层面的小决定由 agent 自行拍板并记录理由,不逐一打断用户;只把实质性的范围/取舍决定摆给用户判断。
  - 用户对拿不准的问题可随时标记"暂定",允许推迟到有更具体依据(原型、对比、子系统盘点结果)时再定——不强求一次性想清楚。

## Decisions so far

- [01-subsystem-classification-framework](issues/01-subsystem-classification-framework.md) — 归类用四档(MVP 必做/可选/现代化改造/丢弃)即可,不再细分丢弃理由;归类依据统一为"设计参考价值"而非保真度。
- [03-ugc-dsl-design-inheritance](issues/03-ugc-dsl-design-inheritance.md) — UGC/DSL 创作层不直接沿用旧方案的四层结构,基于新目的地重新设计,但旧方案与关键修正清单中的教训作为重要参考输入。**追加(2026-07-21)**:M3=包外内容包→加载→可玩([ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md));编辑器(9)改判丢弃,创作者 Web 平台+留言板进 [post-mvp-backlog.md](post-mvp-backlog.md)([ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md))。
- [ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md) — 不做任何形式的 LPC 行为等价验证,推翻 ADR-0009 的三层验证框架。
- [04-engine-code-disposition](issues/04-engine-code-disposition.md) — `engine/` 现有约 45k 行代码整体重写,不逐段复用;旧代码只作参考,不作重写起点。
- [05-six-constraints-continuation](issues/05-six-constraints-continuation.md) — 旧六条收缩约束逐条重新评估后全部延续:不搞分布式架构/网关(单机 1000 在线 + 100 并发)、运维观测后置、纯 Python、内存+本地 JSON 存档。
- [06-scaling-commercialization-support-points](issues/06-scaling-commercialization-support-points.md) — 商业模式:玩家侧双货币+订阅+不 pay-to-win(参考 Iron Realms),创作者侧按题材包消费分成(参考 Roblox/Fortnite);承载靠题材包数量横向扩展而非单世界变大;架构支撑点=账本抽象/题材包资产归属元数据/消费埋点/世界实例隔离。
- [07-governance-cost-tracking](issues/07-governance-cost-tracking.md) — 推进治理机制:止损线(进度类 3 倍预估强制重评、会话类接近 120K token 无进展强制 handoff)+ 里程碑 M0~M4(定稿→引擎骨架→单场景可玩→UGC 闭环一次→商业化数据模型)两样建;AI 成本/token 台账取消,不建。
- [08](issues/08-subsystem-classification-research.md)+[09-subsystem-classification-confirm](issues/09-subsystem-classification-confirm.md) — 41 个子系统四档归类(2026-07-21):MVP 必做 18 / 可选 4 / 现代化改造 9 / 丢弃 11(金钱拆两半计入)。二次改判:坐骑 38→MVP 必做;编辑器 9→丢弃([ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md))。跨票遗留已关闭。
- [10-mvp-scenes-selection](issues/10-mvp-scenes-selection.md) — MVP 场景清单定稿:新手村(华山村,中立不绑定门派)+ 城镇(扬州丰富子集,老玩家熟悉地标)+ 门派(少林寺)+ 野外(扬州↔少林沿途)+ 官道(跨区域连接)+ 水陆交通(渡口/渡船)+ 坐骑(官道野外可骑乘)。这条要求直接触发坐骑与交通系统(38)从"现代化改造+MVP 不做"改判为"MVP 必做"(已同步进 08 号票)。**mvp-scope 地图 10/10 票解决**——[02-engine-boundary-combat-effects](issues/02-engine-boundary-combat-effects.md) 已拍板(2026-07-19,用 `/design-an-interface` 三源调研+三设计对比,见 [ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md)):战斗结算流程框架 + 效果生命周期机制归引擎,精确边界定稿,战斗/状态/技能/死亡轮回四子系统归类维持 MVP 必做不变。结论已写回 [CLAUDE.md](../../CLAUDE.md) 的"项目一句话"与"架构不变量"章节。

## Not yet specified

- 创作者 Web 平台与留言板的**具体里程碑编号与排期**(已列入 [post-mvp-backlog.md](post-mvp-backlog.md),待 M4 前后再开里程碑)。

## Out of scope

- 引擎内建原版编辑器(`editord`/`F_EDIT`)、引擎内建留言板/文选——见 [ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)。
