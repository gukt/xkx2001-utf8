# 战斗与效果生命周期簇 玩法切片（玩家视角 + 数据流）

> 产出角色：玩法切片策划。来源：当前仓库 LPC 一手源码（唯一真相源）。每条结论标注来源（LPC 文件路径 + 函数/对象名，必要时附行号）。
> 选片原则：覆盖「命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活」耦合链的六个代表性节点，且跨系统交互处优先。共 6 个切片。
> 范围边界：不输出 engine 接口草案；不深入招式文学文案；证据一律来自仓库根目录 LPC 源码（`feature/`/`inherit/`/`adm/daemons/`/`kungfu/`/`d/death/`/`cmds/`）。

---

## 切片 1：普攻对砍--kill/fight/hit 三种起手到三类伤害结算

### 玩家操作步骤

1. 玩家在房间内遇到目标，输入 `kill <人物>`（`cmds/std/kill.c:main()`）——单方面开启生死搏斗；或 `fight <人物>`（`cmds/std/fight.c:main()`）——点到为止的切磋，对玩家需双向确认；或 `hit <人物>`（`cmds/std/hit.c:main()`）——仅限玩家互殴的偷袭一招。
2. `kill` 走 `feature/attack.c:kill_ob(ob)`：检查 `environment()->query("no_fight")`（禁止战斗区拦截），把对方 id 加入 `killer` 列表，向对方播报 `HIR "看起来...想杀死你！"`，再调 `fight_ob(ob)`。`fight_ob`（`attack.c:40-48`）执行 `set_heart_beat(1)` + `enemy += ({ob})`。
3. 战斗由 `inherit/char/char.c:heart_beat()`（:60-169）每个 tick 驱动：若 `!is_busy()` 且 `is_fighting()`，调 `feature/attack.c:attack()`（:208-224）。`attack()` 先 `clean_up_enemy()` 清掉已死/换房/非 killing 的昏迷敌人（:64-75），再 `select_opponent()` 从 `enemy` 列表随机挑一个（:79-88，`random(MAX_OPPONENT)`，`MAX_OPPONENT=4`，:12）。
4. `attack()` 调 `COMBAT_D->fight(this_object(), opponent)`（:220）。`COMBAT_D` 即 `adm/daemons/combatd.c`（或 `s_combatd.c` 原型版）的 `fight()`（:787-845）。
5. `fight()` 三分支（combatd.c:799-844）：
   - 对方 `is_busy()` 或 `!living()` -> `do_attack(TYPE_QUICK)`（快速攻击，伤害减半）；
   - 否则按 `random(victim.dex*3) < me.str*2 + apply/speed` 判定是否主动出击 -> `do_attack(TYPE_REGULAR)`；
   - 否则进入 `guarding` 戒备态，播报「注视着...企图寻找机会出手」。
6. `do_attack(me, victim, weapon, attack_type)`（combatd.c:340-780）七步结算：
   - (0) 选技能：取 `weapon->skill_type` 或 `query_skill_prepare()` 准备技能，默认 `unarmed`；
   - (1) `me->reset_action()`（attack.c:143-171）从武功 daemon 取 `actions` mapping（含 `action` 文案/`dodge`/`parry`/`force`/`damage`/`damage_type`）；
   - (2) 算 `ap = skill_power(me, attack_skill, ATTACK)`（combatd.c:286-333，`level^3/3 + combat_exp`，乘 str/dex 与 jingli_bonus 50~150）、`dp = skill_power(victim, "dodge", DEFENSE)`；
   - (3) `random(ap+dp) < dp` -> 闪避（播报 `SKILL_D(dodge_skill)->query_dodge_msg`，双方扣 jingli `jiajin`）；
   - (4) 否则算 `pp = skill_power(victim,"parry",DEFENSE)`，`random(ap+pp) < pp` -> 格挡；
   - (5) 命中：算 `damage = apply/damage`，叠加 `action["damage"]`/`action["force"]`/`me.str`/技能等级/`jiali`（加力，内力驱动）/`jiajin`（精力加成），再让 `force_skill->hit_ob`、`martial_skill->hit_ob`、`weapon->hit_ob`（或 `me.hit_ob`）依次回调加成伤害与文案；
   - (6) `victim->receive_damage("qi", damage, me)`（damage.c:13-37），并按概率 `receive_wound("qi", damage - apply/armor, me)`（damage.c:39-66，造成「伤势」降 eff_qi）；
   - (7) 给经验/潜力，若非 killing 且 `victim.qi*2 <= max_qi` 则双方 `remove_enemy` 收场（winner_msg 播报「承让了」）。
7. `receive_damage` 内部：校验 type ∈ {`jing`,`qi`,`jingli`}，`set_temp("last_damage_from", who)` 记录伤害来源，若活且来源是玩家则 `set_temp("last_eff_damage_from", who.id)`（用于 PK 判定），扣减对应属性，`set_heart_beat(1)` 保证战斗 tick 不停。
8. `hit`（偷袭）走 `call_out("do_hit",1,me,obj)`（hit.c:81），1 秒后 `COMBAT_D->do_attack(me,obj,weapon)` 一招，若对方未 `yield` 则对方回敬一招——只打一个回合，不进 heart_beat 循环（除非顺势升级为 kill/fight）。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 敌对列表 | `feature/attack.c:15-16` `static object *enemy`/`string *killer` | `enemy` 存战斗对象，`killer` 存 id；`MAX_OPPONENT=4`（:12） |
| 起手命令 | `cmds/std/kill.c:main`（:9-88）/`fight.c:main`（:8-65）/`hit.c:main`（:9-98） | kill 走 `kill_ob`，fight 走 `fight_ob` 双向，hit 走 `do_attack` 单回合 |
| kill_ob | `feature/attack.c:51-62` | no_fight 拦截、`killer += id`、`fight_ob(ob)`、红字警告对方 |
| fight_ob | `feature/attack.c:40-48` | `set_heart_beat(1)` + `enemy += ({ob})` |
| 战斗 tick | `inherit/char/char.c:heart_beat` :118-133 | `is_busy` -> `continue_action`；否则 wimpy 逃跑检定 + `attack()` |
| 选敌 | `feature/attack.c:select_opponent` :79-88 | `random(MAX_OPPONENT)`，超长取 `enemy[0]` |
| 战斗调度 | `adm/daemons/combatd.c:fight` :787-845 | 三分支：QUICK/REGULAR/guarding |
| 命中结算 | `combatd.c:do_attack` :340-780 | 七步：选技->取 action->AP/DP->闪避/格挡/命中->伤害公式->施加->给经验 |
| 战力公式 | `combatd.c:skill_power` :286-333 | `level^3/3 + combat_exp`，攻击乘 str、防御乘 dex，jingli_bonus=50+jingli/max*50（封顶 150） |
| 三类伤害 | `feature/damage.c:receive_damage` :13-37 | type ∈ {jing 精, qi 气, jingli 精力}，扣 `query(type)` |
| 伤势（wound） | `feature/damage.c:receive_wound` :39-66 | type ∈ {jing, qi}，扣 `eff_<type>`（伤势上限），并连带压低当前值 |
| 伤害来源 | `damage.c:21`/`:26` | `set_temp("last_damage_from", who)` / `last_eff_damage_from`（玩家来源专用，PK 判定用） |
| 自动开战 | `combatd.c:auto_fight` :852-867 + `start_hatred/vendetta/aggressive/berserk` :904-962 | `feature/attack.c:init` :229-258 触发：hatred（is_killing 旧仇）、vendetta（门派世仇）、aggressive（NPC 态度） |
| hit 偷袭 | `cmds/std/hit.c:do_hit` :88-98 | `call_out` 1 秒后 `do_attack` 两次（我方 + 对方回敬，除非 yield） |

