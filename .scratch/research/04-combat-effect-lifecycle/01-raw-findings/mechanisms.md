# 战斗与效果生命周期簇 — 通用机制抽象（LPC 考古）

> 本文件为「战斗/效果机制设计师」产出，从《侠客行》LPC 一手源码中抽象「命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活」耦合链的通用机制。**LPC 源码是唯一真相源**；每条结论标注 `文件路径:函数/对象名`。机制抽象不绑定具体武功/毒名内容，只提取结构与触发模型。
>
> 证据约束：本文中所有 `feature/`、`inherit/`、`adm/daemons/`、`kungfu/`、`d/death/`、`cmds/std/`、`include/` 引用均来自当前仓库根目录的实际文件。行号以 Read 工具实际读取结果为准。

## 0. 耦合链总览（命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活）

《侠客行》把战斗、Effect、死亡三者缝在同一个 tick 驱动器上：`heart_beat()`。完整链路是：

```
heart_beat (char.c:60)
   ├─ check eff_qi/eff_jing < 0 ───────────► die()                    [硬死亡快道]
   ├─ check qi/jing/jingli < 0
   │     ├─ living()==1  ─► unconcious()                              [昏迷]
   │     └─ disable_type==" <昏迷不醒>" ─► die()                       [两段式：已昏迷再负=死]
   ├─ attack() (attack.c:208) ─► COMBAT_D->fight() (combatd.c:787)
   │     └─ do_attack() (combatd.c:340)
   │           ├─ AP/DP/PP 三段随机命中判定
   │           ├─ victim->receive_damage("qi", damage, me)           [伤害落点]
   │           ├─ victim->receive_wound("qi", damage-armor, me)      [创伤]
   │           ├─ SKILL_D(force_skill)->hit_ob / weapon->hit_ob       [effect 注入点]
   │           └─ message_vision(result, me, victim) + report_status [状态播报]
   └─ tick-- ==0 时 update_condition() (condition.c:21)
         └─ CONDITION_D(cnd)->update_condition(me, info)              [Effect 周期结算]
               ├─ receive_damage / receive_wound / receive_curing     [Effect 回灌伤害]
               ├─ apply_condition(cnd, duration-1)                     [续期]
               └─ message_vision / tell_object                         [Effect 播报]
```

**关键耦合点**：

1. **`set_heart_beat(1)` 是战斗与 Effect 的总开关**。`attack.c:44 fight_ob()`、`damage.c:34/63 receive_damage()/receive_wound()` 都会显式拉起 heart_beat。意思是：一旦有人开打或挨打，整个世界的心跳就被点亮，Effect 结算也就跟着跑。
2. **伤害是 Effect 的入口，Effect 又是伤害的入口**。`combatd.c:678 do_attack` 直接调 `victim->receive_damage`；而 `condition/*.c` 内部又会反向调 `receive_damage/receive_wound`（如 `bt_poison.c:33-34`、`hanbing_damage.c:23-24`、`hyz_damage.c:30-31`）。两者形成自驱闭环。
3. **`last_damage_from` / `last_eff_damage_from` 是死亡判定的来源指针**。`damage.c:21,47 receive_damage/receive_wound` 写入 `temp("last_damage_from", who)`；`damage.c:112 unconcious()` 读它做 `winner_reward`；`damage.c:192 die()` 读它做 `killer_reward` 与 PKill 日志。Effect 内部传字符串 `"身中西域灵蛇毒死掉了"`（`bt_poison.c:33`）作为 `who`，从而支持"非战斗者致死"的归因。

下文逐条展开。

---

## 1. 交战与敌对（attack.c / team.c）

### 1.1 双列表：`enemy` 与 `killer` 分离

`feature/attack.c:15-16`：

```c
static object *enemy = ({});
static string *killer = ({});
```

- **`enemy` 列表**（`object *`）：当前正在交战的对象引用。`fight_ob(ob)`（:40）写入，决定 `heart_beat` 里 `attack()` 选谁打。
- **`killer` 列表**（`string *`，存 id）：意图"杀死"对方的名单。`kill_ob(ob)`（:51）写入，并 `tell_object(ob, HIR "看起来...想杀死你！")` 给受害者红色警告。

**两者的语义差**是设计核心：`fight`（切磋）只进 `enemy`、不进 `killer`，所以"只会消耗体力，不会真的受伤"（`cmds/std/fight.c` help 文案）；`kill`（性命相搏）进 `killer`，`combatd.c:680` 处用 `me->is_killing(victim->query("id"))` 作为是否触发 `receive_wound`（创伤）的开关之一。也就是说 **`killer` 标志会改变伤害结算的严重程度**，不只是 UI 提示。

### 1.2 `MAX_OPPONENT=4` 与随机选敌

`attack.c:12 #define MAX_OPPONENT 4`。`select_opponent()`（:79）：

```c
which = random(MAX_OPPONENT);
return which < sizeof(enemy) ? enemy[which] : enemy[0];
```

机制含义：即便 `enemy` 列表 >4 人，每 tick 也只在**前 4 个槽位**里随机选一个出手；若 `enemy` 列表只有 1-3 人，`which` 可能越界，回退到 `enemy[0]`。这是"一个角色同时被很多人围攻时，单回合只能打其中 4 个"的硬约束，也是组队围攻（team）的并发上限来源。

### 1.3 敌对清理与"非 kill 不退"规则

- `clean_up_enemy()`（:64）：每 tick 在 `attack()` 开头调一次。规则是 `!objectp(enemy[i]) || environment()!=environment() || (!living(enemy[i]) && !is_killing(enemy[i]->query("id")))` 三选一则移除。**关键**：如果对方已昏迷（`!living()`）但我方 `is_killing` 他，**不会**从 enemy 列表移除——这是 `kill` 语义的延伸："杀手不会因为对方晕了就停手"，下一步 `attack()` 还会继续打昏迷者（`combatd.c:799 fight()` 中 `victim->is_busy() || !living(victim)` 走 `TYPE_QUICK` 快攻分支）。
- `remove_enemy()`（:91）：若 `is_killing(ob->query("id"))` 返回 0 拒绝退战。
- `remove_all_enemy()`（:112）：只清 `enemy`，保留 `killer`。**注释明确说明**："We ask our enemy to stop fight, but not nessessary to confirm...bcz the fight will start again if our enemy keeping call COMBAT_D->fight() on us."（:115-117）——这是双向解战但单向信任的设计。
- `remove_all_killer()`（:126）：同时清 `killer` 与 `enemy`，在 `die()` 中调用（`damage.c:230`）。

### 1.4 自动开战触发器（init / auto_fight）

`attack.c:229 init()` 在另一个对象进入当前房间时被 MudOS 调用，是自动开战的入口。检查链（:238-257）：

1. `is_fighting()` 或 `!living()` 或对方 linkdead → 跳过；
2. `userp(ob) && is_killing(ob->query("id"))` → `COMBAT_D->auto_fight(this, ob, "hatred")`（旧仇重启）；
3. `vendetta_mark` 匹配 → `auto_fight(..., "vendetta")`（世仇）；
4. `userp(ob) && attitude=="aggressive"` → `auto_fight(..., "aggressive")`（NPC 嗜杀）。

`combatd.c:852 auto_fight()` 用 `call_out("start_" + type, 0, me, obj)` 异步触发，给受害者"溜走"的机会。四个 `start_*` 分支（:869/:904/:928/:946）共用前置检查 `is_fighting(obj) || !living(me) || environment()!=environment(obj) || environment(me)->query("no_fight")` 四条任一为真即放弃。`start_berserk`（:869）还引入 `shen`（善恶值）与 `neili` 对抗判定：`neili > (random(shen)+shen)/10` 则克制住不出手。

**`no_fight` 房间标志**是全局硬约束，`attack.c:54 kill_ob()` 第一行就 `if (environment()->query("no_fight")) return;`，`cmds/std/kill.c:10`、`cmds/std/fight.c:9`、`cmds/std/hit.c:13` 同样拦截。地府区所有房间都 `set("no_fight", 1)`（`d/death/gate.c:21`、`gateway.c`、`road1-3`、`inn1/2` 全部）。

### 1.5 组队（team.c）

`feature/team.c` 用 `static object leader, lord, *team`（:8）维护组队关系。

