# 玩家心理与留存：战斗与效果生命周期簇体验点评

> 角色：玩家心理与留存专家。从动机心理学、留存曲线、心流节奏、社交压力视角点评《侠客行》LPC 战斗/Effect/死亡簇的玩家体验。
> 证据规则：每条结论标注 LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名。engine 仅作批判对照，不作反向脑补来源。

---

## 1. 战斗挫败：命中率 / 伤害随机性 / 被秒杀

### 1.1 命中率：永远存在打不中的可能，且玩家无法预判

LPC 命中判定是 `random(ap + dp) < dp`（`adm/daemons/s_combatd.c:377` / `adm/daemons/combatd.c:430`），即闪避概率 = `dp/(ap+dp)`。由于 `ap` 与 `dp` 均强制下限为 1（`s_combatd.c:360,368`），**即使攻击方碾压防御方，也永远有被打空的可能**。这对玩家心理有两面效应：

- **正面**：弱者总有翻盘希望，避免绝对碾压的乏味。
- **负面（流失风险）**：连续 miss 会产生强烈的"系统针对我"归因偏差（attribution bias）。玩家在练功打怪时连续 3-4 次打空，会感到"今天运气差"而退出；打 Boss 时关键一击 miss 导致死亡，挫败感被放大。

更隐蔽的问题在于 **AP/DP 的非线性放大**：`skill_power()` 中 `power = (level*level*level) / 3`（`s_combatd.c:237`），技能等级走立方增长。这意味着高技能玩家对低技能玩家命中率趋近 100%，但低技能玩家对高技能玩家命中率趋近 0--形成 **"打不中就永远打不中"的绝望循环**。对新引擎而言，纯 `random(ap+dp)` 模型应考虑加入"保底命中"（如最低 5% 命中 / 最高 95% 命中），防止极端数值差下的零交互体验。

### 1.2 伤害随机性：方差极大，单次伤害可波动数倍

伤害结算路径叠加了多层随机（`s_combatd.c:451-537`）：

1. 基础伤害：`damage = (damage + random(damage)) / 2`（`:452`）--本身已有 0.5x~1x 浮动。
2. 伤害加成：`damage += (damage_bonus + random(damage_bonus))/2`（`:536`）--再叠加 0.5x~1x 浮动。
3. 力量加成 `damage_bonus = me->query_str()`（`:468`）+ 内功 `hit_ob`（`:472-484`）+ 招式 `force`（`:486`）+ 武功 `hit_ob`（`:500`）+ 武器 `hit_ob`（`:507`）+ 夹劲 jiajin（`:518`）--全部累加。

最终单次伤害可在数倍区间内波动。对玩家而言，**"上一刀刮痧、这一刀暴毙"的不可预期性**破坏了战斗的节奏感与可控感。现代玩家习惯的是"伤害相对稳定、暴击是偶发惊喜"而非"基础伤害本身就大幅随机"。

### 1.3 被秒杀：无硬上限的伤害，高战力 NPC 可一刀致命

关键发现：**伤害硬上限被注释掉了**（`s_combatd.c:530-533`）：

```c
// Temporally tuning down damage power
// Seems need not this now, player's qi are much longer.
//if( damage_bonus > 360 ) damage_bonus = 180 + damage_bonus/2;
//if( damage_bonus > 180 && userp(me) ) damage_bonus = 120 + damage_bonus/3;
```

注释说明开发者曾尝试加伤害上限但放弃了。后果是：高内力/高力量的 NPC（尤其是门派师父级 NPC）单次伤害可超过玩家最大气血，形成**一刀秒杀**。

唯一的减伤机制是 `combat_exp` 经验差循环（`s_combatd.c:541-545`）：当受害者经验远高于攻击者时，伤害逐次减 1/3。但这是**对弱者攻击强者的保护**，而非保护弱者被强者秒杀。新手在野外遇到 aggressive NPC（`s_combatd.c:835-849 start_aggressive` 直接 `kill_ob`），若 NPC 战力远超玩家，玩家无任何生还窗口。

