# 红队挑战：现代战斗玩法评审结论质疑

> 角色：现代玩法挑战者（红队）。任务：对 `03-engine-insights/modern-design-review.md` 的“保留/现代化/丢弃”三档结论与交叉文件（`player-psychology.md`、`ugc-surface.md`、`engine-comparison.md`、项目 `CLAUDE.md`）提出尖锐质疑。每条质疑引用被质疑文件与段落，并附 LPC 一手源码或 engine 模块证据。禁止凭空推断。

---

## 0. 总质疑摘要

`modern-design-review.md` 存在三处需要评审委员会重新裁决的偏见：

1. **将“主动按键操作”默认为现代化方向**，未充分论证文本 MUD 目标用户是否追求该方向，且与文本媒介的可读性约束冲突。
2. **将地府轮回/鬼魂态降级为“题材包可选内容”**，与项目基线中“死亡与轮回为 MVP 必做”冲突，且低估了引擎层支撑需求。
3. **对玩家心理结论选择性吸收**：采纳“防秒杀”“死亡惩罚封顶”等保护机制，却未处理这些机制与“保留 wound 上限伤害”“保留地府重量感”之间的内在矛盾。

---

## 1. 质疑一：是否过度现代化，丢弃文本 MUD 武侠战斗的核心沉浸价值？

### 1.1 “战中玩家不主动选招 = 最大过时点”的质疑

**被质疑结论**：`modern-design-review.md §5.3`（段落 3）与 `§6.2`（“战中不主动选招”条目）认为：
> “战中玩家不主动选招（`attack.c:163` 随机触发）是最大的过时点……新引擎至少应提供主动释放大招/绝技的指令面，把随机招式降级为普攻自动循环。”

**红队挑战**：

- **LPC 并非没有主动操作面**。`cmds/skill/perform.c:10-80` 已实现玩家主动施放外功绝技：检查 `is_busy`/`huagong`/`feng`/`cannot_perform`（`perform.c:14-25`），解析 `martial.skill`（`perform.c:36-48`），调 `SKILL_D(skill)->perform_action(me, arg)`（`perform.c:65`），并挂 `apply_condition("perform", martial)` 冷却锁（`perform.c:69`）。`cmds/skill/exert.c:8-42` 同样提供内功主动运功。`modern-design-review.md` 将“普攻随机”扩大为“玩家全程无操作”，证据不足。
- **招式文案阅读是文本 MUD 不可替代的沉浸源**。`kungfu/skill/18-zhang.c:52-218` 的 `action[]` 数组每条含文学化文案（如 `$N一招「亢龙有悔」向$n的$l攻去！`）、`damage_type`（瘀伤/劈伤/内伤/擦伤/刺伤等）、`dodge`/`parry`/`force`/`damage` 修正与 `post_action`（如 `sanhui` 三叠亢龙有悔）。`adm/daemons/combatd.c:68-204 damage_msg()` 按 6 档伤害区间输出不同严重度描述，`combatd.c:278 report_status()` 输出彩色状态报告。`modern-design-review.md §0` 声称关注“设计意图与玩家体验，而非逐键手感”，但 §5.3 的“过时点”结论恰恰从“逐键手感”视角（“玩家不操作”“无操作意义”）推出，与 §0 方法论自相矛盾。
- **Build 配置是深层策略层，不应被“按键”定义取代**。`feature/skill.c:42-78` 的 `map_skill` 与 `prepare_skill` 让玩家在战前决定武功映射与双手互搏组合，战斗是 build 的检验而非 APM 比拼。`modern-design-review.md §5.3` 把主动选招作为默认现代化，等于把文本 MUD 武侠从“build 驱动的阅读式战斗”改造成“操作驱动的动作战斗”，后者在现代市场已有 Genshin/魂系等成熟品类，文本 MUD 在此赛道无竞争优势。

**裁决建议**：将 §5.3“战中玩家不主动选招”从“最大过时点”降级为“可选增强项”。perform/exert 已提供主动操作面；普攻自动循环是“武侠小说式战斗叙事”的载体。若增强，应优先扩展 perform/exert 的丰富度与资源管理，而非把普攻改为主动按键。

