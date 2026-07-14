# ADR-0032：门派核心循环设计（拜师/练功/任务链/死亡整合）

- 状态：已通过（2026-07-13）+ 决策 1 实施期细化（attempt_apprentice 条件模型）
- 日期：2026-07-13
- 阶段：M3 Wave 2 前置（M3-1 门派完整核心循环）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（call_out 翻译 busy condition）/ dissent 6（previous_object，attempt_apprentice 钩子）/ dissent 5（themed 治理，拜师是题材内容）/ dissent 10（平台特性范围，1 门派 + 全量后置）/ dissent 1（CombatKernel 主题无关，门派武学走 SkillData 声明）

## 背景

[04 §三 M3](../xkx-arch/04-迁移路径与避坑清单.md) 要求"武侠核心循环：拜师、练功、战斗、任务、死亡轮回可玩"。[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) M3-1 选雪山派做完整核心循环。阶段 2 全子系统 + M3-2 CPK 格式已就绪，但拜师/练功/任务链是新引擎能力（阶段 2 未实现）。

**LPC 规格调研**（Explore agent，2026-07-13）确认 4 类机制的"已实现 vs 新引擎能力 vs 内容生产"边界：

| 机制 | 已实现（阶段 2） | M3-1 新引擎能力 | 内容生产（YAML/LLM） |
|---|---|---|---|
| 拜师 | `Attributes.family` 字符串（ADR-0005） | bai 命令 + family mapping + attempt_apprentice 钩子 + 叛师 | 师傅 NPC 条件 |
| 练功 | `Skills` 组件（levels/learned/skill_map，2.3）+ skill_death_penalty | learn/practice/dazuo/tuna 命令 + improve_skill + busy 循环 | 技能招式表/valid_learn |
| 任务链 | 单步 give_item + ask trigger + reward（S4 ADR-0007） | kill_npc/reach_room/fight_win + 多步 chain + time-gate | 任务对话/分档奖励 |
| 死亡惩罚 | 通用 death_penalty/killer_reward/skill_death_penalty（2.2/2.3 完整）+ 阴间还阳（2.6） | **无**（雪山用通用，LPC 确认无专属） | 无 |

**关键发现**：LPC 中雪山派无专属死亡惩罚（`damage.c:250` break_relation 是华山风清扬专属，`hua.c:56` 是血刀门专属）。雪山派玩家死亡走通用 `death_penalty`/`killer_reward`/`skill_death_penalty`，阶段 2 已完整实现。M3-1 死亡部分只需整合（复用 2.6 governance 阴间还阳闭环），无新引擎能力。

## 问题：3 类新引擎能力需要设计

### 1. 拜师机制（feature/apprentice.c + kungfu/class/xueshan/）

LPC `family` mapping 有 7 字段（`family_name`/`generation`/`master_id`/`master_name`/`title`/`privs`/`enter_time`），当前引擎 `Attributes.family: str` 只有 family_name 字符串。拜师流程：ask 剃度 -> kneel（设 class=lama）-> bai 师傅 -> attempt_apprentice 检查（属性/技能/任务门槛）-> recruit（写 family mapping）-> 逐级拜师。叛师：betrayer+1 + score=0 + 技能减半。

### 2. 练功机制（feature/skill.c + cmds/skill/）

LPC 5 命令：learn（请教 NPC，消耗 potential）/ practice（练习，消耗 jingli）/ dazuo（打坐练 neili/max_neili）/ tuna（吐纳炼 jingli/max_jingli）/ enable（map 技能）。`improve_skill(skill, amount)` 运行时函数（learned += amount; if learned > (lvl+1)²: lvl++，对照 skill.c:149）。dazuo/tuna 的 busy 期间（call_out）不能行动。

### 3. 门派任务链扩展（d/xueshan/npc/）

