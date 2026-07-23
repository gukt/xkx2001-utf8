---
Status: ready-for-agent
---

# 05 — B6 步行 `cost` 精力

**What to build:** 玩家步行（非骑乘）穿过房间按目标房 `terrain.cost`（缺省按 1 计，与骑乘分支缺省对齐）扣 `jingli_current`（规则：`cost * 2`）；精力不足以支付本次消耗时移动被拒绝并提示原因，不产生「移动后精力为负」或「步行导致昏迷」（昏迷路径仍只走战斗/既有 Unconscious 触发点）。骑乘时坐骑精力扣减规则（`MOUNT_JINGLI_PER_TERRAIN_COST`）不变、与步行消耗互不叠加——`Riding` 组件存在时只走既有骑乘分支。

对应 spec：`.scratch/polishing/spec.md` §B6（User Stories 18–20；Implementation Decisions「B6」）。

**Blocked by:** None — 可立即开始。

- [ ] `commands.py::_cmd_go` 非骑乘分支：读取目标房 `Terrain.cost`（缺省 1），按 `cost * 2` 计算所需 `jingli_current`；`jingli_current` 恰好等于所需消耗时放行（扣至 0），不足则拒绝移动并提示（文案措辞自定，需明确指出精力不足）。
- [ ] 确认 `Riding` 组件存在时的分支完全跳过本规则（不叠加步行消耗），既有骑乘精力扣减路径不变。
- [ ] 不新增契约字段（复用既有 `Terrain.cost`、`Vitals.jingli_current`/`jingli_max`）。
- [ ] 新测试文件或扩展 `test_terrain.py`：覆盖精力充足放行、精力不足拒绝、精力恰好等于消耗放行且扣至 0、骑乘分支不受影响四类场景。
- [ ] `just test` 全绿。
