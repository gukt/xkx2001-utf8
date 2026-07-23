---
Status: resolved
---

# 02 — A3 YAML 简写规范化（官方范本清理冗余方位 aliases）

**What to build:** 票 `01`（A1+A2）落地后，清理官方范本（`engine/data/m1_default_scene.yaml`、`engine/data/m2_mvp_scene.yaml`，以及后续 `xingxiu_mechanics.yaml` 等）里因内置同义词而变得冗余的标准方位 `aliases`（如出口已写 `aliases: [东]` 而「东」现在是 `east` 的内置默认同义词）。同步在场景创作文档补充「标准方位不必手写、地名写在目标房一次」的推荐写法段落，防止新创作者照抄旧范本的冗余样板。

对应 spec：`.scratch/polishing/spec.md` §A3（User Stories 8–9；Implementation Decisions「A3」）。

**Blocked by:** `01`（A1+A2 出口导航别名落地，否则清理范本会破坏当前导航行为）。

- [x] 逐条检查官方范本出口 `aliases`，删除与票 `01` 内置默认同义词完全重复的条目；**保留**非标准/自定义地名类 `aliases`（如「武庙」若仍写在出口而非目标房，视情况迁移到目标房 `name`/`aliases` 而非直接删除）。
- [x] `docs/scene-authoring-guide.md`（或等价创作文档）新增段落：说明标准方位不必在每条出口手写、地名建议写在目标房 `name`/`aliases` 一次即可被邻接出口命中，并给出前后对比示例片段。
- [x] 验收：既有场景相关测试（`test_scene_yangzhou_hub.py`、`test_scene_shaolin.py`、`test_verify_m2_matrices.py` 等）在清理后仍全绿；不新增依赖已删别名的断言。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-23）

- **清理规则**：从 `m2_mvp_scene.yaml` / `xingxiu_mechanics.yaml` 出口 `aliases` 删除与 `directions.DIRECTION_FORMS` 完全重复的内置项；另删除与**目标房 `name` 字面相同**的条目（已由层 ② 覆盖，如广场→武庙的「武庙」、北大街→北门的「北门」）。`m1_default_scene.yaml` 仅有出口绰号「北道」，无内置冗余，未改。
- **保留**：非标准绰号/地名仍挂在出口上（如「村里」「官道」「峰顶」「密道」类）；未做「全部迁到目标房」的激进搬迁，避免无谓扩大 Ambiguous 面。
- **文档**：`docs/scene-authoring-guide.md` 新增「出口写法推荐」段（前后对比 YAML）；`docs/creator-contract-v0.md` 出口 `aliases` 行同步一句「标准十向不必手写」。
- **验收**：`just test` 885 绿；场景相关测试未改断言。
