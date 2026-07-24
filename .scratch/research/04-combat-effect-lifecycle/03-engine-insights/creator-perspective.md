# 创作者视角：战斗与效果生命周期簇可扩展性评估

> 角色：UGC 游戏专家。从题材包创作者视角审视「战斗 / Effect / 死亡」三系统的可扩展性：
> 配武功、挂 Effect、调数值、设死亡惩罚的工作流与痛点；机制暴露 vs 封装；规模对创作工具的要求；
> 武功/装备/Effect 作为题材包核心资产的可交易性；现有 engine（`skills.py` / `death_flow.py` /
> `combat.py` / `conditions.py`）对创作者友好度的影响。
>
> **证据基线**（一手盘点，非 brief 的估算值）：LPC `kungfu/condition/` 实有 **72** 个 condition
> daemon（非 brief 所写 ~30+）；`kungfu/skill/` 实有 **257** 个武功 `.c` + **27** 个 perform 子目录；
> `kungfu/class/` **19** 个门派目录 / **254** 个 `.c`（少林一派 60+ NPC 文件）；`inherit/weapon/`
> 15 类 + `inherit/armor/` 11 类；`d/death/` 地府区 **580 行 / 13 房间**。所有结论标注来源。

---

## 0. 一句话结论

LPC 的战斗/Effect/死亡内容创作是「**每个 Effect / 每招武功 / 每段死亡流程都写一个 .c daemon**」
的纯代码模式，门槛极高、规模爆炸、无校验。现有 engine 把「**纯数值招式**」与「**纯数据死亡策略**」
做成了声明式 YAML（创作者友好度跃升），但同时**完全缺失 LPC 最核心的三类创作者资产**——
时效性 Effect 引擎（毒/盲/牢/醉）、装备数值接入战斗、死亡叙事流程（地府/鬼魂/轮回）；
且 `conditions.py` 与 LPC `condition.c` 概念错位（布尔求值器 vs 时效 Effect 引擎），是当前最大的
创作者能力空洞。商业化上，武功/装备/Effect 正是题材包的核心可交易资产，缺这三块等于创作者
「卖不出差异化的战斗体验」。

---

## 1. 创作者工作流与痛点（LPC 现状）

### 1.1 配武功：数据与代码强耦合，每招一个 daemon

LPC 配一个武功的标准范式见 `kungfu/skill/18-zhang.c`（降龙十八掌）：

- **数据层**（`action` mapping 数组，`:52-218`）：每招一个 mapping，含 `action`（文案）、
  `dodge`/`parry`/`force`/`damage`/`lvl`/`skill_name`/`damage_type`/`weapon`。18 招 = 18 条纯数据，
  创作者理论上只需填表。
- **代码层**（`query_action(me, weapon)` `:241-291`）：但实际选招不是纯查表——`query_action`
  内嵌条件分支：若 `me->query_skill_mapped("force")=="huntian-qigong"` 且 `me->query_temp("sanhui")`
  在 1-3 之间，返回三悔连击 mapping 并挂 `post_action: (: sanhui :)` 闭包；否则按技能等级 /
  内力 / 加力 (`jiali`) 随机触发不同威力档。**「亢龙有悔」一招有 4 套不同的数值与文案分支**。
- **学习/练习钩子**（`valid_learn` `:222-231`、`practice_skill` `:293-302`、`valid_enable` `:220`、
  `query_skill_name` `:233-239`）：全是 LPC 函数，`valid_learn` 里硬编码「必须空手」「混天气功≥20」
  「max_neili≥100」三条门槏。
- **绝技 perform**（`perform_action_file` `:304-307`）：`__DIR__"18-zhang/" + action` 指向子目录，
  每个绝技又一个独立 `.c`。

**痛点**：
1. 创作者无法只填表完成一个武功——任何带连击/条件触发/资源消耗的招式都强制写 LPC 代码
   （`18-zhang.c:253-291` 的 `query_action` 分支）。
2. 257 个武功 × 平均 N 招 = 数千条 action 数据散落在 257 个 `.c` 里，**无统一 schema、无校验、
   无预览**。`force`/`damage`/`lvl` 的取值范围、缩放关系全凭作者手感（见 §4 数值）。
3. 招式文案 `$N`/`$n`/`$l`/`$w` 占位符替换逻辑硬编码在 `s_combatd.c:620-633`
   （`replace_string(result, "$l", limb)` 等），创作者必须记忆这套占位符协议，无文档校验。
4. `post_action` 闭包（`18-zhang.c:264` 的 `(: sanhui :)`）能改战斗状态（删 temp、连击计数），
   是无约束的任意代码副作用，创作者易写出破坏战斗轮次的逻辑。

