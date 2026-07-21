# 10 — 三条交叉测试

**What to build:** 三条此前分开测试导致组合路径没被验证过的交叉场景：(a) 内容包模式下建立 `Engaged` 交战关系后 save→restore，交战状态与 `pack_manifest` 都能正确恢复；(b) 一个声明了 `SkillBehavior` 钩子的招式，通过完整的 tick 驱动自动交战回合（而不是直接构造 `CombatContext` 调用 `resolve_attack`）触发钩子，证明钩子在真实调度链路里也生效；(c) 玩家骑乘坐骑沿官道走到渡口，渡船在场时骑乘状态 `go` 过河，坐骑与骑手同步换房间、且这条组合不会被 `Terrain.cost` 校验意外拒绝。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) B3-4（P1-6/T1）。

**Blocked by:** 03（(b) 项断言 `SkillBehavior.hit_by`/`post_action` 的返回值需要建立在新签名之上）。

**Status:** resolved

- [x] 新增（或扩展现有 `test_load_pack.py`/`test_m3_pack_loop.py`）一条测试：`--pack` 模式下建立 `Engaged` 后 `save_world`→`restore_world`，断言双方 `Engaged.opponent` 正确恢复、`pack_manifest` 正确恢复（走 `reattach_pack_manifest`）。
- [x] 新增（或扩展现有 `test_skill_behavior_hooks.py`）一条测试：通过 `attach_combat_system` + `TickLoop.advance()` 的真实 tick 路径（而非直接构造 `CombatContext` 调 `resolve_attack`）触发一个声明了 `SkillBehavior` 钩子的招式，断言钩子确实生效、播报文案出现在真实的战斗播报里。
- [x] 新增（或扩展 `test_mount.py`/`test_ferry.py`）一条测试：玩家骑乘状态沿官道走到渡口房间，渡船在场时 `go` 过河，断言坐骑 `Position` 与骑手同步更新，且 `Terrain.cost` 校验不会因为渡口房间本身声明的地形代价而误拒绝这次移动。
- [x] 三条测试均遵循现有 restore 综合测/tick 层 seam 的既有断言模式，不新增测试基础设施。
- [x] `just test` 全绿。

## Comments
