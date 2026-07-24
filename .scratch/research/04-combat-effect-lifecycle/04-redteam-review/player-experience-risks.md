# 红队评审：战斗与效果生命周期簇玩家体验风险

> 角色：玩家体验风险挑战者。任务：在 Phase 1 产出基础上，识别「战斗与效果生命周期簇」中导致玩家流失的关键痛点，并判定哪些保护机制是 MVP/停机加固阶段**必须**实现，而非可选增强。
>
> 质疑对象：`03-engine-insights/player-psychology.md`、`03-engine-insights/numerical-balance.md`、以及 `01-raw-findings/` 与 `02-user-stories/` 中的乐观/中性表述。每条结论均要求标注 LPC 源码或 engine 模块证据。

---

## 核心结论（摘要）

1. **玩家心理评估对「被秒杀 / 命中率挫败」严重度仍偏温和**：`skill_power` 的 `level^3/3` 立方缩放、`random(ap+dp) < dp` 无 cap 的命中模型、被注释掉的伤害上限，叠加 aggressive NPC 的自动 `kill_ob`，使新手在野外可能**进入房间即被秒杀**。这不只是「挫败」，而是典型的 Session 0 流失触发器。
2. **死亡惩罚焦虑被系统性低估**：`death_penalty` 同时削减 combat_exp、potential（减半）、balance（>1w 部分减半）、全技能 -1 级，并触发 `gate.c` 物品全销毁、`break_marriage` 断婚约，且无单日/连续死亡递减。**惩罚不是「沉重但可接受」，而是对中重度玩家的资产与社交投入双重清零。**
3. **中毒 / 被控的「无力感」不是边缘体验，是核心流失源**：`update_condition` 每 5~15 tick 持续扣血，玩家除等待或寻找高门槛 `xidu` 外几乎无自救路径；`blind`、`drunk`、`aphroclisiac`、`city_jail` 等效果直接剥夺行动/社交控制权。该风险不应仅列为「高」，应作为 P0 保护机制输入。
4. **PvP 社交压力 / 围攻 / 霸凌风险在现有评估中覆盖不足**：`MAX_OPPONENT=4` 是**攻击者上限**而非保护，受害者每 tick 仅反击 1 人；`hit` 偷袭、`kill stealing`、复活点无保护期、pker 限制在杀 2 人后才生效，共同构成「老玩家围杀新手 → 反复死亡 → 更弱 → 继续被围杀」的恶性循环。
5. **必须机制（不可后置）**：新手保护期（时间 + 进度双门槛）、单次伤害硬上限防秒杀、死亡惩罚递减 / 日上限 / 被杀保护期、通用负面状态解除路径、PvP 围攻限制与复活保护、默认开启的精简战斗信息。这些不是「体验优化」，而是决定玩家能否度过前 3 小时的留存底线。

---

## 1. 战斗挫败 / 被秒杀 / 命中率随机性——严重度被低估

### 1.1 命中率模型：「永远有 1% 以上 miss」对弱者其实是「永远有接近 100% miss」

`player-psychology.md` §1.1 指出 `random(ap+dp) < dp` 使「弱者总有翻盘希望」，但同时承认「高技能玩家对低技能玩家命中率趋近 100%，低技能玩家对高技能玩家命中率趋近 0」——这一负面效应被正面表述稀释。

证据：

- `adm/daemons/combatd.c:430`：`if (random(ap + dp) < dp) ...` 闪避判定；`ap`、`dp` 下限为 1，因此极端差下命中率可无限接近 0%。
- `adm/daemons/combatd.c:317`：`power = (level * level * level) / 3`，等级差 2 倍则战力差 8 倍，命中概率被立方放大。
- `adm/daemons/s_combatd.c:530-533`：伤害硬上限被注释掉，开发者明确留下注释 "Seems need not this now"，意味着高战力 NPC 可一刀致命。
- `feature/attack.c:254-257`：`attitude == "aggressive"` 的 NPC 对进入房间的玩家直接触发 `auto_fight` → `kill_ob`。

玩家体验：新手刚出新手村，进入有 aggressive NPC 的房间，还未输入任何指令即被自动开战；由于命中概率被碾压，自己攻击几乎全 miss，而 NPC 单招伤害可超过玩家 max_qi。**这不是「翻盘希望」，是无力反抗的负反馈循环。**

### 1.2 伤害方差与秒杀：缺乏硬上限是致命设计