### 1.2 挂 Effect：每个状态一个独立 daemon，副作用任意

LPC Effect 引擎见 `feature/condition.c`（113 行）：

- `apply_condition(cnd, info)` / `update_condition()` 由 `heart_beat` 驱动（`:21-69`）。
- 每个 condition 是 `CONDITION_D(cnd)` 加载的**独立 daemon**，实现 `update_condition(me, duration)`
  返回 `CND_CONTINUE` 标志续命，返回 0 即过期移除（`:62-63`）。
- `info` 是 `mixed`（任意类型），由各 daemon 自定义（`condition.c:79-85`）。

72 个 condition daemon 的实际形态（证据抽样）：

| Condition | 文件 | 副作用（创作者必须写的代码） |
|-----------|------|------------------------------|
| 西域灵蛇毒 | `kungfu/condition/bt_poison.c:7-42` | `receive_wound("jing",damage/2)` + `receive_damage("jingli",damage/2)`；duration 自减 `5+skill("poison")/10`（玩家毒功越高解得越快）；按 `eff_jing` 三段不同文案 |
| 寒冰绵掌阴毒 | `kungfu/condition/hanbing_damage.c:8-31` | `receive_damage("qi",(duration/2)+20)` + `receive_wound("jing",...)`；duration -1 |
| 嵌入暗器 | `kungfu/condition/embedded.c:9-33` | `receive_wound("qi",3)`；**直接调 `COMMAND_DIR"std/remove"->do_remove(me,ob)` 自动拔甲**（跨系统副作用） |
| 城市牢狱 | `kungfu/condition/city_jail.c:6-24` | 过期时 `me->move("/d/city/yamen")` + `set("startroom",...)`（跨区域传送 + 改出生点） |

**痛点**：
1. **「挂 Effect」=「写一个完整 daemon」**：不是填「每 tick 掉 X 点血、持续 Y tick」，而是写一个
   有 `update_condition` 入口、自己调 `receive_damage`/`receive_wound`/`move`/`apply_condition`
   自递减的 LPC 对象。72 个 daemon 即 72 份独立逻辑，**无通用 Effect 基类约束副作用边界**。
2. 副作用边界失控：`embedded.c:23` 直接调命令层 `remove` daemon 拔甲；`city_jail.c:9` 直接 `move`
   玩家跨区。创作者无法在「只声明伤害」与「触发跨系统行为」之间做安全的分级选择——只有「不写」
   或「写任意代码」两档。
3. duration 语义不统一：`bt_poison.c:36-38` 按 `skill("poison")` 缩短；`hanbing_damage.c:26` 纯 -1；
   `embedded.c:29` -1。解毒机制各自为政，创作者无法统一表达「某药解某类毒」。
4. `condition.c:44-51` 注释承认：daemon 加载失败会污染 heart_beat 日志，引擎只能把坏 condition
   静默删除——**创作者写错 Effect 不会报错，只会「静默失效」**，调试极难。

### 1.3 调数值：公式硬编码、无预览、无平衡校验

战斗数值全部硬编码在 `adm/daemons/s_combatd.c` 的 `do_attack`（`:294-679`）与 `skill_power`
（`:212-245`）：

- `skill_power`：`power = (level^3)/3`；攻击力 `(power+combat_exp)/30 * str/100 * jingli_bonus`
  （`:237-244`）；`jingli_bonus = 50 + jingli*50/max_jingli`，上限 150（`:231-232`）。
- 命中：`random(ap+dp) < dp` 闪避（`:377`）；`random(ap+pp) < pp` 招架（`:422`）。
- 伤害：`damage = apply/damage` + `action["damage"]/10*damage/30` + `action["force"]/10*damage_bonus/100`
  + 多级 `hit_ob` 钩子加成（`:451-535`）。
- `damage_msg`（`:71-167`）：9 类伤害文案（擦伤/割伤/劈伤/刺伤/跌伤/鞭伤/咬伤/瘀伤/内伤），
  每类 5-6 档伤害区间文案，**全硬编码在 daemon 里**，创作者无法在题材包里加新伤害类型或调阈值。

**痛点**：
1. 创作者改一个系数（如 `level^3` 改 `level^2.5`）要直接改 `s_combatd.c` 核心 daemon——
   **没有「题材包级数值覆写」机制**，所有题材包共用同一套硬编码公式。
2. 招式 `force`/`damage`/`lvl` 的合理范围无任何校验：`18-zhang.c` 里 `force` 从 330 到 650、
   `damage` 从 20 到 120，缩放关系靠作者经验，无预览工具告诉你「这招在 100 级角色身上打多少血」。