- **`leader` vs `lord`**：`set_leader()`（:10）是"跟随者"关系，`set_lord()`（:19）是"驯服者/主从"关系（野兽被驯服后 set_lord，见 `inherit/char/trainee.c:78 me->set_lord(ob)`）。两者分离。
- **`follow_me(ob, dir)`**（:37）：当 leader 移动时，队员按 `move` 技能对抗判定是否跟上：`random(ob->query_skill("move")) > this->query_skill("move")` 则用 `call_out("follow_path", 1, dir)` 延迟一拍跟上（:42-44），否则立即 `follow_path(dir)`。**关键副作用**：`follow_path()`（:28）开头无条件 `this_object()->remove_all_enemy()`（:32）——**移动会清空 enemy 列表**（但保留 killer），这是"逃跑"机制的核心。
- **`dismiss_team()`**（:103）：解散队伍。在 `damage.c:124 unconcious()`、`damage.c:244 die()` 中被调用——**昏迷与死亡都会强制解散队伍**。
- **team 与战斗的耦合**：`team.c` 本身没有"合击"逻辑（合击在 `s_combatd.c` 的注释里提到 `stand/teamwork` temp 标志，是 cyz&kitten 的 prototype，未进主路径）。team 的战斗意义主要是：①共享 enemy（leader 被打队员跟上）；②死亡时连带解散。

### 1.6 玩家命令层（cmds/std）

| 命令 | 文件 | 行为 | 与 attack.c 的接口 |
|------|------|------|-------------------|
| `kill <人物>` | `cmds/std/kill.c` | 主动 `kill_ob`，写入 killer 列表；对玩家 PK 有 `pker` condition 惩罚窗口（`me->query_condition("pker") > 240 || obj->query("mud_age") < 18000` 拦截，:51） | `me->kill_ob(obj)` (:74) |
| `fight <人物>` | `cmds/std/fight.c` | 切磋，只 `fight_ob`；对玩家需对方二次 `fight` 确认（`pending/fight` 机制，:32-37） | `me->fight_ob(obj); obj->fight_ob(me)` (:53-54) |
| `hit <人物>` | `cmds/std/hit.c` | 偷袭，`call_out("do_hit", 1, me, obj)` 异步一次 `COMBAT_D->do_attack` 互换一招；只对玩家，NPC 走 `kill`（:78） | `COMBAT_D->do_attack(me, obj, weapon)` (:113-116) |
| `forcekill <A> with <B>` | `cmds/std/forcekill.c` | 念咒操控 NPC 去杀 B（降伏法 `necromancy` skill >=90 + `xs_necromancy` condition） | `target->kill_ob(victim)` (:62) |

---

## 2. 命中与伤害结算（combatd.c / s_combatd.c / damage.c）

### 2.1 `do_attack()` 七步流水线

`adm/daemons/combatd.c:340 do_attack(me, victim, weapon, attack_type)` 是命中->伤害的核心。`s_combatd.c:294 do_attack` 结构几乎一致（cyz&kitten 的 prototype 版，加了 `anubis_attack` 反击分叉 :346-351）。七步：

**Step 0 — 选技能**（:366-378）：从 `query_skill_prepare()` 取预备技能键，决定 `attack_skill`（weapon 存在则用 weapon 的 `skill_type`，否则用 prepare 或默认 `"unarmed"`）。`action_flag`（0/1）用于双手互博时切换主/副手技能。

**Step 1 — 取招式 action**（:383-401）：`me->reset_action()`（`attack.c:143`）把 `actions` 设为 `call_other(SKILL_D(skill), "query_action", me, ob)` 的函数指针（或 weapon 的 `actions`，或 `default_actions`）。然后 `action = me->query("actions")`，取 `action["action"]`（招式文案）、`action["damage_type"]`（伤害类型，影响 `damage_msg`）、`action["dodge"]`、`action["force"]`、`action["damage"]`、`action["post_action"]` 等字段。

**Step 2 — 计算 AP/DP**（:406-422）：
- `ap = skill_power(me, attack_skill, SKILL_USAGE_ATTACK)`（:409）
- `dp = skill_power(victim, "dodge", SKILL_USAGE_DEFENSE)`（:417）
- 受害者 `is_busy()` 时 `dp /= 3`（:419）——**忙碌状态显著降低闪避**。

**Step 3 — 闪避判定**（:430 `if( random(ap + dp) < dp )`）：
经典 `A/(A+B)` 概率模型。命中失败走 `RESULT_DODGE`（`include/combat.h:11 #define RESULT_DODGE -1`），调 `SKILL_D(dodge_skill)->query_dodge_msg(limb)` 取闪避文案，扣 `my["jingli"] -= my["jiajin"]`（:458，jiajin=出招精力消耗），并给 NPC 加经验。

**Step 4 — 格挡判定**（:468-511 `pp` 计算 + :488 `random(ap + pp) < pp`）：
- 有武器：`pp = skill_power(victim, "parry", DEFENSE)`；空手对武器则 `pp *= 2`（:472，"空手入白刃"加成）。
- 无武器对有武器：`pp = 0`（:476，**无招架能力**）。
- `is_busy()` 时 `pp /= 2`。
- 命中失败走 `RESULT_PARRY`（`combat.h:12 #define RESULT_PARRY -2`），调 `SKILL_D(parry_skill)->query_parry_msg`。

**Step 5 — 命中后的伤害叠加链**（:515-641）：
```
damage = apply/damage                              [:519]  武器基础
damage = (damage + random(damage)) / 2            [:520]  随机化
damage += action["damage"]/10 * damage/30         [:528]  招式加成
damage += skill(attack_skill)/10 * damage/10      [:534]  技能加成
damage_bonus = str                                [:536]  力量基线
  + SKILL_D(force_skill)->hit_ob (内力加成)        [:541-562]
  + action["force"]/10 * damage_bonus/100         [:564-570]
  + skill(attack_skill)/4 + skill("force")/2      [:573-577]
  + SKILL_D(martial_skill)->hit_ob (招式 hit_ob)   [:578-585]
  + weapon->hit_ob 或 me->hit_ob (武器/怪物特效)   [:588-603]
  + jiajin 加成 (jingli/20 + jiajin - your_jingli/25) [:606-617]
damage += (damage_bonus + random(damage_bonus))/2 [:628-631]
defense_factor = your["combat_exp"]               [:636]  经验削减
  while random(defense_factor) > my["combat_exp"] [:637]  递归削减 1/3
    damage -= damage/3; defense_factor /= 2
特殊护甲 hit_by / 特殊 dodge hit_by                [:644-672]  最终改写 damage
```

**关键**：`hit_ob()` 是 Effect 注入点。`SKILL_D(skill)->hit_ob(me, victim, damage_bonus, factor)` 可返回 `string`（文案）、`int`（加成数值）、`mapping`（`["result"]+["damage"]`）。`inherit/skill/force.c:6 hit_ob` 与 `inherit/skill/temp.c:7 hit_ob`（北冥神功吸内力）都是这条链上的挂载点。武器 `inherit/weapon/blade.c:46 hit_ob` 也在此链（用于削减护甲 armor_prop）。

**Step 6 — 伤害落点**（:678-686）：
```c
damage = victim->receive_damage("qi", damage, me);            // 当前气血
if( random(damage) > apply/armor
    && (is_killing(victim->id) && ... || ...) )
    victim->receive_wound("qi", damage - apply/armor, me);    // 创伤上限
```
**`is_killing` 标志再次出现**：杀手模式下 `receive_wound` 触发概率从 `!random(7)`（无武器）/`!random(4)`（有武器）提升到 `!random(4)`/`!random(2)`（:680）。这就是"切磋只伤气血、杀人会留创伤"的机制根源。

**Step 7 — 经验奖励 + 投降/反 riposte**（:694-779）：
- 战斗中 `improve_skill` 成长（:702/:711）。
- 若双方都非 `is_killing` 且 `victim->query("qi")*2 <= max_qi`（血量过半），`me->remove_enemy(victim); victim->remove_enemy(me)` 自动休战，播 `winner_msg`（:749-758）。**这是 fight 模式自动收手的判定**。
- `action["post_action"]` 函数指针（:762）：招式结算后的回调，可挂额外效果。
- Riposte 反击（:766-779）：`TYPE_REGULAR` 攻击 `damage<1` 且 `victim->query_temp("guarding")` 时，按 `apply/speed` 对抗决定是否反击一招 `TYPE_QUICK` 或 `TYPE_RIPOSTE`。

### 2.2 `fight()` 的三种攻击类型

`combatd.c:787 fight(me, victim)` 决定本次 tick 怎么打：