`player-psychology.md` §1.2 描述伤害多层随机为「上一刀刮痧、这一刀暴毙」，但仅列为「破坏节奏感」。红队认为：在文本 MUD 中玩家没有帧级闪避/格挡操作，**单次伤害若可超过 max_qi，则玩家没有第二次反应机会**，等同于黑屏死亡。

证据：

- `adm/daemons/combatd.c:519-631`：基础伤害 + 招式加成 + 力量 + 内功 hit_ob + 武功 hit_ob + 武器 hit_ob + jiajin + 随机，多层叠加。
- `adm/daemons/s_combatd.c:530-533`：原伤害上限 `damage_bonus > 360` 等逻辑被注释。
- `adm/daemons/combatd.c:636-641`：`defense_factor` 循环只保护高经验者免受低经验者攻击，不保护低经验者免受高经验者秒杀。
- `engine/src/openmud/combat.py:85-113` `DefaultWuxiaPowerModel` 与 `resolve_attack(:132-216)` 无伤害硬上限。

### 1.3 wimpy 默认关闭：新玩家失去唯一逃生阀

`player-psychology.md` §4.4 建议「默认开启温和 wimpy」，但在原始 LPC 中 `wimpy` 默认值为 0，玩家必须主动设置。多数新手根本不知道该机制存在。

证据：

- `inherit/char/char.c:124-130`：仅当 `wimpy_ratio > 0` 且气血低于阈值才自动逃跑。
- `cmds/usr/wimpy.c:17`：wimpy 上限 80%，无默认值强制提示。
- `cmds/std/kill.c:51-53`、`cmds/std/hit.c:71-72`：新手保护仅 `mud_age < 18000`（约 5 小时），对慢节奏 MUD 过短。

**红队挑战**：`player-psychology.md` §8 把「新手保护不足」列为「中高」，应上调为「极高」。5 小时在文本 MUD 中往往只够完成基础引导，新手尚未掌握 wimpy、解毒、逃跑等机制，已可被 aggressive NPC 或老玩家击杀。

---

## 2. 死亡惩罚焦虑——累积压力被严重低估

### 2.1 六重惩罚叠加，且缺少封顶/递减

`player-psychology.md` §2.1 列出六重惩罚，但总结为「极其严厉」后仍建议「新引擎引入死亡惩罚递减/封顶」。红队认为：在 LPC 原始设计中，这些惩罚**没有**封顶/递减，本身就是导致玩家弃游的核心机制，应作为必须修复项而非建议项。

证据：

- `adm/daemons/combatd.c:987-1025` `death_penalty`：
  - `:1001-1011` combat_exp 扣 1%（上限 5000，>50 才扣）。
  - `:1007-1008` potential 直接减半。
  - `:999-1000` shen / behavior_exp 各扣 5%。
  - `:1013-1015` balance > 10000 部分减半。
  - `:1022` `skill_death_penalty()`：所有技能 -1 级，`skill_map` 清空。
- `feature/skill.c:121-147` `skill_death_penalty`：每技能 -1，learned 重置，高等级技能需重新积累 `(level+1)^2` 经验。
- `feature/damage.c:152-253` `die()`：同时触发 `clear_condition`、`death_penalty`、`killer_reward`、`make_corpse`、物品掉落、`break_marriage`、风清扬师徒断裂。

### 2.2 物品全销毁是「劝退级」惩罚

`player-psychology.md` §2.2 正确指出 `gate.c` 销毁全部物品，但低估了其对中重度玩家的打击：LPC 中装备获取周期长，且 `death_penalty` 中的 balance 惩罚已扣钱，**死亡 = 钱扣半 + 装备清零 + 技能降级**。

证据：

- `d/death/gate.c:32-36`：`inv = all_inventory(me); for(...) destruct(inv[i]);` 所有非角色物品销毁。
- `adm/daemons/combatd.c:1013-1015`：存款超过 1w 部分对半扣。
- `feature/damage.c:249`：`MARRY_D->break_marriage(this_object())` 死亡断婚约。

### 2.3 死亡次数 `death_times` 逻辑反向，无法形成保护

`numerical-balance.md` §6.1 指出 `death_times` 阈值递增（`combat_exp >= 10000 * death_times`），但 `death_times` 本身并不用于减轻惩罚，**反而让老玩家更容易触发 death_times++**。红队认为这进一步说明 LPC 的死亡惩罚设计未考虑保护机制。

证据：

- `adm/daemons/combatd.c:997-998`：`if (combat_exp >= 10000 * death_times) death_times++;`。
- 同函数中 `death_times` 不参与任何惩罚减免计算。

