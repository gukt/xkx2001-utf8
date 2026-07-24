# 红队评审：战斗与效果生命周期簇 — 数值平衡风险与可利用漏洞

> 角色：数值平衡风险挑战者（红队第 6 路）。任务：在 Phase 1 初稿基础上，对「战斗与效果生命周期簇」发起数值平衡层面的对抗性质疑。每条结论必须标注一手来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名），禁止凭空推断。重点覆盖：伤害公式/命中率/数值缩放崩坏点、MAX_OPPONENT=4 围攻压力、Effect 强度与持续时间、死亡惩罚数值、付费数值红线、engine PowerModel 协议抽象充分性。

---

## 1. 伤害公式/命中率/数值缩放：可被利用的崩坏点

### 1.1 skill_power 立方缩放是高等级区间必然崩坏的根源

**被质疑点**：numerical-balance.md §3.1 已指出 `skill_power()` 使用 `level^3/3`，但只给出 level 100→200 的 8 倍增长示例，未指出在真实 NPC/玩家数值区间内的崩坏阈值。

**红队补充量化**：

- `adm/daemons/combatd.c:skill_power()`（:288-333）中 `power = level^3 / 3`，之后 `AP = (power + combat_exp)/30 * min(str/10 * jingli_bonus/10, 300)`（:321-322）。
- 以 `clone/npc/suicong3.c:37-49` 的 NPC 数值为参照：max_qi=1200, max_jing=1200, max_neili=2000, combat_exp=100000, skills=100。
- 该 NPC 的 skill_power（攻击技能 100，str 约 20，jingli_bonus 取中位 100）≈ (100^3/3 + 100000)/30 * min(20/10*100/10, 300) = (333333+100000)/30 * 20 ≈ 288,889。
- 一个新手玩家（skill=10，combat_exp=100，str=10，jingli_bonus=50）的 DP ≈ (10^3/3 + 100)/30 * min(10/10*50/10, 300) = (333+100)/30 * 5 ≈ 72。
- 闪避概率 = DP/(AP+DP) = 72/(288889+72) ≈ 0.025%；新手对 NPC 命中率反向≈ 99.97%。

**可利用漏洞**：当高技能角色攻击低技能角色时，`random(ap+dp) < dp`（combatd.c:430）虽然理论上保留命中/闪避可能，但 `ap` 与 `dp` 的差距可达 3~4 个数量级，实际变成确定性碾压。numerical-balance.md §2.1 说"永远有命中和闪避可能"，在整数随机数精度下是伪命题。

**反例**：numerical-balance.md §9.1 建议保留 A/(A+B) 模型，但未指出必须加命中率 cap。若不加 5%~95% cap，立方缩放会让高等级角色对低等级角色形成数学上的必中/必闪，破坏 PvP/PvE 弹性。

---

### 1.2 伤害加成 6+ 层乘法叠加的指数放大

**被质疑点**：mechanisms.md §2.1 Step 5 与 numerical-balance.md §1.2 列出伤害链，但未量化多层叠加后的方差与秒杀风险。

**红队量化**：

- `adm/daemons/combatd.c:519-631` 的伤害链：

  1. `damage = apply/damage`，武器基础值（如 sword.c 中 weapon_prop/damage 可由 10~50）。
  2. `damage = (damage + random(damage))/2`（:520）→ 0.5x~1x。
  3. `damage += action["damage"]/10 * damage/30`（:528）→ 18-zhang damage=120 时 +0.4*damage。
  4. `damage += skill/10 * damage/10`（:534）→ skill=100 时 +damage。
  5. `damage_bonus = str + force_hit_ob + action["force"]/10*damage_bonus/100 + skill/4 + force/2 + martial_hit_ob + weapon_hit_ob + jiajin`（:536-617）。
  6. `damage += (damage_bonus + random(damage_bonus))/2`（:628-631）→ 再乘 0.5x~1x。
  7. `combat_exp` 防御衰减循环（:636-641）在高 exp 差下可多次减 1/3。

