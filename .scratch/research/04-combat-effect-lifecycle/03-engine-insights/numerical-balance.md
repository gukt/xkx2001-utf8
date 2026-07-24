# 数值平衡评估：战斗与效果生命周期簇

> 角色：数值平衡专家 | 输出层：03-engine-insights
> 证据规则：每条结论标注 LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名。

## 0. 评估总览

LPC 战斗数值体系是一套**多轴耦合、立方缩放、手工调参**的系统，核心特征是：
技能等级立方缩放（`level^3/3`）、A/(A+B) 概率对抗、三类伤害两层上限、Effect 时效
引擎独立 daemon。它在新引擎语境下的最大可参考价值是**「哪些数值维度必须建模」**，
最大的风险警示是**立方缩放在高等级区间必然爆炸**与**死亡惩罚对技能等级的毁灭性打击**。

engine `DefaultWuxiaPowerModel` 采用线性公式 `force*(1+str*0.02)`，数值维度覆盖严重
不足（无 combat_exp / jingli / 招架分离 / 伤口系统），作为 MVP 自洽可测，但**题材包
调参空间不足以还原武侠战斗的数值纵深**。

---

## 1. 伤害公式：三类伤害与两层数值模型

### 1.1 三类伤害与双层属性架构（LPC）

`feature/damage.c:receive_damage(type,damage,who)`（:13-37）与
`receive_wound(type,damage,who)`（:39-66）定义了三类伤害和两层属性：

- **三类伤害类型**：`jing`（精）、`qi`（气）、`jingli`（精力）。`receive_wound` 只支持
  `jing`/`qi` 两类（:44-45 拒绝 `jingli`）。
- **三层属性**：`max_jing`/`max_qi`/`max_jingli`（永久上限） > `eff_jing`/`eff_qi`
  （当前有效上限，可被 wound 降低） > `jing`/`qi`/`jingli`（当前值）。
- **damage vs wound 区别**：
  - `receive_damage` 只扣当前值，到 -1 截断（:31-32）；`eff_` 上限不变。
  - `receive_wound` 先扣 `eff_` 上限（:53-59），再把当前值压到不超过新 `eff_`（:61）。
  即 **wound 是永久性伤害**（需要 `receive_curing` 或自然恢复 `eff_++`），damage 是
  临时伤害（`receive_heal` 即可恢复）。

**数值平衡含义**：两层模型让「轻伤」与「重伤」有数值区分。轻伤只扣 `qi`，恢复快
（`heal_up` 中 `qi += con/3 + max_neili/10`，`feature/damage.c:300-302`）；重伤扣
`eff_qi`，每 tick 只 +1（:305-306），恢复极慢。这制造了战斗的**累积压力感**。

### 1.2 combatd 伤害数值链（LPC）

`adm/daemons/combatd.c:do_attack()`（:340-780）的伤害结算分 7 步，数值链如下：

1. **基础伤害**（:519-520）：`damage = apply/damage; damage = (damage + random(damage))/2`
   — 武器伤害值取 50%~100% 随机。`apply/damage` 来自武器 `weapon_prop/damage`
   （`feature/equip.c:wield()` :100-102 累加到 `apply/`）。
2. **NPC 伤害加成**（:523-524）：`damage += (apply/attack+1)/10 * (damage/10)` —
   NPC 专属，补偿其无武功招式 hook 的劣势。
3. **招式伤害加成**（:528-529）：`damage += action["damage"]/10 * (damage/30)` —
   招式 `damage` 字段（如 18-zhang 的 25~120，`kungfu/skill/18-zhang.c:57-216`）。
4. **技能等级加成**（:534）：`damage += (skill(attack_skill)+1)/10 * (damage/10)` —
   技能等级线性放大基础伤害。
5. **力量伤害加成** `damage_bonus = query_str()`（:536），随后被多层放大：
   - 内功 `force_skill->hit_ob()` 返回值（:543-561，徒手全加 / 持械 1/3）；
   - 招式 `action["force"]`（:564-570，徒手 `force/10*damage_bonus/100` / 持械
     `force/10*damage_bonus/300`）；
   - 技能+内功等级（:573-576，徒手 `(skill/4+force/2+1)/10*damage_bonus/10`）；
   - 武功 `martial_skill->hit_ob()`（:578-585）；
   - 武器/角色 `hit_ob()`（:588-603）；
   - 加劲 `jiajin`（:606-617，`jingli/20 + jiajin - victim_jingli/25`）。
6. **最终合并**（:628-633）：`damage += (damage_bonus + random(damage_bonus))/2`
   — 伤害加成也取 50%~100% 随机。
7. **combat_exp 防御衰减**（:636-641）：`while random(defense_factor) > combat_exp:
   damage -= damage/3; defense_factor /= 2` — 防御方 combat_exp 越高，伤害衰减
   越多，但每次只减 1/3 且 defense_factor 减半，呈指数递减。

