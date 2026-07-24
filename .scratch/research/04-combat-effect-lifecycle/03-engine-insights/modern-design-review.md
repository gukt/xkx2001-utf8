# 现代战斗玩法评审：LPC 战斗与效果生命周期簇 vs 当代游戏

> 角色产出：现代战斗玩法设计师（`03-engine-insights/modern-design-review.md`）
> 对标对象：现代 MMO（WoW/FF14）、动作战斗（魂系/原神动作）、手游回合/即时（星铁/明日方舟/Genshin）、MOBA（LoL/Dota2）。
> 证据原则：每条结论标注 LPC 文件路径 + 函数/对象名（行号）。LPC 是唯一真相源；engine 模块不作为反向脑补来源。
> 本评审止步于"设计输入层"，不输出 engine 接口草案（见 brief §1.4）。

---

## 0. 评审方法论与对标坐标系

本评审采用"双轴对标"：

- **机制轴**：把 LPC 的每条战斗机制拆成可比较的设计维度（节奏、命中、伤害、状态、死亡、招式），对照当代主流品类在该维度上的成熟解法。
- **时代风险轴**：对每条机制判定三档——
  - `保留`（LPC 设计在文本 MUD 语境下有当代不可替代的价值，值得新引擎继承精神）；
  - `现代化`（机制本身有价值但实现过时，需用当代解法重做）；
  - `丢弃`（与当代玩家习惯/商业化根本冲突，新引擎不应继承）。

需要前置说明的是：LPC 战斗是**纯文本、服务端权威、tick 驱动**的回合制-自动战斗混合体——玩家下达 `kill`/`fight` 后，战斗由 `heart_beat()` 自动推进，玩家不逐招操作，而是通过"战前配招 + 战中触发招式随机选择 + 被动技能 hook"参与。这与现代任何品类都不同构，因此对标时关注的是**设计意图与玩家体验**，而非"逐键手感"。

---

## 1. 战斗节奏：heart_beat tick 驱动 + MAX_OPPONENT=4

### 1.1 LPC 实现

- 战斗由 `inherit/char/char.c:60 heart_beat()` 驱动，每个 heart_beat 周期执行一次（MudOS 驱动默认周期约 2 秒，属驱动级配置，非 LPC 源码常量；源码侧表现为 `char.c:53 set_heart_beat(1)` 开启、`char.c:157 set_heart_beat(0)` 关闭）。
- 每个 heart_beat 内，若在战斗中调用 `feature/attack.c:208 attack()`，它经 `attack.c:79-88 select_opponent()` 选定**单一目标**——`which = random(MAX_OPPONENT)`，`MAX_OPPONENT=4`（`attack.c:12`）。即使 `enemy` 列表多于 4 人，本 tick 也只随机挑一个攻击（`attack.c:85-87`）。
- 是否真的出击还要过一道闸：`adm/daemons/combatd.c:818 fight()` 中 `random(victim->query_dex()*3) < me->query_str()*2 + apply/speed` 才发动 `TYPE_REGULAR` 攻击，否则进入 `guarding`（仅观望，`combatd.c:837-842`）。即一个 tick 内可能"什么都不做"。
- 多打一/围攻：`feature/attack.c:15 static object *enemy`，多名攻击者各自独立 tick 攻击同一目标，但单角色单 tick 只出 1 招（除非 `double_attack`/`pixie-jian` 双招特例，`combatd.c:807-814`）。
- 状态更新更慢：`char.c:54 tick = 5 + random(10)`，`char.c:141-144` 每 `tick` 个 heart_beat 才调一次 `update_condition()`。即中毒/灼烧等 Effect 的"跳"比普攻慢 5~15 倍。
- 昏迷恢复：`feature/damage.c:134 call_out("revive", random(100 - query("con")) + 30)`——以秒计的随机苏醒窗口，体质 `con` 影响时长。

### 1.2 当代对标

| 品类 | 节奏特征 | 与 LPC 差距 |
|------|----------|-------------|
| 现代 MMO（WoW/FF14） | GCD 1.5~2.5s + 大量瞬发/off-GCD 技能；玩家每个 GCD 都在做决策 | LPC 的 tick ≈ GCD 量级，但玩家**不操作**，节奏"发生"而非"被驱动" |
| 动作/魂系 | 帧级（60FPS），i-frame 闪避、精确格挡窗口 | LPC 无帧概念，节奏完全服务端 tick |
| 手游即时（Genshin） | 实时连段 + 元素反应 + 大招 Burst | LPC 无连段、无即时切人 |
| 手游回合（星铁） | 回合内 100% 玩家掌控 | LPC 是"自动战斗 + 战前配置"，更接近放置类 |

### 1.3 评估

