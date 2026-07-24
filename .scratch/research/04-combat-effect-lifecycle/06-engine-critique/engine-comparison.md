# engine 批判对照报告：战斗与效果生命周期簇

> 06-engine-critique 层产出。逐项对照 `engine/src/openmud/` 6 模块与 LPC 一手源码，标注偏差与遗漏。
> **LPC 是唯一真相源**；engine 模块仅作批判对照对象，不作反向脑补来源。
> 每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。

---

## 模块 1：combat.py vs feature/attack.c + feature/damage.c + adm/daemons/s_combatd.c

### 1.1 命中/伤害结算管线对齐度

**LPC 设计**（`s_combatd.c:do_attack` :294-633）：
- 步骤 (0) 选技能 `attack_skill`（weapon->skill_type / prepare / unarmed）→ (1) `reset_action()` 取 `action` mapping（含 force/damage/dodge/action 文案）→ (2) `ap = skill_power(me, attack_skill, ATTACK)`、`dp = skill_power(victim, "dodge", DEFENSE)`，`is_busy()` 时 `dp/=3` → (3) `random(ap+dp) < dp` 闪避 → (4) `pp = skill_power(victim,"parry",DEFENSE)`（持械对徒手 `pp*=2`，徒手对持械 `pp=0`），`is_busy()` 时 `pp/=2`，`random(ap+pp)<pp` 招架 → (5) 命中：`damage = apply/damage`，叠加 `damage_bonus`（str + force 技能 hit_ob + martial 技能 hit_ob + weapon hit_ob + jiali + jiajin）→ `defense_factor=combat_exp` 概率削减 → armor `hit_by` 削减 → (6) `receive_damage("qi", damage, me)` → 概率 `receive_wound("qi", damage-armor, me)` → (7) 经验/技能成长。
- 关键：命中后 `hit_ob` 有 **4 个独立钩子源**：force 技能 `SKILL_D(force_skill)->hit_ob(me,victim,damage_bonus,jiali)`（:473）、martial 技能 `SKILL_D(martial_skill)->hit_ob(me,victim,damage_bonus)`（:501）、weapon `weapon->hit_ob(me,victim,damage_bonus)`（:508）或徒手 `me->hit_ob(me,victim,damage_bonus)`（:512）；`hit_by` 有 **2 个源**：特殊 armor `foo->hit_by(me,victim,damage,weapon)`（:550）、特殊 dodge 技能 `SKILL_D(dodge_skill)->hit_by(me,victim,damage)`（:562）。返回值统一支持 `int`（改伤害）/`string`（追加文案）/`mapping`（result+damage）三态。
- 三类伤害（`feature/damage.c:receive_damage` :13-37 / `receive_wound` :39-66）：`jing` 精 / `qi` 气 / `jingli` 精力（wound 仅 jing/qi）。`receive_damage` 改 `current`，`receive_wound` 改 `eff_` 上限并连带压 `current`。`set_temp("last_damage_from", who)` 记录伤害来源。

**engine 现状**（`combat.py:resolve_attack` :132-216）：
- 七步：选技能/取招式（退化为读 `ctx.move`）→ 算 `ap=attack_power` / `dp=defense_power` / `pp=parry_power` → dodge `_roll_opposed(rng,ap,dp)`（:157）→ parry `_roll_opposed(rng,ap,pp)`（:169）→ 算伤害 `base_damage` + `hit_ob` + `hit_by` + `post_action` → inflict 报告 → exp+riposte（二者 no-op，:195-196）。
- `DefaultWuxiaPowerModel`（:85-113）：`AP = force × (1 + str × str_factor)`、`DP = defender_dex × dex_factor + move.dodge`、`PP = DP`（招架与闪避共用同一防御势）、`base_damage = move.damage 或 AP 同公式`。
- `hit_ob` 钩子（`_invoke_hit_ob` :236-252）：单一来源 `get_skill_behavior(skill_id).hit_ob(ctx, damage)`，返回 `int`（替换伤害）/`str`（追加文案）/`None`。`hit_by`（:255-260）：同一 `SkillBehavior.hit_by(ctx)` 返回 `str|None`。`post_action`（:273-278）只追加文案，**不得改伤害**。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 1.1a | **负面遗漏**：三类伤害只剩一类 | `damage.c:receive_damage` 支持 `jing`/`qi`/`jingli`，`receive_wound` 支持 `jing`/`qi`；`s_combatd.c:576` 命中只打 `qi` 但 wound 也打 `qi`，另 force 技能/condition 可打 jing/jingli | `combat.py:191` `remaining = ctx.defender_qi_current - damage`；`combat_system.py:apply_combat_result:240` 只写 `vitals.qi_current` | engine 战斗**只扣 qi**。LPC 的精（jing）伤、精力（jingli）耗、`eff_` 上限伤（receive_wound 两层结构）全无。`Vitals` 组件（`components.py:460`）虽有 `neili_current`/`jingli_current` 字段，但战斗管线从不触及。 |
| 1.1b | **负面遗漏**：current/eff 两层血量缺失 | `damage.c:receive_damage` 改 `query(type)`（current），`receive_wound` 改 `query("eff_"+type)`（上限）并连带压 current；`heal_up`（:270-331）区分 current 回到 eff vs eff 回到 max | `Vitals`（`components.py:460`）只有 `qi_current`/`qi_max`，无 `eff_qi` 中间层 | LPC 三层血量（current → eff → max）在 engine 塌缩为两层（current → max）。wound（上限伤）这一伤害类别整体缺失。 |
| 1.1c | **负面遗漏**：多源 hit_ob/hit_by 塌缩为单源 | `s_combatd.c:473` force 技能 hit_ob、`:501` martial 技能 hit_ob、`:508` weapon hit_ob / `:512` me.hit_ob（徒手）、`:550` armor hit_by、`:562` dodge 技能 hit_by——共 4+2 个独立钩子点 | `combat.py:_invoke_hit_ob`（:236）/`_invoke_hit_by`（:255）只查**唯一** `get_skill_behavior(skill_id)` | engine 命中后只能挂一个 SkillBehavior；LPC 的"武器带毒"（`skill.c:142 hit_ob` 给 victim `apply_condition("snake_poison",...)`）、"内功加成"、"防具特效"、"闪避技能反击"无法分别接入。 |
| 1.1d | **负面遗漏**：hit_ob 返回 mapping 三态塌缩 | `s_combatd.c:478-482` force hit_ob 可返回 `mapping`（`foo["result"]`+`foo["damage"]`），weapon/armor 同 | `combat.py:_invoke_hit_ob`（:248-252）只处理 `int`/`str`/`None` | engine 无法表达"既改伤害又追加文案"的复合返回。 |
| 1.1e | **负面遗漏**：combat_exp / armor / jiajin 数值层缺失 | `s_combatd.c:541-545` `defense_factor=combat_exp` 概率削减伤害；`:578-587` `apply/armor` 减伤 + wound 判定；`:518-525` jiali/jiajin 精力驱动加成 | `combat.py` 无 combat_exp、无 armor 减伤、无 jiajin；`DefaultWuxiaPowerModel` 仅 force/str/dex | engine 战斗数值维度远少于 LPC（无经验削伤、无护甲、无精力驱动力）。 |
| 1.1f | **负面遗漏**：hit_ob 签名缺 factor 参数 | `skill.c:142` `hit_ob(object me, object victim, int damage_bonus, int factor)`——`factor` 是 jiali（内力加持量） | `skills.py:63` `hit_ob(self, ctx, damage)` | engine hit_ob 拿不到"内力加持强度"这类上下文，限制武功表达力。 |
| 1.1g | **正面偏差**：PowerModel 可整体替换 | LPC 公式硬编码在 `s_combatd.c` daemon 内 | `combat.py:72-82 PowerModel` Protocol + `attach_power_model`（:119） | engine 把 AP/DP/PP/伤害公式抽成协议，题材包可整体替换（ADR-0004），比 LPC 的"改 daemon 源码"更利于 UGC。 |
| 1.1h | **正面偏差**：纯函数快照 + 无副作用 inflict | LPC `do_attack` 直接改 victim dbase（receive_damage 副作用） | `combat.py:CombatContext` frozen dataclass + `resolve_attack` 只算不写，apply 由调用方负责（:145-148） | engine 结算与副作用分离，可纯函数直测；LPC 难以单测。 |

