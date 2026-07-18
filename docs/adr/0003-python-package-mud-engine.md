---
Status: accepted
---

# Python 包名定为 mud_engine

M1 绿场启动前，将 import 包从 ADR-0002 约定的 `src/xkx/` 改为 `src/mud_engine/`（`import mud_engine`）。`pyproject.toml` 发行名为 `mud-engine`。理由：新目标是题材无关核心引擎，不再绑定《侠客行》品牌语义；`mud_engine` 不与工作区目录 `engine/` 同名，避免 `import engine` 与路径混淆；绿场阶段改名成本最低。archive tag `archive/engine-pre-m1-rewrite` 内旧路径仍为 `engine/src/xkx/...`，查阅命令不变。

## 考虑过的选项

- **保留 `xkx`**：与仓库品牌一致，但易被误解为侠客行专用引擎。
- **`src/engine` + `import engine`**：与工作区 `engine/` 同名，文档与口头交流易混。
- **`mudcore`**：语义可行，最终选用更直白的 `mud_engine`。

## 影响

- 活代码 import 统一为 `from mud_engine ...`；ADR-0002 中「保留 `src/xkx/`」的包路径约定由本 ADR 取代，0002 其余条款（工作区路径、tag 冻结）不变。
