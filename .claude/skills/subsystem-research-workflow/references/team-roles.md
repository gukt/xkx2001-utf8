# 默认团队角色模板

本 skill 默认使用以下 11 人虚拟调研团队。用户可以根据子系统特点增删角色。

## 一手考古组

### LPC 源码考古员（1 人）

- **职责**：逐目录阅读子系统相关源码，输出完整源码清单、调用链、数据结构、关键回调与状态变量。
- **产出**：`01-raw-findings/source-inventory.md`
- **核心能力**：耐心、细致、能从分散代码中定位相关文件。

### 玩法切片策划（1 人）

- **职责**：从源码中挑选 4-6 类代表性玩法，做成"玩家视角 + 数据流"的切片。
- **产出**：`01-raw-findings/gameplay-slices.md`、`02-user-stories/player-stories.md`
- **核心能力**：能把代码还原成玩家体验流程。

## 机制抽象组

### 任务机制设计师（1 人）

- **职责**：从源码中抽象通用机制（状态机、触发器、目标判定、奖励结算、失败/重置、并发限制、限额等）。
- **产出**：`01-raw-findings/mechanisms.md`、`02-user-stories/system-stories.md`
- **核心能力**：能从具体实现中提取通用模式。

### 引擎架构师（2+ 人）

- **职责 1**：把通用机制映射到题材无关 engine 核心，输出抽象方案。
- **职责 2**：思考题材包（UGC）创作层应暴露的最小表面。
- **产出**：`03-engine-insights/abstraction-options.md`、`03-engine-insights/ugc-surface.md`
- **核心能力**：区分 engine 核心与题材包内容，识别可复用原语。

### UGC 游戏专家（1 人）

- **职责**：从创作者视角审视子系统可扩展性，评估哪些机制适合暴露给题材包创作者。
- **产出**：`03-engine-insights/creator-perspective.md`、`02-user-stories/operator-stories.md`
- **核心能力**：理解创作者门槛与创作面设计。

### 横向对比验证员（1 人）

- **职责**：交叉检查各实现，找出共同模式与特例，验证核心模型的覆盖度。
- **产出**：`04-redteam-review/cross-check-report.md`
- **核心能力**：善于发现矛盾、遗漏与伪通用。

## 现代评审组

### 现代任务玩法设计师（1 人）

- **职责**：对标当前主流游戏设计，评估 LPC 机制的当代可玩性与过时风险。
- **产出**：`03-engine-insights/modern-design-review.md`、`04-redteam-review/modern-challenges.md`
- **核心能力**：熟悉现代 MMO / 开放世界 / 手游设计。

### 玩家心理与留存专家（1 人）

- **职责**：从动机心理学、留存曲线、心流节奏、社交压力等角度点评玩家体验。
- **产出**：`03-engine-insights/player-psychology.md`、`04-redteam-review/player-experience-risks.md`
- **核心能力**：理解玩家行为动机与挫败来源。

### 商业化与增长专家（1 人）

- **职责**：从付费设计、UGC 创作者经济、题材包消费、用户增长等角度评估商业潜力。
- **产出**：`03-engine-insights/commercialization.md`、`04-redteam-review/commercial-risks.md`
- **核心能力**：理解游戏经济、付费与增长模型。

## 终审组（评审委员会）

由 5 人组成：玩法切片策划、引擎架构师 1 人、UGC 游戏专家、现代任务玩法设计师、商业化与增长专家。

- **职责**：审阅所有初稿、组织红队对抗、对分歧做裁决、最终汇总。
- **产出**：`05-synthesis/final-report.md`

## 角色调整原则

- 如果子系统没有明显的 UGC 创作面，可以减少或合并 UGC 相关角色。
- 如果子系统 heavily 依赖数值平衡，可以增加数值策划角色。
- 如果子系统涉及网络/性能/安全，可以增加对应技术专家。