S4 ADR-0007 `QuestObjective.kind` 仅 give_item（kill_npc/reach_room 后置）。雪山派任务链：gelun1 单步 give_item（已有）+ fsgelun 多步（kill->give corpse->delayed reward）+ darba fight->flag->unlock 拜师 + jiamu time-gate 工资。

## 决策

### 决策 1：FamilyComp 组件 + 拜师命令组

新建 `FamilyComp` 组件（`runtime/components.py`，对照 LPC `family` mapping 7 字段）：

| 字段 | 类型 | 对照 LPC apprentice.c |
|---|---|---|
| `family_name` | `str` | `family["family_name"]`（如"雪山派"） |
| `generation` | `int` | `family["generation"]`（辈分，gen 6-13） |
| `master_id` | `str` | `family["master_id"]`（师傅 prototype_id） |
| `master_name` | `str` | `family["master_name"]` |
| `title` | `str` | `family["title"]`（门派称号，如"喇嘛"） |
| `privs` | `str` | `family["privs"]`（权限，如"-assign"可收徒） |
| `enter_time` | `int` | `family["enter_time"]`（mud_age 入门时间） |
| `betrayer` | `int` | `betrayer`（叛师计数） |

`Attributes.family: str` 保留（向后兼容 `family_eq` 谓词 ADR-0005），拜师后同步 `Attributes.family = family_name`。

**拜师命令组**（`runtime/commands.py` 新增）：

- `bai <NPC>`：玩家拜师。调 NPC `attempt_apprentice` 钩子（NpcDef 声明入门条件 + 引擎求值），通过则 recruit（写 FamilyComp + 同步 Attributes.family）。
- `kneel`：剃度动作（gongcang 师傅专属，设 `class=lama`，对照 gongcang.c:114 do_kneel）。
- `recruit <player>`：NPC 收徒（force_me/PrivilegedAction，NPC AI 或师傅 NPC 调用）。

**attempt_apprentice 钩子**（NpcDef 扩展）：声明式入门条件（技能等级/属性/任务标记/combat_exp），引擎求值。条件数据是内容生产（YAML 声明），求值引擎是新能力。

> **实施期细化**（2026-07-13 M3-1 编码落地）：原拟「复用层1 谓词 ADR-0016」，但 ADR-0016 护栏明确「不引入 attr_gt/le/ge」，gongcang 入门条件含 `combat_exp >= 10000` 无法用层1 谓词表达。改为独立结构化条件模型 `ApprenticeConditions`（min_combat_exp / reject_gender / allow_families / other_family_max_combat_exp / min_skills / require_flags，[layer0.py](../../engine/src/xkx/dsl/layer0.py)），领域语义更清晰且不违反护栏。属本 ADR 内部实施细化，不偏离 00-04 基线。

**叛师**（`betrayer` 命令，后置 M3-1 部分）：betrayer+1 + score=0 + 技能减半（对照 LPC）。M3-1 最小实现 betrayer+1 + family 清空，技能减半公式后置。

### 决策 2：练功机制（improve_skill + 5 命令 + busy condition）

**improve_skill 运行时函数**（`runtime/skill.py` 新建，对照 skill.c:149）：

```python
def improve_skill(world, eid, skill, amount, *, weak_mode=False):
    """提升技能熟练度。learned += amount; if learned > (lvl+1)²: lvl++。"""
```

复用 `Skills.learned`（2.3 已实现）+ `skill_death_penalty` 真实公式（2.3）。

**5 练功命令**（`runtime/commands.py` 新增）：

- `learn <skill> from <NPC>`：请教学习。消耗 potential，gain = random(int)（对照 learn.c:95-141）。combat_exp 门控（my_skill³/10 > combat_exp 阻止）。
- `practice <skill>`：练习。消耗 jingli，improve_skill(skill, skill_basic/5+1)（对照 practice.c:69-73）。需武器检查（skill 数据声明）。
- `dazuo`：打坐练 neili/max_neili。neili_gain = 1+force/10；neili>max_neili*2 时 max_neili++（对照 dazuo.c:74-105）。busy 期间。
- `tuna`：吐纳炼 jingli/max_jingli/eff_jingli。jingli_gain = 1+force/10（对照 tuna.c:60-93）。busy 期间。
- `enable <skill>`：map 技能（对照 enable.c，复用 Skills.skill_map 2.3）。