### 体验要点

- **kill/fight/hit 三档起手**对应「生死搏/切磋/偷袭」三种社交意图，机制差异明确：kill 单方面成立且 NPC 必回 kill（kill.c:71-76 `obj->kill_ob(me)`），fight 需 NPC `accept_fight` 或玩家双向确认（fight.c:32-43），hit 限玩家间且只打一招（hit.c:45 `if(!userp(obj)) return`）。现代引擎可保留三档语义但需重新设计「同意制」的 UX。
- **MAX_OPPONENT=4 的围攻上限**（attack.c:12,85）：`select_opponent` 只在前 4 个敌人中随机选，第 5+ 个敌人虽在 `enemy` 列表但不被主动攻击——这是围攻的隐式平衡阀，但代码未显式说明，玩家无感知。新引擎应显式建模「同时被多少人围攻」。
- **三类伤害 + 伤势双层模型**（damage.c:13-66）：`receive_damage` 扣当前值（可快速回血），`receive_wound` 扣伤势上限 `eff_*`（需 `receive_curing` 慢修复，damage.c:85-103）。这制造了「轻伤-重伤」梯度，是武侠「内伤难愈」体验的核心，新引擎应保留此双层结构。
- **`last_damage_from` / `last_eff_damage_from` 双来源标记**（damage.c:21,26）：前者记任意来源（含环境/condition），后者只记玩家来源——专用于 `die()` 中 PK 日志（damage.c:210-214 `PKILL_DATA`）与 `killer_reward` 中的 `pker` condition 判定（combatd.c:1087-1089）。区分「谁最后一击」vs「谁真正参与 PK」是反恶意捡人头的机制，新引擎应继承。
- **七步 do_attack 是高度耦合的巨型函数**（combatd.c:340-780，单函数 ~440 行）：命中、伤害、回调、经验、反击全在一个函数里，`hit_ob` 回调链（force/martial/weapon/me 四个钩子，:539-603）是武功/装备挂载 Effect 的主入口——这也是新引擎 UGC 挂点的关键表面。

---

## 切片 2：武功绝技爆发--perform/exert 调度到招式附带 Effect

### 玩家操作步骤

1. 玩家先用 `enable` 指令把所学武功「映射」到某技能槽（如 `enable strike 18-zhang`、`enable force huntian-qigong`），存入 `feature/skill.c:skill_map` mapping（:42-58 `map_skill`）。
2. 战斗中输入 `perform <招式名>`（`cmds/skill/perform.c:main`）施外功绝技，或 `exert <功能名>`（`cmds/skill/exert.c:main`）运内功异能。
3. `perform.c`（:10-111）前置校验：`is_busy()`（上动作未完成）、`query_temp("huagong")`（内力被化去）、`query_temp("feng")`（招数被封）、`cannot_perform`（自定义封禁）四道门闸。
4. 解析 `martial.skill` 参数：若未显式指定 `martial`，取 `weapon->skill_type` 或 `query_skill_prepare()` 的准备技能；双手准备两技能时 `martial="combo"`。
5. 调 `SKILL_D(skill)->perform_action(me, arg)`（:65）——武功 daemon 内分发到子招式文件（如 `kungfu/skill/18-zhang.c:perform_action_file` :304-307 返回 `__DIR__"18-zhang/"+action` 子目录）。成功则 `me->apply_condition("perform", martial)`（:69）——给一个 perform 冷却 condition 防连续施招。
6. `exert.c`（:8-42）走内功：取 `query_skill_mapped("force")`，调 `SKILL_D(force)->exert_function(me, arg)`，回退到 `SKILL_D("force")->exert_function`。典型内功功能如 `kungfu/skill/beiming-shengong/lifeheal.c`（疗伤：消耗 150 neili，`target->receive_curing("qi", 10+force/2)` + `add("qi",...)`，lifeheal.c:29-33）。
7. 普攻路径上的武功挂载：`do_attack` 在命中步（combatd.c:470-515）依次调四个 `hit_ob` 回调——
   - `force_skill->hit_ob(me, victim, damage_bonus, jiali)`（:473，内力加成，如 `hanbing-mianzhang.c:hit_ob` :136-142 命中时 `victim->apply_condition("hanbing_damage", ...)` 附带寒冰毒）；
   - `martial_skill->hit_ob(me, victim, damage_bonus)`（:501，外功加成）；
   - `weapon->hit_ob(...)` 或 `me->hit_ob(...)`（:507-515，武器/肉身特技）。
