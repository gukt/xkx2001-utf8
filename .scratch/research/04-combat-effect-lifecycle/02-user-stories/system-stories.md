# 系统/NPC 自动触发视角 User Stories

> 产出方：战斗/效果机制设计师。本文件覆盖「系统与 NPC 自动触发」层 User Stories，对应 LPC 中由 `heart_beat` 战斗循环、`update_condition` Effect 周期结算、`unconcious`/`revive` 昏迷苏醒、地府 `death_stage` 轮回触发等**无玩家显式输入即自动执行**的行为。玩家层（player-stories）与巫师/运营层（operator-stories）由其他角色产出，不在此文件。
>
> 每条 Story 标注 LPC 证据（`文件:函数`），格式：`作为 <系统/NPC 角色>，我希望 <行为>，以便 <价值>`，附验收条件。

---

## Epic 1：心跳战斗循环（char.c heart_beat）

### Story 1.1 - 战斗 tick 驱动器自动选敌出手

**作为** 战斗系统核心调度器（`inherit/char/char.c` heart_beat），**我希望** 每 tick 在角色处于 `is_fighting()` 且非 `is_busy()` 时自动调用 `attack()` 选敌出手，**以便** 玩家无需逐招输入即可持续战斗。

**证据**：`char.c:118-133`（`if (is_busy()) continue_action(); else { wimpy 检查; attack(); }`）、`attack.c:208 attack()` -> `COMBAT_D->fight(this, opponent)`。

**验收**：
- 角色进入 `enemy` 列表后，下一 tick 自动发起 `attack()`。
- `is_busy()` 时不攻击，转 `continue_action()` 处理 busy 队列。
- `wimpy_ratio` 触发时自动 `GO_CMD->do_flee()` 逃跑（`char.c:124-130`，血量低于阈值自动跑）。
- 无对手时 `attack()` 返回 0，不报错。

### Story 1.2 - 硬死亡快道（创伤上限归零即死）

**作为** 战斗系统，**我希望** 当 `eff_qi` 或 `eff_jing` 小于 0 时跳过昏迷直接 `die()`，**以便** 严重创伤（非当前血量）致死不被昏迷缓冲挽救。

**证据**：`char.c:100-104`（`if (my["eff_qi"] < 0 || my["eff_jing"] < 0) { remove_all_enemy(); die(); return; }`）。

**验收**：
- `receive_wound` 把 `eff_qi`/`eff_jing` 扣到负值后，下一 tick `heart_beat` 第一段判定即死。
- 不经过 `unconcious()`，直接 `die()`。

### Story 1.3 - 两段式昏迷/死亡判定

**作为** 战斗系统，**我希望** 当前血量耗尽时先 `unconcious()`，已昏迷者再次负值才 `die()`，**以便** 玩家有一次"晕倒缓冲"而非一击必死。

**证据**：`char.c:108-115`（`if (qi<0 || jing<0 || jingli<0) { remove_all_enemy(); if (living()) unconcious(); else if (disable_type==" <昏迷不醒>") die(); }`）。

**验收**：
- 首次血量负值且 `living()==1` -> `unconcious()`，进入 `<昏迷不醒>` disable。
- 已 `<昏迷不醒>` 状态下再负值 -> `die()`。
- 非昏迷的 disable 状态（如 sleeping）血量负值不触发 die（注释 :110 明确："die only if falling unconcious"）。

### Story 1.4 - 静止时关闭心跳节能

**作为** 战斗系统，**我希望** 当角色完全无战斗、无 Effect、无交互且 `heal_up()` 无更新时 `set_heart_beat(0)` 关闭心跳，**以便** 节省 CPU（避免空转 tick）。

**证据**：`char.c:147-158`（`if (((cnd_flag & CND_NO_HEAL_UP) || !heal_up()) && !is_fighting() && !interactive(this)) { ... if (!ob) set_heart_beat(0); }`）。

**验收**：
- NPC 闲置于无玩家房间 -> 关闭心跳。
- 玩家掉线 linkdead -> 关闭心跳。
- `receive_damage`/`fight_ob`/`apply_condition` 等会 `set_heart_beat(1)` 重新点亮。

---

## Epic 2：Effect 周期结算引擎（condition.c）

### Story 2.1 - Effect 定时结算（每 6-15 tick 一次）

**作为** Effect 引擎（`feature/condition.c`），**我希望** 每 `tick` 次 heart_beat（`tick = 5 + random(10)`）调用一次 `update_condition()` 遍历所有 condition daemon，**以便** 持续性 Effect（中毒/内伤/通缉等）按周期结算而非每 tick 都跑（性能优化）。

**证据**：`char.c:54`（`tick = 5 + random(10);`）、`char.c:141-144`（`if (tick--) return; else tick = 5 + random(10); cnd_flag = update_condition();`）。

**验收**：
- Effect 结算频率 = heart_beat 频率 × (6-15 倍)。
- `update_condition` 返回 `cnd_flag`，包含 `CND_NO_HEAL_UP` 时禁止 `heal_up()`（`char.c:149`）。
- 无 condition 时 `update_condition` 返回 0，不阻止 heal_up。

### Story 2.2 - Effect daemon 懒加载与容错

**作为** Effect 引擎，**我希望** condition daemon 不存在时自动 `call_other(..., "???")` 加载，加载失败时写日志并从 mapping 移除该 condition，**以便** 单个坏 daemon 不卡死玩家心跳。

**证据**：`condition.c:36-51`（`cnd_d = find_object(CONDITION_D(cnd[i])); if (!cnd_d) { err = catch(call_other(CONDITION_D(cnd[i]), "???")); ... if (err || !cnd_d) { log_file("condition.err", ...); map_delete(conditions, cnd[i]); continue; } }`）。