- **`现代化`**：tick 驱动本身在现代仍有生命力（所有回合制/放置类/CRPG 如《神界原罪》《博德之门 3》仍是 turn/tick）。**过时的不是 tick，而是"玩家在 tick 中无事可做"**。`combatd.c:818` 的出击闸、`attack.c:85` 的单目标随机选择，使玩家在战斗中沦为旁观者，这在当代会被判为"无操作意义"。
- **`保留`**：`MAX_OPPONENT=4` + `random(MAX_OPPONENT)` 选目标的围攻模型（`attack.c:79-88`）其实是个朴素但有效的"混乱战场"模拟——多敌围攻时并非稳定集火，而是随机分心。这个**设计意图**（多对一时不是简单加法叠加，而是注意力分散）值得保留精神，但 `MAX_OPPONENT=4` 的硬上限数值过时（现代多以软衰减或威胁值/嘲讽系统处理，见 §3）。
- **`现代化`**：Effect 更新频率（`char.c:141-144` 每 5~15 tick）与普攻（每 tick）的节奏不一致是**隐藏的体验问题**——中毒数字跳得比普攻慢很多，玩家难以建立"我正在持续掉血"的直觉。现代游戏（如 WoW DoT）DoT 跳与 GCD 对齐或有独立可视 tick。新引擎应让 Effect 跳数与战斗节奏在玩家感知上对齐。

---

## 2. 命中与伤害：combatd 命中结算 + 三类伤害

### 2.1 LPC 实现

命中结算在 `adm/daemons/combatd.c:340 do_attack()`，是**三段概率判定**：

1. **闪避判定**（`combatd.c:430`）：`if( random(ap + dp) < dp )` -> 闪避。命中概率 = `AP/(AP+DP)`。
   - AP = `skill_power(me, attack_skill, ATTACK)`（`combatd.c:410`），DP = `skill_power(victim, "dodge", DEFENSE)`（`combatd.c:417`）；`victim->is_busy()` 时 `dp/=3`（`combatd.c:419-420`）。
2. **招架判定**（`combatd.c:468-480,488`）：`if( random(ap + pp) < pp )` -> 招架。PP 逻辑有武器状态分支：持械对持械用 `parry`；**空手对持械 PP×2**（`combatd.c:471-472`，鼓励空手防御）；**持械对空手 PP=0**（`combatd.c:476-477`，空手无法招架兵器）。
3. **伤害结算**（`combatd.c:519-537`）：`damage = apply/damage; (damage+random(damage))/2; ... += skill*damage/100`，`damage_bonus = query_str()`，叠加 force/martial/weapon 的 `hit_ob` hook 返回值。

伤害模型在 `feature/damage.c:13-66`：
- 三类伤害：`jing`（精）、`qi`（气）、`jingli`（精力）（`damage.c:18` 类型校验）。
- `receive_damage(type, damage, who)`（`damage.c:13`）扣当前值；`receive_wound(type, damage, who)`（`damage.c:39`）扣**上限值** `eff_type`，且当前值不能超过上限（`damage.c:61`）——即 wound 是"重伤上限"机制。
- 伤害来源 `set_temp("last_damage_from", who)`（`damage.c:21`），用于死亡归属与 `killer_reward`。
- 关键数值公式 `combatd.c:317 skill_power()`：`power = (level*level*level)/3`——**技能等级三次方缩放**，再乘 `str/10` 与 `jingli_bonus`。高等级技能数值爆炸式碾压。
- 经验值减伤 `combatd.c:636-641`：`while( random(defense_factor) > my["combat_exp"] ){ damage -= damage/3; defense_factor/=2; }`——经验值高者**概率性**减伤，可多次触发。
- 暴击：**无显式暴击系统**。`combatd.c:520 (damage + random(damage))/2` 是伤害浮动而非暴击。
- 格挡（block）：无独立 block，并入 parry。
- 伤害类型 `action["damage_type"]`（如"割伤/刺伤/瘀伤/内伤"，`combatd.c:79-204 damage_msg()`）仅影响**文本播报**，不影响数值抗性（无元素抗性、无护甲类型相克）。

### 2.2 当代对标

| 维度 | 当代成熟解法 | LPC 现状 |
|------|-------------|---------|
| 命中模型 | 攻防差值查表/掷骰 + 命中率上限下限（cap） | `AP/(AP+DP)` 概率，无 cap，极端值下 0% 或 100%（`combatd.c:430`） |
| 暴击 | 暴击率 + 暴击伤害倍率，独立属性 | 无，仅有 `random(damage)` 浮动（`combatd.c:520`） |
| 格挡/闪避 | 独立三轴：dodge/parry/block | parry 与 dodge 两轴，block 并入 parry（`combatd.c:468-488`） |
| 伤害类型 | 物理/魔法/真实，护甲 vs 法抗，元素相克 | 三类内功气血资源（`damage.c:18`），但伤害"类型"仅文本（`combatd.c:79`） |
| 减伤 | 固定减伤 + 百分比减伤分层 | 经验值概率减伤（`combatd.c:636`）+ `apply/armor` 固定扣（`combatd.c:578`） |
| 数值缩放 | 线性/多项式 + 等级压缩 | **三次方**（`combatd.c:317`），无压缩，数值极易失控 |

### 2.3 评估

