# 04 战斗与效果生命周期簇 — LPC 源码考古清单

> 产出角色：LPC 源码考古员（一手考古组）
> 唯一真相源：仓库根目录下 LPC 一手源码（`feature/` `inherit/` `adm/daemons/` `kungfu/` `d/death/` `cmds/std/` `include/`）。
> 范围：战斗（命中→伤害）/ 状态Effect（时效播报）/ 死亡与轮回 / 武功技能（命中来源与 effect 载体）/ 装备（战斗数值）/ 战斗命令。
> 证据约定：每条结论后用 `(file:path:line / fn-or-obj)` 标注来源；行号以本仓库当前 HEAD 为准。

---

## 1. 总体分布

### 1.1 战斗核心 feature 层（6 个活文件 + 3 个备份）

| 文件 | 行数 | 职责 |
|---|---|---|
| `feature/attack.c` | 258 | 敌对列表 `enemy[]`/`killer[]`、`fight_ob`/`kill_ob`/`is_fighting`/`is_killing`/`remove_enemy`/`remove_killer`/`remove_all_enemy`/`remove_all_killer`、`select_opponent`/`attack()`/`special_attack()`、`reset_action()` 武功→动作接口、`init()` 自动开战 (feature/attack.c:229-258) |
| `feature/damage.c` | 331 | 三类伤害 `receive_damage`/`receive_wound`/`receive_heal`/`receive_curing`、`ghost` 鬼魂态、`unconcious()`/`revive()`/`die()`/`reincarnate()`、`heal_up()` 自然恢复（战斗 vs 和平差速） |
| `feature/condition.c` | 113 | `conditions` mapping、`update_condition()` 由 heart_beat 驱动、`apply_condition`/`query_condition`/`clear_condition`/`clear_all_condition`、外部 daemon 分发（`CONDITION_D(x)` 宏） |
| `feature/skill.c` | 183 | `skills`/`learned`/`skill_map`/`skill_prepare` 四个 mapping、`set_skill`/`map_skill`/`prepare_skill`/`query_skill`/`improve_skill`/`skill_death_penalty` |
| `feature/team.c` | 127 | `leader`/`lord`/`team[]`、`follow_me`/`follow_path`、`add_team_member`/`join_team`/`dismiss_team`/`is_team_leader` |
| `feature/equip.c` | 140 | `wear()`/`wield()`/`unequip()`，聚合 `armor_prop`/`weapon_prop` 到 `apply/*` 临时修饰、双手/副手武器槽位切换 |
| `feature/attback.c` | 218 | `attack.c` 的旧版备份（无 `S_COMBAT_D` special_attack 分支），保留以备回滚 |
| `feature/damage.c.bk` | 27 | `damage.c` 极小备份（仅 receive_damage 片段） |
| `feature/damage_backup.c` | 312 | `damage.c` 的较大备份版本（含独立 `die()`，无 `last_eff_damage_from`/PKILL 日志） |

> 备注：`.bk`/`_backup`/`attback.c` 是历史快照，运行时未被 inherit，仅供考古对照。

### 1.2 inherit/char 战斗循环层（4 个文件）

| 文件 | 行数 | 职责 |
|---|---|---|
| `inherit/char/char.c` | 187 | 角色基类，组合 14 个 F_* feature；`heart_beat()` 战斗循环主驱动（char.c:60-169）；`visible()` 含 ghost 可见性判定 (char.c:171-187) |
| `inherit/char/trainee.c` | 232 | 野兽/坐骑 NPC AI：`do_gen`/`do_yao`/`do_ting`/`do_fang`/`do_stop` 命令、`train_it` 忠诚度训练、`biting()` 主动 `kill_ob` (trainee.c:227-232) |
| `inherit/char/npc.c` | 186 | NPC 调度：`chat()` 战斗/非战斗消息分发、`random_move`、`cast_spell`/`exert_function`/`perform_action` 委托到 SKILL_D (npc.c:154-185)、`accept_fight`/`accept_kill`/`return_home` |
| `inherit/char/master.c` | 29 | 占位文件（仅 create + seteuid） |

### 1.3 战斗 daemon（adm/daemons/）

| 文件 | 行数 | 职责 |
|---|---|---|
| `adm/daemons/combatd.c` | 1098 | 主战斗 daemon（`COMBAT_D` 宏指向）。包含 `damage_msg`/`eff_status_msg`/`status_msg`/`report_status`、`skill_power` 数值公式、`do_attack`（7 步：选技→取动作→AP/DP→闪避/招架/命中→结算伤害→给经验→反击）、`fight`、`auto_fight`+`start_berserk`/`start_hatred`/`start_vendetta`/`start_aggressive`、`announce`、`winner_reward`、`death_penalty`、`killer_reward` |
| `adm/daemons/s_combatd.c` | 974 | 原型战斗 daemon（`S_COMBAT_D` 宏指向）。结构与 combatd.c 几乎一致，差异：含 `anubis_attack()` 双手互博特殊攻击分支 (s_combatd.c:247-287)；`skill_power` 公式略简（无 str/dex 300 上限钳制）；`perform_action` 调用会附带 `apply_condition("perform", 5)` 锁。注释明确称"prototype"，仅 `attack.c:special_attack()` 在 `stand/anubis` temp 标志下使用 (feature/attack.c:197-206) |
| `adm/daemons/chard.c` | 192 | 角色守护：`setup_char`（按 race 计算属性）、`make_corpse`（生成尸体+物品转移+was_userp 标记，chard.c:116-171）、`break_relation`（风清扬师徒关系解除） |

### 1.4 状态/Effect 内容层（kungfu/condition/，72 个 .c 文件，~2421 行）

> 全清单（72 条，按功能聚合）：

- **持续伤害类（DoT，每 tick 扣数值）**：`hanbing_damage`(寒冰绵掌阴毒, 31 行)、`jiujian_qi_damage`、`juehu_damage`(绝户爪, 62 行，附带 `apply/attack`/`apply/defense` 削弱与性别改造)、`hyz_damage`、`qs_damage`、`qs_self_damage`、`yyz_damage`(玉阳针, 59 行)
- **毒类（持续伤害 + 文案播报）**：`bt_poison`(西域灵蛇毒, 42 行)、`chilian_poison`、`hsf_poison`、`huadu_poison`、`insect_poison`、`snake_poison`、`xx_poison`(星宿毒, 37 行)、`xx_poisonold`、`sxs_poison`、`zf_poison`(100 行)、`rose_poison`、`sanpoison`、`sl_poison`、`qianzhu-poison`、`mang_shedan`、`xianglu-du`(43 行)
- **控制/状态干扰**：`aphroclisiac`(春药, 48 行，强制攻击随机目标)、`blind`(盲, 36 行，扣除 apply/attack+apply/defense 后通过 `let_know` 还原)、`drunk`(醉, 35 行，过量直接 `unconcious`)、`sleep`、`slumber_drug`、`laugh`、`embedded`(嵌入暗器, 37 行，每 tick 扣 qi + NPC 自动拔除)
- **恢复/治疗**：`bandaged`(绷带, 42 行，按 `temp/medication` 治疗 eff_qi)、`jing_curing`、`neili_save`、`zuochan`(坐禅, 40 行)
- **监禁计时**：`city_jail`(24 行，到时 move 到 /d/city/yamen)、`dali_jail`、`bonze_jail`
- **PK/犯罪追踪**：`killer`(14 行，官府通缉倒计时)、`pker`(11 行，PK 杀气累加)、`xakiller`(14 行)、`dlkiller`、`wei_pk`(15 行)、`poisoned`
- **任务/职业计时**：`biao`、`biaoju`、`gb_job`(丐帮 job)、`hz_job`、`lmjob`、`lyjob`、`ypjob`、`th_gain`、`th_yapu_fail`、`th_yapu_job`、`ts_pending`、`xbiao`、`work`(11 行)、`drug_purchase`、`jin_used`
- **杂项/特殊**：`perform`(11 行，pfm 锁，仅在 is_fighting 时持续)、`pregnant`、`santa`、`vote_clear`、`vote_suspension`、`b_ciwan`、`b_cizu`、`zhao`、`tiaoshui`、`bonze_drug`、`cool_drug`、`hot_drug`、`slumber_drug`、`xs_necromancy`(48 行，降伏法控制)、`liangyi_check`、`killer`(重复)

