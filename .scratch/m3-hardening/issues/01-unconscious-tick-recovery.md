# 01 — 昏迷 tick 自动苏醒

**What to build:** 玩家气血耗尽陷入昏迷（`Unconscious`）后，即使没有人再打他一下，经过一段 tick 驱动的时长也会自然醒来恢复行动能力，不再是只能等被杀的软锁。苏醒阈值与醒来后的气血恢复比例是挂在 `DeathPolicy` 上的数据驱动参数（与现有 `penalty_ratio`/`revive_room_key` 同构），题材包可覆盖，不是硬编码常量。苏醒只清除 `Unconscious`，不重新触发交战（昏迷时 `Engaged` 已经在 `_handle_player_depleted` 里清过）。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-2。

**Blocked by:** None — 可立即开始。

**Status:** resolved

- [x] `Unconscious`（`engine/src/mud_engine/components.py`）新增字段 `ticks_remaining: int`，陷入昏迷时按 `DeathPolicy` 参数写入初值（不再是空 marker）。
- [x] `DeathPolicy`（`death_flow.py`）新增 `unconscious_recovery_ticks: int`（默认给一个 MVP 数值，如 5）与 `recovery_vitals_ratio: float`（默认如 0.2）两个数据字段，场景可声明覆盖。
- [x] 新增一个挂在 `world.events` 的 `on_tick` 订阅者（与 `attach_ai_system`/`attach_ferries` 同构的 `attach_xxx` 函数，放在 `death_flow.py`）：遍历 `entities_with(Unconscious)`，每 tick 递减 `ticks_remaining`，归零时移除 `Unconscious`、把 `Vitals.qi_current` 设为 `max(1, int(qi_max * recovery_vitals_ratio))`、推一条 `world.pending_messages` 提示"你悠悠转醒"。不触碰 `Engaged`。
- [x] `save.py` 对应组件 codec 扩展支持新字段；对老存档（缺 `ticks_remaining` 的昏迷态实体）做"缺失字段回退默认值"处理，不新增迁移框架。
- [x] 不新增 `rest` 命令，不改动昏迷相关的现有文案（US23）。
- [x] 测试（tick 层 seam）：反复调用 `TickLoop.advance()`/`dispatch(ON_TICK, ...)` 断言 `ticks_remaining` 递减、归零后 `Unconscious` 被移除、`Vitals.qi_current` 恢复到预期比例、`Engaged` 不被重新建立；覆盖场景覆盖 `DeathPolicy` 参数的用例；覆盖老存档缺字段回退默认值的用例。
- [x] `just test` 全绿，不破坏现有 `test_death_flow.py`/`test_death.py`。

## Comments