### 1.2 “use-based 技能成长争议大”的质疑

**被质疑结论**：`modern-design-review.md §5.3`（段落 4）认为：
> “use-based 技能成长（`combatd.c:450`）在当代争议大……新引擎建议至少给玩家可分配点数接口。”

**红队挑战**：

- LPC 的 use-based 成长是武侠沉浸的关键：`adm/daemons/combatd.c:450 me->improve_skill(attack_skill, random(int))` 与 `combatd.c:442 victim->improve_skill("dodge", 1)` 让“招式越用越熟”有叙事实感。`modern-design-review.md` 仅将其与“挂机刷”绑定，但未引用 `feature/skill.c:166-168` 的 `spi=30` 学习技能数上限惩罚——多学技能会分散经验，本身就是对纯挂机最优解的约束。
- `player-psychology.md` 全文未讨论 use-based 成长对心理/留存的影响。“争议大”是结论，但无证据。红队认为，在武侠文本语境下，use-based 成长可能是**正向沉浸源**，而非争议源。
- `modern-design-review.md §8 未决问题 4` 将“use-based 成长是否保留”列为未决，但 §5.3 已给出明确现代化建议，存在结论先行。

**裁决建议**：保留 use-based 成长作为默认机制，可分配点数作为题材包可选扩展，而非默认现代化。

---

## 2. 质疑二：tick 驱动战斗现代化是否会破坏战斗紧张感与可读性？

### 2.1 “玩家在 tick 中无事可做”与 guard 机制的质疑

**被质疑结论**：`modern-design-review.md §1.3`（段落 1）与 `§7.1` 认为：
> “过时的不是 tick，而是玩家在 tick 中无事可做……应在 tick 之上提供主动绝技/主动走位/主动防御。”

**红队挑战**：

- **guard/guarding 不是“空转”，而是武侠对峙张力**。`adm/daemons/combatd.c:818-842 fight()` 三分支中，当 `random(victim->query_dex()*3) >= me->query_str()*2 + apply/speed` 时进入 `guarding` 态，播 `guard_msg`“注视着对方，企图寻找机会出手”。这是武侠小说中“两人对峙良久，突然出手”的节奏来源。`modern-design-review.md` 将其判为“节奏被打断”，但 `player-psychology.md §4.1` 承认 1 秒 tick 给了玩家阅读战况、输入指令的时间窗口——玩家正在阅读战斗叙事，这是核心玩法循环，不是“空等”。
- **“主动走位”是品类错位**。文本 MUD 的房间是离散拓扑节点，无 2D/3D 空间坐标。引入“走位”“闪避方向”既无实现基础，也无文本叙事意义。`modern-design-review.md` 用 MMO/动作品类标准评判文本 MUD，未考虑媒介差异。

**裁决建议**：撤回 §7.1 的“主动走位”建议；将 §1.3 对 guard 的定性从“节奏断裂”改为“武侠对峙张力”。

### 2.2 Effect 更新频率与普攻对齐的质疑

**被质疑结论**：`modern-design-review.md §1.3`（段落 3）认为：
> “Effect 更新频率（`char.c:141-144` 每 5~15 tick）与普攻不一致是隐藏的体验问题……应让 Effect 跳数与战斗节奏在玩家感知上对齐。”

**红队挑战**：

- `feature/condition.c:15-19` 注释明确警告：“don't make player got too much this kind of conditions or you might got lots of 'Too long evaluation' error”。`char.c:54 tick = 5+random(10)` 是**性能设计**，不是体验 bug。`modern-design-review.md` 建议对齐频率，未评估性能后果。
- 毒/内伤等持续状态在武侠叙事中本就是“慢慢侵蚀”。`kungfu/condition/bt_poison.c:11-26` 每次 Effect tick 独立播报“你觉得一股冷气直透心口”，低频播报制造的是中毒的“阴险感”与“失控感”，与普攻的激烈节奏形成对比。`player-psychology.md §3.1` 也指出这种“无法主动干预”的无力感是中毒体验的一部分。强行对齐会削弱武侠特色。