8. 招式 action mapping 由 `kungfu/skill/18-zhang.c:query_action` :241-291 返回，含 `action`（文案）、`dodge`/`parry`（命中修正）、`force`/`damage`（伤害修正）、`lvl`（学习门槛）、`damage_type`（瘀伤/劈伤/内伤等，决定 damage_msg 文案）、`post_action`（命中后回调，如 `sanhui` 三叠亢龙有悔，:316-319）。
9. 特殊格挡反击：`18-zhang.c:query_parry_msg` :18-38 当空手且 18-zhang>=100 且准备 strike 时，格挡触发「神龙摆尾」反手一掌——递归调 `COMBAT_D->do_attack(victim, me, weapon)`（:36），是武功被动招式的典型模式。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 技能映射 | `feature/skill.c:map_skill` :42-58 / `prepare_skill` :62-78 | `skill_map`/`skill_prepare` mapping；`query_skill` :94-109 合算 `apply/<skill>` + `skills[skill]/2` + `skills[mapped]` |
| perform 命令 | `cmds/skill/perform.c:main` :10-111 | 四道门闸 + `SKILL_D(skill)->perform_action(me,arg)` + `apply_condition("perform", martial)` 冷却 |
| exert 命令 | `cmds/skill/exert.c:main` :8-42 | `SKILL_D(force)->exert_function(me,arg)`，回退 `SKILL_D("force")` |
| 招式数据 | `kungfu/skill/18-zhang.c:action` mapping 数组 :52-218 | 每招含 action/dodge/parry/force/damage/lvl/skill_name/damage_type/weapon |
| 招式分发 | `18-zhang.c:perform_action_file` :304-307 | 返回子目录路径 `__DIR__"18-zhang/"+action` |
| 内功回调 | `combatd.c:do_attack` :470-484 `force_skill->hit_ob` | 返回 string(文案)/int(加成)/mapping(result+damage) |
| 外功回调 | `combatd.c:do_attack` :500-504 `martial_skill->hit_ob` | 同上 |
| 武器/肉身回调 | `combatd.c:do_attack` :507-515 `weapon->hit_ob`/`me->hit_ob` | 武器特技或肉身特技 |
| Effect 附挂实例 | `kungfu/skill/hanbing-mianzhang.c:hit_ob` :136-142 | `random(skill)>30` -> `victim->apply_condition("hanbing_damage", random(skill/20)+old)` |
| 内力驱动 | `combatd.c:do_attack` :471 `my["jiali"]` + `my["neili"]>jiali` | jiali=加力值（enable force 时设），neili 够才触发 force_skill->hit_ob |
| 精力加成 | `combatd.c:do_attack` :518-525 `jiajin` | `my["jingli"]>jiajin` 时 `foo = jingli/20 + jiajin - victim.jingli/25` 加 damage_bonus，并扣 jingli |
| 格挡反击 | `18-zhang.c:query_parry_msg` :18-38 | 神龙摆尾递归 `do_attack(victim, me, weapon)` |
| post_action | `combatd.c:do_attack` :661-662 `evaluate(action["post_action"],...)` | 命中后钩子（如 sanhui 三叠连击判定，18-zhang.c:316-319） |
| 双手互博 | `combatd.c:fight` :806-833 `pixie-jian`/`double_attack` | 辟邪剑法（无性+>=60）或 `double_attack` 属性触发第二下 `do_attack` |

### 体验要点

- **武功是「action 数据 + hit_ob 回调 + perform_action 子招」三位一体**：`query_action` 给普攻提供招式文案与数值修正，`hit_ob` 在命中时挂 Effect（毒/内伤/化内力等），`perform_action` 提供主动绝技。这三层是新引擎武功 DSL 的最小表面，UGC 创作者需能独立定义每一层。
- **`perform` 冷却用 condition 实现**（perform.c:69 `apply_condition("perform", martial)`）：把「技能 CD」建模为时效性 condition，复用 condition 引擎统一调度——这是 LPC 的巧妙复用，但 condition 名 `perform` 同时承载「冷却剩余」与「正在用的 martial 类型」双重语义，新引擎应拆分为显式 CD 字段。
- **`hit_ob` 回调返回值多态**（combatd.c:473-484）：可返回 string（纯文案）、int（伤害加成）、mapping（result 文案 + damage 伤害）。这种弱类型接口对 UGC 创作者极不友好，新引擎应统一为结构化返回（如 `{message, damage_bonus, applied_effects}`）。
- **门派武功集位于 `kungfu/class/<门派>/`**（如 baituo/dali/emei/gaibang/gumu/huashan/mingjiao/quanzhen/shaolin/wudang 等 19 门派）：门派是武功的归属映射，不涉及社交组织机制（见总则 2.2）。新引擎题材包应能以「门派 = 武功集合包」形式打包。
- **内力/精力是双资源驱动**（combatd.c:471 jiali+neili、:518 jiajin+jingli）：内力驱动 force_skill（强力加成），精力驱动 jiajin（轻量加成且抵消对方精力）。这制造了「内功型 vs 外功型」武学风分化，但资源类型只有 neili/jingli 两种，现代引擎可扩展为更细的资源体系。

---

## 切片 3：中毒与持续状态--condition.c 时效引擎与状态播报

### 玩家操作步骤

1. 玩家在战斗中被 `hanbing-mianzhang`（寒冰绵掌）命中，`hit_ob` 回调（hanbing-mianzhang.c:138-141）以 `random(skill)>30` 概率 `victim->apply_condition("hanbing_damage", random(skill/20)+old)`——给目标挂上「寒冰阴毒」condition，duration 随武功等级递增。
2. `feature/condition.c:apply_condition(cnd, info)`（:79-85）直接 `conditions[cnd] = info`——**不检查是否已存在**，由挂载方自行决定是否覆盖（注释 :73-77 明确）。
3. condition 的结算不主动触发，而是由 `inherit/char/char.c:heart_beat()` 降频驱动：:141-142 `if( !tick-- ) return; else tick = 5+random(10);`——每 6~15 个 heart_beat tick（约每 6~15 秒）才调一次 `update_condition()`（:144）。
4. `feature/condition.c:update_condition()`（:21-69）遍历 `conditions` mapping：对每个 condition，`find_object(CONDITION_D(cnd[i]))` 加载对应 daemon（如 `kungfu/condition/hanbing_damage.c`），`call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]])` 调其 `update_condition(me, duration)`。
5. daemon 的 `update_condition` 做三件事：播报状态文案、施加伤害/效果、自减 duration 并重新 `apply_condition`。以 `hanbing_damage.c`（:8-31）为例：
   - 播报：`tell_object(me, HIB "你觉得一股冷气直透心口..." )` + `message("vision", me->name()+"突然打了个寒战...", environment(me), me)`；
   - 伤害：`me->receive_damage("qi", (duration/2)+20, "因寒冰绵掌阴毒侵入内脏而死")` + `receive_wound("jing", (duration/2)+20, ...)`——注意伤害来源是字符串（非对象），`last_damage_from` 存的是死因描述；
   - 自减：`me->apply_condition("hanbing_damage", duration-1)`，`duration<1` 返回 0（过期移除），否则返回 `CND_CONTINUE`（=1，保留）。