**busy condition**（EffectComp，ADR-0027 call_out 翻译）：dazuo/tuna 启动 busy EffectComp（duration = 消耗量/恢复速度），busy 期间行动命令 deny（命令管线 s2 权限段检查 busy condition）。复用 ADR-0017 EffectComp + ADR-0027 call_out->Effect 翻译模式。

**技能数据 YAML**（`SkillData` 载体，内容生产）：valid_learn（学习条件）/ practice_skill（练习消耗/检查）/ query_action（招式表，对照 xueshan-jian.c:148）。SkillData 由题材包 CPK 注入（M3-2 CPK 格式），LLM 生成 + 人工修订。

### 决策 3：门派任务链扩展（QuestObjective 多 kind + 多步 chain）

**QuestObjective.kind 扩充**（`dsl/layer0.py`，S4 后置项补全）：

- `give_item`（S4 已有）
- `kill_npc`：击杀指定 NPC（对照 fsgelun kill corpse）
- `reach_room`：到达指定房间
- `fight_win`：战斗并击败指定 NPC（对照 darba fight->flag->unlock，不杀死，打赢设标记）

**多步 chain**（`QuestDef.objectives: list[QuestObjective]`，S4 单 objective 扩为 list）：按顺序完成，`QuestLog.current_step` 跟踪当前步骤。全部完成才 reward。

**time-gate 奖励**（`QuestReward` 扩展）：`time_gate` 字段（mud_age 间隔，对照 jiamu lama_wage）。复用 Condition tick（ADR-0018）判定时间门控。

**任务数据 YAML**（内容生产）：任务对话/分档奖励/多步 objective 数据，LLM 生成 + 人工修订。

### 决策 4：死亡轮回整合（复用 2.2/2.6，雪山无专属）

**复用现有**（阶段 2 已完整实现）：

- `death.py`（2.2）：die/unconcious/revive/reincarnate/death_penalty/killer_reward/skill_death_penalty/make_corpse
- `governance.py`（2.6）：阴间还阳闭环（enter_underworld + death_stage 5 段 + reincarnate_at）

**雪山派无专属死亡惩罚**（LPC 调研确认）：通用 death_penalty（combat_exp 三段扣减 + potential 扣半 + skill_death_penalty）。`break_relation`（华山风清扬专属）后置 M3 stub。

M3-1 死亡部分**无新引擎能力**，只需内容整合（雪山派死亡走通用路径 + 阴间还阳衔接 2.6）。

### 决策 5：门派武学数据（SkillData/FormationData 填雪山派）

**SkillData 载体**（ADR-0027 接口就绪）：填雪山派武学（longxiang-banruo 龙象般若功 / lamaism 密宗佛法 / xueshan-jian 雪山剑法 / force 内功等）。武学数据是题材包 CPK 资产（M3-2 CPK 格式），LLM 生成 + 人工修订。

**FormationData 阵法**（ADR-0027 CombatModifier 接口）：雪山派无阵法（LPC 调研确认），后置。

**主题无关性**（ADR-0030 硬门禁）：门派武学走 SkillData/FormationData 声明，不进 combat 内核。test_theme_neutrality 持续通过。

### 决策 6：内容生产方式（独立 LLM + Langfuse，开放问题 1 裁决）

[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) 开放问题 1 裁决：Wave 2 用独立 LLM 生产雪山派完整内容 + Langfuse 追踪修订量（兼顾 M2 验证 + M3 内容生产）。

**内容生产范围**（YAML/层0/层1，LLM 可生成）：

