# 04-combat-effect-lifecycle 调研总则

> 本次调研属于 `.scratch/research/` 下第 4 个研究主题。**主题=战斗与效果生命周期簇**：战斗系统(7) + 状态/Effect系统(31) + 死亡与轮回(39) 三系统统一调研，强调三者耦合链 **命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活**。本调研与 03-world-space 同构采用「LPC 考古为主 + 批判性对照现有 engine」模式（新引擎已建 combat.py / combat_system.py / conditions.py / death.py / death_flow.py / skills.py）。
>
> **Grilling 对齐记录**：阶段 0 由用户预填决策（镜像 03-world-space，差异点已标注），10 个 grilling 决策点均已明确指示，故跳过逐条提问；两处延伸判断经用户确认：①武功/技能层（inherit/skill + kungfu/skill + kungfu/class + engine skills.py）纳入为「命中与 effect 载体」；②红队增至 6 路（加数值与平衡风险挑战），数值平衡专家既出 Phase1 设计输入又参与红队数值挑战。

## 1. 调研目标

1. **忠实还原 LPC 原始细节**：基于当前仓库一手源码，梳理《侠客行》战斗与效果生命周期簇的实现方式、数据结构、调用链与状态流转--涵盖 attack/damage 三类伤害、condition 时效性 Effect 引擎、die/reincarnate/ghost 死亡轮回、地府区域流程、武功招式作为命中与 effect 载体。
2. **提取设计灵感与风险警示**：从现代战斗设计、玩家心理、商业化（战斗付费/pay-to-win 红线）、性能（战斗 tick 并发开销）、数值平衡角度，输出对新引擎可参考的方向、应避免的过时模式与需警惕的设计陷阱。
3. **批判性对照现有 engine**：审阅 `engine/src/openmud/` 下 combat.py / combat_system.py / conditions.py / death.py / death_flow.py / skills.py，标注与 LPC 原始设计的偏差与遗漏。engine 模块**仅作批判对照对象，不作反向脑补来源**；LPC 才是唯一真相源。
4. **不输出 engine 接口草案**：本次调研止步于设计输入层，具体 engine 抽象与接口设计留待后续任务单独决策。

## 2. 范围边界

### 2.1 纳入范围

**战斗系统（命中 -> 伤害）**
- `feature/attack.c`（258 行）：`enemy`/`killer` 列表、`fight_ob`/`is_fighting`/`is_killing`、`attack()`、`MAX_OPPONENT=4`，调用 `S_COMBATD`。
- `feature/damage.c`（331 行）：`receive_damage(type, damage, who)`/`receive_wound(type, damage, who)` 三类伤害（jing 精 / qi 气 / jingli 精力）、`set_temp("last_damage_from", who)` 伤害来源、`set_heart_beat(1)`、`ghost` 标志、`die()`（:152）、`reincarnate()`（:255）、`is_ghost()`。
- `feature/skill.c`（183 行）、`feature/team.c`（127 行：组队）、`feature/equip.c`（140 行：装备）。
- `inherit/char/char.c`：`heart_beat()` 战斗循环驱动（:101-113 `remove_all_enemy`/`die`/`unconcious`/`attack` 调用、:107-113 昏迷 vs 死亡判定）。
- `inherit/char/trainee.c`（NPC 战斗 AI：`revive`/`biting`/`do_yao attack`）。
- `adm/daemons/combatd.c` + `s_combatd.c`：战斗 daemon（命中/伤害结算核心）。
- 命令 `cmds/std/`：`kill.c`/`fight.c`/`hit.c`/`forcekill.c`/`wield.c`/`unwield.c`/`wear.c`/`remove.c`/`eat.c`。

**状态/Effect 系统（状态播报）**
- `feature/condition.c`（113 行）：`conditions` mapping、`update_condition()` 由 `heart_beat` 驱动、`CONDITION_D` 外部 daemon 调用（每个 condition 是独立 daemon）。
- `kungfu/condition/`（~30+ condition，即 Effect 内容层）：`aphroclisiac`（春药）、`*_poison`（各类毒：`bt_poison`/`chilian_poison`/`hsf_poison`/`huadu_poison`/`insect_poison`）、`*_damage`（伤害：`hanbing_damage`/`jiujian_qi_damage`/`juehu_damage`/`hyz_damage`）、`drunk`（醉）、`blind`（盲）、`embedded`（嵌入暗器）、`*_jail`（牢：`city_jail`/`dali_jail`/`bonze_jail`）、`bandaged`（包扎）等。

