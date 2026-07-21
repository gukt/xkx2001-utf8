# 02 — 持刃门禁与装备语义对齐

**What to build:** 少林山门的进入条件不再暗中要求"背包里没有 `edged` 标签物品"——角色目前没有任何命令能把武器收起来，这条条件在体验上等价于玩家永远猜不出规则的隐藏门槏。山门只保留性别 + 门派归属两项确实可操作的门槏，并更新拒绝文案。`EntityGateContext.is_wielding_edged_weapon` 这条求值能力本身**保留在引擎层**（不删代码、不改条件求值器语法），只是本次停机不再有任何官方场景内容消费它，供未来真的落地 wield/unwield 命令时直接复用。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-3。

**Blocked by:** None — 可立即开始。

**Status:** ready-for-agent

- [ ] `engine/data/m2_mvp_scene.yaml` 少林山门房间的 `entry_guard.condition`：删除 `not: {predicate: is_wielding_edged_weapon}` 这一支，只保留性别 + 门派归属两支；同步改写 `deny_message`（去掉"且不得持刃器入内"一类表述）。
- [ ] `entity_gate.py` 的 `EntityGateContext.is_wielding_edged_weapon` 求值能力**不删除**，保留供未来 wield 系统复用。
- [ ] `test_entry_guard.py`、`test_scene_shaolin.py` 里断言"持刃/edged 物品被拒"的用例改为断言新的两条件门槏（性别 + 门派），不再构造/携带 edged 物品作为拒绝案例。
- [ ] 不新增 `wield`/`unwield`/`stash` 命令。
- [ ] `just test` 全绿，尤其 `test_entry_guard.py`、`test_scene_shaolin.py`。

## Comments