**崩坏点**：当 `damage_bonus` 叠加到数百时，第 6 步的 `damage += damage_bonus` 会让最终伤害从武器基础值的 1~2 倍暴增至 10~50 倍。numerical-balance.md §1.2 提到"6+ 层乘法叠加"，但未给出具体倍数。

**反例**：`s_combatd.c:530-533` 原本有伤害上限注释 `if(damage_bonus > 360) damage_bonus = 180 + damage_bonus/2`，但被注释掉了。numerical-balance.md §1.3 与 player-psychology.md §1.3 都引用该注释说明开发者意识到风险但未根治，但未指出：无上限时，高力量+高内力+高技能+高加力的玩家/NPC 可对同档目标造成一击必杀。

---

### 1.3 engine DefaultWuxiaPowerModel 线性公式丢失维度且自身也有边界崩坏

**被质疑点**：numerical-balance.md §2.4/§3.5/§8 批评 engine `DefaultWuxiaPowerModel` 线性且维度不足，红队进一步指出其题材包调参空间不足以还原武侠体验，且线性本身也有边界崩坏风险。

**证据**：

- `engine/src/openmud/combat.py:DefaultWuxiaPowerModel`（:85-113）：`attack_power = max(0, int(force * (1 + str * str_factor)))`（:98-100），`str_factor=0.02`；`defense_power = max(0, int(defender_dex * dex_factor + move.dodge))`（:102-104），`dex_factor=1.0`；`parry_power = defense_power`（:106-107）。

**红队反例**：

- 若题材包创作者将 `str_factor` 从 0.02 调到 0.10，则 str=50 时 AP 倍率从 2.0 变成 6.0，线性系数微调会直接放大 str 的边际收益，没有 `level^3` 那种天然天花板。
- `base_damage`（:109-113）在 `move.damage > 0` 时直接返回 `move.damage`，否则返回 `attack_power`。创作者若给招式填 `damage: 9999`，engine 会直接造成 9999 点伤害，无伤害上限校验。numerical-balance.md §8.2 建议增加 `wound_threshold` 等参数，但当前 engine 完全无上限护栏。
- `engine/src/openmud/combat_system.py:apply_combat_result`（:227-245）只写 `vitals.qi_current = max(0, vitals.qi_current - result.damage)`，无 `receive_wound` 等效路径，无两层伤害模型。

---

## 2. PvE vs PvP 数值鸿沟：MAX_OPPONENT=4 与组队围攻压力

### 2.1 MAX_OPPONENT=4 的围攻上限在攻击方与防御方之间不对称

**被质疑点**：gameplay-slices.md §6 / mechanisms.md §1.2 / numerical-balance.md §4.1 都提到 `MAX_OPPONENT=4` 限制被围攻者反击人数，但未量化这种不对称的数值压力。

**红队量化**：

- `feature/attack.c:12 #define MAX_OPPONENT 4`；`select_opponent()`（:79-88）每 tick 只在前 4 个敌人中随机选 1 个反击。
- 若 4 名攻击者围攻 1 名受害者：受害者每 tick 受 4 次独立 `do_attack` 判定（每个攻击者跑自己的 heart_beat 调 `attack()`），但只反击 1 次。
- 每名攻击者独立过 `fight()` 的出击判定：`random(victim_dex*3) < attacker_str*2 + apply/speed`（combatd.c:818）。假设 victim_dex=20，attacker_str=20，apply/speed=0，则攻击方出击概率 = `random(60) < 40` ≈ 66.7%；若 attacker_str=30，则概率 ≈ 83.3%。
- 4 名攻击者同时出击的期望人数 = 4 * 0.667 ≈ 2.67 次/ tick。

**可利用漏洞**：numerical-balance.md §4.1 说"4 人围攻 = 4 倍伤害输出"，但实际是期望 2.67 倍 + 方差。更关键的是：受害者的 DP/PP 在每次被攻击时独立判定，没有"被多人围攻时闪避/招架递减"机制，也没有"围攻方伤害分摊"——4 人围攻时受害者每 tick 的期望受击次数是攻击者人数的线性函数，而反击次数固定为 1。

