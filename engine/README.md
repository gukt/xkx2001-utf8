# mud_engine — 题材无关的核心 MUD 引擎

Greenfield Python 引擎。路径固定为仓库根下的 `engine/`。

旧实现（约 45k 行，服务于「全量复刻侠客行 + 行为等价验证」）已从工作区移除，冻结于 git tag
`archive/engine-pre-m1-rewrite`。查阅：`git show archive/engine-pre-m1-rewrite:engine/src/xkx/...`。
禁止 import、禁止当重写起点。见 [ADR-0002](../docs/adr/0002-engine-workspace-greenfield-reset.md)。

**当前阶段**：M1 核心引擎骨架（空场景 + 命令-移动-存档最小闭环）。见
[M1 spec](../.scratch/m1-core-engine-skeleton/spec.md) 与根目录 [PROGRESS.md](../PROGRESS.md)。

## 开发

优先用仓库根的 `just`（自带 `cd engine && uv run`）：

```bash
just install   # uv sync --all-extras
just test
just lint
just gate      # lint + test
```

## 布局

- `src/mud_engine/`：引擎源码（绿场，从零写；`import mud_engine`）
- `tests/`：测试（pytest + hypothesis）
- `prototypes/`：throwaway 设计原型（不进正式包路径，可随时删）
