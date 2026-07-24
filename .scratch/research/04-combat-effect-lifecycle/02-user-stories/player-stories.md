# 战斗与效果生命周期簇 玩家故事（Player User Stories）

> 产出角色：玩法切片策划。来源：当前仓库 LPC 一手源码（唯一真相源）。每条故事标注来源（LPC 文件:函数/对象名）。
> 视角：玩家在战斗 / Effect / 死亡与轮回中会做什么、遭遇什么。格式 `作为<角色>，我希望/遇到<行为/情境>，以便<价值>`。证据列于每条之后。
> 覆盖：普攻起手三档、武功绝技、Effect 中毒与持续状态、昏迷苏醒、死亡下地府走轮回、组队围攻，以及跨系统体验。共 12 条。

---

## US-1：选择战斗烈度--kill/fight/hit 三档起手

**作为** 想与他人交手的玩家，**我希望** 在 kill（生死搏）/ fight（切磋）/ hit（偷袭一招）三种起手方式间选择，**以便** 按社交意图控制战斗烈度与后果。

- `kill <人物>` 走 `feature/attack.c:kill_ob`（:51-62）：单方面成立，NPC 必回 `kill_ob`（`cmds/std/kill.c:71-76`），向对方红字警告「想杀死你」。
- `fight <人物>` 走 `feature/attack.c:fight_ob`（:40-48）：对玩家需双向确认（`cmds/std/fight.c:32-43` pending/fight 机制），对 NPC 需 `accept_fight` 同意（:52）；非 killing 且 `victim.qi*2<=max_qi` 时自动收手播「承让了」（`combatd.c:749-759`）。
- `hit <人物>` 仅限玩家间一招偷袭（`cmds/std/hit.c:45` `if(!userp(obj)) return`），双方各打一招（`hit.c:88-98 do_hit` 两次 `do_attack`），除非对方 `yield`。
- `no_fight` 区三档全禁（kill.c:16、fight.c:12、hit.c:14）。
- 限制：骑乘禁战（kill.c:42-43、fight.c:18-19）、侠客岛禁玩家互攻（kill.c:48-49、hit.c:66-67）、pker>240 或对方 mud_age<18000 禁 kill（kill.c:51-53）。

**验收**：三档命令语义分明；kill 单方成立且 NPC 必反击；fight 双方同意才开打且血量低自动收手；hit 只打一招且只对玩家；禁战区/骑乘/特定区域被拦。

---

## US-2：施展武功绝技与内功异能

**作为** 学了武功的玩家，**我希望** 用 `perform` 施展外功绝技、用 `exert` 运内功异能（疗伤/护体等），**以便** 在战斗中获得超越普攻的爆发与功能。

- `enable` 先映射武功到技能槽（`feature/skill.c:map_skill` :42-58 存 `skill_map`）。
- `perform <招式>` 调 `SKILL_D(skill)->perform_action(me,arg)`（`cmds/skill/perform.c:65`），成功后 `apply_condition("perform", martial)` 加冷却 condition（:69）。
- `exert <功能>` 调 `SKILL_D(force)->exert_function(me,arg)`（`cmds/skill/exert.c:25`），回退 `SKILL_D("force")`（:33）。
- 前置门闸：`is_busy`/`huagong`（内力被化）/`feng`（招被封）/`cannot_perform`（自定义封禁）（perform.c:19-36）；`pixie/ciwan`（刺腕）禁 exert（exert.c:17-18）。
- 内功功能例：`kungfu/skill/beiming-shengong/lifeheal.c` 疗伤--消耗 150 neili，`target->receive_curing("qi", 10+force/2)`（:29-33），战斗中禁用（:11）。
- 招式数据：`kungfu/skill/18-zhang.c:action` 数组（:52-218）每招含 action 文案/dodge/parry/force/damage/lvl/damage_type；`query_action`（:241-291）可触发「亢龙有悔」三叠连击（sanhui，:255-265 post_action）。

**验收**：perform/exert 需先 enable；冷却 condition 防连续施招；内功功能消耗 neili 且战斗中受限；招式有等级门槛（lvl）与伤害类型（damage_type 决定文案）。

---

## US-3：被毒/状态折磨与毒抗减毒

**作为** 被寒冰绵掌命中或中西域灵蛇毒的玩家，**我希望** 感知状态分级播报、毒抗技能能减毒，**以便** 知道自己伤情并有机会自救。