**裁决建议**：保留 `5+random(10)` 稀释频率作为默认；Effect 频率不一致不应判为“需现代化”，至少标注为“需 A/B 测试验证”。

---

## 3. 质疑三：死亡惩罚现代化是否会丢失 LPC 死亡的重量感与轮回叙事？

### 3.1 “默认轻惩罚”与轮回叙事重量的质疑

**被质疑结论**：`modern-design-review.md §4.3`（段落 3）与 `§6.2` 认为：
> “地府流程保留为题材包的死亡叙事，但引擎层默认惩罚参数应是可配置的，且默认值偏轻。”

**红队挑战**：

- LPC 的轮回叙事重量感来自惩罚与仪式的绑定。`combatd.c:987-1025 death_penalty()` 扣 combat_exp、potential 减半、skill -1 级；`d/death/gate.c:32-36` 入地府销毁全部物品；`d/death/gateway.c:28-37` 禁止回头；`d/death/road2.c:24-46` 迷雾循环需走 5 次；`d/death/npc/wgargoyle.c:51-71` 白无常 55 秒剧情后才能复活。惩罚越重，轮回流程越像“劫后余生”的仪式。若默认惩罚偏轻，轮回流程退化为无成本过场动画，与其保留的叙事价值自相矛盾。
- `player-psychology.md §6.2` 建议的是“死亡惩罚递减与封顶”（当日第 3 次起惩罚减半），**保留单次死亡的重量但防止反复恶性循环**。`modern-design-review.md` 的“默认偏轻”更激进，且未解释为何轻惩罚能保留叙事重量。
- `modern-design-review.md §6.1` 将“两段式死亡”“no_death 安全区”“地府走轮回”并列为保留项，但 §6.2 又建议“死亡惩罚过重且不可逆”现代化为“默认轻惩罚”。保留地府轮回的“惩罚-仪式-重生”三段式却抽走惩罚，三段式仅剩仪式外壳。

**裁决建议**：不采用“默认偏轻”。采用 `player-psychology.md §6.2` 的“单次保留重量 + 当日死亡封顶/递减”方案。`DeathPolicy` 保留 `penalty_ratio`，但新增 `daily_penalty_cap` 与 `repeat_death_decay`。

### 3.2 “死亡全清物品应丢弃”的质疑

**被质疑结论**：`modern-design-review.md §6.3` 第 3 条认为：
> “死亡全清物品不可逆（`gate.c:32-36`）应丢弃……即便硬核如魂系，掉魂也是可捡回的。”

**红队挑战**：

- `player-psychology.md §2.2` 承认装备全损“比经验惩罚更致命”，但并未建议完全取消，而是强调其对新玩家资产清零的杀伤。完全取消死亡掉装备会消除 LPC 死亡的“真实损失”感。
- `modern-design-review.md` 的魂系类比不适用于纯文本 MUD：魂系通过精确跑图与视觉地标实现“捡回”，文本环境无此类空间锚点。强行引入“捡回尸体”可能造成更差寻路体验。
- 更平衡的方案是保留 LPC 的 `CHAR_D->make_corpse` + `damage.c:227-228` 尸体掉落（已部分实现），仅去除地府 `gate.c:32-36` 的二次销毁。`engine/src/openmud/death_flow.py:77-86 DeathPolicy` 已支持 `drop_items: bool = True`，方向正确；`modern-design-review.md` 将其判为“应丢弃”过于武断。

**裁决建议**：保留尸体掉落机制，去除地府二次销毁；不把“死亡全清物品”整体丢弃。

---

## 4. 质疑四：保留 LPC 机制（地府轮回/鬼魂态）的论证是否充分？

### 4.1 地府轮回是否只是“题材包可选内容”？

**被质疑结论**：`modern-design-review.md §4.3`（段落 3）将地府流程定位为“可选题材包内容而非引擎默认”，`§8` 未决问题 2 又问其应放引擎核心还是题材包。

**红队挑战**：