**反例**：modern-design-review.md §1.3 建议保留 MAX_OPPONENT 的"注意力分散"精神，但 modern-design-review.md §6.2 又建议 PvP 必备 CC 韧性/DR。当前 LPC 与 engine 都没有围攻伤害递减或韧性机制，4v1 在 PvP 中几乎是确定性秒杀。

---

### 2.2 engine 1v1 限制使 LPC 的围攻风险在当前 engine 中不存在，但未来补多对手时风险会复现

**证据**：

- `engine/src/openmud/combat_system.py:try_engage()`（:93-114）严格 1v1：`Engaged` 组件只有单一 `opponent`（components.py:692-698）。
- 这导致 engine 当前没有围攻风险，但也意味着 gameplay-slices.md §6 的"组队围攻"无法运行。

**红队警告**：若 future 按 abstraction-options.md §1.4 方向 B 扩展为 N 对手敌对列表，必须同时引入：

- 被围攻方 DP/PP 随攻击者数量递减；
- 围攻方每人伤害递减（人海惩罚）；
- 否则 LPC 的 4v1 线性碾压会在 engine 复现。

---

### 2.3 PvE 数值鸿沟：NPC combat_exp 对玩家的碾压

**被质疑点**：numerical-balance.md §4.3 已指出 NPC combat_exp 10 万~40 万 vs 新手玩家几百几千的鸿沟，红队补充具体命中/伤害影响。

**量化**：

- `clone/npc/shan.c:64-79`：combat_exp=400000, skills=100-120, max_qi=900。
- 新手玩家 combat_exp=1000, skill=10 时，对 shan 的 AP ≈ (10^3/3 + 1000)/30 * str_factor ≈ 极小；shan 的 DP ≈ (100^3/3 + 400000)/30 * dex_factor ≈ 巨大。
- 玩家命中率 ≈ AP/(AP+DP) 趋近于 0；shan 命中率 ≈ 100%。
- 玩家伤害经过 combat_exp 防御衰减循环（combatd.c:636-641）后，`while random(defense_factor) > my["combat_exp"]` 中 defense_factor=400000 远大于 my.combat_exp=1000，几乎必然触发多次 1/3 衰减，最终伤害可能只剩原始值的 1/9~1/27。

**反例**：这种设计让新手完全无法挑战高 combat_exp NPC，必须按线性进度刷低等级怪。numerical-balance.md §4.3 认为这是"刻意设计"，但未评估其留存风险——player-psychology.md §1.3 指出被秒杀是最强负向情绪触发器。engine 当前因无 combat_exp 轴（engine-comparison.md §1.1e/§6.1f），反而避免了这种碾压，但代价是高低等级区分度不足。

---

## 3. Effect 数值：中毒/被封印/被擒拿的强度与持续时间

### 3.1 毒类 Effect 的数值模型不统一，存在 OP 与废招

**被质疑点**：numerical-balance.md §5.1 已批评毒的伤害公式不统一，红队给出具体强度对比。

**量化对比**：假设玩家 max_qi=1000, max_jing=1000，被挂上 duration=100 的中毒：

- `bt_poison.c`（:33-34）：每 tick `receive_wound("jing", damage/2)` + `receive_damage("jingli", damage/2)`，其中 `damage = duration or 10`（:30-31）=100。每 tick 扣 jing_eff=50 + jingli=50。duration 每次减 `5 + poison_skill/10`（:37-38），无 poison 技能时减 5，100 duration 持续约 20 tick；total jing_eff 损失 ≈ 1000（等于 max_jing）。
- `chilian_poison.c`（:21-22）：每 tick `receive_damage("qi", random(duration)/2+10)` + `receive_wound("jing", random(duration)/2+10)`。duration=100 时随机 10~60，平均 35。每 tick 扣 qi=35 + jing_eff=35，duration 每次 -1（:30），持续 100 tick；total qi 损失 ≈ 3500，jing_eff 损失 ≈ 3500。
- `hanbing_damage.c`（:23-24）：每 tick `receive_damage("qi", duration/2+20)` + `receive_wound("jing", duration/2+20)`。duration=100 时扣 70+70，duration 每次 -1（:26），持续 100 tick；total qi 损失 ≈ 7000，jing_eff 损失 ≈ 7000。

