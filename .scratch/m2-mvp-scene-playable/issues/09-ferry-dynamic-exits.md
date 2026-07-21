# 09 — 渡口渡船：Ferry 组件 + on_tick 周期翻转出口（动态出口机制首个真实用例）

**What to build:** 落地 spec Implementation Decisions「F2」的渡口部分：`Ferry(far_bank: EntityId, cross_interval: int, direction: str)` 组件（挂在渡口房间上，两岸各挂一份，`far_bank` 互相指向对方），走 01 号票的房间级能力注册表挂载（YAML `ferry:` 字段）。场景加载时**不**预先建立"过河"这条 `Exit`（两岸初始互不连通）。新增运行时态 `FerryState`（挂 `world.ferries`，纯内存不进存档，与 `world.nature`/`world.ai` 同构，由 `attach_ferries` 挂载）+ 一个挂 `on_tick` 的系统，按 `cross_interval` 周期翻转"渡船在哪一岸"：到达 A 岸时，往 A 岸房间的 `Exits` 增加一条指向 B 岸的 `Exit`（`direction` 字段声明的方向名），同时移除 B 岸对应的那条（渡船不能同时停靠两岸）。这是 M1 04 号票"运行时可增删出口"机制的**第一个真实题材用例**，直接复用该机制、不新起一套连接机制。`look` 在挂了 `Ferry` 的房间追加一行渡船状态提示（渡船当前在哪一岸/还有多久到达），现算不塞进 `Description`（运行时派生值 vs 启动固定数据不混进同一组件，三态标注精神）。

**Blocked by:** 01（`Ferry` 是房间级能力，走注册表挂载）。

**Status:** resolved

- [x] `Ferry(far_bank, cross_interval, direction)` 组件落地，走房间级能力注册表；`far_bank` 引用另一个房间键，加载期校验该房间已定义且也挂了 `Ferry`（互相指向）。
- [x] `FerryState` 运行时态（不进存档）+ `attach_ferries(world)`（幂等，与 `attach_ai_system` 同构）挂 `on_tick` 订阅者。
- [x] on_tick 系统按周期翻转：渡船到岸时该岸房间 `Exits.by_direction[direction]` 出现一条指向对岸的 `Exit`，离岸的那一侧对应方向条目被移除。
- [x] 渡船不在场时尝试 `go <过河方向>`：因为该方向本来就没有 `Exit` 条目，走现有 `go` 命令"那个方向没有出口"路径即可，不需要新的拒绝分支。
- [x] `look` 在挂 `Ferry` 的房间追加一行渡船状态文案（现算，不写进 `Description`），文案至少体现"在哪一岸"与"距离到达还有多久"两个信息点。
- [x] tick 层测试（复用 `TickLoop.advance`/`dispatch(ON_TICK, ...)` seam）：反复推进 tick，断言出口按周期在两岸间正确转移、渡船状态文案随之更新。
- [x] `attach_ferries` 重复调用不重复注册（同 `attach_ai_system` 幂等约束）。
- [x] 存档恢复后 `FerryState` 不进存档、由下次 `load_scene` 重新填充（同 `world.nature`/`world.ai` 语义，本票不需要额外处理，但需要一条测试验证"restore 后 world.ferries 起始为空/需重新 attach"这一行为不是隐性 bug）。
- [x] 现有测试全绿不回归。