3. `death_penalty`（`s_combatd.c:874-907`）与 `killer_reward`（`:910-972`）也全硬编码：
   战斗经验/潜能/善恶/银两/技能惩罚的具体比例写死在 daemon 里，创作者无法按题材调死亡代价。

### 1.4 设死亡惩罚与复活：手搓地府叙事区

死亡流程横跨 `feature/damage.c` + `d/death/` 13 房间 580 行：

- `die()`（`damage.c:152-253`）：`no_death` 房 -> `unconcious()`；否则 `clear_condition` ->
  `COMBAT_D->death_penalty` -> `killer_reward` -> `make_corpse` -> `ghost=1` ->
  `move(DEATH_ROOM)` -> `DEATH_ROOM->start_death()`（`:226-248`）。
- 地府叙事（`d/death/`）：
  - `gate.c`（鬼门关）：`init()` 销毁全部 inventory + `clear_condition()`（`:30-47`）；
  - `gateway.c`（酆都城门）：`valid_leave` 单向封锁回头路（`:28-37`）；
  - `inn1.c`（小店）：通过 `ask [自己id] about 回家` 解谜触发 `reincarnate()` + `move("/d/city/wumiao")`
    （`:51-83`）——**复活是一个 ask 谜题**，不是数据配置；
  - `hell.c`/`death.c`：`block_cmd` 命令白名单（只许 say/tell/look/quit/suicide/goto）。
- `reincarnate()`（`damage.c:255-264`）：把 jing/qi/eff_jing/eff_qi/jingli/neili 全拉满。

**痛点**：
1. 死亡叙事=手搓一个多房间区域：每个房间 `init()`/`valid_leave`/`block_cmd` 都是 LPC 代码，
   创作者要复刻「死后走地府」体验只能照抄 580 行或全删。**无「死亡流程模板」可言**。
2. `death_penalty`（`s_combatd.c:874-907`）惩罚项混杂：combat_exp / shen / behavior_exp /
  potential / balance / skill（`skill_death_penalty`）/ death_times / vendetta / thief，
  全是武侠题材专属字段，**题材无关的引擎不该承载这些**，但 LPC 里它们焊死在 daemon。
3. `killer_reward`（`:910-972`）硬编码 PKS/MKS 计数、`pker` condition（PK 追杀）、`vendetta` 世仇、
  在城市杀人给 killer condition 100 tick——**PvP 惩罚逻辑不可配置**。

---

## 2. 引擎对照：现有 engine 对创作者友好度评估

> 仅评估，不深读实现。每条标注 engine 模块 + 行号/类名 与 LPC 证据的偏差。

### 2.1 `skills.py`（317 行）——友好度：数据层高、行为层缺口大

**已做对**：
- `SkillData` / `SkillMove` 是 `@dataclass(frozen=True)` 纯数据（`skills.py:23-53`），
  `load_skills_from_mapping`（`:151-282`）解析 YAML `skills:` 段，创作者**填表即可定义招式数值**。
  实证见 `engine/data/m2_mvp_scene.yaml:624-652`：`luohan_quan` 用 `type/level_req/learn_condition
  (gte con>=10)/practice(neili,jingli,exp)/exp_thresholds/moves(name,force,dodge,damage_type,damage)`
  纯 YAML 声明——这是相对 LPC `18-zhang.c` 的巨大进步，创作者不用写代码就能配一招。
- `learn_condition` 复用 `conditions.py` 的受限 AST（`gte`/`field`/`value`），门槏声明式可表达。

**缺口（创作者痛点转移点）**：
1. **动态选招无法表达**：LPC `18-zhang.c:241-291` 的 `query_action` 条件连击（sanhui 三悔、
   按内力/加力分档）在 engine 里**无对应声明面**——`SkillMove` 只有静态 force/dodge/damage，
   没有「当 force 技能==X 且内力>Y 时替换为 Z 招」的条件结构。创作者要做连击/蓄力/状态触发招
   只能落代码（见下条）。
2. **行为钩子只剩 3 个且约束更紧**：`SkillBehavior` Protocol 只有 `hit_ob`/`hit_by`/`post_action`
   （`skills.py:59-67`）。对照 LPC `18-zhang.c` 的 `valid_learn`/`valid_enable`/`practice_skill`/
   `query_skill_name`/`perform_action_file` 五类钩子 + `query_parry_msg`（招架文案）+ `post_action`
   闭包——engine 缺学习校验钩子、练习消耗钩子、绝技 perform 概念、招架反击文案钩子。