**红队结论**：同样 duration=100，`bt_poison` 总伤约 1000，`chilian_poison` 约 7000，`hanbing_damage` 约 14000——同 duration 不同毒的总伤可差 14 倍。numerical-balance.md §5.1 说"没有统一的 Effect 强度框架"，但未给出量化的不平衡倍数。

**反例**：numerical-balance.md §9.2 建议建立统一模型（如 `damage_per_tick = base + duration * coefficient`），但未指出 LPC 当前三种毒的差异已大到需要立即禁用其中几种的地步。

---

### 3.2 控制类 Effect：juehu_damage 的攻防削减过强且恢复极慢

**被质疑点**：numerical-balance.md §5.2 提到 `juehu_damage.c` 的线性削弱+线性恢复，红队补充其对低等级角色的毁灭性。

**量化**：

- `kungfu/condition/juehu_damage.c:40-47`：每 tick `add_temp("apply/attack", -duration)` + `add_temp("apply/defense", -duration)`，然后每 tick `add_temp(..., +1)` 恢复。
- 若 duration=400，则 attack/defense 各 -400。
- 在 `combatd.c:skill_power()`（:300-302）中 `level = query_skill(skill) + apply/attack`，低等级角色 skill=20 时，-400 attack 会让 level 变为 -380，skill_power 中 `if (level < 1)` 分支（:312-314）返回 `combat_exp/20 * jingli_bonus/10`——AP 从立方区暴跌到线性区。
- 恢复需 400 tick（约 400~800 秒，因为 condition 每 5~15 heart_beat 才更新一次，实际可能更久）。

**红队结论**：numerical-balance.md §5.2 说"-400 对低等级角色是毁灭性的"，但未指出 duration 400 时恢复时间长达数分钟，且期间角色几乎无法命中/闪避。这是"一击废号"级别的控制效果。

**反例**：`blind.c`（:11-35）通过 `cimu_power` temp 削减 apply/attack/defense，duration 到 0 后一次性恢复，比 juehu_damage 温和。两种控制机制差异巨大，说明 LPC 缺乏统一的 CC 强度分级。

---

### 3.3 醉酒的非线性阈值存在极端跳变

**被质疑点**：player-stories.md §US-4 与 mechanisms.md §3.3 提到醉酒三段曲线，红队指出其阈值附近的跳变风险。

**量化**：

- `kungfu/condition/drunk.c:10`：`limit = 3 + con + max_neili/40`。
- 一个 con=15, max_neili=400 的玩家 limit=3+15+10=28。
- duration=27 时（微醺）每 tick `receive_healing("jing",10)+("qi",15)`，回血；duration=28 时（醉酒）扣 jing 10；duration=29 时直接 `unconcious()`（:14）。

**红队结论**：在 limit 阈值附近，duration 从 27→29 会让 Effect 从"回血"跳变到"昏迷"，存在 2 tick 内从正面效果变硬控的极端非线性。numerical-balance.md §5.1 与 player-psychology.md §3.2 提到醉酒可导致昏迷，但未量化阈值附近的跳变幅度。

---

### 3.4 engine 完全缺失 Effect 引擎，无法评估数值风险

**证据**：

- engine-comparison.md §3 明确指出 `engine/src/openmud/conditions.py` 是通用布尔求值器，不是 LPC `feature/condition.c` 的时效性 Effect 引擎。
- engine 中无 `apply_condition`/`update_condition`/`clear_condition` 等效 API。
- `engine/src/openmud/skills.py:DemoPoisonStrikeBehavior`（:87-102）名为毒击，实则只 `damage+5`，不挂持久毒。