**验收**：
- 首次 apply 的 condition 在下次 update 时触发 daemon 加载。
- daemon 文件不存在或编译错误 -> 写 `condition.err` 日志 + 从 `conditions` mapping 删除。
- 其他 condition 不受影响，继续结算。

### Story 2.3 - Effect 续期与过期协议

**作为** Effect daemon，**我希望** `update_condition(me, info)` 返回 `CND_CONTINUE` 则保留 condition，返回 0 或不含 `CND_CONTINUE` 则过期移除，**以便** Effect 自治生命周期。

**证据**：`condition.c:62-64`（`flag = call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]]); if (!(flag & CND_CONTINUE)) map_delete(conditions, cnd[i]);`）、`include/condition.h:6 #define CND_CONTINUE 1`。

**验收**：
- `bt_poison.c:41 return 1;`（=CND_CONTINUE）-> 保留。
- `killer.c:13 return 1;`（duration<1 时 return 0）-> 过期。
- daemon 自调 `apply_condition(cnd, duration-1)` 续期，duration 归零返回 0 移除。

### Story 2.4 - 持续伤害型 Effect 回灌伤害

**作为** 持续伤害 Effect（如 `bt_poison`/`hanbing_damage`/`hyz_damage`），**我希望** 每 tick 在 `update_condition` 内调 `receive_damage`/`receive_wound` 对受害者扣血，**以便** Effect 能独立致死（不依赖外部攻击）。

**证据**：`bt_poison.c:33-34`（`me->receive_wound("jing", damage/2, "身中西域灵蛇毒死掉了"); me->receive_damage("jingli", damage/2, "身中...死掉了");`）、`hanbing_damage.c:23-24`、`hyz_damage.c:30-31`、`sanpoison.c:39-40`、`embedded.c:17`（`me->receive_wound("qi", 3, "出血过多死了")`）。

**验收**：
- Effect 触发的伤害写入 `last_damage_from = "<原因字符串>"`（非 object）。
- 该伤害可触发 `unconcious`/`die`（通过 `set_heart_beat(1)` 点亮下一轮判定）。
- `die()` 中 `stringp(killer)` 分支播"被X毒死了"谣言（`damage.c:200-205`）。

### Story 2.5 - 交互触发型 Effect 扫描房间

**作为** 交互型 Effect（如 `aphroclisiac` 春药），**我希望** `update_condition` 内 `all_inventory(environment(me))` 扫描在场角色并对可见活物触发 emote/攻击，**以便** Effect 能驱动社交/战斗行为。

**证据**：`aphroclisiac.c:35-43`（`ob = all_inventory(environment(me)); for(...) if (!living(ob[i]) || ob[i]==me || !me->visible(ob[i])) continue; message_vision(...ra[random...]..., me, ob[i]); break;`）。

**验收**：
- 只对可见的、非自己的、活着的角色触发。
- 只触发第一个匹配对象（`break`）。

### Story 2.6 - 位移型 Effect 到期传送

**作为** 牢狱型 Effect（如 `city_jail`/`bonze_jail`/`dali_jail`），**我希望** `duration < 1` 时自动 `me->move(target_room)` 把角色传送到释放点，**以便** 刑满自动释放无需人工介入。

**证据**：`city_jail.c:9-14`（`if (duration < 1) { me->move("/d/city/yamen"); message("vision", ...); me->set("startroom", "/d/city/yamen"); ... return 0; }`）。

**验收**：
- duration 归零 -> 传送到指定房间 + 改 startroom + 播放出狱文案。
- 返回 0 使 condition 从 mapping 移除。

### Story 2.7 - 嵌入暗器 Effect 让 NPC 自动拔除

**作为** `embedded` Effect（嵌入暗器），**我希望** 对 NPC 且 `!is_fighting() && living()` 时自动调 `COMMAND_DIR"std/remove"->do_remove(me, ob)` 让 NPC 主动拔暗器，**以便** NPC 不依赖玩家指令自我恢复。

**证据**：`embedded.c:20-27`（`if (!userp(me) && me->query("race")=="人类" && living(me) && !me->is_fighting() && ob=me->query_temp("armor/embed")) { COMMAND_DIR"std/remove"->do_remove(me, ob); ... return 1; }`）。

**验收**：
- 玩家不会自动拔（`!userp(me)` 拦截），必须手动 `remove`。
- NPC 在非战斗、清醒时自动拔除嵌入暗器。

---

## Epic 3：昏迷与苏醒（damage.c unconcious/revive）

### Story 3.1 - 昏迷自动苏醒定时器

**作为** 昏迷机制（`feature/damage.c` unconcious），**我希望** `call_out("revive", random(100 - con) + 30)` 在 30+ 秒后自动苏醒，**以便** 昏迷者无需外部干预自醒，且 `con`（体质）越高醒越快。

**证据**：`damage.c:134`（`call_out("revive", random(100 - query("con")) + 30);`）。

**验收**：
- 苏醒时间 = 30 + random(100-con) 秒。
- `con` 越高 random 上限越低，醒得越快。
- `con >= 100` 时 random(0)=0，固定 30 秒醒。
- 期间 `block_msg/all=1` 屏蔽所有消息（玩家"眼前一黑"）。

### Story 3.2 - 苏醒时移出容器

**作为** revive 机制，**我希望** 苏醒时若角色被装进容器/生物体内（`environment()->is_character()`），逐层 `move(environment(environment))` 移出到真实房间，**以便** 不卡在容器里苏醒。