- **`保留`**：**三类资源（jing/qi/jingli）+ wound 上限伤害**是一个有当代价值的设计。`damage.c:39-66` 的"当前值 vs 上限值"双层模型（`eff_jing`/`eff_qi`）等价于现代游戏的"血量 + 最大血量 debuff"——例如 WoW 的吸血减疗、魂系的"最大 HP 下降"。`wound` 只能靠 `receive_curing`（`damage.c:85`）缓慢恢复上限，这种"重伤需要专门治疗"的设计在武侠语境下有题材独特性，应保留精神。
- **`现代化`**：命中三段判定（闪避 -> 招架 -> 命中，`combatd.c:430,488`）结构合理，但缺少**命中率 cap 与保底**。现代游戏普遍有 5%~95% 命中区间，避免极端 build 导致 0%/100% 无趣解。新引擎应引入 cap。`is_busy -> dp/=3`（`combatd.c:419`）这种"控制态降低闪避"的思路也对，但应改为显式 debuff 而非隐式除法。
- **`丢弃`**：**技能等级三次方缩放**（`combatd.c:317 power = level^3/3`）是过时的数值设计。三次方意味着等级差 2 倍则战力差 8 倍，配合经验值减伤（`combatd.c:636`）形成"高等级碾压低等级几乎无伤"的局。现代游戏用多项式 + 等级压缩/物品等级系统避免数值爆炸。新引擎**不应继承三次方**。
- **`丢弃`**：`combatd.c:636-641` 经验值概率减伤是"用经验值当第二防御属性"的偷懒做法，使老玩家凭时长而非配装获得生存力，与现代"配装驱动"理念冲突，且与 pay-to-win 边界模糊（见商业化红队）。
- **`现代化`**：伤害类型（割/刺/瘀/内）目前只影响文本（`combatd.c:79 damage_msg`）。武侠题材天然适合"兵器相克 + 内功抗性"的弱元素系统——例如刺伤对轻甲加成、内伤无视外甲。新引擎可把 `damage_type` 升级为有数值意义的伤害谱系，但**不必做成 MMO 式完整元素相克表**（会喧宾夺主）。
- **`现代化`**：缺少暴击/格挡独立轴。建议补齐暴击（rate + damage multiplier）与 block（独立于 parry 的减伤而非完全规避），这是当代玩家已形成的心智预期，缺失会显得"战斗数值扁平"。

---

## 3. Effect/状态：condition 时效 Effect vs 现代 Buff/Debuff

### 3.1 LPC 实现

- `feature/condition.c`：每个 condition 是**独立外部 daemon**，`conditions` 是 `mapping`（`condition.c:8`）。
- `update_condition()`（`condition.c:21-69`）遍历所有 condition，对每个调用 `CONDITION_D(cnd[i])->update_condition(this_object(), info)`（`condition.c:62`）；daemon 返回 `CND_CONTINUE` 则续存，返回 0 则自动移除（`condition.c:63`）。
- `apply_condition(cnd, info)`（`condition.c:79-85`）**直接覆盖**同名 condition，无叠加规则——注释明说"It is condition giver's responsibility to check if the condition should override"（`condition.c:74-77`）。即叠加/刷新/优先级**由每个 giver 自行实现**，无统一规则。
- 驱动：`char.c:144 cnd_flag = update_condition()`，每 `tick = 5 + random(10)`（`char.c:54`）调一次。
- 内容层（`kungfu/condition/`，30+ 个）风格差异极大，举几例：
  - **中毒**（`bt_poison.c:7-42`）：每 tick `receive_wound("jing", damage/2)` + `receive_damage("jingli", damage/2)`（`:33-34`），duration 按 `5 + poison_skill/10` 递减（`:36-38`）——解毒技能缩短中毒时长。这是少有的"技能对抗状态"机制。
  - **盲**（`blind.c:11-24`）：每 tick duration-1，到期恢复 `apply/attack`/`apply/defense`（`blind.c:28-34`，`cimu_power`）。盲本身不直接改命中，而是通过临时扣 `apply/attack` 间接影响 `skill_power`（`combatd.c:299-300`）。
  - **醉**（`drunk.c:6-35`）：分段效果——低度治疗（`:24-29` receive_healing），高度伤害+昏迷（`:12-15` unconcious）。limit = `3 + con + max_neili/40`（`:10`）——内功提升酒量。
  - **嵌入暗器**（`embedded.c:9-33`）：每 tick `receive_wound("qi", 3)`（`:17`）持续掉血，NPC 会自动 `remove`（`:22-27`）。
  - **坐牢**（`city_jail.c:7-23`）：纯 countdown，到期 `move` 到衙门外（`:9-14`）——硬控/禁闭，期间被 `block_cmd` 限制指令（参见 `d/death/death.c:30-37` 的 block_cmd 模式）。

### 3.2 当代对标

