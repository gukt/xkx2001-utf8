# 05 — 角色成长组件：Vitals / BaseAttributes / SkillLevels + status/skills 命令

**What to build:** 落地 spec Implementation Decisions「B2」的三个组件：`Vitals(qi_current, qi_max, neili_current, neili_max, jingli_current, jingli_max)`（气血/内力/精力，两层 当前/上限）、`BaseAttributes(str_, con, dex, int_)`（力量/根骨/敏捷/智力，字段名避开 Python 关键字加下划线，展示文案用中文）、`SkillLevels(levels: dict[str, SkillProgress])`（`SkillProgress(level, exp)`，只存"学会了哪些技能+等级/经验"，招式内容查 03 号票的 `SKILLS` 全局注册表，不复制）。三者按 spec「对象模型」标准拆成独立组件（不是一个跨领域大杂烩），走 01 号票落地的 NPC 级能力注册表模式挂载（YAML `vitals:`/`attributes:`/`skills:` 字段，玩家与 NPC 都可能挂——教学木桩/野外怪物/门派 NPC 都需要 `Vitals` 才能被攻击）。新增 `status` 命令（展示当前玩家气血/内力/精力 当前/上限 + 四项基础属性）与 `skills` 命令（展示已学技能及等级/经验进度）。

**Blocked by:** 01（`Vitals`/`BaseAttributes`/`SkillLevels` 是 NPC 级能力，需要走注册表模式挂载，避免手工改 `_NPC_KNOWN_FIELDS`）。

**Status:** resolved

- [x] `Vitals`/`BaseAttributes`/`SkillLevels`/`SkillProgress` 组件形状落地，作为三个独立 dataclass（不合并）。
- [x] 三者的存档序列化/反序列化走 01 号票的注册表 codec（`to_dict`/`from_dict`），运行时可变（气血会变化）进存档。
- [x] YAML 加载：NPC/玩家段可声明 `vitals:`（气血/内力/精力起始值+上限）、`attributes:`（四维属性）、`skills:`（初始已学技能+等级/经验，供门派 NPC/野外怪物预置战斗力）；缺省时给出合理默认值（不强制每个实体都声明）。
- [x] `status` 命令：展示玩家当前 `Vitals`（三种资源 当前值/上限）+ `BaseAttributes`（四维，中文展示）；玩家实体若缺这些组件给出明确提示而非崩溃（防御性——理论上玩家实体在 M2 场景加载时应始终带这些组件，但测试要覆盖缺失路径）。
- [x] `skills` 命令：展示 `SkillLevels.levels` 里每项技能的等级/经验；未学会任何技能时给出"你还没有学会任何技能"一类提示。
- [x] 命令层测试（`execute_line`/`commands.execute` seam）：给定预置 `Vitals`/`BaseAttributes`/`SkillLevels` 的测试玩家，断言 `status`/`skills` 输出内容与状态查询一致。
- [x] 存档往返测试：`Vitals`（气血变化后）/`SkillLevels`（学会技能后）save→restore 后数值一致。
- [x] 现有测试全绿不回归。