**证据**：`damage.c:140-141`（`while (environment()->is_character()) this_object()->move(environment(environment()));`）。

**验收**：
- 被抓进怪物肚子里昏迷 -> 苏醒时被吐出到怪物所在房间。
- 嵌套容器逐层外移。

### Story 3.3 - die() 中静默苏醒再判死

**作为** die 机制，**我希望** `die()` 被调用时若角色 `!living()`，先 `revive(1)` 静默苏醒再执行死亡流程，**以便** 死亡判定在"活体"状态下统一执行（避免昏迷中死亡的副作用混乱）。

**证据**：`damage.c:179`（`if (!living(this_object())) revive(1);`）。

**验收**：
- 已昏迷者被持续攻击到死 -> die() 先静默苏醒 -> 再走死亡流程。
- `revive(1)` 的 quiet 参数跳过苏醒文案。

### Story 3.4 - 安全区降级为昏迷

**作为** die 机制，**我希望** 在 `environment()->query("no_death") && userp(this)` 的安全区，`die()` 降级为 `unconcious()` + `remove_call_out("revive")`，**以便** 安全区玩家只晕不死。

**证据**：`damage.c:159-177`（`if (environment()->query("no_death") && userp(this_object())) { unconcious(); remove_call_out("revive"); return; }`）。

**验收**：
- 安全区血量耗尽 -> 走 unconcious 流程而非 die。
- 不扣 combat_exp/shen/skill（不走 death_penalty）。
- 不进地府、不留尸体。

---

## Epic 4：死亡与地府轮回（damage.c die + d/death/）

### Story 4.1 - 死亡强制清空所有 Effect

**作为** die 机制，**我希望** 死亡时 `clear_condition()` 清空所有 condition + `delete("poisoner")` 清毒源，**以便** 死者不带 Effect 进地府。

**证据**：`damage.c:184-185`（`this_object()->clear_condition(); this_object()->delete("poisoner");`）、`condition.c:105 clear_condition()`（`conditions = 0;`）。

**验收**：
- 所有中毒/内伤/通缉/通通清零。
- 地府区 `gate.c:38 init()` 会再 `clear_condition()` 一次（双保险）。

### Story 4.2 - 死亡造尸体并掉落

**作为** die 机制，**我希望** `CHAR_D->make_corpse(this, killer)` 造尸体物品并 `move` 到当前房间，**以便** 战利品（尸体）可被拾取/搜索/复活术施法。

**证据**：`damage.c:226-228`（`if ((!environment()->query("no_death") || !userp(this)) && objectp(corpse = CHAR_D->make_corpse(this_object(), killer))) corpse->move(environment());`）。

**验收**：
- 玩家与 NPC 死亡都造尸体（NPC 死亡在 destruct 前先造尸体）。
- 安全区不造尸体（`no_death` 拦截）。

### Story 4.3 - 玩家死亡进地府变鬼

**作为** die 机制，**我希望** 玩家死亡时 `ghost = 1` + `move(DEATH_ROOM)` + `DEATH_ROOM->start_death(this)`，**以便** 玩家以鬼魂形态进入地府走轮回。

**证据**：`damage.c:246-248`（`ghost = 1; this_object()->move(DEATH_ROOM); DEATH_ROOM->start_death(this_object());`）、`include/login.h:23 #define DEATH_ROOM "/d/death/gate.c"`。

**验收**：
- `is_ghost()` 返回 1，活人 `visible()` 看不见（`char.c:181-186`）。
- 三属性归 1（非 0，避免再触发死亡判定，`damage.c:236-238`）。
- 进入 `gate.c` 触发 `init()` 销毁所有物品 + `clear_condition()`。

### Story 4.4 - 地府白无常自动播报轮回

**作为** 地府 NPC 白无常（`d/death/npc/wgargoyle.c`），**我希望** 玩家进入房间时 `init()` 触发 `call_out("death_stage", 30, ob, 0)`，每 5 秒播一条 `death_msg`，最后自动 `reincarnate()` + `move(REVIVE_ROOM)`，**以便** 玩家无需操作即可在约 55 秒后自动复活。

**证据**：`wgargoyle.c:40-50 init()` -> `call_out("death_stage", 30, previous_object(), 0)`、`wgargoyle.c:53-72 death_stage()` 每 5 秒推进 stage，末尾 `ob->reincarnate()` + drop 物品 + `ob->move(REVIVE_ROOM)`。

**验收**：
- 玩家进 gate -> 30 秒后白无常开口 -> 每 5 秒一条台词（共 5 条）-> reincarnate。
- 复活前 `DROP_CMD->do_drop(ob, inv[i])` 掉落所有物品。
- 复活到 `REVIVE_ROOM`（或 `/d/xiakedao/shatan` 侠客岛特例，:69）。
- `ob->query("xkd/set")` 时传侠客岛沙滩（特殊复活点）。

### Story 4.5 - 地府主动探索分支立即复活

**作为** 地府 `inn1` 房间（小店），**我希望** 玩家"问自己回家"（`redirect_ask` 检测 `"<自己的id> about 回家"`）触发 `do_stuff(ob)` 立即 `reincarnate()` + `move("/d/city/wumiao")`，**以便** 探索型玩家可跳过等待立即复活。

**证据**：`d/death/inn1.c:45-78 do_stuff(ob)`（`write(...); ... ob->reincarnate(); ob->move("/d/city/wumiao"); message("vision", ...);`）。

**验收**：
- 玩家走到 inn1 + `ask <自己id> about 回家` -> 立即 reincarnate + 传五庙。
- 比被动等待快（无需 55 秒）。