### 1.2 enemy/killer 列表与 MAX_OPPONENT

**LPC 设计**（`feature/attack.c`）：
- `static object *enemy = ({})` + `static string *killer = ({})`（:15-16）。`MAX_OPPONENT=4`（:12）。
- `fight_ob(ob)`（:40-48）：加入 enemy 列表，`set_heart_beat(1)`。`kill_ob(ob)`（:51-62）：同时入 killer 列表（id 串），对 victim 播"想杀死你"，再 `fight_ob`。
- `select_opponent()`（:79-88）：`which = random(MAX_OPPONENT)`，从 enemy 列表随机挑一个（`which < sizeof(enemy) ? enemy[which] : enemy[0]`）。即**单回合最多从 4 个敌人中随机选 1 个出手**。
- `clean_up_enemy()`（:64-75）：清失效敌人（已 dest / 不在同房间 / 非活且非 killer）。
- `is_fighting(ob)` / `is_killing(id)`（:24-37）区分"交手"与"追杀"。
- `remove_all_enemy()`（:112-123）保留 killer，只清 enemy；`remove_all_killer()`（:126-136）两者全清。
- **fight vs kill 二分**：fight 可 `remove_enemy` 脱战（:91-97），kill 一旦标记不可单方脱战（:93 `is_killing` 则 return 0）。

**engine 现状**（`combat_system.py`）：
- `Engaged` 组件（`components.py:692-698`）只有单一 `opponent: EntityId` 字段——**严格 1v1**。
- `try_engage`（:93-114）：若 attacker 已有 Engaged 且 opponent != defender → "你正在和其他人交战，分不开身"；若 defender 已 Engaged → "对方正在和别人交战"。**无 enemy 列表、无 MAX_OPPONENT、无多敌围攻**。
- `_on_combat_tick`（:248-273）：遍历 `entities_with(Engaged)`，按 `frozenset({entity,opponent})` 去重后双方各出手一次——**单对单**。
- 无 fight/kill 二分：只有 Engaged 与否，无"追杀"语义。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 1.2a | **负面遗漏**：多对手围攻缺失 | `attack.c:12 MAX_OPPONENT=4`、`select_opponent`（:79-88）从最多 4 敌随机选 1 | `Engaged.opponent` 单字段（`components.py:698`）；`try_engage`（:100-104）拒绝第二对手 | engine 无法表达 1v2+ 围攻（MVP 场景"组队围攻"无支撑）。LPC 的多敌列表 + 随机选敌是核心战斗结构。 |
| 1.2b | **负面遗漏**：fight/kill 二分缺失 | `attack.c:fight_ob`（:40）/`kill_ob`（:51）双 API；`remove_enemy`（:91）查 `is_killing` 决定能否脱战 | `combat_system.py` 只有 `try_engage`/`clear_engagement`，无 kill 语义 | engine 无"切磋 vs 拼死"区分，无法表达 LPC 的"killer 不可单方脱战"规则。 |
| 1.2c | **负面遗漏**：clean_up_enemy 失效敌清理缺失 | `attack.c:clean_up_enemy`（:64-75）按 dest/不同房/非活且非 killer 清理 | `combat_system.py:_on_combat_tick`（:259-265）只查对手是否仍 Engaged，不查是否同房/存活 | engine 依赖手动 `clear_engagement`，无 LPC 那种每 tick 自动清失效敌的健壮性。 |
| 1.2d | **正面偏差**：ECS 化的双向 Engaged | LPC enemy 列表是 per-object 静态数组，跨对象同步靠 `remove_all_enemy` 主动通知对方 | `combat_system.py:try_engage`（:112-113）双向各挂 Engaged 组件 | engine 用 ECS 组件双向标记，状态一致性靠组件系统保证，比 LPC 手动同步更清晰。 |

### 风险/影响
- **1.1a/b**：战斗只扣 qi、无 wound 上限伤，使"中毒耗精"、"内伤降上限"等武侠核心体感无法实现；`Vitals` 有 neili/jingli 字段却不用，是未接线的占位。
- **1.1c**：单源 hit_ob 使"武器毒 + 内功加成 + 武功特效"无法叠加，严重限制武功表达力——LPC 的 `skill.c:hit_ob` 本身就是通过 `apply_condition` 给毒的桥（见模块 3）。
- **1.2a**：MAX_OPPONENT=4 是 LPC 战斗基线结构，engine 1v1 限制使"组队围攻"玩法切片（brief 纳入范围）无引擎支撑。

---

## 模块 2：combat_system.py vs LPC 战斗循环（heart_beat + attack）

**LPC 设计**（`inherit/char/char.c:heart_beat` :60-169 + `attack.c:attack` :208-224）：
- `heart_beat` 每 tick 顺序：清 cmd_count / 限频道 → 查 `eff_qi<0 || eff_jing<0` → `remove_all_enemy(); die()`（:100-104，**上限伤致死**）→ 查 `qi<0 || jing<0 || jingli<0` → `remove_all_enemy()`；`living()` 则 `unconcious()`，否则（已昏迷 disable_type==" <昏迷不醒>"）`die()`（:108-115，**两段式：先昏迷后死亡**）→ `is_busy()` 则 `continue_action()`（:118-121）→ 否则查 wimpy 自动逃跑（:124-130，`env/wimpy` 气血百分比阈值）→ `attack()`（:132）→ NPC `chat()`（:135-139）→ 每 5+random(10) tick 跑一次 `update_condition()`（:141-144）→ `heal_up()`（:149）→ 无人交互则 `set_heart_beat(0)` 停跳（:157）。
- `attack()`（`attack.c:208-224`）：`clean_up_enemy()` → `select_opponent()` → `set_temp("last_opponent",opponent)` → 查 `yield`（:217 让招）→ `special_attack`（anubis 双手互博，:219）→ `COMBAT_D->fight(this_object(), opponent)`。
- `init()`（:229-258）：遇他对象时，按 `is_killing`/`vendetta_mark`/`attitude=="aggressive"` 触发 `COMBAT_D->auto_fight(...,type)`（hatred/vendetta/aggressive 三种主动开战）。