**数值平衡批判**：伤害公式有 **6+ 层乘法叠加**，每层都引用不同数值源（武器、招式、
技能等级、力量、内功、加劲），导致**数值调参自由度极高但可控性极低**。任何一层的
数值偏离都会被后续层放大。注释 `// disable action["damage"] temporarily until we find
a consistent damage sys`（:527）和被注释掉的全局上限（:625-626 `if damage_bonus > 360`）
说明**开发者自己也意识到数值失控但未根治**。

### 1.3 伤口判定概率（LPC）

`combatd.c:680-686`：伤口（`receive_wound`）触发条件是概率性的：
- `random(damage) > apply/armor`（伤害超过护甲）
- AND（`is_killing` 时 1/2 或 1/4 概率；非 `is_killing` 时 1/4 或 1/7 概率）
- 持械时概率更高（1/2 vs 1/4 kill，1/4 vs 1/7 non-kill）

**含义**：`kill` 模式（`kill_ob`）比 `fight` 模式（`fight_ob`）更容易造成永久伤口，
这是 PvP 比切磋更危险的数值根源。`feature/attack.c:kill_ob()`（:51-62）设置 `killer`
列表，`do_attack` 中 `is_killing` 检查（:680）即查此列表。

---

## 2. 命中率 / 闪避 / 招架 / 暴击

### 2.1 A/(A+B) 概率对抗模型（LPC）

`combatd.c:skill_power()`（:288-333）计算 AP/DP/PP，命中判定用
`random(ap+dp) < dp`（:430）——即 **AP/(AP+DP) 命中概率**。

- **AP（攻击力）** = `(skill_level^3 / 3 + combat_exp) / 30 * (str/10) *
  (jingli_bonus/10)`，其中 `jingli_bonus = 50 + jingli/max_jingli * 50`，上限 150
  （:309-311）。
- **DP（闪避力）** = 同公式但用 `dex` 替代 `str`，且 `fight/dodge` temp 可加成
  （:304-306）。
- **PP（招架力）** = 同 DP 公式但用 `parry` 技能。

关键特性：
- **永远有命中和闪避可能**（AP、DP 都 >= 1，:410-411/421-422）——无 100% 命中或
  100% 闪避，这与现代游戏的「确定性命中」设计不同。
- **无暴击系统**：LPC 原版没有 crit 概念，伤害方差来自 `random(damage)` 的 50%
  波动（:520/629）而非暴击倍率。这是设计空白而非刻意选择。
- **负 dodge/parry**：招式可设负 dodge（如 `18-zhang.c:210` 亢龙有悔 `dodge: -20`），
  意味着该招式**降低自身闪避**换取伤害——但实现是 `set_temp("fight/dodge", action["dodge"])`
  （:414-415），乘进 DP 公式 `level * (100 + dodge/10)/100`（:305），负 dodge 直接
  降低防御方闪避力。

### 2.2 招架的特殊规则（LPC）

`combatd.c:468-480`：招架力计算有非对称规则：
- 防御方持械时 `pp = skill_power(victim, "parry")`；若攻击方徒手且招式无 `weapon`
  字段，`pp *= 2`（:472）——**空手打持械者，招架翻倍**。
- 防御方徒手时：攻击方持械则 `pp = 0`（:476-477，徒手无法招架武器）；双方徒手则
  `pp = skill_power(victim, attack_skill)`（:479，用同技能对抗）。

**数值平衡含义**：这条规则让武器 vs 徒手有明显数值优势（徒手无法招架武器攻击），
鼓励玩家持械。但某些武功（如降龙十八掌 `valid_learn` 要求空手，`18-zhang.c:224`）
必须徒手，形成天然的数值 trade-off。

### 2.3 busy 状态的数值削弱（LPC）

`combatd.c:419` `if victim->is_busy() dp /= 3`，`:482` `pp /= 2`。
被 busy 的目标闪避降至 1/3、招架降至 1/2，几乎必中——这是 control effect
（如擒拿/封印）的数值价值所在。

### 2.4 engine 对照：_roll_opposed（engine）

`engine/src/openmud/combat.py:_roll_opposed()`（:219-224）实现同样的
`random(attack+defense) < defense` 概率。但 `DefaultWuxiaPowerModel`（:85-113）
的 AP/DP 公式极简：
- AP = `force * (1 + str * 0.02)`（线性，:98-100）
- DP = `dex * 1.0 + move.dodge`（线性，:102-104）
- PP = DP（:106-107，**招架与闪避共用同一防御势**）

**偏差**：engine 缺失了 LPC 的 5 个数值维度——combat_exp、jingli_bonus、技能等级立方、
str/dex 乘数、busy 削减。这使得 engine 的命中概率几乎只由 `force` 和 `dex` 决定，
**无法表达「老手对新手的高命中率」或「精力充沛时的战斗优势」**。题材包调参时
只有 `str_factor`（0.02）和 `dex_factor`（1.0）两个系数可用。

---

## 3. 数值缩放：立方爆炸与边际递减

### 3.1 技能等级的立方缩放（LPC，核心风险）

`combatd.c:skill_power()` :317：`power = (level * level * level) / 3`