**死亡与轮回（死亡判定 -> 复活）**
- `feature/damage.c:die()`/`reincarnate()`/`ghost`：死亡判定 + 鬼魂态 + 轮回复活。
- `d/death/`（地府区 ~580 行）：`gate`/`gateway`/`hell`/`inn1`/`inn2`/`road1-3`/`noteroom`/`blkbot`/`block`/`death`--玩家死后变鬼进入地府走轮回流程。
- `inherit/char/char.c` heart_beat 中的 `die`/`unconcious` 判定。

**武功/技能层（命中来源与 effect 载体）**
- `inherit/skill/`：`skill.c`/`skill2.c`/`force.c`/`temp.c`（技能基类）。
- `kungfu/skill/`：大量武功（`18-zhang` 降龙十八掌 / `6mai-shenjian` 六脉神剑 / `beiming-shengong` 北冥神功 / `archery` 射箭 / `blade`/`sword`/`axe` 各兵器招式…）。
- `kungfu/class/`：门派武功集（`baituo`/`dali`/`emei`/`gaibang`/`gumu`/`huashan`/`lingjiu`/`mingjiao`/`murong`…）。

**装备（战斗数值）**
- `inherit/weapon/`：15 类（`_sword`/`_blade`/`_axe`/`_bow`/`_club`/`_dagger`/`_fork`/`_halberd`/`_hammer`/`_hook`/`_pike`/`_staff`/`_stick`/`_whip` + `throwing`）。
- `inherit/armor/`：`armor`/`boots`/`cloth`/`finger`/`hands`/`head`/`neck`/`shield`/`surcoat`/`waist`/`wrists`。

### 2.2 不纳入范围

