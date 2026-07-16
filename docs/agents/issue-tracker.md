# Issue Tracker：本地 Markdown

本仓库的 issue 和 spec（也可以理解为 PRD）以 markdown 文件的形式存放在 `.scratch/` 下。

## 约定

- 每个 feature 一个目录：`.scratch/<feature-slug>/`
- spec 文件为 `.scratch/<feature-slug>/spec.md`
- 实现类 issue 一票一文件，路径为 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号——绝不用一个合并的 tickets 文件
- triage 状态记录在每个 issue 文件顶部的 `Status:` 行（角色字符串见 `triage-labels.md`）
- 评论和对话历史追加在文件末尾的 `## Comments` 标题下

## 当某个 skill 说"发布到 issue tracker"时

在 `.scratch/<feature-slug>/` 下新建一个文件（目录不存在则先创建）。

## 当某个 skill 说"取相关的 ticket"时

读取所引用路径对应的文件。用户通常会直接给出路径或 issue 编号。

## Wayfinding 相关操作

供 `/wayfinder` 使用。**地图**（map）是一个文件，每个**子项**（ticket）对应一个子文件。

- **地图**：`.scratch/<effort>/map.md`——包含 Notes / Decisions-so-far / Fog 三块内容。
- **子 ticket**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 开始编号，正文写问题本身。`Type:` 行记录 ticket 类型（`research`/`prototype`/`grilling`/`task`）；`Status:` 行记录 `claimed`/`resolved`。
- **阻塞关系**：顶部一行 `Blocked by: NN, NN`。当所列的每个文件都是 `resolved` 时，该 ticket 才算解除阻塞。
- **frontier（可认领的边界）**：扫描 `.scratch/<effort>/issues/` 下状态为 open、未被阻塞、未被认领的文件；编号靠前者优先。
- **认领（claim）**：动手前先把 `Status` 设为 `claimed` 并保存。
- **解决（resolve）**：在 `## Answer` 标题下追加答案，把 `Status` 设为 `resolved`，然后在地图的 Decisions-so-far 里追加一条指向该 ticket 的摘要 + 链接。

## 为什么用本地 markdown 而不是 GitHub Issues

`git remote` 指向 GitHub（`gukt/xkx2001-utf8`），这本是该 skill 的默认姿态。但本仓库覆盖了这个默认值：这里的工程决策一直全部记录在本地 markdown 里（`docs/adr/ADR-NNN-xxx.md`、`PROGRESS.md`），从未用 GitHub Issues 追踪过这类内部架构决策。用本地 markdown 能让 wayfinder 的地图和 ticket 与项目在每个 session 开工时读的其他文档保持同一种媒介。