3. **`post_action` 不许改伤害**：`combat.py:274` 明确「不得改本回合伤害数值」，而 LPC
   `18-zhang.c:316-320` 的 `sanhui` 正是靠 `post_action` 改战斗状态。engine 把「行为钩子」收窄为
   「只读播报」，创作者无法用钩子实现连击/状态附加，被迫把这些塞进 `hit_ob` 或写 PowerModel。
4. **绝技 perform 无概念**：LPC 有 27 个 perform 子目录（`kungfu/skill/*/`），engine 无
   `perform`/绝技声明面，创作者的「大招」无处安放。
5. **行为注册是 Python 代码**：`DemoPoisonStrikeBehavior`/`SilkRopeCaptureBehavior`（`skills.py:87-145`）
   是 Python 类，经 `register_skill_behavior`（`:70-72`）注册。**纯 YAML 创作者做不出毒击/擒拿**，
   必须写 Python——这与「M3 包外声明式内容包」目标（CLAUDE.md 架构不变量 5）存在张力。

### 2.2 `death_flow.py`（446 行）——友好度：数据层好、叙事层全缺

**已做对**：
- `DeathPolicy`（`death_flow.py:77-86`）纯数据：`penalty_ratio`/`revive_room_key`/`drop_items`/
  `drop_currency`/`unconscious_recovery_ticks`/`recovery_vitals_ratio`，经 `parse_death_policy`
  （`:118-137`）从 `death_policy:` YAML 段加载。`m2_mvp_scene.yaml:665-667` 实证：两行 YAML
  即可声明死亡策略——相对 LPC `s_combatd.c:874-907` 硬编码是巨大进步。
- `LootTable`（`:89-97`）纯数据 + `parse_loot_table`（`:140-160`），NPC `loot:` 段声明掉落
  （`m2_mvp_scene.yaml:603-609`：`wild_bandit` 掉 `currency:[15,15]` + `items:[bandit_purse]` +
  `kill_exp:10`）。
- 昏迷苏醒是 tick 计数（`:411-429`），非 LPC 的 `call_out("revive", random(100-con)+30)`
  随机延迟——更可预测、更易调参。

**缺口（创作者无法表达的死亡内容）**：
1. **无鬼魂态 / 无地府叙事区**：LPC `die()` 设 `ghost=1` + `move(DEATH_ROOM)` + `start_death`
   （`damage.c:246-248`），玩家变鬼走 13 房间地府解谜复活（`d/death/inn1.c:51-83` 的 ask 谜题）。
   engine `_execute_player_death`（`death_flow.py:208-270`）直接掉物 + 惩罚 + 复活到 `revive_room`
   ——**无 ghost 组件、无死亡区域流程、无轮回叙事**。`death.py` 只有 `DeathState` 三态枚举
   （ALIVE/UNCONSCIOUS/DEAD，`death.py` 全 46 行），无 LPC `is_ghost()` 等价。
2. **无 clear_condition**：LPC `die()` 调 `clear_condition()`（`damage.c:184`）清空所有 Effect；
   engine 无 Effect 引擎（见 §2.4），死亡无 Effect 可清。
3. **无 killer_reward / 无 PK 惩罚**：LPC `killer_reward`（`s_combatd.c:910-972`）的 PKS/MKS 计数、
   pker 追杀 condition、vendetta 世仇、城市杀人标记——engine 全无。PvP 题材包创作者无法配置
   「杀人后果」。
4. **无尸体**：LPC `make_corpse`（`damage.c:227`）生成尸体物件；engine 无尸体概念，
   掉落只走 `_drop_inventory_to_room`（`death_flow.py:283-288`）。
5. **惩罚维度单一**：engine `DeathPolicy` 只有 `penalty_ratio`（统一比例扣货币 + 技能经验，
   `:291-305`）。LPC 死亡惩罚是分项的（combat_exp / shen / behavior_exp / potential / balance /
   skill 各自比例，`s_combatd.c:880-904`）。题材包要表达「死一次掉 10% 经验但不掉钱」或
   「死亡加善恶惩罚」无法做到——只能调一个 `penalty_ratio`。
6. **`no_death` 区语义弱化**：LPC `no_death` 房把死亡降级为昏迷（`damage.c:159-177`）；
   engine `NoDeathZone` 组件（经 `next_death_state` 的 `in_no_death_zone` 参数）也降级为昏迷
   （`death_flow.py:194-207`），这点对齐了，但创作者无法配置「安全区里死亡仍扣 X%」这类中间态。

### 2.3 `combat.py`（291 行）——友好度：PowerModel 是亮点，钩子链缺口大

