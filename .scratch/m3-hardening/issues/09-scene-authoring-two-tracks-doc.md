# 09 — 官方/示例双轨范本文档

**What to build:** 有一份文档解释清楚"默认场景 `engine/data/m2_mvp_scene.yaml`"与"内容包 `manifest.yaml + scene.yaml`"这两条轨道之间的关系——它们共用同一套场景 YAML 语法（06 号票冻结的 v0 契约），差异只在"是否被一份 `manifest.yaml` 包裹、是否通过 `--pack` 加载"，创作者不会误以为这是两套互相不兼容的格式,需要分别学习。这份文档明确说明本窗口不做官方场景包化（不强制把默认场景改造成一个带 `manifest.yaml` 的内容包目录），只做说明性文档，双轨共存的现状被诚实记录。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) B3-3（P1-4/C1）。

**Blocked by:** 06（创作者契约 v0——本文档需要引用其冻结的 v0 契约作为双轨共用基础）。

**Status:** ready-for-agent

- [ ] 新增文档（建议 `docs/scene-authoring-guide.md`）：说明"官方默认场景"（`engine/data/m2_mvp_scene.yaml`，走无 `--pack` 的默认 CLI 入口，无 manifest 包裹）与"内容包"（`manifest.yaml` + `scene.yaml`，走 `--pack`/`--validate`）共用同一份 06 号票冻结的场景 YAML v0 契约,唯一差异是是否被 manifest 包裹、走哪条 CLI 入口。
- [ ] 引用 `.scratch/m3-ugc-loop-creation-surface/example-pack/` 作为内容包轨的具体样例，引用 `engine/data/m2_mvp_scene.yaml` 作为官方轨的具体样例。
- [ ] 明确声明本文档**不伴随任何代码改动**（不做官方场景包化），纯说明性产出。
- [ ] 无自动化测试要求，验收标准是人工核对文档内容与引用链完整。

## Comments