这是**立方缩放**（O(level^3)），在 skill_power 中先立方再除以 30，再乘
str/dex 和 jingli_bonus。以 skill level 100 为例：
- `power = 100^3/3 = 333,333`
- `AP = (333333 + combat_exp) / 30 * (str/10) * (jingli_bonus/10)`

而 skill level 200（翻倍）：
- `power = 200^3/3 = 2,666,667`（**8 倍增长**，而非 2 倍）

**这是指数爆炸**。LPC 靠 `combat_exp` 的线性叠加（`power + combat_exp`）和 30 的除数
来部分缓冲，但高等级区间（>150）的数值膨胀不可避免。NPC `shan.c` 的
`set_skill("wuxing-quan", 120)`（:76）和 `suicong3.c` 的 `set_skill` 全 100（:37-49）
说明设计者把 NPC 技能等级控制在 100-120，回避了立方爆炸区。

**新引擎建议**：立方缩放在纸笔 MUD 时代可行（玩家成长慢），但在追求快节奏的现代
游戏里是数值灾难。建议改为**多项式或对数缩放**（如 `level * k1 + level^1.5 * k2`），
保留成长曲线但控制上限。

### 3.2 jingli_bonus 的边际递减（LPC，正面案例）

`combatd.c:309-311`：`jingli_bonus = 50 + jingli/max_jingli * 50`，`if > 150 then 150`

这是**线性+上限封顶**——精力从 0 到 50% 时 bonus 从 50 涨到 75，50% 到 100% 时
涨到 100，超过 100% 精力（`jingli` 可达 `max_jingli*2`，`damage.c:316`）时封顶 150。
设计合理：前半段线性收益，后半段递减，防止精力溢出导致数值爆炸。

### 3.3 str/dex 乘数封顶（LPC，combatd vs s_combatd 差异）

`combatd.c:321-322/328-329` 有 `if (str/10)*(jingli_bonus/10) > 300 then ... * 300`
的封顶逻辑——**combatd 对高 str 角色有数值上限**。

但 `s_combatd.c:240-244` **没有这个封顶**——`return (power + combat_exp)/30 *
str/100 * jingli_bonus` 无上限。这说明两个 combat daemon 的数值平衡**不一致**，
s_combatd 是 prototype（文件头注释明确标注 `protocode`，:12），其数值未调优。

### 3.4 combat_exp 的防御衰减循环（LPC，正面案例）

`combatd.c:636-641`：`while random(defense_factor) > my["combat_exp"]: damage -=
damage/3; defense_factor /= 2`

这是**指数衰减**——每次循环伤害减 1/3，defense_factor 减半。高 combat_exp 防御方
可以多次触发衰减，但每次只减 1/3，不会归零。这提供了**边际递减的防御收益**：
combat_exp 翻倍不会让伤害归零，只是多一轮 1/3 衰减。

### 3.5 engine 对照：线性缩放无边际递减

`engine/src/openmud/combat.py:DefaultWuxiaPowerModel` 的 `attack_power`（:98-100）
是纯线性 `force * (1 + str * 0.02)`，无立方、无封顶、无边际递减。

- 优点：数值可控，MVP 自洽可测（ADR-0001 不追求 LPC 还原）。
- 缺点：**无法表达「高等级角色的碾压优势」也「无法表达边际递减」**，战斗在高低等级
  之间的区分度不足。题材包若想还原武侠「高手一掌秒杀」的体验，线性公式不够。
- `PowerModel` Protocol（:72-83）允许题材包整体替换，这是正确的抽象方向——但
  `DefaultWuxiaPowerModel` 作为默认值过于简单，未提供立方/对数等可选缩放函数。

---

## 4. PvE vs PvP 平衡

### 4.1 MAX_OPPONENT=4 与围攻数值（LPC）

`feature/attack.c:12` `#define MAX_OPPONENT 4`，`:79-88 select_opponent()` 用
`random(MAX_OPPONENT)` 选择目标——**每次只攻击 1 个目标**，但可被最多 4 人围攻。

围攻的数值压力来自**每个攻击者独立调用 `fight()`**（`combatd.c:787-845`）：
- 每个 attacker 的 `fight()` 独立判定 `random(victim_dex*3) < attacker_str*2 + apply/speed`
  （:818）决定是否攻击 vs 防守（guard）。
- 被围攻者每 tick 被多个 attacker 各自结算一次 `do_attack()`，伤害累积。
- **没有围攻伤害加成**：LPC 没有侧翼/背刺/多人合击的数值加成（`attack.c:197-206
  special_attack()` 只是 Anubis 实验性 prototype）。

**数值平衡含义**：4 人围攻 = 4 倍伤害输出（每人独立），但被围攻者的 DP/PP 不变——
这是**线性叠加的数值压力**。低 combat_exp 角色被 4 人围攻几乎必死，高 combat_exp
角色靠防御衰减循环可存活。这种平衡**依赖 combat_exp 作为分水岭**。

### 4.2 NPC 的数值补偿（LPC）

`combatd.c:523-524`：NPC 专属伤害加成 `damage += (apply/attack+1)/10 * (damage/10)`。