6. 返回值约定（condition.c:62-64）：`flag & CND_CONTINUE` 为真则保留，否则 `map_delete` 移除；`CND_NO_HEAL_UP`（=2）位控制是否阻止 `heal_up`（char.c:149 `cnd_flag & CND_NO_HEAL_UP`）。
7. 各类 condition 的差异化行为：
   - **毒类**（`bt_poison.c` 西域灵蛇毒 :7-42）：按 `eff_jing` 分三档播报（轻/中/重），`receive_wound("jing",damage/2)` + `receive_damage("jingli",damage/2)`，衰减率受 `me.query_skill("poison",1)/10` 影响（bt_poison.c:36-38）——毒抗技能减毒；
   - **伤害类**（`hanbing_damage.c`/`juehu_damage.c` 绝户伤害 :10-63）：juehu 按 duration>400/>200/else 三档播报，并 `add_temp("apply/attack",-duration)`/`apply/defense,-duration` 永久扣攻防直到过期恢复，过期时若 `ori_gender=="男性"` 恢复性别（:53-58）——绝户爪的「阉割」效果；
   - **控制类**（`blind.c` :11-24）：`let_know` 过期时 `add_temp("apply/attack",amount)` 恢复被刺目扣的攻防（:26-35）；
   - **醉酒**（`drunk.c` :6-35）：`limit = 3+con+max_neili/40`，超限直接 `unconcious()`（醉倒），半限 `receive_damage("jing",10)`，1/4 限反而 `receive_healing("jing",10)+("qi",15)`（微醺回血）——酒量由 con+内力决定；
   - **嵌入暗器**（`embedded.c` :9-33）：`receive_wound("qi",3,"出血过多死了")` 持续流血，NPC 会自动 `do_remove` 拔除（:20-27）；
   - **通缉/ PK 惩罚**（`killer.c`/`pker.c`）：纯倒计时 condition，无效果只记时长（官府通缉 / PK 红名期），被 `killer_reward` 施加（combatd.c:1047 `apply_condition("killer",100)`、:1089 `apply_condition("pker",old+120)`）；
   - **包扎治疗**（`bandaged.c`）：正向 condition，`receive_curing("qi",3+random(5))` 慢修复伤势，或读 `medication` temp 加药效。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 挂载入口 | `feature/condition.c:apply_condition` :79-85 | `conditions[cnd] = info`，无去重，覆盖式 |
| 查询 | `condition.c:query_condition` :91-95 | 返回 `conditions[cnd]`（通常为 int duration） |
| 结算驱动 | `inherit/char/char.c:heart_beat` :141-144 | `tick` 每 6~15 tick 调一次 `update_condition()` |
| 结算核心 | `feature/condition.c:update_condition` :21-69 | 遍历 mapping，`CONDITION_D(cnd)` 加载 daemon，`call_other(...,"update_condition",me,info)` |
| daemon 加载 | `condition.c:36-52` | `find_object` + `catch(call_other(...,"???"))` 懒加载，失败 `map_delete` 移除并 log |
| 返回值 | `include/condition.h` `CND_CONTINUE=1`/`CND_NO_HEAL_UP=2` | daemon 返回 `(flag & CND_CONTINUE)` 决定保留/移除 |
| 清除 | `condition.c:clear_condition` :105-108 / `clear_one_condition` :97-103 / `clear_all_condition` :110-113 | `conditions=0` 全清；`die()` 调 `clear_condition`（damage.c:184）、`death_penalty` 也调（combatd.c:995） |
| 毒抗减毒 | `bt_poison.c:36-38` | `me.query_skill("poison",1)/10` 加快 duration 衰减 |
| 死因字符串 | `hanbing_damage.c:23`/`bt_poison.c:33-34` | `receive_damage(type, dmg, "因...而死")`——who 参数为字符串时成死因描述，记入 `last_damage_from` |
| 状态播报 | `tell_object`（本人）+ `message("vision",...,environment,({me}))`（房间他人，排除本人） | 三档文案按伤情分级（如 bt_poison 按 eff_jing 三档） |
| 攻防修改 | `juehu_damage.c:40-47` / `blind.c:26-35` | `add_temp("apply/attack",-duration)` 永久扣减，过期恢复 |

### 体验要点

- **condition 是「daemon + duration + CND_CONTINUE」的极简时效引擎**：每个 condition 是独立 daemon 文件（`kungfu/condition/<name>.c`），通过 `CONDITION_D(cnd)` 宏（condition.c:36）懒加载。这天然支持 UGC 横向扩展——创作者只需新增一个 daemon 文件即可定义新状态——但代价是 condition 之间无组合/互斥/优先级机制，叠加全靠 `apply_condition` 覆盖式写入（condition.c:79-85 不查重）。新引擎应保留「每状态一个定义单元」的扩展性，但补上组合规则层。
- **`update_condition` 降频驱动是性能关键**（char.c:141-142 `tick=5+random(10)`）：并非每 tick 都结算，而是每 6~15 秒一次，condition.c:16-20 注释明言「don't make player got too much this kind of conditions or you might got lots of 'Too long evaluation' error」——LPC 已意识到 condition 遍历的 heart_beat 开销。新引擎 1000 在线时 Effect 遍历是性能红队重点。
- **`CND_NO_HEAL_UP` 位是 condition 与回血系统的耦合点**（char.c:149）：condition 可阻止 `heal_up()`，实现「中毒期间无法自然回血」。但只有 2 个位标志（CONTINUE/NO_HEAL_UP），缺少「阻止移动」「阻止攻击」等更细的控制位——新引擎应扩展为状态机而非位标志。
- **死因字符串是 condition 的死亡叙事**（hanbing_damage.c:23 `receive_damage("qi",dmg,"因寒冰绵掌阴毒侵入内脏而死")`）：condition 杀人时 `last_damage_from` 是字符串死因而非玩家对象，`die()` 中 `objectp(killer)` 为假，走 `rumor` 频道「莫名其妙地死了」（damage.c:200-205）。这区分了「被杀」与「被状态折磨致死」，新引擎应保留此叙事层。
- **condition 无「来源」字段**：`apply_condition(cnd, info)` 的 info 通常只是 int duration，不记谁下的毒、何时下的。这导致 `juehu_damage` 的攻防扣减只能用 `wudang/juehu_damage` temp 标记防重复施加（juehu_damage.c:38-43），无法做「毒强度叠加」或「来源溯源」。新引擎 Effect 应带来源与堆叠策略元数据。

---

## 切片 4：昏迷与苏醒--两段式死亡判定的第一段

### 玩家操作步骤

1. 战斗中玩家 `qi`/`jing`/`jingli` 被打到负值。`inherit/char/char.c:heart_beat()` :108-115 判定：`my["qi"]<0 || my["jing"]<0 || my["jingli"]<0` -> `remove_all_enemy()`（停止战斗），然后：
   - 若 `living(this_object())`（仍清醒）-> 调 `feature/damage.c:unconcious()`（昏迷，第一段）；
   - 否则若 `disable_type == " <昏迷不醒>"`（已经昏迷着再挨致命伤）-> 调 `die()`（死亡，第二段）。