### 1.5 死亡与轮回区域（d/death/，12 个 .c + 3 个 NPC，580 行）

| 文件 | 行数 | 职责 |
|---|---|---|
| `d/death/gate.c` | 57 | **鬼门关**（`DEATH_ROOM` 入口，include/login.h:23）。`init()` 销毁玩家所有非 character 物品 + `clear_condition()` + 屏蔽 suicide；唯一出口 north → gateway；守卫 wgargoyle |
| `d/death/gateway.c` | 50 | **酆都城门**。`valid_leave()` 禁止向南回头；守卫 bgargoyle |
| `d/death/road1.c` | 42 | **鬼门大道**十字路口，连接 gateway/road2/inn1/inn2 |
| `d/death/road2.c` | 61 | **鬼门大道**。`valid_leave()`：向北需 `temp/long_road` 累加到 5 才放行，否则 `notify_fail` 制造循环错觉 |
| `d/death/road3.c` | 38 | **路的尽头**。死胡同，仅 south 回 road2（注释坦承"还没想到"） |
| `d/death/inn1.c` | 83 | **小店**。**轮回出口谜题**：`redirect_ask` 解析 "ask <self> about 回家"，触发 `do_stuff` → `ob->reincarnate()` + `ob->move("/d/city/wumiao")` (inn1.c:67-83) |
| `d/death/inn2.c` | 52 | **黑店**。死胡同 + 墙面文案提示"靠自己" |
| `d/death/noteroom.c` | 41 | **犯罪记录室**。巫师专用，普通玩家进入即被踢回 `/d/death/death` |
| `d/death/blkbot.c` | 56 | **空房间**。罪犯隔离：屏蔽 practice/lian/dazuo/exercise/tuna/du/study/sleep/respirate/xuelian/lianneili/lianqi/quit 等所有成长指令 |
| `d/death/block.c` | 31 | **死刑室**。`block_cmd` 仅允许 quit/suicide/goto |
| `d/death/death.c` | 37 | **死刑室**（block.c 的变体，注释同源 mantian may/2001） |
| `d/death/hell.c` | 32 | **第十八层地狱**。`block_cmd` 仅允许 say/tell/reply/who/look/quit/suicide/goto |
| `d/death/npc/` | (3 文件) | `bgargoyle.c`/`wgargoyle.c`/`wgargoyle1.c` 鬼门关守卫 |

### 1.6 武功/技能层（kungfu/skill/ 359 条目）

- **顶级 .c 文件**：~144 个（武功招式定义 + 基类封装）
- **子目录**：每个武功可有同名子目录存放 `perform_action` 分文件，共 215 个子目录文件
- **基类封装**（`inherit/skill/`，4 文件）：
  - `inherit/skill/skill.c`（183 行）— 标准技能 daemon 骨架：`valid_learn`/`valid_effect`/`type`/`skill_improved`/`exert_function`/`perform_action`/`cast_spell`/`conjure_magic`/`scribe_spell` 分发、默认 `hit_ob`（武器涂毒 → `apply_condition("snake_poison", ...)`，skill.c:142-157）、`sum`/`NewRandom`（少林武功专用随机函数）
  - `inherit/skill/skill2.c`（179 行）— skill.c 变体：`perform_action` 成功后追加 `me->apply_condition("perform", 5)` (skill2.c:99)，`hit_ob` 涂毒时附带 `victim->kill_ob(me)` (skill2.c:152)
  - `inherit/skill/force.c`（61 行）— 内功基类：`hit_ob` 计算内力加成与反震伤害（force.c:7-55），含 `beiming-shengong` 吸星判定 (force.c:11-26)
  - `inherit/skill/temp.c`（20 行）— 临时占位 skill
- **代表性武功结构（`kungfu/skill/18-zhang.c`，321 行）**：
  - `mapping *action` 数组（18 条）：每条含 `action`（文案）、`dodge`/`parry`/`force`/`damage` 数值修正、`lvl` 解锁等级、`skill_name`、`damage_type`（瘀伤/劈伤/内伤…）、可选 `weapon`、`post_action`（如 `(: sanhui :)`）(18-zhang.c:52-218)
  - `query_action(me, weapon)` (18-zhang.c:241-291) 按当前 force/sanhui/技能等级返回不同动作 mapping，含三连击 `sanhui` 触发分支
  - `query_parry_msg` (18-zhang.c:18-38) 反击分支：满足条件时直接调 `COMBAT_D->do_attack(victim, me, ...)` 触发神龙摆尾反击
  - `valid_enable`/`valid_learn`/`practice_skill`/`perform_action_file` 标准接口
- **数值规模**：18-zhang 单个 mapping `force: 480~650+random(150)`, `damage: 25~120+random(50)`, `lvl: 5~90` —— 反映技能数值跨 18 级翻 5~10 倍以上的曲线
- **门派武功集**（`kungfu/class/`，19 个目录，254 个 .c 文件）：baituo/dali/emei/gaibang/gumu/huashan/lingjiu/mingjiao/murong/quanzhen/shaolin/shenlong/taohua/wudang/xingxiu/xixia/xuedao/xueshan/misc。每个目录含 NPC 定义 + `auto_perform.h` 共享文件，例如 `kungfu/class/shaolin/auto_perform.h` 定义 NPC 自动 pfm 调度（按 `weapon->query("skill_type")` 分派 `perform_action("whip.chanrao")`/`"club.zuida"`/`"sword.sanjue"`/`"cuff.jingang"` 等，auto_perform.h:1-78）

### 1.7 装备层