**留存风险**：被秒杀是最强的负向情绪触发器（研究显示非自愿死亡是 MUD 留存的第一杀手）。玩家投入数小时练功后一刀归零，极易触发"沉没成本反转"--投入越多、失去越痛、流失越快。

---

## 2. 死亡惩罚焦虑：下地府 / 轮回 / 鬼魂态 / 掉落 / 经验惩罚

### 2.1 死亡惩罚的叠加：六重打击

`death_penalty()`（`s_combatd.c:874-907` / `combatd.c:987-1025`）对玩家施加的惩罚清单：

| 惩罚项 | 代码位置 | 幅度 |
|--------|----------|------|
| 战斗经验 | `:886-894` | 损失 `combat_exp/100`（上限 5000），小额则固定 -20 |
| 潜力 | `:890-891` | 直接减半 `potential/2` |
| 善恶值 | `:884` | `shen` 减 1/20 |
| 行为经验 | `:885` | `behavior_exp` 减 1/20 |
| 银两（余额） | `:896-897` | 余额超 10000 部分减半 |
| 技能 | `:904` | `skill_death_penalty()` 技能降级 |

**这是极其严厉的惩罚**。现代手游/ MMO 主流设计已转向"轻惩罚重成长"--死亡损失经验 5%-10% 而非减半潜力、不损失装备。LPC 的减半潜力 + 技能降级相当于**直接回退数日甚至数周的练功成果**。

### 2.2 装备全损：地府入口销毁全部物品

`d/death/gate.c:32-36` 的 `init()`：

```c
inv = all_inventory(me);
for(i=0; i<sizeof(inv); i++) {
    if( inv[i]->is_character())continue;
    destruct(inv[i]);
}
```

玩家进入鬼门关时，**所有非生物物品被直接销毁**（非掉落、不可拾回）。这比经验惩罚更致命--装备往往需要长时间获取或购买，全损等于**对中重度玩家资产的一次性清零**。

### 2.3 鬼魂态与地府流程：强制离线体验

死亡后 `ghost = 1`（`feature/damage.c:246`），玩家被 `move(DEATH_ROOM)`（`:247`，即 `/d/death/gate.c`）。鬼魂态下 `is_ghost()` 返回真，活人看不见鬼魂（`inherit/char/char.c:181-185 visible()`），玩家**社交隔离**。

地府流程是强制的线性流程：
- `gate.c`（鬼门关，销毁物品）-> `gateway.c`（酆都城门，**禁止回头** `:32-36`）-> `road1` -> `road2`（**迷雾迷宫**，需走 5 步才通过 `:28-38`）-> `inn1.c`/`inn2.c`（找到"自己"才能轮回 `inn1.c:67-83 do_stuff`）。
- 或被动等待 `d/death/npc/wgargoyle.c:48 death_stage`：30 秒后开始播报，每 5 秒一条共 6 条，约 60 秒后 `reincarnate()` 并移至 `REVIVE_ROOM`（`/d/city/wumiao.c`）。

整个流程**强制耗时 1-3 分钟**，期间 `suicide` 指令被禁（所有地府房间 `do_suicide` 返回"你还死着呢"）。对玩家而言这是一段**不可跳过、无交互乐趣、纯惩罚体验**的"死亡过场动画"，现代设计应允许跳过或压缩。

### 2.4 额外惩罚：婚姻破裂

`feature/damage.c:249`：`MARRY_D->break_marriage(this_object())` --死亡会导致婚姻关系破裂。这不仅是数值惩罚，更是对玩家社交投入的破坏，情感打击叠加数值打击。

### 2.5 焦虑累积效应

`death_penalty()` 中 `death_times` 计数（`:882-883`）记录死亡次数。惩罚不随死亡次数递减--每次死亡都是同等严厉的全套惩罚。对反复死亡的玩家（尤其被 PK 反复击杀的受害者），**惩罚无上限累积、无递减保护**，形成恶性循环：死亡 -> 变弱 -> 更容易死 -> 更弱。