**已做对**：
- `PowerModel` Protocol（`combat.py:72-83`）：`attack_power`/`defense_power`/`parry_power`/
  `base_damage` 四方法，`attach_power_model`（`:119-124`）挂到 world。**题材包可整体替换战斗公式**
  ——这是相对 LPC `s_combatd.c:skill_power` 硬编码 `(level^3)/3` 的关键改进，创作者能定义自己的
  题材数值曲线（仙侠 / 科幻 / 校园各用不同 PowerModel）。
- `DefaultWuxiaPowerModel`（`:85-113`）作自洽默认（AP=force×(1+str×0.02)，DP=dex+move.dodge）。
- `resolve_attack` 七步管线（`:132-216`）结构清晰，`hit_ob`/`hit_by`/`post_action` 钩子
  （`:236-278`）接入 `SkillBehavior`。

**缺口**：
1. **无多级钩子链**：LPC `do_attack` 有 6 层 `hit_ob`/`hit_by` 串联——force 技能、martial 技能、
   weapon、me 本人、armor、dodge 技能各一层（`s_combatd.c:471-569`）。engine 只有一层
   `SkillBehavior.hit_ob`（招式所属技能）。**创作者无法让「装备也参与命中改伤害」**——weapon
   的 `hit_ob`（如 `inherit/weapon/sword.c:24-67` 削减对方护甲耐久）无接入点。
2. **无装备数值接入战斗**：`combat_system.py:46` 用 `_DEFAULT_MOVE = CombatMoveSnapshot(name="拳头",
   force=5, ...)`，武器不喂招式数值；`Equippable` 组件（`components.py:270-274`）是「占位（18 号票）。
   M1 不实现 wield/wear」；`m2_mvp_scene.yaml:406-414` 的 `steel_blade` 只有 `tags:[weapon,edged]`，
   **无 `weapon_prop/damage`**。创作者配一把「伤害 30 的剑」当前完全做不到——剑是纯文案物件。
3. **无伤害类型文案表**：LPC `damage_msg`（`s_combatd.c:71-167`）按 9 类伤害类型给文案；
   engine `CombatRoundResult.message_fragments`（`combat.py:60-69`）只是「命中，造成 N 点伤害」
   字符串拼接，无按 damage_type 分级文案。创作者的「劈伤」「内伤」无文案差异。
4. **exp_gain / riposte 是 no-op**（`combat.py:263-270`）：LPC 命中给 combat_exp + improve_skill
   （`s_combatd.c:595-616`）、未命中给 riposte 反击（`:664-678`）——engine 占位未接线，
   创作者的「招架反击」「命中成长」无配置面。

### 2.4 `conditions.py`（257 行）——友好度：概念错位，Effect 引擎完全缺失

**这是当前最大的创作者能力空洞**（brief 已标注，此处给出证据）：

- `conditions.py` 是**通用布尔表达式求值器**：`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not`
  五种 frozen 节点（`:92-142`），`evaluate` 纯函数只读 `ConditionContext` 返回 bool（`:170-176`）。
  它的用途是「门槏 / 物品使用限制 / NPC 行为条件」三类动态规则的**共同条件子语言**（模块
  docstring `:1-8` 明示），供 `skills.py` 的 `learn_condition`（`m2_mvp_scene.yaml:628-631` 的
  `gte: con>=10`）和 Nature / EntityGate 复用。
- LPC `feature/condition.c` 是**时效性 Effect 引擎**：`apply_condition(cnd, info)`（`:79-85`）+
  `update_condition()` 由 heart_beat 驱动（`:21-69`）+ 每个 condition 是独立 daemon 带
  `receive_damage`/`move`/`apply_condition` 自递减等**副作用**。

**两者同名不同物**。engine 把 `conditions.py` 这个名字用在了布尔求值上，导致 LPC 的 72 个
Effect（毒/盲/牢/醉/嵌入/包扎/孕/睡/笑/杀手追杀……）**在 engine 里没有任何对应抽象**——
grep 确认 engine 中无 `apply_condition`/`update_condition`/`TimedEffect`/`tick_condition`
（仅 `events.py`/`tick.py`/`components.py`/`commands.py` 因泛词命中）。

**对创作者的后果**：
- 创作者想配「中蛇毒每 tick 掉 5 点精、持续 20 tick、毒功越高解得越快」（`bt_poison.c`）
  ——engine **无任何声明面**，既无 YAML Effect 段，也无 Effect 钩子协议。唯一能做的是写
  `SkillBehavior.hit_ob` 在命中时直接扣血（一次性，非持续），完全不是 LPC condition 语义。