**inherit/weapon/**（29 文件，15 类武器）：

- **基础类**（14 个 `*.c`，定义 `init_<type>(damage, flag)` + `weapon_prop/damage` + `skill_type` + `verbs` + 委托 `actions` 到 `WEAPON_D`）：`axe`/`blade`/`bow`/`club`/`dagger`/`fork`/`halberd`/`hammer`/`hook`/`pike`/`staff`/`stick`/`sword`/`throwing`/`whip`
- **AS_FEATURE 桩**（15 个 `_*.c`，每个仅 `#define AS_FEATURE` + `#include "<type>.c"`，供 feature/ 层 inherit 而不重复继承 EQUIP）
- **特殊 hit_ob**：
  - `inherit/weapon/sword.c:hit_ob`（67 行）— 击中敌方 cloth 时按概率磨损 `armor_prop/armor` 累计扣减，分阶段改 long 文案与价值（剑/刀类武器护甲磨损系统）
  - `inherit/weapon/throwing.c`（15 行）— inherit `COMBINED_ITEM` + `F_EQUIP`，可堆叠暗器
- **flag 宏**（`include/weapon.h`）：`TWO_HANDED=1`/`SECONDARY=2`/`EDGED=4`/`POINTED=8`/`LONG=16`/`SELF_ACTION=32`，决定双手占用、副手、利刃、穿刺、长兵、自定动作等

**inherit/armor/**（11 文件，对应 11 个槽位类型）：

- `armor`/`boots`/`cloth`/`finger`/`hands`/`head`/`neck`/`shield`/`surcoat`/`waist`/`wrists`
- 通用：`armor_type` + `armor_prop` mapping，重量 >3000 时自动扣 `armor_prop/dodge`（重甲降闪避）
- **特殊 `cloth.c`**（67 行）：`do_tear` 撕布做绷带（do_tear:23-42）；`is_special()` + `hit_by()` 让涂毒衣服反伤近战攻击者并传染 `xx_poison` (cloth.c:46-67)
- **armor_type 常量**：通过 `include/armor.h` 的 `TYPE_ARMOR`/`TYPE_CLOTH` 等定义

### 1.8 战斗命令（cmds/std/，9 个文件 631 行）

| 文件 | 行数 | 职责 |
|---|---|---|
| `cmds/std/kill.c` | 109 | `kill <target>` 主动开战。校验 `no_fight`/`rided`/`surrender`/`xiakedao`/`pker` 限制；`me->kill_ob(obj)`；NPC 调 `accept_kill` + 反 `kill_ob`；玩家则 `fight_ob` + 设 `pking/<id>` 临时标记 + 提示对方也下 kill (kill.c:69-85) |
| `cmds/std/fight.c` | 83 | `fight <target>` 切磋。点到为止，玩家需双向同意（pending/fight），NPC 调 `accept_fight` 决定，"can_speak"NPC 否则直接 fight_ob (fight.c:32-62) |
| `cmds/std/hit.c` | 112 | `hit <target>` 偷袭。玩家对玩家单次 `COMBAT_D->do_attack` 双向一招（hit.c:88-98），含 combat_exp 差距限制 |
| `cmds/std/forcekill.c` | 45 | `forcekill <victim> with <npc>` 命令 NPC 代杀。需 NPC 处于 `xs_necromancy` 降伏状态且施法者在场 (forcekill.c:29-44) |
| `cmds/std/wield.c` | 64 | `wield <obj>` 装备武器，委托 `ob->wield()`（equip.c），支持 `wield all` |
| `cmds/std/unwield.c` | 47 | `unwield <obj>` 卸武器，委托 `ob->unequip()`；若卸剑且 dodge 映射为 dugu-jiujian 则自动 `map_skill("dodge")` 解除 (unwield.c:27-29) |
| `cmds/std/wear.c` | 81 | `wear <obj>` 穿护具，含 `female_only` 性别限制 |
| `cmds/std/remove.c` | 69 | `remove all\|<obj>` 脱护具，含 `bandage` 类型文案 |
| `cmds/std/eat.c` | 21 | `eat <obj>` 吃食物，委托 `ob->feed_ob(me)` |

> 旁路命令（与本簇相关但非 brief 必查）：`cmds/std/halt.c`（中止战斗）、`cmds/std/follow.c`/`lead.c`/`ride.c`/`unride.c`（跟战/骑乘）、`cmds/std/jingzuo.c`（静坐恢复）、`cmds/std/train.c`（驯兽）、`cmds/std/throw.c`（投掷暗器）、`cmds/std/steal.c`（偷窃引发战斗）。

### 1.9 关键头文件（include/）

- `include/combat.h`：`TYPE_REGULAR=0`/`TYPE_RIPOSTE=1`/`TYPE_QUICK=2`、`RESULT_DODGE=-1`/`RESULT_PARRY=-2`、`SKILL_USAGE_ATTACK=1`/`SKILL_USAGE_DEFENSE=2`
- `include/condition.h`：`CND_CONTINUE=1`（延续）、`CND_NO_HEAL_UP=2`（抑制恢复）
- `include/weapon.h`：6 个 flag 位 + 14 个武器路径宏 + `F_*` AS_FEATURE 别名 + `WEAPON_USAGE_ATTACK/PARRY`
- `include/globals.h:45-70`：`CHAR_D=/adm/daemons/chard`、`COMBAT_D=/adm/daemons/combatd`、`CONDITION_D(x)=/kungfu/condition/x`、`SKILL_D(x)=/kungfu/skill/x`
- `include/login.h:23`：`DEATH_ROOM="/d/death/gate.c"`
- `feature/attack.c:13`：`S_COMBAT_D="/adm/daemons/s_combatd"`（局部宏，仅 special_attack 用）

---

## 2. 调用链与数据结构

### 2.1 战斗主循环：heart_beat → attack → fight → do_attack

```
inherit/char/char.c:heart_beat() [char.c:60-169]
  ├─ userp: clear_cmd_count; 频道限流 (>10 msg 自动 chblk_on) [char.c:70-81]
  ├─ 钳制 neili/jingli/jing 不超过 max*2 [char.c:84-97]
  ├─ if eff_qi<0 || eff_jing<0: remove_all_enemy(); die(); return [char.c:100-104]
  ├─ if qi<0 || jing<0 || jingli<0:
  │     remove_all_enemy();
  │     if living(): unconcious();          // 首次昏迷
  │     elif disable_type == " <昏迷不醒>": die();   // 已昏迷再扣则死
  │     return [char.c:108-115]
  ├─ if is_busy(): continue_action(); return [char.c:118-121]
  ├─ if is_fighting() && wimpy_ratio 触发: GO_CMD->do_flee [char.c:124-130]
  ├─ attack();                              // 主入口 [char.c:132]
  ├─ NPC: this_object()->chat();            // 含自动 exert/perform [char.c:135-139]
  ├─ tick-- (5+random(10) 周期): cnd_flag = update_condition()
  │     if (CND_NO_HEAL_UP | !heal_up) && !is_fighting && !interactive: set_heart_beat(0) [char.c:141-158]
  └─ 玩家: update_age; idle 踢出 [char.c:160-168]
```

```
feature/attack.c:attack() [attack.c:208-224]
  ├─ clean_up_enemy()                       // 清失效/不在同房/非 killing 的昏迷目标
  ├─ opponent = select_opponent()           // random(MAX_OPPONENT=4) 范围内随机
  ├─ if yield: return 1                     // 不还手 temp 标志
  ├─ if !special_attack(opponent):           // Anubis 双手互博分支
  │     COMBAT_D->fight(this_object(), opponent);
  └─ return 1
```

```
adm/daemons/combatd.c:fight(me, victim) [combatd.c:787-845]
  ├─ if !living(me): return
  ├─ if victim->is_busy() || !living(victim):
  │     me->guarding=0; victim->fight_ob(me); do_attack(TYPE_QUICK);
  │     双武器/双手互博/pixie-jian 额外 do_attack (action_flag=1)
  ├─ elif random(victim.dex*3) < me.str*2 + apply/speed:
  │     me->guarding=0; victim->fight_ob(me); do_attack(TYPE_REGULAR);
  │     同上额外攻击判定
  ├─ elif !me->guarding: me->guarding=1; 显示 guard_msg
  └─ else: return
```

### 2.2 do_attack 七步结算（combatd.c:340-780）

```
(0) 选 attack_skill: weapon.skill_type / prepare 第 1/2 个 / "unarmed"  [combatd.c:367-378]
(1) reset_action() -> query("actions") 取动作 mapping            [combatd.c:382-396]
    action 含: action 文案 / dodge / parry / force / damage / lvl / damage_type / weapon / post_action
(2) limb = victim->query("limbs")[random]; AP = skill_power(me, attack_skill, ATTACK); DP = skill_power(victim, "dodge", DEFENSE) [combatd.c:406-422]
(3) 闪避判定: if random(ap+dp) < dp: 走 dodge_skill->query_dodge_msg; 双方 jingli 扣减; damage = RESULT_DODGE [combatd.c:430-461]
(4) 招架判定: PP = skill_power(victim, "parry", DEFENSE) (持武器者) 或 skill_power(victim, attack_skill, DEFENSE) (空手对空手); if random(ap+pp) < pp: parry_skill->query_parry_msg; damage = RESULT_PARRY [combatd.c:468-511]
(5) 命中结算 [combatd.c:513-672]:
    damage = apply/damage (随机半化) + action.damage/10*(damage/30) + 技能等级系数
    damage_bonus = me.str + force_skill->hit_ob(...jiali) + action.force + martial_skill->hit_ob + weapon.hit_ob 或 me.hit_ob + jiajin
    if TYPE_QUICK: damage /= 2
    defense_factor 循环: while random(defense_factor) > my.combat_exp: damage -= damage/3; defense_factor /= 2
    特殊护甲 hit_by / 特殊 dodge hit_by 修正 damage 或返回 mapping
    victim->receive_damage("qi", damage, me)
    if random(damage) > apply/armor && (is_killing 或随机): victim->receive_wound("qi", damage - apply/armor, me); wounded=1
(6) 文案: result += damage_msg(damage, action.damage_type); replace $l / $w; message_vision [combatd.c:678-732]
(7) 经验/反跳 [combatd.c:744-779]:
    report_status(victim, wounded)
    if !is_killing 双方 && victim.qi*2 <= max_qi: 双向 remove_enemy + winner_msg (非杀人战斗自动停手)
    action.post_action(me, victim, weapon, damage)
    if TYPE_REGULAR && damage<1 && victim.guarding && speed 判定:
       victim.guarding=0; random(dex)<5: do_attack(victim, me, TYPE_QUICK)  // 漏招
       else: do_attack(victim, me, TYPE_RIPOSTE)                            // 反击
```

### 2.3 skill_power 数值公式（combatd.c:288-333）

```
level = query_skill(skill) + apply/attack 或 apply/defense
       (DEFENSE 时若 is_fighting 再乘 (100 + fight/dodge/10) / 100)
jingli_bonus = 50 + jingli/(max_jingli+1)*50   // 上限 150

if level < 1: return combat_exp/20 * (jingli_bonus/10)

power = level^3 / 3                            // 立方曲线
if ATTACK: return (power + combat_exp)/30 * min(str/10 * jingli_bonus/10, 300)
if DEFENSE: return (power + combat_exp)/30 * min(dex/10 * jingli_bonus/10, 300)
```

### 2.4 伤害与死亡链（feature/damage.c）

```
receive_damage(type, damage, who) [damage.c:13-37]
  type ∈ {"jing","qi","jingli"}
  set_temp("last_damage_from", who)
  if living && userp(who): set_temp("last_eff_damage_from", who.id)  // PK 日志源
  set(type, query(type) - damage)  // 不低于 -1
  set_heart_beat(1)

receive_wound(type, damage, who) [damage.c:39-66]
  type ∈ {"jing","qi"}             // 精力不可受 wound
  set_temp("last_damage_from", who); 同上 last_eff_damage_from
  set("eff_"+type, query("eff_"+type) - damage)  // 不低于 -1
  if query(type) > val: set(type, val)            // 当前值不超过 eff 上限
  set_heart_beat(1)

unconcious() [damage.c:105-135]
  if !living: return; if wizardp && env/immortal: return
  defeater = last_damage_from; COMBAT_D->winner_reward(defeater, this)
  if userp(defeater): set_temp("last_fainted_from", defeater.id)
  remove_all_enemy(); interrupt_me(); dismiss_team()
  disable_player(" <昏迷不醒>"); set jing/qi/jingli = 0; block_msg/all = 1
  COMBAT_D->announce(this, "unconcious")
  call_out("revive", random(100-con) + 30)        // 体质越高苏醒越快

revive(quiet) [damage.c:137-150]
  remove_call_out("revive"); 移出容器; enable_player()
  if !quiet: announce("revive"); block_msg/all=0; 显示苏醒文案

die() [damage.c:152-253]
  if environment.no_death && userp: unconcious() fallback; return  // 无死亡房降级
  if !living: revive(1); if wizardp && env/immortal: return
  clear_condition(); delete("poisoner")
  COMBAT_D->announce(this, "dead")
  if userp && !env.no_death: COMBAT_D->death_penalty(this)
  if killer = last_damage_from:
     set_temp("my_killer", killer.id); COMBAT_D->killer_reward(killer, this)
  elif userp: CHANNEL_D 谣言 "莫名其妙地死了"
  日志: PKILL_DATA / PLAYER_DEATH (按 last_eff_damage_from / killer 分类)
  if !env.no_death || !userp: corpse = CHAR_D->make_corpse(this, killer); corpse.move(env)
  remove_all_killer(); all_inventory(env)->remove_killer(this)
  if userp:
     set jing/eff_jing/qi/eff_qi = 1; jingli = 1
     if env.no_death: eff_jing=max_jing; eff_qi=max_qi; return  // 安全区不进地府
     dismiss_team(); save(); ghost = 1; move(DEATH_ROOM); DEATH_ROOM->start_death(this)
     MARRY_D->break_marriage(this)
     if family/master_id == "feng qingyang": CHAR_D->break_relation(this)
  else: destruct(this)

reincarnate() [damage.c:255-264]
  ghost = 0; 恢复 jing/qi/eff_jing/eff_qi/jingli/neili 至 max

heal_up() [damage.c:270-331]
  water/food -1
  if is_fighting: jing += con/9 + max_jingli/30; qi += con/9 + max_neili/30; jingli += (str+dex)/12; neili += force_skill/6
  else:          jing += con/3 + max_jingli/10; qi += con/3 + max_neili/10; jingli += (str+dex)/4;  neili += force_skill/2
  jingli 上限 max*2; eff_* 满后缓慢自然 +1 上限回涨
```

### 2.5 death_penalty / killer_reward（combatd.c:987-1096）

```
death_penalty(victim) [combatd.c:987-1025]:
  if !userp || wizardp: return
  clear_condition()
  if combat_exp >= 10000 * death_times: death_times++
  shen -= shen/20; behavior_exp -= behavior_exp/20
  amount = combat_exp/100 (cap 5000); if >50: combat_exp -= amount; potential -= potential/2
  else if combat_exp > 20: combat_exp -= 20
  balance 超 10000 部分对半; death_count++; delete vendetta/rob_victim/initiator
  if thief: thief /= 2
  skill_death_penalty()  // feature/skill.c:121-147: 每技能 -1 级
  save()

killer_reward(killer, victim) [combatd.c:1027-1096]:
  if !env.no_death:
    killer->killed_enemy(victim)
    if userp(victim):
      killer.PKS++; killer.pktime = mud_age
      if 城内: apply_condition("killer", 100)     // 官府通缉
      mode = 野兽"咬"/家畜"踩"/飞禽"啄"/人"杀"; CHANNEL rumor 播报
    else if 人类 victim: killer.MKS++
    if victim.id == taishan/fengchan.winner: killer.free_rider = 1  // 防蹭盟主奖励
    if killer 比 victim 弱 1/4~1 倍: shen -= victim.shen/10; behavior_exp -= victim.behavior_exp/10
    if 双方 userp 且 pking/<id> temp: apply_condition("pker", pker+120)
    if vendetta_mark: killer.vendetta/<mark>++
```

### 2.6 condition 时效引擎（feature/condition.c）

```
update_condition() [condition.c:21-69]   // 由 char.c:144 每 5+random(10) tick 调用
  if !mapp(conditions) || !sizeof: return 0
  for each cnd in keys(conditions):
    cnd_d = find_object(CONDITION_D(cnd))   // = /kungfu/condition/<cnd>
    if !cnd_d: catch(load); 若仍失败则 log + map_delete
    flag = call_other(cnd_d, "update_condition", me, conditions[cnd])
    if !(flag & CND_CONTINUE): map_delete(conditions, cnd)
    update_flag |= flag
  if empty: conditions = 0
  return update_flag

apply_condition(cnd, info) [condition.c:79-85]
  conditions[cnd] = info                  // 直接覆盖，不查重（giver 负责）

query_condition(cnd) [condition.c:91-95]
  return conditions[cnd]                  // 0 表示无

clear_condition() / clear_all_condition() [condition.c:105-113]
  conditions = 0                          // 死亡时由 die() 调用
```

> 每个 condition daemon 是独立 .c 文件，需实现 `int update_condition(object me, mixed info)`。返回 `0` = 过期移除；返回 `CND_CONTINUE=1` = 延续；位或 `CND_NO_HEAL_UP=2` = 抑制 `heal_up()`（如 `hanbing_damage`/`juehu_damage` 等重伤效果）。info 形态因 daemon 而异（多为 int duration，也可能是 mapping）。daemon 内通常调 `me->apply_condition(self, duration-1)` 推进计时。

### 2.7 地府轮回流程（d/death/）

```
玩家 die() -> ghost=1 -> move("/d/death/gate.c")  [damage.c:247]
                                       ↓
gate.c (鬼门关) init():
  ├─ 销毁 all_inventory 中所有非 character 物品
  ├─ me->clear_condition()
  └─ 出口 north -> gateway
                                       ↓
gateway.c (酆都城门): valid_leave 禁止 south 回头; 出口 north -> road1
                                       ↓
road1.c (鬼门大道十字): north=road2 / south=gateway / west=inn1 / east=inn2
                                       ↓
road2.c (鬼门大道): 北上需 temp/long_road 累加到 5 才放行 (valid_leave road2.c:24-46)
   ↑       ←———————— 死循环错觉 ————————↓
   ↓ (累计 5 次后)
road3.c (路的尽头): 死胡同，仅 south 回 road2
                                       ↓
inn1.c (小店): redirect_ask 解析 "ask <self-id> about 回家"
   ├─ do_stuff(ob):
   │   ├─ ob->reincarnate()          // ghost=0, 恢复 max
   │   └─ ob->move("/d/city/wumiao") // 回到阳间
   └─ 隐藏出口

旁路:
  blkbot.c (空房间) - 罪犯隔离，屏蔽所有成长/quit 指令
  noteroom.c (犯罪记录室) - 巫师专用
  death.c / block.c (死刑室) - 仅 quit/suicide/goto
  hell.c (第十八层地狱) - 仅 say/tell/reply/who/look/quit/suicide/goto

注: DEATH_ROOM->start_death(this) 在 die() 中被调用 (damage.c:248)，但 grep 全仓库无 start_death 函数定义 — LPC call_other 对不存在函数静默返回 0，实际为 no-op。地府流程完全由房间 init/valid_leave 驱动。
```

### 2.8 武功招式调度链

```
玩家/NPC 装备 weapon -> wield() -> owner->reset_action() [feature/equip.c:104]
  reset_action() [feature/attack.c:143-171]:
    根据 weapon.skill_type 或 prepare 选 type
    if skill_map[type] (= mapped_to 武功):
      set("actions", (: call_other, SKILL_D(skill), "query_action", me, ob :))  // 委托给武功
    else if weapon: set("actions", weapon->query("actions"))  // 武器自带
    else: set("actions", query("default_actions"))

do_attack (combatd.c:340):
  action = me->query("actions")   // 即调用 SKILL_D(<mapped>)->query_action(me, weapon)
  -> 18-zhang.c:query_action (18-zhang.c:241-291):
     按当前 sanhui temp / force 技能 / strike 技能 / random 返回 mapping
     mapping 含 action 文案 + dodge/parry/force/damage 修正 + damage_type + 可选 post_action

特殊 hook:
  - SKILL_D(force_skill)->hit_ob(me, victim, damage_bonus, jiali) [combatd.c:541-562]
    如 inherit/skill/force.c:hit_ob 计算内力伤害 + 反震 + beiming-shengong 吸星
  - SKILL_D(martial_skill)->hit_ob(me, victim, damage_bonus) [combatd.c:578-585]
    如 18-zhang 自定义 hit_ob
  - weapon->hit_ob(me, victim, damage_bonus) [combatd.c:588-595]
    如 sword.c:hit_ob 磨损护甲
  - victim armor/cloth->hit_by(me, victim, damage, weapon) [combatd.c:644-656]
    如 cloth.c:hit_by 反伤涂毒
  - SKILL_D(dodge_skill)->hit_by(me, victim, damage) [combatd.c:660-672]
    如 beiming-shengong.c:hit_by 吸星
  - action.post_action(me, victim, weapon, damage) [combatd.c:762-763]
    如 18-zhang 的 sanhui 后处理

NPC 自动战斗:
  inherit/char/npc.c:chat() [npc.c:99-128]:
    自动调 SKILL_D("force")->exert_function recover/regenerate/refresh
    if chat_chance_combat + chat_msg_combat: 随机 evaluate functionp 或 say msg
  门派 NPC: kungfu/class/<sect>/auto_perform.h:auto_perform()
    按 weapon.skill_type 分派 perform_action("whip.chanrao" / "club.zuida" / "sword.sanjue" / "cuff.jingang" ...)
```

### 2.9 装备数值聚合（feature/equip.c）

```
wield() [equip.c:46-107]:
  flag = query("flag")
  if TWO_HANDED: 需空出 weapon/secondary/armor shield 三槽
  else:
    if !old_weapon: weapon = this
    elif !secondary && !shield:
      if SECONDARY: secondary = this
      elif old_weapon SECONDARY: old_weapon.unequip; weapon = this; old_weapon.wield
      else: 失败
    else: 失败
  for k in keys(weapon_prop): owner->add_temp("apply/"+k, weapon_prop[k])  // 聚合 apply/damage, apply/attack 等
  owner->reset_action()

wear() [equip.c:7-44]:
  type = armor_type; 校验未占用同 type 槽
  owner->set_temp("armor/"+type, this)
  for k in keys(armor_prop):
    applied_prop[k] = (applied_prop[k] 或 0) + armor_prop[k]   // 累加
  owner->set_temp("apply", applied_prop)
  set("equipped", "worn")

unequip() [equip.c:109-140]:
  按 equipped=="wielded"|"worn" 回滚 temp/weapon|secondary_weapon|armor/<type>
  apply 对应扣减; owner->reset_action()
```

---

## 3. 关键回调与状态变量

### 3.1 持久化 dbase 字段（会随 save() 落盘）

| 字段 | 类型 | 含义 | 来源 |
|---|---|---|---|
| `jing`/`qi`/`jingli` | int | 当前精/气/精力（受 damage 递减，受 heal 递增） | feature/damage.c:13,39,68 |
| `eff_jing`/`eff_qi` | int | 当前精/气上限（受 wound 递减，受 curing 递增） | damage.c:53,93 |
| `max_jing`/`max_qi`/`max_jingli`/`max_neili` | int | 永久上限 | char.c:84-97 |
| `neili` | int | 内力（force 技能源） | damage.c:320-328 |
| `combat_exp` | int | 战斗经验（命中/伤害修正） | combatd.c:351-354 |
| `behavior_exp` | int | 行为经验（死亡惩罚 -10%） | combatd.c:1000,1078 |
| `potential`/`max_potential` | int | 潜能（死亡时 -50%） | combatd.c:1007-1008 |
| `shen` | int | 善恶值（PK 调整 -10%/-20%） | combatd.c:999,1077 |
| `death_times`/`death_count` | int | 死亡计数（影响 death_penalty 阈值） | combatd.c:997-998,1016 |
| `PKS`/`MKS` | int | 玩家杀/怪杀计数 | combatd.c:1043,1066 |
| `pktime` | int | 上次 PK 时刻（mud_age） | combatd.c:1045, kill.c:14 |
| `balance` | int | 钱庄存款（>10000 部分对半惩罚） | combatd.c:1013-1015 |
| `thief` | int | 偷窃标记（死亡时对半） | combatd.c:1020-1021 |
| `vendetta/<mark>` | int | 世仇计数 | combatd.c:1091-1092 |
| `gender`/`ori_gender` | str | 性别（juehu_damage 可改男性→无性） | kungfu/condition/juehu_damage.c:53-58 |
| `family/master_id` | str | 师傅 ID（风清扬徒弟死亡触发 break_relation） | damage.c:250 |
| `skills`/`learned`/`skill_map`/`skill_prepare` | mapping | 技能体系 | feature/skill.c:9-12 |
| `conditions` | mapping | 状态 Effect 表 | feature/condition.c:8 |
| `startroom` | str | 登录回到房间（地府/牢房会改写） | d/death/death.c:25, city_jail.c:14 |

### 3.2 临时 temp 字段（不落盘，进程内有效）

| temp 字段 | 含义 | 来源 |
|---|---|---|
| `enemy[]`/`killer[]` | 敌对/杀意列表（static 变量，非 temp） | feature/attack.c:15-16 |
| `last_damage_from` | 最后伤害来源对象（死亡判定用） | damage.c:21 |
| `last_eff_damage_from` | 最后有效伤害者 ID（仅玩家对玩家，PK 日志） | damage.c:25-26 |
| `last_fainted_from` | 最后击晕者 ID | damage.c:117 |
| `my_killer` | 致死者 ID（写尸） | damage.c:193, chard.c:141 |
| `last_opponent` | 上一回合对手 | attack.c:216 |
| `weapon`/`secondary_weapon` | 主/副手武器槽 | equip.c:66,74,82 |
| `armor/<type>` | 各槽位护具（armor/cloth/boots/head/...） | equip.c:29,128 |
| `apply/<stat>` | 装备聚合修饰（apply/damage, apply/attack, apply/defense, apply/armor, apply/speed, apply/dodge...） | equip.c:34-41,100-102 |
| `apply/astral_vision` | 阴眼（可见鬼魂） | char.c:183 |
| `apply/armor_vs_force` | 抗内力护甲 | inherit/skill/force.c:51 |
| `fight/dodge` | 当前动作 dodge 修正（DEFENSE 时生效） | combatd.c:415, skill_power:304 |
| `action_flag` | 双手/二段攻击切换（0 主 / 1 副） | attack.c:156, combatd.c:811 |
| `yield` | 不还手标志 | attack.c:217 |
| `guarding` | 防御态势（蓄势） | combatd.c:801,820,839 |
| `looking_for_trouble` | auto_fight call_out 锁（防重入） | combatd.c:861-863 |
| `pking/<id>` | 玩家主动 PK 标记（影响 pker condition 累加） | kill.c:79, combatd.c:1088 |
| `initiate_pk` | PK 发起者 ID 数组 | fight.c:79, hit.c:79 |
| `initiator` | 战斗发起者 | kill.c:80, combatd.c:1019 |
| `free_rider` | 摘桃标记（杀盟主时不给奖励） | combatd.c:1074,1081,1084, kill.c:67 |
| `block_msg/all` | 屏蔽所有消息（昏迷/盲时） | damage.c:131,149 |
| `medication` | bandaged 治疗 stack | kungfu/condition/bandaged.c:14 |
| `sanhui`/`sanxiao` | 18-zhang 三连击状态 | 18-zhang.c:255-264, d/death/gate.c:40 |
| `long_road` | 地府 road2 循环计数 | d/death/road2.c:28-37 |
| `stand/anubis` | Anubis 双手互博特殊战斗标志 | attack.c:200, s_combatd.c:346 |
| `cimu_power`/`pixie/cimu` | 辟邪剑法刺目效果量 | kungfu/condition/blind.c:28-33 |
| `wudong/juehu_damage` | 武当绝户爪已应用 apply 削减标记 | kungfu/condition/juehu_damage.c:38-42 |
| `armor/embed` | 嵌入暗器对象 | kungfu/condition/embedded.c:16 |
| `action_flag`/`fight/dodge` | 见上 | combatd.c |

### 3.3 关键回调函数（feature/inherit 钩子契约）

| 回调 | 调用方 | 作用 |
|---|---|---|
| `heart_beat()` | driver 周期触发 | 战斗循环主驱动 (char.c:60) |
| `attack()` | heart_beat | 选敌并委托 COMBAT_D->fight (attack.c:208) |
| `reset_action()` | wield/wear/unequip/map_skill | 重新计算 `actions` mapping (attack.c:143) |
| `chat()` | heart_beat (NPC) | 自动 exert/perform + 战斗消息 (npc.c:99) |
| `auto_perform()` | 门派 NPC chat_combat | 自动 pfm 调度 (class/<sect>/auto_perform.h) |
| `accept_fight(who)` | fight.c | NPC 决定是否接受切磋 (npc.c:30) |
| `accept_kill(who)` | kill.c | NPC 决定是否反击 (npc.c:69) |
| `killed_enemy(victim)` | killer_reward | 杀手侧回调 (combatd.c:1039) |
| `defeated_enemy(victim)` | winner_reward | 击晕方回调 (combatd.c:984) |
| `die()`/`unconcious()`/`revive()`/`reincarnate()` | heart_beat/Combatd | 死亡链 (damage.c) |
| `clear_condition()` | die/death_penalty/gate.c | 清空 Effect (condition.c:105) |
| `interrupt_me(who)` | combatd/unconcious | 中断 dazuo/jingzuo 等长动作 (damage.c:122, combatd.c:748) |
| `dismiss_team()` | unconcious/die | 退队 (team.c:103) |
| `save()` | die/death_penalty | 落盘 (damage.c:245, combatd.c:1023) |
| `SKILL_D(x)->query_action(me, weapon)` | reset_action | 返回动作 mapping |
| `SKILL_D(x)->hit_ob(me, victim, damage_bonus, factor)` | do_attack(5) | 内功/武功附加伤害 |
| `SKILL_D(x)->hit_by(me, victim, damage, ...)` | do_attack(5) | 防御方武功改写伤害 |
| `SKILL_D(x)->query_dodge_msg(limb)` / `query_parry_msg(weapon, victim)` | do_attack(3)(4) | 闪避/招架文案 |
| `SKILL_D(x)->perform_action(me, arg)` / `exert_function(me, arg)` | 命令/chat | 主动 pfm/exert 内功 |
| `weapon->hit_ob(me, victim, damage_bonus)` | do_attack(5) | 武器附加效果（如涂毒、磨损） |
| `armor->hit_by(me, victim, damage, weapon)` | do_attack(5) | 护具改写伤害（如毒衣反伤） |
| `action["post_action"](me, victim, weapon, damage)` | do_attack(7) | 动作后置 hook |
| `CONDITION_D(x)->update_condition(me, info)` | update_condition | Effect tick |
| `CHAR_D->make_corpse(victim, killer)` | die | 生成尸体 + 物品转移 (chard.c:116) |
| `CHAR_D->setup_char(ob)` | char.c:setup | 按 race 初始化属性 (chard.c:22) |

---

## 4. 关键文件清单表（汇总，便于后续角色引用）

### 4.1 战斗核心（命中→伤害）

| 路径 | 行 | 关键函数/对象 |
|---|---|---|
| feature/attack.c | 258 | enemy[], killer[], MAX_OPPONENT=4, fight_ob, kill_ob, is_fighting, is_killing, select_opponent, attack, special_attack, reset_action, init |
| feature/damage.c | 331 | ghost, receive_damage, receive_wound, receive_heal, receive_curing, unconcious, revive, die, reincarnate, heal_up, max_food_capacity, max_water_capacity |
| feature/condition.c | 113 | conditions, update_condition, apply_condition, query_condition, clear_one_condition, clear_condition, clear_all_condition, query_all_condition |
| feature/skill.c | 183 | skills, learned, skill_map, skill_prepare, set_skill, delete_skill, map_skill, prepare_skill, query_skill_mapped, query_skill_prepared, query_skill, skill_death_penalty, improve_skill |
| feature/team.c | 127 | leader, lord, team, set_leader, set_lord, follow_path, follow_me, add_team_member, join_team, is_team_leader, have_team_member, set_team, dismiss_team, query_team |
| feature/equip.c | 140 | wear, wield, unequip |
| inherit/char/char.c | 187 | heart_beat, setup, visible, is_character, create |
| inherit/char/trainee.c | 232 | do_gen, do_yao, do_ting, do_fang, do_stop, train_it, biting, is_trainee |
| inherit/char/npc.c | 186 | carry_object, add_money, accept_fight, accept_kill, return_home, chat, random_move, cast_spell, exert_function, perform_action |
| adm/daemons/combatd.c | 1098 | damage_msg, eff_status_msg, status_msg, report_status, skill_power, do_attack, fight, auto_fight, start_berserk, start_hatred, start_vendetta, start_aggressive, announce, winner_reward, death_penalty, killer_reward |
| adm/daemons/s_combatd.c | 974 | (与 combatd.c 同名函数集) + anubis_attack |
| adm/daemons/chard.c | 192 | setup_char, make_corpse, break_relation |

### 4.2 状态/Effect 内容层（72 个 condition daemon，节选代表性 17 个）

| 路径 | 行 | 类型 | 关键行为 |
|---|---|---|---|
| kungfu/condition/aphroclisiac.c | 48 | 春药 | 每次随机攻击房内活物，duration-1 |
| kungfu/condition/bt_poison.c | 42 | 毒(西域灵蛇) | receive_wound jing + receive_damage jingli，按 poison 技能缩短 duration |
| kungfu/condition/hanbing_damage.c | 31 | 伤害(寒冰绵掌) | receive_damage qi + receive_wound jing |
| kungfu/condition/juehu_damage.c | 62 | 伤害(绝户爪) | apply/attack+apply/defense 持续 -duration → 每tick +1 还原；男性→无性 |
| kungfu/condition/jiujian_qi_damage.c | - | 伤害(九剑气) | (代表，未细读) |
| kungfu/condition/hyz_damage.c | - | 伤害 | (代表，未细读) |
| kungfu/condition/yyz_damage.c | 59 | 伤害(玉阳针) | (代表，未细读) |
| kungfu/condition/embedded.c | 37 | 嵌入暗器 | 每 tick receive_wound qi=3；NPC 战斗外自动拔除 |
| kungfu/condition/bandaged.c | 42 | 治疗 | 按 temp/medication/vulnerary 治 eff_qi |
| kungfu/condition/drunk.c | 35 | 醉 | 过量直接 unconcious；轻度时 receive_healing |
| kungfu/condition/blind.c | 36 | 盲 | 扣 apply/attack+apply/defense，结束时 let_know 还原 |
| kungfu/condition/city_jail.c | 24 | 牢 | 到时 move 到 /d/city/yamen 并设 startroom |
| kungfu/condition/dali_jail.c | - | 牢 | (同上模式) |
| kungfu/condition/bonze_jail.c | - | 牢 | (同上模式) |
| kungfu/condition/killer.c | 14 | 官府通缉 | 倒计时，到时通知 |
| kungfu/condition/pker.c | 11 | PK 杀气 | 累加 120 秒 |
| kungfu/condition/perform.c | 11 | pfm 锁 | 仅 is_fighting 时持续，战斗结束自动消失 |

### 4.3 死亡与轮回（12 个区域文件 + 3 NPC）

| 路径 | 行 | 关键对象/函数 |
|---|---|---|
| d/death/gate.c | 57 | init (销毁物品 + clear_condition + 屏蔽 suicide), do_suicide |
| d/death/gateway.c | 50 | valid_leave (禁止回头), do_suicide |
| d/death/road1.c | 42 | exits 十字 |
| d/death/road2.c | 61 | valid_leave (long_road 计数谜题) |
| d/death/road3.c | 38 | 死胡同 |
| d/death/inn1.c | 83 | redirect_ask, do_stuff (reincarnate + move 回阳间) |
| d/death/inn2.c | 52 | item_desc 墙面提示 |
| d/death/noteroom.c | 41 | init (踢回普通玩家) |
| d/death/blkbot.c | 56 | do_practice (屏蔽成长指令) |
| d/death/block.c | 31 | block_cmd |
| d/death/death.c | 37 | block_cmd |
| d/death/hell.c | 32 | block_cmd |
| d/death/npc/bgargoyle.c, wgargoyle.c, wgargoyle1.c | - | 守卫 NPC |

### 4.4 武功/技能（基类 + 代表性武功，节选）

| 路径 | 行 | 关键函数/对象 |
|---|---|---|
| inherit/skill/skill.c | 183 | valid_learn, valid_effect, type, skill_improved, exert_function, perform_action, cast_spell, conjure_magic, scribe_spell, hit_ob (默认涂毒), sum, NewRandom |
| inherit/skill/skill2.c | 179 | 同上变体；perform_action 成功后 apply_condition("perform", 5)；hit_ob 涂毒附带 kill_ob |
| inherit/skill/force.c | 61 | hit_ob (内力加成/反震/beiming 吸星), hit_by |
| inherit/skill/temp.c | 20 | 占位 |
| kungfu/skill/dodge.c | 17 | dodge_msg, query_dodge_msg |
| kungfu/skill/parry.c | 24 | (未读，基类招架) |
| kungfu/skill/unarmed.c | 7 | (极小，基类) |
| kungfu/skill/blade.c, sword.c, axe.c, ... | 4~ | 各兵器基类（多数仅 inherit SKILL） |
| kungfu/skill/18-zhang.c | 321 | action[18], query_action, query_parry_msg (神龙摆尾反击), valid_enable, valid_learn, practice_skill, perform_action_file, sanhui |
| kungfu/skill/6mai-shenjian.c | 106 | (六脉神剑) |
| kungfu/skill/beiming-shengong.c | 49 | valid_enable, valid_learn, exert_function_file, hit_by (吸星) |
| kungfu/skill/archery.c | - | (射箭) |
| kungfu/class/<sect>/auto_perform.h | ~78 | auto_perform (按 weapon skill_type 分派 pfm) |

### 4.5 装备（武器 15 类 + 护具 11 类）

武器基础类（inherit/weapon/）：

| 路径 | 行 | init_<type> | flag 默认 | verbs |
|---|---|---|---|---|
| sword.c | 67 | init_sword | EDGED | slash, slice, thrust |
| axe.c | 23 | init_axe | EDGED | chop, slice, hack |
| blade.c | (同模式) | init_blade | EDGED | (类同) |
| bow.c, club.c, dagger.c, fork.c, halberd.c, hammer.c, hook.c, pike.c, staff.c, stick.c, whip.c | (各 10~25) | init_<type> | 各异 | 各异 |
| throwing.c | 15 | init_throwing | - | throw |
| _sword.c ~ _whip.c (15 个 AS_FEATURE 桩) | 2~3 | #include 主类 | - | - |

护具（inherit/armor/）：

| 路径 | 行 | armor_type | 特殊 |
|---|---|---|---|
| armor.c | 16 | TYPE_ARMOR | 重甲降 dodge |
| boots.c, finger.c, hands.c, head.c, neck.c, shield.c, surcoat.c, waist.c, wrists.c | (各 10~20) | TYPE_<X> | (基类) |
| cloth.c | 67 | TYPE_CLOTH | do_tear 撕布做绷带；is_special+hit_by 涂毒反伤 |

### 4.6 战斗命令

| 路径 | 行 | 命令 | 关键行为 |
|---|---|---|---|
| cmds/std/kill.c | 109 | kill <target> | 主动开战，校验多限制，kill_ob + NPC accept_kill + 玩家 pking temp |
| cmds/std/fight.c | 83 | fight <target> | 切磋需双向同意，NPC accept_fight |
| cmds/std/hit.c | 112 | hit <target> | 偷袭，单次 COMBAT_D->do_attack 双向一招 |
| cmds/std/forcekill.c | 45 | forcekill <victim> with <npc> | 需 xs_necromancy 降伏 |
| cmds/std/wield.c | 64 | wield <obj/all> | 委托 ob->wield() |
| cmds/std/unwield.c | 47 | unwield <obj> | 委托 ob->unequip()；dugu-jiujian 联动 |
| cmds/std/wear.c | 81 | wear <obj> | 委托 ob->wear()；female_only |
| cmds/std/remove.c | 69 | remove all/<obj> | 委托 ob->unequip() |
| cmds/std/eat.c | 21 | eat <obj> | 委托 ob->feed_ob(me) |

### 4.7 头文件

| 路径 | 关键定义 |
|---|---|
| include/combat.h | TYPE_REGULAR/RIPOSTE/QUICK, RESULT_DODGE/PARRY, SKILL_USAGE_ATTACK/DEFENSE |
| include/condition.h | CND_CONTINUE=1, CND_NO_HEAL_UP=2 |
| include/weapon.h | TWO_HANDED/SECONDARY/EDGED/POINTED/LONG/SELF_ACTION, 14 武器宏, F_* AS_FEATURE, WEAPON_USAGE_* |
| include/armor.h | TYPE_ARMOR/CLOTH/... (本调研未深读) |
| include/globals.h:45-70 | CHAR_D, COMBAT_D, CONDITION_D(x), SKILL_D(x) |
| include/login.h:23 | DEATH_ROOM = "/d/death/gate.c" |
| include/skill.h | query_skill_mapped, map_skill, query_skill, improve_skill, query_skill_prepare 原型 |

---

## 5. 待深入文件清单（推荐后续细读）

> 优先级 P0 = 与耦合链「命中→伤害→Effect→死亡→复活」直接相关的核心；P1 = 机制代表性或规模巨大；P2 = 内容层抽样。

### 5.1 P0（机制核心，建议各角色必读）

1. **`feature/damage.c`**（331 行）— 三类伤害 + die/reincarnate/ghost 的全部实现。死亡链唯一真相源。
2. **`adm/daemons/combatd.c`**（1098 行）— `do_attack` 七步结算 + `skill_power` 立方公式 + `death_penalty`/`killer_reward`。数值与平衡专家必读。
3. **`feature/condition.c`** + **`kungfu/condition/aphroclisiac.c`/`bt_poison.c`/`hanbing_damage.c`/`juehu_damage.c`/`embedded.c`/`bandaged.c`/`blind.c`/`drunk.c`** — Effect 引擎分发 + 7 类代表性 daemon（控制/毒/伤害/嵌入/治疗/盲/醉）。
4. **`inherit/char/char.c:heart_beat`**（char.c:60-169）— 战斗/Effect/死亡三系统的统一调度入口。
5. **`d/death/inn1.c` + `gate.c` + `road2.c`**（共 ~200 行）— 地府轮回的入出口与谜题机制。
6. **`feature/attack.c`**（258 行）— 敌对列表与 attack() 主入口，含 MAX_OPPONENT=4 上限。
7. **`inherit/skill/skill.c` + `force.c`**（共 244 行）— 武功 hook 契约（hit_ob/hit_by/exert_function/perform_action）。

### 5.2 P1（机制代表性或大规模）

8. **`adm/daemons/s_combatd.c`**（974 行）— 与 combatd.c 对照，理解 prototype 双手互博/Anubis 分支。可只读 `anubis_attack` (s_combatd.c:247-287) 与 `skill_power` 公式差异。
9. **`adm/daemons/chard.c`**（192 行）— `make_corpse` 物品转移逻辑 + `setup_char` race 属性初始化。
10. **`feature/equip.c`**（140 行）— 装备数值聚合（apply/* 累加）+ 双手/副手武器槽管理。
11. **`kungfu/skill/18-zhang.c`**（321 行）— 最复杂的武功之一：18 个 action mapping + `query_action` 多分支（sanhui 三连击 + force 加成）+ `query_parry_msg` 反击。武功招式调度代表性文件。
12. **`kungfu/skill/beiming-shengong.c` + `inherit/skill/force.c`** — 内功 hit_by 吸星机制。
13. **`inherit/weapon/sword.c` + `inherit/armor/cloth.c`**（共 134 行）— 武器磨损护甲 + 毒衣反伤，代表装备层 hit_ob/hit_by 钩子。
14. **`inherit/char/npc.c`**（186 行）— NPC 自动战斗 `chat` 调度 + `exert_function`/`perform_action` 委托。
15. **`kungfu/class/shaolin/auto_perform.h`**（~78 行）— 门派 NPC 自动 pfm 分派逻辑，可作为 NPC AI 抽象参考。

### 5.3 P2（内容层抽样，按需查阅）

16. **`kungfu/condition/zf_poison.c`**（100 行）— 最复杂的 poison daemon，可作毒系 Effect 细节参考。
17. **`kungfu/condition/xs_necromancy.c`**（48 行）— 降伏法控制（与 forcekill.c 联动）。
18. **`kungfu/condition/juehu_damage.c`**（62 行）— 性别改造 + apply 削减 + 缓慢还原，最复杂的伤害型 Effect。
19. **`d/death/blkbot.c` + `noteroom.c` + `hell.c`** — 罪犯隔离与死刑室机制。
20. **`feature/damage_backup.c`**（312 行）+ **`feature/attback.c`**（218 行）— 历史备份，对照旧版战斗/伤害实现演化（如 `last_eff_damage_from`/PKILL 日志是后加的）。
21. **`cmds/std/kill.c` + `fight.c` + `hit.c`**（共 304 行）— 三种开战方式的差异（kill 真打 / fight 切磋 / hit 偷袭），含 pker 限制、combat_exp 差距限制等社会规则。
22. **`kungfu/skill/dodge.c` + `parry.c`**（共 41 行）— 闪避/招架文案基类。
23. **`include/combat.h` + `condition.h` + `weapon.h` + `globals.h`** — 常量与宏定义全貌。
24. **`kungfu/skill/<其他武功>.c`** — 按调研需要抽样，如 `6mai-shenjian.c`/`dugu-jiujian/`/`pixie-jian*`/`dagou-bang/` 等含特殊机制的武功。
25. **`kungfu/class/<其他门派>/auto_perform.h`** — 抽样对照门派 NPC 自动战斗差异。

---

## 6. 总体观察（仅事实陈述，不含 engine 对照评判）

> engine 对照与设计建议由后续角色（机制抽象组 / engine 批判对照员 / 评审委员会）输出。本节仅列出考古层面观察到的事实。

1. **耦合链一致性**：feature/attack.c（敌对管理）→ adm/daemons/combatd.c（命中/伤害结算）→ feature/damage.c（数值扣减 + die/unconcious）→ feature/condition.c（Effect 时效引擎）→ d/death/（地府轮回）形成完整闭环，由 inherit/char/char.c:heart_beat 统一驱动。任一环节均有明确的函数调用证据，无猜测。

2. **两套 combatd 并存**：`combatd.c`（主用，由 `COMBAT_D` 宏指向）与 `s_combatd.c`（原型，由 `S_COMBAT_D` 局部宏指向，仅 `attack.c:special_attack` 在 `stand/anubis` temp 下调用）。两者 90%+ 代码重复，`s_combatd.c` 注释明确称"prototype"，尚未合并入主线（s_combatd.c:4-12）。

3. **Effect 引擎形态**：LPC condition 是「外部 daemon + mapping 表 + heart_beat tick」三件组。每个 condition 是 `/kungfu/condition/<name>.c` 独立文件，通过 `CONDITION_D(x)` 宏分发（include/globals.h:70）。info 字段（多为 duration int，也有 mapping）由 daemon 自解释。返回值位或 `CND_CONTINUE`/`CND_NO_HEAL_UP` 控制延续与恢复抑制（include/condition.h）。death 与 unconcious 时 `clear_condition()` 一刀切（damage.c:184, combatd.c:995, gate.c:38）。

4. **三类伤害体系**：`jing`/`qi`/`jingli` 三种当前值 + `eff_jing`/`eff_qi` 两种上限值（精力无 eff）。`receive_damage` 扣当前值，`receive_wound` 扣上限值（且当前值不能超过新上限），`receive_heal`/`receive_curing` 分别恢复当前值与上限值。`heal_up` 在战斗 vs 和平状态下恢复速率差 3 倍（damage.c:288-328）。

5. **两段式死亡**：`unconcious()`（昏迷，`call_out revive 30+random(100-con)`）→ 若昏迷中再扣至负则 `die()`。`die()` 在 `no_death` 房间降级为 `unconcious()`（damage.c:159-177）。玩家死亡 = `ghost=1` + move 到 `/d/death/gate.c` + 货币/经验/技能惩罚 + 物品落尸。`reincarnate()` 仅重置数值与 ghost 标志，由地府谜题房间 `inn1.c:do_stuff` 触发。

6. **MAX_OPPONENT=4 与多目标**：`select_opponent` 在 `random(MAX_OPPONENT)` 范围内选敌，超出 4 个时仅随机前 4 个（attack.c:85-88）。`fight_ob` 不限制 enemy 数量，但每 tick 只攻击 1 个。

7. **武功三层 hook**：`SKILL_D(force_skill)->hit_ob`（内功）、`SKILL_D(martial_skill)->hit_ob`（武功本身）、`weapon->hit_ob`（武器）在 do_attack 第 5 步串行调用，可返回 string（文案）/ int（伤害加成）/ mapping（result + damage）。防御侧对称有 `armor->hit_by` 与 `dodge_skill->hit_by`。

8. **数值规模非线性**：`skill_power` 用 `level^3/3` 立方曲线（combatd.c:317, s_combatd.c:237），叠加 `combat_exp` 与 `str`/`dex`/`jingli_bonus`，形成高技能等级爆炸式压制。18-zhang 单招 `force` 从 330 到 650+random(150)，`damage` 从 20 到 120+random(50)，跨度大。

9. **死亡惩罚分层**：`death_penalty`（victim 侧）扣 combat_exp 1% 上限 5000、potential 减半、balance 超 1w 部分对半、技能 -1 级；`killer_reward`（killer 侧）加 PKS、shen 调整、可能 apply_condition("killer"/"pker")。两层分别由 combatd.c:987 与 1027 实现，互不重叠。

10. **PK 与社会规则分散在命令层**：`kill.c`/`fight.c`/`hit.c` 各自校验 `pker` condition、`combat_exp` 差距、`xiakedao` 保护区、`mud_age` 新手保护、`surrender` 投降状态等。规则未集中，散落各命令。

11. **地府轮回是房间驱动而非函数驱动**：`DEATH_ROOM->start_death(this)` 实际是 no-op（全仓库无 `start_death` 定义）。流程完全由 `gate.c`/`gateway.c`/`road2.c`/`inn1.c` 的 `init`/`valid_leave`/`add_action` 实现，包括销毁物品、清状态、谜题循环、最终通过 `ask <self> about 回家` 触发 reincarnate + move 回 /d/city/wumiao。

12. **备份文件保留演化痕迹**：`feature/attback.c`（218 行，旧 attack.c 无 special_attack）、`feature/damage_backup.c`（312 行，旧 damage.c 无 `last_eff_damage_from` 与 PKILL 日志）、`feature/damage.c.bk`（27 行片段）显示 PK 日志与双手互博是后加功能。`d/death/road3.c` 注释坦承"还没想到"（road3.c:11），是半成品。
