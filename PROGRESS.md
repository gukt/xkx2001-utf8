# 项目进度

> 本文件是跨 session 的"活的状态"——每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> **2026-07-17 项目重设**：原目标与取舍战略被发现存在问题，重新设定目标中。重设前的完整进度历史已归档至 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)（含更早的按阶段归档 [docs/archive/progress-archive/](docs/archive/progress-archive/)），仅作背景参考，不代表当前状态。

**最后更新**：2026-07-17（项目重设，本文件重新起草）

## 当前状态速览

- **阶段**：目标重设中，尚无新阶段划分。
- **分支**：见当前 git 分支。
- **engine/ 现状**：重设前已有实现（详见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md) 与 [docs/archive/progress-archive/](docs/archive/progress-archive/)），去留待评估。

## Done

（重设后暂无——历史 Done 见 [docs/archive/](docs/archive/)。）

## In Progress

- 重新设定项目目标与取舍战略。

## Blocked

**当前无阻塞项。**

## Next Up

1. 明确新目标与范围。
2. 决定 `engine/` 已有实现的去留（参考 [docs/archive/strategy-review/](docs/archive/strategy-review/) 的进度/偏离分析，但结论不受其约束）。
3. 新目标定稿后重写 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量章节。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR（[docs/adr/](docs/adr/)，重设后从头编号）。