- 项目 `CLAUDE.md` 架构不变量第 4 条指出“36+5 个已发现子系统全部归类为 MVP 必做（18）/可选（4）/现代化改造（9）/丢弃（11）”，其中“死亡与轮回（系统 39）”在子系统归类中为 **MVP 必做**。`CLAUDE.md` 架构不变量第 7 条 MVP 场景清单虽未直接列“地府”，但死亡与轮回作为系统 39 已被归入必做。`modern-design-review.md` 建议其“题材包可选”，与项目基线冲突。
- `ugc-surface.md §4.3` 指出：若未来支持地府，创作面应走 C 轨（房间/区域流程轨）+ 可信房间钩子，且 ghost 态组件需一并设计。这说明地府不是“可丢可不丢”的装饰品，而是需要引擎提供 ghost 态、房间钩子链、轮回出口机制的系统性工作。
- `engine-comparison.md §5.1a` 将“地府轮回流程整体缺失”列为 engine 最严重的负面遗漏之一，并指出这是 brief 明确纳入的 MVP 场景的直接断层。这与 `modern-design-review.md` 的“题材包可选”结论直接矛盾。

**裁决建议**：驳回“题材包可选”定位。地府轮回与鬼魂态应作为引擎必须支撑的 MVP 能力实现，至少提供受限动词集、鬼魂可见性规则、鬼域禁武等最小支撑。

### 4.2 鬼魂态保留理由是否充分？

**被质疑结论**：`modern-design-review.md §4.3`（段落 5）与 `§6.1` 认为：
> “鬼魂态 + astral_vision 可见性是有趣的探索机制，可作为题材包的‘鬼魂跑尸/阴阳两界’玩法保留精神，但不应作为默认死亡流程强制走。”

**红队挑战**：

- 鬼魂态是 LPC 死亡流程不可分割的部分：`feature/damage.c:9 int ghost = 0`、`:11 is_ghost()`、`:246 ghost = 1`、`:255-264 reincarnate()` 设 `ghost=0`；`inherit/char/char.c:181-186 visible()` 用 ghost 决定可见性。没有 ghost 态，地府流程无法解释“活人看不见死者”的隔离，轮回叙事崩塌。
- `gameplay-slices.md` 切片 5 明确指出：
  > “代码未实现‘鬼魂干扰阳间’机制（无 poltergeist 类 condition），是未实现的扩展点。”
  这说明 LPC 中鬼魂态本身是一个**未充分实现的 stub**，不是已验证的玩法。`modern-design-review.md` 将其列为“保留”，论证仅一句“有趣的探索机制”，未引用任何围绕鬼魂态的实际玩法实现。
- `ugc-surface.md §4.3` 结论明确：“ghost 态是地府叙事的一部分，应在地府流程设计时一并考虑，不单独建。” 这否定了 `modern-design-review.md` 把 ghost 态作为独立可选机制保留的建议。

**裁决建议**：将鬼魂态从“独立保留项”改为“地府轮回设计的附属组件”，不单独保留为可选探索机制；引擎 core 需提供 ghost 组件与可见性规则。

### 4.3 地府流程本身是半成品

**补充质疑**：

- `d/death/road3.c:9-13` 的房间描述字面是 `..... 还没想到 ....`，开发者自己承认未完成。`wgargoyle.c:48-71` 的自动复活是 55 秒强制等待，期间玩家无法做任何事。`inn1.c:67-83` 的隐藏复活路径 `ask <自己id> about 回家` 无任何提示（`inn2.c` 墙上“靠自己啦”是唯一暗示）。
- 这不是一个“有民俗魅力的成熟死亡叙事”，而是一个功能未完成、交互极低、强制时长的惩罚过场。说“保留精神”等于保留一个从未实现好的设计意图。

**裁决建议**：明确 LPC 地府是“需重新设计”而非“保留精神”。白无常 55 秒强制等待应标为设计缺陷，现代设计应改为有玩家选择的地府交互（如赎罪任务减惩罚、选择复活点）。

---

## 5. 质疑五：玩家心理与留存结论是否与现代玩法建议矛盾？

### 5.1 “主动操作 + 轻惩罚”的矛盾