**留存建议**：新引擎应引入"死亡惩罚递减/封顶"机制，如单日死亡惩罚上限、连续死亡后惩罚递减、或"保护期"机制。

---

## 3. 中毒 / 被控无力感：持续掉血 / 被封印 / 被擒拿的失控体验

### 3.1 持续掉血毒：无交互窗口的被动失血

`feature/condition.c:21 update_condition()` 由 `heart_beat` 驱动，每 5-15 秒 tick 一次（`inherit/char/char.c:54,141-142 tick = 5 + random(10)`）。每类 condition 是独立 daemon，在 `update_condition()` 内执行副作用。

典型毒 condition 的体验：

- **`kungfu/condition/bt_poison.c`（西域灵蛇毒）**：每 tick `receive_wound("jing", damage/2)` + `receive_damage("jingli", damage/2)`（`:33-34`），且 duration 每次只减 `5 + poison_skill/10`（`:36-38`）--若玩家毒抗低，毒可持续数十 tick，**持续掉血数十次**。
- **`kungfu/condition/hanbing_damage.c`（寒冰绵掌阴毒）**：每 tick `receive_damage("qi", duration/2+20)` + `receive_wound("jing", duration/2+20)`（`:23-24`），duration 越长伤害越高，**越毒越痛**。
- **`kungfu/condition/embedded.c`（嵌入暗器）**：每 tick 固定 `receive_wound("qi", 3)`（`:17`），虽然量小但**持续到手动拔出**，NPC 会自动拔（`:20-27`）但玩家需要找方法。

**无力感来源**：中毒后玩家在 tick 之间**无法主动干预**（毒在自己身上 tick，不是对方在打你），只能被动看着血量下降。`hanbing_damage.c` 的文案"你觉得一股冷气直透心口"（`:17`）持续刷屏，强化了"我正在被侵蚀、但我无能为力"的失控感。

### 3.2 被控：丧失行动权

- **`kungfu/condition/blind.c`（盲）**：`let_know()` 中 `me->add_temp("apply/attack", amount)` + `me->add_temp("apply/defense", amount)`（`:30-31`）--盲状态会**削减攻防数值**，被盲期间战斗力大幅下降，且被恢复后才发现自己之前"莫名其妙打不中/打不疼"。
- **`kungfu/condition/drunk.c`（醉）**：duration 超过阈值时直接 `me->unconcious()`（`:14`）--**醉酒可导致昏迷**，玩家突然失去控制权。
- **`kungfu/condition/aphroclisiac.c`（春药）**：每 tick 强制对房间内对象触发 emote（`:36-42`），**玩家角色行为被劫持**，产生社交尴尬（尤其在公共区域）。
- **`kungfu/condition/city_jail.c`（牢狱）**：duration 期间玩家被移至衙门，到期才被"扔出来"（`:9-14`）--**强制禁闭**，期间无法进行正常游戏。

### 3.3 解毒门槛高，加剧无力感

唯一的主动解毒手段 `kungfu/skill/wudu-xinfa/xidu.c`（吸毒）要求：五毒心法 >= 70 级（`:17`）、内力 >= 150（`:20`）、自己未中毒（`:10-14`）、且**不能在战斗中运功**（`:7-8`）。这意味着大多数中毒玩家**无法自救**，必须找到高技能的他人帮忙，若身边无人则只能等死或耗到自然消退。

**留存建议**：新引擎应保证玩家在中毒后有至少一条可执行的应对路径（吃药/运功/求助 NPC），避免"中毒 = 等死"的死局体验。

---

## 4. 心流节奏：heart_beat tick 对沉浸与紧张感的作用

### 4.1 tick 节奏：1 秒一次的伪实时战斗

LPC `heart_beat` 默认 1 秒触发一次（`inherit/char/char.c:53 set_heart_beat(1)`）。`heart_beat()` 中每 tick 调用 `attack()`（`:132`），即**每个参战者每秒攻击一次**。

