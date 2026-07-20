# 30 - 物品查找函数去重（#6 Duplicated Code）

**Smell:** `commands._find_reachable_container`（commands.py:810）与 `parsing.DeterministicParser._find_reachable_container_id`（parsing.py:361）同构遍历 room/player 找 Container 物品；`commands._find_lookable_item`（commands.py:767）与 `parsing._look_item_candidates`（parsing.py:377）同形遍历 room/player + 一层嵌套。两处逻辑重复。

**Fix:** 抽公共查找函数到共享位置（`matching.py` 已有 `match_target`，可加 lookup；或新建 lookup 模块）。注意 commands↔parsing import 方向：parsing 已 `from mud_engine.commands import execute, resolve_verb`，commands 不 import parsing，抽第三处避免循环。

**From:** BCD re-pass code-review 物品批 Standards #6（commit 79b831ef）。

**Status:** resolved

- [x] 两处查找逻辑收敛到单一实现，无行为回归
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `d739c48a`。
新建 `engine/src/mud_engine/lookup.py`，收敛 `find_reachable_container`（commands/parsing 同构可达容器查找）与 `iter_lookable_containers`（look 遍历结构）。commands 与 parsing 改调共享实现，402 绿。
