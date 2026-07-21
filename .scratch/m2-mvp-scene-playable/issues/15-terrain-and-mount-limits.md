# 15 — 地形通行与坐骑限制：Terrain 组件 + 骑乘校验 + 精力耗尽摔落

**What to build:** 落地 spec Implementation Decisions「F1」末段：`Terrain(cost: int = 1)` 房间级组件（走 01 号票注册表挂载）；`go` 命令扩展：玩家处于骑乘状态且目标房间 `Terrain.cost > Mount.ability` 时拒绝移动并提示"这地方骑不过去"（步行不受此限制，可以先 `unride` 再走）；骑乘状态下移动额外消耗坐骑的 `jingli_current`（扣减量 = 目标房间 `Terrain.cost` 的一个数据驱动系数，不是玩家自己的精力）；坐骑 `jingli_current` 归零时转入类似 06 号票的"昏迷"态（**复用** `Unconscious` marker，不新建平行的"坐骑昏迷"状态类型），同时强制解除骑乘关系（骑手被摔下来，双向 `Riding`/`Mount.ridden_by` 清空），移动结算正常完成（玩家步行完成本次移动，只是失去坐骑加速收益）。

**Blocked by:** 01（`Terrain` 走注册表），06（复用 `Unconscious` marker），10（`Mount`/`Riding`）。

**Status:** resolved

- [x] `Terrain(cost: int = 1)` 组件落地，走房间级能力注册表（YAML `cost:`/`terrain:` 字段，命名以实现阶段与 spec 用词"房间的 cost" 对齐）。
- [x] `go` 命令扩展：骑乘状态下，目标房间 `Terrain.cost > Mount.ability` 时拒绝移动，给出提示且不消耗坐骑精力（校验在移动发生前）；不骑乘时不受 `Terrain.cost` 限制（步行永远可通行，只是可能慢，MVP 不建模步行速度差异）。
- [x] 骑乘且校验通过的移动：扣减坐骑 `jingli_current`（扣减量与 `Terrain.cost` 的关系需是明确、可测试的数据驱动公式，不是魔法数字）。
- [x] `jingli_current` 归零：坐骑挂 `Unconscious`（复用 06 号票组件，不新建组件类型）；骑手 `Riding` 与坐骑 `Mount.ridden_by` 双向清空（摔下来）；本次移动仍然完成（骑手落地在目标房间，坐骑留在——需明确坐骑摔下来后停留在哪个房间：移动发生前的房间还是移动后的房间，实现阶段决定并测试锁定，建议摔在移动后的房间，即"人马一起走到半路马倒了"的直觉）。
- [x] 命令层/tick 层测试覆盖：地形限制拒绝、正常骑乘通过、精力耗尽摔落三种路径。
- [x] 存档往返：`Terrain.cost` 与坐骑摔落后的状态 save→restore 一致。
- [x] 现有测试全绿不回归。