| 维度 | 当代成熟解法 | LPC 现状 |
|------|-------------|---------|
| 数据结构 | Buff/Debuff 列表，每条含 source/stack/duration/priority/dispellable | `mapping conditions`，info 是自由 `mixed`（`condition.c:8,91`），无统一 schema |
| 叠加规则 | 显式 stack（独立层数）/ refresh（刷新时长）/ replace（覆盖）三选一，引擎强制 | 无统一规则，giver 自管（`condition.c:74-77`） |
| 驱动 | 每 tick/每秒统一推进，UI 实时倒计时 | 每 5~15 heart_beat 推进（`char.c:141-144`），无 UI |
| 净化 | Cleanse/Dispel 分类（魔法/物理/诅咒可被特定技能清除） | 无通用净化，`clear_condition`（`condition.c:105`）一刀切清空 |
| 控制（CC） | 硬控（stun/silence/root）与软控（slow/减攻速）分类，有韧性/CC 免疫属性 | 无 CC 分类，盲/牢/醉各管各的，无韧性抗性 |
| Buff 来源 | 来源可追溯（谁加的、第几层）以做归属 | 仅记录伤害来源 `last_damage_from`（`damage.c:21`），Effect 无归属 |

### 3.3 评估

- **`保留`**：**"每个 condition 是独立 daemon"的解耦设计**（`condition.c:36-62`，`find_object(CONDITION_D(...))` 动态加载）在架构上是先进的——Effect 内容与 Effect 引擎分离，新 Effect 即新文件，不改核心。这与现代游戏的"Effect/Buff 是数据驱动 asset"理念一致，是新引擎应继承的架构精神（对应 UGC 创作层挂 Effect 的诉求，见 brief §3.2）。
- **`保留`**：**状态与武功的耦合**（如 `bt_poison.c:36` 解毒技能缩短毒时长、`drunk.c:10` 内功提升酒量）是武侠题材独特的"技能对抗状态"设计，有题材魅力，值得保留并体系化——把"以毒攻毒""内功逼酒"做成显式机制。
- **`现代化`**：`apply_condition` 直接覆盖（`condition.c:81-84`）+ 无统一叠加规则是**最大过时点**。现代玩家预期"中毒叠 3 层变剧毒""刷新不覆盖更高级 buff"，而 LPC 全靠每个 giver 自觉。新引擎必须在 Effect 引擎层强制 stack/refresh/replace 三种策略与优先级，不能下放给内容层。
- **`现代化`**：缺少 CC 分类与韧性（tenacity）属性。盲/牢/醉/中毒在 LPC 里是平行的 condition，没有"硬控可被净化、软控可堆叠"的区分，也没有"连续被控递减（DR, diminishing return）"。现代 PvP 设计中 DR 是防"无限连控致死"的标配（LoL 的韧性、WoW 的 DR）。新引擎若做 PvP 必须补。
- **`现代化`**：Effect 无来源归属（`damage.c:21` 只记伤害来源，不记 Effect 来源）。现代游戏 buff/debuff 都有 caster 归属，用于"驱散时只驱散敌人的""击杀加 buff 者得助攻"等。新引擎应给每条 Effect 加 `source` 字段。
- **`现代化`**：纯文本播报无 UI 倒计时（`condition.c` 无 duration 查询接口供 UI）。文本 MUD 时代合理，但新引擎若有多人/Web 客户端，必须暴露 Effect 列表与剩余时长——这直接影响玩家"何时该交解控技能"的决策。

---

## 4. 死亡惩罚：下地府走轮回 + 鬼魂态

### 4.1 LPC 实现

死亡是**两段式判定 + 强惩罚 + 强制流程**：

- **两段式判定**（`char.c:99-115`）：
  - `eff_qi < 0 || eff_jing < 0` -> 直接 `die()`（`char.c:100-104`，上限被打穿=死）。
  - `qi < 0 || jing < 0 || jingli < 0` -> `unconcious()`（`char.c:108-111`，当前值被打空=昏迷）；若已处于昏迷态再被打则 `die()`（`char.c:112-113`）。
- **昏迷**（`damage.c:105-135 unconcious()`）：`remove_all_enemy`、清零三资源（`damage.c:128-130`）、`block_msg/all=1`（屏蔽所有消息）、`call_out("revive", random(100-con)+30)`（`damage.c:134`）随机苏醒。`no_death` 房间内 `die()` 降级为 `unconcious()`（`damage.c:159-177`）。
- **死亡惩罚**（`combatd.c:987-1025 death_penalty()`）：
  - `combat_exp` 扣 `combat_exp/100`（上限 5000，`combatd.c:1001-1011`）；
  - `potential` 减半（`combatd.c:1007-1008`）；
  - `shen` 扣 5%、`behavior_exp` 扣 5%（`combatd.c:999-1000`）；
  - `balance`（存款）超 10000 部分减半（`combatd.c:1013-1015`）；
  - `death_count++`、清 `vendetta`、`thief` 减半、`skill_death_penalty()`（技能也会掉，`combatd.c:1022`）。
