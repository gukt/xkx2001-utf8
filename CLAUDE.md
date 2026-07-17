# CLAUDE.md - 侠客行 MUD 现代化重构 项目指令

> 本文件每个 session 自动加载。**2026-07-17 项目重设**：原目标架构与取舍战略被发现存在问题，旧的六条收缩约束、关键架构不变量、开发规范已随旧 `CLAUDE.md` 整体归档，不再自动生效。新目标尚未重新设定。
>
> 开工第一件事：读本文件 + [PROGRESS.md](PROGRESS.md)（活状态，目前是重设后的空模板）。需要旧背景（旧目标怎么论证的、踩过什么坑、某个实现决策当时为什么这么做）时去 [docs/archive/README.md](docs/archive/README.md) 找——那批文档冻结但依然是真实历史，不是当前基线。

## 项目一句话（待重新设定）

原定：将经典 LPC MUD《侠客行》（8412 LPC 文件、6414 房间、21 门派）从 0 重构为全新 greenfield Python 项目，行为等价验证。该目标本身及其取舍战略正在重新评估中，本节待新方向确定后重写。

## 仓库拓扑

- `adm/ cmds/ d/ kungfu/ ...`（仓库根）：**LPC 规格源，只读参考，禁止修改**。无论新目标如何调整，这批文件的"只读参考"性质不变。
- [engine/](engine/)：**greenfield Python 项目**（当前工作区）。`src/xkx/` 包，`tests/` 测试。已有实现在新目标下可能大改，具体去留待重设结论。
- [docs/archive/](docs/archive/)：**旧目标的完整历史归档**（架构基线、64 条 ADR、进度归档、战略复审、旧 `CLAUDE.md`/`PROGRESS.md`）。只读参考，不是当前基线，见 [docs/archive/README.md](docs/archive/README.md)。
- [docs/adr/](docs/adr/)：**重设后的新决策日志**，从头编号（惰性创建，第一条 ADR 落地时才建）。格式见 [domain-modeling ADR-FORMAT](.claude/skills/domain-modeling/ADR-FORMAT.md)：`NNNN-slug.md`，不带 `ADR-` 前缀，短段落即可。
- [docs/agents/](docs/agents/)：engineering skills 的仓库级配置（issue tracker / triage 标签 / domain docs 消费规则），与目标本身无关，重设不影响。
- `todo.md` / `README`：遗留的 LPC UTF-8 转码记录，与新项目无关，忽略。

## 开发工具链（重设前的约定，暂沿用）

以下是纯工具链事实，与"目标是什么"无关，重设不改变这些，除非新方向明确要换语言/框架：

- Python >=3.12，包名 `xkx`，代码在 [engine/src/xkx/](engine/src/xkx/)。
- **Python 命令目录**：所有 `python`/`pytest`/`ruff`/`uv` 命令在 [engine/](engine/) 下执行（`cd engine && ...`）。**优先用 task runner**：仓库根 [justfile](justfile) 封装了常用命令，自带 `cd engine && uv run`；`just --list` 列出全部命令。
- 测试：pytest + hypothesis。lint/format：ruff，行长上限 100。
- 注释/排版：中文回复，中英文之间加空格，类注释不带 `@author`/`@version`。
- 提交：只在用户要求时 commit/push；在 master 分支时先开分支。

## 决策日志（ADR）

新方向确定后，架构假设的偏离在 [docs/adr/](docs/adr/) 写一条 ADR（`NNNN-slug.md`，不带前缀，格式见上）。旧 ADR-0001～0064 在 [docs/archive/adr/](docs/archive/adr/)，只做背景参考，不作为新决策的约束。

## session 交接

- 开工第一件事：读 [PROGRESS.md](PROGRESS.md) + 本文件。
- 收工前：更新 [PROGRESS.md](PROGRESS.md) 的 Done / In Progress / Blocked / Next Up + 日期。
- 长任务跨 session：在 PROGRESS.md 的 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。

## 其他注意事项

- 根目录下是侠客行源码，engine 下是新引擎。执行命令时注意区分工作目录层级。
- 思考、回复和关键注释都用中文，中文与英文或数字之间加空格排版。
- 优先使用 `just` 命令（如果有）。

## Agent skills

### Issue tracker

本地 markdown（`.scratch/<effort>/`），未用 GitHub Issues。见 [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md)。

### Triage labels

默认五角色标签（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix）。见 [docs/agents/triage-labels.md](docs/agents/triage-labels.md)。

### Domain docs

single-context：根目录 `CONTEXT.md`（惰性创建）+ [docs/adr/](docs/adr/)（新决策，惰性创建）+ [docs/archive/](docs/archive/)（旧背景参考）。见 [docs/agents/domain.md](docs/agents/domain.md)。

## 待办（重设进行中）

- [ ] 重新设定项目目标与取舍战略（参考 [docs/archive/strategy-review/](docs/archive/strategy-review/) 但不受其结论约束）
- [ ] 决定 `engine/` 已有实现的去留范围（全部重来 / 部分复用 / 逐子系统评估）
- [ ] 新目标定稿后重写本文件的"项目一句话"与架构不变量章节