**engine 现状**（`combat_system.py`）：
- `attach_combat_system`（:77-90）：挂 `ON_TICK` → `_on_combat_tick`，幂等。
- `_on_combat_tick`（:248-273）：遍历 Engaged 对，去重后 `resolve_one_strike` 双向各一次。
- `resolve_one_strike`（:134-165）：`run_vetoable(ON_BEFORE_COMBAT_ROUND)` 可否决 → `build_combat_context` → `resolve_attack` → `apply_combat_result`（气血归零转 `handle_vitals_depleted`）→ `dispatch(ON_COMBAT_ROUND)` → `_broadcast_round`。
- `try_engage`（:93-114）：显式建立 1v1 交战。**无 NPC 主动 aggro**（注释 :6 "19 号票仅复用 try_engage"）。
- 事件点：`ON_BEFORE_COMBAT_ROUND` / `ON_COMBAT_ROUND` / `ON_COMBAT_END`（:41-43）。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 2.1a | **负面遗漏**：上限伤致死路径缺失 | `char.c:100-104` `eff_qi<0\|\|eff_jing<0` 直接 die | `combat_system.py:apply_combat_result`（:235-245）只查 `qi_current<=0` | engine 无"上限伤"概念（见 1.1b），故无此死亡路径。LPC 两条死亡路径（上限伤直死 vs 当前血昏迷/致死）在 engine 塌缩为一条。 |
| 2.1b | **负面遗漏**：wimpy 自动逃跑缺失 | `char.c:124-130` `env/wimpy` 百分比阈值触发 `GO_CMD->do_flee` | `combat_system.py` 无 wimpy；`CombatSystem.flee_success_chance`（:74）只是逃跑成功率，非自动触发 | engine 无"气血低自动脱战"机制，玩家无法设残血逃跑阈值。 |
| 2.1c | **负面遗漏**：is_busy/continue_action 缺失 | `char.c:118-121` `is_busy()` 时 `continue_action()` 不出手 | `combat_system.py` 无 busy/连招概念 | engine 无"忙乱态"打断出手，无法表达连续技/被封穴。 |
| 2.1d | **负面遗漏**：yield（让招）缺失 | `attack.c:217` `query_temp("yield")` 则不出手 | 无对应 | engine 无"切磋让招"开关。 |
| 2.1e | **负面遗漏**：NPC 主动 aggro 缺失 | `attack.c:init`（:229-258）`auto_fight` 三型（hatred/vendetta/aggressive）；`char.c:135-139` NPC `chat()` | `combat_system.py:6` 注释"19 号票 NPC aggro 暂缓"；无 init/auto_fight | engine 战斗只能由玩家显式 `attack` 发起，NPC 不会主动开战。MVP 的"野外遇敌"无引擎支撑。 |
| 2.1f | **负面遗漏**：heal_up 战斗中回血缺失 | `damage.c:heal_up`（:270-331）：战斗中 `jing += con/9 + max_jingli/30`、`qi += con/9 + max_neili/30`（减速回血），非战斗时 `/3` `/10`（正常） | engine 无 heal_up tick；`death_flow._on_unconscious_tick`（:417-429）只在昏迷苏醒时回 `recovery_vitals_ratio` | engine 战斗中无持续回血，LPC 的"边打边恢复"节奏缺失。 |
| 2.1g | **负面遗漏**：update_condition tick 驱动缺失 | `char.c:144` 每 5+random(10) tick 跑 `update_condition()` | engine 无 condition tick（见模块 3） | 战斗 tick 不驱动状态/Effect 更新，LPC 的"边打边中毒发作"无引擎支撑。 |
| 2.1h | **正面偏差**：vetoable 前置事件 | LPC 战斗无前置否决点，`attack()` 直接调 `COMBAT_D->fight` | `combat_system.py:resolve_one_strike`（:142-148）`run_vetoable(ON_BEFORE_COMBAT_ROUND)` 可被规则否决 | engine 引入可否决的回合前置事件，利于"禁武区/剧情锁战"等规则接入，LPC 只能靠 `no_fight` 房间标志硬挡。 |
| 2.1i | **正面偏差**：事件驱动解耦 | LPC heart_beat 内联 attack/condition/heal 全部逻辑 | `combat_system.py` 用 ON_TICK 订阅 + 独立 ON_COMBAT_* 事件 | engine 把战斗从 heart_beat 单体中拆出为独立子系统，可独立测试与替换。 |

### 风险/影响
- **2.1e/g**：NPC aggro + condition tick 双缺失，使 MVP 场景"野外遇敌中毒持续掉血"这一核心玩法切片**无法端到端跑通**——engine 战斗是"玩家显式 attack + 瞬时结算 + 无后续状态"。
- **2.1f**：无战斗中回血，战斗节奏会比 LPC 更"一刀毙命"，缺乏拉锯感。

---

## 模块 3：conditions.py vs feature/condition.c（重点：概念错位）

### 3.1 概念错位定性

**LPC condition.c 是时效性 Effect 引擎**（`feature/condition.c`）：
- `mapping conditions`（:8）：每个 condition 是 `cnd_name -> info` 映射，`info` 通常是 `int duration`（剩余 tick）。
- `update_condition()`（:21-69）：由 `heart_beat` 每 5+random(10) tick 调用（`char.c:144`）。遍历所有 condition，对每个 `find_object(CONDITION_D(cnd[i]))` 加载**外部 daemon**，调 `call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]])`。
- daemon 返回 `flag & CND_CONTINUE` 决定是否保留；返回 0 则 `map_delete` 过期移除（:63）。
- `apply_condition(cnd, info)`（:79-85）施加；`query_condition(cnd)`（:91-95）查询；`clear_condition()`（:105-108）全清（die 时调，`damage.c:184`）。
- **每个 condition 是独立 daemon**（`kungfu/condition/*.c`，约 60 个）：例如 `bt_poison.c:update_condition(me, duration)`（:5-40）按 `eff_jing` 分档播报不同文案 + `receive_wound("jing", damage/2, ...)` + `receive_damage("jingli", damage/2, ...)` + 按 `poison` 技能等级递减 duration。即**每 tick 扣血/扣精/播报/倒计时/过期**的完整时效 Effect。

