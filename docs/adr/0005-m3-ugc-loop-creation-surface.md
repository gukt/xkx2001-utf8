---
Status: accepted
Superseded-in-part-by: 0006
---

# M3 UGC 闭环以包外声明式内容为创作面

[03 号票](../../.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 原结论是"不沿用旧 DSL 四层、从零设计但保留避坑教训"。M3 前细化后拍板：M3「创作→加载→可玩」一次打通的创作面是**可独立加载的非官方内容包（manifest + 声明式场景数据，演进自现有 `scene_loader` YAML）+ 包外创作**；不交付游戏内编辑器、Web 评审台、Ink 对话树、RestrictedPython 逃生舱，也不强制 LLM Orchestrator。详见 03 号票 Refinement 节。

**归类更正（2026-07-21）**：子系统 9「编辑器」不再维持「现代化改造」——用户确认引擎不做原版编辑器/留言板能力，创作 UX 走独立 Web 平台（post-MVP）。改判与 backlog 见 [ADR-0006](0006-no-engine-editor-board-post-mvp-creator-platform.md)。本 ADR 其余（M3 创作面边界）仍有效。

## 考虑过的选项

- **M3 把游戏内编辑器升为 MVP 必做**：否决。与 07 号票 M3 定义不符，且会把 UGC 闭环绑到 LPC 文选式交互上。
- **M3 重建旧 L0–L3 + Agent 编排**：否决。与 03 原结论冲突，且超出"打通一次"范围。
- ~~把子系统 9 改判丢弃~~：当时否决；已被 [ADR-0006](0006-no-engine-editor-board-post-mvp-creator-platform.md) 改判为丢弃。