### Story 4.6 - 地府单向流与迷雾循环

**作为** 地府 `gateway` 房间，**我希望** `valid_leave` 拦截 `dir=="south"` 阻止回头，**以便** 地府是单向流程不可逆。

**证据**：`d/death/gateway.c:25-32 valid_leave()`（`if (dir == "south") return notify_fail("...没有回头路了!\n");`）。

**作为** 地府 `road2` 房间，**我希望** `valid_leave` 对 `dir=="north"` 计 `long_road` temp 到 5 才放行，**以便** 制造"迷雾循环"延迟玩家。

**证据**：`d/death/road2.c:21-40 valid_leave()`（`i = me->query_temp("long_road") + 1; if (i==5) { delete; return 1; } else { set; return notify_fail("...景色居然都没有变..."); }`）。

**验收**：
- gateway 只能向北走。
- road2 需连续 5 次 north 才通过（中间 4 次被拦回）。
- `dir=="south"` 清 `long_road` 可回头。

### Story 4.7 - 复活满血但不恢复永久损失

**作为** reincarnate 机制，**我希望** 复活时 `ghost=0` + 三属性 + 创伤上限 + 内力精力全满，但**不**恢复 `combat_exp`/`shen`/`potential`/`skill`/`balance`，**以便** 死亡是真实损失而非"读档"。

**证据**：`damage.c:255-264 reincarnate()`（`ghost = 0; set("jing", max_jing); ... set("neili", max_neili);` -- 仅恢复血量类，不恢复经验/技能/善恶/潜能/存款）。

**验收**：
- 复活后 `is_ghost()==0`，活人可见。
- 当前值与创伤上限全满。
- `combat_exp`/`skill_map`/`potential`/`shen`/`balance` 保持 death_penalty 扣减后的状态。

### Story 4.8 - 死亡时强制存档

**作为** die 机制，**我希望** 玩家死亡时 `this_object()->save()` 强制存档，**以便** 保存 `ghost=1` 状态，防止掉线规避死亡。

**证据**：`damage.c:245`（`this_object()->save();`，在 `ghost=1` 与 `move(DEATH_ROOM)` 之间）。

**验收**：
- 存档发生在 ghost 标志置位之后、移动地府之前。
- 掉线重连后仍在地府。

### Story 4.9 - 死亡解除社交关系

**作为** die 机制，**我希望** 玩家死亡时自动 `dismiss_team()` 解散队伍 + `MARRY_D->break_marriage(this)` 解除婚姻 + 师徒关系特殊处理，**以便** 死亡切断社交绑定。

**证据**：`damage.c:244`（`this_object()->dismiss_team();`）、`:249`（`MARRY_D->break_marriage(this_object());`）、`:250`（风清扬师徒 break_relation）。

**验收**：
- 死亡后不在任何队伍。
- 婚姻关系解除。
- 特定师父（风清扬）的师徒关系解除。

---

## Epic 5：战斗事件自动播报（combatd.c announce + status）

### Story 5.1 - 战斗事件自动 announce

**作为** 战斗系统，**我希望** `unconcious()`/`die()`/`revive()` 自动调 `COMBAT_D->announce(this, event)` 播角色专属文案，**以便** 战斗关键事件对房间可见。

**证据**：`damage.c:132`（`COMBAT_D->announce(this_object(), "unconcious");`）、`:144`（`"revive"`）、`:187`（`"dead"`）、`combatd.c:966-980 announce()` 读 `ob->query("dead_message"/"unconcious_message"/"revive_message")`。

**验收**：
- 死亡/昏迷/苏醒三种事件播三种角色定义文案。
- 文案由角色对象提供（`dead_message` 等字段），可定制。

### Story 5.2 - 受伤状态条自动播报

**作为** do_attack 机制，**我希望** 命中后 `if (damage > 0) report_status(victim, wounded)` 自动播当前状态条，**以便** 战斗中实时显示伤情。

**证据**：`combatd.c:744-746`（`if (damage > 0) { report_status(victim, wounded); ... }`）、`combatd.c:278-284 report_status()`。

**验收**：
- 命中伤害 > 0 后自动播 `( $N看起来... )` 状态条。
- `wounded==1` 播 `eff_status_msg`（创伤比例），`wounded==0` 播 `status_msg`（当前气血比例）。
- 状态条颜色随比例从绿->黄->红渐变。

### Story 5.3 - 双方非 kill 模式自动休战

**作为** do_attack 机制，**我希望** 双方都非 `is_killing` 且受害者血量过半时自动 `remove_enemy` 互退 + 播 `winner_msg`，**以便** 切磋自然收手而非打到死。

**证据**：`combatd.c:749-759`（`if ((!me->is_killing(your["id"])) && (!victim->is_killing(my["id"])) && victim->query("qi")*2 <= victim->query("max_qi")) { me->remove_enemy(victim); victim->remove_enemy(me); message_vision(winner_msg/...); }`）。

**验收**：
- 只在双方都用 `fight` 而非 `kill` 时触发。
- 受害者 qi ≤ max_qi/2 时自动休战。
- 播 winner_msg（人类）或 winner_animal_msg（野兽）。

### Story 5.4 - 受害者被命中时打断 busy

**作为** do_attack 机制，**我希望** 受害者 `is_busy()` 时被命中触发 `victim->interrupt_me(me)`，**以便** 命中可打断对方施法/运功。

**证据**：`combatd.c:747-748`（`if (victim->is_busy()) victim->interrupt_me(me);`）。

**验收**：
- 受害者 busy 状态下被命中 -> interrupt_me 打断当前动作。
- 攻击者可以是任意 enemy。

