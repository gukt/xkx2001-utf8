# Domain Docs

工程类 skill 在探索代码库时，应如何消费本仓库的领域文档。

## 探索前先读这些

- 根目录下的 **`CONTEXT.md`**（如果存在）。
- **`docs/adr/`**——阅读与当前要动手的区域相关的 ADR。本仓库的编号是 `ADR-NNN-slug.md`（例如 [ADR-0001](../adr/ADR-0001-python-toolchain-and-skeleton.md)），不是某些模板默认的裸 `NNNN-slug.md`。
- **`docs/xkx-arch/00-05`**——架构基线及其决策溯源；在 `CONTEXT.md`/ADR 尚未覆盖的地方，暂时把这些文档也当作领域文档看待，它们比本文件更早，承载了项目目前的统一语言。
- 根目录下的 **`CLAUDE.md`**——本仓库的操作手册（约束、不变量、开发规范）；按其自身要求，每个 session 都要读，无论主题是什么。

如果 `CONTEXT.md` 还不存在，**默默跳过即可**——不用提示它缺失，也不用建议现在就创建。`/domain-modeling` skill（通过 `/grill-with-docs` 和 `/improve-codebase-architecture` 触达）会在术语或决策真正被解决时才惰性创建它。

## 文件结构

single-context 仓库（本仓库，以及绝大多数仓库都是这种）：

```
/
├── CLAUDE.md                          ← 操作手册，每个 session 都读
├── CONTEXT.md                         ← 领域词汇表，惰性创建
├── PROGRESS.md                        ← 跨 session 交接的活状态
├── docs/adr/                          ← ADR-NNN-slug.md，一条决策一个文件
├── docs/xkx-arch/                     ← 架构基线（00-05）+ 决策溯源
└── engine/src/xkx/                    ← greenfield 新引擎的 Python 实现
```

`engine/` 之外的仓库根目录是 LPC 规格源（只读参考），不是 multi-context 意义上的第二个 context——这里没有 `CONTEXT-MAP.md`，本文件的指引也不适用于它。

## 使用词汇表里的术语

当你的输出提到某个领域概念时（issue 标题、重构提案、假设、测试名），使用 `CONTEXT.md`（如果已存在）或 `docs/xkx-arch/00-05`（在它存在之前）里定义的术语。不要漂移到词汇表明确避免的同义词上。

如果你需要的概念还不在词汇表里，这是一个信号——要么是你在发明项目里不用的语言（应重新考虑），要么是真的存在一个空白（记下来交给 `/domain-modeling`）。

## 标记与 ADR 的冲突

如果你的输出和某条已有 ADR 冲突，应明确指出，而不是悄悄地覆盖它：

> _与 ADR-0007（事件溯源订单）冲突——但值得重新打开，因为……_

在本仓库，还要额外检查是否与 `CLAUDE.md` 里列出的六条收缩约束或关键架构不变量冲突——这些约束的位阶高于单条 ADR，需要用户明确拍板才能重新讨论（约束 6 明确禁止重新打开那三个已裁决的开放问题）。