- **对方忙碌/昏迷**（:799 `victim->is_busy() || !living(victim)`）：立即 `TYPE_QUICK` 快攻（伤害减半，`do_attack:620 damage /= 2`），并补一记副手 `do_attack`（双手互博 / 辟邪剑特殊条件 :807）。
- **勇敢判定**（:818 `random(victim->dex*3) < me->str*2 + apply/speed`）：成功则 `TYPE_REGULAR` 正常攻击。
- **否则进入 guarding 状态**（:837 `set_temp("guarding", 1)` + `guard_msg` 文案）：本回合防御，为下一回合 riposte 蓄能。

`attack_type` 三值来自 `include/combat.h:7-9`：`TYPE_REGULAR=0`、`TYPE_RIPOSTE=1`、`TYPE_QUICK=2`。

### 2.3 `skill_power()` 的概率权重

`combatd.c:288 skill_power(ob, skill, usage)`：

```c
level = ob->query_skill(skill);            // 含 skill_map 映射加成
level += apply/attack 或 apply/defense     // 装备临时加成
jingli_bonus = 50 + jingli*50/max_jingli  // 精力加成 50-150
if (level < 1) return combat_exp/20 * jingli_bonus/10
power = level^3 / 3                        // 三次方放大
return (power + combat_exp)/30 * str_or_dex/100 * jingli_bonus
```

**设计要点**：①技能等级三次方放大（`level^3/3`），高技能者碾压；②`combat_exp` 是兜底基线，无技能也有战力；③`jingli`（精力）是战斗续航资源，50%-150% 的动态系数；④`str`（攻）/`dex`（防）分离——力量主攻、敏捷主防。`s_combatd.c:212` 版本公式略简（`ob->query_str()/100` 而非 `/10`），是早期 prototype。

### 2.4 `receive_damage` / `receive_wound` / `receive_heal` / `receive_curing`（damage.c）

四类伤害/恢复 API，对应"三类属性 × 两层结构"：

| API | 文件:行 | 影响属性 | 语义 |
|-----|---------|---------|------|
| `receive_damage(type, damage, who)` | `damage.c:13` | `jing`/`qi`/`jingli` | 当前值，可被 heal_up 自然恢复，**负值即触发 unconcious/die** |
| `receive_wound(type, damage, who)` | `damage.c:39` | `jing`/`qi`（不含 jingli） | 创伤上限 `eff_<type>`，降低恢复天花板，**负值即触发 die** |
| `receive_heal(type, heal)` | `damage.c:68` | `jing`/`qi`/`jingli` | 恢复当前值，上限受 `eff_<type>`/`max_<type>` 约束 |
| `receive_curing(type, heal)` | `damage.c:85` | `jing`/`qi` | 恢复创伤上限 `eff_<type>`，上限受 `max_<type>` 约束 |

**三层属性结构**（以 qi 为例）：
```
max_qi  ── 固定上限（属性+等级决定）
eff_qi  ── 创伤上限（≤ max_qi，receive_wound 削减，receive_curing 恢复）
qi      ── 当前值（≤ eff_qi，receive_damage 削减，receive_heal 恢复）
```

**`receive_damage` 的副作用链**（`damage.c:13-37`）：
1. `set_temp("last_damage_from", who)`（:21）——写入伤害来源，供 `unconcious`/`die` 读取。
2. 若 `living() && objectp(who) && userp(who)`，额外 `set_temp("last_eff_damage_from", who->query("id"))`（:26）——**只记录玩家致死**，NPC 致死不记，用于 PKill 日志（`damage.c:210-214` `log_file("PKILL_DATA", ...)`）。
3. `set(type, val)` 扣减（:31-32），扣到 -1 即 clamp 到 -1（不无限负）。
4. `set_heart_beat(1)`（:34）——**点亮心跳**，确保后续 tick 会被检查。

`receive_wound` 同样写 `last_damage_from` 与 `set_heart_beat(1)`（:47, :63），且额外保证 `query(type) > val` 时把当前值也压到创伤上限（:61，**创伤会拖累当前值**）。

### 2.5 `heal_up()` 的战斗内/外恢复差异（damage.c:270）

`heal_up()` 每 tick 调用一次（`char.c:149`）。**战斗中恢复速率显著降低**：

| 属性 | 战斗中恢复 | 非战斗恢复 |
|------|-----------|-----------|
| `jing` | `con/9 + max_jingli/30` | `con/3 + max_jingli/10` |
| `qi` | `con/9 + max_neili/30` | `con/3 + max_neili/10` |
| `jingli` | `(str+dex)/12` | `(str+dex)/4` |
| `neili` | `skill("force",1)/6` | `skill("force",1)/2` |

且 `jingli` 可超 `max_jingli` 至 2 倍（:316），`neili` 同（:326），`jing` 上限 `max_jing*2`（`char.c:94` clamp）。这是"积攒内力"机制的来源。`water`/`food` 优先消耗（:281-285），耗尽则停止恢复——**饥渴会断奶**。

---

## 3. Effect 时效引擎（condition.c）

### 3.1 数据结构：`conditions` mapping

`feature/condition.c:8 mapping conditions;`。key 是 condition 名（如 `"bt_poison"`），value 是 `mixed info`——**类型由 condition daemon 自定义**。实际用法：
- `int duration`（剩余 tick 数）：`bt_poison.c`、`hanbing_damage.c`、`blind.c` 等。
- `string skill_type`：`perform.c`（`me->query_condition("perform")` 返回技能类型字符串，`skill2.c:100 apply_condition("perform", 5)`）。
- 复合结构：`drunk.c` 等只用 duration。

**`apply_condition` 不查重**（:79 注释明确："we don't check if the condition already exist before setting condition info. It is condition giver's reponsibility to check..."）。调用者若想叠加而非覆盖，必须自己读 `query_condition` 后累加（如 `combatd.c:1089 killer->apply_condition("pker", killer->query_condition("pker")+120)`、`snake_poison` 累加见 `inherit/skill/skill2.c:147-150`）。

### 3.2 `update_condition()` 的外部 daemon 调用模型

`condition.c:21 update_condition()` 是 Effect 引擎核心，由 `char.c:144 heart_beat` 每 `tick` 次调一次（`tick = 5 + random(10)`，`char.c:54`，即**每 6-15 个 heart_beat 周期结算一次 Effect**，不是每 tick 都跑）。

```c
cnd = keys(conditions);
while(i--) {
    cnd_d = find_object(CONDITION_D(cnd[i]));       // /kungfu/condition/<name>
    if (!cnd_d)  err = catch(call_other(CONDITION_D(cnd[i]), "???"));  // 懒加载
    if (err || !cnd_d) { map_delete(conditions, cnd[i]); continue; }  // 加载失败即移除
    flag = call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]]);
    if (!(flag & CND_CONTINUE)) map_delete(conditions, cnd[i]);       // 返回值不含 CONTINUE 即过期
}
```

**关键设计**：
1. **每个 condition 是独立 daemon 对象**（`CONDITION_D(cnd)` = `/kungfu/condition/<cnd>`，`include/globals.h:70`）。daemon 是无状态单例，被所有角色共享，`update_condition(me, info)` 接收受害者对象 + 该角色的 condition info。
2. **懒加载 + 容错**：daemon 不存在时 `call_other(..., "???")` 触发加载，加载失败写 `condition.err` 日志并从 mapping 移除（:44-51）——**Effect 引擎不会因单个坏 daemon 卡死整个 heart_beat**。
3. **不 catch 调用本身**（:54-58 注释）：`catch()` 开销大，daemon 自身保证不抛错。这是性能取舍。
4. **返回值协议**（`include/condition.h`）：
   - `CND_CONTINUE = 1`：保留 condition。
   - `CND_NO_HEAL_UP = 2`：禁止 `heal_up()`（`char.c:149` 检查 `cnd_flag & CND_NO_HEAL_UP`）。**但 grep 全仓库，没有任何 condition 实现返回 `CND_NO_HEAL_UP`**——这是一个**预留但未启用的 flag**，设计意图是让某些 Effect（如"运功封脉"）压制自然恢复，但实际未使用。
   - 返回 0 或无 `CND_CONTINUE`：condition 立即过期移除。

### 3.3 Effect 的四种行为模式（按 condition 实现归纳）