这个节奏的双面性：

- **正面**：1 秒间隔给了玩家**阅读战况、输入指令**的时间窗口。MUD 文本战斗需要阅读描述（招式名、伤害描述、状态报告），1 秒间隔是可读的下限。快于 1 秒会导致信息过载（刷屏），慢于 2 秒会感到迟钝。
- **负面**：`select_opponent()` 用 `random(MAX_OPPONENT)` 选择目标（`feature/attack.c:85`，MAX_OPPONENT=4），当 `which >= sizeof(enemy)` 时 fallback 到 `enemy[0]`（`:87`）。**目标选择是随机的**，玩家无法指定"我这次攻击谁"，多敌混战时攻击目标不可控，削弱了战术选择感。

### 4.2 守护（guard）空转：节奏被打断

`s_combatd.c:717-742 fight()` 中，若 `random(victim->query_dex()*3) >= me->query_str()*2 + apply/speed`，则攻击方进入 guard 状态（`:738-742`），只输出"注视着对方的行动"文案，**不发动攻击**。这会在战斗中插入**无输出的空转 tick**，玩家看到的是"你注视着对方"而非战斗描述，节奏突然断裂。

guard 概率取决于双方 `dex`/`str` 比。对低力量玩家，可能出现**频繁空转**（连续数 tick 不出手），产生"我怎么老是不打"的焦虑。

### 4.3 状态播报的信息密度

`s_combatd.c:71-167 damage_msg()` 按伤害区间输出不同长度的描述文本（如"结果只听见 $n 一声惨嚎，$w 已在 $p 的 $l 砍出一道深及见骨的可怕伤口！！"）。加上 `report_status()`（`:198-208`）的血量状态报告，每个攻击 tick 产生 2-4 行文本。**4v4 混战时每秒 8-16 行文本**，信息密度极高。

`brief` 模式（`s_combatd.c:308-311`）允许玩家减少输出，但默认不开。新玩家面对刷屏会**无法提取关键信息**（我的血量还安全吗？对方快死了吗？），导致认知过载（cognitive overload）而退出。

### 4.4 wimpy 逃跑：唯一的节奏退出阀

`inherit/char/char.c:124-130`：当 `qi/max_qi`、`jing/max_jing`、`jingli/max_jingli` 任一低于 `env/wimpy` 百分比时，自动调用 `GO_CMD->do_flee()`。`wimpy` 上限 80%（`cmds/usr/wimpy.c:17`）。

这是**玩家唯一可控的战斗退出机制**。但 `do_flee` 是随机方向逃跑（`cmds/std/go.c` 的 flee 逻辑），可能逃入更危险的区域。且 wimpy 默认值为 0（不自动逃跑），新玩家若不知道设置，会在不知情中被打到死。

**留存建议**：新引擎应默认开启温和的 wimpy（如 20%），并给新玩家明确引导。

---

## 5. PvP 社交压力：组队围攻 / 门派敌对 / 抢怪

### 5.1 围攻：4 打 1 的数值碾压

`feature/attack.c:12 #define MAX_OPPONENT 4`--一个角色最多同时被 4 个敌人攻击。每 tick 每个攻击者各自调用 `attack()` -> `COMBAT_D->fight()`（`:220`），即**受害者每秒承受最多 4 次独立攻击判定**。

受害者每 tick 只能 `select_opponent()` 选 1 个目标反击（`:79-88`）。4v1 时**输出输入比为 4:1**，且受害者的 dodge/parry 每次独立判定（`random(ap+dp) < dp`），4 次中总有概率被命中。组队围攻下，**任何玩家都无法长久存活**。

这在 PvP 场景中是霸凌的温床：一群玩家可以轻松围杀单个玩家，受害者几乎没有反抗空间。

### 5.2 自动敌对触发：不经同意的战斗强加

`feature/attack.c:229-258 init()` 在对象进入房间时自动检查并触发战斗：