### Story 5.5 - Riposte 反击自动触发

**作为** do_attack 机制，**我希望** `TYPE_REGULAR` 攻击落空（`damage<1`）且受害者处于 `guarding` 状态时，按 `apply/speed` 对抗决定受害者是否自动反击一招，**以便** 防御者有反击机会。

**证据**：`combatd.c:766-779`（`if (attack_type==TYPE_REGULAR && damage<1 && victim->query_temp("guarding") && random(1-apply/speed) < random((1-apply/speed)*6)) { ... do_attack(victim, me, victim->weapon, TYPE_QUICK 或 TYPE_RIPOSTE); }`）。

**验收**：
- 攻击落空 + 受害者 guarding -> 速度对抗判定。
- 成功 -> 受害者反击，`TYPE_QUICK`（dex<5 漏破绽）或 `TYPE_RIPOSTE`（正常反击）。
- 反击后 `victim->set_temp("guarding", 0)` 退出防御。

---

## Epic 6：自动开战触发器（attack.c init + combatd.c auto_fight）

### Story 6.1 - 仇人见面自动开战

**作为** 角色的 `init()`（房间进入回调），**我希望** 检测到 `is_killing(ob->id)` 为真的仇人进入时自动 `COMBAT_D->auto_fight(this, ob, "hatred")`，**以便** 旧仇无需手动重启自动开打。

**证据**：`attack.c:247-249`（`if (userp(ob) && is_killing(ob->query("id"))) { COMBAT_D->auto_fight(this_object(), ob, "hatred"); return; }`）。

**验收**：
- 仇人进入房间 -> `call_out("start_hatred", 0, ...)` 异步触发。
- `start_hatred` 检查 `is_fighting || !living || environment!=environment || no_fight` 任一为真即放弃。
- 通过则 `me->kill_ob(obj)` + 播 `catch_hunt_*_msg`（按 race 分系）。

### Story 6.2 - 世仇自动开战

**作为** 角色 init，**我希望** `vendetta_mark` 匹配时自动 `auto_fight(..., "vendetta")`，**以便** 门派世仇自动触发。

**证据**：`attack.c:250-253`（`else if (stringp(vendetta_mark = query("vendetta_mark")) && ob->query("vendetta/" + vendetta_mark)) { COMBAT_D->auto_fight(this_object(), ob, "vendetta"); return; }`）。

**验收**：
- NPC 有 `vendetta_mark`（如"丐袋"标识）+ 玩家 `vendetta/<mark>` 计数 > 0 -> 自动开战。
- `killer_reward` 会 `killer->add("vendetta/"+vmark, 1)` 累加世仇（`combatd.c:1092`）。

### Story 6.3 - aggressive NPC 自动猎杀

**作为** NPC（`attitude="aggressive"`），**我希望** 玩家进入房间时自动 `auto_fight(..., "aggressive")` 猎杀，**以便** 嗜杀 NPC 主动攻击玩家。

**证据**：`attack.c:254-257`（`else if (userp(ob) && (string)query("attitude")=="aggressive") { COMBAT_D->auto_fight(this_object(), ob, "aggressive"); return; }`）。

**验收**：
- 仅对玩家触发（`userp(ob)`），NPC 不互咬（`auto_fight:855 if (!userp(me) && !userp(obj)) return;`）。
- `start_aggressive` 直接 `me->kill_ob(obj)`（无文案，:961）。

### Story 6.4 - berserk 狂暴自动开战（受 neili 克制）

**作为** berserk NPC，**我希望** `shen`（负善值=恶）超过 `quest_exp` 且 `neili` 不足以克制时自动 `kill_ob`，否则降级为 `fight_ob`，**以便** 狂暴状态受内力意志克制。

**证据**：`combatd.c:869-902 start_berserk()`（`shen = 0 - me->query("shen"); if (!userp(me) || me->query("neili") > (random(shen)+shen)/10) return; if (shen > me->query("quest_exp") && !wizardp(obj)) me->kill_ob(obj); else me->fight_ob(obj);`）。

**验收**：
- 善值正（`shen<0` 取反后为负）不触发。
- `neili > (shen+random(shen))/10` 内力克制住 -> 不出手。
- 恶值超过 quest_exp -> kill_ob；否则 fight_ob 切磋。

### Story 6.5 - NPC NPC 不互咬

**作为** auto_fight 机制，**我希望** `if (!userp(me) && !userp(obj)) return;` 阻止 NPC 之间自动开战，**以便** 避免城镇 NPC 互相屠杀。

**证据**：`combatd.c:855`（`if (!userp(me) && !userp(obj)) return;`）。

**验收**：
- 两个 aggressive NPC 相遇不自动开战。
- 至少一方是玩家才触发 auto_fight。

---

## Epic 7：NPC 战斗 AI（npc.c chat）

### Story 7.1 - NPC 内功自动恢复

**作为** NPC chat 调度器，**我希望** `neili > 100` 时按比例自动 `exert refresh/recover/regenerate`，**以便** NPC 在战斗中自我恢复精力/气血/精神。

**证据**：`inherit/char/npc.c:100-107`（`if (query("neili") > 100 && living(this)) { if (jingli*100/max_jingli < 90) SKILL_D("force")->exert_function(this, "refresh"); if (qi*100/(eff_qi+2) < 80) ... "recover"; if (jing*100/(eff_jing+2) < 70) ... "regenerate"; }`）。

**验收**：
- NPC neili > 100 且活着 -> 按阈值自动运功恢复。
- 三个阈值：jingli < 90% / qi < 80% / jing < 70%。
- 用 mapped force 技能（`query_skill_mapped("force")`），否则用默认 force。

