# openmud — 题材无关的核心 MUD 引擎

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

- `src/openmud/`：引擎源码（绿场，从零写；`import openmud`）
- `tests/`：测试（pytest + hypothesis）
- `prototypes/`：throwaway 设计原型（不进正式包路径，可随时删）

## 测试约定

测试名走 BDD 风格：用嵌套类把 Given/When 场景分组，方法名只写 Then（一个方法一个行为焦点，不要塞复合断言）。外层类通常对应"在测什么"（一个命令、一个函数），嵌套类对应"在什么前提/条件下"；没有真正分支的场景不用强行嵌套，一个类里平铺几个 `test_*` 方法即可。

```python
class TestGo:
    class WhenDirectionHasNoExit:
        def test_player_does_not_move(self) -> None: ...
        def test_warning_message_mentions_the_direction(self) -> None: ...

    class WhenDirectionHasExit:
        def test_moves_player_to_the_target_room(self) -> None: ...
```

失败时 pytest 的 node id（如 `TestGo::WhenDirectionHasNoExit::test_player_does_not_move`）本身就是一句完整的行为描述，对人和对 coding agent 都好扫。

**这些嵌套类不带 `Test` 前缀，必须依赖 `pyproject.toml` 里的 `python_classes = ["Test*", "When*", "Given*"]` 才会被 pytest 收集**——用 pytest 默认配置（只认 `Test*`）会把它们静默跳过，不报错也不警告。新增分组类名如果不是 `When*`/`Given*`，记得同步扩展这个列表。