- 创作者想配「中暗器嵌入，每 tick 掉血且自动拔甲」（`embedded.c`）、「坐牢 100 tick 后传送
  到衙门」（`city_jail.c`）——engine 连「跨 tick 持续副作用」的载体都没有。
- **这是题材包差异化的核心战场**：武侠题材的「毒/点穴/内伤」、仙侠的「灼烧/冰冻/封印」、
  科幻的「中毒/辐射/感染」全靠 Effect 引擎。缺它，所有题材包的战斗体验趋同。

### 2.5 装备——友好度：基本未建

- `Equippable` 组件是占位（`components.py:270-274`，「M1 不实现 wield/wear」）。
- 场景物品 `steel_blade` 无任何战斗数值（`m2_mvp_scene.yaml:406-414`）。
- 对照 LPC `feature/equip.c`：`wear()`/`wield()` 把 `armor_prop`/`weapon_prop` 堆叠进
  `apply/*` 临时加成（`:7-107`）；`inherit/weapon/sword.c:24-67` 的 weapon `hit_ob` 还能削减
  对方护甲耐久、改名「破X」、贬值。**engine 创作者当前配不出「有数值的装备」**。

---

## 3. 机制暴露 vs 封装建议

按「题材包创作者应直接配 / 应受限扩展 / 引擎应封装」三档分层：

### 3.1 应暴露给创作者（声明式 YAML + 受限钩子）

| 机制 | 暴露形态 | 证据依据 |
|------|----------|----------|
| 招式纯数值 | YAML `moves:` 段（force/dodge/damage/damage_type/lvl/text） | engine 已做（`skills.py:23-33` + `m2_mvp_scene.yaml:639-644`）；LPC `action` 数组同构（`18-zhang.c:52-218`） |
| 学习/练习门槏 | 受限 AST（`learn_condition` + `practice` 段） | engine 已做（`skills.py:194-221`）；LPC `valid_learn` 是代码（`18-zhang.c:222-231`） |
| 死亡策略 | YAML `death_policy:`（penalty_ratio/revive_room/drop_*） | engine 已做（`death_flow.py:77-86`）；LPC 硬编码（`s_combatd.c:874-907`） |
| NPC 掉落 | YAML `loot:` 段 | engine 已做（`death_flow.py:89-97`）；LPC 无统一表 |
| 战斗公式 | `PowerModel` 协议（整体替换） | engine 已做（`combat.py:72-83`）；LPC 硬编码（`s_combatd.c:212-245`） |
| Effect 声明（待建） | YAML `effects:` 段（type/duration/tick_damage/tick_message/expire_action 白名单） | engine 缺；LPC 72 daemon 各自为政（`kungfu/condition/`） |
| 装备数值（待建） | YAML `weapon_prop:`/`armor_prop:` | engine 缺；LPC `equip.c` 堆叠 model 可参考 |

### 3.2 应受限扩展（受限 Python 钩子，非任意代码）

| 机制 | 受限形态 | 理由 |
|------|----------|------|
| 招式行为钩子 | `SkillBehavior` 协议（扩展到 `valid_learn`/`practice`/`perform`） | engine 当前 3 钩子太少（`skills.py:59-67`）；LPC 5+ 钩子（`18-zhang.c`），但应收敛副作用边界 |
| Effect 跨系统副作用 | 白名单 `expire_action`（`move_to_room`/`deal_damage`/`clear_effect` 枚举）而非任意函数 | LPC `embedded.c:23` 调 remove daemon、`city_jail.c:9` 调 move 是失控先例 |
| 死亡叙事流程 | 房间钩子声明（`on_enter_ghost`/`on_reincarnate`）+ 受限 `block_cmd` 白名单 | LPC 13 房间全代码（`d/death/`），应给「死亡流程模板」 |

### 3.3 引擎应封装（题材无关，不暴露给创作者）

- 三类伤害原子（jing/qi/jingli）的 `receive_damage`/`receive_wound` 内部实现（LPC
  `damage.c:13-66`）——创作者只配「掉什么」，不配「怎么扣上限」。
- 命中/闪避/招架的 `random(ap+dp)<dp` 概率内核（`s_combatd.c:377,422`）——`PowerModel`
  只暴露 power 计算，不暴露判定算法。
- `heart_beat` / tick 驱动调度（LPC `condition.c:21` 注释「costs heart beat evaluation time」）——
  创作者只声明 Effect 的 tick 行为，不接触调度。
- 战斗事件广播（`combat_system.py` 的 `ON_COMBAT_ROUND` 等事件，`combat_system.py:事件常量`）——
  创作者订阅事件，不改事件管线。