### 2.4 engine 的 DeathPolicy 仍不足以防恶性循环

`player-psychology.md` §7.1 表扬 engine `DeathPolicy` 默认 10% 惩罚很温和，但红队指出：engine 同样**无单日死亡上限、无连续死亡递减、无被杀保护期**，10% 统一比例在反复被杀时仍会快速掏空玩家资产。

证据：

- `engine/src/openmud/death_flow.py:77-86` `DeathPolicy`：仅 `penalty_ratio: float = 0.1`，无 `daily_cap`、无 `death_streak_decay`、无 `respawn_protection`。
- `engine/src/openmud/death_flow.py:291-305`：货币与技能经验均按统一比例扣减。

---

## 3. 中毒 / 被控无力感——核心风险被边缘化

### 3.1 持续掉血：玩家只能被动观看

`player-psychology.md` §3.1 正确描述毒的无力感，但仅列为「高」风险。红队认为：在 LPC 中，中毒后玩家**没有通用解毒手段**，多数毒只能等待自然衰减或寻找高门槛他人帮助，属于「等死」体验，应作为 P0 风险。

证据：

- `kungfu/condition/bt_poison.c:33-34`：每 tick `receive_wound("jing", damage/2)` + `receive_damage("jingli", damage/2)`。
- `kungfu/condition/hanbing_damage.c:23-24`：每 tick `receive_damage("qi", duration/2+20)` + `receive_wound("jing", ...)`，duration 越长伤害越高。
- `feature/condition.c:21-69` `update_condition`：由 `heart_beat` 每 `5+random(10)` tick 驱动，玩家无法主动加速或阻止。
- `kungfu/skill/wudu-xinfa/xidu.c`：解毒要求五毒心法 >= 70、内力 >= 150、自己未中毒、非战斗中——门槛极高。

### 3.2 控制效果直接剥夺行动/社交权

`player-psychology.md` §3.2 列举了 `blind`、`drunk`、`aphroclisiac`、`city_jail`，但未充分强调这些效果在公共区域对玩家社交形象的破坏（如春药强制 emote），以及牢狱效果强制禁闭。

证据：

- `kungfu/condition/aphroclisiac.c:35-43`：每 tick 扫描房间并对可见活物触发 emote，玩家角色行为被劫持。
- `kungfu/condition/drunk.c:11-14`：duration 超过阈值直接触发 `unconcious()`。
- `kungfu/condition/city_jail.c:9-14`：到期 `me->move("/d/city/yamen")` 并改 `startroom`。
- `kungfu/condition/blind.c:26-35`：通过 `let_know` 恢复攻防，期间战斗力大幅下降。

### 3.3 `CND_NO_HEAL_UP` 预留未用，抑制回血机制缺位

`mechanisms.md` §3.2 与 `system-stories.md` §2.1 均指出 `CND_NO_HEAL_UP` 位定义了但全仓无实现。红队认为：这意味着 LPC 设计师意识到「中毒期间应无法自然回血」但未完成，现代引擎必须补上，否则中毒+自然回血会稀释负面体验的紧张感。

证据：

- `include/condition.h:6`：`#define CND_NO_HEAL_UP 2`。
- `feature/condition.c:62-64`：仅检查 `CND_CONTINUE`，`CND_NO_HEAL_UP` 未在任何 condition daemon 中返回。
- `inherit/char/char.c:149`：`cnd_flag & CND_NO_HEAL_UP` 检查存在但无实际输入。

### 3.4 engine 完全缺失 Effect 引擎，风险放大

`player-psychology.md` §7.2 与 `engine-comparison.md` 模块 3 均指出：engine `conditions.py` 是布尔求值器，不是 LPC 的时效 Effect 引擎。红队强调：这意味着现代引擎当前**没有任何机制来处理毒、盲、醉、牢狱等效果**，如果按现状上线，玩家将完全不会中毒/被控，战斗体验扁平化；如果匆忙实现而无保护，则会复刻 LPC 的「等死」体验。

证据：

- `engine/src/openmud/conditions.py:92-142`：仅 `Predicate/Equals/Gte/And/Or/Not` 布尔节点。
- `engine/src/openmud/skills.py:87-102` `DemoPoisonStrikeBehavior`：仅命中瞬时 +5 伤害，不挂任何持续 Effect。
- `engine/src/openmud/combat_system.py:227-245` `apply_combat_result`：只写 `qi_current`，无 Effect 挂载点。

---