2. 更早一层判定（char.c:100-104）：`eff_qi<0 || eff_jing<0`（伤势上限被打穿）直接 `die()`，跳过昏迷。
3. `unconcious()`（damage.c:105-135）执行昏迷流程：
   - 不可重复昏迷（`!living()` 则 return）；
   - 巫师 `env/immortal` 免疫；
   - 若有 `last_damage_from` 击晕者，`COMBAT_D->winner_reward(defeater, this)`（combatd.c:982-985 调 `killer->defeated_enemy(victim)`），并 `set_temp("last_fainted_from", defeater.id)`（记晕倒者，反捡人头）；
   - `remove_all_enemy()`（attack.c:112-123，请所有敌人停手，但 killer 列表保留）；
   - `interrupt_me()`（打断 dazuo/jingzuo 等持续动作）；
   - `dismiss_team()`（脱离队伍，team.c:103-122）；
   - 播报 `HIR "你的眼前一黑，接著什么也不知道了...."`；
   - `disable_player(" <昏迷不醒>")`——设置 `disable_type`，正是上一步判定「再挨致命伤则死」的标记；
   - 三项资源归零：`set("jing",0); set("qi",0); set("jingli",0)`；
   - `set_temp("block_msg/all",1)`——屏蔽所有消息（玩家看不到房间任何动态）；
   - `COMBAT_D->announce(this_object(), "unconcious")`（combatd.c:964-979 播 `unconcious_message`）；
   - `call_out("revive", random(100-con)+30)`——苏醒定时器，`con`（体质）越高醒得越快，30~129 秒随机。
4. 昏迷期间玩家是「活靶」：`fight()` 中 `!living(victim)` 触发 `TYPE_QUICK` 快速攻击（combatd.c:799-815），对方可继续打昏迷者；若再挨致命伤，char.c:112-113 判定 `disable_type==" <昏迷不醒>"` -> `die()`。
5. 苏醒：`revive()`（damage.c:137-150）被 `call_out` 触发：`remove_call_out("revive")`，若身处容器内（`environment()->is_character()`）则 `move` 出来，`enable_player()` 解除昏迷态，`announce("revive")` 播报，`set_temp("block_msg/all",0)` 解除消息屏蔽，播 `HIY "慢慢地你终于又有了知觉...."`。
6. 例外：`die()` 中若 `environment()->query("no_death")` 且是玩家（damage.c:159-177），强制走 `unconcious()` + `remove_call_out("revive")`——禁止死亡区只允许昏迷，且立即清除苏醒定时器（需别的方式唤醒）。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 伤势上限判定 | `char.c:heart_beat` :100-104 | `eff_qi<0 \|\| eff_jing<0` -> 直接 `die()` |
| 资源负值判定 | `char.c:heart_beat` :108-115 | `qi<0 \|\| jing<0 \|\| jingli<0` -> `remove_all_enemy` + `unconcious`/`die` 分支 |
| 昏迷入口 | `feature/damage.c:unconcious` :105-135 | winner_reward + remove_all_enemy + interrupt + dismiss_team + disable_player + 资源归零 + block_msg + announce + call_out revive |
| 击晕者记录 | `damage.c:116-117` | `set_temp("last_fainted_from", defeater.id)`（仅玩家来源） |
| 消息屏蔽 | `damage.c:131` `set_temp("block_msg/all",1)` | 昏迷期间所有 `tell_object`/`message` 被屏蔽 |
| 苏醒定时 | `damage.c:134` `call_out("revive", random(100-con)+30)` | con 越高醒越快，30~129 秒 |
| 苏醒 | `feature/damage.c:revive` :137-150 | remove_call_out + enable_player + announce + 解除 block_msg |
| 静默苏醒 | `damage.c:revive(1)` :142-149 | `quiet=1` 时不播报，`die()` 中先 `revive(1)`（:179）再判定 |
| 禁死区 | `damage.c:die` :159-177 | `no_death` 区玩家只昏迷且清 revive 定时器 |
| 昏迷时被揍 | `combatd.c:fight` :799-815 | `!living(victim)` -> `TYPE_QUICK` 快速攻击，可继续打 |
| 昏迷时再挨致命 | `char.c:112-113` | `disable_type==" <昏迷不醒>"` -> `die()`（两段式衔接点） |

### 体验要点

- **两段式死亡是核心设计**（char.c:108-115）：先昏迷（`unconcious`，资源归零但可救），再死亡（`die`，下地府走轮回）。昏迷期间是「活靶」可被继续攻击致死——这制造了「倒地补刀」的 PvP 残酷性，但也给了队友救援窗口（`exert lifeheal` 疗伤、`bandaged` 包扎可救昏迷者，因昏迷本质是资源归零而非状态移除）。新引擎应显式建模「downed 状态」与「execution 时机」。
- **苏醒时间由 con 决定**（damage.c:134 `random(100-con)+30`）：体质越高醒越快，30~129 秒。这把「体质」从纯数值变成「抗击晕」体验参数，但随机区间过大（100 秒方差）导致体验不可预测——现代引擎应缩窄方差或改为确定性阈值。
- **`block_msg/all` 是粗暴的消息屏蔽**（damage.c:131）：昏迷期间屏蔽所有消息，玩家完全「失明失聪」——沉浸感强但挫败感也强（不知道被谁补刀）。`revive` 时一次性解除。新引擎可保留但应区分「战斗消息屏蔽」与「环境感知屏蔽」。
- **`no_death` 区是「安全网」**（damage.c:159-177）：比武场/任务区设 `no_death` 则只昏迷不死亡，且清 `revive` 定时器（需外部唤醒或自然醒）。这是 LPC 的「PvP 安全区」机制，新引擎应作为区域属性保留。
- **`dismiss_team` 在昏迷时触发**（damage.c:124）：昏迷即脱队，是「坦克倒下=队伍溃散」的硬规则——但代码无「队内救援」机制，队友无法替昏迷者挡刀（只能事后 `exert lifeheal`）。新引擎可扩展「掩护/替身」机制。

---

## 切片 5：玩家死亡下地府走轮回--die() 到 reincarnate() 的完整流程

### 玩家操作步骤