**engine conditions.py 是通用布尔求值引擎**（`engine/src/openmud/conditions.py`）：
- 五种 frozen dataclass 节点：`Predicate`（:93）/`Equals`（:104）/`Gte`（:112）/`And`（:120）/`Or`（:126）/`Not`（:134）。
- `evaluate(condition, context)`（:170-176）：纯函数，只读 `ConditionContext` 协议属性（`phase`/`is_night`/`is_raining`/`faction_id`/`gender`/`is_wielding_edged_weapon`），返回 `bool`。
- 文档自述（:1-22）：是"门条件 / 物品使用限制 / NPC 行为条件三类动态规则的**共同条件子语言地基**"——**明确不是 Effect 引擎**。
- **无 mapping、无 duration、无 tick 驱动、无 daemon 调用、无 receive_damage 副作用、无 apply/clear**。

### 偏差/遗漏（关键）

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 3.1a | **概念错位（核心）** | `condition.c`：`mapping conditions` + `update_condition()` heart_beat 驱动 + `CONDITION_D` daemon 每 tick 扣血/播报/倒计时 | `conditions.py`：`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not` + `evaluate` 纯布尔求值 | **LPC 的时效性 Effect 引擎在 engine 完全缺失**。conditions.py 解决的是另一类问题（门/NPC/物品的静态布尔条件），与 LPC condition.c 同名但不同物。两者仅共享"condition"一词。 |
| 3.1b | **负面遗漏**：apply_condition / query_condition / clear_condition API 缺失 | `condition.c:79 apply_condition`、`:91 query_condition`、`:105 clear_condition`、`:97 clear_one_condition` | engine 无任何施加/查询/清除持续状态的 API | 无法表达"中毒施加 → 查询剩余 → 死亡全清"这一 Effect 生命周期。 |
| 3.1c | **负面遗漏**：Effect 内容层（kungfu/condition）无对应 | `kungfu/condition/` ~60 个 daemon：`bt_poison`/`chilian_poison`/`hsf_poison`/`huadu_poison`/`insect_poison`/`snake_poison`（毒）、`hanbing_damage`/`jiujian_qi_damage`/`juehu_damage`/`hyz_damage`（伤害）、`drunk`/`blind`/`embedded`/`bandaged`/`city_jail`/`dali_jail`/`bonze_jail`/`aphroclisiac` | engine 无任何 Effect 内容层；`DemoPoisonStrikeBehavior`（`skills.py:87`）只做命中瞬时 +5 伤害，**不施加持久毒** | LPC 的 30+ 状态效果（毒/伤/盲/醉/牢/包扎/嵌入暗器）在 engine 无任何承载。`DemoPoisonStrikeBehavior.hit_ob`（:95-96）返回 `damage+5`，与 LPC `skill.c:142 hit_ob` 调 `apply_condition("snake_poison",...)` 形成鲜明对比——**LPC hit_ob 本身是 Effect 施加桥，engine hit_ob 只是瞬时数值加成**。 |
| 3.1d | **负面遗漏**：Effect 与战斗/死亡的耦合点缺失 | `damage.c:184 die()` 调 `clear_condition()`（死亡清状态）；`damage.c:185 delete("poisoner")`；condition daemon 内部调 `receive_wound`/`receive_damage`（Effect 反向驱动血量）；`char.c:144 heart_beat` 每 N tick 驱动 update_condition | engine 无 Effect → 血量、死亡 → 清 Effect 的双向耦合 | LPC 的 Effect 是嵌入战斗/死亡生命周期的活组件，engine 的 conditions.py 是与之无关的静态布尔子语言。 |
| 3.1e | **是否拆到别处？** | — | `death_flow._on_unconscious_tick`（:417-429）是**唯一**的时效 Effect 雏形（昏迷倒计时苏醒），但硬编码、不可扩展；`skills.py:SkillBehavior` 是瞬时命中钩子非持续 Effect | LPC 的时效 Effect 引擎**既不在 conditions.py，也未在别处重建**。`_on_unconscious_tick` 只是一个写死的单 Effect，不是通用引擎。 |

### 风险/影响（最高优先级）
- **3.1a/c**：这是本对照报告**最严重的偏差**。LPC 战斗-Effect-死亡三系统的耦合核心是 condition 引擎（命中施加 → tick 发作扣血 → 死亡清除）。engine 缺失这一引擎，意味着：
  1. 「中毒持续掉血」「内伤发作」「盲/醉 debuff」等武侠核心体感**无法实现**；
  2. `DemoPoisonStrikeBehavior` 名含 Poison 却不挂毒，是**名实不符的占位**，易误导后续开发者以为 Effect 已接入；
  3. brief 纳入的玩法切片「中毒持续掉血」「昏迷与苏醒」缺引擎支撑（昏迷靠 death_flow 硬编码特例，中毒无任何支撑）。
- **3.1e**：若不在 conditions.py 之外另建 Effect 引擎，整个战斗-Effect-死亡耦合链断裂。这是后续 engine 设计的**第一待补缺口**。

---

## 模块 4：death.py vs feature/damage.c die()/ghost

**LPC 设计**（`feature/damage.c`）：
- `int ghost = 0`（:9）+ `is_ghost()`（:11）。`die()`（:152-253）：若 `no_death` 区 + user → 转 `unconcious()`（:159-177）；否则 `clear_condition()` + `delete("poisoner")`（:184-185）+ `COMBAT_D->announce(dead)` + `death_penalty`（:190）+ `killer_reward`（:194）+ 日志 PKILL_DATA/PLAYER_DEATH（:209-224）+ `make_corpse` 掉尸体（:227）+ `remove_all_killer`（:230）+ 玩家：`set(jing/qi/jingli=1)` + `ghost=1` + `move(DEATH_ROOM)` + `DEATH_ROOM->start_death` + `break_marriage` + 师徒 break_relation（:233-250）；NPC：`destruct`（:252）。
- `unconcious()`（:105-135）：`winner_reward` + `remove_all_enemy` + `interrupt_me` + `dismiss_team` + `set(jing/qi/jingli=0)` + `disable_player(" <昏迷不醒>")` + `call_out("revive", random(100-con)+30)`（苏醒倒计时与根骨相关）。
- `revive()`（:137-150）：`enable_player` + announce + 播报。
- `reincarnate()`（:255-264）：`ghost=0` + 全量恢复 `jing/qi/eff_jing/eff_qi/jingli/neili` 到 max。
- 两段式判定（`char.c:100-115`）：`eff_qi/eff_jing<0` → die（上限伤致死）；`qi/jing/jingli<0` → `living()` 则 unconcious，已 unconcious 则 die。