| 模式 | 代表 condition | 行为 | 源 |
|------|----------------|------|----|
| **持续伤害型** | `bt_poison.c` / `hanbing_damage.c` / `hyz_damage.c` / `juehu_damage.c` / `sanpoison.c` / `embedded.c` | 每 tick 调 `receive_damage`/`receive_wound` 扣血，自调 `apply_condition(cnd, duration-1)` 续期，`duration<1` 返回 0 过期 | `bt_poison.c:33-34`、`hanbing_damage.c:23-24`、`hyz_damage.c:30-31` |
| **状态标志型** | `blind.c` / `perform.c` / `killer.c` / `sleep.c` / `poisoned.c` | 不直接伤害，改 `temp("apply/...")` 数值或仅计时；`blind.c:30` 在 `let_know` 回调中恢复 `apply/attack`+`apply/defense` | `blind.c:26-35`、`perform.c:6-9` |
| **交互触发型** | `aphroclisiac.c` / `drunk.c` | 扫描 `all_inventory(environment(me))`，对在场角色触发 emote/战斗；`drunk.c:13` 超 limit 直接触发 `unconcious()` | `aphroclisiac.c:35-43`、`drunk.c:11-14` |
| **位移/场景型** | `city_jail.c` / `bonze_jail.c` / `dali_jail.c` / `embedded.c`(NPC 自动 remove) | `duration<1` 时 `me->move(...)` 移动角色到特定房间；`embedded.c:22-27` 让 NPC 自动 `do_remove` 拔暗器 | `city_jail.c:9-14`、`embedded.c:20-27` |

**Effect 生命周期**：`apply_condition`（注入）→ 多次 `update_condition`（每 6-15 tick 结算）→ 返回非 CONTINUE 即移除；或 `clear_condition()`（`damage.c:184 die()` 时调用，死亡清空所有 Effect）/ `clear_one_condition(cnd)`（定向清除）。

### 3.4 Effect 注入点（apply_condition 的调用方）

`apply_condition` 在仓库中被以下系统调用：

| 注入方 | 文件 | 注入的 condition | 触发场景 |
|--------|------|-----------------|---------|
| 武器 `hit_ob` | `inherit/skill/skill.c:147` / `skill2.c:147` | `snake_poison` | 涂毒武器命中 |
| 毒虫 `hit_ob` | `clone/beast/dufeng.c:57` | `insect_poison` | 毒蜂咬伤 |
| 药物 `feed_ob` | `clone/drug/badan.c:32-42` / `xueteng.c:31` | `insect_poison`/`snake_poison`/`xx_poison`/`bonze_drug` | 服用毒药/解药 |
| 战斗奖励 | `combatd.c:1047,1089` | `killer`（城内 PK 通缉）/`pker`（PK 惩罚计时） | 玩家被杀时给杀手挂上 |
| 招式 perform | `inherit/skill/skill2.c:100` | `perform`（5 tick 冷却） |施展绝技后禁止换武器 |
| 状态自续 | 各 `condition/*.c` 内部 | `apply_condition(cnd, duration-1)` | Effect 自我续期 |

---

## 4. 状态播报（message / damage_msg / status_msg）

### 4.1 三层播报 API

- **`message_vision(str, me, victim)`**（combatd.c:732 等大量调用）：面向房间所有人的视觉消息，`$N`/`$n`/`$p`/`$l`/`$w` 占位符替换。`combatd.c:716-730` 做 `$l`(部位)/`$w`(武器名) 替换。
- **`tell_object(ob, str)`**（damage.c:125 等）：仅受害者本人可见。`unconcious()`/`revive()` 的"眼前一黑"/"慢慢有了知觉"都是 `message("system", ..., this_object())`（:125, :146）——用 `system` class 只发给本人。
- **`message("vision", str, environment(me), ({me}))`**（bt_poison.c:11 等）：面向房间**除本人外**所有人。第四参数 `({me})` 是排除列表。

### 4.2 伤害分级文案（damage_msg）

`combatd.c:68 damage_msg(damage, type)` 按 `damage` 数值区间返回不同严重度的文案，按 `type`（`擦伤`/`割伤`/`劈伤`/`砍伤`/`刺伤`/`跌伤`/`鞭伤`/`咬伤`/`瘀伤`/`挫伤`/`内伤`/default）分系。每个 type 有 6 档（<20/<40/<80/<120/<160/else），最后一档通常是"露骨"/"对穿而出"/"像一捆稻草般飞了出去"等夸张描述。

**关键耦合**：`action["damage_type"]`（招式定义的字段）决定走哪个 case，所以**不同武功招式有不同的伤害文案系**——这是"招式手感"的主要来源。

### 4.3 状态条文案（status_msg / eff_status_msg / report_status）

`combatd.c:230 eff_status_msg(ratio)` 与 `:255 status_msg(ratio)` 按 `eff_qi/max_qi` 或 `qi/max_qi` 比例（100/95/90/80/60/40/30/20/10/5 档）返回彩色状态描述（HIG→HIY→HIR→RED 渐变）。`report_status(ob, effective)`（:278）在 `do_attack` 末尾调用（:746），把受伤者的当前状态以 `( $N看起来... )` 格式播给房间。

**三层状态可视化**：
- `eff_status_msg`（创伤比例，:746 `report_status(victim, wounded)` 当 wounded=1）。
- `status_msg`（当前气血比例，:746 wounded=0）。
- `COMBAT_D->announce(ob, "dead"/"unconcious"/"revive")`（combatd.c:966）：读 `ob->query("dead_message"/"unconcious_message"/"revive_message")` 的角色专属死亡/昏迷/苏醒文案。

### 4.4 战斗事件播报（announce / winner_msg / catch_hunt_msg）

`combatd.c:16-59` 定义了四组文案数组：
- `guard_msg`（5 条）：防御蓄势时播。
- `catch_hunt_human_msg`/`catch_hunt_beast_msg`/`catch_hunt_bird_msg`：`start_hatred` 自动开战时播（按 race 分系）。
- `winner_msg`（6 条人类）/`winner_animal_msg`（3 条野兽）：`fight` 模式自动休战时播（:756-758）。

---

## 5. 死亡两段式判定（char.c heart_beat / damage.c）

### 5.1 heart_beat 的四段死亡判定（char.c:99-115）

```c
// (A) 硬死亡快道：创伤上限 eff_qi/eff_jing < 0
if (my["eff_qi"] < 0 || my["eff_jing"] < 0) {
    remove_all_enemy(); die(); return;
}

// (B) 当前值耗尽：qi/jing/jingli < 0
if (my["qi"] < 0 || my["jing"] < 0 || my["jingli"] < 0) {
    remove_all_enemy();
    if (living(this_object()))      unconcious();      // 首次耗尽 → 昏迷
    else if (disable_type == " <昏迷不醒>")  die();   // 已昏迷再负 → 死
    return;
}

// (C) 战斗循环：attack() ...
```

**两段式核心**（:107-113）：
- **第一段（昏迷）**：`living()` 为真（正常活动）时，`qi`/`jing`/`jingli` 任一为负 → `unconcious()`，角色进入 `<昏迷不醒>` disable 状态。
- **第二段（死亡）**：已昏迷（`!living()` 且 `disable_type==" <昏迷不醒>"`）时，再次出现负值 → `die()`。

**设计含义**：昏迷是"软死亡"——玩家不会一被打空就死，先有一次"晕倒缓冲"。但**昏迷状态下敌人不会停手**（`attack.c:70 clean_up_enemy` 不清 `is_killing` 的昏迷敌人，`combatd.c:799 fight` 走 `TYPE_QUICK` 快攻昏迷者），所以昏迷者会被继续打到死。这是 LPC 战斗的残酷性来源。

### 5.2 `unconcious()` 流程（damage.c:105-135）

1. `!living()` 即返回（避免重复昏迷）。
2. `wizardp && env/immortal` 即返回（巫师不死）。
3. `winner_reward(defeater, this)` 给击败者奖励（:114）。
4. `remove_all_enemy()` 清敌对（但保留 killer）。
5. `interrupt_me()` 打断所有进行中的动作（打坐/炼气等，:122 注释）。
6. `dismiss_team()` 强制解散队伍（:124）。
7. `disable_player(" <昏迷不醒>")` 进入 disable 状态，`block_msg/all=1` 屏蔽所有消息接收（:131，玩家"眼前一黑"）。
8. `set("jing"/"qi"/"jingli", 0)` 三属性归零（:128-130）。
9. `COMBAT_D->announce(this, "unconcious")` 播昏迷文案（:132）。
10. `call_out("revive", random(100 - con) + 30)`（:134）——**苏醒时间是 `30 + random(100-con)` 秒**，`con`（体质）越高醒得越快，但至少 30 秒。