`combatd.c:446-451`：NPC 攻击未命中时也有概率获得 combat_exp 和技能提升——
**NPC 在战斗中会变强**。

`combatd.c:818` 的攻击/防守判定：`random(victim_dex*3) < attacker_str*2 + apply/speed`
——速度（`apply/speed`）直接影响攻击频率，NPC 若有高 speed 则更激进。

### 4.3 玩家 vs NPC 的数值鸿沟（LPC）

NPC 数值（`clone/npc/`）：
- `suicong3.c`：max_qi=1200, max_jing=1200, max_neili=2000, combat_exp=100000,
  skills=100。
- `shan.c`：max_qi=900, max_jing=500, max_neili=800, combat_exp=400000,
  skills=100-120。

玩家典型数值（从 `damage.c:heal_up()` 和 `skill.c:improve_skill()` 推断）：
- 玩家 combat_exp 从 0 起步，每次命中 +1（`combatd.c:441/499/698-702`），成长极慢。
- 玩家技能等级靠 `improve_skill`（`feature/skill.c:149-182`）累积，升级所需经验为
  `(level+1)^2`（:176）——**二次方成长曲线**，level 100 需 10201 经验。

**数值鸿沟**：NPC combat_exp 10 万~40 万，玩家早期 combat_exp 几百到几千。在
`skill_power` 公式中 `power + combat_exp` 的线性叠加下，低 combat_exp 玩家对高
combat_exp NPC 的 AP/DP 几乎被 NPC 的 combat_exp 项碾压。再叠加立方缩放（NPC
skill 100 的 power=333333），**新手打高等级 NPC 命中率趋近于 0**。

这是 LPC 的**刻意设计**——用 combat_exp 锁定 PvE 进度，玩家必须先打低等级 NPC
积累 combat_exp。但这也导致**数值鸿沟过大，缺乏弹性**。

### 4.4 组队无战斗加成（LPC）

`feature/team.c`（127 行）只有移动跟随（`follow_me`/`follow_path`）和队伍管理
（`add_team_member`/`dismiss_team`），**没有任何战斗数值加成**——组队不增加伤害、
不减少被伤害、不提供合击/掩护。

`feature/damage.c:unconcious()` :124 `dismiss_team()` 和 `:244` `die()` 中
`dismiss_team()`——昏迷/死亡时解散队伍，这是组队唯一的战斗相关效果（负面）。

**新引擎建议**：如果组队是 MVP 必做场景（CLAUDE.md 第 7 条），应考虑是否引入组队
战斗加成（如合击/掩护/伤害分摊），否则组队只是移动便利，战斗价值为零。

### 4.5 wimpy 逃跑阈值（LPC）

`inherit/char/char.c:124-130`：`wimpy_ratio` 检查 `qi/max_qi <= wimpy_ratio`
（或 jing/jingli 同理）时触发 `GO_CMD->do_flee()`。这是玩家可设的逃跑阈值
（百分比），是 PvE 中避免死亡的主要手段。LPC 默认无 wimpy（需玩家 `set wimpy 20`
等命令设置），**新玩家不知道此机制容易死亡**。

---

## 5. Effect 数值平衡

### 5.1 中毒持续掉血（LPC）

- `bt_poison.c`（西域灵蛇毒）：每 tick `receive_wound("jing", damage/2)` +
  `receive_damage("jingli", damage/2)`（:33-34），`damage = duration or 10`（:30-31）。
  duration 每次减 `5 + poison_skill/10`（:37-38）——**解毒技能直接缩短持续时间**。
- `chilian_poison.c`（赤炼掌毒）：每 tick `receive_damage("qi", random(duration)/2+10)`
  + `receive_wound("jing", random(duration)/2+10)`（:21-22）。伤害随 duration
  线性增长且带随机性，**高 duration 毒极致命**。
- `hanbing_damage.c`（寒冰绵掌阴毒）：每 tick `receive_damage("qi", duration/2+20)`
  + `receive_wound("jing", duration/2+20)`（:23-24）——固定 20 基础 + duration/2，
  duration 每次 -1（:26）。

**数值平衡批判**：毒的伤害公式不统一——`bt_poison` 用 `duration/2`，
`chilian_poison` 用 `random(duration)/2+10`，`hanbing_damage` 用 `duration/2+20`。
三个毒的数值模型不同，没有统一的 Effect 强度框架。新引擎应建立**统一的 Effect
强度-持续时间模型**（如 `damage_per_tick = base + duration * coefficient`）。

### 5.2 被封印/被削弱的强度（LPC）

`juehu_damage.c`（绝户手）：每 tick `add_temp("apply/attack", -duration)` +
`add_temp("apply/defense", -duration)`（:40-41），然后每 tick `add_temp(..., +1)`
逐步恢复（:46-47）。

**这是线性削弱的线性恢复**——duration 400 时攻击/防御各 -400，这在
`skill_power` 公式中会被 `(level+apply/attack)` 累加（:300），-400 的 attack
惩罚对低等级角色是**毁灭性的**（直接归零 AP），对高等级角色影响较小。但恢复
速度是 +1/tick，duration 400 需要 400 tick 恢复——**恢复极慢**。