- 武侠题材专属字段（shen 善恶 / behavior_exp / vendetta 世仇 / PKS / death_times）——
  这些属题材包数据，引擎核心不该承载（LPC `death_penalty` 把它们焊死在 `s_combatd.c:884-899`
  是反例）。

---

## 4. 规模对创作工具的要求

72 Effect + 257 武功 + 19 门派（少林一派 60+ NPC）的规模，对创作工具提出硬要求：

### 4.1 Effect 编辑器（当前零工具）

- 72 个 LPC condition daemon 无统一 schema：`info` 是 `mixed`（`condition.c:79-85`），duration
  语义各自定义（`bt_poison.c:36` 按 skill 缩、`hanbing_damage.c:26` 纯 -1、`embedded.c:29` -1）。
- **要求**：声明式 Effect schema（type / duration / per-tick 伤害 / per-tick 文案 / 到期动作）+
  可视化编辑器，让创作者像填表一样造毒/造灼烧/造冰冻，而非写 daemon。
- **要求**：Effect 互斥/覆盖规则的可配置（LPC `apply_condition` 直接覆盖无检查，`condition.c:79-85`
  注释明示「不查重，由 giver 负责」），工具应可视化 Effect 栈。

### 4.2 数值预览（当前零预览）

- 257 武功的 `force`/`damage`/`lvl` 缩放无校验：`18-zhang.c` force 330-650、damage 20-120，
  配合 `s_combatd.c:486-491` 的 `action["force"]/10*damage_bonus/100` 公式，创作者无法预知
  「100 级角色亢龙有悔打多少血」。
- **要求**：战斗数值沙盒——输入角色属性 + 招式，输出期望伤害 / 命中率 / 击杀回合数。
  `PowerModel` 协议（`combat.py:72-83`）已为此留了接口，可做 dry-run 求值器。

### 4.3 平衡校验（当前零校验）

- 同档 `lvl` 招式跨武功伤害差异巨大，无自动化比对。`death_penalty` 惩罚比例（`s_combatd.c:880-904`）
  全靠手调。
- **要求**：题材包加载时跑「招式 DPS 曲线」「Effect 总伤期望」「死亡惩罚相对经验占比」校验，
  超阈值告警（参考数值平衡专家与数值风险红队的输出）。

### 4.4 门派/NPC 批量管理（少林 60+ NPC）

- `kungfu/class/shaolin/` 60+ NPC 文件（cheng-*/dao-*/du-*/hui-*/qing-*/xuan-*）+ `auto_perform.h`
  + `.h` 头——批量分配技能给 NPC 是体力活。
- **要求**：门派=技能池声明（engine `factions:` 段已做，`m2_mvp_scene.yaml:653-664` 的
  `skill_pool`/`map_skill`），NPC 按门派继承技能池，而非逐个指派。

---

## 5. 创作者经济视角：武功/装备/Effect 作为题材包核心资产

CLAUDE.md 架构不变量 6 列了商业化支撑点（MVP 不要求实现，但留位置）：货币/账本抽象、
题材包资产元数据（创作者归属 + 版本溯源）、消费/参与度埋点（打点到题材包 ID）、世界实例隔离。
承载扩展靠「题材包数量横向扩展」。本节评估战斗资产在此模型下的可交易性。

### 5.1 武功招式 = 题材包的核心差异化资产

- 257 武功 + 19 门派是《侠客行》题材包的核心内容壁垒。新引擎「题材无关」意味着每个题材包
  （武侠/仙侠/科幻/校园）都要有自己的「武功集」——武功是**题材包最有价值的可交易内容**。
- 当前 engine `skills.py` 的 YAML 声明面（`m2_mvp_scene.yaml:624-652`）让武功可作为**题材包
  内声明式资产**打包分发，符合「包外声明式内容包」目标（架构不变量 5）。**但行为钩子仍是
  Python 代码**（`DemoPoisonStrikeBehavior` 等，`skills.py:87-145`），意味着带特殊效果的武功
  无法纯声明式分发——这是 UGC 创作者生态的障碍（CLAUDE.md 明确「UGC 脚本用受限 Python 非
  WASM」，但受限 Python 仍是代码门槛）。
- **建议**：题材包资产元数据应记录每条武功的创作者归属 + 版本（架构不变量 6），支持武功
  作为「资产」在创作者间引用/组合（A 题材包引用 B 题材包的某招）。当前 `SkillData` 无
  `source_pack`/`author`/`version` 字段。

### 5.2 装备 = 可付费外观 + 数值双轨（pay-to-win 红线）