- **地府流程**（`d/death/`）：
  - `damage.c:246-248`：`ghost=1; move(DEATH_ROOM); DEATH_ROOM->start_death()`。`DEATH_ROOM = /d/death/gate.c`（`include/login.h:23`）。
  - `d/death/gate.c:32-36 init()`：**destruct 所有 inventory**（身上所有物品全丢）、`clear_condition`、`no_fight=1`、禁止 `suicide`。
  - `d/death/gateway.c:28-37 valid_leave()`：**禁止回头**（"没有回头路了"），单向流程。
  - `d/death/road1-3.c`：阴森路径，线性走鬼门大道。
  - `d/death/death.c` / `block.c` / `hell.c`：死刑室/第十八层地狱，`block_cmd` 仅允许 `look/quit/say` 等少数指令（`death.c:30-37`），用于惩罚罪犯玩家。
- **轮回复活**（`damage.c:255-264 reincarnate()`）：`ghost=0`，三资源恢复到 max。
- **鬼魂态**（`damage.c:9-11 is_ghost()`，`ghost` 标志）：鬼魂对活人不可见，除非 `astral_vision`（`char.c:181-186 visible()`）。

### 4.2 当代对标

| 维度 | 当代成熟解法 | LPC 现状 |
|------|-------------|---------|
| 死亡惩罚力度 | 轻惩罚为主流：经验微损/装备耐久下降/复活点重生；硬核品类（魂系/暗黑）才掉魂/掉钱 | **极重**：经验大扣 + 潜能减半 + 存款减半 + 物品全丢 + 技能掉 + 强制地府步行 |
| 复活方式 | 多种：原地/复活点/队友复活/道具复活；玩家可选 | 单一路径：强制地府走轮回（`damage.c:247`） |
| 死亡归属 | 击杀者得奖励、被杀者掉落可被拾取 | `killer_reward`（`combatd.c:1027`）、`last_damage_from` 记录（`damage.c:21`） |
| 鬼魂态 | 少数题材用作探索机制（如 WoW 鬼魂跑尸） | 鬼魂态 + `astral_vision` 可见性（`char.c:181`） |
| 安全区 | 复活点/主城禁 PvP | `no_death` 房间死亡降级为昏迷（`damage.c:159`）、`no_fight` 房间禁战（`attack.c:54`） |

### 4.3 评估

- **`保留`**：**两段式判定（昏迷 -> 死亡）**（`char.c:99-115`，`damage.c:105/152`）是优秀设计。它给了"被打空当前值"和"被打穿上限值"两种危险等级，昏迷是可恢复的中间态，死亡是终态。现代游戏普遍有类似"downed state"（如 GOW/Genshin 倒地救援）。新引擎应保留昏迷/死亡的分层，并可在昏迷态加入"队友救援"机制。
- **`保留`**：**`no_death` 房间死亡降级为昏迷**（`damage.c:159-177`）是好的"安全区"设计，给新手村/主城留出无致死空间。对应 MVP 场景"华山村不绑定门派"（见 brief §架构不变量 7）的新手保护诉求。
- **`现代化`**：**地府走轮回作为"题材性死亡流程"**（`d/death/gate.c` 等）有武侠/民俗魅力，**不应丢弃但应改为可选题材包内容而非引擎默认**。问题在力度：`gate.c:32-36` destruct 所有物品 + 经验大扣（`combatd.c:1001`）+ 技能掉（`combatd.c:1022`）对当代玩家是劝退级惩罚。现代设计原则是"死亡惩罚应制造紧张感而非挫败感"（详见玩家心理红队）。建议：地府流程保留为题材包的"死亡叙事"，但引擎层默认惩罚参数（经验/物品/技能）应是**可配置**的，且默认值偏轻。
- **`丢弃`**：**`gateway.c:28-37` 禁止回头 + `gate.c:32` 物品全丢**这种不可逆重罚在当代不可接受。即便硬核如魂系，掉魂也是"可捡回"的，而 LPC 是永久丢失。新引擎不应继承"死亡全清物品"。
- **`现代化`**：**单一复活路径**（强制地府）过时。现代游戏提供多种复活方式（原地/复活点/道具/队友），玩家有选择权。新引擎应把"复活策略"做成题材包可配的接口（复活点列表、复活道具、复活惩罚系数），引擎提供默认轻惩罚复活。
- **`保留`**：**鬼魂态 + `astral_vision` 可见性**（`damage.c:9-11`，`char.c:181-186`）是有趣的探索机制，可作为题材包的"鬼魂跑尸/阴阳两界"玩法保留精神，但不应作为默认死亡流程强制走。

---

## 5. 武功招式：kungfu/skill 招式系统 vs 现代技能树/连招/技能槽

### 5.1 LPC 实现

