# 34 - NPC entities_in_room 查找去重（NPC #7 Duplicated Code）

**Smell:** 4 处重复"遍历 `entities_with(Position)` + 按 room 过滤 + 排除某实体"：`commands._sorted_npc_names_in_room`（348）、`commands.room_say`（712）、`commands._find_npc_in_room`（732）、`parsing._npc_candidates`（414）。

**Fix:** 抽 `world.entities_in_room(room, *, exclude=None)` 方法，4 处改调。

**注意 import 循环：** `components.py:40` 运行时 `from mud_engine.world import EntityId`，world.py 若运行时 import components（`Position`）会循环。需先把 components 的 `EntityId` 改 TYPE_CHECKING + `from __future__ import annotations`，或 `entities_in_room` 不硬编码 Position（接受 `component_type` 参数）。

**From:** BCD re-pass code-review NPC 批 Standards #7（commit bab2f44f）。

**Status:** resolved

- [x] 4 处查找收敛到 `world.entities_in_room`
- [x] import 无循环
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `2461fde0`。
commands（_sorted_npc_names_in_room / room_say / _find_npc_in_room）与 parsing（_npc_candidates）改调 `world.entities_in_room(room, exclude=...)`。components.py 将 `EntityId` 改为 TYPE_CHECKING 导入（所有使用处均为注解，配合 `from __future__ import annotations`），world.py 可运行时 import Position 而无循环依赖。新增 test_world.TestEntitiesInRoom 直接覆盖。402 绿。