### Story 7.2 - NPC 随机行为/招式触发

**作为** NPC chat 调度器，**我希望** 按 `chat_chance`/`chat_chance_combat` 概率触发 `chat_msg`/`chat_msg_combat` 数组中的随机项（string 播报 / functionp 执行），**以便** NPC 有随机行为与战斗招式。

**证据**：`npc.c:115-125`（`if (!chance = query(is_fighting()?"chat_chance_combat":"chat_chance")) return 0; if (arrayp(msg = query(is_fighting()?"chat_msg_combat":"chat_msg"))) { if (random(100) < chance && sizeof(msg)) { rnd = random(sizeof(msg)); if (stringp(msg[rnd])) say(msg[rnd]); else if (functionp(msg[rnd])) return evaluate(msg[rnd]); } }`）。

**验收**：
- 战斗中走 `chat_msg_combat`，非战斗走 `chat_msg`。
- `random(100) < chance` 概率触发。
- string 项 `say()` 播报，function 项 `evaluate()` 执行（可触发 perform/exert 等）。

### Story 7.3 - NPC 自动施法/运功/放绝技

**作为** NPC 默认 chat 函数，**我希望** 提供 `cast_spell`/`exert_function`/`perform_action` 默认实现，**以便** NPC 可在 chat 中自动施法/运功/放绝技。

**证据**：`npc.c:154-206`（`void cast_spell(string spell) { if (stringp(spell_skill = query_skill_mapped("spells"))) SKILL_D(spell_skill)->cast_spell(this_object(), spell); }` + `exert_function` + `perform_action(action)` 解析 `"martial.act"` 调 `SKILL_D(martial_skill)->perform_action(this, act)`）。

**验收**：
- NPC 可在 chat_msg_combat 中用 `(: perform_action, "xianglong-zhang.leiting" :)` 触发绝技。
- `perform_action` 内部分解 `"martial.act"` -> 查 `skill_map` -> 调 `SKILL_D` 的 `perform_action`。
- 被 `temp("feng")` 标志拦截时跳过（pfm feng 特殊机制，:203）。

### Story 7.4 - NPC 自动随机移动

**作为** NPC 默认 chat 函数 `random_move()`，**我希望** 按 `exits` 随机选方向移动，**以便** NPC 在世界游荡。

**证据**：`npc.c:130-152 random_move()`（`exits = environment()->query("exits"); dirs = keys(exits); dir = dirs[random(sizeof(dirs))]; if (doors[dir] & DOOR_CLOSED) command("open " + dir); command("go " + dir);`）。

**验收**：
- `jingli < max_jingli/2` 不移动（体力不足）。
- 人类种族可开门后通过（`doors[dir] & DOOR_CLOSED`）。
- 非人类不开门。

### Story 7.5 - 驯兽自动咬人（trainee.c）

**作为** 驯兽 NPC（`inherit/char/trainee.c`），**我希望** 主人对它下 `yao/attack <victim>` 命令时 `do_yao` -> `call_out("biting", 1, me, vc)` 让野兽自动 `kill_ob` 目标，**以便** 驯兽可被指挥攻击。

**证据**：`trainee.c:139-165 do_yao(victim)`（`call_out("biting",1,me,vc);`）、`:227-229 biting(me, ob)`（`me->kill_ob(ob);`）。

**验收**：
- 主人命令 `yao <victim>` -> 野兽 1 秒后 `kill_ob(victim)`。
- 目标不在同房间则 `biting` 直接返回（:228 检查 `environment(ob) != environment()`）。
- 野兽有 `wildness`/`loyalty` 属性影响服从度（:32-34）。

### Story 7.6 - 驯兽自动跟随主人

**作为** 驯兽 NPC，**我希望** `auto_follow=1` 时自动 `set_leader(ob)` 跟随主人移动，**以便** 驯兽无需手动 `gen` 即跟随。

**证据**：`trainee.c:78 me->set_lord(ob)` + `:81 me->set_leader(ob)`（驯服成功后），`team.c:37 follow_me` 自动跟随逻辑。

**验收**：
- 驯服成功（`training_pts > 100`）-> set_lord + set_leader。
- 主人移动时 `follow_me` 按 move 技能对抗判定跟上。
- 野兽 dis_follow 时 `remove_all_enemy`（`team.c:32` 副作用）。

---

## Epic 8：战斗奖励与惩罚自动结算（combatd.c）

### Story 8.1 - 击败者自动奖励（winner_reward）

**作为** unconcious 机制，**我希望** `unconcious()` 时 `COMBAT_D->winner_reward(defeater, this)` 自动给击败者奖励，**以便** 切磋击败有奖励。

**证据**：`damage.c:114`（`COMBAT_D->winner_reward(defeater, this_object());`）、`combatd.c:982-985 winner_reward()`（`killer->defeated_enemy(victim);` 调 mudlib apply）。

**验收**：
- 昏迷时给 `last_damage_from` 对象调用 `defeated_enemy` apply。
- 击败者若是玩家，记录 `last_fainted_from`（:117）。

### Story 8.2 - 杀手奖励自动结算（killer_reward）

**作为** die 机制，**我希望** `die()` 时有 killer 对象则 `COMBAT_D->killer_reward(killer, this)` 自动结算 PKS/MKS/通缉/世仇等，**以便** 杀手无需人工颁奖。

**证据**：`damage.c:193-194`（`set_temp("my_killer", killer->query("id")); COMBAT_D->killer_reward(killer, this_object());`）、`combatd.c:1027-1096 killer_reward()`。

