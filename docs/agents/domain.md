# Domain Docs

工程类 skill 在探索代码库时，应如何消费本仓库的领域文档。

## 探索前先读这些

- 根目录下的 **`CONTEXT.md`**（如果存在）。
- **`docs/adr/`**——重设后的新决策日志，从头编号，惰性创建（第一条 ADR 落地时才建目录）。格式 `NNNN-slug.md`，不带 `ADR-` 前缀，见 [ADR-FORMAT.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/ADR-FORMAT.md)。
- **`CLAUDE.md`**——本仓库的操作手册；按其自身要求，每个 session 都要读，无论主题是什么。
- **`docs/archive/`**——2026-07-17 项目重设前的完整历史（旧架构基线 `docs/xkx-arch/`、旧 ADR `ADR-0001`～`ADR-0064`、旧 `PROGRESS.md`、旧 `CLAUDE.md`、战略复审）。**只读背景参考，不是当前基线**——查某个历史决策的论证过程、或理解 `engine/` 代码里一段实现的来龙去脉时才去找，见 [docs/archive/README.md](../archive/README.md)。不要把这里的结论当作当前应遵循的约束。

如果 `CONTEXT.md` 还不存在，**默默跳过即可**——不用提示它缺失，也不用建议现在就创建。`/domain-modeling` skill（通过 `/grill-with-docs` 和 `/improve-codebase-architecture` 触达）会在术语或决策真正被解决时才惰性创建它。

## 文件结构

single-context 仓库（本仓库，以及绝大多数仓库都是这种）：

```
/
├── CLAUDE.md                          ← 操作手册，每个 session 都读
├── CONTEXT.md                         ← 领域词汇表，惰性创建
├── PROGRESS.md                        ← 跨 session 交接的活状态（重设后新起）
├── docs/adr/                          ← 重设后的新 ADR，NNNN-slug.md，惰性创建
├── docs/archive/                      ← 重设前的完整历史，只读参考
└── engine/src/xkx/                    ← greenfield 引擎实现（重设中，去留待评估）
```

`engine/` 之外的仓库根目录是 LPC 规格源（只读参考），不是 multi-context 意义上的第二个 context——这里没有 `CONTEXT-MAP.md`，本文件的指引也不适用于它。

## 使用词汇表里的术语

当你的输出提到某个领域概念时（issue 标题、重构提案、假设、测试名），使用 `CONTEXT.md`（如果已存在）里定义的术语。不要漂移到词汇表明确避免的同义词上。`docs/archive/` 里的旧术语仅供参考，重设后如与新方向冲突不必强行沿用。

如果你需要的概念还不在词汇表里，这是一个信号——要么是你在发明项目里不用的语言（应重新考虑），要么是真的存在一个空白（记下来交给 `/domain-modeling`）。

## 标记与 ADR 的冲突

如果你的输出和某条已有新 ADR（`docs/adr/`）冲突，应明确指出，而不是悄悄地覆盖它：

> _与 `docs/adr/0003-xxx.md` 冲突——但值得重新打开，因为……_

和 `docs/archive/` 里的旧 ADR/旧架构基线冲突不需要这样标记——那批已经被重设撤回，冲突是预期状态，不是需要人工拍板的异常。