**红队结论**：numerical-balance.md §8.3 列出 engine 缺失的数值机制，其中"两层伤害""伤口概率""jingli 消耗"等 8 项都依赖 Effect 引擎。在 Effect 引擎缺失的情况下，所有 Effect 相关的数值平衡风险在当前 engine 中不存在，因为功能不存在；但这也意味着 brief 要求的"中毒持续掉血"等玩法切片无法运行。

---

## 4. 死亡惩罚数值：过苛还是过轻？

### 4.1 LPC 死亡惩罚：对技能等级过苛，对 combat_exp 过轻

**被质疑点**：numerical-balance.md §6.1 已批判 LPC 死亡惩罚"轻 exp 罚 + 重 skill 罚"，红队给出具体比例与等价时间损失。

**量化**：

- `adm/daemons/combatd.c:death_penalty()`（:987-1025）：

  - combat_exp 扣 1%，上限 5000（:1001-1011）。
  - potential 减半（:1007-1008）。
  - balance 超 10000 部分减半（:1013-1015）。
  - shen/behavior_exp 各扣 5%（:999-1000）。
  - `skill_death_penalty()` 所有技能 -1 级（:1022）。

- `feature/skill.c:skill_death_penalty()`（:121-147）：技能 -1 级，`learned` 重置为 `(level+1)^2/2`（:141）。

**等价时间损失**：

- 一个 skill=100 的技能死亡后变 99，重新升到 100 需要积累 `(99+1)^2 = 10000` 经验点（skill.c:176）。
- `combatd.c:698-702` 每次命中/闪避/招架获得的 improve_skill 经验是 `random(int)` 量级，通常 1~10；按每次战斗平均 +3 估算，需要约 3333 次有效战斗动作 才能补回 1 级。
- 相比之下，combat_exp=100000 的玩家死亡只扣 1000（上限 5000），约占 1%~5%，远小于技能等级损失的时间价值。

**红队结论**：numerical-balance.md §6.1 说"技能 -1 级过苛"，但未给出与 combat_exp 惩罚的等价时间对比。技能 -1 级的实际时间成本是 combat_exp 1% 惩罚的数十倍甚至上百倍，惩罚结构严重失衡。

---

### 4.2 engine 单一比例惩罚虽温和，但损失了 LPC 的分项保护

**被质疑点**：numerical-balance.md §6.3 与 commercialization.md §3.2 都指出 engine `DeathPolicy.penalty_ratio` 是统一 10% 比例，红队补充其具体影响。

**量化**：

- `engine/src/openmud/death_flow.py:DeathPolicy`（:77-86）`penalty_ratio: float = 0.1`。
- `_apply_currency_penalty()`（:291-296）：`loss = int(currency.amount * ratio)`，无免税额。
- `_apply_skill_exp_penalty()`（:299-305）：`loss = int(prog.exp * ratio)`，按统一比例扣所有技能经验。

**与 LPC 对比**：

- LPC 的金钱惩罚有 10000 免税额（combatd.c:1013），低收入玩家几乎不受金钱惩罚；engine 对任何金额都扣 10%，新手死亡时可能损失全部货币。
- LPC 的技能惩罚是 -1 级（高等级极痛），engine 是扣 10% 经验（高等级相对温和）。numerical-balance.md §6.3 认为这是更合理的设计，但红队指出：engine 的温和也削弱了死亡威慑，可能让玩家不再重视死亡。

**反例**：player-psychology.md §2 强调 LPC 惩罚过重导致流失；engine 矫枉过正到 10% 统一比例，可能让死亡变成"轻微不便"。需要在"逼退新手"与"无威慑"之间找平衡。

---

### 4.3 死亡惩罚的 death_times 阈值是未完成设计

**被质疑点**：numerical-balance.md §6.1 提到 `death_times` 递增阈值但未深入；gameplay-slices.md §5 也质疑其设计意图。

**证据**：

- `adm/daemons/combatd.c:997-998`：`if (combat_exp >= 10000 * death_times) death_times++`。
- 第一次死亡时若 combat_exp < 10000，death_times 不加；第二次死亡时若 combat_exp < 20000，仍不加。

