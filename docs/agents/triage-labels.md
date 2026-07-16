# Triage 标签

各 skill 统一用五个规范的 triage 角色来表达状态。本文件把这五个角色映射到本仓库 issue tracker 实际使用的标签字符串。

| mattpocock/skills 中的标签 | 本仓库 tracker 中的标签 | 含义                           |
| --------------------------- | ------------------------ | ------------------------------ |
| `needs-triage`               | `needs-triage`            | 需要维护者评估这个 issue        |
| `needs-info`                 | `needs-info`              | 等待提出者补充更多信息          |
| `ready-for-agent`            | `ready-for-agent`         | 规格已完备，可交给 AFK agent    |
| `ready-for-human`            | `ready-for-human`         | 需要人来实现                    |
| `wontfix`                    | `wontfix`                 | 不会处理                        |

当某个 skill 提到某个角色时（例如"打上 AFK-ready 的 triage 标签"），使用本表中对应的标签字符串。

由于本仓库的 issue tracker 是本地 markdown（见 `issue-tracker.md`），这里的"标签"指的是每个 issue 文件顶部 `Status:` 行的取值，不是 tracker 原生的 label 对象。