`blind.c`（致盲）：通过 `cimu_power` temp 削减 `apply/attack` 和 `apply/defense`
（:28-32 `let_know()` 恢复时 `add_temp(..., amount)`），duration 到 0 时一次性恢复。
比 juehu_damage 温和（一次性恢复 vs 逐 tick 恢复）。

### 5.3 被擒拿的强度（LPC）

LPC 没有统一的「擒拿」Effect。`juehu_damage` 的攻击/防御削弱是最接近的。engine 的
`SilkRopeCaptureBehavior`（`engine/src/openmud/skills.py:105-137`）实现了**命中后
relocate_entity**（把防御方拽入密室），但这是**位移效果而非数值削弱**——没有 AP/DP
惩罚，只是限制行动空间。LPC 的擒拿更接近 juehu 的数值削弱模型。

### 5.4 Effect 的 duration 语义不统一（LPC，关键问题）

`feature/condition.c` 的 `update_condition()`（:21-69）只负责调用外部 daemon 的
`update_condition(me, info)`，duration 的递减逻辑**完全由各 condition daemon 自己实现**：

- `bt_poison.c:37` 减 `5 + poison_skill/10`
- `chilian_poison.c:30` 减 1
- `hanbing_damage.c:26` 减 1（且重复减了两次，:26-27 是 bug）
- `juehu_damage.c:45` 减 1
- `embedded.c:29` 减 1
- `pker.c:9` / `killer.c:12` 减 1

**没有统一的 duration 递减框架**——有的减 1，有的减 5+技能，有的有 bug（hanbing
减了两次）。新引擎必须建立**统一的 Effect 时效引擎**（duration 递减策略由 Effect
类型声明，不由 daemon 硬编码）。

### 5.5 Effect 的恢复机制不统一（LPC）

- `bt_poison` 靠 `poison` 技能缩短 duration（被动恢复）
- `juehu_damage` 靠逐 tick `+1` 恢复 apply 值（缓慢线性恢复）
- `blind` 靠 duration 到 0 后一次性恢复（全量恢复）
- `embedded` 靠 `remove` 命令拔出暗器（主动恢复，`embedded.c:23` NPC 自动拔）

**没有统一的 Effect 恢复模型**。新引擎应考虑 Effect 的恢复路径（自然过期 / 技能
解除 / 物品解除 / 主动操作）作为 Effect 类型的声明字段。

---

## 6. 死亡惩罚数值

### 6.1 LPC 死亡惩罚的多轴削减（LPC）

`adm/daemons/combatd.c:death_penalty()`（:987-1025）：

| 属性 | 惩罚 | 比例 | 来源 |
|------|------|------|------|
| combat_exp | `-combat_exp/100` | 1%，上限 5000 | :1001-1003 |
| shen（善恶值） | `-shen/20` | 5% | :999 |
| behavior_exp | `-behavior_exp/20` | 5% | :1000 |
| potential | `-potential/2` | 50%（仅当 combat_exp 损失>50） | :1007-1008 |
| balance（存款） | `-(balance-10000)/2` | 超过 1 万的部分扣 50% | :1013-1015 |
| thief（偷窃值） | `/2` | 50% | :1020-1021 |
| **所有技能** | **每项 -1 级** | **毁灭性** | :1022 `skill_death_penalty()` |
| death_times | +1（若 combat_exp >= 10000*death_times） | 递增阈值 | :997-998 |
| vendetta | delete | 清零 | :1017 |
| 物品 | 掉落全部背包到尸体 | 100% | `damage.c:227-228` |

`feature/skill.c:skill_death_penalty()`（:121-147）：**所有技能等级 -1**，且重新
计算 learned 经验为 `(level+1)^2/2`——这意味着 level 100 技能死亡后变 99，但
99 到 100 需要重新积累 `(100)^2 = 10000` 经验。

**数值平衡批判**：
- combat_exp 1% 惩罚**过轻**（100 万 combat_exp 只扣 1 万，上限 5000 更是毛毛雨）。
- 技能 -1 级**过苛**（高等级技能的升级经验是二次方，-1 级等于损失大量时间投入）。
- 这种「轻 exp 罚 + 重 skill 罚」的组合**不成比例**，对依赖单一武功的玩家毁灭性大，
  对多武功均衡发展的玩家影响小——**惩罚不均匀**。
- `death_times` 递增阈值（`combat_exp >= 10000 * death_times`）让低 combat_exp
  玩家**不会累积 death_times**（第一次死时 combat_exp < 10000 则不加 death_times），
  但 death_times 本身在 `death_penalty` 中没有被用于加重惩罚——它是**未完成的设计**
  （可能原本计划按 death_times 递增惩罚比例但未实现）。

### 6.2 地府轮回的额外惩罚（LPC）

`d/death/gate.c:init()`（:26-48）：进入鬼门关时 `destruct` 所有非角色物品
（:33-36）——**死亡时再清一次背包**（与 `damage.c:227-228` 掉落尸体重复），
且 `clear_condition()`（:38）清除所有状态。

