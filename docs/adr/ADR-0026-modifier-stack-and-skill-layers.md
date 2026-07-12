# ADR-0026：ModifierStack 三类语义 + 技能三层划分

- 状态：草案（阶段 2 Wave 2 前置）
- 日期：2026-07-12
- 阶段：阶段 2 Wave 2（2.3 Attribute/Skill/Equipment）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2（M2-3）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（规则冲突语义漂移，ModifierStack 三类叠加语义模糊）+ dissent 3（层1 原语蠕变，apply_* 不落入层1 DSL）+ 专家 3 承重论断（技能三层）/ [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.3 + §五 ADR 表 + §七 dissent 映射 / [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（Skills/Attributes 组件 + EffectComp）/ [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（skill_power 简化台账第 4 项已定稿）/ [ADR-0025](ADR-0025-query-index-layer.md)（query/set 运行时接口 + 后置 key 激活）/ [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（主题无关性）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（新组件可序列化）/ [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py)（skill_power 公式 + query_skill 规格）/ [feature/equip.c](../../feature/equip.c)（wield/wear/unequip）/ [feature/skill.c](../../feature/skill.c)（query_skill/set_skill/map_skill）/ [include/weapon.h](../../include/weapon.h) + [include/armor.h](../../include/armor.h)（装备槽位）

## 背景

[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.3 任务卡：实现 ModifierStack 三类语义 + 技能三层划分 + 装备槽，对照 [层 E](../../engine/src/xkx/spec/layer_e_combat.py) skill_power 公式 + LPC equip/unequip。验收：ModifierStack 三类叠加与 LPC `query_temp("apply/attack")` + 装备加成等价；技能三层划分清晰。

**现有资产（阶段 1 已产出，2.3 在此基础上补 ModifierStack 语义 + Equipment 组件）**：

- [components.py](../../engine/src/xkx/runtime/components.py) 13 组件，其中与本 ADR 直接相关：
  - `Skills`：`levels: dict[str, int]`（技能等级）+ `apply_attack/apply_dodge/apply_parry/apply_damage/apply_armor: int`（5 个 apply_* 标量，对应 LPC `query_temp("apply/attack")` 等）+ `weapon: str | None`（当前武器）。**apply_* 是扁平标量字段，非 query 链求值**。
  - `Attributes`：`str_/dex_/int_/con_/age/gender/family`（四维属性 + 种族/门派）。
  - `Vitals`：`qi/max_qi/eff_qi/jing/max_jing/jingli/max_jingli/neili/max_neili`（三层资源）。
  - `Inventory`：`items: set[str]`（物品 id 集合，无装备槽/无堆叠/无容器）。
- [combat/resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) `skill_power()` 已实现完整公式（ADR-0023 简化台账第 4 项已定稿）：`level = skills.get(skill_id, 0) + apply_mod` -> `power = level³/3` -> `jingli_bonus = 50 + jingli/(max_jingli+1)*50`（上限 150）-> ATTACK 用 `str_*2` 加成，DEFENSE 用 `dex_*2` 加成 -> `is_fighting()` 时 DEFENSE 乘 `(100 + fight_dodge/10)/100` -> `level<1` 时用 `combat_exp/20 * (jingli_bonus/10)` 补偿。**直接读 CombatantSnapshot 标量字段，无 ModifierStack 求值**。
- [combat/context.py](../../engine/src/xkx/combat/context.py) `CombatantSnapshot` 快照含 `skills: dict[str, int]` + `apply_attack/apply_dodge/apply_parry/apply_damage/apply_armor: int` + `weapon: str | None` + `attack_skill: str` + `weapon_label: str`。快照构建时从 ECS 组件拷贝。
- [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) DBASE_KEY_MAP 已映射 `apply_attack/apply_dodge/apply_parry/apply_damage/apply_armor/weapon` -> Skills 组件字段；`POSTPONED_KEYS` 含 `equipped`/`apply`（路径）/`weight`（隐含，F_MOVE 负重）。
- [ADR-0025](ADR-0025-query-index-layer.md) query/set 运行时接口（8 个 F_DBASE 函数）+ 后置 key 激活策略（2.3 激活 `equipped`/`weight`/`encumbrance`）。

**dissent 3 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 3 条 + 第 4 条）：

> 规则冲突语义漂移（第 4 条）：LPC 靠注册顺序隐式覆盖触发器命中，层1 若优先级/deny-wins 语义未严格对齐，迁移后 533 valid_leave 命中行为会漂移。靠基线测试断言原 LPC 命中行为。

> 层1 原语蠕变（第 3 条）：反复扩充层1 条件/动作原语可能让层1 逐步长成事实上的规则引擎。靠 KPI<15% + 判定标准（可声明式描述且跨规则复用则扩层1，需图灵完备则层3）护栏。

本 ADR 落地裁决：**ModifierStack 三类语义明确**（永久基础值 / 临时修正 apply_* / 装备加成），三类叠加顺序对照 LPC query 链（基础 + apply + 装备），用 hypothesis 属性测试断言叠加等价。**apply_* 是 ModifierStack 内部层**，不落入层1 DSL（层1 是 condition->action 触发器，apply_* 是数值修正层，两者正交，dissent 3 原语蠕变护栏）。

**专家 3 承重论断**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 3 承重论断 + Q2 收敛"留"项）：

> 技能三层（04 §四留项）：基础技能（unarmed/dodge/parry 等通用）/ 武学技能（kungfu/*/ 门派武学，module pack 资产）/ 特殊技能（特殊 action，CPK 资产）。

本 ADR 落地该裁决：技能三层在 Skills 组件的 `levels` dict 统一存储（skill_id -> level），**层级标记区分**而非物理分表。武学技能是 module pack 资产（非引擎层），特殊技能是 CPK 资产，基础技能是引擎内置默认集。

**CLAUDE.md 不变量**：

- tick=1s + compute<100ms（ModifierStack 求值是纯计算，每 tick skill_power 调用次数有限--CombatSystem 遍历有 CombatState 且 enemies 非空的实体；1000 实体中战斗实体通常 <100，每次 resolve_attack 调 skill_power 2-3 次，总开销在 μs 级。缓存策略后置性能优化备选 1，[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七）。
- CombatKernel 从武侠提取、用非武侠验证（ModifierStack 无武侠语义，武学技能是 module pack 资产非引擎层，test_theme_neutrality 硬门禁）。
- 三层粒度 Theme > Module Pack > UGC CPK（门派武学是 module pack 不是独立题材）。
- 新组件可序列化（ADR-0022 存档崩溃安全，Equipment 组件须可序列化）。
- Command 仅覆盖外部意图（equip/unequip 命令走 8 段管线，ModifierStack 求值是 System/工具层非 Command）。

## 决策

### 1. ModifierStack 三类语义（对照 LPC query 链）

**LPC 的 query 链**（从 [feature/skill.c](../../feature/skill.c) `query_skill` + [adm/daemons/combatd.c](../../adm/daemons/combatd.c) `skill_power` 提取）：

```text
LPC query_skill(skill) 非 raw 模式:
  s = query_temp("apply/" + skill)       # apply 临时修正层
  s += skills[skill] / 2                  # 永久基础值（半值计入有效等级）
  s += skills[skill_map[skill]]           # 映射技能全值（skill_map: unarmed -> daxe）
  return s

LPC skill_power(ob, skill, usage):
  level = query_skill(skill)              # 含 apply/{skill} + 基础/2 + 映射
  level += query_temp("apply/attack")     # ATTACK 额外加 apply/attack
  # 或 DEFENSE: level += query_temp("apply/defense")
  power = level³ / 3
  ...jingli_bonus / str/dex 加成...
```

**LPC equip 如何注入 apply 层**（[feature/equip.c](../../feature/equip.c)）：

- `wield()`：`owner->add_temp("apply/" + key, weapon_prop[key])`（把 weapon_prop 的每个键累加到 apply temp mapping）。
- `wear()`：`applied_prop[key] += armor_prop[key]`（把 armor_prop 累加到 apply temp mapping）。
- `unequip()`：`applied_prop[key] -= prop[key]`（反向扣减）。

> LPC 中装备加成与 condition/buff 引起的 apply 变化**混在同一个 apply temp mapping**（`query_temp("apply")` 返回单个 dict）。unequip 反向扣减依赖累加值正确，若中途有 condition 也改了同一 key，扣减可能出错（LPC 隐性 bug 风险）。

**greenfield 三类语义明确**（dissent 3 应对：三类叠加语义不模糊）：

| 类别 | greenfield 表达 | LPC 对照 | 生命周期 | 求值参与 |
|---|---|---|---|---|
| **永久基础值** | `Skills.levels[skill_id]`（dict）+ `Attributes.str_/dex_/...`（标量） | LPC `skills[skill]` + `query("str")` | 永久（存档持久化） | query_skill 的 `skills[skill]/2` + skill_power 的 str/dex 加成 |
| **临时修正 apply_*** | `Skills.apply_attack/apply_dodge/apply_parry/apply_damage/apply_armor`（5 标量）+ Marks.flags（状态标记） | LPC `query_temp("apply/attack")` 等 apply_* 系列 + `query_temp("marks/X")` | 临时（condition/buff 引起，EffectComp 驱动，存档含剩余 duration） | skill_power 的 `level += apply_mod` + do_attack 步骤 5 的 `apply/damage` |
| **装备加成** | `Equipment` 组件（新，装备槽 + prop 累加值） | LPC `weapon_prop`/`armor_prop` 累加到 apply temp | 装备期（equip 后 unequip 前，存档持久化） | equip 时把 prop 累加到 apply_* 标量，unequip 时反向扣减 |

**三类叠加顺序**（对照 LPC query 链，dissent 3 基线测试断言）：

```text
effective_skill_level(skill_id) =
    Skills.levels[skill_id] / 2                  # 永久基础值（半值）
  + Skills.levels[skill_map[skill_id]]           # 映射技能全值（skill_map）
  + ModifierStack.apply_for(skill_id)            # 临时修正 apply_{skill}
  # 装备加成在 equip 时已注入 apply_* 标量（对照 LPC wield/wear 注入 apply temp）
```

**装备加成的注入式设计**（对照 LPC wield/wear，关键决策）：

greenfield 的 Equipment 组件**存储装备 prop 的原始值**（weapon_prop/armor_prop 的副本），equip 时把 prop 累加到 Skills.apply_* 标量（对照 LPC `add_temp("apply/" + key, prop[key])`），unequip 时反向扣减。这样：

- skill_power 直接读 `Skills.apply_attack` 等标量（无需遍历装备槽），与现有 resolve_attack.py 实现兼容（ADR-0023 第 4 项已定稿，不重新设计公式）。
- Equipment 组件持有 prop 副本，unequip 时按副本扣减（不依赖 apply_* 当前值，避免 LPC "中途 condition 改了同 key 导致扣减出错"的隐性 bug）。
- 临时修正（condition/buff）与装备加成在 apply_* 标量上叠加，但来源可追溯（EffectComp 记录 condition 的 apply 修正，Equipment 记录装备的 prop 累加）。

> 三类语义明确是本 ADR 核心价值：LPC 混在 apply temp mapping 的修正来源不可追溯，greenfield 通过"Equipment 持有 prop 副本 + apply_* 标量叠加 + EffectComp 记录 condition 修正"让来源可追溯，dissent 3 的"语义模糊"风险消除。hypothesis 属性测试断言：equip + condition 同 key 修正后 unequip，apply_* 值正确回到 condition-only 状态。

**apply_* 路径的完整集**（对照 LPC `query_temp("apply/...")` 调用点，[combatd.c](../../adm/daemons/combatd.c)）：

| apply_* key | Skills 字段 | LPC 用途 | skill_power 接入 |
|---|---|---|---|
| `apply/attack` | `apply_attack` | skill_power ATTACK 路径 level 加成 + do_attack 步骤 5 NPC 伤害加成 | `level += apply_attack` |
| `apply/defense` | `apply_dodge`（DEFENSE dodge 路径）+ `apply_parry`（DEFENSE parry 路径） | skill_power DEFENSE 路径 level 加成 | `level += apply_dodge` 或 `apply_parry`（按路径区分） |
| `apply/damage` | `apply_damage` | do_attack 步骤 5 基础伤害 | `damage = apply_damage + random(damage)` |
| `apply/armor` | `apply_armor` | do_attack 步骤 6 wound 判定 | `random(damage) > apply_armor` |
| `apply/speed` | **后置 2.3 扩展**（Skills 加 `apply_speed` 字段） | fight() 主动性判定 + riposte 触发判定 | fight: `random(dex*3) < str*2 + apply_speed`；riposte: `random(1-apply_speed)` |
| `apply/{skill}` | **路径前缀**（query_skill 内含，非 Skills 标量） | query_skill 非 raw 模式 `s += apply/{skill}` | 通过 `query(world, eid, "apply/"+skill)` 路径访问 |

> LPC `apply/defense` 是单个值，greenfield 按路径拆为 `apply_dodge`（dodge 路径）+ `apply_parry`（parry 路径）。现有 resolve_attack.py `skill_power()` 已按 `apply_parry_path` 参数区分（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 第 80-86 行），本 ADR 沿用此区分。`apply/speed` 当前无 Skills 字段，2.3 扩展（后置 key 激活）。

### 2. 技能三层划分（专家 3 承重论断落地）

**LPC 的技能三层**（从 [feature/skill.c](../../feature/skill.c) + [kungfu/](../../kungfu/) + [include/skill.h](../../include/skill.h) 提取）：

| 层级 | LPC 来源 | 示例 | greenfield 资产层级 |
|---|---|---|---|
| **基础技能** | `std/skill.c` / 通用 `SKILL_D(skill)` | unarmed/dodge/parry/force/axe/blade/sword/... | 引擎内置默认集（主题无关，非武侠烙印） |
| **武学技能** | `kungfu/*/` 门派武学（798 文件） | 雪山剑法/辟邪剑/降龙十八掌/... | module pack 资产（武侠题材包，2.7 门派切割） |
| **特殊技能** | 特殊 action（perform/exert/unique） | 武功绝招/内功心法/特殊 action | CPK 资产（UGC 创作层，M3+） |

**greenfield Skills 组件的组织**（levels dict + 层级标记区分）：

- `Skills.levels: dict[str, int]` 统一存储所有技能等级（skill_id -> level），**不物理分表**。基础技能与武学技能在 levels dict 中平等存储，区分靠 skill_id 命名约定 + 层级标记。
- `Skills.skill_map: dict[str, str]`（新字段）：技能映射（对照 LPC `skill_map`，如 `unarmed -> daxe` 表示 unarmed 技能映射到门派武学 daxe）。query_skill 非 raw 模式 `s += skills[skill_map[skill]]`。
- `Skills.skill_prepare: dict[str, str]`（新字段）：技能准备（对照 LPC `skill_prepare`，双技能 prepare 时按 action_flag 切换）。
- **层级标记**：skill_id 命名约定区分层级（`unarmed`/`dodge`/`parry` = 基础；`kungfu/xueshan/sword` = 武学 module pack；`special/xxx` = CPK）。**引擎不解释 skill_id 前缀**，只做 dict 查找；层级标记是 module pack 加载时的注册约定（2.7 门派切割时定）。

> 层级标记是命名约定非引擎枚举：基础技能集（unarmed/dodge/parry 等）是引擎默认 skill_id，但引擎不硬编码"只有这些 skill_id"（test_theme_neutrality 硬门禁--核心引擎源码无 sword/blade/family 字面量，[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)）。武学 skill_id 由 module pack 注册（如 `kungfu/xueshan/sword`），特殊 skill_id 由 CPK 注册。引擎只认 skill_id 字符串 + levels dict 查找。

**query_skill 完整语义**（对照 [feature/skill.c](../../feature/skill.c) 第 94-109 行，接入 ModifierStack）：

```python
def query_skill(world, eid, skill_id: str, raw: bool = False) -> int:
    skills = world.get(eid, Skills)
    if raw:
        return skills.levels.get(skill_id, 0)
    # 非 raw：apply/{skill} + levels[skill]/2 + levels[skill_map[skill]]
    apply_val = query_temp(world, eid, f"apply/{skill_id}")  # 临时修正
    base = skills.levels.get(skill_id, 0) // 2               # 永久基础值（半值）
    mapped = skills.levels.get(skills.skill_map.get(skill_id, ""), 0)  # 映射技能全值
    return apply_val + base + mapped
```

> `apply/{skill}` 路径访问（如 `apply/unarmed`）是 LPC query_skill 的通用修正层，与 `apply/attack`（ATTACK 路径专用）不同。greenfield 用 query_temp 路径前缀解析（ADR-0025 PATH_PREFIX_MAP 扩展 `apply/` 前缀）。

### 3. Equipment 组件（装备槽 + equip/unequip 语义 + 负重）

**LPC 装备槽**（从 [feature/equip.c](../../feature/equip.c) + [include/weapon.h](../../include/weapon.h) + [include/armor.h](../../include/armor.h) 提取）：

| 槽位 | LPC temp key | 数量 | greenfield 字段 |
|---|---|---|---|
| 主武器 | `query_temp("weapon")` | 1 | `weapon: str \| None`（物品 id） |
| 副武器 | `query_temp("secondary_weapon")` | 0-1 | `secondary_weapon: str \| None` |
| 护甲（按 type） | `query_temp("armor/<type>")` | 每 type 1 件（11 type） | `armors: dict[str, str]`（armor_type -> 物品 id） |
| 盾牌 | `query_temp("armor/shield")` | 0-1（属 armors["shield"]） | armors["shield"] |

**LPC armor_type 完整集**（[include/armor.h](../../include/armor.h)）：head/neck/cloth/armor/surcoat/waist/wrists/shield/finger/hands/boots 共 11 种。greenfield 不在内核枚举（保持主题无关，[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 精神），`armors: dict[str, str]` 的 key 是 armor_type 字符串，由题材数据声明。

**LPC weapon flag**（[include/weapon.h](../../include/weapon.h)）：TWO_HANDED(1)/SECONDARY(2)/EDGED(4)/POINTED(8)/LONG(16)/SELF_ACTION(32)。flag 影响 wield 逻辑（双手武器占双槽、副武器切换）。greenfield Equipment 组件存 flag 值（int 位掩码），wield 语义函数读 flag 判断槽位。

**Equipment 组件 schema 草案**（新组件，可序列化，对照 ADR-0022 存档崩溃安全）：

```python
@dataclass
class Equipment:
    """装备组件（2.3，对照 LPC feature/equip.c wield/wear/unequip）。

    装备槽 + 当前装备的物品 id + prop 累加值副本（unequip 反向扣减用）。
    可序列化（字段全基本类型 + dict 容器，ADR-0022 存档崩溃安全）。
    """
    # 装备槽（物品 id，None=空）
    weapon: str | None = None
    secondary_weapon: str | None = None
    armors: dict[str, str] = field(default_factory=dict)  # armor_type -> item_id

    # 装备 prop 累加值副本（unequip 反向扣减用，对照 LPC applied_prop）
    # key: apply_* 路径（如 "attack"/"dodge"/"damage"/"armor"/"speed"）
    # value: 当前装备累计的 prop 值
    applied_props: dict[str, int] = field(default_factory=dict)

    # 负重（对照 LPC F_MOVE weight/encumbrance，ADR-0025 后置 2.3 衔接）
    encumbrance: int = 0  # 当前负重（物品重量总和）
    max_encumbrance: int = 0  # 最大负重（由 str 决定，LPC set_max_encumbrance）
```

**equip/unequip 语义函数**（对照 [feature/equip.c](../../feature/equip.c) wield/wear/unequip，放 runtime/equipment.py，**不加方法到 dataclass**，保持组件纯数据）：

| 语义函数 | LPC 对照 | 行为 |
|---|---|---|
| `wield(world, eid, item_id) -> bool` | `equip.c wield()` | 检查 flag（TWO_HANDED 占双槽/SECONDARY 副手切换）-> 设 weapon/secondary_weapon -> 把 weapon_prop 累加到 Skills.apply_* + Equipment.applied_props -> reset_action |
| `wear(world, eid, item_id) -> bool` | `equip.c wear()` | 检查 armor_type 槽位占用 -> 设 armors[type] -> 把 armor_prop 累加到 Skills.apply_* + Equipment.applied_props |
| `unequip(world, eid, item_id) -> bool` | `equip.c unequip()` | 按 equipped 标记区分 wielded/worn -> 清 weapon/secondary_weapon/armors[type] -> 按 applied_props 副本反向扣减 Skills.apply_* -> reset_action |
| `is_equipped(equipment, item_id) -> bool` | LPC `query("equipped")` | 判断物品是否已装备 |
| `total_weight(equipment) -> int` | LPC `weight()` | 当前装备总重量 |

**装备 prop 注入 apply_* 的映射**（对照 LPC weapon_prop/armor_prop key）：

| prop key | 注入目标 | 说明 |
|---|---|---|
| `attack` | `Skills.apply_attack` | 武器攻击加成 |
| `dodge` | `Skills.apply_dodge` | 武器/护甲闪避加成（可负，重武器减 dodge） |
| `parry` | `Skills.apply_parry` | 武器招架加成 |
| `damage` | `Skills.apply_damage` | 武器伤害加成 |
| `armor` | `Skills.apply_armor` | 护甲防御加成 |
| `speed` | `Skills.apply_speed`（新字段） | 武器速度加成（可负，重武器减 speed） |

> prop 注入是 equip 时一次性累加（对照 LPC `add_temp("apply/" + key, prop[key])`），unequip 时按 Equipment.applied_props 副本反向扣减。若 prop key 不在已知集（如武侠特有 prop），后置扩展（2.7 门派切割时按题材数据声明补）。

**负重（衔接 ADR-0025 后置 2.3 的 move 负重级联）**：

- LPC F_MOVE（[spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_move_spec`）的 weight/encumbrance 语义：物品有 weight，实体有 max_encumbrance（由 str 决定），move 时检查负重上限。
- greenfield Equipment 组件的 `encumbrance`/`max_encumbrance` 字段承接此语义（ADR-0025 §简化台账第 7 项"move() 负重级联后置 2.3"在本 ADR 补全）。
- `add_encumbrance(world, eid, amount) -> None`：增减负重（对照 LPC `add_encumbrance`）。
- move 时的负重检查：`move_to(world, eid, room_id)`（ADR-0025）扩展为检查 `encumbrance <= max_encumbrance`（超载拒绝 move 或扣 speed，对照 LPC F_MOVE 语义）。

**后置 key 激活**（对照 ADR-0025 §5 后置 key 激活策略，2.3 激活）：

| 后置 key | 激活方式 | 目标组件字段 |
|---|---|---|
| `equipped` | DBASE_KEY_MAP 加条目 | Equipment（is_equipped 语义函数，非简单字段） |
| `weight` | DBASE_KEY_MAP 加条目 | Equipment.encumbrance（或 Inventory 扩展） |
| `encumbrance` | DBASE_KEY_MAP 加条目 | Equipment.encumbrance |
| `apply`（路径前缀） | PATH_PREFIX_MAP 加 `apply` 前缀 | Skills.apply_* 标量（按 apply/attack 等子路径分发） |

### 4. skill_power 完整公式接入 ModifierStack（不重新设计公式）

**ADR-0023 简化台账第 4 项已定稿**（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 决策 4 第 4 项 + [resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) `skill_power()` 已实现）。公式不重新设计，2.3 只设计接入路径。

**现有实现的接入点**（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) `skill_power()` 第 57-107 行）：

```python
# 现有：直接读 CombatantSnapshot 标量字段
level = c.skills.get(skill_id, 0) + apply_mod  # apply_mod = c.apply_attack / apply_dodge / apply_parry
```

**2.3 接入 ModifierStack 的路径**：

| skill_power 输入 | 现有来源（快照标量） | 2.3 接入 ModifierStack 后来源 |
|---|---|---|
| `c.skills.get(skill_id, 0)` | CombatantSnapshot.skills dict（快照拷贝自 Skills.levels） | Skills.levels（永久基础值层） |
| `c.apply_attack` / `c.apply_dodge` / `c.apply_parry` | CombatantSnapshot 标量（快照拷贝自 Skills.apply_*） | Skills.apply_*（临时修正层，equip 已注入装备加成） |
| `c.str_` / `c.dex_` | CombatantSnapshot 标量（快照拷贝自 Attributes） | Attributes.str_ / dex_（永久基础值层） |
| `c.jingli` / `c.max_jingli` | CombatantSnapshot 标量（快照拷贝自 Vitals） | Vitals.jingli / max_jingli（永久基础值层） |
| `c.combat_exp` | CombatantSnapshot 标量（快照拷贝自 Progression） | Progression.combat_exp（永久基础值层） |
| `c.is_fighting` / `c.fight_dodge` | CombatantSnapshot 标量（快照拷贝自 CombatState） | CombatState.is_fighting / fight_dodge（临时状态层） |

**接入策略**（关键决策：快照边界不变，ModifierStack 求值在快照构建边界）：

- **快照构建边界求值**：CombatSystem 在调 resolve_attack 前，从 ECS 组件构建 CombatantSnapshot。2.3 在此边界接入 ModifierStack：`snapshot.apply_attack = skills.apply_attack`（已含装备加成，因 equip 时已注入 Skills.apply_* 标量）。
- **resolve_attack 不变**：skill_power 仍读快照标量，无需感知 ModifierStack（ADR-0023 第 4 项已定稿，不重新设计公式）。
- **ModifierStack 求值是 System/工具层**：equip/unequip 时的 prop 注入、condition 的 apply 修正，都是 System/工具层操作（非 Command），在 tick 外或 equip 命令的 8 段管线中执行。

> 接入路径设计的核心：装备加成在 equip 时注入 Skills.apply_* 标量（对照 LPC wield/wear 注入 apply temp），resolve_attack 读快照标量时自动包含装备加成。无需在 skill_power 公式中遍历装备槽，与 ADR-0023 已定稿的公式完全兼容。

**query_skill 接入 ModifierStack**（对照 LPC query_skill 非 raw 模式三层叠加）：

query_skill 非 raw 模式的三层叠加（`apply/{skill}` + `levels[skill]/2` + `levels[skill_map[skill]]`）在 2.3 实现 query_skill 运行时函数时落地（[ADR-0025](ADR-0025-query-index-layer.md) query/set 接口的扩展）。skill_power 调 query_skill 获取 level，再叠加 `apply/attack` 或 `apply/defense`。

> 现有 resolve_attack.py 的 skill_power **没有调 query_skill**，而是直接 `c.skills.get(skill_id, 0) + apply_mod`（简化版，未含 skill_map 映射全值 + levels/2 半值）。这是 ADR-0023 简化台账的简化点（skill_power 公式已定稿但 query_skill 三层叠加未完整接入）。2.3 补全 query_skill 运行时函数后，skill_power 可改为调 query_skill 获取完整 level（含 skill_map），或保持现状（快照边界由 CombatSystem 负责调 query_skill 填充 snapshot.skills 有效值）。**2.3 倾向后者**：快照边界求值，resolve_attack 不变。

### 5. 简化范围（不做什么，对齐 04 §六收敛）

对照 LPC equip/skill 完整语义，本 ADR 简化以下项（后置或砍掉）：

| LPC 语义 | 简化决策 | 理由 / 后置时机 |
|---|---|---|
| 完整 treemap apply 路径（`apply/a/b/c` 任意深度） | 不实现 | 只支持 `apply/<known_key>` 已知子路径（attack/dodge/parry/damage/armor/speed + skill_id）；ADR-0025 §简化台账第 4 项已定 |
| 动态技能加载（LPC `SKILL_D(skill)` 运行时 load_object） | 不实现 | greenfield 技能数据是静态声明（module pack 注册时加载），无 LPC clone/load_object 机制 |
| 武学招式编辑器（perform/exert 完整实现） | 后置 M3 | [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做已定，2.3 不补 |
| apply 状态修饰 short()（打坐/鬼气/断线/昏迷） | 后置 2.5 | ADR-0025 §简化台账第 6 项已定，TitleSystem + condition 状态修饰 |
| 双武器完整切换逻辑（辟邪剑/双手互博） | 后置 2.4 | fight() 中双武器二次 do_attack，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做已定 |
| LPC `default_ob` 回退（master copy 默认值） | 不实现 | ADR-0025 §简化台账第 2 项已定，greenfield 无 clone/master copy |
| LPC `evaluate()` function 求值（actions 是 functionp） | 不实现 | ADR-0025 §简化台账第 5 项已定，greenfield 无 LPC function 类型 |
| 完整武器系统规格（武器继承树/材质/耐久） | 后置 M3 | [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做已定，2.3 只补 Equipment 组件 + equip/unequip 语义 |
| 物品堆叠/容器/数量 | 后置 M3 | Inventory.items 是 id 集合，2.3 不扩堆叠/容器 |
| 护甲耐久/武器磨损 | 后置 M3 | LPC 护甲/武器无显式耐久（destroy 触发后置），2.3 不实现 |
| apply 修正的来源审计轨迹（condition vs 装备 vs buff） | 后置性能优化 | Equipment.applied_props 记录装备来源，EffectComp 记录 condition 来源，但 apply_* 标量的完整来源链审计后置（dissent 7 派生变更审计覆盖缺口的 2.3 级应对） |

> 简化台账与 [ADR-0025](ADR-0025-query-index-layer.md) §简化台账 / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §简化台账模式一致：明确列出"不做什么"及其后置时机，避免实施时模糊。

### 6. ModifierStack 缓存策略（性能，后置）

**tick=1s + compute<100ms 不变量评估**（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七性能优化备选 1）：

- 每 tick skill_power 调用次数：CombatSystem 遍历有 CombatState 且 enemies 非空的实体（1000 实体中战斗实体通常 <100），每次 resolve_attack 调 skill_power 2-3 次（AP + DP + PP），总调用 <300 次/tick。
- 单次 skill_power 开销：μs 级（[ADR-0012](ADR-0012-performance-microbenchmark.md) resolve_attack 25.9μs 含 skill_power），300 次 < 8ms，远低于 100ms 预算。
- **结论**：2.3 不做 ModifierStack 缓存（收敛优先于完备）。若 T10 压测后 tick profiler 实测 skill_power 成瓶颈，按 [15](../xkx-arch/15-阶段2-子系统实施计划.md) §七备选 1 引入缓存（dirty-flag + 快照边界求值，apply_* 变更时失效）。

## 代码结构

### 新建 `engine/src/xkx/runtime/equipment.py`

```python
# 装备语义函数（对照 LPC feature/equip.c wield/wear/unequip）
def wield(world, eid, item_id) -> bool: ...
def wear(world, eid, item_id) -> bool: ...
def unequip(world, eid, item_id) -> bool: ...
def is_equipped(equipment, item_id) -> bool: ...
def total_weight(equipment) -> int: ...
def add_encumbrance(world, eid, amount) -> None: ...

# ModifierStack 求值（快照边界用，对照 LPC query 链）
def effective_skill_level(world, eid, skill_id, raw=False) -> int: ...
def effective_apply(world, eid, apply_key) -> int: ...
```

### 扩展 `engine/src/xkx/runtime/components.py`

- 新增 `Equipment` 组件（weapon/secondary_weapon/armors + per-slot prop 副本
  weapon_props/secondary_weapon_props/armor_props + encumbrance/max_encumbrance，
  见下方"实现期细化"第 2 项）。
- `Skills` 组件扩展：`apply_speed: int = 0`（apply/speed 字段）+ `skill_map: dict[str, str]`
  + `skill_prepare: dict[str, str]` + `learned: dict[str, int]`（skill_death_penalty
  learned 进度用，见下方"实现期细化"第 1 项）。

### 扩展 `engine/src/xkx/runtime/dbase_map.py`

- DBASE_KEY_MAP 加 `equipped`/`weight`/`encumbrance`/`apply_speed` 条目（从 POSTPONED_KEYS 移除）。
- PATH_PREFIX_MAP 加 `apply` 前缀（`apply/attack` -> Skills.apply_attack 等子路径分发）。

### 扩展 `engine/src/xkx/runtime/query.py`（ADR-0025 产出）

- `query_skill(world, eid, skill_id, raw=False)` 运行时函数（三层叠加：apply/{skill} + levels/2 + levels[skill_map]）。
- `apply/` 路径前缀解析（`apply/attack` -> Skills.apply_attack 标量）。

### 扩展 `engine/src/xkx/combat/context.py`

- `CombatantSnapshot` 加 `apply_speed: int = 0`（若 fight/riposte 路径需要）。
- 快照构建边界从 Equipment + Skills.apply_* 拷贝（equip 已注入 apply_*，快照自动含装备加成）。

### 测试 `engine/tests/test_modifier_stack.py`

- ModifierStack 三类叠加：永久基础值 + 临时修正 apply_* + 装备加成，对照 LPC query 链。
- equip/unequip 语义：wield/wear/unequip 的 prop 注入与反向扣减。
- 负重：add_encumbrance + move 负重检查。
- 技能三层：levels dict + skill_map + skill_prepare。
- hypothesis 属性测试：
  - equip + condition 同 key 修正后 unequip，apply_* 正确回到 condition-only 状态（dissent 3 基线断言）。
  - query_skill 三层叠加往返一致（raw vs 非 raw + skill_map 映射）。
  - 三类叠加顺序无关性（装备加成与临时修正交换注入顺序，结果一致--因 apply_* 是累加标量）。
- test_theme_neutrality 硬门禁持续通过（Equipment 无武侠语义，armor_type/weapon_prop 由题材数据声明）。

## 简化台账（与 LPC equip/skill 的差异）

| # | LPC 语义 | greenfield 实现 | 后置时机 | 关联 |
|---|---|---|---|---|
| 1 | 完整 treemap apply 路径 | 只 `apply/<known_key>` 已知子路径 | 砍掉 | [ADR-0025](ADR-0025-query-index-layer.md) §台账第 4 项 |
| 2 | 动态技能加载（SKILL_D load_object） | 静态声明（module pack 注册） | 砍掉 | [feature/skill.c](../../feature/skill.c) |
| 3 | 武学招式编辑器（perform/exert） | 不实现 | M3 | [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做 |
| 4 | apply 状态修饰 short() | 不实现 | 2.5 TitleSystem | [ADR-0025](ADR-0025-query-index-layer.md) §台账第 6 项 |
| 5 | 双武器完整切换（辟邪剑/双手互博） | 不实现 | 2.4 Combat | [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做 |
| 6 | `default_ob` 回退 | 不实现 | 砍掉 | [ADR-0025](ADR-0025-query-index-layer.md) §台账第 2 项 |
| 7 | `evaluate()` function 求值 | 不实现 | 砍掉 | [ADR-0025](ADR-0025-query-index-layer.md) §台账第 5 项 |
| 8 | 完整武器系统规格（继承树/材质/耐久） | Equipment 组件 + equip/unequip only | M3 | [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做 |
| 9 | 物品堆叠/容器/数量 | Inventory.items id 集合 only | M3 | [components.py](../../engine/src/xkx/runtime/components.py) Inventory |
| 10 | 护甲耐久/武器磨损 | 不实现 | M3 | LPC 无显式耐久 |
| 11 | apply 修正来源审计轨迹 | Equipment.applied_props + EffectComp 分记 | 后置（dissent 7） | [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp |
| 12 | ModifierStack 缓存 | 不实现（每 tick 重算） | 性能优化备选 1 | [15](../xkx-arch/15-阶段2-子系统实施计划.md) §七 |
| 13 | `apply/speed` 字段 | 2.3 新增 Skills.apply_speed | 本任务 | [combatd.c](../../adm/daemons/combatd.c) fight/riposte |
| 14 | skill_map/skill_prepare 字段 | 2.3 新增 Skills 字段 | 本任务 | [feature/skill.c](../../feature/skill.c) map_skill/prepare_skill |
| 15 | query_skill 完整三层叠加 | 2.3 实现（apply/{skill} + levels/2 + skill_map） | 本任务 | [feature/skill.c](../../feature/skill.c) query_skill |

> 简化台账与 [ADR-0025](ADR-0025-query-index-layer.md) §简化台账 / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §简化台账模式一致。砍掉项 = greenfield 不实现（LPC 特有机制）；后置项 = 对应子系统实现时补。

## 实现期细化（2.3 编码记录）

编码 2.3 时对本 ADR 草案的以下细化（实现偏离草案，记录于此）：

1. **Skills 加 `learned: dict[str, int]` 字段**：草案 §2 Skills 扩展只列
   apply_speed/skill_map/skill_prepare，未覆盖 skill_death_penalty（[skill.c:121-147](../../feature/skill.c)）
   需要的 learned 进度字段。2.3 补 learned（衔接 2.2 skill_death_penalty stub，
   实现真实 learned 阈值公式）。improve_skill 保持简化（KIND_SKILL_IMPROVE 直接
   +1 level，不累加 learned，[world.apply_effects](../../engine/src/xkx/runtime/world.py) 不变）。

2. **Equipment per-slot prop 副本**：草案 §3 schema 用单 `applied_props: dict[str, int]`
   （总和），但 unequip 单个物品需按该物品 prop 反向扣减，单总和 dict 无法
   per-item 区分。2.3 改 per-slot 副本（`weapon_props`/`secondary_weapon_props`/
   `armor_props`），unequip 按槽位副本扣减。

3. **`equipped` 语义 key 不进 DBASE_KEY_MAP**：草案 §3 后置 key 激活表说
   "equipped -> DBASE_KEY_MAP 加条目"，但 equipped 非简单字段（is_equipped 语义
   函数）。2.3 用单独 `SEMANTIC_KEY_MAP`（不参与 validate_dbase_map 字段校验），
   `query("equipped")` 返回装备物品集合，`set("equipped")` raise（装备走 wield/wear）。

4. **apply/ 未知子路径读返回 0**：通用 `apply/{skill}`（任意 skill_id）开放存储
   后置 M3（greenfield 只 6 个已知标量）。未知子路径（`apply/unarmed` 等）读
   返回 0（LPC query_temp 未设语义），set raise（无存储）。

5. **skill_death_penalty 修正 LPC 覆盖 bug**：LPC 无 learned 分支
   `learned = ([sk:val])` 在循环内覆盖整个 mapping 只记最后一个（显然 bug），
   greenfield 用 `learned[sk] = t` 累加记所有技能进度。

6. **wield/wear 不自动算重量**：物品重量/负重自动计算后置 M3 物品系统（草案
   简化台账第 9 项），wield/wear 不调 add_encumbrance，由调用方管理。

## 验收标准（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.3）

- [ ] ModifierStack 三类叠加与 LPC `query_temp("apply/attack")` + 装备加成等价（永久基础值 + 临时修正 apply_* + 装备加成）
- [ ] 技能三层划分清晰（基础技能 / 武学技能 module pack / 特殊技能 CPK，levels dict + skill_map 区分）
- [ ] Equipment 组件：装备槽（weapon/secondary_weapon/armors）+ equip/unequip 语义（对照 LPC wield/wear/unequip）+ 负重（encumbrance/max_encumbrance）
- [ ] skill_power 完整公式接入 ModifierStack（基础值从 Skills.levels，apply_* 从 Skills 标量，装备加成从 Equipment 注入）-- 不重新设计公式（ADR-0023 已定稿）
- [ ] query_skill 完整三层叠加（apply/{skill} + levels/2 + skill_map，对照 LPC query_skill 非 raw 模式）
- [ ] 后置 key 激活：equipped/weight/encumbrance/apply_speed（从 POSTPONED_KEYS 移除，DBASE_KEY_MAP 加条目）
- [ ] apply/ 路径前缀解析（PATH_PREFIX_MAP 加 apply 前缀，apply/attack -> Skills.apply_attack）
- [ ] Equipment 组件可序列化（ADR-0022 存档崩溃安全，字段全基本类型 + dict 容器）
- [ ] hypothesis 属性测试：equip + condition 同 key 修正后 unequip 正确回归 + query_skill 三层叠加往返 + 三类叠加顺序无关性
- [ ] 现有 1101 tests 不回归（resolve_attack.py skill_power 不变，快照边界接入 ModifierStack）
- [ ] ruff 全过（行长 100，中文按字符数计）
- [ ] test_theme_neutrality 硬门禁持续通过（Equipment 无武侠语义，armor_type/weapon_prop 由题材数据声明，核心引擎源码无 sword/blade/family 字面量）

## 关联 dissent

| dissent | 本 ADR 应对 |
|---|---|
| **3（规则冲突语义漂移，ModifierStack 三类叠加语义模糊）** | 三类语义明确（永久基础值 / 临时修正 apply_* / 装备加成）+ 三类叠加顺序对照 LPC query 链 + hypothesis 属性测试断言叠加等价（equip + condition 同 key 修正后 unequip 正确回归） |
| **3（层1 原语蠕变，apply_* 不落入层1 DSL）** | apply_* 是 ModifierStack 内部层（数值修正层），不落入层1 DSL（层1 是 condition->action 触发器，apply_* 是数值修正，两者正交）。层1 KPI<15% 护栏不因 apply_* 膨胀 |
| **专家 3 承重论断（技能三层）** | 基础技能（引擎内置默认集）/ 武学技能（module pack 资产）/ 特殊技能（CPK 资产）三层划分落地，levels dict + skill_map 统一存储 + 层级标记区分 |
| **8（存储语义，新组件可序列化）** | Equipment 组件字段全基本类型 + dict 容器，可序列化（ADR-0022 存档崩溃安全）；Skills 扩展字段（apply_speed/skill_map/skill_prepare）同可序列化 |
| **7（派生变更审计覆盖缺口）** | Equipment.applied_props 记录装备来源，EffectComp 记录 condition 来源；apply_* 标量的完整来源链审计后置（2.3 级应对：分记来源，不建完整链） |

## 不做（范围边界）

- **不实现代码**：本 ADR 是设计文档，编码是第二波 2.3 agent 的任务。
- **不重新设计 skill_power 公式**：ADR-0023 简化台账第 4 项已定稿（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 已实现），2.3 只设计接入路径（快照边界求值，resolve_attack 不变）。
- **不做完整 treemap apply 路径**：只 `apply/<known_key>` 已知子路径（attack/dodge/parry/damage/armor/speed + skill_id），[ADR-0025](ADR-0025-query-index-layer.md) §简化台账第 4 项已定。
- **不做动态技能加载**：greenfield 技能数据是静态声明（module pack 注册时加载），无 LPC clone/load_object 机制。
- **不做武学招式编辑器**：perform/exert 完整实现后置 M3（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做）。
- **不做双武器完整切换逻辑**：辟邪剑/双手互博后置 2.4 Combat（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做）。
- **不做 ModifierStack 缓存**：每 tick 重算 skill_power 开销 μs 级（<8ms/tick），缓存后置性能优化备选 1（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七）。
- **不做完整武器系统规格**：武器继承树/材质/耐久后置 M3，2.3 只补 Equipment 组件 + equip/unequip 语义。
- **不做物品堆叠/容器/数量**：Inventory.items 是 id 集合，2.3 不扩。
- **不做 apply 修正来源完整审计链**：Equipment.applied_props + EffectComp 分记来源，完整链后置（dissent 7）。
- **不做 apply 状态修饰 short()**：后置 2.5 TitleSystem（[ADR-0025](ADR-0025-query-index-layer.md) §简化台账第 6 项）。
- **不扫全量 LPC 调用点**：聚焦层 E 规格 + equip.c 涉及键（apply_* / weapon_prop / armor_prop / equipped / weight / encumbrance）。
- **不修改 LPC 源**（只读规格）。
- **不在内核枚举武器类型/护甲类型**：armor_type/weapon_prop 由题材数据声明（[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 主题无关性），Equipment 组件存字符串 key，内核不解释。

*最后更新：2026-07-12*