- 命中挂毒：`kungfu/skill/hanbing-mianzhang.c:hit_ob`（:136-142）`random(skill)>30` -> `victim->apply_condition("hanbing_damage", random(skill/20)+old)`。
- 结算：`feature/condition.c:update_condition`（:21-69）每 6~15 秒（`char.c:141-142 tick`）调 daemon 的 `update_condition(me, duration)`。
- `hanbing_damage.c`（:8-31）：按 `eff_jing` 分档播报，`receive_damage("qi",(duration/2)+20)` + `receive_wound("jing",...)`，死因字符串「因寒冰绵掌阴毒侵入内脏而死」。
- `bt_poison.c`（:7-42）：西域灵蛇毒按 `eff_jing` 三档播报（轻/中/重），衰减率受 `me.query_skill("poison",1)/10` 加快（:36-38）--毒抗技能可减毒。
- `juehu_damage.c`（:10-63）：绝户伤害按 duration>400/>200/else 三档，`apply/attack` 与 `apply/defense` 扣 duration 点，过期恢复；过期且 `ori_gender=="男性"` 恢复性别（:53-58）。
- 死因叙事：condition 杀人时 `last_damage_from` 是字符串死因，`die()` 走 `rumor`「莫名其妙地死了」（damage.c:200-205）。

**验收**：状态有分级文案（轻/中/重）；毒抗技能加快毒衰减；condition 杀人有死因叙事；绝户爪有「阉割」特殊效果且过期可恢复。

---

## US-4：醉酒与控制状态的非线性效果

**作为** 喝酒或被刺目的/被嵌入暗器的玩家，**我希望** 感知控制状态的分级效果与恢复机制，**以便** 评估自己战斗能力的变化。

- `drunk.c`（:6-35）：`limit = 3+con+max_neili/40`（酒量由体质+内力决定）；`duration>limit` 直接 `unconcious()` 醉倒；`>limit/2` 扣 `jing` 10（醉酒伤神）；`>limit/4` 反而 `receive_healing("jing",10)+("qi",15)`（微醺回血）。
- `blind.c`（:11-24）：刺目扣 `apply/attack`/`apply/defense`（由 `cimu_power` temp 记额度），过期 `let_know`（:26-35）恢复。
- `embedded.c`（:9-33）：嵌入暗器每 tick `receive_wound("qi",3,"出血过多死了")` 持续流血；NPC 会自动 `do_remove` 拔除（:20-27），玩家需手动 `remove`。
- `bandaged.c`：包扎正向 condition，`receive_curing("qi",3+random(5))` 慢修复伤势，或读 `medication` temp 加药效。
- `CND_NO_HEAL_UP` 位（`include/condition.h`=2）：condition 可阻止 `heal_up` 自然回血（`char.c:149`）。

**验收**：醉酒有「微醺回血-醉酒伤神-醉倒」三段非线性曲线；刺目/嵌入有明确恢复路径（过期/拔除）；包扎可慢修复伤势；部分状态可阻止自然回血。

---

## US-5：昏迷与被补刀的恐惧

**作为** 战斗中资源被打空的玩家，**我希望** 昏迷后有苏醒希望（con 越高醒越快），但恐惧昏迷时被继续攻击致死，**以便** 体验「倒地-救援-补刀」的紧张感。

- 昏迷判定：`char.c:heart_beat` :108-115 `qi<0 || jing<0 || jingli<0` -> `remove_all_enemy` + `unconcious`（清醒）或 `die`（已昏迷再挨致命）。
- `unconcious()`（damage.c:105-135）：资源归零、`block_msg/all=1` 屏蔽所有消息、`disable_player(" <昏迷不醒>")`、`call_out("revive", random(100-con)+30)`（30~129 秒，con 越高醒越快）。
- 昏迷时是活靶：`combatd.c:fight` :799-815 `!living(victim)` 触发 `TYPE_QUICK` 快速攻击（伤害减半但可继续打）。
- 两段式衔接：昏迷中再挨致命伤，`char.c:112-113` `disable_type==" <昏迷不醒>"` -> `die()`。
- 苏醒：`revive()`（damage.c:137-150）`enable_player` + 解除 `block_msg` + 播「慢慢地你终于又有了知觉」。
- `no_death` 区只昏迷不死亡且清 revive 定时器（damage.c:159-177），需外部唤醒或自然醒。

**验收**：资源负值触发昏迷；昏迷期间消息屏蔽且可被补刀；苏醒时间与 con 正相关；禁死区只昏迷不死亡；昏迷即脱队（dismiss_team）。