`d/death/death.c`（死刑室）：非巫师玩家被 `block_cmd` 锁定（:23-27），只能
quit/suicide/goto——**死亡后无法操作**，必须走完地府流程才能复活。

**数值平衡含义**：地府流程是**时间惩罚**（玩家必须花时间走完鬼门关→酆都城→
轮回流程），不是数值惩罚。但对玩家来说，时间惩罚 + 物品清空 + 技能 -1 级的
组合**可能过苛**，导致死亡后弃游。

### 6.3 engine 对照：单一比例惩罚（engine）

`engine/src/openmud/death_flow.py:DeathPolicy`（:77-86）：
- `penalty_ratio: float = 0.1`（10% 统一比例）
- `drop_items: bool = True`
- `drop_currency: bool = True`
- `_apply_currency_penalty()`（:291-296）：扣 10% 货币
- `_apply_skill_exp_penalty()`（:299-305）：扣 10% 技能经验（**不是技能等级**）

**偏差**：
- engine 用**单一 10% 比例**惩罚货币和技能经验，比 LPC 的多轴惩罚**简化过度**。
- engine 扣的是**技能经验**（exp），LPC 扣的是**技能等级**（level）——engine 的
  设计更合理（不直接降级，只扣经验），避免了 LPC 的毁灭性等级损失。
- engine 没有 shen/behavior_exp/potential/balance 等维度——这些是 LPC 特有的武侠
  世界属性，题材包若需要可自行扩展，但 engine 的 DeathPolicy 没有**可扩展的惩罚
  维度列表**（只有 4 个固定字段）。
- engine 的 `drop_items=True` 掉落全部背包（:244-245），与 LPC 一致——但 LPC
  还掉尸体（`CHAR_D->make_corpse`），engine 没有 corpse 概念。

---

## 7. 付费数值红线

### 7.1 绝不能付费影响的数值（pay-to-win 红线）

基于 LPC 数值体系，以下数值**直接影响战斗胜负**，付费影响即破坏公平性：

| 数值 | LPC 来源 | 红线理由 |
|------|----------|----------|
| combat_exp | `combatd.c:skill_power()` :314/317 | 决定 AP/DP 和防御衰减，是战斗力的核心轴 |
| 技能等级（skill level） | `skill_power()` :295 `query_skill(skill)` | 立方缩放进 AP，1 级差异 = 3 倍 power 差异 |
| max_neili / max_jingli | `heal_up()` :320-327 | 决定战斗持久力和内力消耗上限 |
| str / dex / con / int | `skill_power()` :321/328 | 直接乘进 AP/DP 公式 |
| 武器 weapon_prop/damage | `do_attack()` :519 | 基础伤害来源 |
| jiali / jiajin | `do_attack()` :539/606 | 内力/精力加成，直接加伤害 |
| apply/attack / apply/defense / apply/armor | `skill_power()` :300/302 | 全局战斗属性加成 |
| jingli_bonus | `skill_power()` :309 | 精力充沛度的战斗加成（上限 150） |

### 7.2 可做付费便利的数值

| 便利项 | LPC 对应 | 理由 |
|--------|----------|------|
| 复活房间选择 | `death_flow.py:revive_room_key` | 不影响战斗力，只影响便利性 |
| 死亡惩罚减免（次数限制） | `death_penalty()` | 若为订阅特权且有次数上限，不破坏公平 |
| 背包扩展（格子数） | `Container.items` | 便利性，非战斗力 |
| 精力/体力恢复速度加成 | `heal_up()` 的恢复速率 | 等待时间便利，非战斗数值 |
| 自动捡取/自动战斗辅助 | 无 LPC 对应 | QoL，非数值 |
| 外观/称号/颜色 | 无战斗影响 | 纯装饰 |
| 坐骑速度加成 | `apply/speed` | 若只影响移动非战斗 speed 则可（LPC `apply/speed` 同时影响战斗，需分离） |

### 7.3 红线警示：apply/speed 的双重用途

`combatd.c:766/818` 中 `apply/speed` 同时影响**反击概率**和**攻击主动性**
（`random(victim_dex*3) < attacker_str*2 + apply/speed`）。若付费坐骑提供
`apply/speed` 加成，会间接影响战斗——**必须分离移动 speed 与战斗 speed**，
或确保付费 speed 加成只影响移动不影响战斗。

---

## 8. engine PowerModel 协议的题材包调参评估

### 8.1 PowerModel Protocol 的抽象正确性

`engine/src/openmud/combat.py:PowerModel`（:72-83）定义了 4 个方法：
`attack_power` / `defense_power` / `parry_power` / `base_damage`。

**正确点**：
- 协议化设计允许题材包整体替换（`attach_power_model`，:119-124），符合 ADR-0004。
- `CombatContext`（:33-56）携带了 str/con/dex/int/neili/qi 快照，为题材包提供了
  足够的输入维度。
- `CombatMoveSnapshot`（:21-30）有 `force`/`dodge`/`damage`/`damage_type`，对应
  LPC 的 `action` mapping 字段。