### 5.3 `revive()` 苏醒（damage.c:137-150）

- `remove_call_out("revive")` 取消待执行的苏醒（:139）。
- `while(environment()->is_character()) move(environment(environment))`（:140）——如果被装进容器/生物体内，逐层移出到真实房间。
- `enable_player()` 恢复行动能力（:142）。
- `quiet==0` 时 `announce(this, "revive")` + 播 "慢慢地你终于又有了知觉"（:143-147）。

### 5.4 `die()` 流程（damage.c:152-253）

1. **`no_death` 房间降级**（:159-177）：若 `environment()->query("no_death") && userp(this)`，降级为 `unconcious()` + `remove_call_out("revive")`，直接返回——**安全区不死**。
2. `!living()` 时先 `revive(1)` 静默苏醒（:179）——确保死亡判定在"活体"状态下执行。
3. `wizardp && env/immortal` 即返回（:180）。
4. `clear_condition()` 清空所有 Effect（:184）。
5. `delete("poisoner")` 清毒源（:185）。
6. `announce(this, "dead")` 播死亡文案（:187）。
7. **`death_penalty(this)`**（:190，仅玩家 + 非 no_death 房间）：见下节。
8. `killer = query_temp("last_damage_from")`（:192）：
   - 有 killer 对象：`set_temp("my_killer", killer->id)` + `killer_reward(killer, this)`（:193-194）。
   - 无 killer 但 `stringp(killer)`（毒名等）：`CHANNEL_D->do_channel(rum_ob, "rumor", ...)` 播"被毒死"谣言（:200-205）。
9. **死亡日志**（:209-224）：`log_file("PKILL_DATA"/"PLAYER_DEATH", ...)` 区分玩家杀/NPC杀/字符串杀三类。
10. `CHAR_D->make_corpse(this, killer)` 造尸体并 `move` 到当前房间（:226-228）——**尸体是独立物品对象**。
11. `remove_all_killer()` + `all_inventory(environment())->remove_killer(this)`（:230-231）双向清敌。
12. **玩家分支**（:233-250）：
    - `set("jing"/"qi"/"jingli", 1)` + `set("eff_jing"/"eff_qi", 1)`（:236-238）——**归 1 不归 0**，避免再次触发死亡判定。
    - `no_death` 房间：`set("eff_jing"/"eff_qi", max)` 直接满血返回（:239-243）。
    - 否则 `dismiss_team()` + `save()` 存档 + `ghost = 1` + `move(DEATH_ROOM)` + `DEATH_ROOM->start_death(this)`（:244-248）——**进入地府流程**。
    - `MARRY_D->break_marriage(this)` 解除婚姻（:249）。
    - 师徒关系特殊处理（:250）。
13. **NPC 分支**（:252）：`destruct(this_object())`——NPC 死了直接销毁。

### 5.5 `death_penalty()`（combatd.c:987-1025）

仅对玩家，扣除：
- `clear_condition()` 再清一次 Effect（:995）。
- `death_times += 1`（若 `combat_exp >= 10000 * death_times`，:997-998）——**死亡次数门槛递增**。
- `shen -= shen/20`（善恶值扣 5%，:999）。
- `behavior_exp -= behavior_exp/20`（行为经验扣 5%，:1000）。
- `combat_exp -= combat_exp/100`（封顶 5000，:1001-1011）——**战斗经验惩罚是主要损失**。
- `potential -= potential/2`（潜能减半，:1007-1008）。
- `balance` 超过 10000 部分扣半（存款惩罚，:1013-1015）。
- `death_count += 1`（:1016）。
- `delete("vendetta")` 清世仇（:1017）。
- `thief` 减半（:1020-1021，小偷标记）。
- `skill_death_penalty()`（`skill.c:121`）——**所有技能等级 -1**（learned 映射联动），`skill_map = 0` 清技能映射。

### 5.6 `killer_reward()`（combatd.c:1027-1096）

给杀手：
- `killer->killed_enemy(victim)` 调 mudlib apply（:1039）。
- `PKS += 1`（玩家击杀玩家计数，:1043）/`MKS += 1`（杀 NPC 计数，:1066）。
- `pktime = mud_age`（:1045，PK 冷却起点）。
- 城内 PK：`killer->apply_condition("killer", 100)`（:1047，**官府通缉 100 tick**）。
- `shen -= victim_shen/10`（杀正派掉善值，:1076-1077）。
- `behavior_exp -= victim_behavior_exp/10`（:1078）。
- `apply_condition("pker", query_condition("pker")+120)`（:1089，PK 惩罚计时累加）。
- `vendetta/<vmark> += 1`（:1092，世仇累加）。
- 撒谣言 `"被X杀死了"`（:1060-1061）。

### 5.7 `reincarnate()` 复活（damage.c:255-264）

```c
ghost = 0;
set("jing", max_jing);  set("qi", max_qi);
set("eff_jing", max_jing);  set("eff_qi", max_qi);
set("jingli", max_jingli);  set("neili", max_neili);
```

**满血复活**，所有当前值 + 创伤上限 + 内力精力全满。注意：**不恢复 `combat_exp`/`shen`/`potential`/`skill`/`balance`**——这些在 `death_penalty` 里扣的东西是永久损失，复活不补。这是 LPC 死亡惩罚的设计哲学：**死亡是真实损失，不是"读档"**。

---

## 6. 鬼魂与地府轮回（ghost / d/death/）

### 6.1 `ghost` 标志与可见性

`feature/damage.c:9 int ghost = 0;`，`is_ghost()`（:11）返回 `ghost`。

`inherit/char/char.c:181-186 visible(ob)` 用 ghost 决定能否看见：
```c
if (ob->is_ghost()) {
    if (is_ghost()) return 1;                          // 鬼见鬼
    if (query_temp("apply/astral_vision")) return 1;   // 阴阳眼
    return 0;                                          // 活人看不见鬼
}
```

**设计含义**：死亡后玩家以鬼魂形态进入地府，活人看不见他——这是"阴阳两隔"的社交隔离。

### 6.2 地府区流程（d/death/）

玩家死亡 → `ghost=1` → `move(DEATH_ROOM)`（`include/login.h:23 #define DEATH_ROOM "/d/death/gate.c"`）→ `DEATH_ROOM->start_death(this)`（`damage.c:248`）。

**注意**：`start_death` 函数在仓库中**无定义**（grep 全仓只在 3 处 damage.c 调用，无任何 `void start_death` 定义）——该函数可能缺失或本应存在于 `gate.c` 但被删除。实际触发路径是 `gate.c` 的 `init()`（玩家进入房间时触发）+ 房间内 NPC `d/death/npc/wgargoyle.c` 的 `init()` 链式 `call_out("death_stage", 30, ...)`。

**地府区拓扑**（10 个房间，~580 行）：

```
gate (鬼门关) ──north──► gateway (酆都城门) ──north──► road1 ──north──► road2 ──north──► road3 (尽头)
                                              │                      │
                                              ├──west──► inn1 (小店)   └──west──► inn2 (黑店)
                                              └──south── 不可回头（gateway.valid_leave 拦截）
另：death (死刑室) / hell (十八层地狱) / blkbot (空房) / block / noteroom (犯罪记录室)
```

**关键机制**：
- **`gate.c:32-37 init()`**：玩家进入鬼门关时，`all_inventory` 遍历销毁所有非 character 物品 + `clear_condition()`——**鬼魂不带任何物品与 Effect 进地府**。
- **`gateway.c:25-32 valid_leave()`**：`dir=="south"` 返回"没有回头路了"——**单向流**，只能向北走。
- **`road2.c:21-40 valid_leave()`**：`long_road` temp 计数到 5 才放行——**迷雾循环**，玩家需走 5 次才能通过。
- **`inn1.c:45-78 do_stuff()`**：玩家"问自己回家"后，`ob->reincarnate()` + `move("/d/city/wumiao")`——**地府轮回的出口之一**。
- **`wgargoyle.c:38-50 death_stage()`**：白无常 NPC init 后 `call_out("death_stage", 30, ob, 0)`，每 5 秒播一条 `death_msg`（共 5 条，:16-22），最后 `ob->reincarnate()` + drop 所有物品 + `move(REVIVE_ROOM)`——**地府轮回的出口之二，全自动**。

