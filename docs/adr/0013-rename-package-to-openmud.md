---
Status: accepted
---

# Python 包名从 mud_engine 改为 openmud

M3 停机加固阶段，将 import 包从 [ADR-0003](0003-python-package-mud-engine.md) 约定的 `src/mud_engine/`（`import mud_engine`）改为 `src/openmud/`（`import openmud`）。`pyproject.toml` 中 wheel 打包路径同步改为 `src/openmud`，`known-first-party` 同步改为 `openmud`；发行名暂时保持 `mud-engine`，后续如发布 PyPI 可再评估是否改为 `open-mud`。

## 考虑过的选项

- **保留 `mud_engine`**：表意直白，但带下划线、读写较长，更像内部技术包名。
- **`open_mud`**：符合 PEP 8，但两个词之间边界清晰，更像描述性短语。
- **`openmud`**（选定）：更短、更像独立产品/品牌，参考 `fastapi`、`openai` 等合并词风格；同时保留 "Open MUD" 的语义。
- **`core`**：语义过泛，不适合作为顶层包名。

## 影响

- 所有活代码（`src/`、`tests/`、`scripts/`）的 import 统一改为 `from openmud ...`。
- 当前基线文档（`CLAUDE.md`、`docs/condition-dsl.md`、`docs/scene-authoring-guide.md`、`docs/creator-contract-v0.md`、`.scratch/` 下 active tickets 等）中的包名引用同步更新。
- 历史归档（`docs/archive/`、`.scratch/m1-core-engine-skeleton/`、`.scratch/m2-mvp-scene-playable/`、`.scratch/m3-engine-architecture-review/`、`.scratch/research/`、`docs/adr/0003-python-package-mud-engine.md`）保持原样，以保留决策历史。