**验收**：
- 杀玩家 -> `PKS+=1` + 城内 PK 挂 `killer` condition 100 tick + 撒谣言。
- 杀 NPC 人类 -> `MKS+=1`。
- 杀手 combat_exp 在 victim 的 1/4~1 倍区间 -> 扣 `shen`（杀正派掉善值）。
- PK 惩罚累加 `apply_condition("pker", old+120)`。

### Story 8.3 - 死亡惩罚自动扣除（death_penalty）

**作为** die 机制，**我希望** 玩家死亡时 `COMBAT_D->death_penalty(this)` 自动扣 combat_exp/shen/potential/skill/balance + `skill_death_penalty()` 全技能 -1，**以便** 死亡有真实损失。

**证据**：`damage.c:190`（`COMBAT_D->death_penalty(this_object());`）、`combatd.c:987-1025 death_penalty()`、`skill.c:121-147 skill_death_penalty()`。

**验收**：
- `death_times` 递增（若 combat_exp 达门槛）。
- `shen`/`behavior_exp` 扣 5%。
- `combat_exp` 扣 1%（封顶 5000）。
- `potential` 减半。
- `balance` 超 10000 部分扣半。
- 全技能等级 -1，`skill_map = 0` 清映射。
- 末尾 `victim->save()` 存档。

### Story 8.4 - 死亡日志自动记录

**作为** die 机制，**我希望** 玩家死亡时按死因分类写 `PKILL_DATA`/`PLAYER_DEATH` 日志，**以便** 巫师可追溯死亡原因。

**证据**：`damage.c:209-224`（`if (stringp(query_temp("last_eff_damage_from"))) log_file("PKILL_DATA", ...被X杀死了 PlayerKill...); else if (objectp(killer)) log_file("PLAYER_DEATH", ...被X杀死了...); else if (stringp(killer)) log_file("PLAYER_DEATH", ...died from X...);`）。

**验收**：
- 玩家杀手（`last_eff_damage_from` 字符串）-> 写 PKILL_DATA + PLAYER_DEATH。
- NPC 杀手（object）-> 写 PLAYER_DEATH。
- 字符串死因（毒等）-> 写 PLAYER_DEATH "died from <string>"。

---

## Epic 9：其他自动行为

### Story 9.1 - 挂机超时自动踢线

**作为** heart_beat 机制，**我希望** `query_idle(this) > IDLE_TIMEOUT` 时 `user_dump(DUMP_IDLE)` 自动踢挂机玩家，**以便** 释放服务器资源。

**证据**：`char.c:167-168`（`if (query_idle(this_object()) > IDLE_TIMEOUT) this_object()->user_dump(DUMP_IDLE);`）。

**验收**：
- 仅对玩家（`if (!interactive(this)) return;` 在 :160）。
- idle 超时自动 dump。

### Story 9.2 - 频道刷屏自动禁言

**作为** heart_beat 机制，**我希望** `channel_msg_cnt > 10` 时自动 `chblk_on=1` 禁言 + 播谣言，**以便** 防止频道刷屏。

**证据**：`char.c:72-79`（`if ((int)query_temp("channel_msg_cnt") > 10) { ... CHANNEL_D->do_channel(rum_ob,"rumor","...频道被关闭了"); set("chblk_on", 1); } set_temp("channel_msg_cnt", 0);`）。

**验收**：
- 每 tick 重置 `channel_msg_cnt`。
- 超 10 条 -> 禁言 + 撒谣言。

### Story 9.3 - 内力/精力超上限自动 clamp

**作为** heart_beat 机制，**我希望** `neili > max_neili*2` / `jingli > max_jingli*2` / `jing > max_jing*2` 时自动 clamp 到 2 倍上限，**以便** 防止数值溢出。

**证据**：`char.c:84-97`（`if (my["neili"] > my["max_neili"]*2) my["neili"] = my["max_neili"]*2;` + jingli + jing）。

**验收**：
- 每 tick 检查并 clamp 三属性。
- 允许超 max 至 2 倍（积攒机制），但不超 2 倍。

### Story 9.4 - 战斗中自然恢复降速

**作为** heal_up 机制，**我希望** `is_fighting()` 时恢复速率降为非战斗的 1/3，**以便** 战斗中无法靠自然回血拖时间。

**证据**：`damage.c:288-302`（`if (this_object()->is_fighting()) my["jing"] += my["con"]/9 + my["max_jingli"]/30; else my["jing"] += my["con"]/3 + my["max_jingli"]/10;` + qi + jingli + neili 类似）。

**验收**：
- 战斗中 con/9，非战斗 con/3。
- jingli 战斗中 (str+dex)/12，非战斗 /4。
- neili 战斗中 skill("force")/6，非战斗 /2。

### Story 9.5 - 水食耗尽停止恢复

**作为** heal_up 机制，**我希望** `water<1 || food<1` 时玩家停止恢复，**以便** 饥渴会断奶。

**证据**：`damage.c:281-285`（`if (my["water"] > 0) { my["water"] -= 1; update_flag++; } if (my["food"] > 0) { my["food"] -= 1; update_flag++; } if (my["water"] < 1 && userp(this)) return update_flag; if (my["food"] < 1 && userp(this)) return update_flag;`）。

**验收**：
- 玩家 water/food 任一归零 -> 立即 return，跳过后续恢复。
- NPC 不受此限（`userp` 拦截）。

### Story 9.6 - 双手互博/辟邪剑自动副手攻击