- 技能是**数值等级 + 招式表**双结构：
  - 等级侧：`feature/skill.c:17-25 set_skill()` 设等级，`skill_map`（`skill.c:42-58 map_skill`）把基础技能映射到武功（如 sword -> 某剑法），`skill_prepare`（`skill.c:62-78 prepare_skill`）预备最多 2 个技能（双手互搏，`combatd.c:807`）。
  - 招式侧：以 `kungfu/skill/18-zhang.c:52-100 action[]` 为例，每个招式是一个 mapping：`action`（文本）、`dodge`/`parry`（修正）、`force`/`damage`（数值）、`lvl`（解锁等级）、`skill_name`、`damage_type`、`weapon`。
- 招式选择：`feature/attack.c:143-171 reset_action()` 根据武器/预备技能/映射武功决定本次用哪套 action；`combatd.c:384 action = me->query("actions")` 取出，但具体哪一招是**随机/按规则**从 action[] 中选（`attack.c:163-165 call_other SKILL_D(skill)->query_action`）。
- **反击/特殊招式**：`18-zhang.c:11-38 query_parry_msg()` 在被招架时触发"神龙摆尾"反击，直接调 `COMBAT_D->do_attack(victim, me, ...)`（`18-zhang.c:36`）——即**招式可递归调用战斗结算**，实现反击/连招。`combatd.c:766-779` 的 riposte 机制是引擎侧的反击钩子。
- **武功 hook**：`combatd.c:541-561 force_skill->hit_ob`、`combatd.c:578-585 martial_skill->hit_ob`、`combatd.c:588-603 weapon->hit_ob`——武功/内功/武器都能通过 `hit_ob` hook 注入额外伤害或效果，是 Effect 的重要载体。
- **技能成长**：use-based（使用增长），`combatd.c:450 me->improve_skill(attack_skill, random(int))`、`combatd.c:442 victim->improve_skill("dodge", 1)`——战斗中 dodge/parry/攻击技能都会因使用而涨经验。无技能点分配。

### 5.2 当代对标

| 维度 | 当代成熟解法 | LPC 现状 |
|------|-------------|---------|
| 技能获取 | 技能树/天赋树，玩家主动选择点数分配 | use-based 自动成长（`combatd.c:450`），玩家无分配权 |
| 招式释放 | 主动按键 + 冷却 + 资源消耗（MP/CD） | 战中**随机触发**（`attack.c:163`），玩家不主动选招 |
| 连招 | 显式连段（A->B->C 有条件触发） | 隐式：`action_flag` 双招（`combatd.c:811`）、反击递归（`18-zhang.c:36`） |
| 技能槽 | 固定技能栏，玩家配置可用技能 | 无技能栏概念，"装备"武功即生效（`skill.c:42 map_skill`） |
| 技能解锁 | 等级/任务/付费解锁 | `action["lvl"]` 招式按等级解锁（`18-zhang.c:58` lvl:5/10/15...） |
| Build 多样性 | 天赋树 + 装备词条 + 技能替换 | `map_skill` 映射 + `prepare_skill` 双手 + 装备，build 空间中等 |

### 5.3 评估

- **`保留`**：**武功 = 数值等级 + 招式表 + hook**（`skill.c` + `18-zhang.c:52` + `combatd.c:541`）是武侠题材最核心的设计资产。招式表（action[] 带 dodge/parry/force/damage/damage_type/weapon）天然适配"一招一式有文学性描述 + 有独立数值"的武侠感。新引擎应保留"招式是数据驱动的可配置 asset"这一架构（对应 UGC 创作层配招式诉求）。
- **`保留`**：**`hit_ob` hook 三层注入**（force 内功 / martial 武功 / weapon 兵器，`combatd.c:541/578/588`）是优雅的可扩展点——任何一层都能改伤害、加 Effect、加文本。这种"责任链式伤害修改"正是现代游戏 Damage Pipeline 的雏形（如 WoW 的 modifier 链）。新引擎应把它做成正式的、有序的伤害管线，而非散落的 `foo` 类型判断（`combatd.c:544-560` 用 `stringp/intp/mapp` 反复判类型是技术债）。
- **`现代化`**：**战中玩家不主动选招**（`attack.c:163` 随机/规则触发）是最大的过时点。当代玩家预期"我决定何时放绝招"。LPC 模式接近现代的"自动战斗"（如手游 auto-battle），但作为主玩法不可接受。新引擎至少应提供"主动释放大招/绝技"的指令面（对应 `cmds/std/` 的 `perform.c` condition 暗示的 perform 机制），把随机招式降级为"普攻自动循环"。
- **`现代化`**：**use-based 技能成长**（`combatd.c:450`）在当代争议大。优点是"练即所得"有沉浸感，缺点是**玩家无法控制 build 方向**，且鼓励挂机刷。现代趋势是 use-based + 可分配点数混合，或纯点数树。新引擎建议至少给玩家"在使用积累的经验上主动分配"的接口，否则创作者调平衡极难。
- **`现代化`**：**无冷却/无资源消耗的主动技能**——LPC 靠 `jingli`（精力，`combatd.c:401,458` 接招消耗）和 `neili`（内力，`combatd.c:539 jiali`）做软限制，但无显式 CD。现代游戏的大招普遍有 CD + 资源双限制以控制节奏与爆发窗口。新引擎应引入技能 CD 与资源消耗的通用机制。
- **`保留`**：**反击/递归招式**（`18-zhang.c:36` 神龙摆尾反击、`combatd.c:766` riposte）是有题材魅力的"被动触发主动招"设计，值得保留精神——但要注意递归调用 `do_attack`（`18-zhang.c:36`）有无限递归风险，新引擎需加反击深度上限。

