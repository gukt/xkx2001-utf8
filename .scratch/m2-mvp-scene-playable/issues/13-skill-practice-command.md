# 13 — 技能练习命令：practice（经验/升级判定）

**What to build:** 落地 spec Implementation Decisions「B2」末段的成长闭环：`practice <技能>` 命令消耗内力/精力（数值来自 03 号票 `SkillData` 声明的纯数据参数，不是硬编码常量）练习玩家已学会（`SkillLevels.levels` 里已有条目）的技能以换取经验，达到经验门槏（同样是 `SkillData` 声明的字段，如分级门槏表或公式参数）后自动升级并给出提示。练习消耗不足（内力/精力不够）时给明确提示，不扣资源不加经验。本票**不**处理"如何学会一门新技能"（`learn` 命令，14 号票，依赖门派框架），只处理"已学会的技能怎么练"——用测试预置的 `SkillLevels` 条目即可独立验证本票，不必等 14 号票的 `learn` 真的能跑通。

**Blocked by:** 03（`SkillData` 提供消耗/经验门槏参数），05（`Vitals`/`SkillLevels` 真实组件）。

**Status:** ready-for-agent

- [ ] `practice <技能>`：技能不在玩家 `SkillLevels.levels` 里（未学会）给出"你还没学会这个技能"一类提示；已学会但内力/精力不足给出"你现在练不动"一类提示，且不产生任何状态变更。
- [ ] 成功练习：扣减对应资源（`Vitals.neili_current`/`jingli_current`，具体扣哪个或两个都扣由 `SkillData` 该技能的声明字段决定），增加 `SkillProgress.exp`。
- [ ] 升级判定：`exp` 达到 `SkillData` 声明的门槏（等级 -> 门槏值的映射或公式，字段形状由实现阶段定，需在 03 号票的 `SkillData` 形状基础上扩展，若 03 号票尚未包含该字段则本票在 03 号票基础上补充）时，`SkillProgress.level` 自动 +1，`exp` 处理方式（清零/结转）需明确并测试锁定，给玩家清晰的升级提示。
- [ ] 命令层测试覆盖：未学会技能、资源不足、正常练习获得经验（未到门槏）、练习触发升级（到达门槏）四种路径。
- [ ] 存档往返：`SkillProgress.level`/`exp` 变化后 save→restore 一致。
- [ ] 现有测试全绿不回归。