**轮回的两条路径**：
1. **被动等待**（wgargoyle.c）：30 秒 + 5×5=25 秒 ≈ 55 秒后自动复活。
2. **主动探索**（inn1.c）：玩家走到 inn1 触发"问影子"分支立即复活。

两条路径最终都调 `reincarnate()`（满血）+ 移动到复活点（`REVIVE_ROOM` 或 `/d/city/wumiao` 或 `/d/xiakedao/shatan` 侠客岛特例）。

### 6.3 `no_death` / `no_fight` 安全区

- `no_fight`（战斗禁制）：`attack.c:54` / `cmds/std/kill.c:10` 等拦截开战。
- `no_death`（死亡禁制）：`damage.c:159 die()` 第一分支降级为 `unconcious`——**安全区只晕不死**。地府区全部 `no_fight`（鬼不能打架）但**不** `no_death`。

---

## 7. 武功招式调度（inherit/skill + kungfu/skill + kungfu/class）

### 7.1 技能三层映射（skill.c）

`feature/skill.c` 维护四个 mapping（:9-12）：
- `skills`（`skill → level`）：技能等级表。
- `learned`（`skill → 经验点`）：升级进度，超过 `(level+1)^2` 则 `level++`（:176）。
- `skill_map`（`type → skill`）：**技能映射**，把 `unarmed`/`dodge`/`parry`/`force` 等"类别"映射到具体武功（如 `dodge → douzhuan-xingyi`）。`map_skill(skill, mapped_to)`（:42）。
- `skill_prepare`（`type → skill`）：**预备技能**，双手互博时主/副手各备一个。`prepare_skill(skill, mapped_to)`（:62）。

`query_skill(skill, raw)`（:94）的非 raw 返回值：
```c
s = apply/<skill>          // 临时加成（装备/Effect）
s += skills[skill]/2       // 基础技能一半
s += skills[skill_map[skill]]  // 映射技能全值
```
即**有效技能 = 临时加成 + 基础/2 + 映射武功**。这是为什么"装备了 dodge 类武功"会比裸 dodge 强的核心公式。

### 7.2 招式 action 的来源（reset_action）

`attack.c:143 reset_action()`：
- 有武器 + `SELF_ACTION` flag：用 weapon 自带的 `actions`。
- 有武器 + 映射武功：`set("actions", (: call_other, SKILL_D(skill), "query_action", me, ob :))`——**actions 是函数指针**，每次攻击动态生成。
- 无武器 + 映射武功：同上但不传 weapon。
- 无映射：用 weapon 的 `actions` 或 `default_actions`。

`action` mapping 字段（combatd.c:384 读取）：
- `action`：招式文案（如 `$N一招「亢龙有悔」向$n的$l攻去！`）。
- `damage_type`：伤害类型（`刺伤`/`劈伤`/`内伤`/...），决定 `damage_msg` 文案系。
- `damage`：招式伤害加成。
- `force`：招式内力加成。
- `dodge`：招式闪避加成（写入 `temp("fight/dodge")`，`combatd.c:415`）。
- `weapon`：占位符替换用的武器名（空手时用 `手指`/`拳头`/`手掌`/`手爪`，:721-730）。
- `post_action`：招式后效回调（:762）。

### 7.3 `hit_ob()` — 命中时的 effect 注入钩子

`inherit/skill/skill.c:142 hit_ob(me, victim, damage_bonus, factor)` 是**技能基类**的默认实现，专门给武器涂毒：
```c
if (weapon && weapon->query("poison_applied") > 0) {
    victim->apply_condition("snake_poison", random(poison_applied + weapon_damage) + existing);
    if (!victim->is_killing(me->id)) victim->kill_ob(me);  // 中毒自动反击
    if (victim->poisoner != me) victim->poisoner = me;
    return HIR "$n只觉得伤口上一麻！\n" NOR;
}
```

**子类覆盖示例**：
- `inherit/skill/force.c:6 hit_ob`：内力对抗计算 `damage = myneili/20 + factor - yourneili/25`，可触发"内力反震"（damage<0 时反向伤害攻击者，:33-49）。
- `inherit/skill/temp.c:7 hit_ob`：北冥神功特例——`victim` 会吸 `me` 的 `max_neili`（:19-20），并在战斗中给 victim 加 potential/combat_exp（:22-24）。这是"以彼之道还施彼身"的 effect 实现。
- `inherit/weapon/blade.c:46 hit_ob`：刀类武器削减护甲（`armor_prop/armor -= 1`，`victim->add_temp("apply/armor", -1)`），并按残破程度改 `name`/`long`/`value`——**武器特效直接改装备状态**。

### 7.4 `perform_action()` — 主动绝技（skill2.c:82）

```c
int perform_action(object me, string arg) {
    sscanf(arg, "%s %s", action, target);
    file = this_object()->perform_action_file(action);
    return call_other(file, "perform", me, target_ob);
}
```

调用方：`inherit/char/npc.c:201 perform_action(action)` 解析 `"martial.act"` 格式（如 `"xianglong-zhang.leiting"`），调 `SKILL_D(martial_skill)->perform_action(this, act)`。

**perform 文件示例**（`kungfu/skill/xianglong-zhang/leiting.c:32 perform(me, target)`）：
1. 前置检查链：`target` 存在 + `is_character` + `is_fighting`（:38-42）、空手（:45）、`str>=30`（:47）、`force` 映射必须是 `huntian-qigong`（:50）、`force>=135`（:53）、`strike>=135`（:56）、`neili` 足够（:59）、不在其他 perform 中（:62）、无 `sanhui_busy`（:65）、无 `hyz_damage` 内伤（:68）。
2. 播招式文案（:71）。
3. **临时改属性**：`add_temp("apply/attack", skill/3)` / `apply/strike` / `apply/damage`（:75-77）。
4. `COMBAT_D->do_attack(me, target, weapon)`（:79）——**复用主攻击管线**。
5. 扣 `neili -= amount*3` / `jingli -= amount`（:81-82）。
6. **恢复属性**（:84-86）——临时加成只对这一击生效。
7. `start_busy(1+random(2))`（:88）——**绝技后强制 busy**。

### 7.5 `exert_function()` — 内功主动技（skill.c:62）

`exert <function> [<target>]` 命令解析，调 `exert_function_file(func)` 返回的文件 `exert(me, target_ob)`。典型 exert：

`kungfu/skill/huntian-qigong/powerup.c:17 exert(me, target)`：
1. `target != me` 拒绝（:19）。
2. `neili < 1000` 拒绝（:22）。
3. 扣 `neili -= skill*6/5` / `jingli -= skill/5`（:28-29）。
4. **`add_temp("apply/attack"/"dodge"/"parry", skill/3)`**（:36-38）+ `set_temp("powerup", 1)`。
5. `start_call_out( (: call_other, __FILE__, "remove_effect", me, skill/3 :), skill/8)`（:41）——**延时回调移除加成**，持续 `skill/8` tick。
6. `is_fighting()` 时 `start_busy(3)`（:43）。
7. `remove_effect(me, amount)`（:47-52）：扣回 `apply/*` + `delete_temp("powerup")`。

### 7.6 NPC 自动战斗 AI（npc.c chat）

`inherit/char/npc.c:97 chat()` 在 `char.c:136 heart_beat` 中对非 user 调用（`if (!userp(this_object())) this_object()->chat()`）：

1. **内功自动恢复**（:100-107）：`neili > 100` 时按比例自动 `exert refresh/recover/regenerate`——NPC 会自己用内功回血回精。
2. **`chat_chance_combat` vs `chat_chance`**（:115）：战斗中走 `chat_msg_combat`，非战斗走 `chat_msg`。`random(100) < chance` 时触发，`stringp` 播报、`functionp` 执行（:119-123）——**NPC 的随机行为/招式触发器**。
3. 默认行为：`random_move()`（:130）、`cast_spell`/`exert_function`/`perform_action`（:154-206）——NPC 可在 chat 中自动施法/运功/放绝技。

### 7.7 门派归属（kungfu/class）

`kungfu/class/` 下按门派组织（`baituo`/`dali`/`emei`/`gaibang`/`gumu`/`huashan`/`lingjiu`/`mingjiao`/`murong`/...）。门派通过 `family/family_name` 字段标识（如 `sanpoison.c:22 me->query("family/family_name")=="星宿派"` 检查），同一武功对不同门派有不同行为（星宿派中 sanpoison 不掉血而用化功大法抵御，:23-29）。**门派是 effect 的条件分支，不是独立机制**。

---