---

## US-6：死亡下地府走轮回与满血复活

**作为** 被杀的玩家，**我希望** 死后走地府流程最终满血复活（而非永久死亡），但承受数值惩罚，**以便** 死亡有代价但游戏可继续。

- `die()`（damage.c:152-253）：`clear_condition` + `death_penalty` + `killer_reward` + 造尸体 + `ghost=1` + `move(DEATH_ROOM=/d/death/gate.c)`（`include/login.h:23`）。
- 死亡惩罚 `combatd.c:death_penalty`（:987-1025）：`death_times++`、shen/behavior_exp 扣 1/20、combat_exp 扣 1%（封顶 5000）、potential 砍半、balance 超 10000 部分砍半、`skill_death_penalty`（skill.c:121-147 全技能降 1 级 + 清 skill_map）、`save`。
- 地府入口 `d/death/gate.c`（鬼门关）：`init`（:26-48）清空所有物品 + `clear_condition` + `no_fight=1` + 禁 `suicide`。
- 白无常剧情 `d/death/npc/wgargoyle.c:death_stage`（:51-71）：30 秒后开始，每 5 秒一段共 5 段对话（问名/翻帐册/「阳寿未尽？」/「罢了罢了，你走吧」），第 5 段后 `reincarnate()` + 丢光物 + `move(REVIVE_ROOM)`。
- `reincarnate()`（damage.c:255-264）：`ghost=0` + jing/qi/jingli/eff_*/neili 全回满。
- 地府单向流程：`gateway.c:valid_leave` 禁回头（:28-37），`road2.c:valid_leave` 迷雾循环需 `long_road` 累 5（:24-46），`road3.c` 死路。
- 隐藏复活：`inn1.c:do_stuff`（:67-83）`ask <自己id> about 回家` -> `reincarnate` + `move("/d/city/wumiao")`。
- 断关系：`die` :249 `MARRY_D->break_marriage`（断婚约）、:250 `break_relation`（风清扬徒弟断师徒）。
- 鬼魂可见性：`char.c:181-186` 鬼只被鬼或 `astral_vision` 看到。

**验收**：死亡扣数值（exp/技能/存款/shen）但可恢复；地府区清空物品且禁战；白无常 50 秒自动复活满血；地府单向不可回头；有隐藏主动复活路径；鬼魂对阳间不可见。

---

## US-7：城内 PK 触发官府通缉与红名惩罚

**作为** 在城内杀人的玩家，**我希望** 知道城内 PK 会触发官府通缉与红名惩罚，**以便** 权衡 PK 的法律代价。

- 城内 PK 自动挂 `killer` condition 100 duration（`combatd.c:killer_reward` :1047 `if(strsrch(file_name(env),"/d/city/")>=0) apply_condition("killer",100)`）。
- `killer.c`（:6-16）：纯倒计时，过期播「官府不再通缉你了」。
- 主动 PK 且 `pking/<id>` temp 存在时挂 `pker` condition +120（combatd.c:1087-1089）；`pker.c` 纯倒计时。
- pker>240 时禁止 kill（`kill.c:51-53` `if(me.query_condition("pker")>240 ...)` 「你感到一丝内疚，手突然软了下来」）。
- PK 日志：`die()`（damage.c:209-214）写 `PKILL_DATA` + `PLAYER_DEATH`（用 `last_eff_damage_from` 玩家来源标记）。
- 死亡播报：`killer_reward`（combatd.c:1060-1061）`rumor` 频道「被 X 咬/踩/啄/杀死了」（按 killer 种族）。
- shen 偏移：killer.combat_exp < victim 且 > victim/4 时 `shen -= victim.shen/10`（:1076-1077）。

**验收**：城内 PK 触发官府通缉 condition；pker 累计过高禁止再 PK；PK 有日志记录与 rumor 播报；善恶值（shen）随 PK 偏移。

---

## US-8：组队跟随与围攻多名敌人

**作为** 想和朋友/NPC 一起战斗的玩家，**我希望** 组队后能跟随队长移动、多人围攻同一目标，**以便** 协同作战。