- **hatred**（仇恨）：NPC 记住曾杀自己的玩家 ID（`killer` 列表），再遇时 `COMBAT_D->auto_fight(this_object(), ob, "hatred")`（`:247-249`）。`s_combatd.c:797-817 start_hatred` 直接 `me->kill_ob(obj)`。
- **vendetta**（世仇）：门派标记触发，`query("vendetta_mark")` 与对方 `vendetta/` 映射匹配即自动开打（`:250-253`）。
- **aggressive**（攻击性）：NPC `attitude == "aggressive"` 时对进入房间的玩家自动攻击（`:254-257`），`s_combatd.c:835-849 start_aggressive` 直接 `kill_ob`。
- **berserk**（狂暴）：邪派 NPC 随机攻击房间内玩家（`s_combatd.c:765-795 start_berserk`）。

**这些触发不经玩家同意**。玩家可能只是路过一个房间就被 NPC 追杀，或因门派身份被对方门派 NPC 自动攻击。对新手而言，"走着走着突然被打"是强烈的不可控感来源。

### 5.3 hit（偷袭）：无需同意的单次攻击

`cmds/std/hit.c` 允许对玩家偷袭（`:88-98 do_hit`），直接 `COMBAT_D->do_attack(me, obj, weapon)`。虽有限制--双方 `combat_exp` 差距不超过 3 倍（`:29-33`）、对方 `mud_age > 18000`（5 小时，`:71`）、对方不在战斗中（`:54`）--但偷袭仍是**非自愿的单方面攻击**，且对方来不及反应。

### 5.4 抢怪与 kill stealing

`s_combatd.c:910-972 killer_reward()` 将奖励给 `last_damage_from`（最后造成伤害者）。`free_rider` 临时标记（`:949, 956-959`）防止对已被他人打昏迷的 NPC 突袭抢奖励，但**对正常战斗中的 NPC 无保护**--高战力玩家可随时切入最后一击抢走 kill 经验和掉落。

### 5.5 PK 追究机制：有但不足

现有反 PK 机制：

- **新手保护**：`mud_age < 18000`（5 小时）的玩家不可被 `kill`（`cmds/std/kill.c:51-53`）或 `hit`（`cmds/std/hit.c:71-72`）。
- **pker 累积**：每次 PK 击杀 `apply_condition("pker", +120)`（`s_combatd.c:961-963`），当 `pker > 240` 时禁止继续 PK（`kill.c:51`）。即**杀第 3 人后即被限制**。
- **killer 通缉**：在 `/d/city/` 区域 PK 施加 `killer` condition 100 tick（`s_combatd.c:924`），官府通缉。
- **安全区**：`no_fight` 房间禁止一切战斗（`kill.c:16`、`fight.c:12`、`attack.c:54`）；`no_death` 房间死亡转为昏迷（`damage.c:159,189`）。

**不足之处**：

1. 新手保护仅 5 小时，对慢节奏 MUD 远远不够（很多玩家 5 小时才刚出新手村）。
2. pker 限制是"杀 2 人后才触发"，前 2 次恶性 PK 无阻碍。
3. `hit`（偷袭）不触发 pker 累积，可被滥用于骚扰（虽然不致死，但持续骚扰）。
4. **无受害者保护期**：被 PK 后立即可在复活点被再次击杀，无冷却。

---

## 6. 必须保护玩家的体验底线

基于上述分析，综合建议新引擎**必须实现**以下保护机制（标注参考的 LPC 先例与 engine 现状差距）：

### 6.1 新手保护期（扩展）

- **LPC 先例**：`mud_age < 18000`（5 小时）免 PK（`kill.c:51-53`）。
- **建议**：扩展为"前 N 小时 / 前M级"双重门槛的全面保护，不仅免 PK，还免 aggressive NPC 自动攻击、免偷袭。5 小时对现代玩家太短，建议按"进度里程碑"（如完成新手任务链）而非纯时间判定。