**engine 现状**（`death.py`）：
- `DeathState` 枚举（:13-18）：`ALIVE`/`UNCONSCIOUS`/`DEAD`——**三态无 GHOST**。
- `next_death_state`（:21-43）纯函数：未耗尽不变；已 DEAD 保持；`in_no_death_zone` → UNCONSCIOUS；耗尽+非免死+存活 → UNCONSCIOUS（第一段容错）；耗尽+非免死+已昏迷 → DEAD（第二段）；已 DEAD 保持。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 4.1a | **负面遗漏**：ghost 鬼魂态缺失 | `damage.c:9 int ghost`、`:11 is_ghost()`、`:246 ghost=1`、`:257 ghost=0`；`char.c:181-185 visible()` 鬼魂只对鬼魂/有天眼可见 | `DeathState`（:13-18）无 GHOST 态；engine 无 ghost 标志、无 is_ghost | LPC 的"死后变鬼"态在 engine 完全缺失。鬼魂可见性、鬼魂独立交互（只见鬼/天眼通）无支撑。 |
| 4.1b | **负面遗漏**：上限伤致死路径缺失 | `char.c:100-104` `eff_qi<0\|\|eff_jing<0` → die | `next_death_state`（:21-43）无 eff_ 概念，只有 `vitals_depleted`（qi_current） | engine 不区分"当前血耗尽"vs"上限伤致死"，缺 LPC 的第二条死亡路径。 |
| 4.1c | **负面遗漏**：unconcious 苏醒倒计时与根骨挂钩缺失 | `damage.c:134` `call_out("revive", random(100-con)+30)`——根骨越高醒越快 | `death_flow._on_unconscious_tick`（:417-429）固定 `ticks_remaining`（DeathPolicy.unconscious_recovery_ticks），与属性无关 | engine 昏迷时长是固定配置，无 LPC 的"根骨影响苏醒"属性挂钩。 |
| 4.1d | **负面遗漏**：die() 的清状态/师徒/婚姻断裂缺失 | `damage.c:184 clear_condition`、`:185 delete("poisoner")`、`:249 break_marriage`、`:250 break_relation`（风清扬师徒） | `death_flow._execute_player_death`（:212-270）无清状态（无状态可清，见模块 3）、无师徒/婚姻断裂 | engine 死亡不清理 Effect（因无 Effect 引擎）、不断裂社交关系（婚姻/师徒系统未建）。 |
| 4.1e | **负面遗漏**：make_corpse 尸体缺失 | `damage.c:227 CHAR_D->make_corpse` 掉尸体对象到房间 | `death_flow._drop_inventory_to_room`（:283-288）直接掉背包物品到房间，无尸体容器 | engine 无尸体对象，死亡掉落是裸物品列表，缺 LPC 的"尸体可搜刮/可复活"语义。 |
| 4.1f | **负面遗漏**：死亡日志/PKILL 缺失 | `damage.c:209-224` 写 PKILL_DATA/PLAYER_DEATH 日志，区分 PlayerKill 与普通死 | engine 无死亡日志 | engine 无击杀审计与 PvP 记录（商业化/运营埋点缺失）。 |
| 4.1g | **正面偏差**：两段式纯函数化 | LPC 两段判定散在 `char.c:heart_beat` 内联，与 attack/heal 混杂 | `death.py:next_death_state` 纯函数，不读写 World | engine 把死亡状态机抽成纯函数可直测，LPC 难以单测。注释明确"不执行掉落/惩罚/复活（那是 17 号票）"——职责分离清晰。 |
| 4.1h | **正面偏差**：免死区显式组件化 | LPC `damage.c:159 environment()->query("no_death")` 查房间属性 | `death.py:39 in_no_death_zone` + `NoDeathZone` 房间组件（`components.py:524`） | engine 用 ECS 组件标记免死区，比 LPC 的字符串属性查询更类型安全。 |

### 风险/影响
- **4.1a**：ghost 态缺失是模块 5 地府轮回缺失的根因——无 ghost 就无"鬼魂走地府"流程。
- **4.1b**：上限伤路径缺失与模块 1 的 eff_ 缺失同源，是战斗-死亡耦合的断层。

---

## 模块 5：death_flow.py vs d/death/ + die()/reincarnate()

**LPC 设计**：
- `die()`（`damage.c:152-253`）玩家分支：`ghost=1` → `move(DEATH_ROOM)`（`:247`，`DEATH_ROOM` = `/d/death/gate` 鬼门关，`include/login.h:23`）→ `DEATH_ROOM->start_death` → `break_marriage` → 师徒 break_relation。
- **地府区** `d/death/`（~580 行，14 房间）：`gate`（鬼门关，`init` 清所有 condition + 销毁全部背包物品 + 封 suicide）、`gateway`（酆都城门，单向不可回头）、`road1-3`（鬼门大道，串起 inn/hell）、`inn1`/`inn2`（客栈）、`hell`（第十八层地狱，封绝大多数命令）、`blkbot`（空房间/自首室，封练习类命令）、`block`/`death`（死刑室，封命令只留 quit/suicide/goto）、`noteroom`。玩家以鬼魂态在其中行走，全程 `no_fight`（鬼域禁武）。
- `reincarnate()`（`damage.c:255-264`）：`ghost=0` + 全量恢复。
- `death_penalty`（`combatd.c:987-1025`）：`skill_death_penalty`（技能经验惩罚）。
- `killer_reward`（`combatd.c:1027+`）/`winner_reward`（`combatd.c:982`）：击杀奖励。