- 组队：`feature/team.c:add_team_member`（:51-66）`team` 数组 + `set_team` 同步引用；`is_team_leader`（:85-91）取 `team[0]`（过滤 living 后）。
- 跟随：`follow_me`（:37-49）按 `move` 技能检定跟上队长；`follow_path`（:28-35）先 `remove_all_enemy()`（移动断战斗）再 `GO_CMD->main`。
- 围攻：多人各自 `kill_ob` 同一目标，目标 `enemy` 列表累积（attack.c:15）；`select_opponent`（:79-88）每 tick 从前 `MAX_OPPONENT=4`（:12）个敌人中随机选 1 反击。
- 队长倒下溃散：`unconcious`（damage.c:124）/`die`（:244）调 `dismiss_team`（team.c:103-122）。
- NPC 群体反击：`kill.c:74` `if(!obj->is_grpfight()) obj->kill_ob(me)`--`is_grpfight()` 控制被 kill 后是否全组反击。
- 功勋归最后一击者：`killer_reward` `PKS++`/`MKS++`（combatd.c:1043,1065-1067）。

**验收**：组队后跟随队长移动（受 move 技能检定）；移动即脱离战斗；被围攻者每 tick 只反击前 4 人中随机 1 人；队长昏迷/死亡队伍溃散；NPC 可群体反击。

---

## US-9：自动开战与仇恨记忆

**作为** 在野外活动的玩家，**我希望** 知道哪些 NPC 会自动攻击我（仇恨/世仇/狂暴/主动型），**以便** 规避或准备应战。

- `feature/attack.c:init`（:229-258）：敌对目标进房间时，检查 `is_killing`（旧仇）/`vendetta_mark`（门派世仇）/`attitude=="aggressive"`（NPC 主动）触发 `COMBAT_D->auto_fight`。
- `combatd.c:auto_fight`（:852-867）`call_out("start_"+type,0,...)` 延迟 0 秒给逃跑窗口（注释 :762）。
- 4 种类型：
  - `hatred`（:904-926）：is_killing 旧仇，播「仇人相见」+ `kill_ob`；
  - `vendetta`（:928-944）：`vendetta_mark` 配对门派世仇，直接 `kill_ob`；
  - `aggressive`（:946-962）：NPC attitude=aggressive 主动杀，`kill_ob`；
  - `berserk`（:869-902）：按负 shen 判定狂暴，高 shen 负值才 `kill_ob`（否则 `fight_ob` 切磋），需 neili 不足才触发。
- 限制：NPC 不自动打 NPC（:855 `if(!userp(me)&&!userp(obj)) return`）、`no_fight` 区禁自动开战、`looking_for_trouble` temp 防重复触发。

**验收**：4 种自动开战类型分明；旧仇/世仇持久记忆；狂暴按 shen/neili 判定；NPC 不互打；安全区与防重复触发保护。

---

## US-10：装备武器护具与双手/双武

**作为** 想提升战斗力的玩家，**我希望** 装备武器与护具获得数值加成，且支持双手武器/双持武器/副手盾，**以便** 配置战斗 build。

- `wield <装备>`：`cmds/std/wield.c:do_wield`（:36-52）调 `feature/equip.c:wield`（:46-107）。
- `equip.c:wield`：读 `weapon_prop` mapping，按 `flag` 位（`TWO_HANDED`/`SECONDARY`）决定主手/副手/双手；`owner->add_temp("apply/"+k, v)` 累加属性；`reset_action()` 重算 action（:104）。
- 双手武器占两手（:65-70）；副手武器需 `SECONDARY` flag（:82）；主副切换逻辑（:86-93）。
- `wear`（equip.c:7-44）：读 `armor_prop`，按 `armor_type` 槽位（同一类型只能一件，:29-30）；`apply` 累加属性。
- `unequip`（:109-140）：反向扣回属性，`reset_action`。
- 限制：`perform` condition 与武器 skill_type 不符时禁 wield（wield.c:40-42）；`is_busy` 禁 wield（wield.c:15）。
- 特殊护具回调：`combatd.c:do_attack` :548-557 `victim->query_temp("armor/cloth")->is_special()` 时调 `hit_by` 改伤害。

**验收**：武器/护具数值累加到 apply；双手/双持/副手盾槽位互斥；卸装反向扣属性；特殊护具有命中回调；战斗中禁换装。

---

## US-11：逃跑与 wimpy 自动脱战

**作为** 打不过的玩家，**我希望** 血量低时自动逃跑或手动 flee，**以便** 避免被杀。

