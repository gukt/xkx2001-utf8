# 24 — 场景内容：少林寺（门派身份门槏 + 拜师 + 学技能）

**What to build:** 落地 [10 号票](../../mvp-scope/issues/10-mvp-scenes-selection.md) 定稿的少林寺场景内容（spec 用户故事 38–41、65、块 H）：山门（挂 `EntryGuard`，严格身份/性别/武器权限校验，示范条件求值器在门槏场景的真实用法）+ 广场 + 达摩院/藏经阁（剧情向房间，有描述、有展示型 NPC，无特殊交互机制）+ 武场（技能学习教学位）+ 武僧/知客僧 NPC。知客僧支持 `join 少林`（08 号票机制真实验收场），武僧支持 `learn <少林专属技能，如罗汉拳>`（14 号票机制真实验收场，需要在 03 号票的 `SKILLS` 全局注册表与本票的 `factions:` 段之间正确连线 `map_skill`）。房间键使用 `shaolin_*` 前缀。

**Blocked by:** 08（`join` 命令 + `FactionDefinition`），11（`EntryGuard` + `EntityGateContext`），14（`learn` 命令完整实现）。

**Status:** resolved

- [x] 山门房间挂 `EntryGuard`：条件覆盖性别/是否已属其他门派/所持武器类型（对照 spec 用户故事 38"性别/是否已属其他门派/所持武器类型等场景声明的具体条件"），不满足时给出明确原因文案。
- [x] 广场 + 达摩院 + 藏经阁：剧情向房间，各有独立描述与至少一个展示型 NPC（无 `Inquiry`/`Behaviors` 亦可，纯粹"有名字有描述"）。
- [x] 武场房间 + 武僧 NPC：`learn <少林技能>`（如"罗汉拳"或对应内力技能类型如"内功"）成功后玩家 `SkillLevels` 出现该技能。
- [x] 知客僧 NPC：`join 少林`（或场景声明的具体命令措辞）满足条件后玩家 `Faction.faction_id` 变为少林。
- [x] `factions:` 段声明的少林 `FactionDefinition`：`skill_pool`/`map_skill` 正确关联 03 号票 `skills:` 段声明的少林专属技能（如"混元一气功"映射自"内功"技能类型）。
- [x] 房间键统一 `shaolin_*` 前缀；出口预留一个方向连接官道/野外（为 25 号票协调）。
- [x] 端到端剧本片段测试：不满足门槏时山门拒绝进入 -> 满足条件后进入 -> `join 少林` 成功 -> `learn` 少林专属技能成功。
- [x] 现有测试全绿不回归；`just verify-*` 一键矩阵全绿。
