# 14 — 门派技能学习：learn 命令（map_skill 解析 + skill_pool + 门槏校验）

**What to build:** 落地 spec Implementation Decisions「E1」末段定义的 `learn` 命令完整解析流程：先查玩家 `Faction.faction_id` 对应的 `FactionDefinition.map_skill`，把玩家输入的技能类型（如"内功"）映射为具体技能 id（如"混元一气功"，映射不到给出"你的门派不会这个"一类提示）；再查该技能 id 是否在该门派 `skill_pool` 内、`SkillData` 声明的等级/属性门槏是否满足（复用 08 号票地基的条件求值器表达学习限制，不写散落的 if 比较）；全部通过才学会并写入玩家 `SkillLevels`。玩家无门派归属（`Faction.faction_id is None`）时给出"你还没有门派"提示。本票是 08 号票（门派框架）与 03 号票（技能数据）+ 05 号票（`SkillLevels`）三者的汇合点，命令语义对应 spec 用户故事 16、40、46。

**Blocked by:** 03（`SkillData` 门槏字段），05（`SkillLevels` 组件），08（`Faction`/`FactionDefinition`/`map_skill`）。

**Status:** ready-for-agent

- [ ] `learn <技能类型>`：无门派归属 -> 明确提示；门派 `map_skill` 无对应映射 -> "你的门派不会这个"；映射到的技能不在该门派 `skill_pool` -> 明确拒绝原因；等级/属性门槏不满足 -> 给出具体缺什么（如"你的根骨不够"），不是笼统"不满足条件"。
- [ ] 学习条件求值复用 `conditions.evaluate`（08 号票已定的条件子语言），不新写散落 if 比较——`SkillData` 声明的门槏字段需要能表达成 `Condition` 节点（如等级门槏、属性门槏），若 03 号票的 `SkillData` 形状尚不支持，本票在其基础上补充该字段的条件化表达。
- [ ] 全部通过后：技能 id 写入玩家 `SkillLevels.levels`（初始等级/经验的默认值需明确，如 level=1, exp=0），给出成功提示。
- [ ] 重复 `learn` 已学会的技能给出提示（不重复添加/不重置进度）。
- [ ] 命令层测试覆盖：无门派、映射不到、不在技能池、门槏不满足、成功学会、重复学习六种路径。
- [ ] 存档往返：新学会的技能 save→restore 后仍在 `SkillLevels` 里。
- [ ] 现有测试全绿不回归。