---

## 6. 综合评估：保留 / 现代化 / 丢弃 清单

### 6.1 应保留（LPC 设计精神，新引擎继承）

| 机制 | LPC 证据 | 保留理由 |
|------|----------|---------|
| 三类资源 + wound 上限伤害双层模型 | `damage.c:13-66` | 等价现代"血量+最大血量 debuff"，武侠题材独特 |
| 两段式死亡（昏迷 -> 死亡） | `char.c:99-115`，`damage.c:105/152` | 现代普遍的 downed state，有恢复中间态 |
| 安全区死亡降级（`no_death` -> 昏迷） | `damage.c:159-177` | 新手/主城保护，对应 MVP 华山村需求 |
| Effect = 独立 daemon 的数据驱动解耦 | `condition.c:36-62` | 架构先进，适配 UGC 挂 Effect |
| 状态与武功耦合（解毒缩时/内功逼酒） | `bt_poison.c:36`，`drunk.c:10` | 武侠"以功克毒"题材魅力 |
| 武功 = 招式表 + 等级 + hit_ob hook | `skill.c`，`18-zhang.c:52`，`combatd.c:541` | 核心武侠设计资产，招式可数据驱动 |
| 三层 hit_ob 注入（内功/武功/兵器） | `combatd.c:541/578/588` | 现代伤害管线的雏形，可扩展 |
| MAX_OPPONENT 围攻的"注意力分散"意图 | `attack.c:79-88` | 多对一非简单叠加的设计直觉 |
| 反击/递归招式（神龙摆尾） | `18-zhang.c:36`，`combatd.c:766` | 被动触发主动招的题材魅力 |
| 鬼魂态 + astral_vision 可见性 | `damage.c:9-11`，`char.c:181-186` | 可作题材包"阴阳两界"探索机制 |

### 6.2 应现代化（机制有价值但实现过时）

| 机制 | LPC 证据 | 现代化方向 |
|------|----------|-----------|
| tick 驱动战斗中玩家无事可做 | `char.c:60`，`combatd.c:818` 出击闸 | 保留 tick 但给玩家主动操作面（绝技/走位） |
| Effect 更新频率与普攻不一致 | `char.c:141-144`（每 5~15 tick） | Effect 跳数与战斗节奏在玩家感知上对齐 |
| 命中无 cap 无保底 | `combatd.c:430`（AP/(AP+DP)） | 引入 5%~95% 命中区间 |
| 伤害类型仅文本无数值意义 | `combatd.c:79 damage_msg` | 升级为弱元素/兵器相克（武侠向，非 MMO 式） |
| 缺暴击/独立格挡轴 | `combatd.c:520` 仅浮动 | 补暴击（rate+dmg）与 block 独立轴 |
| Effect 叠加无统一规则 | `condition.c:81-84` 直接覆盖 | 引擎强制 stack/refresh/replace + 优先级 |
| 无 CC 分类与韧性/DR | 各 condition 各管各 | 硬控/软控分类 + tenacity + DR |
| Effect 无来源归属 | 仅 `damage.c:21` 伤害来源 | 每条 Effect 加 source 字段 |
| Effect 无 UI 倒计时接口 | `condition.c` 无 duration 查询 | 暴露 Effect 列表与剩余时长 |
| 单一复活路径 | `damage.c:247` 强制地府 | 复活策略题材包可配（复活点/道具/队友） |
| 死亡惩罚过重且不可逆 | `gate.c:32` 全清物品，`combatd.c:1001` | 默认轻惩罚，惩罚参数可配 |
| 战中不主动选招 | `attack.c:163` 随机触发 | 主动绝技指令 + 普攻自动循环 |
| use-based 技能成长无分配权 | `combatd.c:450` | use-based + 可分配点数混合 |
| 无技能 CD/资源双限制 | 仅 `jingli`/`neili` 软限制 | 引入 CD + 资源通用机制 |

### 6.3 应丢弃（与当代根本冲突）

| 机制 | LPC 证据 | 丢弃理由 |
|------|----------|---------|
| 技能等级三次方缩放 | `combatd.c:317 power=level^3/3` | 数值爆炸，现代用多项式+等级压缩 |
| 经验值概率减伤 | `combatd.c:636-641` | 用时长当防御属性，与配装理念冲突，涉付费红线 |
| 死亡全清物品不可逆 | `gate.c:32-36` destruct inventory | 当代不可接受，硬核品类也允许捡回 |
| 地府禁止回头 | `gateway.c:28-37` | 单向强制流程剥夺玩家选择权（叙事可保留，强制应丢弃） |

---

## 7. 给新引擎的设计输入方向（非接口草案）