**engine 现状**（`death_flow.py`）：
- `handle_vitals_depleted`（:171-185）：玩家 → `_handle_player_depleted`；NPC → `_handle_npc_death`。
- `_handle_player_depleted`（:188-209）：`next_death_state` → UNCONSCIOUS 则挂 `Unconscious` + `clear_engagement` + 播报；DEAD 则 `_execute_player_death`。
- `_execute_player_death`（:212-270）：挂 Dead → `run_vetoable(ON_BEFORE_DEATH)` 可否决（否决则退回昏迷）→ `dispatch(ON_DEATH)` → `clear_engagement` → `drop_items` → `currency_penalty` + `skill_exp_penalty` → 移除 Dead/Unconscious → 传送到 `revive_room` → 全量恢复 qi/neili/jingli → `dispatch(ON_REVIVE)` + 播报"死而复生"。
- `_handle_npc_death`（:308-336）：`clear_engagement` → `loot`（currency + items + kill_exp）→ `destroy_entity`。
- `DeathPolicy`（:77-86）：`penalty_ratio`/`revive_room_key`/`drop_items`/`drop_currency`/`unconscious_recovery_ticks`/`recovery_vitals_ratio`。
- `_on_unconscious_tick`（:417-429）：昏迷倒计时苏醒。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 5.1a | **负面遗漏**：地府轮回流程整体缺失 | `d/death/` 14 房间鬼魂行走流程（gate→gateway→road→inn→hell/blkbot）；`die():247 move(DEATH_ROOM)` + `start_death` | `death_flow._execute_player_death`（:256-258）直接 `revive_room` 传送，无鬼魂行走 | **engine 死亡是"瞬时传送复活"，LPC 是"变鬼走地府轮回"**。MVP 场景"玩家死亡下地府走轮回"（brief 2.1 纳入范围）无引擎支撑。 |
| 5.1b | **负面遗漏**：ghost 态与地府禁武缺失 | `damage.c:246 ghost=1`；`d/death/gate.c` 等 `set("no_fight",1)` 鬼域禁武；鬼魂可见性 `char.c:181-185` | engine 无 ghost 态（见 4.1a），无"鬼魂独立交互层" | 死后玩家与活人同处一室，无"鬼魂只见鬼"的隔离。 |
| 5.1c | **负面遗漏**：死亡清状态缺失（因无状态） | `die():184 clear_condition()` + `:185 delete("poisoner")`；`gate.c:init` `me->clear_condition()` 再清一次 | `_execute_player_death` 无 clear_condition 调用（无 Effect 引擎可清，见模块 3） | LPC 双重清状态（die 时 + 入鬼门关时），engine 因无 Effect 引擎而无此清理。毒/盲/醉等状态死后残留。 |
| 5.1d | **负面遗漏**：make_corpse 尸体缺失 | `die():227 CHAR_D->make_corpse` | `_drop_inventory_to_room`（:283-288）裸掉物品 | 见 4.1e。 |
| 5.1e | **负面遗漏**：师徒/婚姻断裂缺失 | `die():249 break_marriage` + `:250 break_relation` | 无 | 社交关系断裂未建（婚姻/师徒系统未纳入 MVP，可接受但需记录）。 |
| 5.1f | **负面遗漏**：killer_reward/winner_reward 区分缺失 | `combatd.c:982 winner_reward`（击倒非致死奖励）+ `:1027 killer_reward`（击杀奖励） | `_grant_kill_exp`（:398-408）单一经验授予 | engine 无 LPC 的"击晕 vs 击杀"奖励二分（与 1.2b fight/kill 缺失同源）。 |
| 5.1g | **负面遗漏**：death_penalty 技能惩罚粒度差异 | `combatd.c:987-1025 death_penalty` + `victim->skill_death_penalty()`（按技能类型分别惩罚） | `_apply_skill_exp_penalty`（:299-305）按统一 `penalty_ratio` 扣所有技能 exp | engine 是统一比例扣 exp，LPC 是按技能类型差异化惩罚（skill_death_penalty 可针对特定技能）。 |
| 5.1h | **正面偏差**：DeathPolicy 数据驱动 | LPC 死亡惩罚硬编码在 `combatd.c:death_penalty` + `skill_death_penalty` 各 skill daemon | `death_flow.DeathPolicy`（:77-86）frozen dataclass + `parse_death_policy`（:118-137）从 YAML 解析 | engine 把死亡惩罚参数抽成题材包可声明数据，比 LPC 硬编码更利于 UGC。 |
| 5.1i | **正面偏差**：LootTable 数据驱动 | LPC NPC 掉落散在各 NPC/技能 daemon | `death_flow.LootTable`（:89-97）+ `parse_loot_table`（:140-160）从 YAML 解析 | engine 把 NPC 战利品参数化，题材包可声明。 |
| 5.1j | **正面偏差**：ON_BEFORE_DEATH 可否决 | LPC die() 无前置否决 | `_execute_player_death`（:224-236）`run_vetoable(ON_BEFORE_DEATH)` 可否决退回昏迷 | engine 引入死亡前置否决，利于"剧情锁命/任务护盾"接入，LPC 只能靠 `no_death` 房间或 wizard immortal。 |
| 5.1k | **正面偏差**：玩家/NPC 死亡分流显式 | LPC die() 内 `userp()` 分支内联 | `handle_vitals_depleted`（:171-185）显式分流 `_handle_player_depleted` / `_handle_npc_death` | engine 职责分离清晰。 |

### 风险/影响
- **5.1a/b**：地府轮回与 ghost 态双缺失，是 brief 明确纳入的 MVP 场景之一（「玩家死亡下地府走轮回」）的**直接断层**。若要补，需先建 ghost 态（模块 4）+ 鬼魂房间层 + 鬼域禁武。
- **5.1c**：死亡不清状态与模块 3 的 Effect 引擎缺失形成连锁——即使后续建了 Effect 引擎，death_flow 也需补 `clear_effect` 调用。

---

## 模块 6：skills.py vs inherit/skill + kungfu/skill + kungfu/class

**LPC 设计**：
- `inherit/skill/skill.c`：`hit_ob(object me, object victim, int damage_bonus, int factor)`（:142）基类默认实现——**检测武器带毒则 `victim->apply_condition("snake_poison",...)`** + `victim->kill_ob(me)` + 设 `poisoner`，返回文案（:144-160）。即 skill 的 hit_ob 是 Effect 施加桥。
- `kungfu/skill/18-zhang.c:hit_ob`（:309）：武功特化 hit_ob（如三辉 temp 管理）。
- `inherit/skill/skill.c` 另有：`query_action`（返回 action mapping，含 force/damage/dodge/action 文案）、`query_dodge_msg`/`query_parry_msg`（闪避/招架文案）、`parry_available`、`is_special`、`hit_by`。
- `kungfu/skill/`：大量武功（18-zhang 降龙十八掌 / 6mai-shenjian 六脉神剑 / beiming-shengong 北冥神功 / archery 射箭 / blade/sword/axe 各兵器招式）。
- `kungfu/class/`：19 门派武功集（baituo/dali/emei/gaibang/gumu/huashan/lingjiu/mingjiao/murong/quanzhen/shaolin/shenlong/taohua/wudang/xingxiu/xixia/xuedao/xueshan/misc）——门派 → 武功集归属。
- 技能成长：`improve_skill(skill, amount)`（`s_combatd.c:387/433/504/615` 等，命中/闪避/招架时成长）；`combat_exp`/`potential` 成长。

**engine 现状**（`skills.py`）：
- `SkillMove`（:23-33）：`name`/`force`/`dodge`/`damage_type`/`damage`/`lvl`/`text`。
- `SkillData`（:36-52）：`skill_id`/`skill_type`/`level_req`/`moves`/`practice_neili_cost`/`practice_jingli_cost`/`practice_exp_gain`/`exp_thresholds`/`learn_condition`。
- `SKILLS` 全局注册表（:54）+ `load_skills_from_mapping`（:151）/`replace_skills_registry`（:170）从 YAML 解析。
- `SkillBehavior` Protocol（:59-67）：`hit_ob(ctx, damage) -> int|str|None`、`hit_by(ctx) -> str|None`、`post_action(ctx) -> str|None`。
- `DemoPoisonStrikeBehavior`（:87-102）：`hit_ob` 返回 `damage+5`（瞬时，不挂毒）、`hit_by` 返回"毒素渗入伤口！"文案。
- `SilkRopeCaptureBehavior`（:105-137）：`hit_ob` 调 `relocate_entity` 把防御方拽入密室。
- `select_move`（`combat_system.py:198-224`）：从 `SkillLevels` 选最高 force 且等级达标的招式。

### 偏差/遗漏