## 8. 装备数值（inherit/weapon + inherit/armor）

### 8.1 装备插槽与双手模型（equip.c）

`feature/equip.c` 的 `wield()`（:46）/`wear()`（:7）/`unequip()`（:109）管理装备：

**武器插槽**（wield :60-98）：
- `temp("weapon")`：主手武器。
- `temp("secondary_weapon")`：副手武器（需 `SECONDARY` flag，:82）。
- `temp("armor/shield")`：盾牌（占用副手，:68）。
- `TWO_HANDED`（weapon.h:16 = 1）：双手武器，需空出主+副+盾（:65-69）。
- 切换逻辑（:74-97）：旧武器若可作副手则降为 secondary，否则需先放下。

**防具插槽**（wear :28-32）：`armor_type` 决定槽位，同类型只能穿一件（`owner->query_temp("armor/"+type)` 检查）。类型见 `inherit/armor/`：`armor`/`boots`/`cloth`/`finger`/`hands`/`head`/`neck`/`shield`/`surcoat`/`waist`/`wrists`。

### 8.2 装备数值注入 `apply` temp mapping

`equip.c:33-41 wear()` 把 `armor_prop` 累加到 `owner->query_temp("apply")`：
```c
apply = keys(armor_prop);
for (i=0; i<sizeof(apply); i++)
    if (undefinedp(applied_prop[apply[i]]))
        applied_prop[apply[i]] = armor_prop[apply[i]];
    else
        applied_prop[apply[i]] += armor_prop[apply[i]];   // 累加
owner->set_temp("apply", applied_prop);
```

`equip.c:100-102 wield()` 类似，但用 `add_temp("apply/"+key, val)` 累加武器 prop。

**`apply` mapping 是装备数值的统一汇聚点**，被多处读取：
- `skill.c:99 query_skill`：`s = query_temp("apply/" + skill)`——装备直接加技能等级。
- `combatd.c:300-306 skill_power`：`apply/attack`、`apply/defense`、`apply/dodge`、`apply/speed`、`apply/armor`、`apply/damage`。
- `combatd.c:680`：`apply/armor` 作为护甲值，决定 `receive_wound` 是否触发。
- `char.c:183 visible`：`apply/astral_vision`（阴阳眼，见鬼）。

### 8.3 武器分类与 flag（weapon.h + inherit/weapon/）

`include/weapon.h` 定义 15 类武器路径宏 + 5 个 flag：
- `TWO_HANDED=1`：双手。
- `SECONDARY=2`：可副手。
- `EDGED=4`：刃类（刀/剑）。
- `POINTED=8`：尖类（矛/枪）。
- `LONG=16`：长兵器。
- `SELF_ACTION=32`：武器自带 actions（不走技能映射）。

`inherit/weapon/blade.c:18 init_blade(damage, flag)` 设 `weapon_prop/damage` + `flag |= EDGED` + `skill_type="blade"` + `actions` 指向 `WEAPON_D->query_action` + `verbs=({"slash","slice","hack"})`。

**武器与技能的关系**：`attack_skill = weapon->query("skill_type")`（`combatd.c:372`），决定走哪个 `SKILL_D(attack_skill)` 的 `query_action`/`hit_ob`。即"用刀走刀法、用剑走剑法"。

### 8.4 武器/护甲特效钩子（hit_ob / hit_by）

- **武器 `hit_ob(me, victim, damage_bonus, factor)`**：在 `combatd.c:588-595 do_attack` Step 5 调用，可返回 string/int/mapping 改伤害。`blade.c:46` 削护甲是典型。
- **护甲 `hit_by(me, victim, damage, weapon)`**：在 `combatd.c:644-656` 调用（仅 `is_special()` 护甲），可返回 string/int/mapping 改写最终伤害。`cloth` 槽位才触发（:644 `query_temp("armor/cloth")`）。
- **dodge 技能 `hit_by(me, victim, damage)`**：`combatd.c:660-672`，仅 `is_special()` 的 dodge 技能触发（如特殊闪避招式可改伤害）。

**三者都返回 `mapping ["result"]+["damage"]` 的协议**，与 `hit_ob` 一致——这是 effect 注入的统一接口。

---

## 9. 与周边系统的耦合链（综合）

### 9.1 命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活 完整闭环

```
玩家 kill <obj>
  └► cmds/std/kill.c:74 me->kill_ob(obj)
       └► attack.c:51 kill_ob() 写 killer 列表 + set_heart_beat(1) + 通知对方
            └► char.c:60 heart_beat() 下一 tick
                 └► char.c:132 attack()
                      └► attack.c:208 attack() → select_opponent() → COMBAT_D->fight()
                           └► combatd.c:787 fight() → do_attack(me, victim, weapon, TYPE_REGULAR)
                                ├► (Step5) weapon->hit_ob / SKILL_D(force)->hit_ob   [Effect 注入]
                                ├► (Step6) victim->receive_damage("qi", damage, me)
                                │    └► damage.c:13 set_temp("last_damage_from", me) + set_heart_beat(1)
                                ├► (Step6) victim->receive_wound("qi", damage-armor, me)  [if is_killing]
                                ├► (Step6) combatd.c:678 message_vision(damage_msg)       [状态播报]
                                └► (Step7) report_status(victim, wounded)                 [状态条]
            └► 下一 tick，victim 的 heart_beat:
                 ├► char.c:100 check eff_qi/eff_jing < 0 → die()                    [硬死]
                 ├► char.c:108 check qi/jing/jingli < 0
                 │    ├► living() → unconcious() → call_out("revive", 30+random(70)) [昏迷]
                 │    └► <昏迷不醒> → die()                                          [两段死]
                 └► char.c:144 tick-- ==0 → update_condition()                       [Effect 结算]
                      └► condition.c:62 CONDITION_D(cnd)->update_condition(me, info)
                           ├► bt_poison.c:33 receive_wound("jing", ...)             [Effect 回灌伤害]
                           │    └► damage.c:39 set_temp("last_damage_from", "身中...死掉了")
                           ├► apply_condition(cnd, duration-1)                       [续期]
                           └► message_vision/tell_object                             [Effect 播报]
            └► die() (damage.c:152):
                 ├► clear_condition() + announce("dead") + death_penalty()           [永久损失]
                 ├► killer_reward(killer) → apply_condition("killer"/"pker")        [给杀手挂 Effect]
                 ├► CHAR_D->make_corpse() → 尸体物品                                 [战利品]
                 ├► ghost=1 + move(DEATH_ROOM) + start_death()                       [进地府]
                 └► wgargoyle.c:38 death_stage() call_out 链 → reincarnate()          [轮回复活]
                      └► damage.c:255 ghost=0 + 满血 + move(REVIVE_ROOM)             [复活点重生]
```

### 9.2 与移动系统的耦合

- `team.c:32 follow_path()` 移动前无条件 `remove_all_enemy()`——**移动清敌**。
- `attack.c:70 clean_up_enemy()` 中 `environment(enemy[i])!=environment()` 即移除——**跨房间解战**。
- `combatd.c:799 fight()` 中 `victim->is_busy() || !living(victim)` 触发快攻——**昏迷/忙碌者被持续攻击**。
- 地府 `gateway.c:25 valid_leave()` 单向流、`road2.c:21` 迷雾循环——**地府是受控场景**。

### 9.3 与存档系统的耦合

- `damage.c:245 die()` 玩家分支 `this_object()->save()`——**死亡时强制存档**（保存 ghost=1 状态，防止回档复活）。
- `combatd.c:1023 death_penalty()` 末尾 `victim->save()`——**惩罚扣完立即存档**（防止掉线规避）。
- `char.c:167 query_idle > IDLE_TIMEOUT` → `user_dump(DUMP_IDLE)`——**挂机超时踢线**。

### 9.4 与经济系统的耦合

- `death_penalty` 扣 `balance` 超过 10000 部分的一半（`combatd.c:1013-1015`）——**死亡有存款惩罚**。
- `killer_reward` 给杀手加 `vendetta/<vmark>` 世仇计数（:1092）——**世仇是经济社交资源**。

### 9.5 与社交系统的耦合

- `die()` 解除婚姻 `MARRY_D->break_marriage(this)`（:249）。
- `die()` 解散队伍 `dismiss_team()`（:244）。
- `unconcious()` 也解散队伍（:124）。
- `visible()` 鬼魂隔离（`char.c:181`）——**死亡切断社交可见性**。
- `killer_reward` 撒谣言 `CHANNEL_D->do_channel(rum_ob, "rumor", ...)`（:1060）——**死亡广播**。