- 不做 LPC 行为等价验证（[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）。
- 不把 engine 侧现有实现当作正确形态反向脑补（engine 仅作批判对照）。
- 不依赖旧文档结论（`docs/archive/` 仅作必要时二手参考）。
- 不输出可直接落地的 engine 代码或接口契约。
- 不纳入具体武功招式的文学性设计（招式名/描述文案），只调研机制与结构。
- 不深入门派阵营系统的社交/组织机制（仅武功招式归属门派这一映射关系）。

## 3. 调研团队与职责（13 席 Phase1 + 6 路红队 + 评审委员会）

### 3.1 一手考古组

| 角色 | 职责 | 产出 |
|------|------|------|
| LPC 源码考古员 | 逐目录盘点战斗/Effect/死亡/武功相关源码，输出代码清单、调用链、数据结构、关键回调与状态变量 | `01-raw-findings/source-inventory.md` |
| 玩法切片策划 | 挑 4-6 类代表性玩法切片（如普攻对砍、武功绝技爆发、中毒持续掉血、昏迷与苏醒、玩家死亡下地府走轮回、组队围攻） | `01-raw-findings/gameplay-slices.md`、`02-user-stories/player-stories.md` |

### 3.2 机制抽象组

| 角色 | 职责 | 产出 |
|------|------|------|
| 战斗/效果机制设计师 | 抽象通用机制：交战/敌对列表、命中/伤害结算（三类伤害）、Effect 时效引擎、状态播报、死亡两段式判定、鬼魂/轮回复活、武功招式调度 | `01-raw-findings/mechanisms.md`、`02-user-stories/system-stories.md` |
| 引擎架构师 A | 把通用机制映射到题材无关 engine 核心，输出抽象方案与可选方向 | `03-engine-insights/abstraction-options.md` |
| 引擎架构师 B | 思考题材包（UGC）创作层应暴露的最小表面（创作者如何定义武功/招式/Effect/死亡惩罚/复活点） | `03-engine-insights/ugc-surface.md` |
| UGC 游戏专家 | 从创作者视角审视战斗/Effect 可扩展性（配招式、挂 Effect、调数值、设死亡惩罚） | `03-engine-insights/creator-perspective.md`、`02-user-stories/operator-stories.md` |
| 横向对比验证员（红队） | 交叉检查各战斗/Effect/死亡实现与抽象方案，找共用模式与特例，验证覆盖度 | `04-redteam-review/cross-check-report.md` |

### 3.3 现代评审组

| 角色 | 职责 | 产出 |
|------|------|------|
| 现代战斗玩法设计师 | 对标现代 MMO/动作战斗/手游战斗，评估 LPC 战斗节奏、回合 vs tick、招式手感、过时风险 | `03-engine-insights/modern-design-review.md`、`04-redteam-review/modern-challenges.md` |
| 玩家心理与留存专家 | 战斗挫败、死亡惩罚焦虑、中毒/被控无力感、心流节奏、PvP 社交压力 | `03-engine-insights/player-psychology.md`、`04-redteam-review/player-experience-risks.md` |
| 商业化与增长专家 | 战斗付费点、pay-to-win 红线、武功/装备作为题材包资产、消费埋点 | `03-engine-insights/commercialization.md`、`04-redteam-review/commercial-risks.md` |
| 性能与可扩展性专家 | 战斗 tick 并发开销、Effect 遍历开销、全员战斗广播、1000 在线峰值、heart_beat 密度 | `03-engine-insights/performance-review.md`、`04-redteam-review/performance-risks.md` |
| 数值平衡专家 | 伤害公式/命中率/数值缩放、PvE/PvP 平衡、付费数值红线、LPC 数值体系批判 | `03-engine-insights/numerical-balance.md`、`04-redteam-review/numerical-risks.md` |

### 3.4 终审组（评审委员会，5 人）

玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代战斗玩法设计师 + 商业化与增长专家。

职责：审阅所有初稿与红队报告 -> 组织对抗 -> 对分歧裁决 -> 统一文风、消除矛盾 -> 生成最终报告。

### 3.5 engine 批判对照员（06-engine-critique 层）

逐项对照现有 engine 6 模块与 LPC 原始设计，产出 `06-engine-critique/engine-comparison.md`。

## 4. 调研方法

### 4.1 多 Agent 并行 Workflow（三阶段）

- **Phase 1：并行初稿**（12 席）：各角色同步阅读源码并产出指定章节初稿。一手考古组与机制抽象组先跑，现代评审组同时跑（基于源码而非初稿，避免 barrier 等待）；engine 批判对照员同阶段产出 06 层。
- **Phase 2：红队对抗**（6 路并行）：横向对比验证、现代玩法挑战、体验风险挑战、商业化风险挑战、性能风险挑战、数值平衡风险挑战。每条质疑必须引用被质疑文件与段落。
- **Phase 3：评审委员会汇总**（1 个 xhigh agent）：统一文风、消除矛盾、对红队质疑裁决、标注未决问题，生成最终报告。

### 4.2 资料来源优先级

1. 当前仓库根目录下 LPC 源码（`feature/attack.c`/`damage.c`/`condition.c`/`skill.c`/`team.c`/`equip.c`、`inherit/char/`、`inherit/skill/`、`inherit/weapon/`/`armor/`、`adm/daemons/combatd.c`/`s_combatd.c`、`kungfu/condition/`、`kungfu/skill/`、`kungfu/class/`、`d/death/`、`cmds/std/`）--**唯一真相源**。
2. `engine/src/openmud/` 下已建模块（combat.py / combat_system.py / conditions.py / death.py / death_flow.py / skills.py）--**仅作批判对照对象**（产出在 `06-engine-critique/`）。
3. `docs/archive/` 与 `.scratch/` 下既有调研（如 m1/m2 票、03-world-space）--必要时二手参考。

## 5. 输出目录结构（7 层）

```
.scratch/research/04-combat-effect-lifecycle/
├── 00-brief/               # 本总则
├── 01-raw-findings/        # source-inventory / gameplay-slices / mechanisms
├── 02-user-stories/        # player / operator-wizard / system-auto（三层全覆盖）
├── 03-engine-insights/     # abstraction-options / ugc-surface / modern-design-review
│                           # / player-psychology / commercialization / performance-review
│                           # / creator-perspective / numerical-balance
├── 04-redteam-review/      # cross-check / modern-challenges / player-experience-risks
│                           # / commercial-risks / performance-risks / numerical-risks
├── 05-synthesis/           # final-report.md
└── 06-engine-critique/     # 逐项对照 combat.py/combat_system.py/conditions.py/death.py
                            # /death_flow.py/skills.py 与 LPC 设计
```

## 6. 关键约束

- **基于一手资料**：所有结论必须能从当前仓库源码中找到证据（标注文件路径 + 函数/对象名）。
- **全局与细节兼顾**：既要有宏观脉络（三类伤害 / Effect 时效引擎 / 两段式死亡 / 地府轮回 / 武功招式调度），也要有代表性实例细节（attack.c 的 MAX_OPPONENT、damage.c 的 die/reincarnate、condition.c 的 update_condition、d/death 的地府流程）。
- **现代视角批判**：对过时、不符合当代玩家习惯或商业化潜力的设计显式标注。
- **engine 对照可证伪**：每条 engine 偏差/遗漏标注必须同时给出 LPC 证据与 engine 模块位置。特别注意 `conditions.py` 概念错位（通用布尔求值引擎 vs LPC 时效性 Effect 引擎）这一关键偏差。
- **User Stories 完整**：覆盖玩家、巫师/运营、系统/NPC 自动触发三层。
- **数值平衡显性化**：战斗重度依赖数值，数值平衡专家与数值风险红队须显式评估伤害公式/命中率/缩放/付费数值红线。