| # | 偏差类型 | LPC 证据 | engine 证据 | 说明 |
|---|---------|---------|------------|------|
| 6.1a | **负面遗漏**：门派武功归属缺失 | `kungfu/class/` 19 门派目录（baituo/dali/emei/.../xueshan），每门派聚合本派武功集 | `skills.py` 无 faction→skill 映射；`SkillData` 无 `faction`/`class` 字段 | engine 技能是扁平注册表（`SKILLS` dict），无门派归属。`conditions.py:ConditionContext.faction_id`（:74）存在但仅用于门条件查询，不驱动武功归属。MVP 场景"门派（少林寺）"武功集无数据结构支撑。 |
| 6.1b | **负面遗漏**：hit_ob 作为 Effect 施加桥缺失 | `skill.c:142 hit_ob` 基类默认 `apply_condition("snake_poison",...)`；`18-zhang.c:309 hit_ob` 管理三辉 temp | `DemoPoisonStrikeBehavior.hit_ob`（:95-96）只 `damage+5`，不施加任何持久状态 | **LPC hit_ob 的核心职责之一是挂 Effect**（通过 apply_condition），engine hit_ob 只做瞬时数值加成。这与模块 3 的 Effect 引擎缺失是同一断层的两面。 |
| 6.1c | **负面遗漏**：query_dodge_msg/query_parry_msg 缺失 | skill daemon 提供 `query_dodge_msg(limb)`/`query_parry_msg(weapon,victim)`，每招式独立闪/架文案 | `CombatMoveSnapshot.text`（:33）单文案字段；`combat.py:message_fragments` 仅"被闪避"/"被招架"通用文案 | engine 无按招式/部位的闪避招架文案，战斗播报单调。 |
| 6.1d | **负面遗漏**：weapon hit_ob 缺失 | `s_combatd.c:508 weapon->hit_ob` 武器独立钩子（武器带毒/特效应） | engine 无武器作为 effect 源；武器仅是 `move.skill_type` 来源 | "涂毒武器"这一武侠核心机制无引擎支撑（LPC 的 weapon hit_ob 是毒的主要施加路径之一）。 |
| 6.1e | **负面遗漏**：技能在用中成长缺失 | `s_combatd.c:387 improve_skill("dodge",1)`（闪避时）/`:433 improve_skill("parry",1)`（招架时）/`:504 improve_skill(attack_skill,1)`（命中时）/`:615 improve_skill("parry",random(damage))`（yield 时） | `_grant_kill_exp`（`death_flow.py:398-408`）只在击杀时给 exp；`select_move`（:198-224）只查 `SkillLevels` 不改 | engine 技能只在击杀时一次性给经验，LPC 是"每次闪/架/命中都成长"。练习成长有 `practice_*` 字段但战斗中成长缺失。 |
| 6.1f | **负面遗漏**：combat_exp/potential 成长缺失 | `s_combatd.c:386/432/600-609` `combat_exp += 1` + `potential += 1`；`defense_factor=combat_exp` 削伤 | engine 无 combat_exp、无 potential | engine 战斗无"战斗经验"这一独立成长轴（既不削伤也不成长），与 1.1e 同源。 |
| 6.1g | **负面遗漏**：force（内功）作为 hit_ob 独立源缺失 | `s_combatd.c:471-484` `my["jiali"]` + `force_skill = query_skill_mapped("force")` → `SKILL_D(force_skill)->hit_ob(me,victim,damage_bonus,jiali)`，内功可返 int/str/mapping | engine 无 force 技能类型独立钩子；`SkillData.skill_type`（:41）是字符串但不被 combat 区分 | "内功加成伤害/特效"这一武侠核心机制（北冥神功、降龙十八掌的内力驱动）无独立接入点。 |
| 6.1h | **负面遗漏**：技能映射（query_skill_mapped）缺失 | `attack.c:158 query_skill_mapped(type)` 把某类技能映射到特定武功 daemon；`reset_action`（:143-171）按映射选 `SKILL_D(skill)->query_action` | `select_move`（:198-224）只按 force 最高选，无"把 dodge 类映射到某轻功"的映射机制 | engine 无技能类别→具体武功的映射，无法表达"我的闪避用凌波微步"这类配置。 |
| 6.1i | **正面偏差**：SkillData 纯数据声明式 | LPC 武功是 `.c` daemon（代码），含 `query_action` 返回 mapping（半数据半代码） | `skills.py:SkillData` frozen dataclass + `load_skills_from_mapping`（:151）从 YAML 解析 | engine 武功是纯数据（YAML），比 LPC 的 daemon 代码更利于 UGC 创作者声明，无需写 LPC。这是 ADR-0005 UGC 创作层的正确方向。 |
| 6.1j | **正面偏差**：SkillBehavior 协议可选 | LPC 每武功都有 daemon（即使无特殊行为也要实现） | `skills.py:60` "多数招式只填 SkillData 数值，不实现本协议" | engine 把"数值招式"与"有副作用的招式"分离，无副作用的纯数值武功无需写代码。 |
| 6.1k | **正面偏差**：learn_condition 结构化门槏 | LPC 学武条件散在师傅 NPC 的对话/动作里 | `SkillData.learn_condition`（:51）结构化 dict，复用 conditions.py 求值 | engine 学武门槏数据驱动（虽 conditions.py 是布尔引擎非 Effect 引擎，但用于学武门槏是恰当的）。 |

### 风险/影响
- **6.1a**：门派武功归属缺失，MVP 场景"门派（少林寺）"的武功集无数据结构承载。
- **6.1b/d/g**：hit_ob 三源（force/weapon/martial）在 engine 塌缩为单源 SkillBehavior，且该单源不挂 Effect——武功的"内功驱动""武器带毒""招式特效"三层表达力全失。
- **6.1e**：技能只在击杀时成长，玩家无法靠"对练/闪避"提升技能，成长路径单一。

---

## 汇总：正面偏差 vs 负面遗漏

### 正面偏差（engine 做得更好的地方）

1. **PowerModel 可整体替换**（`combat.py:72-82`）：AP/DP/PP/伤害公式抽成 Protocol，题材包可整体替换（ADR-0004），优于 LPC 硬编码 daemon。
2. **结算纯函数化 / 副作用分离**（`combat.py:resolve_attack` + `CombatContext` frozen）：可纯函数直测，LPC `do_attack` 直接改 victim dbase 难以单测。
3. **死亡状态机纯函数化**（`death.py:next_death_state`）：两段式判定抽成纯函数，职责分离（不执行掉落/复活，交 death_flow）。
4. **DeathPolicy / LootTable 数据驱动**（`death_flow.py:77-97`）：死亡惩罚/战利品从 YAML 解析，题材包可声明，优于 LPC 硬编码。
5. **SkillData 纯数据声明式**（`skills.py:36-52`）：武功从 YAML 加载，无需写 LPC daemon，利于 UGC（ADR-0005）。
6. **SkillBehavior 协议可选**（`skills.py:60`）：纯数值招式无需实现钩子。
7. **事件驱动解耦 + vetoable 前置否决**（`combat_system.py:ON_BEFORE_COMBAT_ROUND` / `death_flow.py:ON_BEFORE_DEATH`）：引入可否决的前置事件点，利于规则接入，LPC 只能靠 `no_fight`/`no_death` 房间属性硬挡。
8. **ECS 化组件标记**（`Engaged`/`Unconscious`/`Dead`/`NoDeathZone`）：双向 Engaged 状态一致性靠组件系统保证，优于 LPC 手动 `remove_all_enemy` 同步。
9. **免死区显式组件化**（`NoDeathZone`）：比 LPC `query("no_death")` 字符串属性更类型安全。
10. **玩家/NPC 死亡分流显式**（`death_flow.handle_vitals_depleted`）：职责清晰。

