---
Status: accepted
---

# engine/ 路径保留，工作区绿场清空

[04 号票](../../.scratch/mvp-scope/issues/04-engine-code-disposition.md) 已拍板「整体重写、旧代码只作参考」，但未定文件系统落点。M1 第 0 步拍板：

- **保留路径名 `engine/`** 作为唯一活代码根（`src/mud_engine/`、`tests/`、`justfile`/`CLAUDE.md` 约定；包路径见 [ADR-0003](0003-python-package-mud-engine.md)）。
- **旧树不进工作区、不建 `engine_v2`、不整棵搬进 `docs/archive/`**——避免 coding agent 双真相、误复用、以及日常 grep/glob 扫到约 45k 行废代码的 token 浪费。
- **冻结方式**：git tag `archive/engine-pre-m1-rewrite`（指向清空前的 commit）。按需查阅：`git show archive/engine-pre-m1-rewrite:engine/src/xkx/...`。
- **例外保留**：`engine/prototypes/`（throwaway，如 `ecs_ugc`）可留在工作区，不进入正式包 import 路径。

## 考虑过的选项

- **`engine_v2` 双目录并存**：否决。永久双真相，文档/just/import 全要改，agent 最易改错树。
- **整棵归档到 `docs/archive/engine-...`**：否决。与「LPC 只读参考」表面一致，但旧 engine 是可被误 import 的 Python，且日常会持续消耗 token。
- **在 `engine/` 内渐进清理、新旧混放**：否决。半清半留时 agent 会把旧模块当起点，直接违背整体重写。

## 影响

- 工作区 `engine/` 自本 ADR 起即为绿场；M1 及后续实现只往这里写。
- 旧实现的形状参考（ECS、原子写存档等）优先读 [M1 spec](../../.scratch/m1-core-engine-skeleton/spec.md) 与已吸收的教训；确需对照源码时再用 tag 按需 `git show`。