## 4. PvP 社交压力 / 围攻 / 霸凌——评估覆盖不足

### 4.1 MAX_OPPONENT=4 是攻击者上限，不是保护

`player-psychology.md` §5.1 正确指出 4v1 的碾压，但 `gameplay-slices.md` §6 与 `mechanisms.md` §1.2 仍将其描述为「围攻的隐式平衡阀」。红队认为：这个上限**只限制受害者反击目标数**，不限制攻击者人数；每名攻击者独立 tick，受害者每秒最多承受 4 次独立命中判定，而自己只能反击 1 次。**这是霸凌机制而非平衡。**

证据：

- `feature/attack.c:12`：`#define MAX_OPPONENT 4`。
- `feature/attack.c:79-88` `select_opponent`：`which = random(MAX_OPPONENT)`，从 enemy 列表随机挑一个反击。
- `adm/daemons/combatd.c:787-845` `fight`：每个攻击者独立调用，被围攻者无额外减伤/格挡增益。
- `engine/src/openmud/combat_system.py:692-698` `Engaged`：当前 engine 甚至只支持 1v1，未来若扩展到多对手，必须对围攻方做伤害递减或人数上限。

### 4.2 偷袭 / 抢怪 / 复活点围堵

`player-psychology.md` §5.3–5.5 提到 `hit` 偷袭与 kill stealing，但认为「有但不足」。红队认为：这些机制组合起来，对新手是**可随时发生的非自愿 PvP**，且无有效反制。

证据：

- `cmds/std/hit.c:45,88-98`：`hit` 限玩家间，异步 1 秒后双方互换一招，对方反应时间极短。
- `cmds/std/kill.c:51-53`：pker > 240 才禁止 kill，意味着前 2 次 PK 杀人无累计阻碍。
- `adm/daemons/combatd.c:1047,1089`：城内杀人挂 `killer` 100 tick / `pker` +120，但 `hit` 偷袭不触发 pker 累积。
- `adm/daemons/combatd.c:1027-1096` `killer_reward`：奖励归最后一击者，`free_rider` 仅防止对昏迷 NPC 抢怪，对正常战斗中的 NPC 无保护。
- `feature/damage.c:255-264` `reincarnate`：复活满血但无保护期，复活点 `/d/city/wumiao` 一出安全区即可再次被杀。

### 4.3 自动敌对触发：玩家「路过即开战」

`player-psychology.md` §5.2 指出 hat/vendetta/aggressive 不经同意，但红队强调：在野外，玩家可能只是换房间探索，就被 aggressive NPC 或世仇 NPC 自动开战。这与主动选择 PvP 不同，属于**环境强加的失控**。

证据：

- `feature/attack.c:229-258` `init`：按 `is_killing` / `vendetta_mark` / `attitude == "aggressive"` 自动触发 `COMBAT_D->auto_fight`。
- `adm/daemons/combatd.c:852-867` `auto_fight`：`call_out("start_"+type, 0, ...)` 给 0 秒延迟，基本即开战。
- `adm/daemons/combatd.c:855`：NPC 不互打，只打玩家。

### 4.4 engine 当前无 PvP 保护机制

`player-psychology.md` §7.1 列出 engine 缺失：新手保护期、被杀保护期、连续死亡递减、反 PK 累积。红队认为这些缺失意味着 engine 若直接支持 PvP，将完全复刻 LPC 的霸凌环境。

证据：

- `engine/src/openmud/combat_system.py:93-114` `try_engage`：无 `mud_age`、无 `pker`、无区域法律检查。
- `engine/src/openmud/death_flow.py:212-270` `_execute_player_death`：无 `killer_reward`、无 PKS/MKS、无 pker condition。
- `engine/src/openmud/components.py:524` `NoDeathZone`：仅有安全区，无「城市内杀人触发通缉」等 PvP 法律层。

---

## 5. 必须的保护机制——优先级排序

以下机制不是「可选优化」，而是玩家能否在首次死亡 / 首次中毒 / 首次被围攻后仍留下来的**体验底线**。按优先级从高到低排列。

### P0-1：扩展新手保护期（时间 + 进度双门槛）

- **必须理由**：LPC 的 `mud_age < 18000`（约 5 小时）对慢节奏 MUD 过短；`player-psychology.md` §6.1 已建议扩展，红队要求作为**必须**。
- **实现方向**：除时间外，增加「完成新手任务链 / 离开新手村 / 达到某等级」等进度门槛；在此期间免 PK、免 aggressive NPC 自动攻击、免 `hit` 偷袭。
- **证据**：`cmds/std/kill.c:51-53`、`cmds/std/hit.c:71-72`；`feature/attack.c:254-257` aggressive NPC。