**不足点**：
- Protocol 只有 4 个方法，**缺少 LPC 的 5 个关键数值维度**：
  1. 无 `combat_exp` 参数（LPC 的防御衰减循环和 AP 线性叠加缺失）；
  2. 无 `jingli` / `jingli_bonus` 参数（精力充沛度加成缺失）；
  3. 无 `skill_level` 参数（立方缩放缺失——`CombatContext` 有属性但无技能等级）；
  4. 无 `busy` / `is_killing` 状态（wound 概率和 dp/pp 削减缺失）；
  5. 无 `jiali` / `jiajin` / `neili` 消耗（内力加成缺失）。
- `CombatContext` 有 `attacker_neili_current` 但 `DefaultWuxiaPowerModel` 完全
  不使用它——**数据携带了但公式没用**。
- `parry_power` 默认等于 `defense_power`（:106-107），**无法表达 LPC 的招架非对称
  规则**（徒手 vs 持械的 pp 翻倍/归零）。

### 8.2 DefaultWuxiaPowerModel 的调参空间

`DefaultWuxiaPowerModel`（:85-113）只有 2 个可调系数：
- `str_factor: float = 0.02`（力量对 AP 的线性系数）
- `dex_factor: float = 1.0`（敏捷对 DP 的线性系数）

**调参空间严重不足**。题材包若想调整：
- 命中率基线 → 无参数可用（只能改 str_factor/dex_factor 间接影响）。
- 伤害缩放曲线 → 无参数（线性公式无法变立方/对数）。
- 精力影响 → 无参数。
- 经验影响 → 无参数。
- 暴击/伤口概率 → **完全没有建模**。

**建议**：`DefaultWuxiaPowerModel` 应至少增加以下可调参数，供题材包在不替换整个
PowerModel 的情况下调整：
- `exp_factor`（combat_exp 对 AP/DP 的线性贡献系数）
- `jingli_factor`（jingli_bonus 系数和上限）
- `skill_power_fn`（可选的技能等级→power 缩放函数，默认线性，可替换为立方/对数）
- `wound_threshold`（伤口触发阈值）
- `busy_penalty`（busy 时 dp/pp 削减比例）

### 8.3 engine 缺失的数值机制

engine 对照 LPC，**完全缺失以下数值机制**：

1. **两层伤害（damage vs wound）**：engine 只有 `qi_current`（`CombatContext`
   :44/49），无 `eff_qi` / `max_qi` 区分。`death_flow.py` 的
   `recovery_vitals_ratio: float = 0.2`（:86）只恢复 qi 到 20%，无 wound 概念。
2. **伤口概率**：LPC 的 `random(damage) > apply/armor` 伤口判定（`combatd.c:680`）
   在 engine 中不存在。
3. **combat_exp 防御衰减**：engine 无 `while random(defense_factor) > combat_exp`
   循环（`combatd.c:636-641`）。
4. **jingli 消耗**：LPC 每次攻击消耗 `jiajin` 精力（`combatd.c:458/508/616`），
   engine 无精力消耗机制。
5. **riposte（反击）**：`combat.py:_invoke_riposte()`（:268-270）是 no-op，LPC 的
   反击逻辑（`combatd.c:766-779`）未实现。
6. **exp_gain**：`combat.py:_invoke_exp_gain()`（:263-265）是 no-op，LPC 的命中/
   被击中获 exp（`combatd.c:441-451/497-501/696-712`）未实现。
7. **双攻/连击**：LPC 的 `double_attack` / `pixie-jian` 双攻
   （`combatd.c:807-814/826-833`）在 engine 中不存在。
8. **guard/防守节奏**：LPC 的 `guarding` temp 和 `random(dex*3) < str*2 + speed`
   攻击/防守判定（`combatd.c:818/837-842`）在 engine 中不存在——engine 每个 tick
   必定攻击。

---

## 9. 综合数值平衡建议

### 9.1 新引擎应保留的 LPC 数值设计

1. **A/(A+B) 概率对抗**（`combatd.c:430`）：简单优雅，保证永远有命中/闪避可能。
   engine 已保留（`combat.py:_roll_opposed`）。
2. **两层伤害模型**（damage vs wound）：制造累积压力感，区分轻伤/重伤。engine
   应补建 `eff_qi` / `max_qi` 层。
3. **combat_exp 防御衰减循环**（`combatd.c:636-641`）：边际递减的防御收益，避免
   高 exp 角色无敌。
4. **jingli_bonus 线性+封顶**（`combatd.c:309-311`）：合理的边际递减模型。
5. **kill vs fight 的伤口概率差异**（`combatd.c:680`）：PvP 比切磋更危险的数值
   根源，应保留。
6. **DeathPolicy 协议化**（`death_flow.py:77-86`）：题材包可声明死亡惩罚参数，
   方向正确。

### 9.2 新引擎应避免的 LPC 数值陷阱

