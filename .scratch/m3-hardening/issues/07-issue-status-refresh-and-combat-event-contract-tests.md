# 07 — 票 Status 刷新 + 战斗事件点最小契约测

**What to build:** M2 的 16～20 号票（`SkillBehavior` 钩子接线、死亡流程接线、NPC 死亡重生、aggro 行为、同名序号消歧）状态从 `ready-for-agent` 刷新为 `resolved`，因为它们对应的实现与测试早已存在，票面状态与工程事实不符本身就是一种"文档谎言"。已经存在的 `on_before_combat_round`/`on_combat_round`/`on_combat_end` 三个战斗事件点补上最小契约测试（否决 `on_before_combat_round` 能中止本回合结算、`on_combat_round`/`on_combat_end` 在预期时机被分发且携带正确的上下文字段），让这批事件点不再是"挂了但没人验证过真的会触发"的隐性契约。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-8。

**Blocked by:** 03（`combat.py` 消灭全局态 + `SkillBehavior` 签名重构需要先落地，事件契约测试要建在重构后的调用路径上，避免同一批代码被两张票各改一次）。

**Status:** resolved

- [x] 刷新 `.scratch/m2-mvp-scene-playable/issues/16-skill-behavior-hook-wiring.md`、`17-death-flow-wiring.md`、`18-npc-death-and-respawn-flow.md`、`19-aggro-behavior.md`、`20-same-name-target-disambiguation.md` 五个文件的 `**Status:**` 行，从 `ready-for-agent` 改为 `resolved`（对照现有实现：`death_flow.py`、`test_skill_behavior_hooks.py`、`test_death_flow.py`、`test_aggro.py`、`test_disambiguation.py` 均已存在且通过）。
- [x] 新增战斗事件点契约测试（放在 `test_combat_engagement.py` 或新建 `test_combat_events_contract.py`）：
  - [x] `on_before_combat_round`：注册一个否决 handler，断言本回合被跳过（不扣血/不产生结算），且能正常在下一 tick 恢复非否决状态。
  - [x] `on_combat_round`：断言每次自动交战回合结算后确实分发一次，携带的上下文字段（交战双方、本回合结果）与实际结算一致。
  - [x] `on_combat_end`：断言交战关系解除（死亡/脱离）时分发一次，不多分发也不漏分发。
- [x] 测试模式参照现有 `test_domain_events.py`/`test_command_hooks.py`（否决/分发/上下文字段断言）。
- [x] `just test` 全绿。

## Comments