### P0-2：单次伤害硬上限（防秒杀）

- **必须理由**：无上限时高战力 NPC/玩家可一击致命，玩家无反应窗口。`player-psychology.md` §6.4 建议硬上限，红队要求**必须**。
- **实现方向**：单次伤害不超过目标 max_qi 的某个比例（如 50%~60%），或不超过 attacker 自身 max_qi 的倍数；同时适用于 PvE 与 PvP。
- **证据**：`adm/daemons/s_combatd.c:530-533` 上限被注释；`adm/daemons/combatd.c:519-631` 多层叠加无封顶；`engine/src/openmud/combat.py:132-216` 无上限。

### P0-3：死亡惩罚递减 / 日上限 / 被杀保护期

- **必须理由**：避免「死亡 → 变弱 → 更易死」的恶性循环。`player-psychology.md` §6.2–6.3 建议，红队要求**必须**。
- **实现方向**：
  - 单日死亡惩罚上限（如最多扣 X%）。
  - 连续死亡后惩罚递减（第 3 次起减半）。
  - 被杀后 N 分钟内不可被攻击 / 不可攻击他人，让玩家喘息、整理装备。
- **证据**：`adm/daemons/combatd.c:987-1025` `death_penalty` 无封顶；`feature/damage.c:255-264` `reincarnate` 无保护期；`engine/src/openmud/death_flow.py:77-86` `DeathPolicy` 无相关字段。

### P0-4：负面状态可解除路径（通用解毒 / 驱散 / 医师 NPC）

- **必须理由**：当前 LPC 中多数毒/控状态无低门槛解除路径，玩家只能等死。`player-psychology.md` §6.5 建议，红队要求**必须**。
- **实现方向**：
  - 每种负面 Effect 至少一条普通玩家可执行解除路径：通用解毒药、城镇医师 NPC、时间自然消退有上限。
  - Effect 系统必须支持 `dispellable` 标志与来源归属，便于「解药只解某类毒」「驱散只驱散敌人的 buff」。
- **证据**：`kungfu/condition/bt_poison.c:36-38` 仅毒抗技能可加速；`kungfu/skill/wudu-xinfa/xidu.c` 解毒门槛极高；`feature/condition.c:79-85` 无去重/无来源；`engine-comparison.md` 模块 3 Effect 引擎整体缺失。

### P0-5：PvP 围攻限制与复活保护

- **必须理由**：`MAX_OPPONENT=4` 对受害者是 4:1 的火力碾压。`player-psychology.md` §6.7 建议，红队要求**必须**。
- **实现方向**：
  - PvP 场景下同一玩家最多同时被 2 名玩家攻击，或围攻方每人伤害递减（人海惩罚）。
  - 复活后保护期（见 P0-3）。
  - 复活点 / 安全区出界后短时间内仍受保护。
- **证据**：`feature/attack.c:12,79-88`；`feature/damage.c:247` 复活点 `/d/city/wumiao`；`adm/daemons/combatd.c:1027-1096` 无围攻限制。

### P1：战斗信息可读性（默认精简 + 结构化状态条）

- **必须理由**：默认全量文本在 4v4 混战时可达每秒 8~16 行，新手无法提取关键信息。`player-psychology.md` §6.6 建议，红队认为应默认开启。
- **实现方向**：默认启用精简战斗描述；以血条百分比、Effect 图标/倒计时等结构化形式呈现状态。
- **证据**：`adm/daemons/combatd.c:71-204` `damage_msg` 多档文案；`combatd.c:278-284` `report_status` 文本播报；`s_combatd.c:308-311` `brief` 模式默认关闭。

---

## 6. 对现有评估的显性质疑