1. 玩家在非 `no_death` 区被杀，`die()`（damage.c:152-253）触发：
   - `clear_condition()`（:184，清所有状态）、`delete("poisoner")`（:185）；
   - `COMBAT_D->announce(this_object(), "dead")`（:187，播 `dead_message`）；
   - `COMBAT_D->death_penalty(this_object())`（:190，玩家才扣）；
   - 若有 `last_damage_from` 击杀者：`set_temp("my_killer", killer.id)` + `COMBAT_D->killer_reward(killer, this)`（:192-194）；
   - 否则玩家被环境/状态杀死：走 `aqingsao`（阿庆嫂）NPC 播 `rumor` 频道「莫名其妙地死了」（:195-206）；
   - 写日志：`PKILL_DATA`（被玩家杀）/`PLAYER_DEATH`（:209-224）；
   - `CHAR_D->make_corpse(this, killer)` 造尸体并 `move` 到房间（:226-228）；
   - `remove_all_killer()`（attack.c:126-136，清 killer 列表）+ 房间所有人 `remove_killer(this)`（:231）；
   - **玩家分支**（:233-250）：打断 busy、`set jing/qi/jingli=1`（留 1 点不归零，防反复触发）、`save()`、`ghost=1`（置鬼魂态）、`move(DEATH_ROOM)`（`include/login.h:23` 定义 `DEATH_ROOM="/d/death/gate.c"`）、`DEATH_ROOM->start_death(this)`、`MARRY_D->break_marriage`（断婚约）、风清扬徒弟 `break_relation`（断师徒）；
   - NPC 分支：`destruct(this_object())`（:252，NPC 死即销毁）。
2. `death_penalty`（combatd.c:987-1025）扣罚：`clear_condition`、`death_times++`（若 combat_exp>=10000*old_times）、`shen -= shen/20`、`behavior_exp -= 1/20`、`combat_exp -= exp/100`（封顶 5000，>50 才扣，否则扣 20）、`potential -= 1/2`、`balance`（存款）超 10000 部分砍半、`death_count++`、清 `vendetta`/`rob_victim`/`initiator` temp、`thief` 减半、`skill_death_penalty()`（skill.c:121-147 所有技能降 1 级+重置 skill_map）、`save()`。
3. `killer_reward`（combatd.c:1027-1096）：`killed_enemy` 回调、`PKS++`、城内 PK 施 `killer` condition 100（官府通缉，:1047）、`rumor` 播报死法（咬/踩/啄/杀，按 killer 种族，:1051-1058）、`shen` 偏移、`pker` condition+120（若 `pking/<id>` temp 存在，:1087-1089）、`vendetta` 记仇。
4. 玩家变鬼后进入地府区 `d/death/gate.c`（鬼门关）：`init()`（gate.c:26-48）立即清空玩家所有物品（`destruct(inv[i])`，:33-36）并 `clear_condition()`（:38）——鬼是赤条条的。`no_fight=1`（:21）禁战，`suicide` 被拦（:50-55「你还死着呢」）。
5. 鬼门关 NPC 白无常 `d/death/npc/wgargoyle.c`（:42-49 `init`）：`call_out("death_stage",30,ob,0)`——30 秒后开始剧情，每 5 秒一段共 5 段对话（:10-17 `death_msg`：问名/盯视/翻帐册/「阳寿未尽？」/「罢了罢了，你走吧」），第 5 段后（:58-71）`ob->reincarnate()`（damage.c:255-264 复活：`ghost=0` + 资源回满）、`DROP_CMD->do_drop` 丢光身上物、`move(REVIVE_ROOM)`（复活点，侠客岛特殊处理 :67）。
6. 期间鬼可在地府区游走：`gateway.c`（酆都城门）`valid_leave` 禁止往南回头（:28-37「没有回头路了」）；`road1.c` 通向 `inn1`/`inn2`/`road2`；`road2.c`（:24-46）迷雾循环——`long_road` temp 满 5 才能北行（:30-33），否则「四周景色居然都没有变」；`road3.c` 是死路（:15-17 仅南回）。
7. 地府两条复活路径：
   - **自动复活**：白无常剧情走完（30+5*4=50 秒）自动 `reincarnate` + 移到 `REVIVE_ROOM`；
   - **玩家主动**：`inn1.c`（小店）`do_stuff`（:67-83）——壁炉旁有个「长得跟你一模一样」的影子（:23-30 `item_desc/shadows`），`ask <自己id> about 回家` 触发（:51-65 `redirect_ask`），`reincarnate` + `move("/d/city/wumiao")`（扬州武庙）。
8. 异常区：`death.c`/`block.c`/`blkbot.c`（死刑室）`block_cmd`（:24-31）只允许 `quit`/`suicide`/`goto`，设 `startroom` 为 `/d/death/death`——这是关押违规玩家的「禁闭室」。`hell.c`（18 层地狱，:13-32）允许 `say`/`tell`/`look`/`quit`/`suicide`/`goto`，也设 `startroom`。`noteroom.c`（犯罪记录室，:30-40）玩家直接被踢回 `death.c`。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 死亡入口 | `feature/damage.c:die` :152-253 | clear_condition + announce + death_penalty + killer_reward + 造尸体 + remove_all_killer + ghost=1 + move(DEATH_ROOM) |
| 鬼魂态 | `feature/damage.c:9` `int ghost=0` / `:11` `is_ghost()` / `:246` `ghost=1` | 鬼魂可见性：`char.c:181-186` `visible` 中 `ob.is_ghost()` 需 `is_ghost()` 或 `astral_vision` 才可见 |
| 死亡惩罚 | `combatd.c:death_penalty` :987-1025 | death_times++ + shen/behavior_exp/combat_exp/potential/balance 扣减 + skill_death_penalty + save |
| 技能降级 | `feature/skill.c:skill_death_penalty` :121-147 | 所有技能 -1 级，learned 重置，skill_map 清空 |
| 击杀奖励 | `combatd.c:killer_reward` :1027-1096 | PKS++ + killer condition（城内 PK）+ pker condition（pking temp）+ rumor 播报 + shen/vendetta |
| 尸体 | `die` :226-228 `CHAR_D->make_corpse(this, killer)->move(environment)` | 尸体留在原房间 |
| 地府入口 | `include/login.h:23` `DEATH_ROOM="/d/death/gate.c"` | 死亡传送目标 |
| 鬼门关清场 | `d/death/gate.c:init` :26-48 | 清空所有物品 + clear_condition + no_fight + 禁 suicide |
| 白无常剧情 | `d/death/npc/wgargoyle.c:death_stage` :51-71 | 30s 起 + 5 段 × 5s 对话 -> reincarnate + drop all + move(REVIVE_ROOM) |
| 复活 | `feature/damage.c:reincarnate` :255-264 | ghost=0 + jing/qi/jingli/eff_jing/eff_qi/neili 回满 |
| 复活点 | `wgargoyle.c:68` `REVIVE_ROOM` / `inn1.c:78` `/d/city/wumiao` | 默认复活点 vs 主动复活点 |
| 地府拓扑 | `gate.c`(鬼门关)->`gateway.c`(酆都城门)->`road1`->`road2`(迷雾循环)->`road3`(死路)；`road1`<->`inn1`/`inn2` | 单向流程，`gateway.valid_leave` 禁回头 |
| 迷雾循环 | `road2.c:valid_leave` :24-46 | `long_road` temp 累 5 才放行北行 |
| 禁闭室 | `death.c`/`block.c`/`blkbot.c` `block_cmd` :24-31 | 仅 quit/suicide/goto 可用，设 startroom |
| 18 层地狱 | `hell.c:init` :13-32 | 允许 say/tell/look/quit/suicide/goto，设 startroom |
| 断关系 | `die` :249 `MARRY_D->break_marriage` / :250 `break_relation`（风清扬徒弟） | 死亡断婚约与特定师徒关系 |