**矛盾点**：`modern-design-review.md §1.3` 与 `§5.3` 建议在 tick 上增加主动绝技/走位/防御操作面；`player-psychology.md §4.3` 指出默认战斗信息密度已高到可能认知过载。

**红队挑战**：

- `modern-design-review.md` 未说明“增加操作面”如何不加剧信息过载。若每 tick 玩家都要决策绝技/走位/防御，文本输出量与决策压力会同步上升。
- `player-psychology.md §6.6` 建议默认开启精简战斗描述以降低认知负荷，这与“增加主动操作”方向相反：精简描述是为了少读，主动操作是为了多决策。文本 MUD 的沉浸感来自“读文字 + 想象”，而非“高频决策”。

### 5.2 “防秒杀硬上限”与“保留 wound 上限伤害”的矛盾

**矛盾点**：`player-psychology.md §6.4` 建议引入“单次伤害不超过目标最大气血 X%”的硬上限（如 60%）；`modern-design-review.md §2.3` 同时“保留” `damage.c:39-66` 的 wound 上限伤害机制。

**红队挑战**：

- 武侠战斗的标志性体验是“高手一掌重伤”——内力深厚者的绝杀可以一击打穿上限（`eff_qi < 0` 直接 `die()`，`char.c:100-104`）。若加 60% 硬上限，该体验消失。
- `combatd.c:317` 的立方缩放（`power = level^3/3`）虽数值失控，但其设计意图正是让高手碾压低手。这是武侠世界的核心设定。
- 两者叠加的结果是：wound 机制存在但永远打不穿（被硬上限截断），`eff_qi < 0` 的死亡路径形同虚设。这不是“保留精神”，是名义保留实质废弃。

**裁决建议**：“防秒杀硬上限”与“保留 wound 上限伤害”二选一。建议保留 wound 机制，但限制立方缩放（改为受控多项式缩放）而非加硬上限——这样“高手碾压”体验保留，但不会一刀秒杀。

### 5.3 “围攻限制”与“MAX_OPPONENT 注意力分散意图”的矛盾

**矛盾点**：`modern-design-review.md §1.3` 与 `§6.1` 保留 `MAX_OPPONENT=4` 的“注意力分散”设计意图；`player-psychology.md §6.7` 建议 PvP 场景下“同一玩家最多同时被 2 名玩家攻击”。

**红队挑战**：

- 若限制到 2v1，`MAX_OPPONENT` 的“注意力分散”设计意图就不存在（2 人围攻不存在注意力分散问题）。若保留 MAX_OPPONENT 精神（多人围攻有注意力分散），就不能限制到 2v1。
- 两份文件在围攻设计上直接冲突，评审委员会必须统一裁决。

### 5.4 “use-based 成长争议大”缺乏心理证据

**矛盾点**：`modern-design-review.md §5.3` 判定 use-based 成长“争议大”，但 `player-psychology.md` 未讨论该机制对心理/留存的影响。

**红队挑战**：

- “争议大”是结论，但无证据。玩家心理专家认为死亡与随机性是主要流失源，与 use-based 成长无直接关联。现代玩法评审可能受现代 MMO 品类偏见驱动。

---

## 6. 汇总裁决建议