- 师傅 NPC 条件数据（attempt_apprentice 入门条件）
- 技能招式表（SkillData valid_learn/practice_skill/query_action）
- 任务对话/多步 objective/分档奖励
- 房间/NPC/物品 YAML（层0）

**新引擎能力**（需编码，非 LLM 生成）：拜师命令组 + 练功命令组 + improve_skill + busy condition + 任务链扩展。

**Langfuse 追踪**（kill criteria 5）：measure_revision.py（ADR-0004）度量人工修订量。3 轮迭代后 >40% 触发 kill criteria 5（Agent 降级为辅助）。07-agent-schema-mapping 映射文档指导 LLM 生成。

> **实施期细化**（2026-07-13 M3-1 子任务 4 落地）：LLM 选型改火山方舟 Endpoint + deepseek-v4-flash 模型（非 Claude API），Langfuse 后置（本轮用 measure_revision 本地度量 semantic_ratio 产出首个 kill criteria 5 数据点，Langfuse 跨迭代趋势追踪后置）。详见 [ADR-0036](ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)。本轮子集先行（2 师傅 + 3 武学 + 1 任务链），完整雪山派内容下一 session。SkillData 保持决策 2 bool stub，rich LPC 条件记 GAP 后置。属本 ADR 决策 6 的实施期 LLM 选型变更，关联 03 §六 技术选型基线偏离（Claude API 主 -> 火山方舟，架构本支持「可插拔」，火山方舟契合「符合部署环境」rationale）。

### 决策 7：范围边界（1 门派完整 + 全量后置）

**M3-1 做**：

- 拜师机制（FamilyComp + bai/kneel/recruit + attempt_apprentice 钩子 + 叛师最小）
- 练功机制（improve_skill + learn/practice/dazuo/tuna/enable + busy condition）
- 任务链扩展（kill_npc/reach_room/fight_win + 多步 chain + time-gate）
- 雪山派完整内容（拜师链 gongcang->samu->ling-zhi->jinlun->jiumo + 练功 + 任务链 + 死亡轮回）
- 独立 LLM 内容生产 + Langfuse 追踪（M2 验证）
- 可玩 demo（CLI REPL 完整闭环）

**M3-1 不做**（后置）：

- 19 门派全量内容（后置 M3 后全量迁移）
- 全量门派拜师链（只雪山派 5 级拜师，其他门派后置）
- 叛师完整逻辑（技能减半公式后置）
- 阵法合击（雪山无阵法，后置）
- break_relation（华山专属，后置）
- 多门派任务链（只雪山派，后置）

## 开放问题（待用户裁决）

1. **FamilyComp vs 扩展 Attributes.family**：新建 FamilyComp 组件（7 字段 mapping）vs 扩展 Attributes.family 为 mapping？**倾向**：FamilyComp 新组件（Attributes.family 保留 str 兼容 family_eq 谓词，拜师后同步）。

2. **busy condition 实现**：EffectComp（ADR-0027 call_out 翻译）vs 独立 BusyComp？**倾向**：EffectComp 复用（duration + busy flag，命令管线 s2 检查）。

3. **多步任务链状态机**：QuestLog 扩展 current_step vs 独立 QuestChainComp？**倾向**：QuestLog 扩展 current_step（S4 QuestLog 已有，最小扩展）。

4. **独立 LLM 选型**：Claude API + Langfuse（开放问题 1 已裁决）vs 其他？**倾向**：Claude API（03 §六技术选型）+ Langfuse 追踪。**实施期裁决**（2026-07-13）：改火山方舟 Endpoint + deepseek-v4-flash + Langfuse 后置，见 [ADR-0036](ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)。

5. **fight_win objective 实现**：战斗并击败（不杀死）vs kill_npc（杀死）？**倾向**：fight_win 独立 kind（darba 打赢设标记解锁拜师，不杀死 NPC，对照 darba.c:118 chat 设 jlfw）。

