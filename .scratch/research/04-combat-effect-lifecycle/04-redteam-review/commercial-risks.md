# 红队商业化风险挑战：战斗与效果生命周期簇

> 角色：商业化风险挑战者（红队）。任务：识别「战斗与效果生命周期簇」的经济风险与 pay-to-win 陷阱，重点质疑战斗付费点、死亡惩罚付费减免、武功/装备/Effect 资产归属、数值红线遵守情况、engine 商业支撑点完整性。
> 质疑规则：每条结论必须标注被质疑文件与段落，并给出 LPC 或 engine 证据来源（文件路径 + 函数/对象名/行号）。禁止凭空推断。

---

## 0. 总评

商业化方案（`03-engine-insights/commercialization.md`）在死亡惩罚、武功、装备三条主线上**大方向守住不 pay-to-win 红线**，但存在三处结构性风险：

1. **数值红线内部存在矛盾**——数值平衡专家把「技能等级」列为绝对红线，商业化方案却把「付费加速技能升级」判为边界安全；
2. **便利性付费与数值付费的边界在某些场景下模糊**——复活点选择、昏迷加速、技能重置、PvP 保护期等 convenience 项目，在 PvP/死亡循环中可能转化为实际战斗优势；
3. **engine 当前缺少商业化支撑点的数据基建**——Effect 引擎缺失、资产无归属字段、事件上下文无 `pack_id`、Currency 无双货币类型、全局注册表未按 World 隔离，导致即便商业化规则正确，也无法落地分成与埋点。

以下按主题逐条质疑。

---

## 1. 数值红线遵守情况：商业化方案与数值平衡专家的矛盾

### 1.1 技能等级被数值专家列为红线，商业化方案却允许付费加速

**被质疑**：`03-engine-insights/commercialization.md` §1.2 表格第 2 行（:69）。

数值平衡专家在 `03-engine-insights/numerical-balance.md` §7.1 明确把「技能等级（skill level）」列为**绝不能付费影响**的数值红线，理由是 LPC `skill_power()` 使用立方缩放，`level` 差 1 级可造成约 3 倍 `power` 差异（numerical-balance.md:419）。

商业化方案在同一节却把「付费加速技能升级（双倍经验）」判为「边界安全」，理由是「加速只省时间不破上限」（commercialization.md:69）。**这是直接矛盾**：

- 若技能等级本身影响战斗胜负，则任何缩短到达该等级时间的付费手段，本质都是**让玩家更早获得本应通过时间积累的战斗数值优势**；
- 方案中的补救条件「加速倍率须全玩家可获取（订阅福利），不能是 premium 独占的更高倍率」只是把 pay-to-win 转化为「订阅玩家 vs 免费玩家」的不平等，并未消除数值优势；
- 该判定与 §7.1 中「技能等级…付费影响即破坏公平性」的措辞冲突，红队认为应统一为**禁止付费加速技能等级成长**，或至少要求加速完全不影响 PvP 匹配的等级区间。