### 负面遗漏（engine 缺失的能力，按严重度排序）

1. **【最严重】时效性 Effect 引擎整体缺失**（模块 3）：LPC `condition.c` 的 `mapping conditions` + `update_condition()` heart_beat 驱动 + `CONDITION_D` daemon 每 tick 扣血/播报/倒计时/过期，在 engine 完全无对应。`conditions.py` 是同名异物的布尔求值引擎。30+ Effect 内容层（毒/伤/盲/醉/牢/包扎/嵌入）无承载。`DemoPoisonStrikeBehavior` 名含 Poison 却不挂毒，是误导性占位。**这是战斗-Effect-死亡耦合链的断层核心。**
2. **【严重】ghost 鬼魂态 + 地府轮回流程缺失**（模块 4/5）：LPC `die()` 设 `ghost=1` + 移入 `d/death/gate` 鬼门关，玩家走 14 房间地府轮回。engine 死亡是"瞬时传送复活"，无 ghost 态、无鬼域禁武、无鬼魂可见性隔离。MVP 场景"玩家死亡下地府走轮回"直接断层。
3. **【严重】多对手围攻缺失**（模块 1.2）：LPC `MAX_OPPONENT=4` + `enemy`/`killer` 列表 + `select_opponent` 随机选敌。engine `Engaged` 严格 1v1。MVP 场景"组队围攻"无引擎支撑。
4. **【严重】三类伤害塌缩为一类**（模块 1.1a/b）：LPC `receive_damage(jing/qi/jingli)` + `receive_wound(jing/qi)` 两层（current/eff）血量。engine 战斗只扣 `qi_current`，无精伤、精力耗、上限伤。"中毒耗精""内伤降上限"无法实现。
5. **【严重】hit_ob 多源塌缩为单源 + 不挂 Effect**（模块 1.1c/6.1b/d/g）：LPC 有 force/weapon/martial 三个独立 hit_ob 源 + armor/dodge 两个 hit_by 源，且 `skill.c:hit_ob` 基类默认通过 `apply_condition` 挂毒。engine 单一 `SkillBehavior.hit_ob` 只做瞬时数值加成。
6. **【中】NPC 主动 aggro 缺失**（模块 2.1e）：LPC `attack.c:init` 的 `auto_fight` 三型（hatred/vendetta/aggressive）。engine 无 NPC 主动开战。MVP"野外遇敌"无支撑。
7. **【中】fight/kill 二分缺失**（模块 1.2b）：LPC `fight_ob`/`kill_ob` 区分切磋与拼死，killer 不可单方脱战。engine 只有 Engaged。
8. **【中】战斗中回血（heal_up）缺失**（模块 2.1f）：LPC 边打边按 con/neili 回血。engine 战斗中无回血。
9. **【中】wimpy 自动逃跑缺失**（模块 2.1b）：LPC `env/wimpy` 气血阈值自动 flee。engine 无。
10. **【中】门派武功归属缺失**（模块 6.1a）：LPC `kungfu/class/` 19 门派武功集。engine `SkillData` 无 faction 字段。MVP"门派（少林寺）"武功集无数据结构。
11. **【中】技能在用中成长缺失**（模块 6.1e）：LPC 每次闪/架/命中 `improve_skill`。engine 只在击杀给 exp。
12. **【中】combat_exp 削伤/成长缺失**（模块 1.1e/6.1f）：LPC combat_exp 既概率削伤又成长。engine 无此轴。
13. **【中】上限伤致死路径缺失**（模块 4.1b）：LPC `eff_qi<0` 直死。engine 无 eff_ 概念。
14. **【中】死亡清状态缺失**（模块 4.1d/5.1c）：LPC die() + 入鬼门关双清 condition。engine 无 Effect 可清（与遗漏 1 联动）。
15. **【低】尸体对象缺失**（模块 4.1e/5.1d）：LPC `make_corpse`。engine 裸掉物品。
16. **【低】死亡日志/PKILL 缺失**（模块 4.1f）：LPC 写 PKILL_DATA/PLAYER_DEATH。engine 无审计。
17. **【低】师徒/婚姻断裂缺失**（模块 5.1e）：LPC `break_marriage`/`break_relation`。engine 无（社交系统未建，可接受）。
18. **【低】query_dodge_msg/query_parry_msg 缺失**（模块 6.1c）：LPC 按招式/部位的闪架文案。engine 通用文案。
19. **【低】unconcious 苏醒与根骨挂钩缺失**（模块 4.1c）：LPC `random(100-con)+30`。engine 固定 ticks。
20. **【低】is_busy/continue_action/yield 缺失**（模块 2.1c/d）：LPC 忙乱态/让招。engine 无。

---

## 关键结论

1. **conditions.py 概念错位是本对照报告的核心发现**（模块 3）：LPC 的时效性 Effect 引擎在 engine 既不在 conditions.py（那是布尔求值器），也未在别处重建（`_on_unconscious_tick` 是硬编码单 Effect，不是通用引擎）。这是战斗-Effect-死亡耦合链的断层核心，应作为后续 engine 设计的**第一待补缺口**。
2. **ghost 态 + 地府轮回是 MVP 场景的直接断层**（模块 4/5）：brief 2.1 纳入「玩家死亡下地府走轮回」，engine 死亡是瞬时传送复活，无 ghost 态与鬼魂房间层。
3. **多对手围攻 + 三类伤害是战斗结构性的两处塌缩**（模块 1.2/1.1）：MAX_OPPONENT=4 与 jing/qi/jingli 三类伤害是 LPC 战斗基线，engine 1v1 + 单类 qi 使"组队围攻""中毒耗精"等玩法切片无支撑。
4. **engine 的正面方向正确**：PowerModel/SkillData/DeathPolicy 的数据驱动与协议化设计符合 ADR-0004/0005 的题材无关 + UGC 方向，纯函数化与事件驱动解耦利于测试与扩展。偏差多为"未建"而非"建错"。
5. **DemoPoisonStrikeBehavior 是误导性占位**（模块 3.1c/6.1b）：名为毒击却不挂持久毒，易让后续开发者误以为 Effect 已接入，建议显式标注为"瞬时伤害示范，非 Effect 引擎示范"。