## 不做（范围边界）

见决策 7。

## kill criteria

- **kill criteria 5**（Agent 创作）：M3-1 独立 LLM 单 CPK 经 3 轮生成-修订迭代后人工修订量 >40% -> 先扩 DSL 层1-2 表达力；扩后仍 >30% -> Agent 降级为辅助；LLM token 预算耗尽 -> 回退人工创作 DSL。
- **kill criteria 7**（项目级）：18 个月未达 M3（单题材可玩 demo）-> 冻结迁移。M3-1 可玩 demo 是此 kill criteria 的判定物。
- **M3-1 内部**：拜师/练功/任务链机制行为等价验证失败（与 LPC 规格偏差 >阈值）-> 暂停，先修行为等价；可玩 demo 不可玩（完整循环跑不通）-> 暂停调整。
- **主题无关性回归**（test_theme_neutrality 不通过）-> 暂停，门派武学走 SkillData 声明不进内核（ADR-0030 硬门禁）。

## 验收标准（对应 04 §三 M3 武侠核心循环 + 16-M3 M3-1）

- [ ] FamilyComp 组件 + bai/kneel/recruit 命令 + attempt_apprentice 钩子（拜师闭环）
- [ ] improve_skill 运行时 + learn/practice/dazuo/tuna/enable 命令 + busy condition（练功闭环）
- [ ] QuestObjective kill_npc/reach_room/fight_win + 多步 chain + time-gate（任务链闭环）
- [ ] 雪山派完整内容（5 级拜师链 + 练功 + 任务链 + 死亡轮回）以 CPK 形式入库
- [ ] 独立 LLM 内容生产 + Langfuse 追踪（M2 验证，修订量 <40%）
- [ ] 可玩 demo（CLI REPL 完整循环：拜师 -> 练功 -> 战斗 -> 任务 -> 死亡轮回 -> 还阳）
- [ ] 行为等价验证（关键 NPC/任务与 LPC 规格对照）
- [ ] test_theme_neutrality 硬门禁持续通过（门派武学走 SkillData 声明）
- [ ] test_load_test CI 门禁不退化（tick p99 < 100ms）
- [ ] 全量 tests 绿 + ruff 全过

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（call_out 翻译 busy condition，EffectComp）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（previous_object，attempt_apprentice 钩子 + recruit PrivilegedAction）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 5（themed 治理，拜师/练功是题材内容，走 CPK 资产）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 10（平台特性范围过载，1 门派 + 全量后置）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 主题无关，门派武学走 SkillData/FormationData 声明）
- [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) M3-1（门派核心循环主线）/ 开放问题 1（独立 LLM + Langfuse）
- [03](../xkx-arch/03-DSL-UGC与Agent协作.md) §六（Agent 协作创作 + Langfuse 追踪 + kill criteria 5）/ [07](../xkx-arch/07-agent-schema-mapping.md)（LPC -> schema 映射）
- [ADR-0031](ADR-0031-cpk-format-and-themeregistry-static-loading.md)（CPK 格式，门派内容以 CPK 入库）
- [ADR-0030](ADR-0030-family-content-pack-boundary-race-extraction.md)（FamilyBonus 载体，拜师加成）
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md)（call_out->EffectComp 翻译 + CombatModifier/SkillData 接口）
- [ADR-0007](ADR-0007-minimal-quest-system.md)（S4 最小任务系统，M3-1 扩展 kill_npc/reach_room/多步 chain）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（EffectComp，busy condition 载体）
- [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)（Condition tick，time-gate 奖励）
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（FamilyComp 可序列化）

> **ADR 编号说明**：本 ADR-0032 是 M3-1 前置（Wave 2），原 [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) ADR 映射（ADR-0032 审核/ADR-0033 版权/ADR-0034 确定性）顺延为 ADR-0033/0034/0035（按 Wave 顺序编号）。16-M3 ADR 映射表同步更新。