**作为** fight 机制，**我希望** 特殊条件（双手互博 `prepare > 1` / 辟邪剑 `pixie-jian>=60 + 无性` / `double_attack`）下，主攻击后自动补一记副手 `do_attack`，**以便** 这些特性能多打一招。

**证据**：`combatd.c:807-814`（`if ((!weapon && prepare>1) || (weapon sword && pixie-jian>=60 && mapped==pixie-jian && gender==无性) || (double_attack && !weapon)) { me->set_temp("action_flag", 1); do_attack(me, victim, weapon, TYPE_QUICK); me->set_temp("action_flag", 0); }`）。

**验收**：
- 满足条件 -> 主攻击后 `action_flag=1` 副手攻击再 `action_flag=0`。
- 双手互博需空手 + prepare > 1。
- 辟邪剑需剑 + 无性 + 60 级。
- double_attack 需空手 + 属性。

---

## 附录：系统故事覆盖矩阵

| 自动行为 | Epic | Story | 触发源 | 频率 |
|---------|------|-------|--------|------|
| heart_beat 战斗 tick | 1 | 1.1 | char.c:60 | 每 heart_beat |
| 硬死亡快道 | 1 | 1.2 | char.c:100 | 每 heart_beat |
| 两段式判定 | 1 | 1.3 | char.c:108 | 每 heart_beat |
| 心跳节能 | 1 | 1.4 | char.c:147 | 静止时 |
| Effect 周期结算 | 2 | 2.1 | char.c:144 | 每 6-15 tick |
| Effect daemon 容错 | 2 | 2.2 | condition.c:36 | 每次 update |
| Effect 续期/过期 | 2 | 2.3 | condition.c:62 | 每次 update |
| Effect 回灌伤害 | 2 | 2.4 | bt_poison.c:33 等 | 每 tick |
| Effect 扫描房间 | 2 | 2.5 | aphroclisiac.c:35 | 每 tick |
| Effect 到期传送 | 2 | 2.6 | city_jail.c:9 | duration 归零 |
| NPC 自动拔暗器 | 2 | 2.7 | embedded.c:20 | 每 tick |
| 昏迷自动苏醒 | 3 | 3.1 | damage.c:134 | 30+ 秒 |
| 苏醒移出容器 | 3 | 3.2 | damage.c:140 | revive 时 |
| die 静默苏醒 | 3 | 3.3 | damage.c:179 | die 时 |
| 安全区降昏迷 | 3 | 3.4 | damage.c:159 | die 时 |
| 死亡清 Effect | 4 | 4.1 | damage.c:184 | die 时 |
| 死亡造尸体 | 4 | 4.2 | damage.c:226 | die 时 |
| 进地府变鬼 | 4 | 4.3 | damage.c:246 | die 时 |
| 白无常自动轮回 | 4 | 4.4 | wgargoyle.c:40 | 进 gate 55 秒 |
| inn1 主动复活 | 4 | 4.5 | inn1.c:45 | ask 触发 |
| 地府单向流 | 4 | 4.6 | gateway/road2 | 移动时 |
| 复活满血不补损失 | 4 | 4.7 | damage.c:255 | reincarnate 时 |
| 死亡强制存档 | 4 | 4.8 | damage.c:245 | die 时 |
| 死亡解社交 | 4 | 4.9 | damage.c:244,249 | die 时 |
| 战斗事件 announce | 5 | 5.1 | combatd.c:966 | unconcious/die/revive |
| 状态条播报 | 5 | 5.2 | combatd.c:744 | 命中后 |
| 双方 fight 自动休战 | 5 | 5.3 | combatd.c:749 | qi 过半 |
| 命中打断 busy | 5 | 5.4 | combatd.c:747 | 命中时 |
| Riposte 反击 | 5 | 5.5 | combatd.c:766 | 落空+guarding |
| 仇人自动开战 | 6 | 6.1 | attack.c:247 | 房间进入 |
| 世仇自动开战 | 6 | 6.2 | attack.c:250 | 房间进入 |
| aggressive NPC 猎杀 | 6 | 6.3 | attack.c:254 | 房间进入 |
| berserk 受 neili 克制 | 6 | 6.4 | combatd.c:869 | 房间进入 |
| NPC 不互咬 | 6 | 6.5 | combatd.c:855 | auto_fight |
| NPC 内功自恢 | 7 | 7.1 | npc.c:100 | 每 chat |
| NPC 随机行为 | 7 | 7.2 | npc.c:115 | 每 chat |
| NPC 自动施法 | 7 | 7.3 | npc.c:154 | chat_msg |
| NPC 随机移动 | 7 | 7.4 | npc.c:130 | 每 chat |
| 驯兽咬人 | 7 | 7.5 | trainee.c:139 | 命令触发 |
| 驯兽跟随 | 7 | 7.6 | trainee.c:78 | 驯服后 |
| 击败者奖励 | 8 | 8.1 | damage.c:114 | unconcious |
| 杀手奖励 | 8 | 8.2 | damage.c:193 | die |
| 死亡惩罚 | 8 | 8.3 | damage.c:190 | die |
| 死亡日志 | 8 | 8.4 | damage.c:209 | die |
| 挂机踢线 | 9 | 9.1 | char.c:167 | 每 tick |
| 频道刷屏禁言 | 9 | 9.2 | char.c:72 | 每 tick |
| 数值超限 clamp | 9 | 9.3 | char.c:84 | 每 tick |
| 战斗恢复降速 | 9 | 9.4 | damage.c:288 | heal_up |
| 水食断奶 | 9 | 9.5 | damage.c:281 | heal_up |
| 双手互博副手 | 9 | 9.6 | combatd.c:807 | 命中后 |
