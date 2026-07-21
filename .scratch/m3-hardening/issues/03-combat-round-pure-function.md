# 03 — 消灭 `combat.py` 战斗回合全局态

**What to build:** `resolve_attack` 真正做到"给定同一份输入两次求值结果一致、不依赖任何进程级可变态"。当前 `_ROUND_EXTRA_FRAGMENTS` 模块级全局列表意味着两次并发或嵌套调用会互相污染文案片段，这与既有的"纯函数结算"叙事矛盾。`SkillBehavior.hit_by`/`post_action` 改为通过**返回值**（而不是调用一个全局 `append_round_fragment` 副作用函数）向 `resolve_attack` 传回本回合追加文案，让"招式钩子只读快照、把结果显式返回给调用方"这条约束覆盖到播报文案，不留副作用后门。`hit_ob` 已有的"返回值可修改伤害数值"约定不受影响（签名不变），改动范围收敛到确实有问题的 `hit_by`/`post_action` 两个钩子。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-4。这张票是 07、10 号票的前置依赖，因为都会 touch `resolve_attack`/`SkillBehavior` 调用路径。

**Blocked by:** None — 可立即开始。

**Status:** resolved

- [x] `skills.py` 的 `SkillBehavior` Protocol：`hit_by(self, ctx: CombatContext) -> None` 改为 `hit_by(self, ctx: CombatContext) -> str | None`；`post_action(self, ctx: CombatContext) -> None` 改为 `post_action(self, ctx: CombatContext) -> str | None`；返回字符串即为本次调用要追加的播报片段，`None` 表示无追加。
- [x] `combat.py`：删除 `_ROUND_EXTRA_FRAGMENTS` 模块级列表与 `append_round_fragment` 函数（含 `__all__` 里的导出）；`resolve_attack` 改为在本次调用作用域内用局部变量收集 `hit_by`/`post_action` 的返回值，拼进 `fragments` 元组，不再 `.clear()` 一个全局态。
- [x] `hit_ob` 签名不变（已经能返回 `int | str | None`）。
- [x] `skills.py` 里现有的示范钩子 `DemoPoisonStrikeBehavior.hit_by`（当前调用 `append_round_fragment("毒素渗入伤口！")`）改为 `return "毒素渗入伤口！"`。
- [x] `test_skill_behavior_hooks.py` 里对 `hit_by`/`post_action` 断言方式同步更新——从"检查全局列表内容"改为"检查 `resolve_attack` 返回的 `CombatRoundResult.fragments` 是否包含预期片段"。
- [x] 新增一条纯函数直测：连续两次独立调用 `resolve_attack`（给定同一份输入）互不污染，结果一致——专门断言这个改动恢复的纯函数属性。
- [x] `just test` 全绿，尤其 `test_combat.py`、`test_skill_behavior_hooks.py`、`test_combat_engagement.py`。

## Comments