---

## 10. 设计警示与过时模式（现代视角）

> 以下为机制层面的设计风险，供现代评审组与红队参考。具体玩法/心理/商业批判不在此展开。

1. **`killer` 列表改变伤害结算**（`combatd.c:680`）：意图标志直接影响数值（创伤概率翻倍），现代设计更倾向于"切磋/生死"只影响奖励/惩罚，不影响战斗数学本身。否则"假装切磋实则偷袭"的玩法无法成立。
2. **`MAX_OPPONENT=4` 硬编码**（`attack.c:12`）：围攻上限是定值，无法按场景/角色调整。现代 MMO 通常用威胁值/aggro 表 + 软上限。
3. **两段式死亡的"昏迷缓冲"被快攻绕过**（`combatd.c:799`）：昏迷者被 `TYPE_QUICK` 持续攻击，缓冲形同虚设。现代设计要么让昏迷者完全无敌、要么有"处决"机制显式终结。
4. **`death_penalty` 永久损失 `combat_exp`/`skill`/`potential`**（`combatd.c:987`、`skill.c:121`）：经验/技能等级不可逆损失，现代玩家心理难以接受（"一死回到解放前"）。现代 MMO 多用"装备耐久损失"/"经验债"/"复活惩罚时长"等可恢复机制。
5. **Effect 引擎与 heart_beat 强耦合**（`condition.c:21` + `char.c:144`）：Effect 结算频率取决于 `tick = 5+random(10)`，且 Effect daemon 在 heart_beat 中**不 catch 调用**（:58 注释明说性能取舍）——单个 Effect daemon 抛错会卡死玩家 heart_beat。现代设计应隔离 Effect 执行（独立调度器/协程）。
6. **`CND_NO_HEAL_UP` 预留未用**（`condition.h` + `char.c:149`）：flag 定义了但全仓无实现，是"死代码"风险——要么移除要么补全语义。
7. **`start_death` 函数缺失**（`damage.c:248` 调用但无定义）：依赖 NPC `init()` 间接触发，是脆弱的隐式契约。现代设计应显式定义死亡流程入口。
8. **`receive_damage` 的 `who` 参数同时接受 `object` 与 `string`**（`damage.c:21` vs `bt_poison.c:33`）：弱类型，`last_damage_from` 可能是角色对象也可能是"身中西域灵蛇毒死掉了"字符串，下游 `objectp(killer)` 判断（`damage.c:192`）才能区分。现代设计应分离"伤害来源对象"与"致死原因字符串"。
9. **武器 `hit_ob` 直接改装备状态**（`blade.c:46` 削护甲 `armor_prop/armor -= 1` + 改 `name`/`value`）：战斗中改装备元数据，破坏装备不可变契约，难以回滚/序列化。
10. **`update_condition` 不查重也不去重**（`condition.c:79` 注释）：同一 condition 可被多次 apply 覆盖，调用者需自己累加——这是 bug 温床（`snake_poison` 累加逻辑分散在 `skill.c:147`/`skill2.c:147`/`badan.c:32` 多处，行为不一致）。

---

## 11. 未决问题（供后续抽象阶段决策）

1. **Effect 引擎是否应脱离 heart_beat 独立调度？** LPC 把战斗 tick 与 Effect tick 缝在一起（且 Effect 只每 6-15 tick 跑一次），现代引擎是否应分两个调度器（战斗回合 vs Effect 时钟）？
2. **`killer`/`enemy` 双列表是否应合并为"敌对关系 + 意图"的单一结构？** 现代设计倾向后者（一个关系对象带 intent 字段）。
3. **死亡两段式是否应保留？** 现代设计是否用"倒地"（downed）+ "处决"（execute）替代昏迷/死亡二分？
4. **`last_damage_from` 的多态（object/string）是否应拆为 `last_attacker` + `death_cause`？**
5. **`apply` temp mapping 作为装备数值汇聚点是否应改为显式的"修饰器栈"？** LPC 用一个 mapping 累加所有装备 prop，现代设计倾向"修饰器/修饰符"（modifier）模式，可追溯来源。
6. **Effect daemon 的 `CND_CONTINUE`/`CND_NO_HEAL_UP` 协议是否应扩展为更丰富的生命周期回调？**（on_apply/on_tick/on_expire/on_dispel 等）

---

## 附录：关键源码指针速查

| 机制 | 文件 | 关键函数/对象 |
|------|------|--------------|
| 敌对列表 | `feature/attack.c` | `enemy`/`killer`(:15-16)、`fight_ob`(:40)、`kill_ob`(:51)、`select_opponent`(:79)、`MAX_OPPONENT=4`(:12) |
| 命中判定 | `adm/daemons/combatd.c` | `do_attack`(:340)、`fight`(:787)、`skill_power`(:288)、`auto_fight`(:852) |
| 伤害结算 | `feature/damage.c` | `receive_damage`(:13)、`receive_wound`(:39)、`receive_heal`(:68)、`receive_curing`(:85)、`heal_up`(:270) |
| 死亡判定 | `inherit/char/char.c` | `heart_beat`(:60)、:99-115 四段判定 |
| 昏迷/复活 | `feature/damage.c` | `unconcious`(:105)、`revive`(:137)、`die`(:152)、`reincarnate`(:255) |
| Effect 引擎 | `feature/condition.c` | `conditions`(:8)、`update_condition`(:21)、`apply_condition`(:79)、`clear_condition`(:105) |
| Effect 内容 | `kungfu/condition/*.c` | `bt_poison`/`hanbing_damage`/`blind`/`embedded`/`city_jail`/`aphroclisiac`/`drunk`/`killer`/`perform` |
| 状态播报 | `adm/daemons/combatd.c` | `damage_msg`(:68)、`eff_status_msg`(:230)、`status_msg`(:255)、`report_status`(:278)、`announce`(:966) |
| 死亡惩罚 | `adm/daemons/combatd.c` | `death_penalty`(:987)、`killer_reward`(:1027)、`winner_reward`(:982) |
| 地府区 | `d/death/` | `gate`/`gateway`/`road1-3`/`inn1`/`inn2`/`death`/`hell`/`npc/wgargoyle` |
| 技能映射 | `feature/skill.c` | `skills`/`learned`/`skill_map`/`skill_prepare`(:9-12)、`map_skill`(:42)、`query_skill`(:94) |
| 招式调度 | `inherit/skill/skill.c` + `skill2.c` | `perform_action`(:82/:82)、`exert_function`(:62/:62)、`hit_ob`(:142/:142) |
| 武功实例 | `kungfu/skill/xianglong-zhang/leiting.c` | `perform`(:32) |
| 内功实例 | `kungfu/skill/huntian-qigong/powerup.c` | `exert`(:17) |
| 装备数值 | `feature/equip.c` | `wield`(:46)、`wear`(:7)、`unequip`(:109) |
| 武器基类 | `inherit/weapon/blade.c` 等 | `init_blade`(:18)、`hit_ob`(:46) |
| 防具基类 | `inherit/armor/armor.c` / `cloth.c` | `setup` |
| 装备常量 | `include/weapon.h` | `TWO_HANDED`/`SECONDARY`/`EDGED`/`POINTED`/`SELF_ACTION` |
| Effect 常量 | `include/condition.h` | `CND_CONTINUE=1`/`CND_NO_HEAL_UP=2` |
| 战斗常量 | `include/combat.h` | `TYPE_REGULAR=0`/`TYPE_RIPOSTE=1`/`TYPE_QUICK=2`/`RESULT_DODGE=-1`/`RESULT_PARRY=-2` |
| Daemon 宏 | `include/globals.h` | `COMBAT_D`(:47)/`SKILL_D(x)`(:69)/`CONDITION_D(x)`(:70) |
| 组队 | `feature/team.c` | `leader`/`lord`/`team`(:8)、`follow_me`(:37)、`dismiss_team`(:103) |
| NPC AI | `inherit/char/npc.c` | `chat`(:97)、`accept_fight`(:30)、`accept_kill`(:69)、`perform_action`(:201) |
| 驯兽 | `inherit/char/trainee.c` | `train_it`(:50)、`do_yao`(:139)、`biting`(:227) |
| 命令 | `cmds/std/` | `kill.c`/`fight.c`/`hit.c`/`forcekill.c`/`wield.c`/`unwield.c`/`wear.c`/`remove.c`/`eat.c` |