> 遵守 brief §1.4：不输出 engine 接口，只给设计方向。

1. **战斗定位应明确"半自动"而非"全自动"**：LPC 的"全自动 + 战前配置"在当代只适合放置类细分市场。新引擎若想服务更广玩家，应在 tick 之上提供"主动绝技/主动走位/主动防御"的操作层，把 LPC 的随机招式降级为"普攻自动循环"。否则战斗对当代玩家无操作意义（§1.3、§5.3）。

2. **伤害管线应正式化**：把 LPC 散落的 `hit_ob` 三层 hook（`combatd.c:541/578/588`）重构成有序的 Damage Pipeline（来源 -> 命中判定 -> 暴击 -> 减伤 -> 伤害类型修正 -> wound/damage 分流 -> Effect 触发），消除 `stringp/intp/mapp` 反复判类型的技术债（`combatd.c:544-560`）。这是现代战斗引擎的标配结构。

3. **Effect 引擎必须强制叠加策略**：不能像 `condition.c:74-77` 那样把叠加规则下放给内容层。引擎层提供 stack/refresh/replace 三种策略 + 优先级 + source 归属 + dispellable 标志，内容层只声明用哪种。这是 UGC 创作层挂 Effect 的前提（对应 `ugc-surface` 调研）。

4. **死亡惩罚做成可配参数 + 默认轻惩罚**：地府走轮回作为**题材包**内容保留叙事价值，但引擎层默认复活应是轻惩罚（复活点 + 小幅经验/耐久损失）。`death_penalty`（`combatd.c:987`）里的各项扣减都应是题材包可覆盖的参数，而非硬编码。两段式昏迷/死亡（`char.c:99-115`）保留为引擎默认。

5. **数值缩放必须替换三次方**：`skill_power`（`combatd.c:317`）的三次方与经验值减伤（`combatd.c:636`）共同导致"高等级无脑碾压"。新引擎应采用受控的多项式缩放 + 等级压缩区间，并由数值平衡专家显式标定（见数值平衡调研）。

6. **武功招式做成数据驱动 asset**：保留 `18-zhang.c:52` 的 action[] 表结构精神（招式 = 文本 + 数值 + 解锁等级 + 伤害类型），但把"战中随机触发"改为"玩家主动释放绝技 + 普攻自动循环"，并给招式加 CD/资源消耗。`hit_ob` hook 保留为招式注入 Effect 的扩展点。

7. **PvP 必备 CC 韧性/DR**：若 MVP/题材包涉及 PvP（`cmds/std/kill.c` 的 PK 机制、`combatd.c:1027 killer_reward` 的 PK 奖惩），必须引入硬控/软控分类与 DR，否则会出现"无限连控致死"的体验灾难（详见玩家心理红队）。

---

## 8. 未决问题（移交评审委员会）

1. **战斗操作粒度**：新引擎是走"半自动（主动绝技 + 自动普攻）"还是"纯回合（玩家每回合决策）"？这决定 tick 是否保留为玩家可见节奏。本评审倾向半自动，但需与引擎架构师 A 对齐（`abstraction-options`）。
2. **地府流程的引擎 vs 题材包边界**：`d/death/` 的轮回流程应放在引擎核心还是武侠题材包？若放题材包，引擎需提供什么样的"死亡流程 hook"供题材包接入？需与 UGC 创作层对齐（`ugc-surface`）。
3. **伤害类型是否做相克**：升级 `damage_type`（`combatd.c:79`）为数值相克会显著增加 build 深度，但也增加平衡复杂度与武侠题材的"兵器/内功"复杂度。需数值平衡专家裁决（`numerical-balance`）。
4. **use-based 成长是否保留**：use-based（`combatd.c:450`）与现代点数树之争涉及留存设计，需玩家心理与商业化共同裁决。

---

## 附：关键证据索引（LPC 文件:行/函数）

- 战斗节奏：`feature/attack.c:12,79-88,208`；`inherit/char/char.c:53,60,99-115,141-144`；`adm/daemons/combatd.c:818,837-842`
- 命中伤害：`adm/daemons/combatd.c:288-333(skill_power),340(do_attack),410,417,430,468-488,519-537,636-641`；`feature/damage.c:13-66,85`
- Effect：`feature/condition.c:8,21-69,79-85`；`kungfu/condition/bt_poison.c:7-42`；`blind.c:11-34`；`drunk.c:6-35`；`embedded.c:9-33`；`city_jail.c:7-23`
- 死亡：`feature/damage.c:105-135,152-264`；`inherit/char/char.c:99-115`；`adm/daemons/combatd.c:987-1025`；`d/death/gate.c:32-36`；`d/death/gateway.c:28-37`；`include/login.h:23`
- 武功招式：`feature/skill.c:17-78`；`feature/attack.c:143-171`；`kungfu/skill/18-zhang.c:11-38,52-100`；`adm/daemons/combatd.c:541-603,766-779`
- 命令：`cmds/std/kill.c:9-88`