### 6.2 死亡惩罚递减与封顶

- **LPC 先例**：无（`death_penalty()` 每次同等惩罚，`s_combatd.c:874-907`）。
- **engine 现状**：`death_flow.py:78-86 DeathPolicy` 有 `penalty_ratio: float = 0.1`（统一 10% 比例惩罚），远比 LPC 温和，且无技能降级、无潜力减半、无装备全损。这是**正确的方向**。
- **建议**：增加"单日死亡惩罚上限"和"连续死亡递减"（如当日第 3 次起惩罚减半），避免恶性循环。`DeathPolicy` 应增加 `daily_penalty_cap` 字段。

### 6.3 被杀保护期（复活冷却）

- **LPC 先例**：无。复活后立即可在 `REVIVE_ROOM`（`/d/city/wumiao.c`，`no_fight` 安全区）被围堵，虽安全区内不能打，但一出安全区即可被杀。
- **建议**：复活后给予 N 分钟"不可被攻击/不可攻击"保护期，让玩家有喘息、整理装备、恢复状态的时间。

### 6.4 伤害硬上限（防秒杀）

- **LPC 先例**：曾尝试但被注释掉（`s_combatd.c:530-533`）。
- **engine 现状**：`combat.py:132-216 resolve_attack()` 无伤害上限逻辑；`DefaultWuxiaPowerModel`（`:85-113`）的 `base_damage` 直接返回 `attack_power`，无封顶。
- **建议**：引入"单次伤害不超过目标最大气血的 X%"硬上限（如 60%），保证玩家至少有 2 次反应窗口。这对 NPC 秒杀玩家和玩家秒杀 NPC 都适用。

### 6.5 中毒应对路径保证

- **LPC 先例**：`xidu.c` 解毒门槛极高（五毒心法 70 + 内力 150 + 非战斗中），多数玩家无法自救。
- **建议**：保证每种负面 condition 至少有一条"普通玩家可执行"的解除路径（通用解毒药、城镇 NPC 医师、时间自然消退有上限）。`condition.c:62-63` 的 `CND_CONTINUE` 机制应保证 condition 有必然消退的 duration 上限，而非无限持续。

### 6.6 战斗信息可读性

- **LPC 先例**：`brief` 模式可选（`s_combatd.c:308-311`），但默认关闭。
- **建议**：默认开启精简战斗描述，将伤害数值/状态以结构化方式呈现（如血条百分比而非纯文字描述），降低认知负荷。engine 的 `CombatRoundResult.message_fragments`（`combat.py:60-70`）已是结构化元组，**方向正确**，应保持并强化。

### 6.7 围攻限制（反霸凌）

- **LPC 先例**：`MAX_OPPONENT = 4`（`attack.c:12`）限制了敌人列表上限，但 4v1 仍是碾压。
- **建议**：PvP 场景下对围攻做额外限制，如"同一玩家最多同时被 2 名玩家攻击"，或围攻方每人伤害递减（人海惩罚）。

---

## 7. engine 批判对照：玩家体验视角的偏差

> 以下对照 engine 现有模块与 LPC 设计，从玩家体验角度标注偏差。

### 7.1 `engine/src/openmud/death.py` + `death_flow.py`：惩罚温和但缺关键保护

- **正面差距**：`DeathPolicy`（`death_flow.py:77-86`）默认 `penalty_ratio=0.1`、`drop_items=True`（掉落到房间而非销毁）、无潜力减半、无技能降级、无地府流程--比 LPC 温和得多，符合现代设计。
- **缺失**：
  - 无新手保护期机制（LPC 有 `mud_age < 18000`）。
  - 无被杀保护期 / 复活冷却。
  - 无连续死亡递减。
  - `NoDeathZone` 组件存在（`death_flow.py:23,194`），但无 `no_fight`（禁战斗区）对应物--安全区只防死不防打。
  - 无反 PK 累积机制（pker/killer condition）。

### 7.2 `engine/src/openmud/conditions.py`：概念错位（通用布尔求值 vs 时效 Effect）