| # | 被质疑结论 | 质疑核心 | 裁决建议 |
|---|---|---|---|
| 1 | `modern-design-review.md §5.3`：战中不主动选招 = 最大过时点 | perform/exert 已是主动操作面；文本 MUD 核心价值是阅读招式叙事 | 降级为“可选增强项”；强化 perform/exert 丰富度 |
| 2 | `modern-design-review.md §1.3/§7.1`：tick 中无事可做 + 需走位 | guard 是张力机制；走位是品类错位 | 撤回“走位”；guard 重定性为对峙张力 |
| 3 | `modern-design-review.md §1.3`：Effect 频率应对齐普攻 | 低频播报是中毒阴险感设计；性能警告约束 | 保留稀释频率；标注为需 A/B 测试 |
| 4 | `modern-design-review.md §4.3/§6.2` + `player-psychology.md §2/§6`：轻惩罚 + 递减封顶 + 防秒杀 | 叠加后死亡无后果；魂系类比品类错位 | 改“分层惩罚”；防秒杀与重惩罚二选一 |
| 5 | `modern-design-review.md §4.3/§6.1`：鬼魂态/地府为题材包可选 | 与项目 MVP 必做基线冲突；LPC 地府是半成品 | 地府/鬼魂态作为引擎 MVP 能力实现；LPC 地府需重新设计而非保留精神 |
| 6 | `player-psychology.md §6.4` vs `modern-design-review.md §2.3`：防秒杀 vs 保留 wound | 硬上限会废弃 `eff_qi < 0` 死亡路径 | 保留 wound，限制缩放曲线而非加硬上限 |
| 7 | `player-psychology.md §6.7` vs `modern-design-review.md §1.3/§6.1`：围攻限制 vs MAX_OPPONENT | 2v1 限制与“注意力分散”意图冲突 | 评审委员会必须二选一统一裁决 |
| 8 | `modern-design-review.md §5.3`：use-based 成长争议大 | 无心理证据；技能数上限已约束挂机 | 保留 use-based 为默认，可分配点数为可选 |

---

## 附：关键证据索引

### 被质疑文件与段落

- `03-engine-insights/modern-design-review.md`：§0（方法论）、§1.3（tick/guard/Effect 频率）、§2.3（wound 保留）、§4.3（死亡惩罚/地府/鬼魂态）、§5.3（招式选择/use-based 成长）、§6.1（保留清单）、§6.2（现代化清单）、§6.3（丢弃清单）、§7.1（战斗定位）
- `03-engine-insights/player-psychology.md`：§2（死亡惩罚焦虑）、§3.1（中毒无力感）、§4.1（tick 节奏）、§4.3（信息密度）、§6（保护机制建议）
- `03-engine-insights/ugc-surface.md`：§4.3（地府创作面与 ghost 态）
- `06-engine-critique/engine-comparison.md`：模块 4/5（ghost 态 + 地府轮回缺失是 MVP 断层）
- `CLAUDE.md`：架构不变量第 4 条（子系统四档归类，死亡与轮回为 MVP 必做）、第 7 条（MVP 场景清单）

### LPC 源码证据

- 主动绝技/内功：`cmds/skill/perform.c:10-80`、`cmds/skill/exert.c:8-42`
- 招式文案与结构：`kungfu/skill/18-zhang.c:52-218`、`kungfu/skill/18-zhang.c:241-291`
- 伤害描述与状态：`adm/daemons/combatd.c:68-204`（`damage_msg`）、`adm/daemons/combatd.c:278`（`report_status`）
- 技能映射与成长：`feature/skill.c:42-78`、`feature/skill.c:166-168`、`adm/daemons/combatd.c:450`
- guard 机制：`adm/daemons/combatd.c:818-842`
- Effect 频率与性能警告：`inherit/char/char.c:54`、`inherit/char/char.c:141-144`、`feature/condition.c:15-19`
- 中毒播报：`kungfu/condition/bt_poison.c:11-26`
- 死亡惩罚：`adm/daemons/combatd.c:987-1025`、`feature/skill.c:121-147`
- 地府流程：`feature/damage.c:246-248`、`d/death/gate.c:32-36`、`d/death/gateway.c:28-37`、`d/death/road2.c:24-46`、`d/death/npc/wgargoyle.c:51-71`、`d/death/inn1.c:67-83`、`d/death/road3.c:9-13`
- 鬼魂态：`feature/damage.c:9-11`、`:246-248`、`:255-264`；`inherit/char/char.c:181-186`
- wound 上限伤与硬死路径：`feature/damage.c:39-66`、`inherit/char/char.c:100-104`
- 立方缩放：`adm/daemons/combatd.c:317`

### engine 证据

- `engine/src/openmud/death_flow.py:77-86`（`DeathPolicy` 数据驱动惩罚参数）
- `engine/src/openmud/death_flow.py:283-288`（`_drop_inventory_to_room` 掉落实现）
- `engine/src/openmud/death.py:13-18`（`DeathState` 枚举无 GHOST 态）