**证据**：
- 红线来源：`03-engine-insights/numerical-balance.md:418-428`（表格：技能等级、combat_exp、max_neili/max_jingli、str/dex/con/int、武器 weapon_prop/damage、jiali/jiajin、apply/*、jingli_bonus 均列为红线）；
- 矛盾来源：`03-engine-insights/commercialization.md:69`「付费加速技能升级（双倍经验）…边界安全」。

### 1.2 「死亡后保留 skill_map」被判为安全，但 skill_map 清空是 LPC 死亡惩罚的组成部分

**被质疑**：`03-engine-insights/commercialization.md` §1.1 表格第 1 行（:45）。

商业化方案把「死亡后保留 skill_map（不用重新 map 技能）」判为纯便利性付费。但 `feature/skill.c:skill_death_penalty()` :145 在死亡惩罚中**清空 skill_map**，且 `feature/skill.c:map_skill()` :42-58 是战斗时 `reset_action()` 选择武功动作的前置条件。保留 skill_map 意味着玩家死亡后无需重新执行映射操作即可继续发挥全部武功效能，这确实不直接改数值，但在高频死亡场景下（如 PvP 霸凌），**付费保留操作便利会显著降低死亡的有效打击感**，间接削弱惩罚的威慑力。

更关键的是，这与商业化方案自身 §3.1 把「技能等级损失」列为禁止付费减免（commercialization.md:207-210）存在张力：如果 skill_map 清空是 `skill_death_penalty()` 的副作用，那么付费保留它就是对同一惩罚链条的**部分付费绕过**。

**证据**：
- `feature/skill.c:skill_death_penalty()` :121-147（死亡时所有技能 -1 级、learned 重置、skill_map 清空）；
- `feature/skill.c:map_skill()` :42-58（skill_map 决定战斗动作来源）；
- 商业化自我矛盾：`commercialization.md:45` 判为安全，`commercialization.md:207-210` 又禁止付费减免技能等级损失。

### 1.3 商业化方案对「阵营损失（shen）付费保留」的判定过宽

**被质疑**：`03-engine-insights/commercialization.md` §3.1 表格最后一行（:211）。

商业化方案把「shen（善恶/阵营）损失」判为「可付费保留」，理由是「阵营是社交/门派属性，非战斗数值」。但 LPC 中 shen 直接影响 `killer_reward()` 的善恶偏移（`combatd.c:1076-1077`），并间接决定 NPC 的 `berserk` 触发阈值（`combatd.c:869-902` 按负 shen 判定狂暴）。在武侠题材包中，shen 可能关联门派技能学习资格、NPC 敌对态度、甚至某些武功的可用性。因此**shen 并非纯社交属性**，付费保留阵营损失可能转化为任务/门派/战斗准入优势。

**证据**：
- `adm/daemons/combatd.c:killer_reward()` :1076-1077（shen 调整）；
- `adm/daemons/combatd.c:start_berserk()` :869-902（shen 判定狂暴）；
- 商业化判定：`03-engine-insights/commercialization.md:211`「阵营损失…可付费保留」。

---

## 2. 死亡惩罚付费减免：红线清晰但存在绕过路径

### 2.1 死亡数值惩罚禁止付费减免的方向正确，但 engine 的 `penalty_ratio` 单一比例反而削弱了红线区分度

**被质疑**：`03-engine-insights/commercialization.md` §3.1-3.2。

商业化方案正确地把 combat_exp、potential、balance、技能等级列为禁止付费减免（commercialization.md:207-210），符合 numerical-balance.md 红线。但 engine `death_flow.py:DeathPolicy` 只提供单一 `penalty_ratio`（:81），统一扣减货币与技能经验（death_flow.py:291-305）。

这种单一比例设计**表面上看更安全**（难以做定向减免），但也带来两个风险：

1. **无法表达 LPC 的分项惩罚结构**（combatd.c:987-1025：combat_exp 1%、potential 50%、balance 超 1 万部分 50%、shen/behavior_exp 5%、skill -1 级）。若题材包希望采用 LPC 式重惩罚，必须改代码而非调 YAML；
2. **商业化时若要推出「死亡保险」类产品**，单一比例无法只保货币不保经验，或只保装备不保技能，容易被迫回到「全保/全不保」的二元选择，增加越线诱惑。

**证据**：
- engine 单一比例：`engine/src/openmud/death_flow.py:77-86` DeathPolicy、`death_flow.py:291-305` `_apply_currency_penalty`/`_apply_skill_exp_penalty`；
- LPC 分项惩罚：`adm/daemons/combatd.c:death_penalty()` :987-1025。

### 2.2 「付费跳地府迷宫」被判为便利，但地府迷宫在 LPC 中是死亡惩罚的「时间成本」组成部分

**被质疑**：`03-engine-insights/commercialization.md` §1.4 表格第 1 行（:113）。

商业化方案认为付费跳过 `d/death/road2.c:valid_leave()` 的 `long_road` 五次走迷宫是纯便利。但 LPC 地府流程是死亡惩罚的**仪式+时间惩罚**（player-psychology.md §2.3 明确把地府流程称为「强制离线体验」「不可跳过、无交互乐趣、纯惩罚体验」）。付费跳过时间惩罚，虽然不改数值，但**降低了死亡惩罚的整体痛感**，与「死亡惩罚不可付费减免」原则存在边界模糊。

红队认为：地府迷宫跳过可作为**订阅/全玩家福利**存在，但不应作为 premium 独占付费项，否则付费玩家死亡成本显著低于免费玩家，形成心理层面的「付费免惩」。

**证据**：
- 地府迷宫机制：`d/death/road2.c:24-46` valid_leave（`long_road` 累 5 才放行）；
- 时间惩罚定性：`03-engine-insights/player-psychology.md:81-88`（地府流程是强制耗时 1-3 分钟的纯惩罚体验）。

### 2.3 engine 死亡惩罚力度远低于 LPC，压缩了合规付费空间但也隐藏了题材包越线风险

**被质疑**：`03-engine-insights/commercialization.md` §6.2 第 4 点（:360）。

商业化专家指出：LPC `skill_death_penalty()` 是「每技能 -1 级」（feature/skill.c:131），engine 是「按比例扣经验」（death_flow.py:303-305），因此 LPC 模式下「付费保技能等级」痛感更强、付费空间更大，engine 模式下付费空间更小。这一观察正确，但反向也成立：

- 若题材包创作者为了「增强商业化空间」而自行恢复 LPC 式 -1 级惩罚，则付费保技能等级会**直接变成 pay-to-win**（因为技能等级是数值红线）；
- engine 的温和设计实际上降低了未来引入 LPC 式重惩罚的商业安全性，因为一旦恢复重惩罚，相关付费点极易越线。

**证据**：
- LPC 技能降级：`feature/skill.c:skill_death_penalty()` :121-147；
- engine 扣经验：`engine/src/openmud/death_flow.py:299-305` `_apply_skill_exp_penalty`；
- 商业化专家判断：`03-engine-insights/commercialization.md:360`。

---

## 3. 装备与便利性付费：边界模糊与 engine 结构漏洞

### 3.1 engine 当前无法区分「数值件」与「外观件」，留下付费装备越线后门

**被质疑**：`02-user-stories/operator-stories.md` US-W22（:217-221）、`03-engine-insights/creator-perspective.md` §5.2（:361-369）。

商业化方案在 §1.3 正确判定「更高数值装备」「不磨损装备」「带毒武器」均为红线（commercialization.md:91-93）。但 engine `components.py:Equippable` 只是占位组件（`components.py:270-274`「M1 不实现 wield/wear」），`m2_mvp_scene.yaml` 的 `steel_blade` 只有 `tags:[weapon,edged]` 而**无 `weapon_prop/damage`、无 `stat_prop`/`cosmetic` 双槽**（creator-perspective.md §2.5、operator-stories US-W20）。

这意味着：

- 即使商业化规则禁止付费数值装备，engine 也**没有数据结构来强制区分**数值属性与外观属性；
- 题材包创作者若把付费外观装备同时加上隐藏 `damage` 标签或 `SkillBehavior` 钩子，即可绕过「不 pay-to-win」约束；
- 缺乏装备数值接入战斗的 schema，导致「数值件免费、外观件付费」的红线无法被 `--validate` 校验。

**证据**：
- engine 装备占位：`engine/src/openmud/components.py:270-274` Equippable；
- 场景物品无数值：`engine/data/m2_mvp_scene.yaml:406-414` steel_blade；
- 双槽需求：`02-user-stories/operator-stories.md:217-221` US-W22；
- 商业化红线：`03-engine-insights/commercialization.md:91-93`。

### 3.2 「坐骑速度加成」若不加拆分，会复刻 LPC `apply/speed` 的双用途陷阱

**被质疑**：`03-engine-insights/numerical-balance.md` §7.3（:442-446）、`03-engine-insights/commercialization.md` §7.2 表格最后一行（:439）。

数值平衡专家明确警告：`apply/speed` 在 LPC 中同时影响反击概率和攻击主动性（combatd.c:766/818），若付费坐骑提供 `apply/speed` 加成会间接影响战斗，必须**分离移动 speed 与战斗 speed**（numerical-balance.md:442-446）。

商业化方案在 §7.2 把「坐骑速度加成」判为边界安全，但只给出条件「若只影响移动非战斗 speed」。由于 engine 当前没有移动 speed 与战斗 speed 的分离 schema（`components.py` 无 speed 类型白名单），该条件**无法被 engine 强制执行**。题材包创作者很可能沿用 LPC 的单一 `apply/speed` 语义，导致付费坐骑越线。

**证据**：
- LPC `apply/speed` 双用途：`adm/daemons/combatd.c:818`（攻击主动性）、`:766-779`（反击概率）；
- 数值专家警告：`03-engine-insights/numerical-balance.md:442-446`；
- 商业化条件判定：`03-engine-insights/commercialization.md:439`。

### 3.3 「昏迷苏醒时间缩短」在 PvP 中可能转化为数值优势

**被质疑**：`03-engine-insights/commercialization.md` §1.4 表格第 4 行（:116）。

商业化方案把「付费缩短复活冷却时间」判为便利，理由是 engine `DeathPolicy.unconscious_recovery_ticks` 是配置项。但 `unconscious` 在 LPC 中是战斗中间态——昏迷玩家是「活靶」可被继续攻击致死（combatd.c:799-815 走 TYPE_QUICK 快攻），苏醒越快意味着**在 PvP 中被补刀致死的窗口越短**。

因此，缩短昏迷苏醒时间不仅是 convenience，在 PvP 场景下是**生存能力加成**，属于数值边界项目。商业化方案未区分 PvE/PvP 场景，留下公平性风险。

**证据**：
- 昏迷是活靶：`adm/daemons/combatd.c:fight()` :799-815；
- engine 昏迷参数：`engine/src/openmud/death_flow.py:85` `unconscious_recovery_ticks`；
- 商业化判定：`03-engine-insights/commercialization.md:116`。

---

## 4. Effect 与题材包资产归属：商业化核心支撑点严重缺失

### 4.1 `conditions.py` 概念错位导致 Effect 作为资产完全无法承载

**被质疑**：`03-engine-insights/commercialization.md` §6.2 第 1 点（:352-355）、`03-engine-insights/creator-perspective.md` §2.4（:226-251）、`06-engine-critique/engine-comparison.md` 模块 3。

商业化方案和创作者视角都指出：`engine/src/openmud/conditions.py` 是通用布尔求值器（Predicate/Equals/Gte/And/Or/Not，conditions.py:92-142），**不是** LPC `feature/condition.c` 的时效性 Effect 引擎（conditions.py:1-22 docstring 自述）。

这意味着：

- 毒、盲、醉、牢、包扎、嵌入暗器等 72 个 LPC Effect（creator-perspective.md §0）在 engine 中**无任何对应抽象**；
- Effect 是题材包差异化战斗体验与商业化核心资产（武侠毒/点穴 vs 仙侠灼烧/封印 vs 科幻辐射），缺失 Effect 引擎等于**题材包「卖不出差异化战斗体验」**（creator-perspective.md §5.3）；
- 即使未来补建 Effect 引擎，当前也没有 `source_pack`/`creator_id`/`version` 字段来支撑分成。

这是商业化层面**最高优先级的结构性缺口**。

**证据**：
- conditions.py 自述：`engine/src/openmud/conditions.py:1-22`；
- LPC Effect 引擎：`feature/condition.c:8,21-69,79-85`；
- 72 个 condition daemon：`03-engine-insights/creator-perspective.md:8-11`、`kungfu/condition/` 目录；
- engine-critique 定性：`06-engine-critique/engine-comparison.md` 模块 3.1a「概念错位（核心）」。

### 4.2 武功/装备/Effect 均缺少创作者归属与版本溯源字段

**被质疑**：`03-engine-insights/commercialization.md` §2.2（:165-179）、`02-user-stories/operator-stories.md` US-W25（:241-247）。

`06 号票`要求「题材包资产元数据：创作者归属 + 版本溯源」（CLAUDE.md 架构不变量 6）。但 engine 中：

- `skills.py:SkillData` :37 只有 `skill_id`，无 `pack_id`/`creator_id`/`version`（commercialization.md:168-169）；
- `components.py:ItemTemplateKey` :431 只有 `key`，无归属字段（commercialization.md:170）；
- `death_flow.py:LootTable` :90 的 `item_template_keys` 引用模板，但模板本身无归属（commercialization.md:171）；
- `SKILLS` 是全局扁平 `dict[str, SkillData]`，多包加载时 skill_id 冲突无法处理（commercialization.md:178）。

没有归属字段，就无法实现「按题材包消费分成」（CLAUDE.md 架构不变量 6）。这是商业化落地的**数据基建缺失**。

**证据**：
- SkillData 无归属：`engine/src/openmud/skills.py:36-53`；
- ItemTemplateKey 无归属：`engine/src/openmud/components.py:431`；
- 全局注册表问题：`engine/src/openmud/skills.py:54` `SKILLS`、`:56` `_SKILL_BEHAVIORS`；
- 需求来源：`02-user-stories/operator-stories.md:241-247` US-W25、`03-engine-insights/commercialization.md:165-179`。

### 4.3 全局技能注册表未按 World 隔离，威胁多题材包分成准确性

**被质疑**：`03-engine-insights/commercialization.md` §5.4（:321-334）。

`SKILLS` 与 `_SKILL_BEHAVIORS` 是模块级全局变量（skills.py:54/56），`replace_skills_registry()` 每次 `load_scene` 清空重建。单 World 下安全，但 `06 号票`要求「每个题材包/世界实例独立进程运行」（commercialization.md:323）。若未来一进程跑多 World，全局注册表会串包，导致：

- 不同题材包的同名 skill_id 互相覆盖；
- 消费记录无法准确归因到具体题材包；
- 创作者分成计算错误。

**证据**：
- 全局注册表：`engine/src/openmud/skills.py:54-56`；
- 隔离需求：`03-engine-insights/commercialization.md:321-334`、`docs/adr/0009-single-process-single-world.md`。

---

## 5. Engine 商业支撑点：货币、埋点、隔离均不到位

### 5.1 Currency 组件无双货币类型，死亡惩罚与商店消费无法区分免费/付费

**被质疑**：`03-engine-insights/commercialization.md` §5.1（:299-312）。

Iron Realms 模式要求「双货币：免费金币 + premium 点数，可在玩家间市场互换」（commercialization.md §0）。但 engine `components.py:Currency` :650 只有单一 `amount: int`，无 `currency_type` 字段。

这导致：

- 死亡金钱惩罚无法区分扣的是免费金币还是 premium 点数——若 premium 被重罚会引发客诉（commercialization.md:309）；
- 商店购买装备无法记录「用哪种货币买的」，分成只对 premium 消费生效的规则无法执行；
- 付费解锁武功时无法判断消费类型。

**证据**：
- 单一 Currency：`engine/src/openmud/components.py:650`；
- 双货币需求：`03-engine-insights/commercialization.md:11-19`（Iron Realms 模式）、`commercialization.md:299-312`。

### 5.2 战斗/死亡事件上下文缺少 `pack_id`，无法落地题材包消费埋点

**被质疑**：`03-engine-insights/commercialization.md` §4.2（:262-274）、`02-user-stories/operator-stories.md` US-W24（:234-239）。

CLAUDE.md 架构不变量 6 要求「消费/参与度埋点可打点到题材包 ID」。engine 在 `combat_system.py` 和 `death_flow.py` 中已设事件点（`ON_BEFORE_COMBAT_ROUND`/`ON_COMBAT_ROUND`/`ON_COMBAT_END`、`ON_BEFORE_DEATH`/`ON_DEATH`/`ON_REVIVE`），但所有事件上下文（`CombatRoundContext`、`CombatEndContext`、`DeathContext`、`TickContext`）均**无 `pack_id` 字段**（commercialization.md:274）。

商业化方案建议「在 World 层面挂载 pack_id，事件上下文从 world.pack_id 读取」（commercialization.md:290），但目前 `World` 类无此字段。缺少埋点维度，题材包消费分成与参与度分析无法落地。

**证据**：
- 事件上下文无 pack_id：`engine/src/openmud/combat.py:33-56` CombatContext、`:59-70` CombatRoundResult；`engine/src/openmud/death_flow.py:99-107` DeathContext；
- 需求来源：`02-user-stories/operator-stories.md:234-239` US-W24、`03-engine-insights/commercialization.md:262-290`。

### 5.3 账本抽象缺失，分成结算无据可依

**被质疑**：`03-engine-insights/commercialization.md` §5.1（:307-310）。

商业化方案建议新增 `LedgerEntry` 数据类记录 `{timestamp, from_entity, to_entity, amount, currency_type, pack_id, item_key, creator_id}`，但 engine 当前完全无此抽象。没有消费账本，就无法：

- 追踪每笔 premium 消费的去向；
- 按题材包 + 创作者计算分成；
- 审计退款、纠纷、套利行为。

**证据**：
- 无 LedgerEntry：`engine/src/openmud/` 全模块 grep 无 `Ledger`、`ledger`、`transaction` 等价物；
- 需求来源：`03-engine-insights/commercialization.md:307-310`。

---

## 6. PvP 与保护期付费：公平性风险

### 6.1 PvP 保护期付费可能制造「付费玩家免被 PK」的不公平生态

**被质疑**：`03-engine-insights/commercialization.md` §1.5 表格第 1 行（:136）。

商业化方案把「付费购买 PvP 保护期（一段时间不被强制 PK）」判为边界安全，但附加条件「不得在 PvP 区域提供强制保护」。然而：

- LPC 的新手保护只有 `mud_age < 18000`（5 小时），player-psychology.md §6.1 已指出这远远不够，建议扩展为保护期；
- 玩家心理专家把「被杀保护期（复活冷却）」列为**必须实现的体验底线**（player-psychology.md §6.3），属于基础保护机制；
- 若该保护期成为付费项，则免费玩家在复活后/新手期外将成为付费玩家的「猎物」，**破坏 PvP 生态公平性**。

红队认为：PvP 保护期应作为**全玩家基础机制**或**订阅通用福利**，不应作为按次付费项目，否则直接鼓励「付费规避社交风险」。

**证据**：
- LPC 新手保护：`cmds/std/kill.c:51-53`、`cmds/std/hit.c:71-72`；
- 保护期是体验底线：`03-engine-insights/player-psychology.md:226-228` §6.3；
- 商业化判定：`03-engine-insights/commercialization.md:136`。

### 6.2 「付费查看对手战斗数值」虽不碰数值，但会放大老玩家对新玩家的碾压

**被质疑**：`03-engine-insights/commercialization.md` §1.5 表格第 2 行（:137）。

商业化方案把「付费查看对手 AP/DP/PP」判为安全。该功能确实不改数值，但 LPC 的数值体系中高技能/高经验玩家对低等级玩家已有碾压优势（numerical-balance.md §4.3），付费查看会**让强者更精准地选择可碾压目标**，加剧新手挫败感。

此功能可作为纯信息工具存在，但必须配套「新手保护/不可查看低于某等级玩家」等规则，否则会成为霸凌辅助工具。

**证据**：
- 数值鸿沟：`03-engine-insights/numerical-balance.md:236-253` §4.3；
- 商业化判定：`03-engine-insights/commercialization.md:137`。

---

## 7. 隐藏 pay-to-win 陷阱：时间付费与 LPC 遗留数值设计的耦合

### 7.1 LPC 的 `combat_exp` 防御衰减循环和立方缩放，使「节省时间」类付费间接获得数值优势

**被质疑**：`03-engine-insights/numerical-balance.md` §3.1、§3.4、§9.2（:146-166, 185-193, 540-541）。

数值平衡专家指出 LPC `skill_power()` 使用 `level^3/3` 立方缩放（combatd.c:317），且 `combat_exp` 会概率性削减伤害（combatd.c:636-641）。这两项设计使「游戏时长」直接转化为巨大的战斗数值优势：

- 等级差 2 倍则 power 差 8 倍；
- 高 combat_exp 角色对低 combat_exp 角色命中率趋近 100%，被命中率趋近 0。

在此体系下，**任何「节省时间」的付费项目（加速升级、加速练功、自动战斗）都会让玩家更快抵达高等级/高经验区间，从而获得碾压性战斗优势**。这与「不 pay-to-win」原则存在结构性冲突——不是付费买数值，而是付费买「到达数值的时间」，结果等价。

红队建议：新引擎必须废弃立方缩放与 combat_exp 防御衰减（numerical-balance.md §9.2 已建议），否则便利性付费会系统性滑向 pay-to-win。

**证据**：
- 立方缩放：`adm/daemons/combatd.c:skill_power()` :317；
- 经验减伤：`adm/daemons/combatd.c:do_attack()` :636-641；
- 数值专家弃用建议：`03-engine-insights/numerical-balance.md:540-541`。

---

## 8. 结论与红线澄清建议

### 8.1 已守住的红线（给予肯定）

商业化方案在以下方面守住红线，红队无异议：

1. **明确禁止付费减免死亡数值惩罚**：combat_exp、potential、balance、技能等级均被列为禁止付费减免（commercialization.md:207-210、:232-233）；
2. **明确禁止顶级武功/装备售卖**：商业化潜力表把「顶级武功/装备售卖」列为禁止（commercialization.md:349-350）；
3. **复活点选择、跳迷宫等被判为便利**：方向正确，但需配套「全玩家可获取」或「订阅福利」限制；
4. **PowerModel 可替换**：把战斗公式交给题材包是正确边界，避免 engine 层做付费捷径。

### 8.2 需要重新定案的边界项目

红队建议对以下项目的商业化分类进行重新定案：

| 项目 | 当前商业化判定 | 红队建议 | 理由 |
|------|---------------|---------|------|
| 付费加速技能升级 | 边界安全 | **禁止**或仅限全玩家订阅福利 | 技能等级是数值红线（numerical-balance.md:419） |
| 付费保留 skill_map | 安全 | 改为订阅/全玩家福利 | 是 `skill_death_penalty()` 副作用的一部分 |
| 付费缩短昏迷苏醒时间 | 便利 | 仅限非 PvP 场景或全玩家福利 | PvP 中是生存能力加成 |
| 付费 PvP 保护期 | 边界安全 | **基础机制免费**，不得按次付费 | 否则免费玩家成为猎物 |
| 付费保留 shen/阵营 | 可保留 | 需限制为不影响门派/任务/战斗准入 | shen 影响 NPC 态度与 berserk（combatd.c:869-902） |
| 付费查看对手数值 | 安全 | 增加「不可查看低等级玩家」规则 | 避免霸凌辅助 |
| 付费坐骑 speed 加成 | 边界安全 | engine 必须强制拆分移动/战斗 speed | 否则直接越线 |

### 8.3 Engine 必须补的商业化基建（按优先级）

1. **新建 Effect 引擎**（优先级 P0）：`conditions.py` 不是 Effect 引擎，必须新建独立模块承载时效性 Effect，并带 `pack_id`/`creator_id`/`version`；
2. **资产归属字段**（P0）：`SkillData`、`ItemTemplateKey`、Effect handler、`LootTable` 追加 `pack_id`/`creator_id`/`version`；
3. **World.pack_id 与事件埋点**（P0）：所有战斗/死亡事件上下文携带 `pack_id`；
4. **双货币与账本**（P1）：`Currency` 增加 `currency_type`，新增 `LedgerEntry`；
5. **装备数值与双槽 schema**（P1）：`Equippable` 支持 `stat_prop`（数值，不可付费）与 `cosmetic`（外观，可付费），并接入战斗；
6. **注册表按 World 隔离**（P1）：`SKILLS`、`_SKILL_BEHAVIORS`、PowerModel 改为 per-World；
7. **`DeathPolicy` 分项惩罚**（P2）：把单一 `penalty_ratio` 扩展为分项配置，便于题材包声明且避免付费越线。

---

## 9. 关键证据索引

### LPC 源码证据
- `feature/skill.c:skill_death_penalty()` :121-147（死亡技能降级、skill_map 清空）
- `feature/skill.c:map_skill()` :42-58（skill_map 决定战斗动作）
- `adm/daemons/combatd.c:skill_power()` :288-333（立方缩放、 combat_exp、jingli_bonus）
- `adm/daemons/combatd.c:do_attack()` :636-641（combat_exp 防御衰减循环）
- `adm/daemons/combatd.c:fight()` :787-845（busy/昏迷触发 TYPE_QUICK）
- `adm/daemons/combatd.c:killer_reward()` :1027-1096（shen 调整、pker condition）
- `adm/daemons/combatd.c:start_berserk()` :869-902（shen 判定狂暴）
- `feature/condition.c:8,21-69,79-85`（时效 Effect 引擎）
- `d/death/road2.c:24-46`（地府迷宫 long_road）
- `d/death/gate.c:26-48`（地府入口清物品/清 condition）

### Engine 模块证据
- `engine/src/openmud/skills.py:36-53` SkillData（无归属字段）
- `engine/src/openmud/skills.py:54-56` SKILLS / _SKILL_BEHAVIORS 全局注册表
- `engine/src/openmud/conditions.py:1-22,92-142` 布尔求值器（非 Effect 引擎）
- `engine/src/openmud/components.py:270-274` Equippable 占位
- `engine/src/openmud/components.py:431` ItemTemplateKey
- `engine/src/openmud/components.py:650` Currency 单一 amount
- `engine/src/openmud/death_flow.py:77-86` DeathPolicy（单一 penalty_ratio）
- `engine/src/openmud/death_flow.py:85` unconscious_recovery_ticks
- `engine/src/openmud/death_flow.py:99-107` DeathContext（无 pack_id）
- `engine/src/openmud/combat.py:33-56` CombatContext、`:59-70` CombatRoundResult（无 pack_id）
- `engine/data/m2_mvp_scene.yaml:406-414` steel_blade（无数值字段）

### 调研文件证据
- `03-engine-insights/commercialization.md` §1.1-1.5、§3、§4、§5、§6
- `03-engine-insights/numerical-balance.md` §7、§8、§9
- `03-engine-insights/player-psychology.md` §2、§5、§6
- `03-engine-insights/creator-perspective.md` §2、§5
- `02-user-stories/operator-stories.md` US-W20、US-W22、US-W24、US-W25
- `06-engine-critique/engine-comparison.md` 模块 1、3、4、5、6