| 被质疑文件 | 原表述 | 红队质疑 |
|-----------|--------|---------|
| `player-psychology.md` §8 | 「被秒杀」「死亡惩罚过重」为「极高」，其余多为「高/中」 | 同意前两项为极高，但认为「中毒等死」「被围攻 4v1」「新手保护不足」也应上调为「极高」，而非「高」或「中高」。 |
| `player-psychology.md` §6.1 | 新手保护期扩展为「建议」 | 应作为**必须**（P0-1），无新手保护则后续所有保护都失去意义。 |
| `player-psychology.md` §6.4 | 伤害硬上限为「建议」 | 应作为**必须**（P0-2），无上限则任何保护机制都可能被单次秒杀击穿。 |
| `gameplay-slices.md` §6 / `mechanisms.md` §1.2 | 称 `MAX_OPPONENT=4` 为「围攻的隐式平衡阀」 | 该上限限制的是受害者反击数，不是攻击者数，应定性为「霸凌温床」而非「平衡阀」。 |
| `numerical-balance.md` §6.1 | 称 combat_exp 1% 惩罚「过轻」 | 红队认为该评估忽略了 potential 减半、技能 -1 级、物品销毁、婚姻断裂的叠加效应，综合惩罚已远超现代玩家承受阈值。 |
| `player-psychology.md` §3.1–3.2 | 将中毒/被控列为「高」风险 | 应作为 P0 风险，因为玩家在中毒后缺乏可执行应对路径，直接触发「失控 → 等死」的流失模式。 |

---

## 7. 证据索引

### LPC 源码

- 命中 / 伤害 / 秒杀：`adm/daemons/combatd.c:317`, `:430`, `:519-631`, `:636-641`, `:680`, `:766-779`, `:787-845`, `:987-1025`, `:1027-1096`；`adm/daemons/s_combatd.c:212-245`, `:294-633`, `:377`, `:422`, `:451-538`, `:530-533`, `:541-545`, `:665-678`, `:686-743`, `:765-795`, `:797-817`, `:835-849`, `:852-867`, `:874-907`, `:910-972`；`feature/damage.c:13-66`, `:105-264`, `:270-331`；`feature/attack.c:12`, `:15-16`, `:40-62`, `:64-88`, `:112-136`, `:208-224`, `:229-258`；`inherit/char/char.c:60-169`, `:181-186`。
- Effect / 中毒 / 被控：`feature/condition.c:8`, `:21-69`, `:79-113`；`include/condition.h:5-6`；`kungfu/condition/bt_poison.c:7-42`, `:33-38`；`kungfu/condition/hanbing_damage.c:8-31`, `:23-27`；`kungfu/condition/blind.c:11-35`；`kungfu/condition/drunk.c:6-35`；`kungfu/condition/aphroclisiac.c:35-43`；`kungfu/condition/city_jail.c:6-24`；`kungfu/condition/embedded.c:9-33`；`kungfu/skill/wudu-xinfa/xidu.c`。
- PvP / 围攻 / 偷袭：`cmds/std/kill.c:9-88`, `:51-53`, `:69-85`；`cmds/std/hit.c:9-98`, `:45`, `:71-72`, `:88-98`；`feature/team.c:28-49`, `:103-122`；`d/death/inn1.c:67-83`；`d/death/gate.c:26-48`。

### engine 模块

- 战斗：`engine/src/openmud/combat.py:22-30`, `:60-70`, `:72-113`, `:132-216`, `:219-224`, `:236-278`；`engine/src/openmud/combat_system.py:41-43`, `:70`, `:77-90`, `:93-114`, `:134-165`, `:198-224`, `:227-245`, `:248-273`, `:276-301`, `:692-698`。
- Effect 缺失：`engine/src/openmud/conditions.py:1-22`, `:92-142`；`engine/src/openmud/skills.py:59-67`, `:87-102`, `:105-137`。
- 死亡：`engine/src/openmud/death.py:21-43`；`engine/src/openmud/death_flow.py:43-45`, `:48-74`, `:77-86`, `:89-97`, `:118-137`, `:171-270`, `:283-305`, `:308-336`, `:339-408`, `:411-429`。

---

## 8. 结论

LPC 战斗/Effect/死亡簇的玩家体验设计是**惩罚导向远大于保护导向**。Phase 1 的玩家心理评估已经识别了大部分风险，但红队认为其对以下几点的严重度仍偏温和：

1. 新手期被 aggressive NPC / 高战力玩家秒杀的 Session 0 流失风险。
2. 死亡惩罚六重叠加且无封顶/递减导致的「越死越弱」恶性循环。
3. 中毒 / 被控后缺乏可执行解除路径的「等死」无力感。
4. `MAX_OPPONENT=4` 与偷袭 / 抢怪 / 无复活保护共同构成的 PvP 霸凌环境。

因此，新引擎在停机加固阶段**必须**实现：扩展新手保护期、单次伤害硬上限、死亡惩罚递减 / 日上限 / 被杀保护期、通用负面状态解除路径、PvP 围攻限制与复活保护。这些机制不是体验优化，而是决定玩家能否留存到底线。