- wimpy 自动逃跑：`char.c:heart_beat` :123-130 `if(is_fighting() && wimpy_ratio>0 && qi*100/max_qi<=ratio || jing... || jingli...)` -> `GO_CMD->do_flee(this)`。
- wimpy_ratio 来自 `query("env/wimpy")`（玩家环境变量，:125）。
- 逃跑即脱战：`team.c:follow_path` :32 `remove_all_enemy()`（移动清 enemy，但 killer 保留）。
- 手动 `flee`：`GO_CMD->do_flee` 随机选出口逃跑。
- 逃跑后仍被记仇：`remove_all_enemy`（attack.c:112-123）不清 `killer` 列表，旧仇 NPC 进同房仍 `auto_fight` hatred。
- 逃跑失败：出口被挡（`exit_blockers`）或无出口则 flee 无效。

**验收**：血量低于 wimpy 阈值自动 flee；逃跑清当前战斗但不清旧仇；可手动 flee；出口被挡时逃跑失败。

---

## US-12：伤势双层模型与疗伤/包扎恢复

**作为** 受伤的玩家，**我希望** 区分「当前体力」与「伤势上限」，并能通过内功疗伤/包扎/药物慢修复，**以便** 体验「轻伤易复-重伤难愈」的武侠医疗感。

- 双层伤害：`receive_damage`（damage.c:13-37）扣当前 `qi`/`jing`/`jingli`；`receive_wound`（:39-66）扣 `eff_qi`/`eff_jing`（伤势上限），并连带压低当前值。
- 自然回血：`heal_up()`（damage.c:270-331）每 tick 回复，战斗中回复减速（:288-302 `is_fighting` 时 jing/qi 回复量除以 3）；eff_* 慢修复（:293-296 `eff_jing++`）。
- 内功疗伤：`beiming-shengong/lifeheal.c` `exert` 疗伤--`target->receive_curing("qi", 10+force/2)`（:29）修伤势上限，战斗中禁用（:11），需 150 neili。
- `receive_curing`（damage.c:85-103）专修 `eff_*`（伤势上限），不超过 `max_*`。
- 包扎：`bandaged.c` condition 每 tick `receive_curing("qi",3+random(5))` 慢修伤势，或读 `medication` temp 加药效。
- `CND_NO_HEAL_UP`（condition.h=2）：部分 condition 阻止 `heal_up` 自然回血（char.c:149）。
- 伤势过重禁疗：`lifeheal.c:20-22` `if(target.eff_qi < target.max_qi/4) return`「受伤过重，经受不起你的真气震荡」。

**验收**：当前值与伤势上限分层；战斗中回血减速；内功疗伤修伤势上限但有门槛（neili/非战斗/伤势不过重）；包扎可慢修复；部分状态阻止自然回血。

---

## 跨故事交叉体验要点

1. **战斗烈度三档 + 自动开战四类 + wimpy 逃跑** 共同构成 PvP/PvE 的「开战-持续-退出」闭环：玩家可选择起手烈度（US-1），但 NPC 会按仇恨/世仇/狂暴/主动自动开战（US-9），打不过可 wimpy 自动逃跑（US-11）。新引擎应保留此闭环但需重新设计 PvP 同意制（LPC 的 fight 双向确认较原始）。
2. **Effect 系统是「正向 + 负向 + 控制」混合**：负向（毒/伤害/醉酒/刺目/嵌入，US-3/US-4）、正向（包扎/微醺回血/疗伤，US-4/US-12）、控制（killer/pker 通缉计时，US-7）。condition 引擎统一调度但缺少组合规则，新引擎应分类并补堆叠/互斥/优先级。
3. **两段式死亡 + 地府轮回 + 满血复活** 是「死亡有代价但游戏可继续」的设计（US-5/US-6）：昏迷可被补刀（US-5 的恐惧），死亡扣数值走地府（US-6 的惩罚），但最终满血复活。惩罚对老玩家极重（技能降级），新引擎应重新校准。
4. **围攻的隐式平衡 + 队长溃散**（US-8）：MAX_OPPONENT=4 限制被围攻者反击人数，但攻击者无限制--围攻方占优；队长倒下即溃散无递补。新引擎应显式建模围攻上限与队长转移。
5. **装备/武功/Effect 三层 build 耦合**（US-2/US-10/US-12）：武功通过 `hit_ob` 挂 Effect（US-2），装备通过 `apply/*` 加数值与 `hit_by` 回调（US-10），Effect 通过 `apply/attack`/`apply/defense` 改战斗数值（US-4 的 juehu）。三层共享 `apply/*` 临时属性池，是新引擎 UGC 创作层的核心耦合点。