### 体验要点

- **死亡是「惩罚 + 仪式 + 复活」三段式**：`death_penalty`（数值惩罚）+ 地府区游走（仪式感）+ `reincarnate`（满血复活）。惩罚很重（combat_exp 扣 1%、技能全降 1 级、存款砍半、shen/behavior_exp 扣 5%），但**不死透**——满血复活可继续玩。这是典型的「死亡惩罚但可恢复」设计，新引擎应保留三段式但惩罚力度需重新校准（LPC 的技能降级对老玩家极伤）。
- **地府区是「强制单程叙事」**（gate->gateway->road1->road2->road3 单向，gateway 禁回头）：玩家变鬼后无战斗能力（`no_fight=1` 全区）、物品全清、只能走预设流程。白无常自动剧情 50 秒后强制复活——玩家几乎无操作空间，纯粹是「惩罚过场」。新引擎应考虑让地府更有交互性（如赎罪任务减惩罚），而非纯线性过场。
- **`inn1` 主动复活是隐藏路径**（inn1.c:67-83 `do_stuff`）：玩家可 `ask <自己> about 回家` 主动触发复活到扬州武庙——比默认 `REVIVE_ROOM` 更近中原。这是 LPC 的「探索奖励」设计，但无任何提示（inn2 墙上字「靠自己啦」是唯一暗示），现代引擎应保留隐藏路径但给适度引导。
- **鬼魂可见性是独立系统**（char.c:181-186 `visible`）：鬼只能被鬼或 `astral_vision`（天眼通）看到。这意味着活人看不到鬼魂玩家——地府区与阳间是「叠加层」关系。但代码未实现「鬼魂干扰阳间」机制（无 poltergeist 类 condition），是未实现的扩展点。
- **`death_times` 阈值递增**（combatd.c:882-883 `if(combat_exp >= 10000*death_times) death_times++`）：死亡次数越多，下次触发 `death_times++` 的门槛越高——这是隐性的「老玩家死亡保护」，但逻辑反向（越死越难涨 death_times，反而保护了常死的人），设计意图存疑，新引擎应重新审视。
- **城内 PK 触发官府通缉**（killer_reward :1047 `apply_condition("killer",100)`）：在 `/d/city/` 下杀人自动挂 100 duration 的 killer condition（官府通缉），是 PvP 的法律约束层。新引擎应将「区域法律 + PK 惩罚」作为题材包可配置内容。

---

## 切片 6：组队围攻--team.c 跟随与 attack.c 多敌对列表

### 玩家操作步骤

1. 玩家 A 邀请玩家 B 组队：A 输入 `team with B`（命令在 cmds 下，调 `feature/team.c:add_team_member(ob)` :51-66）——`team` 数组加入双方，`map_array(team, (: $1->set_team(team) :))` 同步队伍引用给所有成员。
2. 队长移动时队员自动跟随：`team.c:follow_me(ob, dir)` :37-49——若 `ob==leader` 或队员 `is_killing(ob.id)`（追杀中），按 `move` 技能判定能否跟上（`random(ob.query_skill("move")) > this.query_skill("move")` 则 `call_out("follow_path",1,dir)` 延迟跟，否则立即 `follow_path`）。`follow_path(dir)` :28-35 先 `remove_all_enemy()`（移动即脱离战斗！）再 `GO_CMD->main(this, dir)`。
3. 围攻成立：多名玩家/NPC 各自对同一目标 `kill_ob`/`fight_ob`——目标的 `enemy` 列表（attack.c:15）累积所有攻击者。但 `attack.c:select_opponent` :79-88 每个 tick 只从 `random(MAX_OPPONENT=4)` 中选一个攻击——**被围攻者每 tick 只反击 1 人，且只在前 4 个敌人中选**。
4. 围攻者各自独立：每个攻击者跑自己的 `heart_beat()`，各自 `attack()` 选自己 `enemy` 列表中的目标——**无集中协调**，队伍只是「跟随关系」，不是「合击关系」。
5. 队长倒下即溃散：`unconcious()`（damage.c:124）与 `die()`（:244）都调 `dismiss_team()`（team.c:103-122）——队长昏迷或死亡，队伍就地解散。队员各自为战。
6. 自动开战的队伍联动：`feature/attack.c:init` :229-258 当敌对目标进入房间，触发 `COMBAT_D->auto_fight(this, ob, type)`（combatd.c:852-867），`type` 为 `hatred`（旧仇 is_killing）/`vendetta`（门派世仇 `vendetta_mark`）/`aggressive`（NPC 态度）/`berserk`（狂暴，按 shen 负值判定）。`call_out("start_"+type, 0, me, obj)` 延迟 0 秒执行（给目标逃跑机会，combatd.c:762 注释「gives victim a chance to slip through」）。
7. NPC 围攻标记：`kill.c:74` `if (!obj->is_grpfight()) obj->kill_ob(me)`——NPC 的 `is_grpfight()` 决定是否「被 kill 后全组反击」，是 NPC 群体仇恨的开关（`is_grpfight` 定义在 NPC char 文件，不在 feature 层）。
8. 战利品与功勋：`killer_reward` 中击杀者 `PKS++`（玩家杀玩家）或 `MKS++`（杀人类 NPC，combatd.c:1065-1067），`shen` 偏移按 `victim.shen/10`（:1076-1077）——围攻中谁给最后一击谁拿功勋，`last_eff_damage_from` 记真正参与 PK 的玩家用于日志（damage.c:210-214）。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据） | 状态/数据 |
|------|----------------------|-------------|-----------|
| 组队 | `feature/team.c:add_team_member` :51-66 / `join_team` :68-83 | `static object *team` 数组，`set_team` 同步引用 |
| 队长/主公 | `team.c:set_leader` :10-15 / `set_lord` :19-24 | `leader`（跟随对象）/`lord`（主人，驯服从属关系） |
| 跟随移动 | `team.c:follow_me` :37-49 / `follow_path` :28-35 | move 技能检定 + `remove_all_enemy()`（移动断战斗）+ `GO_CMD->main` |
| 多敌对列表 | `feature/attack.c:enemy` :15 / `select_opponent` :79-88 | `MAX_OPPONENT=4`，每 tick 随机选 1 反击 |
| 清敌 | `attack.c:clean_up_enemy` :64-75 | 死/换房/非 killing 的昏迷者移出 enemy |
| 全停战斗 | `attack.c:remove_all_enemy` :112-123 | 请对方停手（对方 enemy 移除自己），自身 enemy 清空，killer 保留 |
| 全停生死 | `attack.c:remove_all_killer` :126-136 | killer 清空 + enemy 清理 |
| 队伍溃散 | `damage.c:unconcious` :124 / `die` :244 `dismiss_team()` | 昏迷/死亡即脱队 |
| 脱队 | `team.c:dismiss_team` :103-122 | 队长脱则全散，队员脱则自离 |
| 自动开战 | `feature/attack.c:init` :229-258 + `combatd.c:auto_fight` :852-867 + `start_hatred/vendetta/aggressive/berserk` :904-962 | 4 种自动开战类型，`call_out` 延迟给逃跑窗口 |
| 群体反击 | `cmds/std/kill.c:74` `if(!obj->is_grpfight()) obj->kill_ob(me)` | NPC `is_grpfight()` 控制被 kill 后是否全组反击 |
| 功勋分配 | `combatd.c:killer_reward` :1027-1096 | 最后一击者 `PKS++`/`MKS++` + shen 偏移 |
| PK 来源 | `damage.c:26` `set_temp("last_eff_damage_from", who.id)` | 玩家来源专用，die() 中 PKILL 日志用（damage.c:210-214） |

