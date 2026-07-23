---
Status: resolved
---

# 10 — C12 刷怪条件扩展（官方 hooks 参数化）

**What to build:** 既有官方刷怪钩子（如 `bandit_ambush`）新增读取 `RoomHookBinding.params` 里可选条件参数（如 `min_item_value: <int>`）的能力：扫描触发实体背包非货币物品价值总和/单件是否达到阈值，达到才进入既有概率刷怪判定。整个扩展只在官方轨可信 hook 实现内部完成，**不**往 `entry_guard`/`day_shop`/`learn_condition`/`behaviors[].when` 共用的条件 DSL（`conditions.py`/`ai.condition_from_data`）新增任何谓词或字段；UGC 内容包仍不能声明 `hooks`（ADR-0012 边界不变）。

对应 spec：`.scratch/polishing/spec.md` §C12（User Stories 35–37；Implementation Decisions「C12」）；LPC 出处 [session-qa-provenance-2026-07-23.md](../../polishing-candidate-review/session-qa-provenance-2026-07-23.md) Q8（土门子贵重物才刷马贼）。

**Blocked by:** None — 可立即开始。

- [x] `room_hooks.py`：`bandit_ambush`（及后续同类刷怪钩子）读取 `ctx.params` 里的 `min_item_value`（可选，缺省则不启用该条件，行为与现状一致）；实现「触发实体背包非货币物品价值总和/单件达到阈值」判定函数，供刷怪钩子内部调用。
- [x] 不改动 `ai.py` 条件求值器或 `conditions.py`：本票不新增任何 DSL 谓词/字段（如不新增 `has_item_value_gte`）。
- [x] 验收对照：`min_item_value` 阈值/触发概率数值为本引擎自定义可调参数，不追求与 LPC 源码位一致（ADR-0001，不做行为等价验证）。
- [x] `engine/data/xingxiu_mechanics.yaml`（或既有 `bandit_ambush` 验收房间）补充/调整一条使用 `min_item_value` 的场景切片，用于测试锚点。
- [x] `docs/gap-ledger.md`：「运行时改世界机关」行补一句「贵重物等条件走官方 hooks params，已落地」。
- [x] `test_room_hooks.py`/`test_xingxiu_mechanics_08.py`（现有 `bandit_ambush` 测试文件）扩展 `params.min_item_value` 用例：达阈值触发、未达阈值不触发。
- [x] S3 回归：UGC 包声明 `hooks`（含本票新增的 `params` 形状）仍必须失败，复用既有 ADR-0012 边界测试模式，确认本次扩展未打开 UGC 缺口。
- [x] `just test` 全绿。

## Comments

**实现摘要（2026-07-23）**

- 判定：`RoomHookContext.actor_meets_min_item_value(min_value)`——背包 `Valuable` 单件或总和达阈值；角色 `Currency` 不计。
- 钩子：`bandit_ambush` 读可选 `params.min_item_value`；缺省行为与扩展前一致。
- 验收切片：`xingxiu_mechanics.yaml` 的 `ambush_trail` 设 `min_item_value: 100`；峰脚 `iron_sword` 设 `value: 100`（先 `get 铁剑` 再进小径才刷怪）。
- 阈值 `100` 为本引擎可调参数，不做 LPC 位等价（ADR-0001）。
- 未改 `conditions.py` / `ai.condition_from_data`；UGC 含 `hooks`+`min_item_value` 仍加载失败（S3）。
