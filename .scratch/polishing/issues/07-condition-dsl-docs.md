---
Status: resolved
---

# 07 — B9 条件 DSL 文档化

**What to build:** 新增文档（`docs/condition-dsl.md`，被 `docs/creator-contract-v0.md` 引用）系统讲清 `entry_guard`/`day_shop` 派生 `is_day`/`skills.*.learn_condition`/`npcs.*.behaviors[].when` 四个接入点共用的条件 DSL（`predicate`：`is_night`/`is_day`/`is_raining`/`is_wielding_edged_weapon`；`field`+`value` 精确匹配（`phase`/`faction_id`/`gender`/`has_faction`/属性）；`gte`；`and`/`or`/`not` 组合），每个接入点至少配一个取自现有官方范本的真实 YAML 片段（如少林山门 `entry_guard`、打铁铺 `day_shop`、`luohan_quan.learn_condition`）。文档须显式列出「现在不支持」清单（背包任意物、任务旗标、局部天气查询等），对齐 GAP 台账表述，不新增查询面字段/代码变更。

对应 spec：`.scratch/polishing/spec.md` §B9（User Stories 25–26；Implementation Decisions「B9」）。

**Blocked by:** None — 可立即开始。

- [ ] `docs/condition-dsl.md`：分节讲清四个接入点各自的字段位置（`rooms.*.entry_guard`、`day_shop` 派生 `is_day`、`skills.*.learn_condition`、`npcs.*.behaviors[].when`）+ 共用语法（`predicate`/`field`+`value`/`gte`/`and`/`or`/`not`）。
- [ ] 每个接入点至少一段取自现有官方范本（少林山门 `entry_guard`、打铁铺 `day_shop`、`luohan_quan.learn_condition` 等）的真实 YAML 片段，直接摘自 `engine/data/*.yaml`，不虚构示例。
- [ ] 「现在不支持」清单：背包任意物查询、任务旗标查询、局部天气查询等，措辞与 `docs/gap-ledger.md` 对齐。
- [ ] `docs/creator-contract-v0.md`：新增一行引用 `docs/condition-dsl.md`。
- [ ] 可选：文档内嵌 YAML 范例用既有 `load_scene` seam 跑一次「能加载、条件求值符合预期」验证测试（非必需，如加则归入 `test_conditions.py`/`test_entry_guard.py`）。
- [ ] 无契约/加载器代码变更（本票仅产出文档）。