- **关键偏差**（brief 已标注）：`conditions.py` 是通用条件表达式求值器（`Equals`/`And`/`Or`/`Not`，`:30-33`），**不是 LPC `condition.c` 的时效性 Effect 引擎**。LPC 的 condition 是 `heart_beat` 驱动的、每 tick 执行副作用（掉血/播报/状态变更）的独立 daemon（`condition.c:62 call_other(cnd_d, "update_condition", ...)`）。
- **玩家体验影响**：engine 当前无法表达"中毒每 tick 掉血并播报"这类核心体验。毒/被控的持续效果、pker 的累积计数、killer 的通缉倒计时，在 engine 中都无对应抽象。这是体验层的最大缺口。

### 7.3 `engine/src/openmud/combat.py`：结算合理但缺保护

- **正面**：`resolve_attack`（`:132-216`）七步管线清晰，`CombatRoundResult`（`:59-70`）结构化输出。
- **缺失**：
  - 无伤害硬上限（防秒杀）。
  - 无 `combat_exp` 经验差减伤循环（LPC `s_combatd.c:541-545` 对弱者有保护）。
  - 无 guard 空转机制（LPC 有节奏缓冲，虽体验有争议）。
  - riposte 为 no-op（`:268-270`），LPC 有反击机制（`s_combatd.c:665-678`）。
  - `DefaultWuxiaPowerModel`（`:85-113`）公式简单（`force × (1 + str × 0.02)`），无 LPC 的 `level^3` 非线性放大，**数值差距更平缓**--这对玩家体验是正面的（减少碾压感），但需要数值平衡专家评估。

### 7.4 `engine/src/openmud/death_flow.py` 昏迷机制

- `UNCONSCIOUS_BLOCKED_VERBS`（`:48-74`）禁止昏迷期间 22 个动词，方向正确。
- 昏迷恢复用 `ticks_remaining`（`:417-429`），比 LPC 的 `random(100-con)+30` 秒（`damage.c:134`）更可控。但 LPC 的 constitution 影响恢复速度是一个有意义的"属性投资回报"设计，engine 的固定 tick 数丢失了这层深度。

---

## 8. 总结：体验风险优先级

| 风险 | 严重度 | 流失影响 | LPC 先例 | engine 现状 |
|------|--------|----------|----------|-------------|
| 被秒杀（无伤害上限） | 极高 | 单次即可能流失 | 上限被注释 | 无上限 |
| 死亡惩罚过重 | 极高 | 累积流失 | 六重惩罚+装备全损 | 已大幅减轻 |
| 中毒等死无解 | 高 | 挫败退出 | 解毒门槛极高 | 无 Effect 引擎 |
| 被围攻 4v1 | 高 | PvP 霸凌流失 | MAX_OPPONENT=4 | 无围攻限制 |
| 新手保护不足 | 中高 | 新手期流失 | 仅 5 小时 | 无保护期 |
| 战斗信息过载 | 中 | 认知负荷退出 | 默认全量文本 | 结构化但未精简 |
| 死亡流程强制耗时 | 中 | 体验中断 | 1-3 分钟地府 | 已移除地府 |
| 无复活保护期 | 中 | 反复被杀 | 无 | 无 |

**核心结论**：LPC 战斗簇的玩家体验设计**惩罚导向重于保护导向**，符合 90 年代 MUD "高难度硬核"文化，但与现代玩家期望严重脱节。engine 已在死亡惩罚（`DeathPolicy`）、结构化战斗结果（`CombatRoundResult`）、昏迷动词封锁（`UNCONSCIOUS_BLOCKED_VERBS`）上做了正确改进，但**仍缺三大体验底线**：(1) 伤害硬上限防秒杀；(2) 时效性 Effect 引擎（conditions.py 概念错位）；(3) PvP 保护机制（新手期/复活冷却/围攻限制）。这三项是新引擎从"可玩"到"可留存"的关键跨越。