### 体验要点

- **LPC 的「组队」本质是「跟随关系」而非「合击系统」**（team.c 全文无合击/阵法逻辑，仅 follow/set_team/dismiss）：队伍只解决「一起移动」，不解决「协同攻击」。围攻是多名独立战斗者各打各的 emergent behavior。`stand/teamwork`（阵法合击）在 attack.c:193 注释提及为「prototype」，未上线。新引擎若要做真正合击，需从零设计，不能照搬 team.c。
- **`MAX_OPPONENT=4` 是围攻的隐式平衡阀**（attack.c:12,85）：被 5+ 人围攻时，第 5+ 人虽在 enemy 列表但不被反击——相当于「免费输出位」。但攻击者无此限制（每人独立选敌），导致围攻方占优。且 `select_opponent` 的 4 是硬编码，无法配置。新引擎应显式建模「围攻上限」并允许题材包调整。
- **移动即脱战**（team.c:32 `follow_path` 调 `remove_all_enemy`）：跟随队长移动会清除所有敌对关系——这是「逃跑=脱战」的硬规则，但 killer 列表保留（attack.c:112-123 `remove_all_enemy` 不清 killer），所以「逃得了打，逃不了仇」。新引擎应区分「脱离当前战斗」与「终结敌对关系」。
- **队长倒下=队伍溃散**（damage.c:124,244 `dismiss_team`）：无「副队长」递补机制，队长昏迷/死亡队伍立即解散。这在 PvP 围攻中是「斩首战术」的机制基础——但过于脆弱，新引擎应支持队长转移。
- **`auto_fight` 的 4 种类型是 NPC AI 的核心**（combatd.c:904-962）：`hatred`（记仇，is_killing 持久）、`vendetta`（门派世仇，`vendetta_mark` 配对）、`aggressive`（主动攻击型 NPC）、`berserk`（狂暴，按负 shen 判定）。这 4 种是题材包 NPC 行为的配置点，但都通过 `call_out("start_"+type,0,...)` 延迟触发——0 秒延迟但仍是异步，给目标 1 tick 逃跑窗口。新引擎 NPC AI 应支持更丰富的仇恨模型。

---

## 跨切片交叉发现

1. **「命中 -> 伤害 -> 状态 -> 死亡 -> 复活」全链由 `heart_beat` 单线程驱动**（char.c:60-169）：战斗 tick（每 ~2 秒）、condition 结算（每 6~15 秒）、死亡判定（每 tick 检查 eff/qi 负值）、回血（heal_up 每 tick）。单线程单 World 的性能瓶颈即在此——1000 玩家同时战斗 + 挂满 condition 时，heart_beat 遍历开销巨大（condition.c:16-20 注释已警告）。
2. **`set_heart_beat(1)` 是战斗的「开关」**（attack.c:44 fight_ob 调用 / damage.c:34 receive_damage 调用）：任何伤害/战斗都强制开启 heart_beat；而 char.c:149-158 在完全和平时 `set_heart_beat(0)` 关闭以省 CPU。这是 LPC 的「按需驱动」优化，新引擎应保留此惰性激活模式。
3. **`last_damage_from` / `last_eff_damage_from` / `last_fainted_from` / `my_killer` 是伤害溯源的四级标记**（damage.c:21,26,117 / :193）：分别记「任意最后伤害源」「玩家参与 PK 源」「击晕者」「最终杀手」——用于死因播报、PK 日志、反捡人头、击杀奖励。这套溯源体系是新引擎「击杀归因」的参考原型。
4. **condition 的 `apply_condition` 无去重无来源**（condition.c:79-85）是 Effect 系统的最大设计债——导致 `juehu_damage` 要用 `wudang/juehu_damage` temp 防重复施加（juehu_damage.c:38-43），`bt_poison` 衰减率靠 `poison` 技能减毒（bt_poison.c:36-38）而非配置。新引擎 Effect 必须带来源、堆叠策略、优先级。
5. **`disable_type` 字符串标记是状态机的退化形态**（damage.c:127 `disable_player(" <昏迷不醒>")`、char.c:112 比对 `disable_type==" <昏迷不醒>"`）：用字符串而非枚举标记状态，扩展性差且易写错。新引擎应用显式状态机（Alive/Downed/Dead/Ghost）。
6. **地府区是「死亡惩罚的可视化过场」**：物品清场（gate.c:33-36）、迷雾循环（road2.c:24-46）、白无常剧情（wgargoyle.c:51-71）、隐藏复活路径（inn1.c:67-83）——这是一套「惩罚-仪式-重生」叙事，但玩家操作空间极小（几乎只能等 50 秒自动复活）。新引擎应保留仪式感但增加玩家能动性（如赎罪/减惩罚任务）。