1. **立方缩放**（`level^3/3`）：高等级区间数值爆炸，改用多项式或对数缩放。
2. **6+ 层伤害乘法叠加**（`do_attack` :519-631）：调参不可控，应收敛为 2-3 层。
3. **技能 -1 级死亡惩罚**（`skill_death_penalty`）：毁灭性惩罚，改用经验惩罚
   （engine 已如此）。
4. **Effect duration 递减不统一**：各 condition daemon 自行实现减 duration，
   应建立统一时效引擎。
5. **NPC 伤害加成硬编码**（`combatd.c:523-524`）：应改为可配置的 NPC 数值修正。
6. **无组队战斗加成**（`team.c`）：组队只是移动便利，战斗价值为零——若 MVP 要求
   组队，应引入战斗加成。
7. **wimpy 默认关闭**：新玩家不知道逃跑机制易死亡，应默认开启低阈值 wimpy。
8. **hanbing_damage 的 double-decrement bug**（:26-27 重复减 duration）：
   Effect 引擎统一管理 duration 可避免此类 bug。

### 9.3 PowerModel 的演进方向

engine 的 `PowerModel` Protocol 是正确的抽象方向，但需要：
- 扩展 `CombatContext` 携带 `combat_exp` / `skill_level` / `jingli` / `busy` /
  `is_killing` 状态。
- `DefaultWuxiaPowerModel` 增加可调参数（`exp_factor` / `jingli_factor` /
  `skill_power_fn` 等），提供立方/对数等可选缩放函数。
- 增加 `wound_power` 方法到 Protocol（伤口概率计算），或作为 `base_damage` 的
  可选返回值。
- `parry_power` 不应默认等于 `defense_power`——应允许题材包声明招架的非对称规则。

---

## 10. 证据索引

### LPC 源码
- `feature/damage.c`：receive_damage(:13)/receive_wound(:39)/receive_heal(:68)/
  receive_curing(:85)/unconcious(:105)/revive(:137)/die(:152)/reincarnate(:255)/
  heal_up(:270)
- `feature/attack.c`：MAX_OPPONENT=4(:12)/select_opponent(:79)/attack(:208)/
  kill_ob(:51)/fight_ob(:40)
- `feature/condition.c`：update_condition(:21)/apply_condition(:79)/
  clear_condition(:105)
- `feature/skill.c`：skill_death_penalty(:121)/improve_skill(:149)
- `feature/team.c`：follow_me(:37)/add_team_member(:51)/dismiss_team(:103)
- `feature/equip.c`：wield(:46)/wear(:7)/unequip(:109)
- `adm/daemons/combatd.c`：skill_power(:288)/do_attack(:340)/fight(:787)/
  death_penalty(:987)/killer_reward(:1027)
- `adm/daemons/s_combatd.c`：skill_power(:212)（无 str/dex 封顶的 prototype 版）
- `inherit/char/char.c`：heart_beat(:90-169) wimpy(:124-130)
- `inherit/skill/skill.c`：hit_ob(:142)（武器毒效）
- `inherit/weapon/sword.c`：hit_ob(:24)（护甲磨损）
- `inherit/armor/armor.c`：setup() 重量影响 dodge(:13-15)
- `kungfu/skill/18-zhang.c`：action 数组(:52-218)/query_action(:241)/
  hit_ob 注释(:309)/sanhui(:316)
- `kungfu/condition/bt_poison.c`：update_condition(:7)
- `kungfu/condition/chilian_poison.c`：update_condition(:8)
- `kungfu/condition/hanbing_damage.c`：update_condition(:8)（:26-27 double-decrement bug）
- `kungfu/condition/juehu_damage.c`：update_condition(:10)（apply 削弱 :40-47）
- `kungfu/condition/embedded.c`：update_condition(:9)
- `kungfu/condition/drunk.c`：update_condition(:7)
- `kungfu/condition/blind.c`：update_condition(:11)/let_know(:26)
- `kungfu/condition/pker.c` / `killer.c`：纯计时 condition
- `d/death/gate.c`：init() 物品清除(:26-48)
- `d/death/death.c`：block_cmd(:30)
- `clone/npc/suicong3.c`：NPC 数值(:30-49)
- `clone/npc/shan.c`：NPC 数值(:64-79)
- `include/combat.h`：TYPE_REGULAR/RIPOSTE/QUICK(:7-9)
- `include/condition.h`：CND_CONTINUE/NO_HEAL_UP(:5-6)

### engine 模块
- `engine/src/openmud/combat.py`：PowerModel(:72)/DefaultWuxiaPowerModel(:85)/
  resolve_attack(:132)/_roll_opposed(:219)
- `engine/src/openmud/combat_system.py`：CombatSystem(:70)/try_engage(:93)/
  _DEFAULT_MOVE(:46)
- `engine/src/openmud/death_flow.py`：DeathPolicy(:77)/LootTable(:89)/
  _execute_player_death(:212)/_apply_skill_exp_penalty(:299)
- `engine/src/openmud/skills.py`：SkillBehavior(:60)/DemoPoisonStrikeBehavior(:87)/
  SilkRopeCaptureBehavior(:105)/SkillData(:36)/SkillMove(:23)