- LPC 装备是数值件（`equip.c` 堆 prop）+ weapon `hit_ob` 特效（`sword.c:24-67` 削甲）。
- 商业化上装备天然分两轨：**数值件**（影响战斗，必须可免费获取，pay-to-win 红线）与
  **外观件**（纯文案/标签，可付费）。CLAUDE.md 不 pay-to-win 约束要求引擎能区分「装备的
  数值部分」与「外观部分」。
- 当前 engine 装备是纯 `tags`（`m2_mvp_scene.yaml:411-414`），无数值也无外观区分——**未来
  做装备商业化时，`Equippable` 占位（`components.py:270-274`）需明确分 `stat_prop`（数值，
  不付费）与 `cosmetic`（外观，可付费）两槽**。
- 消费/参与度埋点（架构不变量 6）应能打点到「玩家用了哪个题材包的哪把武器」——需要装备
  带题材包 ID 元数据，当前无。

### 5.3 Effect = 题材包的「玩法 DNA」，最强差异化但最难交易

- Effect 决定题材包战斗手感（武侠的毒/点穴 vs 仙侠的灼烧/封印 vs 科幻的辐射/感染）。
  **缺 Effect 引擎（§2.4），题材包间战斗体验趋同，商业化「横向扩展」卖点被削弱**。
- Effect 比武功更难纯声明式分发：LPC condition 带 `move`/拔甲等跨系统副作用（`embedded.c`/
  `city_jail.c`），受限 Effect schema（§3.2）需谨慎设计白名单，否则要么封死创意、要么放任
  副作用失控。
- **建议**：Effect 应作为题材包资产带版本溯源（架构不变量 6），并支持「A 题材包的毒被 B
  题材包的药解」这类跨包引用——需要 Effect type 的全局命名空间 + 解毒映射声明。

### 5.4 死亡惩罚 = 商业化的敏感区

- LPC `death_penalty`（`s_combatd.c:874-907`）扣 combat_exp/potential/balance/skill——
  **直接卖「减免死亡惩罚」就是 pay-to-win**，踩 CLAUDE.md 红线。
- engine `DeathPolicy.penalty_ratio`（`death_flow.py:81`）是统一比例，商业化上更安全
  （不易做定向减免），但也少了「死亡保险」「轮回加速」等可付费的合规设计点。
- **建议**：商业化支撑点（架构不变量 6）的「货币/账本抽象」应把死亡惩罚货币与战斗货币
  分账，允许「用不可付费货币买一次轮回保护」而非「付费免惩罚」。

---

## 6. 结论与遗留

1. **engine 的声明式数据层是正确方向**：`SkillData`/`DeathPolicy`/`LootTable`/`PowerModel`
   把 LPC 焊死的数值/策略变成了 YAML，创作者友好度显著提升。这一层应继续扩大覆盖（Effect、
   装备数值、伤害文案表）。
2. **三类核心创作者资产缺失是最大风险**：时效性 Effect 引擎（`conditions.py` 概念错位）、
   装备数值接入战斗（`Equippable` 占位）、死亡叙事流程（无 ghost/地府）。缺这三块，题材包
   创作者「配不出有差异的战斗体验」，商业化「横向扩展」卖点空心化。
3. **行为钩子应在「声明式优先 + 受限代码兜底」间分层**：纯数值走 YAML（多数招式），
   复杂行为走受限 `SkillBehavior`/`EffectBehavior` 协议（少数大招/特殊 Effect），任意 LPC 代码
   （LPC `embedded.c` 调 remove daemon 那种）应被白名单封死。
4. **创作工具是规模化前提**：72 Effect + 257 武功的规模，没有 Effect 编辑器、数值预览、
   平衡校验，创作者会重蹈 LPC「72 个 daemon 各写各的」的覆辙——只是从 LPC 代码换成 YAML。
5. **商业化元数据需前置留位**：武功/装备/Effect 作为题材包资产，`SkillData`/`LootTable`
   等数据类应预留 `source_pack`/`author`/`version` 字段（架构不变量 6 的「资产元数据」），
   即便 MVP 不实现也避免后续破坏性改 schema。

**遗留（超出本角色范围，交由其他角色）**：
- Effect 引擎的具体抽象（交引擎架构师 A/B，`03-engine-insights/abstraction-options.md`/
  `ugc-surface.md`）。
- 数值平衡的具体阈值与公式（交数值平衡专家，`03-engine-insights/numerical-balance.md`）。
- engine `conditions.py` 重命名/重构决策（交 engine 批判对照员，`06-engine-critique/`）。
- 商业化付费点设计（交商业化专家，`03-engine-insights/commercialization.md`）。