**红队结论**：numerical-balance.md §6.1 说 death_times 是"未完成的设计"，正确。但红队进一步指出：该阈值逻辑反向保护常死玩家——死亡次数越多，下次涨 death_times 的门槛越高，反而让经常死亡的人更难累积死亡计数。这与"死亡惩罚应随次数递增"的直觉相反。

---

## 5. 付费数值红线：是否清晰可执行？

### 5.1 红线总体清晰，但存在灰色地带

**被质疑点**：numerical-balance.md §7 与 commercialization.md §1/§3 已列出 pay-to-win 红线，红队补充可执行性分析。

**证据**：

- numerical-balance.md §7.1 列出 8 条不可付费影响的数值：combat_exp、技能等级、max_neili/max_jingli、str/dex/con/int、weapon_prop/damage、jiali/jiajin、apply/*、jingli_bonus。
- commercialization.md §1.1/§3.1 进一步细分：经验/潜力/金钱/技能等级损失禁止付费减免；阵营损失可付费保留；便利性（保 skill_map、跳地府迷宫、选复活点）安全。

#### 5.1.1 灰色地带：死亡不掉落物品的付费

- `feature/damage.c:226-228` `CHAR_D->make_corpse` 会生成尸体含物品；`d/death/gate.c:33-36` 进鬼门关时销毁所有非角色物品。
- commercialization.md §1.1 判定"付费保留地府入口不被销毁的物品"是红线，因为销毁是死亡惩罚的一部分。
- 但 engine `DeathPolicy.drop_items`（death_flow.py:84）默认 True，若题材包声明 `drop_items: false`，则该题材包内所有玩家死亡都不掉落——这不是付费，而是题材包设计选择。若某付费道具只在特定场景提供"死亡不掉落"，是否红线？numerical-balance.md §7.2 把"背包扩展"列为便利，但未明确"死亡保护卷轴"的边界。

#### 5.1.2 灰色地带：坐骑 speed 的双用途

- numerical-balance.md §7.3 与 commercialization.md §1.1 都警告 `apply/speed` 同时影响移动与战斗主动性（combatd.c:766/818）。
- 若付费坐骑只提升"移动 speed"而不提升"战斗 speed"，技术上需要 engine 将两种 speed 分离。当前 engine `DefaultWuxiaPowerModel` 无 speed 参数（combat.py:85-113），`move.dodge` 被当成 DP 的一部分，但没有独立的"移动 speed"字段。commercialization.md §1.1 说"必须分离"，但 engine 当前无法分离。

---

### 5.2 engine 缺乏付费红线的技术护栏

**证据**：

- `engine/src/openmud/death_flow.py:DeathPolicy`（:77-86）只有 6 个字段，无 `paid_mitigations` 或 `currency_type` 标记。
- `engine/src/openmud/components.py:Currency`（:650）是单一 `amount: int`，无货币类型区分（commercialization.md §5.1 指出这是最大缺口）。
- `engine/src/openmud/skills.py:SkillData`（:36-53）无 `pack_id`/`creator_id`/`version` 字段（commercialization.md §2.2/§5.2）。

**红队结论**：numerical-balance.md §7 列出红线，但 engine 当前数据结构无法强制执行。例如：

- 无法区分"免费金币"与"premium 点数"，无法防止"用 premium 买死亡惩罚减免"；
- 无法追溯武功/装备/Effect 的题材包来源，无法做创作者分成；
- `penalty_ratio` 是单一 float，创作者填 2.0 会扣 200% 货币，`_apply_currency_penalty:296` 用 `max(0,...)` 兜底但静默（ugc-surface.md §6.1 已指出）。

---

## 6. engine PowerModel 协议的数值抽象是否充分？

### 6.1 Protocol 缺失 5 个关键数值维度

**被质疑点**：numerical-balance.md §8.1 已列出 5 个缺失维度，红队补充其对题材包调参的具体影响。

**证据**：

- `engine/src/openmud/combat.py:PowerModel`（:72-83）只有 4 个方法：`attack_power`/`defense_power`/`parry_power`/`base_damage`。
- `CombatContext`（:33-56）有 `attacker_neili_current` 等字段，但 `DefaultWuxiaPowerModel` 完全不用它（numerical-balance.md §8.1）。

**具体缺失影响**：

1. 无 combat_exp：无法表达"老手对新手的高命中率"与"经验削伤"（LPC combatd.c:636-641）。
2. 无 jingli / jingli_bonus：无法表达"精力充沛时的战斗优势"（LPC combatd.c:309-311）。
3. 无 skill_level：`CombatContext`（:50）只有属性无技能等级，立方/对数缩放无从谈起。
4. 无 busy / is_killing 状态：wound 概率（combatd.c:680）与 dp/pp 削减（combatd.c:419/482）无法表达。
5. 无 jiali / jiajin / neili 消耗：内力加成（combatd.c:539）与精力加成（combatd.c:606-617）缺失。

---

### 6.2 DefaultWuxiaPowerModel 调参空间严重不足

**被质疑点**：numerical-balance.md §8.2 建议增加 5 个可调参数，红队进一步指出当前 2 个系数无法支撑平衡迭代。

**证据**：

- `engine/src/openmud/combat.py:DefaultWuxiaPowerModel`（:85-113）只有 `str_factor: float = 0.02` 和 `dex_factor: float = 1.0`。

**红队反例**：

- 若题材包想调整"命中率基线"，无参数可用，只能改 `str_factor` 或 `dex_factor`，但这会同时改变 AP 和 DP 的相对强度。
- 若题材包想做"暴击"，Protocol 完全无 `crit_rate`/`crit_damage` 方法，必须整体替换 PowerModel。
- 若题材包想做"护甲减伤"，Protocol 无 wound/armor 相关方法，engine 当前 `apply_combat_result` 直接扣 qi_current，无护甲介入点。

**红队建议**：numerical-balance.md §9.3 建议扩展 `CombatContext` 与增加 `wound_power` 方法，红队进一步建议：

- 增加 `crit_power(ctx) -> CritResult` 方法；
- 增加 `wound_power(ctx, raw_damage) -> WoundResult` 方法；
- 将 `parry_power` 默认不等于 `defense_power`，允许题材包声明招架非对称规则（徒手 vs 持械）；
- `base_damage` 应接收 `move.damage_type` 并支持多资源路由（jing/qi/jingli）。

---

### 6.3 engine 数值抽象 missing 的根本原因是把 LPC 的三层模型压成一层

**被质疑点**：engine-comparison.md §1.1a/b 与 numerical-balance.md §1.1 都指出 engine 把 LPC 的三类伤害/两层血量压成单一 qi_current，红队从数值平衡角度评估其影响。

**证据**：

- LPC：`feature/damage.c:13-66` 三类伤害（jing/qi/jingli）+ 两层（current/eff）。
- engine：`engine/src/openmud/components.py:459-468` `Vitals` 只有 `qi_current`/`qi_max`/`neili_current`/`neili_max`/`jingli_current`/`jingli_max`；`combat_system.py:240` 只扣 `qi_current`。

**红队结论**：

- 压成一层后，engine 无法表达"内伤降上限"（wound）与"中毒耗精"（jing/jingli damage）的数值纵深。
- 对 PowerModel 而言，由于伤害只扣单一资源，`damage_type`（combat.py:28）只是文案标签，无法像 LPC 那样按类型路由到不同资源池。
- 对付费红线而言，由于无多层资源，付费道具若提供"内力恢复"会直接影响 combat 续航，但因无 jingli 消耗机制，该恢复无法被战斗系统消费。

---

## 7. 综合风险优先级

| 风险 | 严重度 | 可利用性 | 来源 | 对 engine 的影响 |
|------|--------|----------|------|------------------|
| skill_power 立方缩放导致高等级碾压 | 极高 | 无需利用，系统自带 | combatd.c:317; numerical-balance.md §3.1 | engine 已避免（线性公式），但丢失武侠纵深 |
| 伤害 6+ 层叠加无上限导致秒杀 | 极高 | 高 | combatd.c:519-631; s_combatd.c:530-533 | engine 线性公式+无上限校验，风险从"立方"变"线性系数失控" |
| MAX_OPPONENT=4 围攻 4v1 碾压 | 高 | 高 | attack.c:12,79-88; combatd.c:818 | engine 当前 1v1 无风险，未来补多对手时必须同步加围攻惩罚 |
| Effect 毒/控制强度差异 14 倍 | 高 | 中 | bt_poison.c; chilian_poison.c; hanbing_damage.c; juehu_damage.c | engine 无 Effect 引擎，风险不存在但功能缺失 |
| 技能 -1 级死亡惩罚过苛 | 高 | 中 | combatd.c:987-1025; skill.c:121-147 | engine 改为扣 10% 经验，过轻可能削弱威慑 |
| 付费红线缺乏技术护栏 | 中高 | 中 | death_flow.py:77-86; components.py:650 | engine 无法强制执行红线，依赖题材包自觉 |
| PowerModel 缺少 5 个维度 | 中 | 低 | combat.py:72-83; numerical-balance.md §8.1 | 题材包调参空间不足，难以还原武侠体验 |

---

## 8. 给评审委员会的未决问题

1. **skill_power 缩放曲线**：新引擎是否应完全丢弃立方缩放（modern-design-review.md §6.3 建议丢弃），还是保留为 `PowerModel` 的可选缩放函数之一？
2. **MAX_OPPONENT=4 的未来**：若 engine 扩展多对手，围攻惩罚（伤害递减/防御递减）是否应作为 engine 不变量，还是下放题材包？
3. **Effect 引擎优先级**：Effect 引擎当前缺失（ADR-0007 延期），但 commercialization.md 与 creator-perspective.md 都指出它是题材包差异化的核心。是否应在 M3 停机加固期至少预留声明式 Effect schema？
4. **死亡惩罚模型**：engine 当前 10% 统一比例是否过轻？是否应恢复 LPC 的分项惩罚但改为可配置（如 `DeathPolicy` 支持 per-stat penalty_ratio）？
5. **付费红线护栏**：是否应在 `Currency`/`SkillData`/`DeathPolicy` 中强制加入 `currency_type`/`pack_id`/mitigation 白名单，否则商业化无法落地？

---

## 9. 证据索引

### LPC 源码

- `adm/daemons/combatd.c:288-333` skill_power 公式
- `adm/daemons/combatd.c:340-780` do_attack 七步结算
- `adm/daemons/combatd.c:787-845` fight 出击判定
- `adm/daemons/combatd.c:987-1025` death_penalty
- `adm/daemons/s_combatd.c:530-533` 被注释的伤害上限
- `feature/attack.c:12,79-88` MAX_OPPONENT=4 / select_opponent
- `feature/damage.c:13-66` receive_damage / receive_wound
- `feature/skill.c:121-147,149-182` skill_death_penalty / improve_skill
- `kungfu/condition/bt_poison.c:7-42` 西域灵蛇毒
- `kungfu/condition/chilian_poison.c:7-31` 赤炼掌毒
- `kungfu/condition/hanbing_damage.c:8-31` 寒冰绵掌阴毒
- `kungfu/condition/juehu_damage.c:10-63` 绝户伤害
- `kungfu/condition/drunk.c:6-35` 醉酒
- `clone/npc/suicong3.c:37-49` NPC 数值
- `clone/npc/shan.c:64-79` NPC 数值

### engine 模块

- `engine/src/openmud/combat.py:72-83` PowerModel Protocol
- `engine/src/openmud/combat.py:85-113` DefaultWuxiaPowerModel
- `engine/src/openmud/combat.py:132-216` resolve_attack
- `engine/src/openmud/combat_system.py:93-114` try_engage
- `engine/src/openmud/combat_system.py:227-245` apply_combat_result
- `engine/src/openmud/death_flow.py:77-86` DeathPolicy
- `engine/src/openmud/death_flow.py:291-305` 惩罚应用
- `engine/src/openmud/components.py:650` Currency
- `engine/src/openmud/skills.py:36-53` SkillData
